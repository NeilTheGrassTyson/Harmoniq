"""
Unit tests for MusicBrainz response-parsing helpers.

All tests are pure-function: no database, no HTTP calls.
"""

from unittest.mock import AsyncMock, patch

from app.services.catalog import (
    _parse_release_year,
    _primary_artist_mbid,
    _primary_artist_name,
    _release_group_mbid,
)

# ── _parse_release_year ────────────────────────────────────────────────────────


class TestParseReleaseYear:
    def test_full_iso_date(self) -> None:
        assert _parse_release_year("1997-05-21") == 1997

    def test_year_only(self) -> None:
        assert _parse_release_year("2000") == 2000

    def test_year_month_only(self) -> None:
        assert _parse_release_year("2003-06") == 2003

    def test_none_returns_none(self) -> None:
        assert _parse_release_year(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert _parse_release_year("") is None

    def test_non_numeric_returns_none(self) -> None:
        assert _parse_release_year("unknown") is None

    def test_partial_numeric_parses_as_int(self) -> None:
        # The function does int(date_str[:4]), so "199" yields 199 (no 4-digit guard).
        assert _parse_release_year("199") == 199


# ── _primary_artist_name ───────────────────────────────────────────────────────


class TestPrimaryArtistName:
    def test_returns_artist_name(self) -> None:
        raw = {
            "artist-credit": [
                {
                    "artist": {
                        "id": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
                        "name": "Radiohead",
                    }
                }
            ]
        }
        assert _primary_artist_name(raw) == "Radiohead"

    def test_empty_credits_returns_none(self) -> None:
        assert _primary_artist_name({"artist-credit": []}) is None

    def test_missing_key_returns_none(self) -> None:
        assert _primary_artist_name({}) is None

    def test_credit_without_artist_key(self) -> None:
        # A credit entry that is a string join-phrase, not a dict.
        raw = {"artist-credit": ["feat. "]}
        assert _primary_artist_name(raw) is None

    def test_multiple_credits_uses_first(self) -> None:
        raw = {
            "artist-credit": [
                {"artist": {"id": "id-1", "name": "Artist A"}},
                {"artist": {"id": "id-2", "name": "Artist B"}},
            ]
        }
        assert _primary_artist_name(raw) == "Artist A"


# ── _primary_artist_mbid ───────────────────────────────────────────────────────


class TestPrimaryArtistMbid:
    def test_returns_mbid(self) -> None:
        raw = {
            "artist-credit": [
                {
                    "artist": {
                        "id": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
                        "name": "Radiohead",
                    }
                }
            ]
        }
        assert _primary_artist_mbid(raw) == "a74b1b7f-71a5-4011-9441-d0b5e4122711"

    def test_empty_credits_returns_none(self) -> None:
        assert _primary_artist_mbid({"artist-credit": []}) is None

    def test_missing_key_returns_none(self) -> None:
        assert _primary_artist_mbid({}) is None


# ── _release_group_mbid ────────────────────────────────────────────────────────


class TestReleaseGroupMbid:
    def test_returns_release_group_id(self) -> None:
        raw = {
            "releases": [
                {
                    "title": "OK Computer",
                    "release-group": {"id": "b84dce42-1b01-4c5d-b32e-b5f1e6e59f2a"},
                }
            ]
        }
        assert _release_group_mbid(raw) == "b84dce42-1b01-4c5d-b32e-b5f1e6e59f2a"

    def test_no_releases_returns_none(self) -> None:
        assert _release_group_mbid({"releases": []}) is None

    def test_missing_releases_key_returns_none(self) -> None:
        assert _release_group_mbid({}) is None

    def test_release_without_release_group_returns_none(self) -> None:
        raw = {"releases": [{"title": "Something", "id": "rel-1"}]}
        assert _release_group_mbid(raw) is None

    def test_multiple_releases_uses_first(self) -> None:
        raw = {
            "releases": [
                {"release-group": {"id": "rg-first"}},
                {"release-group": {"id": "rg-second"}},
            ]
        }
        assert _release_group_mbid(raw) == "rg-first"


# ── MusicBrainz search helpers (HTTP mocked) ──────────────────────────────────


class TestMusicBrainzSearchHelpers:
    """Verify that the MB client functions return the right slice of the API response."""

    async def test_search_artists_returns_artists_list(self) -> None:
        mock_payload = {
            "artists": [
                {"id": "a74b1b7f-71a5-4011-9441-d0b5e4122711", "name": "Radiohead"},
            ]
        }
        with patch(
            "app.services.musicbrainz._get", new=AsyncMock(return_value=mock_payload)
        ):
            from app.services import musicbrainz as mb

            result = await mb.search_artists("radiohead", limit=1)

        assert len(result) == 1
        assert result[0]["name"] == "Radiohead"

    async def test_search_release_groups_returns_list(self) -> None:
        mock_payload = {
            "release-groups": [
                {"id": "rg-1", "title": "OK Computer"},
            ]
        }
        with patch(
            "app.services.musicbrainz._get", new=AsyncMock(return_value=mock_payload)
        ):
            from app.services import musicbrainz as mb

            result = await mb.search_release_groups("ok computer", limit=1)

        assert result[0]["title"] == "OK Computer"

    async def test_search_recordings_returns_list(self) -> None:
        mock_payload = {
            "recordings": [
                {"id": "rec-1", "title": "Karma Police"},
            ]
        }
        with patch(
            "app.services.musicbrainz._get", new=AsyncMock(return_value=mock_payload)
        ):
            from app.services import musicbrainz as mb

            result = await mb.search_recordings("karma police", limit=1)

        assert result[0]["title"] == "Karma Police"

    async def test_lookup_artist_returns_none_on_404(self) -> None:
        import httpx

        mock_response = AsyncMock()
        mock_response.status_code = 404
        error = httpx.HTTPStatusError(
            "Not Found", request=AsyncMock(), response=mock_response
        )

        with patch("app.services.musicbrainz._get", new=AsyncMock(side_effect=error)):
            from app.services import musicbrainz as mb

            result = await mb.lookup_artist("nonexistent-mbid")

        assert result is None
