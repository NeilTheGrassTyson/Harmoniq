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

    async def test_search_artists_default_limit_is_20(self) -> None:
        mock_get = AsyncMock(return_value={"artists": []})
        with patch("app.services.musicbrainz._get", new=mock_get):
            from app.services import musicbrainz as mb

            await mb.search_artists("radiohead")

        assert mock_get.call_args.args[1]["limit"] == "20"

    async def test_search_release_groups_default_limit_is_20(self) -> None:
        mock_get = AsyncMock(return_value={"release-groups": []})
        with patch("app.services.musicbrainz._get", new=mock_get):
            from app.services import musicbrainz as mb

            await mb.search_release_groups("ok computer")

        assert mock_get.call_args.args[1]["limit"] == "20"

    async def test_search_recordings_default_limit_is_20(self) -> None:
        mock_get = AsyncMock(return_value={"recordings": []})
        with patch("app.services.musicbrainz._get", new=mock_get):
            from app.services import musicbrainz as mb

            await mb.search_recordings("karma police")

        assert mock_get.call_args.args[1]["limit"] == "20"

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


# ── Artist search query construction ──────────────────────────────────────────


class TestArtistSearchQuery:
    async def test_query_includes_alias_field_qualifier(self) -> None:
        mock_get = AsyncMock(return_value={"artists": []})
        with patch("app.services.musicbrainz._get", new=mock_get):
            from app.services import musicbrainz as mb

            await mb.search_artists("radiohead")

        query = mock_get.call_args.args[1]["query"]
        assert query == 'artist:"radiohead" OR alias:"radiohead"'

    async def test_user_input_is_lucene_escaped(self) -> None:
        mock_get = AsyncMock(return_value={"artists": []})
        with patch("app.services.musicbrainz._get", new=mock_get):
            from app.services import musicbrainz as mb

            await mb.search_artists("GY!BE")

        query = mock_get.call_args.args[1]["query"]
        assert query == 'artist:"GY\\!BE" OR alias:"GY\\!BE"'

    def test_escape_covers_all_special_chars(self) -> None:
        from app.services.musicbrainz import _escape_lucene

        raw = '+ - && || ! ( ) { } [ ] ^ " ~ * ? : \\'
        escaped = _escape_lucene(raw)
        assert escaped == (
            "\\+ \\- \\&\\& \\|\\| \\! \\( \\) \\{ \\} \\[ \\] "
            '\\^ \\" \\~ \\* \\? \\: \\\\'
        )

    def test_escape_leaves_plain_text_untouched(self) -> None:
        from app.services.musicbrainz import _escape_lucene

        assert _escape_lucene("the beatles") == "the beatles"


# ── Release-group lookup includes ──────────────────────────────────────────────


class TestLookupReleaseGroupIncludes:
    async def test_lookup_requests_artist_credits_and_releases(self) -> None:
        """artists → cold-ingest artist resolution; releases → tracklist sync
        can pick a canonical release without a second round-trip."""
        mock_get = AsyncMock(return_value={"id": "rg-1", "title": "OK Computer"})
        with patch("app.services.musicbrainz._get", new=mock_get):
            from app.services import musicbrainz as mb

            await mb.lookup_release_group("rg-1")

        assert mock_get.call_args.args[1] == {"inc": "artists+releases"}


# ── Release-group quality gate ─────────────────────────────────────────────────


class TestStandardReleaseGroupFilter:
    def test_plain_album_ep_single_pass(self) -> None:
        from app.services.catalog import _is_standard_release_group

        for primary in ("Album", "EP", "Single"):
            assert _is_standard_release_group({"primary-type": primary})

    def test_excluded_secondary_types_fail(self) -> None:
        from app.services.catalog import _is_standard_release_group

        for secondary in ("Live", "Compilation", "Remix", "Demo", "Soundtrack"):
            raw = {"primary-type": "Album", "secondary-types": [secondary]}
            assert not _is_standard_release_group(raw), secondary

    def test_non_standard_primary_fails(self) -> None:
        from app.services.catalog import _is_standard_release_group

        assert not _is_standard_release_group({"primary-type": "Broadcast"})
        assert not _is_standard_release_group({"primary-type": None})
        assert not _is_standard_release_group({})


class TestPickCanonicalRelease:
    def test_prefers_official_then_earliest_date(self) -> None:
        from app.services.catalog import _pick_canonical_release

        releases = [
            {"id": "bootleg", "status": "Bootleg", "date": "1990-01-01"},
            {"id": "reissue", "status": "Official", "date": "2005-06-01"},
            {"id": "original", "status": "Official", "date": "1994-05-24"},
        ]
        assert _pick_canonical_release(releases) == "original"

    def test_empty_and_undated(self) -> None:
        from app.services.catalog import _pick_canonical_release

        assert _pick_canonical_release([]) is None
        # Undated official sorts after dated official, not before.
        releases = [
            {"id": "undated", "status": "Official"},
            {"id": "dated", "status": "Official", "date": "2001"},
        ]
        assert _pick_canonical_release(releases) == "dated"


# ── Release-group browse pagination ────────────────────────────────────────────


class TestBrowseReleaseGroups:
    async def test_paginates_past_first_page(self) -> None:
        page_one = {
            "release-group-count": 3,
            "release-groups": [{"id": "rg-1"}, {"id": "rg-2"}],
        }
        page_two = {
            "release-group-count": 3,
            "release-groups": [{"id": "rg-3"}],
        }
        mock_get = AsyncMock(side_effect=[page_one, page_two])
        with patch("app.services.musicbrainz._get", new=mock_get):
            from app.services import musicbrainz as mb

            result = await mb.browse_release_groups("artist-mbid-1")

        assert [rg["id"] for rg in result] == ["rg-1", "rg-2", "rg-3"]
        assert mock_get.call_count == 2
        first_params = mock_get.call_args_list[0].args[1]
        second_params = mock_get.call_args_list[1].args[1]
        assert first_params["offset"] == "0"
        assert second_params["offset"] == "2"

    async def test_browse_filters_to_album_single_ep(self) -> None:
        mock_get = AsyncMock(
            return_value={"release-group-count": 0, "release-groups": []}
        )
        with patch("app.services.musicbrainz._get", new=mock_get):
            from app.services import musicbrainz as mb

            result = await mb.browse_release_groups("artist-mbid-1")

        assert result == []
        params = mock_get.call_args.args[1]
        assert params["artist"] == "artist-mbid-1"
        assert params["type"] == "album|single|ep"
        assert params["limit"] == "100"

    async def test_single_page_stops_after_one_request(self) -> None:
        mock_get = AsyncMock(
            return_value={"release-group-count": 1, "release-groups": [{"id": "rg-1"}]}
        )
        with patch("app.services.musicbrainz._get", new=mock_get):
            from app.services import musicbrainz as mb

            result = await mb.browse_release_groups("artist-mbid-1")

        assert len(result) == 1
        assert mock_get.call_count == 1
