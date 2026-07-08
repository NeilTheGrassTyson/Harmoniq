"""
Unit tests for MusicBrainz search-result relevance filtering — no database
required (specs/phase-1-catalog.md, Amendments 2026-07-05).
"""

from app.services.catalog import (
    _MAX_RESULTS_PER_CATEGORY,
    _MIN_RELEVANCE_SCORE,
    _filter_and_rank,
    _hit_score,
    _is_housekeeping_name,
)


class TestIsHousekeepingName:
    def test_bracketed_unknown(self) -> None:
        assert _is_housekeeping_name("[unknown]") is True

    def test_bracketed_data(self) -> None:
        assert _is_housekeeping_name("[data]") is True

    def test_bracketed_multiple_artists(self) -> None:
        assert _is_housekeeping_name("[Multiple artists]") is True

    def test_plain_name(self) -> None:
        assert _is_housekeeping_name("Radiohead") is False

    def test_empty_string(self) -> None:
        assert _is_housekeeping_name("") is False

    def test_brackets_mid_string_do_not_count(self) -> None:
        """Only a name that both starts with '[' and ends with ']' counts —
        matches the pre-existing artist-filter semantics exactly."""
        assert _is_housekeeping_name("Foo [Live]") is False


class TestHitScore:
    def test_int_score(self) -> None:
        assert _hit_score({"score": 87}) == 87

    def test_numeric_string_score(self) -> None:
        assert _hit_score({"score": "87"}) == 87

    def test_garbage_string_score(self) -> None:
        assert _hit_score({"score": "not-a-number"}) == 0

    def test_missing_score(self) -> None:
        assert _hit_score({}) == 0

    def test_none_score(self) -> None:
        assert _hit_score({"score": None}) == 0


class TestFilterAndRank:
    def test_drops_housekeeping_and_low_score(self) -> None:
        hits = [
            {"name": "[unknown]", "score": 90},
            {"name": "Real Artist", "score": 10},
            {"name": "Valid Artist", "score": 80},
        ]
        result = _filter_and_rank(hits, name_fn=lambda h: h.get("name"))
        assert [h["name"] for h in result] == ["Valid Artist"]

    def test_sorts_by_score_descending_regardless_of_input_order(self) -> None:
        hits = [
            {"name": "Low", "score": 60},
            {"name": "High", "score": 95},
            {"name": "Mid", "score": 75},
        ]
        result = _filter_and_rank(hits, name_fn=lambda h: h.get("name"))
        assert [h["name"] for h in result] == ["High", "Mid", "Low"]

    def test_caps_at_max_results_keeping_top_scored(self) -> None:
        hits = [
            {"name": f"Artist{i}", "score": 90 - i}
            for i in range(_MAX_RESULTS_PER_CATEGORY + 3)
        ]
        result = _filter_and_rank(hits, name_fn=lambda h: h.get("name"))
        assert len(result) == _MAX_RESULTS_PER_CATEGORY
        assert [h["name"] for h in result] == [
            f"Artist{i}" for i in range(_MAX_RESULTS_PER_CATEGORY)
        ]

    def test_score_exactly_at_threshold_is_kept(self) -> None:
        hits = [{"name": "Boundary", "score": _MIN_RELEVANCE_SCORE}]
        result = _filter_and_rank(hits, name_fn=lambda h: h.get("name"))
        assert len(result) == 1

    def test_score_one_below_threshold_is_dropped(self) -> None:
        hits = [{"name": "JustUnder", "score": _MIN_RELEVANCE_SCORE - 1}]
        result = _filter_and_rank(hits, name_fn=lambda h: h.get("name"))
        assert result == []

    def test_type_check_applies_when_provided(self) -> None:
        hits = [
            {"name": "Special", "type": "Special Purpose", "score": 100},
            {"name": "Normal", "type": "Person", "score": 100},
        ]
        result = _filter_and_rank(
            hits,
            name_fn=lambda h: h.get("name"),
            type_check=lambda h: h.get("type") != "Special Purpose",
        )
        assert [h["name"] for h in result] == ["Normal"]

    def test_album_filtered_by_artist_credit_name_not_album_title(self) -> None:
        """The gap this feature closes: a legitimately-titled album/track by a
        housekeeping artist-credit must still be dropped."""

        def artist_credit_name(raw: dict) -> str | None:
            artist_credits = raw.get("artist-credit", [])
            if artist_credits:
                return artist_credits[0].get("artist", {}).get("name")
            return None

        hits = [
            {
                "title": "A Perfectly Normal Title",
                "artist-credit": [{"artist": {"name": "[unknown]"}}],
                "score": 100,
            },
            {
                "title": "Another Album",
                "artist-credit": [{"artist": {"name": "Radiohead"}}],
                "score": 100,
            },
        ]
        result = _filter_and_rank(hits, name_fn=artist_credit_name)
        assert [h["title"] for h in result] == ["Another Album"]

    def test_empty_input_returns_empty(self) -> None:
        assert _filter_and_rank([], name_fn=lambda h: h.get("name")) == []
