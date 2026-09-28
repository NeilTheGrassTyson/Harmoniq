"""Highlights against a real database (specs/phase-2-highlights.md).

The review-visibility trap is the requirement most likely to be got wrong,
so it is pinned from several directions: a public highlight must never
publish a review its author didn't intend to publish.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, get_optional_clerk_id
from app.config import settings
from app.core.enums import HighlightType, VisibilityScope
from app.database import get_db
from app.main import app
from app.models.catalog import Album, Artist, Track
from app.models.highlight import Highlight
from app.models.rating import Rating
from app.models.spotify import SpotifyConnection
from app.models.user import User
from app.schemas.highlight import AddHighlightRequest
from app.services import highlight as highlight_svc
from app.services import spotify as spotify_svc
from app.services import user as user_svc
from tests.integration.friends_helpers import make_friends

pytestmark = pytest.mark.integration

NOW = datetime(2026, 9, 27, tzinfo=UTC)
PLAYLIST_ID = "37i9dQZF1DXcBWIGoYBM5M"


@pytest.fixture(autouse=True)
def highlights_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "highlights_enabled", True)
    monkeypatch.setattr(settings, "playlist_highlights_enabled", True)
    highlight_svc._refreshing.clear()


async def _user(session: AsyncSession, name: str) -> User:
    user = await user_svc.create_user(session, f"clerk_{name}", name, name.title())
    await session.flush()
    return user


async def _catalog(session: AsyncSession, tag: str) -> tuple[Artist, Album, Track]:
    artist = Artist(mbid=f"ar-{tag}", name=f"Artist {tag}", last_fetched_at=NOW)
    session.add(artist)
    await session.flush()
    album = Album(
        mbid=f"al-{tag}",
        title=f"Album {tag}",
        artist_id=artist.id,
        cover_art_url=f"https://coverartarchive.org/{tag}",
        last_fetched_at=NOW,
    )
    session.add(album)
    await session.flush()
    track = Track(
        mbid=f"tr-{tag}",
        title=f"Track {tag}",
        artist_id=artist.id,
        album_id=album.id,
        last_fetched_at=NOW,
    )
    session.add(track)
    await session.flush()
    return artist, album, track


async def _review(
    session: AsyncSession,
    author: User,
    kind: str,
    entity_id: uuid.UUID,
    text: str,
    *,
    visibility: str = "public",
    at: datetime = NOW,
) -> Rating:
    rating = Rating(
        user_id=author.id,
        entity_type=kind,
        entity_id=entity_id,
        score=8,
        review_text=text,
        visibility=visibility,
        created_at=at,
    )
    session.add(rating)
    await session.flush()
    return rating


async def _add(session: AsyncSession, user: User, kind: str, mbid: str) -> Any:
    return await highlight_svc.add(
        session, user, AddHighlightRequest(entity_type=HighlightType(kind), mbid=mbid)
    )


async def _view(session: AsyncSession, owner: User, viewer: User | None) -> Any:
    response, _ = await highlight_svc.list_for(session, owner, viewer)
    return response


async def _connect(session: AsyncSession, user: User, *, playlists: bool) -> None:
    scopes = spotify_svc.SCOPES + (" playlist-read-private" if playlists else "")
    session.add(
        SpotifyConnection(
            user_id=user.id,
            spotify_user_id=f"sp_{user.username}",
            refresh_token_encrypted="unused",
            scopes=scopes,
        )
    )
    await session.flush()


def _spotify_playlist(
    monkeypatch: pytest.MonkeyPatch, *, name: str | None = "Night Drive"
) -> None:
    async def get(session: AsyncSession, conn: SpotifyConnection, pid: str) -> Any:
        if name is None:
            return None
        return {
            "id": pid,
            "name": name,
            "image_url": None,
            "owner_id": conn.spotify_user_id,
        }

    monkeypatch.setattr(spotify_svc, "get_owned_playlist", get)


# ── Adding and the cap ────────────────────────────────────────────────────────


async def test_fifteen_across_types_and_the_sixteenth_is_refused(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await _user(db_session, "hl_cap")
    await _connect(db_session, owner, playlists=True)
    _spotify_playlist(monkeypatch)
    for n in range(5):
        artist, album, track = await _catalog(db_session, f"cap{n}")
        await _add(db_session, owner, "track", track.mbid)
        await _add(db_session, owner, "album", album.mbid)
        if n < 4:
            await _add(db_session, owner, "artist", artist.mbid)
    playlist = await highlight_svc.add(
        db_session,
        owner,
        AddHighlightRequest(
            entity_type=HighlightType.PLAYLIST, playlist_id=PLAYLIST_ID
        ),
    )
    assert playlist.entity_type is HighlightType.PLAYLIST  # the 15th, one slot
    _, _, extra = await _catalog(db_session, "cap-extra")
    with pytest.raises(highlight_svc.HighlightError) as refused:
        await _add(db_session, owner, "track", extra.mbid)
    assert refused.value.status_code == 409
    # Re-adding something already highlighted is not a sixteenth.
    again = await _add(db_session, owner, "album", "al-cap0")
    assert again.title == "Album cap0"
    count = await db_session.execute(
        select(func.count()).select_from(Highlight).where(Highlight.user_id == owner.id)
    )
    assert count.scalar_one() == highlight_svc.LIMIT


async def test_unknown_catalog_entities_are_refused(db_session: AsyncSession) -> None:
    owner = await _user(db_session, "hl_unknown")
    with pytest.raises(highlight_svc.HighlightError) as missing:
        await _add(db_session, owner, "track", "tr-nowhere")
    assert missing.value.status_code == 404


async def test_a_rating_is_not_required(db_session: AsyncSession) -> None:
    owner = await _user(db_session, "hl_unrated")
    artist, album, track = await _catalog(db_session, "unrated")
    for kind, mbid in (
        ("track", track.mbid),
        ("album", album.mbid),
        ("artist", artist.mbid),
    ):
        item = await _add(db_session, owner, kind, mbid)
        assert item.review is None


# ── Reviews: resolution and the visibility trap ──────────────────────────────


async def test_track_review_then_album_review_then_none(
    db_session: AsyncSession,
) -> None:
    owner = await _user(db_session, "hl_rev")
    _, album1, track1 = await _catalog(db_session, "rev1")
    _, album2, track2 = await _catalog(db_session, "rev2")
    _, _, track3 = await _catalog(db_session, "rev3")
    await _review(db_session, owner, "track", track1.id, "Own track review")
    await _review(db_session, owner, "album", album1.id, "Album one review")
    await _review(db_session, owner, "album", album2.id, "Album two review")
    for track in (track1, track2, track3):
        await _add(db_session, owner, "track", track.mbid)
    items = {i.title: i.review for i in (await _view(db_session, owner, None)).items}
    assert items["Track rev1"].review_text == "Own track review"
    assert items["Track rev2"].review_text == "Album two review"
    assert items["Track rev2"].of_album is True
    assert items["Track rev3"] is None


async def test_artists_never_carry_a_review(db_session: AsyncSession) -> None:
    owner = await _user(db_session, "hl_art")
    artist, _, _ = await _catalog(db_session, "art")
    item = await _add(db_session, owner, "artist", artist.mbid)
    assert item.review is None


async def test_a_public_highlight_never_publishes_a_private_review(
    db_session: AsyncSession,
) -> None:
    owner = await _user(db_session, "hl_trap")
    stranger = await _user(db_session, "hl_trap_str")
    friend = await _user(db_session, "hl_trap_fr")
    await make_friends(db_session, owner, friend)
    _, album, track = await _catalog(db_session, "trap")
    await _review(
        db_session, owner, "track", track.id, "Friends only", visibility="friends"
    )
    await _review(
        db_session, owner, "album", album.id, "Private album", visibility="private"
    )
    await _add(db_session, owner, "track", track.mbid)
    await _add(db_session, owner, "album", album.mbid)

    def reviews(view: Any) -> dict[str, str | None]:
        return {
            i.title: (i.review.review_text if i.review else None) for i in view.items
        }

    # The stranger sees both highlights, and no commentary — not the track's,
    # and not the album review as a fallback for it either.
    assert reviews(await _view(db_session, owner, stranger)) == {
        "Track trap": None,
        "Album trap": None,
    }
    assert reviews(await _view(db_session, owner, friend)) == {
        "Track trap": "Friends only",
        "Album trap": None,
    }
    assert reviews(await _view(db_session, owner, owner)) == {
        "Track trap": "Friends only",
        "Album trap": "Private album",
    }


async def test_the_profile_master_switch_and_moderation_still_apply(
    db_session: AsyncSession,
) -> None:
    owner = await _user(db_session, "hl_master")
    _, album, _ = await _catalog(db_session, "master")
    rating = await _review(db_session, owner, "album", album.id, "Hidden by mods")
    await _add(db_session, owner, "album", album.mbid)
    rating.hidden_at = NOW
    await db_session.flush()
    assert (await _view(db_session, owner, None)).items[0].review is None
    rating.hidden_at = None
    owner.visibility_ratings = VisibilityScope.PRIVATE.value
    await db_session.flush()
    assert (await _view(db_session, owner, None)).items[0].review is None


async def test_only_the_latest_review_counts(db_session: AsyncSession) -> None:
    owner = await _user(db_session, "hl_latest")
    _, album, _ = await _catalog(db_session, "latest")
    await _review(db_session, owner, "album", album.id, "Old public take")
    await _review(
        db_session,
        owner,
        "album",
        album.id,
        "New private take",
        visibility="private",
        at=NOW + timedelta(days=1),
    )
    await _add(db_session, owner, "album", album.mbid)
    assert (await _view(db_session, owner, None)).items[0].review is None


async def test_someone_elses_review_never_appears(db_session: AsyncSession) -> None:
    owner = await _user(db_session, "hl_other")
    critic = await _user(db_session, "hl_critic")
    _, album, _ = await _catalog(db_session, "other")
    await _review(db_session, critic, "album", album.id, "The critic's review")
    await _add(db_session, owner, "album", album.mbid)
    assert (await _view(db_session, owner, None)).items[0].review is None


# ── Visibility of the highlights themselves ──────────────────────────────────


async def test_public_by_default_private_hides_everything(
    db_session: AsyncSession,
) -> None:
    owner = await _user(db_session, "hl_vis")
    stranger = await _user(db_session, "hl_vis_str")
    friend = await _user(db_session, "hl_vis_fr")
    await make_friends(db_session, owner, friend)
    assert owner.visibility_highlights == "public"
    _, album, _ = await _catalog(db_session, "vis")
    await _add(db_session, owner, "album", album.mbid)
    assert len((await _view(db_session, owner, None)).items) == 1
    owner.visibility_highlights = "private"
    assert await _view(db_session, owner, stranger) is None
    assert await _view(db_session, owner, friend) is None
    assert (await _view(db_session, owner, owner)).visibility == "private"
    owner.visibility_highlights = "friends"
    assert await _view(db_session, owner, stranger) is None
    seen = await _view(db_session, owner, friend)
    assert seen and len(seen.items) == 1 and seen.visibility is None


async def test_an_empty_set_is_an_empty_list(db_session: AsyncSession) -> None:
    owner = await _user(db_session, "hl_empty")
    view = await _view(db_session, owner, None)
    assert view.items == [] and view.limit == highlight_svc.LIMIT


# ── Playlists ─────────────────────────────────────────────────────────────────


async def test_playlists_need_the_widened_grant(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await _user(db_session, "hl_scope")
    _spotify_playlist(monkeypatch)
    assert (await highlight_svc.playlist_options(db_session, owner)).status == (
        "not_connected"
    )
    await _connect(db_session, owner, playlists=False)
    assert (await highlight_svc.playlist_options(db_session, owner)).status == (
        "needs_permission"
    )
    with pytest.raises(highlight_svc.HighlightError) as refused:
        await highlight_svc.add(
            db_session,
            owner,
            AddHighlightRequest(
                entity_type=HighlightType.PLAYLIST, playlist_id=PLAYLIST_ID
            ),
        )
    assert refused.value.status_code == 403


async def test_the_scope_is_requested_only_while_the_feature_is_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert "playlist-read-private" in spotify_svc.requested_scopes()
    monkeypatch.setattr(settings, "playlist_highlights_enabled", False)
    assert spotify_svc.requested_scopes() == spotify_svc.SCOPES


async def test_disconnecting_removes_playlists_and_keeps_the_rest(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await _user(db_session, "hl_disc")
    await _connect(db_session, owner, playlists=True)
    _spotify_playlist(monkeypatch)
    _, album, _ = await _catalog(db_session, "disc")
    await _add(db_session, owner, "album", album.mbid)
    await highlight_svc.add(
        db_session,
        owner,
        AddHighlightRequest(
            entity_type=HighlightType.PLAYLIST, playlist_id=PLAYLIST_ID
        ),
    )
    assert len((await _view(db_session, owner, None)).items) == 2
    await spotify_svc.disconnect(db_session, owner)
    remaining = (await _view(db_session, owner, None)).items
    assert [i.entity_type for i in remaining] == [HighlightType.ALBUM]


async def test_playlist_cards_follow_spotify_and_vanish_when_gone(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await _user(db_session, "hl_live")
    await _connect(db_session, owner, playlists=True)
    _spotify_playlist(monkeypatch, name="Night Drive")
    item = await highlight_svc.add(
        db_session,
        owner,
        AddHighlightRequest(
            entity_type=HighlightType.PLAYLIST, playlist_id=PLAYLIST_ID
        ),
    )
    assert item.external_url == f"https://open.spotify.com/playlist/{PLAYLIST_ID}"
    row = await db_session.get(Highlight, item.id)
    assert row is not None
    row.display_refreshed_at = NOW - timedelta(days=1)
    await db_session.flush()
    _, stale = await highlight_svc.list_for(db_session, owner, None)
    assert stale is True

    async def outage(*_args: Any) -> Any:
        raise httpx.ConnectError("Spotify down")

    monkeypatch.setattr(spotify_svc, "get_owned_playlist", outage)
    await highlight_svc.refresh_playlists(db_session, owner.id)
    assert (await _view(db_session, owner, None)).items[0].title == "Night Drive"

    _spotify_playlist(monkeypatch, name="Night Drive (2026)")
    await highlight_svc.refresh_playlists(db_session, owner.id)
    assert (await _view(db_session, owner, None)).items[0].title == "Night Drive (2026)"

    _spotify_playlist(monkeypatch, name=None)
    await highlight_svc.refresh_playlists(db_session, owner.id)
    assert (await _view(db_session, owner, None)).items == []


async def test_switching_off_playlists_hides_them_without_deleting(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await _user(db_session, "hl_pl_off")
    await _connect(db_session, owner, playlists=True)
    _spotify_playlist(monkeypatch)
    await highlight_svc.add(
        db_session,
        owner,
        AddHighlightRequest(
            entity_type=HighlightType.PLAYLIST, playlist_id=PLAYLIST_ID
        ),
    )
    monkeypatch.setattr(settings, "playlist_highlights_enabled", False)
    assert (await _view(db_session, owner, None)).items == []
    assert (await highlight_svc.playlist_options(db_session, owner)).status == (
        "unavailable"
    )
    monkeypatch.setattr(settings, "playlist_highlights_enabled", True)
    assert len((await _view(db_session, owner, None)).items) == 1


async def test_no_playlist_is_reachable_from_the_recommendation_accessor(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await _user(db_session, "hl_boundary")
    await _connect(db_session, owner, playlists=True)
    _spotify_playlist(monkeypatch)
    _, album, _ = await _catalog(db_session, "boundary")
    await _add(db_session, owner, "album", album.mbid)
    await highlight_svc.add(
        db_session,
        owner,
        AddHighlightRequest(
            entity_type=HighlightType.PLAYLIST, playlist_id=PLAYLIST_ID
        ),
    )
    reachable = await highlight_svc.first_party_highlights(db_session, owner.id)
    assert [row.entity_type for row in reachable] == ["album"]


# ── API ───────────────────────────────────────────────────────────────────────


def _client_as(session: AsyncSession, clerk_id: str | None) -> AsyncClient:
    async def _db():
        yield session

    async def _current() -> str:
        assert clerk_id is not None
        return clerk_id

    async def _optional() -> str | None:
        return clerk_id

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _current
    app.dependency_overrides[get_optional_clerk_id] = _optional
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_api_add_view_remove_and_ownership(db_session: AsyncSession) -> None:
    owner = await _user(db_session, "hl_api")
    other = await _user(db_session, "hl_api_other")
    _, album, _ = await _catalog(db_session, "api")
    async with _client_as(db_session, owner.clerk_id) as client:
        added = await client.post(
            "/api/v1/highlights", json={"entity_type": "album", "mbid": album.mbid}
        )
        mine = await client.get(f"/api/v1/highlights/user/{owner.username}")
    app.dependency_overrides.clear()
    assert added.status_code == 201
    assert mine.headers["cache-control"] == "private, no-store"
    assert mine.json()["visibility"] == "public"
    highlight_id = added.json()["id"]

    async with _client_as(db_session, other.clerk_id) as client:
        theirs = await client.get(f"/api/v1/highlights/user/{owner.username}")
        await client.delete(f"/api/v1/highlights/{highlight_id}")
    app.dependency_overrides.clear()
    assert "visibility" not in theirs.json() or theirs.json()["visibility"] is None
    assert await db_session.get(Highlight, uuid.UUID(highlight_id)) is not None

    async with _client_as(db_session, owner.clerk_id) as client:
        removed = await client.delete(f"/api/v1/highlights/{highlight_id}")
    app.dependency_overrides.clear()
    assert removed.status_code == 204
    assert await db_session.get(Highlight, uuid.UUID(highlight_id)) is None


async def test_api_private_highlights_and_the_off_switch(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await _user(db_session, "hl_api_priv")
    owner.visibility_highlights = "private"
    await db_session.flush()
    async with _client_as(db_session, None) as client:
        hidden = await client.get(f"/api/v1/highlights/user/{owner.username}")
        monkeypatch.setattr(settings, "highlights_enabled", False)
        off = await client.get(f"/api/v1/highlights/user/{owner.username}")
    app.dependency_overrides.clear()
    assert hidden.status_code == 403
    assert off.status_code == 404
