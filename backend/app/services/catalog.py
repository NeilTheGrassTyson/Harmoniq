"""
Catalog service: ingestion, upsert, and data retrieval for music entities.

All three entity types (artist, album, track) are keyed on their MusicBrainz ID
(MBID) which is stored as a unique index alongside an internal UUID primary key.
Ingestion is always upsert-on-MBID: existing rows are updated, not duplicated.
"""

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.musicbrainz as mb
import app.services.rating as rating_svc
from app.models.catalog import Album, Artist, Track
from app.schemas.catalog import (
    AlbumDetail,
    AlbumResult,
    ArtistDetail,
    ArtistResult,
    SearchResponse,
    TrackDetail,
    TrackResult,
)
from app.services import user as user_svc

logger = logging.getLogger(__name__)

_SEARCH_CACHE_TTL = 300.0  # 5 minutes — matches MB client TTL
_search_cache: dict[str, tuple[float, SearchResponse]] = {}

_CAA_URL = "https://coverartarchive.org/release-group/{mbid}/front"

_ALBUM_TYPE_MAP: dict[str, str] = {
    "album": "album",
    "single": "single",
    "ep": "ep",
    "compilation": "compilation",
    "broadcast": "other",
    "other": "other",
}


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _parse_release_year(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        return int(date_str[:4])
    except (ValueError, IndexError):
        return None


def _primary_artist_name(raw: dict[str, Any]) -> str | None:
    artist_credits = raw.get("artist-credit", [])
    if artist_credits and isinstance(artist_credits[0], dict):
        artist = artist_credits[0].get("artist", {})
        return artist.get("name")  # type: ignore[no-any-return]
    return None


def _primary_artist_mbid(raw: dict[str, Any]) -> str | None:
    artist_credits = raw.get("artist-credit", [])
    if artist_credits and isinstance(artist_credits[0], dict):
        return artist_credits[0].get("artist", {}).get("id")  # type: ignore[no-any-return]
    return None


def _release_group_mbid(raw_recording: dict[str, Any]) -> str | None:
    """Extract the canonical release-group MBID from a recording."""
    releases = raw_recording.get("releases", [])
    if not releases:
        return None
    rg = releases[0].get("release-group", {})
    return rg.get("id")  # type: ignore[no-any-return]


# ── Upsert helpers ─────────────────────────────────────────────────────────────


async def _upsert_artist(session: AsyncSession, raw: dict[str, Any]) -> Artist:
    mbid: str = raw["id"]
    now = _now()

    result = await session.execute(select(Artist).where(Artist.mbid == mbid))
    artist = result.scalar_one_or_none()

    name = raw.get("name") or ""
    sort_name = raw.get("sort-name") or None
    disambiguation = raw.get("disambiguation") or None

    if artist is None:
        artist = Artist(
            id=uuid.uuid4(),
            mbid=mbid,
            name=name,
            sort_name=sort_name,
            disambiguation=disambiguation,
            image_url=None,
            last_fetched_at=now,
        )
        session.add(artist)
    else:
        artist.name = name
        artist.sort_name = sort_name
        artist.disambiguation = disambiguation
        artist.last_fetched_at = now

    return artist


async def _upsert_album(
    session: AsyncSession,
    raw: dict[str, Any],
    artist_id: uuid.UUID | None = None,
) -> Album:
    mbid: str = raw["id"]
    now = _now()

    result = await session.execute(select(Album).where(Album.mbid == mbid))
    album = result.scalar_one_or_none()

    title = raw.get("title") or ""
    raw_type = (raw.get("primary-type") or "").lower()
    album_type = _ALBUM_TYPE_MAP.get(raw_type, "other") if raw_type else None
    release_year = _parse_release_year(raw.get("first-release-date") or raw.get("date"))
    cover_art_url = _CAA_URL.format(mbid=mbid)

    if album is None:
        album = Album(
            id=uuid.uuid4(),
            mbid=mbid,
            title=title,
            artist_id=artist_id,
            release_year=release_year,
            album_type=album_type,
            cover_art_url=cover_art_url,
            last_fetched_at=now,
        )
        session.add(album)
    else:
        album.title = title
        album.release_year = release_year
        album.album_type = album_type
        album.cover_art_url = cover_art_url
        album.last_fetched_at = now
        if artist_id is not None and album.artist_id is None:
            album.artist_id = artist_id

    return album


async def _upsert_track(
    session: AsyncSession,
    raw: dict[str, Any],
    artist_id: uuid.UUID | None = None,
    album_id: uuid.UUID | None = None,
) -> Track:
    mbid: str = raw["id"]
    now = _now()

    result = await session.execute(select(Track).where(Track.mbid == mbid))
    track = result.scalar_one_or_none()

    title = raw.get("title") or ""
    duration_ms: int | None = raw.get("length")

    if track is None:
        track = Track(
            id=uuid.uuid4(),
            mbid=mbid,
            title=title,
            artist_id=artist_id,
            album_id=album_id,
            duration_ms=duration_ms,
            track_number=None,
            disc_number=None,
            last_fetched_at=now,
        )
        session.add(track)
    else:
        track.title = title
        track.duration_ms = duration_ms
        track.last_fetched_at = now
        if artist_id is not None and track.artist_id is None:
            track.artist_id = artist_id
        if album_id is not None and track.album_id is None:
            track.album_id = album_id

    return track


# ── Artist resolution helper ───────────────────────────────────────────────────


async def _resolve_artist_id(
    session: AsyncSession, artist_mbid: str | None, raw_artist: dict[str, Any] | None
) -> uuid.UUID | None:
    """
    Given a MusicBrainz artist MBID, return the internal UUID, ingesting the
    artist if needed. Returns None when the MBID is absent.
    """
    if not artist_mbid:
        return None
    result = await session.execute(select(Artist).where(Artist.mbid == artist_mbid))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing.id
    if raw_artist:
        ingested = await _upsert_artist(session, raw_artist)
        return ingested.id
    return None


# ── Search ─────────────────────────────────────────────────────────────────────


async def search_and_ingest(query: str, session: AsyncSession) -> SearchResponse:
    cache_key = query.strip().lower()
    cached = _search_cache.get(cache_key)
    if cached is not None:
        cached_at, response = cached
        if time.monotonic() - cached_at < _SEARCH_CACHE_TTL:
            logger.debug("search cache hit: %s", cache_key)
            return response
        logger.debug("search cache stale: %s", cache_key)

    raw_artists: list[dict[str, Any]] = []
    raw_albums: list[dict[str, Any]] = []
    raw_tracks: list[dict[str, Any]] = []
    try:
        raw_artists = await mb.search_artists(query)
        raw_albums = await mb.search_release_groups(query)
        raw_tracks = await mb.search_recordings(query)
    except Exception:
        logger.exception("MusicBrainz search failed for query (redacted in prod)")
        raise

    # Strip MusicBrainz "Special Purpose" housekeeping entries ([unknown],
    # [no artist], etc.) — they degrade search quality and are never real artists.
    raw_artists = [
        a for a in raw_artists
        if a.get("type") != "Special Purpose"
        and not (a.get("name", "").startswith("[") and a.get("name", "").endswith("]"))
    ]

    # ── Ingest artists ────────────────────────────────────────────────────────
    artist_rows: list[Artist] = []
    for raw in raw_artists:
        try:
            artist_rows.append(await _upsert_artist(session, raw))
        except Exception:
            logger.error(
                "Failed to ingest artist mbid=%s", raw.get("id"), exc_info=True
            )

    # ── Ingest albums ─────────────────────────────────────────────────────────
    album_rows: list[Album] = []
    for raw in raw_albums:
        try:
            artist_mbid = _primary_artist_mbid(raw)
            raw_artist_credit = (
                raw.get("artist-credit", [{}])[0].get("artist")
                if raw.get("artist-credit")
                else None
            )
            artist_id = await _resolve_artist_id(
                session, artist_mbid, raw_artist_credit
            )
            album_rows.append(await _upsert_album(session, raw, artist_id))
        except Exception:
            logger.error("Failed to ingest album mbid=%s", raw.get("id"), exc_info=True)

    # ── Ingest tracks ─────────────────────────────────────────────────────────
    track_rows: list[Track] = []
    for raw in raw_tracks:
        try:
            artist_mbid = _primary_artist_mbid(raw)
            raw_artist_credit = (
                raw.get("artist-credit", [{}])[0].get("artist")
                if raw.get("artist-credit")
                else None
            )
            artist_id = await _resolve_artist_id(
                session, artist_mbid, raw_artist_credit
            )

            rg_mbid = _release_group_mbid(raw)
            album_id: uuid.UUID | None = None
            if rg_mbid:
                alb_result = await session.execute(
                    select(Album).where(Album.mbid == rg_mbid)
                )
                alb = alb_result.scalar_one_or_none()
                album_id = alb.id if alb else None

            track_rows.append(await _upsert_track(session, raw, artist_id, album_id))
        except Exception:
            logger.error("Failed to ingest track mbid=%s", raw.get("id"), exc_info=True)

    await session.flush()

    # ── Build response from raw MB data (no extra DB round-trip) ─────────────
    artist_results = [
        ArtistResult(
            mbid=a.get("id", ""),
            name=a.get("name", ""),
            disambiguation=a.get("disambiguation") or None,
            image_url=None,
        )
        for a in raw_artists
    ]

    album_results = [
        AlbumResult(
            mbid=a.get("id", ""),
            title=a.get("title", ""),
            artist_name=_primary_artist_name(a),
            release_year=_parse_release_year(a.get("first-release-date")),
            cover_art_url=_CAA_URL.format(mbid=a.get("id", "")),
        )
        for a in raw_albums
    ]

    track_results = [
        TrackResult(
            mbid=t.get("id", ""),
            title=t.get("title", ""),
            artist_name=_primary_artist_name(t),
            album_title=(
                t.get("releases", [{}])[0].get("title") if t.get("releases") else None
            ),
            album_mbid=_release_group_mbid(t),
            duration_ms=t.get("length"),
        )
        for t in raw_tracks
    ]

    result = SearchResponse(
        artists=artist_results,
        albums=album_results,
        tracks=track_results,
    )
    _search_cache[cache_key] = (time.monotonic(), result)
    return result


# ── Detail views ───────────────────────────────────────────────────────────────


async def get_artist(mbid: str, session: AsyncSession) -> ArtistDetail | None:
    result = await session.execute(select(Artist).where(Artist.mbid == mbid))
    artist = result.scalar_one_or_none()

    if artist is None:
        raw = await mb.lookup_artist(mbid)
        if raw is None:
            return None
        artist = await _upsert_artist(session, raw)
        await session.flush()

    alb_result = await session.execute(
        select(Album).where(Album.artist_id == artist.id)
    )
    albums = alb_result.scalars().all()

    return ArtistDetail(
        mbid=artist.mbid,
        name=artist.name,
        sort_name=artist.sort_name,
        disambiguation=artist.disambiguation,
        image_url=artist.image_url,
        albums=[
            AlbumResult(
                mbid=a.mbid,
                title=a.title,
                artist_name=artist.name,
                release_year=a.release_year,
                cover_art_url=a.cover_art_url,
            )
            for a in albums
        ],
    )


async def get_album(
    mbid: str, session: AsyncSession, viewer_clerk_id: str | None = None
) -> AlbumDetail | None:
    result = await session.execute(select(Album).where(Album.mbid == mbid))
    album = result.scalar_one_or_none()

    if album is None:
        raw = await mb.lookup_release_group(mbid)
        if raw is None:
            return None
        artist_mbid = _primary_artist_mbid(raw)
        raw_artist_credit = (
            raw.get("artist-credit", [{}])[0].get("artist")
            if raw.get("artist-credit")
            else None
        )
        artist_id = await _resolve_artist_id(session, artist_mbid, raw_artist_credit)
        album = await _upsert_album(session, raw, artist_id)
        await session.flush()

    # Resolve artist name for response
    artist_name: str | None = None
    artist_mbid_out: str | None = None
    if album.artist_id is not None:
        art_result = await session.execute(
            select(Artist).where(Artist.id == album.artist_id)
        )
        art = art_result.scalar_one_or_none()
        if art:
            artist_name = art.name
            artist_mbid_out = art.mbid

    trk_result = await session.execute(select(Track).where(Track.album_id == album.id))
    tracks = trk_result.scalars().all()

    viewer_id = None
    if viewer_clerk_id:
        viewer = await user_svc.get_by_clerk_id(session, viewer_clerk_id)
        if viewer:
            viewer_id = viewer.id
    ratings = await rating_svc.list_for_entity(session, "album", album.id, viewer_id)

    return AlbumDetail(
        mbid=album.mbid,
        title=album.title,
        artist_name=artist_name,
        artist_mbid=artist_mbid_out,
        release_year=album.release_year,
        album_type=album.album_type,
        cover_art_url=album.cover_art_url,
        tracks=[
            TrackResult(
                mbid=t.mbid,
                title=t.title,
                artist_name=artist_name,
                album_title=album.title,
                album_mbid=album.mbid,
                duration_ms=t.duration_ms,
            )
            for t in tracks
        ],
        aggregate_score=ratings.aggregate_score,
        reviews=ratings.reviews,
    )


async def get_track(
    mbid: str, session: AsyncSession, viewer_clerk_id: str | None = None
) -> TrackDetail | None:
    result = await session.execute(select(Track).where(Track.mbid == mbid))
    track = result.scalar_one_or_none()

    if track is None:
        raw = await mb.lookup_recording(mbid)
        if raw is None:
            return None
        artist_mbid = _primary_artist_mbid(raw)
        raw_artist_credit = (
            raw.get("artist-credit", [{}])[0].get("artist")
            if raw.get("artist-credit")
            else None
        )
        artist_id = await _resolve_artist_id(session, artist_mbid, raw_artist_credit)
        rg_mbid = _release_group_mbid(raw)
        album_id: uuid.UUID | None = None
        if rg_mbid:
            alb_r = await session.execute(select(Album).where(Album.mbid == rg_mbid))
            alb = alb_r.scalar_one_or_none()
            album_id = alb.id if alb else None
        track = await _upsert_track(session, raw, artist_id, album_id)
        await session.flush()

    artist_name: str | None = None
    artist_mbid_out: str | None = None
    if track.artist_id is not None:
        art_r = await session.execute(
            select(Artist).where(Artist.id == track.artist_id)
        )
        art = art_r.scalar_one_or_none()
        if art:
            artist_name = art.name
            artist_mbid_out = art.mbid

    album_title: str | None = None
    album_mbid_out: str | None = None
    cover_art_url: str | None = None
    if track.album_id is not None:
        alb_r = await session.execute(select(Album).where(Album.id == track.album_id))
        alb = alb_r.scalar_one_or_none()
        if alb:
            album_title = alb.title
            album_mbid_out = alb.mbid
            cover_art_url = alb.cover_art_url

    viewer_id = None
    if viewer_clerk_id:
        viewer = await user_svc.get_by_clerk_id(session, viewer_clerk_id)
        if viewer:
            viewer_id = viewer.id
    ratings = await rating_svc.list_for_entity(session, "track", track.id, viewer_id)

    return TrackDetail(
        mbid=track.mbid,
        title=track.title,
        artist_name=artist_name,
        artist_mbid=artist_mbid_out,
        album_title=album_title,
        album_mbid=album_mbid_out,
        cover_art_url=cover_art_url,
        duration_ms=track.duration_ms,
        track_number=track.track_number,
        disc_number=track.disc_number,
        aggregate_score=ratings.aggregate_score,
        reviews=ratings.reviews,
    )
