"""
Highlight service (specs/phase-2-highlights.md).

Highlights are what a user deliberately chose to represent their taste: up to
15 tracks, albums, artists or Spotify playlists, public by default as a
recorded constitutional exception. That exception holds only because every
highlight is added one at a time by explicit action — nothing here ever
creates one on a user's behalf.

Attached reviews come from rating_svc.latest_visible_reviews, so who may see a
review is decided in one place and a public highlight never publishes a
review its author kept private.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.background import run_exclusive
from app.core.enums import HighlightType, VisibilityScope
from app.core.visibility import scope_allows
from app.models.catalog import Album, Artist, Track
from app.models.highlight import Highlight
from app.models.rating import Rating
from app.models.spotify import SpotifyConnection
from app.models.user import User
from app.schemas.highlight import (
    AddHighlightRequest,
    HighlightItem,
    HighlightReview,
    HighlightsResponse,
    PlaylistOption,
    PlaylistPickerResponse,
)
from app.services import friendship as friendship_svc
from app.services import rating as rating_svc
from app.services import spotify as spotify_svc

logger = logging.getLogger(__name__)

LIMIT = 15
PROVIDER = "spotify"
# How stale a playlist card may get before a view refreshes it from Spotify
# in the background. The card follows the provider live (Founder decision
# 2026-09-27) without a profile ever waiting on Spotify.
_PLAYLIST_REFRESH_AFTER = timedelta(minutes=10)
_refreshing: set[uuid.UUID] = set()

ERR_LIMIT = f"You have {LIMIT} highlights. Remove one to add another."
ERR_NOT_FOUND = "We couldn't find that in the catalog."
ERR_PLAYLIST = "That playlist isn't available to highlight."
ERR_PLAYLIST_ACCESS = "Allow Harmoniq to read your Spotify playlists first."
ERR_PLAYLISTS_OFF = "Playlist highlights aren't available right now."
ERR_SPOTIFY = "Couldn't reach Spotify. Try again in a moment."

_CATALOG: dict[str, Any] = {
    HighlightType.TRACK.value: Track,
    HighlightType.ALBUM.value: Album,
    HighlightType.ARTIST.value: Artist,
}
_SPOTIFY_FAILURES = (
    spotify_svc.SpotifyNotConnectedError,
    spotify_svc.SpotifyAPIError,
    spotify_svc.SpotifyNotConfiguredError,
    httpx.HTTPError,
)


class HighlightError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _playlist_url(playlist_id: str) -> str:
    return f"https://open.spotify.com/playlist/{playlist_id}"


def _playlists_shown(conn: SpotifyConnection | None) -> bool:
    return (
        settings.playlist_highlights_enabled
        and conn is not None
        and spotify_svc.has_playlist_access(conn)
    )


# ── Reads ─────────────────────────────────────────────────────────────────────


async def can_view(session: AsyncSession, owner: User, viewer: User | None) -> bool:
    is_owner = viewer is not None and viewer.id == owner.id
    scope = VisibilityScope(owner.visibility_highlights)
    is_friend = False
    if not is_owner and viewer is not None and scope == VisibilityScope.FRIENDS:
        is_friend = await friendship_svc.are_friends(session, viewer.id, owner.id)
    return scope_allows(scope, is_owner=is_owner, is_friend=is_friend)


async def _rows(session: AsyncSession, owner_id: uuid.UUID) -> list[Highlight]:
    result = await session.execute(
        select(Highlight)
        .where(Highlight.user_id == owner_id)
        .order_by(Highlight.created_at, Highlight.id)
    )
    return list(result.scalars())


def _review(rating: Rating, *, of_album: bool = False) -> HighlightReview:
    return HighlightReview(
        score=rating.score, review_text=rating.review_text, of_album=of_album
    )


async def _items(
    session: AsyncSession,
    owner: User,
    viewer: User | None,
    rows: list[Highlight],
    conn: SpotifyConnection | None,
) -> list[HighlightItem]:
    ids: dict[str, list[uuid.UUID]] = {kind: [] for kind in _CATALOG}
    for row in rows:
        if row.entity_id is not None and row.entity_type in ids:
            ids[row.entity_type].append(row.entity_id)

    tracks: dict[uuid.UUID, Any] = {}
    if ids["track"]:
        result = await session.execute(
            select(Track, Artist.name, Album.cover_art_url)
            .outerjoin(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .where(Track.id.in_(ids["track"]))
        )
        tracks = {track.id: (track, artist, cover) for track, artist, cover in result}
    albums: dict[uuid.UUID, Any] = {}
    if ids["album"]:
        result = await session.execute(
            select(Album, Artist.name)
            .outerjoin(Artist, Artist.id == Album.artist_id)
            .where(Album.id.in_(ids["album"]))
        )
        albums = {album.id: (album, artist) for album, artist in result}
    artists: dict[uuid.UUID, Artist] = {}
    if ids["artist"]:
        result = await session.execute(
            select(Artist).where(Artist.id.in_(ids["artist"]))
        )
        artists = {artist.id: artist for artist in result.scalars()}

    # Reviews: the item's own, or — for a track the owner never reviewed —
    # its album's. Each is checked against its own visibility.
    wanted: list[tuple[str, uuid.UUID]] = []
    for track, _, _ in tracks.values():
        wanted.append(("track", track.id))
        if track.album_id is not None:
            wanted.append(("album", track.album_id))
    wanted += [("album", album_id) for album_id in albums]
    visible, reviewed = await rating_svc.latest_visible_reviews(
        session, owner, viewer.id if viewer else None, wanted
    )

    items: list[HighlightItem] = []
    for row in rows:
        kind = row.entity_type
        if kind == HighlightType.TRACK.value and row.entity_id in tracks:
            track, artist_name, cover = tracks[row.entity_id]
            review = None
            if ("track", track.id) in reviewed:
                own = visible.get(("track", track.id))
                review = _review(own) if own else None
            elif track.album_id is not None:
                album_review = visible.get(("album", track.album_id))
                review = _review(album_review, of_album=True) if album_review else None
            items.append(
                HighlightItem(
                    id=row.id,
                    entity_type=HighlightType.TRACK,
                    title=track.title,
                    subtitle=artist_name,
                    image_url=cover,
                    mbid=track.mbid,
                    review=review,
                )
            )
        elif kind == HighlightType.ALBUM.value and row.entity_id in albums:
            album, artist_name = albums[row.entity_id]
            own = visible.get(("album", album.id))
            items.append(
                HighlightItem(
                    id=row.id,
                    entity_type=HighlightType.ALBUM,
                    title=album.title,
                    subtitle=artist_name,
                    image_url=album.cover_art_url,
                    mbid=album.mbid,
                    review=_review(own) if own else None,
                )
            )
        elif kind == HighlightType.ARTIST.value and row.entity_id in artists:
            artist = artists[row.entity_id]
            items.append(
                HighlightItem(
                    id=row.id,
                    entity_type=HighlightType.ARTIST,
                    title=artist.name,
                    image_url=artist.image_url,
                    mbid=artist.mbid,
                )
            )
        elif (
            kind == HighlightType.PLAYLIST.value
            and _playlists_shown(conn)
            and row.provider_ref
            and row.display_name
        ):
            items.append(
                HighlightItem(
                    id=row.id,
                    entity_type=HighlightType.PLAYLIST,
                    title=row.display_name,
                    subtitle="Spotify playlist",
                    image_url=row.display_image_url,
                    external_url=_playlist_url(row.provider_ref),
                    provider="spotify",
                )
            )
        # Anything else — a vanished catalog entity, or a playlist whose grant
        # has ended or whose feature is off — simply doesn't render.
    return items


async def list_for(
    session: AsyncSession, owner: User, viewer: User | None
) -> tuple[HighlightsResponse | None, bool]:
    """(response, playlists_need_refresh). None when the viewer may not see
    this owner's highlights — decided before anything is read."""
    if not await can_view(session, owner, viewer):
        return None, False
    rows = await _rows(session, owner.id)
    conn = await spotify_svc.get_connection(session, owner.id)
    items = await _items(session, owner, viewer, rows, conn)
    is_owner = viewer is not None and viewer.id == owner.id
    stale_before = _now() - _PLAYLIST_REFRESH_AFTER
    needs_refresh = _playlists_shown(conn) and any(
        row.entity_type == HighlightType.PLAYLIST.value
        and (
            row.display_refreshed_at is None or row.display_refreshed_at < stale_before
        )
        for row in rows
    )
    return (
        HighlightsResponse(
            items=items,
            limit=LIMIT,
            visibility=VisibilityScope(owner.visibility_highlights)
            if is_owner
            else None,
            playlists_available=settings.playlist_highlights_enabled
            if is_owner
            else None,
        ),
        needs_refresh,
    )


