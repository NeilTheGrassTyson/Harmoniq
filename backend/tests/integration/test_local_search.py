"""
Integration tests: local-first search (specs/local-first-search.md).

Exercises the Postgres trigram query path and the fallback decision. The
MusicBrainz client is always mocked — this suite must not hit the live API.
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import catalog as catalog_svc

# ── Fixture payloads (shape matches MusicBrainz responses) ────────────────────

_RADIOHEAD = {
    "id": "rh-artist-mbid",
    "name": "Radiohead",
    "sort-name": "Radiohead",
    "score": 100,
}

_OK_COMPUTER = {
    "id": "rh-okc-mbid",
    "title": "OK Computer",
    "primary-type": "Album",
    "first-release-date": "1997-05-21",
    "artist-credit": [{"artist": {"id": "rh-artist-mbid", "name": "Radiohead"}}],
}

_IN_RAINBOWS = {
    "id": "rh-inrainbows-mbid",
    "title": "In Rainbows",
    "primary-type": "Album",
    "first-release-date": "2007-10-10",
    "artist-credit": [{"artist": {"id": "rh-artist-mbid", "name": "Radiohead"}}],
}

_KARMA_POLICE = {
    "id": "rh-karma-mbid",
    "title": "Karma Police",
    "length": 262000,
    "artist-credit": [{"artist": {"id": "rh-artist-mbid", "name": "Radiohead"}}],
}

# A release *titled* "Radiohead" by an unrelated artist — the measured junk
# class that entity-aware ranking must demote below the artist's own work.
_JUNK_ARTIST = {
    "id": "junk-artist-mbid",
    "name": "X-Dream",
    "sort-name": "X-Dream",
    "score": 100,
}

_JUNK_TITLED_ALBUM = {
    "id": "junk-album-mbid",
    "title": "Radiohead",
    "primary-type": "Album",
    "first-release-date": "2003-01-01",
    "artist-credit": [{"artist": {"id": "junk-artist-mbid", "name": "X-Dream"}}],
}


async def _seed_radiohead(session: AsyncSession) -> None:
    artist = await catalog_svc._upsert_artist(session, _RADIOHEAD)
    await session.flush()
    await catalog_svc._upsert_album(session, _OK_COMPUTER, artist.id)
    await catalog_svc._upsert_album(session, _IN_RAINBOWS, artist.id)
    await session.flush()
    await catalog_svc._upsert_track(session, _KARMA_POLICE, artist.id, album_id=None)
    junk = await catalog_svc._upsert_artist(session, _JUNK_ARTIST)
    await session.flush()
    await catalog_svc._upsert_album(session, _JUNK_TITLED_ALBUM, junk.id)
    await session.flush()


@pytest.mark.integration
class TestSearchLocal:
    async def test_artist_query_returns_artists_own_releases_first(
        self, db_session: AsyncSession
    ) -> None:
        await _seed_radiohead(db_session)

        result = await catalog_svc._search_local(db_session, "radiohead")

        assert result is not None
        assert result.artists[0].name == "Radiohead"
        # Entity-aware ranking: a strong artist match makes the albums and
        # tracks categories relationship-only — the unrelated release that
        # merely *shares the title* "Radiohead" must not appear at all.
        assert [a.title for a in result.albums] == ["In Rainbows", "OK Computer"]
        assert [t.title for t in result.tracks] == ["Karma Police"]
        assert result.tracks[0].artist_name == "Radiohead"

    async def test_title_query_without_artist_match_finds_album(
        self, db_session: AsyncSession
    ) -> None:
        await _seed_radiohead(db_session)
        # Two more title matches so the query clears the thinness floor
        # (_MIN_LOCAL_RESULTS = 3) without any strong artist match.
        artist = await catalog_svc._upsert_artist(db_session, _RADIOHEAD)
        await db_session.flush()
        await catalog_svc._upsert_album(
            db_session,
            {
                "id": "rh-oknotok-mbid",
                "title": "OK Computer OKNOTOK 1997 2017",
                "primary-type": "Album",
                "first-release-date": "2017-06-23",
            },
            artist.id,
        )
        await catalog_svc._upsert_track(
            db_session,
            {"id": "okc-track-mbid", "title": "OK Computer Program"},
            artist.id,
        )
        await db_session.flush()

        result = await catalog_svc._search_local(db_session, "ok computer")

        assert result is not None
        # Title-similarity path: exact title first, related titles behind it.
        assert [a.title for a in result.albums][0] == "OK Computer"

    async def test_single_title_match_is_thin_and_falls_back(
        self, db_session: AsyncSession
    ) -> None:
        await _seed_radiohead(db_session)
        # "ok computer" matches only the one album title here: no strong
        # artist and total < _MIN_LOCAL_RESULTS → defer to MusicBrainz.
        assert (await catalog_svc._search_local(db_session, "ok computer")) is None

    async def test_misspelled_query_finds_artist(
        self, db_session: AsyncSession
    ) -> None:
        await _seed_radiohead(db_session)

        result = await catalog_svc._search_local(db_session, "radiohed")

        assert result is not None
        assert result.artists[0].name == "Radiohead"

    async def test_prefix_fragment_is_a_strong_match(
        self, db_session: AsyncSession
    ) -> None:
        await _seed_radiohead(db_session)

        result = await catalog_svc._search_local(db_session, "radioh")

        assert result is not None
        assert result.artists[0].name == "Radiohead"
        # Prefix boost makes this a strong artist match → albums populated
        # from the artist relationship, not title similarity.
        assert "OK Computer" in [a.title for a in result.albums]

    async def test_housekeeping_artist_excluded(self, db_session: AsyncSession) -> None:
        await catalog_svc._upsert_artist(
            db_session,
            {"id": "hk-artist-mbid", "name": "[unknown]", "sort-name": "[unknown]"},
        )
        await db_session.flush()

        result = await catalog_svc._search_local(db_session, "unknown")

        assert result is None or all(a.name != "[unknown]" for a in result.artists)

    async def test_thin_results_return_none(self, db_session: AsyncSession) -> None:
        # Empty catalog: nothing matches → thin → fall back.
        assert (
            await catalog_svc._search_local(db_session, "completely unseeded band")
        ) is None

    async def test_strong_artist_without_releases_falls_back(
        self, db_session: AsyncSession
    ) -> None:
        # A half-ingested artist (row exists, discography sync failed) must
        # defer to MusicBrainz rather than render a bare artist result.
        await catalog_svc._upsert_artist(db_session, _RADIOHEAD)
        await db_session.flush()

        assert (await catalog_svc._search_local(db_session, "radiohead")) is None


@pytest.mark.integration
class TestSearchOrchestrator:
    async def test_strong_local_match_skips_musicbrainz(
        self, db_session: AsyncSession
    ) -> None:
        await _seed_radiohead(db_session)

        with patch(
            "app.services.catalog.search_and_ingest", new=AsyncMock()
        ) as mb_path:
            result = await catalog_svc.search("radiohead", db_session)

        assert result.artists[0].name == "Radiohead"
        mb_path.assert_not_awaited()

    async def test_thin_local_results_fall_back_to_musicbrainz(
        self, db_session: AsyncSession
    ) -> None:
        fallback_response = catalog_svc.SearchResponse(artists=[], albums=[], tracks=[])
        with patch(
            "app.services.catalog.search_and_ingest",
            new=AsyncMock(return_value=fallback_response),
        ) as mb_path:
            result = await catalog_svc.search("orch_thin_unseeded_q1", db_session)

        assert result is fallback_response
        mb_path.assert_awaited_once_with("orch_thin_unseeded_q1")

    async def test_flag_off_restores_musicbrainz_first(
        self, db_session: AsyncSession
    ) -> None:
        await _seed_radiohead(db_session)
        fallback_response = catalog_svc.SearchResponse(artists=[], albums=[], tracks=[])
        with (
            patch.object(catalog_svc.settings, "search_local_first", False),
            patch(
                "app.services.catalog.search_and_ingest",
                new=AsyncMock(return_value=fallback_response),
            ) as mb_path,
        ):
            result = await catalog_svc.search("orch_flag_off_q1", db_session)

        assert result is fallback_response
        mb_path.assert_awaited_once()
