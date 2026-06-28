"""
Integration tests: catalog persistence, FK integrity, and upsert idempotency.

MusicBrainz HTTP calls are always mocked — this suite must not hit the live API.
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Album, Artist, Track
from app.services import catalog as catalog_svc

# ── Fixture raw payloads (representative MusicBrainz response fragments) ──────


_ARTIST_RAW = {
    "id": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
    "name": "Radiohead",
    "sort-name": "Radiohead",
    "disambiguation": None,
}

_ALBUM_RAW = {
    "id": "b84dce42-1b01-4c5d-b32e-b5f1e6e59f2a",
    "title": "OK Computer",
    "primary-type": "Album",
    "first-release-date": "1997-05-21",
    "artist-credit": [
        {"artist": {"id": "a74b1b7f-71a5-4011-9441-d0b5e4122711", "name": "Radiohead"}}
    ],
}

_TRACK_RAW = {
    "id": "c1d2e3f4-a5b6-7890-abcd-ef1234567890",
    "title": "Karma Police",
    "length": 262000,
    "artist-credit": [
        {"artist": {"id": "a74b1b7f-71a5-4011-9441-d0b5e4122711", "name": "Radiohead"}}
    ],
    "releases": [{"release-group": {"id": "b84dce42-1b01-4c5d-b32e-b5f1e6e59f2a"}}],
}

_ARTIST_MBID = _ARTIST_RAW["id"]
_ALBUM_MBID = _ALBUM_RAW["id"]
_TRACK_MBID = _TRACK_RAW["id"]


# ── §3.6 Catalog persistence & ingestion ─────────────────────────────────────


@pytest.mark.integration
class TestArtistUpsert:
    async def test_upsert_creates_artist(self, db_session: AsyncSession) -> None:
        artist = await catalog_svc._upsert_artist(db_session, _ARTIST_RAW)
        await db_session.flush()

        result = await db_session.execute(
            select(Artist).where(Artist.mbid == _ARTIST_MBID)
        )
        fetched = result.scalar_one()
        assert fetched.name == "Radiohead"
        assert fetched.sort_name == "Radiohead"
        assert fetched.id == artist.id

    async def test_upsert_artist_is_idempotent(self, db_session: AsyncSession) -> None:
        await catalog_svc._upsert_artist(db_session, _ARTIST_RAW)
        await db_session.flush()
        await catalog_svc._upsert_artist(db_session, _ARTIST_RAW)
        await db_session.flush()

        result = await db_session.execute(
            select(Artist).where(Artist.mbid == _ARTIST_MBID)
        )
        assert len(result.scalars().all()) == 1

    async def test_upsert_updates_existing_name(self, db_session: AsyncSession) -> None:
        await catalog_svc._upsert_artist(db_session, _ARTIST_RAW)
        await db_session.flush()

        updated_raw = {**_ARTIST_RAW, "name": "Radiohead (updated)"}
        updated = await catalog_svc._upsert_artist(db_session, updated_raw)
        await db_session.flush()

        assert updated.name == "Radiohead (updated)"


@pytest.mark.integration
class TestAlbumUpsert:
    async def test_upsert_album_with_artist_fk(self, db_session: AsyncSession) -> None:
        artist = await catalog_svc._upsert_artist(db_session, _ARTIST_RAW)
        await db_session.flush()

        album = await catalog_svc._upsert_album(db_session, _ALBUM_RAW, artist.id)
        await db_session.flush()

        assert album.title == "OK Computer"
        assert album.artist_id == artist.id
        assert album.release_year == 1997
        assert album.album_type == "album"

    async def test_upsert_album_nullable_artist_fk(
        self, db_session: AsyncSession
    ) -> None:
        raw = {**_ALBUM_RAW, "id": "album-no-artist-fk-mbid"}
        album = await catalog_svc._upsert_album(db_session, raw, artist_id=None)
        await db_session.flush()

        assert album.artist_id is None

    async def test_upsert_album_is_idempotent(self, db_session: AsyncSession) -> None:
        artist = await catalog_svc._upsert_artist(db_session, _ARTIST_RAW)
        await db_session.flush()

        await catalog_svc._upsert_album(db_session, _ALBUM_RAW, artist.id)
        await db_session.flush()
        await catalog_svc._upsert_album(db_session, _ALBUM_RAW, artist.id)
        await db_session.flush()

        result = await db_session.execute(
            select(Album).where(Album.mbid == _ALBUM_MBID)
        )
        assert len(result.scalars().all()) == 1

    async def test_album_cover_art_url_generated(
        self, db_session: AsyncSession
    ) -> None:
        artist = await catalog_svc._upsert_artist(db_session, _ARTIST_RAW)
        await db_session.flush()
        album = await catalog_svc._upsert_album(db_session, _ALBUM_RAW, artist.id)
        await db_session.flush()

        assert album.cover_art_url is not None
        assert _ALBUM_MBID in album.cover_art_url


@pytest.mark.integration
class TestTrackUpsert:
    async def test_upsert_track_with_all_fks(self, db_session: AsyncSession) -> None:
        artist = await catalog_svc._upsert_artist(db_session, _ARTIST_RAW)
        await db_session.flush()
        album = await catalog_svc._upsert_album(db_session, _ALBUM_RAW, artist.id)
        await db_session.flush()

        track = await catalog_svc._upsert_track(
            db_session, _TRACK_RAW, artist.id, album.id
        )
        await db_session.flush()

        assert track.title == "Karma Police"
        assert track.artist_id == artist.id
        assert track.album_id == album.id
        assert track.duration_ms == 262000

    async def test_upsert_track_nullable_fks(self, db_session: AsyncSession) -> None:
        raw = {**_TRACK_RAW, "id": "track-no-fk-test-mbid"}
        track = await catalog_svc._upsert_track(db_session, raw, None, None)
        await db_session.flush()

        assert track.artist_id is None
        assert track.album_id is None

    async def test_upsert_track_is_idempotent(self, db_session: AsyncSession) -> None:
        artist = await catalog_svc._upsert_artist(db_session, _ARTIST_RAW)
        await db_session.flush()
        album = await catalog_svc._upsert_album(db_session, _ALBUM_RAW, artist.id)
        await db_session.flush()

        await catalog_svc._upsert_track(db_session, _TRACK_RAW, artist.id, album.id)
        await db_session.flush()
        await catalog_svc._upsert_track(db_session, _TRACK_RAW, artist.id, album.id)
        await db_session.flush()

        result = await db_session.execute(
            select(Track).where(Track.mbid == _TRACK_MBID)
        )
        assert len(result.scalars().all()) == 1


@pytest.mark.integration
class TestRelationships:
    async def test_artist_albums_relationship_loadable(
        self, db_session: AsyncSession
    ) -> None:
        artist = await catalog_svc._upsert_artist(db_session, _ARTIST_RAW)
        await catalog_svc._upsert_album(db_session, _ALBUM_RAW, artist.id)
        await db_session.flush()

        await db_session.refresh(artist, ["albums"])
        assert len(artist.albums) == 1
        assert artist.albums[0].mbid == _ALBUM_MBID

    async def test_album_tracks_relationship_loadable(
        self, db_session: AsyncSession
    ) -> None:
        artist = await catalog_svc._upsert_artist(db_session, _ARTIST_RAW)
        album = await catalog_svc._upsert_album(db_session, _ALBUM_RAW, artist.id)
        await catalog_svc._upsert_track(db_session, _TRACK_RAW, artist.id, album.id)
        await db_session.flush()

        await db_session.refresh(album, ["tracks"])
        assert len(album.tracks) == 1
        assert album.tracks[0].mbid == _TRACK_MBID


@pytest.mark.integration
class TestSearchAndIngest:
    """search_and_ingest must never hit the live MusicBrainz API in tests."""

    async def test_search_writes_entities_to_db(self, db_session: AsyncSession) -> None:
        with (
            patch(
                "app.services.catalog.mb.search_artists",
                new=AsyncMock(return_value=[_ARTIST_RAW]),
            ),
            patch(
                "app.services.catalog.mb.search_release_groups",
                new=AsyncMock(return_value=[_ALBUM_RAW]),
            ),
            patch(
                "app.services.catalog.mb.search_recordings",
                new=AsyncMock(return_value=[_TRACK_RAW]),
            ),
        ):
            # Use a unique query to bypass the module-level search cache.
            result = await catalog_svc.search_and_ingest(
                "radiohead_tc_unique_q1", db_session
            )

        assert len(result.artists) == 1
        assert result.artists[0].name == "Radiohead"
        assert len(result.albums) == 1
        assert len(result.tracks) == 1

        db_result = await db_session.execute(
            select(Artist).where(Artist.mbid == _ARTIST_MBID)
        )
        assert db_result.scalar_one_or_none() is not None

    async def test_search_empty_results_handled(self, db_session: AsyncSession) -> None:
        with (
            patch(
                "app.services.catalog.mb.search_artists",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.catalog.mb.search_release_groups",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.catalog.mb.search_recordings",
                new=AsyncMock(return_value=[]),
            ),
        ):
            result = await catalog_svc.search_and_ingest(
                "emptysearch_unique_q2", db_session
            )

        assert result.artists == []
        assert result.albums == []
        assert result.tracks == []

    async def test_resolve_artist_id_ingests_if_missing(
        self, db_session: AsyncSession
    ) -> None:
        """_resolve_artist_id ingests the raw artist data when no DB row exists yet."""
        artist_id = await catalog_svc._resolve_artist_id(
            db_session, _ARTIST_MBID, _ARTIST_RAW
        )
        await db_session.flush()

        assert artist_id is not None
        result = await db_session.execute(
            select(Artist).where(Artist.mbid == _ARTIST_MBID)
        )
        assert result.scalar_one_or_none() is not None

    async def test_resolve_artist_id_returns_none_when_no_mbid(
        self, db_session: AsyncSession
    ) -> None:
        artist_id = await catalog_svc._resolve_artist_id(db_session, None, None)
        assert artist_id is None
