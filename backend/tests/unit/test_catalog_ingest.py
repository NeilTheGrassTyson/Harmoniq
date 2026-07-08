"""
Unit tests for catalog ingestion: alias storage on artist upsert and
artist resolution on cold album lookup.

No database — sessions are mocked; MusicBrainz HTTP calls are patched.
"""

import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.catalog import Album, Artist
from app.services import catalog as catalog_svc
from app.services.catalog import _alias_names, _upsert_artist, get_album, get_artist

# ── Fakes ──────────────────────────────────────────────────────────────────────


class _FakeScalars(list):
    def all(self) -> list[Any]:
        return list(self)


class _FakeResult:
    def __init__(
        self, value: Any = None, scalars_list: list[Any] | None = None
    ) -> None:
        self._value = value
        self._scalars = scalars_list or []

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._scalars)


def _make_session(execute_side_effect: Any) -> tuple[Any, list[Any]]:
    added: list[Any] = []
    session = MagicMock()
    session.execute = AsyncMock(side_effect=execute_side_effect)
    session.flush = AsyncMock()
    session.add = added.append
    return session, added


# ── _alias_names ───────────────────────────────────────────────────────────────


class TestAliasNames:
    def test_extracts_names_from_alias_objects(self) -> None:
        raw = {
            "aliases": [
                {"name": "Ra Dio Head", "locale": None},
                {"name": "레디오헤드", "locale": "ko"},
            ]
        }
        assert _alias_names(raw) == ["Ra Dio Head", "레디오헤드"]

    def test_skips_aliases_without_name(self) -> None:
        raw = {"aliases": [{"locale": "en"}, {"name": "The Beatles"}]}
        assert _alias_names(raw) == ["The Beatles"]

    def test_missing_key_returns_empty(self) -> None:
        assert _alias_names({}) == []


# ── _upsert_artist alias storage ───────────────────────────────────────────────


class TestUpsertArtistAliases:
    async def test_insert_stores_aliases(self) -> None:
        session, added = _make_session(lambda stmt: _FakeResult(None))
        raw = {
            "id": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
            "name": "Radiohead",
            "sort-name": "Radiohead",
            "aliases": [{"name": "Ra Dio Head"}, {"name": "레디오헤드"}],
        }

        artist = await _upsert_artist(session, raw)

        assert artist.aliases == ["Ra Dio Head", "레디오헤드"]
        assert added == [artist]

    async def test_update_overwrites_aliases_when_present(self) -> None:
        existing = Artist(mbid="mbid-1", name="Old Name", aliases=["Old Alias"])
        session, _ = _make_session(lambda stmt: _FakeResult(existing))
        raw = {
            "id": "mbid-1",
            "name": "New Name",
            "aliases": [{"name": "New Alias"}],
        }

        artist = await _upsert_artist(session, raw)

        assert artist is existing
        assert artist.aliases == ["New Alias"]

    async def test_update_preserves_aliases_when_payload_omits_them(self) -> None:
        # Lookup responses carry no aliases key (no inc=aliases); a refresh
        # through that path must not wipe aliases ingested via search.
        existing = Artist(mbid="mbid-1", name="Radiohead", aliases=["Ra Dio Head"])
        session, _ = _make_session(lambda stmt: _FakeResult(existing))
        raw = {"id": "mbid-1", "name": "Radiohead"}

        artist = await _upsert_artist(session, raw)

        assert artist.aliases == ["Ra Dio Head"]


# ── Discography sync ───────────────────────────────────────────────────────────


class TestDiscographySync:
    async def test_sync_skipped_within_ttl(self) -> None:
        catalog_svc._discography_sync_cache.clear()
        artist = Artist(id=uuid.uuid4(), mbid="artist-1", name="Radiohead")
        session, added = _make_session(
            lambda stmt: _FakeResult(value=artist, scalars_list=[])
        )

        browse = AsyncMock(
            return_value=[
                {"id": "rg-1", "title": "OK Computer", "primary-type": "Album"}
            ]
        )
        with patch("app.services.catalog.mb.browse_release_groups", new=browse):
            await get_artist("artist-1", session)
            await get_artist("artist-1", session)

        assert browse.await_count == 1
        albums = [o for o in added if isinstance(o, Album)]
        assert len(albums) == 1
        assert albums[0].artist_id == artist.id

    async def test_sync_updates_existing_rows_without_re_adding(self) -> None:
        catalog_svc._discography_sync_cache.clear()
        artist = Artist(id=uuid.uuid4(), mbid="artist-1", name="Radiohead")
        existing_album = Album(
            id=uuid.uuid4(), mbid="rg-1", title="Old Title", artist_id=None
        )
        session, added = _make_session(
            lambda stmt: _FakeResult(value=artist, scalars_list=[existing_album])
        )

        browse = AsyncMock(
            return_value=[{"id": "rg-1", "title": "New Title", "primary-type": "Album"}]
        )
        with patch("app.services.catalog.mb.browse_release_groups", new=browse):
            await get_artist("artist-1", session)

        assert [o for o in added if isinstance(o, Album)] == []
        assert existing_album.title == "New Title"
        assert existing_album.artist_id == artist.id


# ── Cold album lookup resolves artist ──────────────────────────────────────────


class TestColdAlbumLookup:
    async def test_cold_lookup_sets_artist_id(self) -> None:
        raw_rg = {
            "id": "rg-1",
            "title": "OK Computer",
            "primary-type": "Album",
            "first-release-date": "1997-05-21",
            "artist-credit": [
                {
                    "artist": {
                        "id": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
                        "name": "Radiohead",
                        "sort-name": "Radiohead",
                    }
                }
            ],
        }

        added: list[Any] = []

        async def fake_execute(stmt: Any) -> _FakeResult:
            # Every select misses until both rows are ingested; after that,
            # the detail-assembly queries resolve against the added artist.
            artist = next((o for o in added if isinstance(o, Artist)), None)
            album = next((o for o in added if isinstance(o, Album)), None)
            if artist is not None and album is not None:
                return _FakeResult(value=artist, scalars_list=[])
            return _FakeResult(None)

        session = MagicMock()
        session.execute = AsyncMock(side_effect=fake_execute)
        session.flush = AsyncMock()
        session.add = added.append

        ratings_stub = SimpleNamespace(aggregate_score=None, reviews=[])
        with (
            patch(
                "app.services.catalog.mb.lookup_release_group",
                new=AsyncMock(return_value=raw_rg),
            ),
            patch(
                "app.services.catalog.rating_svc.list_for_entity",
                new=AsyncMock(return_value=ratings_stub),
            ),
        ):
            detail = await get_album("rg-1", session)

        assert detail is not None
        album = next(o for o in added if isinstance(o, Album))
        artist = next(o for o in added if isinstance(o, Artist))
        assert album.artist_id is not None
        assert album.artist_id == artist.id
        assert detail.artist_name == "Radiohead"
        assert detail.artist_mbid == "a74b1b7f-71a5-4011-9441-d0b5e4122711"