# ── Writes ────────────────────────────────────────────────────────────────────


async def _lock_owner(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Serialize adds per user so two tabs can't both take the 15th slot.
    Returns the slots in use: playlist rows count only while they render, so
    a switched-off feature can't fill slots with highlights nobody sees."""
    await session.execute(select(User.id).where(User.id == user_id).with_for_update())
    counted = select(func.count()).select_from(Highlight)
    counted = counted.where(Highlight.user_id == user_id)
    if not _playlists_shown(await spotify_svc.get_connection(session, user_id)):
        counted = counted.where(Highlight.entity_type != HighlightType.PLAYLIST.value)
    return int((await session.execute(counted)).scalar_one())


async def _item_for(session: AsyncSession, user: User, row: Highlight) -> HighlightItem:
    conn = await spotify_svc.get_connection(session, user.id)
    (item,) = await _items(session, user, user, [row], conn)
    return item


async def add(
    session: AsyncSession, user: User, req: AddHighlightRequest
) -> HighlightItem:
    """One explicit highlight. Idempotent for something already highlighted."""
    if req.entity_type == HighlightType.PLAYLIST:
        return await _add_playlist(session, user, req.playlist_id or "")
    model = _CATALOG[req.entity_type.value]
    entity_id = (
        await session.execute(select(model.id).where(model.mbid == (req.mbid or "")))
    ).scalar_one_or_none()
    if entity_id is None:
        raise HighlightError(ERR_NOT_FOUND, 404)
    count = await _lock_owner(session, user.id)
    existing = (
        await session.execute(
            select(Highlight).where(
                Highlight.user_id == user.id,
                Highlight.entity_type == req.entity_type.value,
                Highlight.entity_id == entity_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return await _item_for(session, user, existing)
    if count >= LIMIT:
        raise HighlightError(ERR_LIMIT, 409)
    row = Highlight(
        user_id=user.id,
        entity_type=req.entity_type.value,
        entity_id=entity_id,
        created_at=_now(),
    )
    session.add(row)
    await session.flush()
    logger.info(
        "Highlight added: user_id=%s type=%s entity_id=%s",
        user.id,
        req.entity_type.value,
        entity_id,
    )
    return await _item_for(session, user, row)


async def _add_playlist(
    session: AsyncSession, user: User, playlist_id: str
) -> HighlightItem:
    if not settings.playlist_highlights_enabled:
        raise HighlightError(ERR_PLAYLISTS_OFF, 404)
    conn = await spotify_svc.get_connection(session, user.id)
    if conn is None or not spotify_svc.has_playlist_access(conn):
        raise HighlightError(ERR_PLAYLIST_ACCESS, 403)
    try:
        display = await spotify_svc.get_owned_playlist(session, conn, playlist_id)
    except _SPOTIFY_FAILURES as exc:
        logger.warning("Playlist highlight lookup failed user_id=%s: %s", user.id, exc)
        raise HighlightError(ERR_SPOTIFY, 503) from exc
    if display is None:
        raise HighlightError(ERR_PLAYLIST, 404)
    count = await _lock_owner(session, user.id)
    existing = (
        await session.execute(
            select(Highlight).where(
                Highlight.user_id == user.id,
                Highlight.provider == PROVIDER,
                Highlight.provider_ref == display["id"],
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return await _item_for(session, user, existing)
    if count >= LIMIT:
        raise HighlightError(ERR_LIMIT, 409)
    row = Highlight(
        user_id=user.id,
        entity_type=HighlightType.PLAYLIST.value,
        provider=PROVIDER,
        provider_ref=display["id"],
        display_name=display["name"],
        display_image_url=display["image_url"],
        display_refreshed_at=_now(),
        created_at=_now(),
    )
    session.add(row)
    await session.flush()
    logger.info("Highlight added: user_id=%s type=playlist", user.id)
    return await _item_for(session, user, row)


async def remove(session: AsyncSession, user: User, highlight_id: uuid.UUID) -> None:
    await session.execute(
        delete(Highlight).where(
            Highlight.id == highlight_id, Highlight.user_id == user.id
        )
    )
    logger.info("Highlight removed: user_id=%s id=%s", user.id, highlight_id)


# ── Playlists ─────────────────────────────────────────────────────────────────


async def playlist_options(session: AsyncSession, user: User) -> PlaylistPickerResponse:
    if not settings.playlist_highlights_enabled:
        return PlaylistPickerResponse(status="unavailable")
    conn = await spotify_svc.get_connection(session, user.id)
    if conn is None:
        return PlaylistPickerResponse(status="not_connected")
    if not spotify_svc.has_playlist_access(conn):
        return PlaylistPickerResponse(status="needs_permission")
    try:
        playlists = await spotify_svc.list_owned_playlists(session, conn)
    except spotify_svc.SpotifyNotConnectedError:
        return PlaylistPickerResponse(status="not_connected")
    except _SPOTIFY_FAILURES:
        logger.exception("Playlist list failed user_id=%s", user.id)
        return PlaylistPickerResponse(status="unavailable")
    chosen = set(
        (
            await session.execute(
                select(Highlight.provider_ref).where(
                    Highlight.user_id == user.id, Highlight.provider == PROVIDER
                )
            )
        ).scalars()
    )
    return PlaylistPickerResponse(
        status="ok",
        playlists=[
            PlaylistOption(
                id=p["id"],
                name=p["name"],
                image_url=p["image_url"],
                highlighted=p["id"] in chosen,
            )
            for p in playlists
        ],
    )


async def refresh_playlists(session: AsyncSession, owner_id: uuid.UUID) -> None:
    """Bring playlist cards up to date with Spotify. A playlist that's gone or
    no longer theirs is removed; an outage or refusal changes nothing and is
    retried after the next staleness window."""
    conn = await spotify_svc.get_connection(session, owner_id)
    if conn is None or not _playlists_shown(conn):
        return
    rows = [
        row
        for row in await _rows(session, owner_id)
        if row.entity_type == HighlightType.PLAYLIST.value and row.provider_ref
    ]
    for index, row in enumerate(rows):
        try:
            display = await spotify_svc.get_owned_playlist(
                session, conn, row.provider_ref or ""
            )
        except _SPOTIFY_FAILURES:
            # Spotify is struggling: stop here rather than spend a call per
            # remaining card, and treat them as checked so the next view
            # doesn't retry at once. Their cards keep the last-known display.
            logger.info("Playlist refresh deferred: owner_id=%s", owner_id)
            for waiting in rows[index:]:
                waiting.display_refreshed_at = _now()
            break
        if display is None:
            await session.delete(row)
            logger.info("Playlist highlight removed (gone): highlight_id=%s", row.id)
            continue
        row.display_name = display["name"]
        row.display_image_url = display["image_url"]
        row.display_refreshed_at = _now()
    await session.flush()


async def refresh_playlists_in_background(owner_id: uuid.UUID) -> None:
    """After the response, on its own session; one at a time per owner."""

    async def work(session: AsyncSession) -> None:
        await refresh_playlists(session, owner_id)

    await run_exclusive(_refreshing, owner_id, work, "playlist refresh")


async def first_party_highlights(
    session: AsyncSession, user_id: uuid.UUID
) -> list[Highlight]:
    """The ONLY accessor recommendation code may use for highlights. Playlist
    highlights are provider-backed, and Spotify forbids using its data to
    inform recommendations, so they are unreachable through it by
    construction (specs/phase-2-highlights.md, "The ToS boundary")."""
    rows = await session.execute(
        select(Highlight).where(
            Highlight.user_id == user_id,
            Highlight.entity_type != HighlightType.PLAYLIST.value,
            Highlight.provider.is_(None),
        )
    )
    return list(rows.scalars())
