"""
Unit tests for Home service pure computation functions — no database required.

Tests cover:
- _is_visible_to_viewer: visibility gate logic
- _compute_trending: window boundary, visibility, tiebreaks, aggregate rules
- _compute_friends_top_tracks: window boundary, top-track selection, self-exclusion
- _safe_section: section independence (error in one does not propagate)
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.services.home import (
    _FriendRow,
    _TrendingRow,
    _compute_friends_top_tracks,
    _compute_trending,
    _is_visible_to_viewer,
    _safe_section,
)

# ── Fixtures / factories ──────────────────────────────────────────────────────

_BASE_NOW = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
_CUTOFF_7 = _BASE_NOW - timedelta(days=7)
_CUTOFF_30 = _BASE_NOW - timedelta(days=30)


def _dt(days_ago: float = 0) -> datetime:
    return _BASE_NOW - timedelta(days=days_ago)


def _track_id(n: int = 1) -> uuid.UUID:
    return uuid.UUID(f"00000000-0000-0000-0000-{n:012d}")


def _user_id(n: int = 1) -> uuid.UUID:
    return uuid.UUID(f"00000000-0000-0000-0001-{n:012d}")


def _trending_row(
    track_n: int = 1,
    user_n: int = 1,
    score: int = 8,
    visibility: str = "public",
    days_ago: float = 1.0,
) -> _TrendingRow:
    return _TrendingRow(
        track_id=_track_id(track_n),
        user_id=_user_id(user_n),
        score=score,
        visibility=visibility,
        created_at=_dt(days_ago),
        mbid=f"mbid-track-{track_n}",
        title=f"Track {track_n}",
        artist_name=f"Artist {track_n}",
        cover_art_url=None,
    )


def _friend_row(
    friend_n: int = 1,
    track_n: int = 1,
    score: int = 8,
    visibility: str = "public",
    days_ago: float = 1.0,
) -> _FriendRow:
    return _FriendRow(
        friend_id=_user_id(friend_n),
        friend_username=f"friend{friend_n}",
        friend_display_name=f"Friend {friend_n}",
        friend_avatar_url=None,
        track_id=_track_id(track_n),
        track_mbid=f"mbid-track-{track_n}",
        track_title=f"Track {track_n}",
        artist_name=f"Artist {track_n}",
        cover_art_url=None,
        score=score,
        visibility=visibility,
        created_at=_dt(days_ago),
    )


# ── _is_visible_to_viewer ─────────────────────────────────────────────────────


class TestIsVisibleToViewer:
    def test_public_always_visible(self) -> None:
        assert _is_visible_to_viewer("public", _user_id(2), _user_id(1), set()) is True

    def test_private_not_visible_to_others(self) -> None:
        assert _is_visible_to_viewer("private", _user_id(2), _user_id(1), set()) is False

    def test_private_visible_to_own_rater(self) -> None:
        uid = _user_id(1)
        assert _is_visible_to_viewer("private", uid, uid, set()) is True

    def test_friends_visible_when_mutual_follow(self) -> None:
        rater = _user_id(2)
        viewer = _user_id(1)
        assert _is_visible_to_viewer("friends", rater, viewer, {rater}) is True

    def test_friends_not_visible_without_mutual_follow(self) -> None:
        rater = _user_id(2)
        viewer = _user_id(1)
        assert _is_visible_to_viewer("friends", rater, viewer, set()) is False

    def test_public_visible_to_anonymous_viewer(self) -> None:
        assert _is_visible_to_viewer("public", _user_id(1), None, set()) is True

    def test_private_not_visible_to_anonymous_viewer(self) -> None:
        assert _is_visible_to_viewer("private", _user_id(1), None, set()) is False


# ── _compute_trending ─────────────────────────────────────────────────────────


class TestComputeTrending:
    def test_empty_rows_returns_empty(self) -> None:
        assert _compute_trending([], _CUTOFF_7, None, set(), 10) == []

    def test_single_public_row_in_window(self) -> None:
        rows = [_trending_row(days_ago=1)]
        result = _compute_trending(rows, _CUTOFF_7, None, set(), 10)
        assert len(result) == 1
        assert result[0].track.id == _track_id(1)

    # ── Window boundary ───────────────────────────────────────────────────────

    def test_row_at_exact_cutoff_is_included(self) -> None:
        """created_at == cutoff: the boundary is inclusive."""
        row = _trending_row()
        row.created_at = _CUTOFF_7
        result = _compute_trending([row], _CUTOFF_7, None, set(), 10)
        assert len(result) == 1

    def test_row_one_microsecond_before_cutoff_is_excluded(self) -> None:
        row = _trending_row()
        row.created_at = _CUTOFF_7 - timedelta(microseconds=1)
        result = _compute_trending([row], _CUTOFF_7, None, set(), 10)
        assert len(result) == 0

    def test_row_one_second_after_cutoff_is_included(self) -> None:
        row = _trending_row()
        row.created_at = _CUTOFF_7 + timedelta(seconds=1)
        result = _compute_trending([row], _CUTOFF_7, None, set(), 10)
        assert len(result) == 1

    # ── Visibility filtering ──────────────────────────────────────────────────

    def test_track_with_only_private_ratings_excluded_for_other_viewer(self) -> None:
        viewer = _user_id(99)
        rows = [_trending_row(user_n=1, visibility="private")]
        result = _compute_trending(rows, _CUTOFF_7, viewer, set(), 10)
        assert len(result) == 0

    def test_private_rating_visible_to_rater_themselves(self) -> None:
        rater = _user_id(1)
        rows = [_trending_row(user_n=1, visibility="private")]
        result = _compute_trending(rows, _CUTOFF_7, rater, set(), 10)
        assert len(result) == 1

    def test_friends_rating_visible_to_mutual_follow(self) -> None:
        rater = _user_id(1)
        viewer = _user_id(99)
        rows = [_trending_row(user_n=1, visibility="friends")]
        result = _compute_trending(rows, _CUTOFF_7, viewer, {rater}, 10)
        assert len(result) == 1

    def test_friends_rating_excluded_for_non_mutual(self) -> None:
        viewer = _user_id(99)
        rows = [_trending_row(user_n=1, visibility="friends")]
        result = _compute_trending(rows, _CUTOFF_7, viewer, set(), 10)
        assert len(result) == 0

    def test_track_with_mixed_visibility_appears_if_one_public(self) -> None:
        """A track with one PRIVATE + one PUBLIC rating must appear (PUBLIC makes it visible)."""
        viewer = _user_id(99)
        rows = [
            _trending_row(track_n=1, user_n=1, visibility="private"),
            _trending_row(track_n=1, user_n=2, visibility="public"),
        ]
        result = _compute_trending(rows, _CUTOFF_7, viewer, set(), 10)
        assert len(result) == 1

    # ── Aggregate computation ─────────────────────────────────────────────────

    def test_aggregate_includes_private_ratings_in_score(self) -> None:
        """The aggregate is computed from ALL qualifying ratings, regardless of visibility.
        A PRIVATE rating still contributes to the average even though it gates visibility."""
        viewer = _user_id(99)
        rows = [
            _TrendingRow(
                track_id=_track_id(1),
                user_id=_user_id(1),
                score=10,
                visibility="public",
                created_at=_dt(1),
                mbid="m1",
                title="T1",
                artist_name=None,
                cover_art_url=None,
            ),
            _TrendingRow(
                track_id=_track_id(1),
                user_id=_user_id(2),
                score=2,
                visibility="private",
                created_at=_dt(1),
                mbid="m1",
                title="T1",
                artist_name=None,
                cover_art_url=None,
            ),
        ]
        result = _compute_trending(rows, _CUTOFF_7, viewer, set(), 10)
        assert len(result) == 1
        assert result[0].aggregate_score == pytest.approx(6.0)  # (10 + 2) / 2

    def test_most_recent_per_user_counts_for_aggregate(self) -> None:
        """When a user re-rates a track, only their most recent score contributes."""
        old = _trending_row(track_n=1, user_n=1, score=2, days_ago=5)
        recent = _trending_row(track_n=1, user_n=1, score=10, days_ago=1)
        result = _compute_trending([old, recent], _CUTOFF_7, None, set(), 10)
        assert len(result) == 1
        assert result[0].aggregate_score == pytest.approx(10.0)

    # ── Ordering and tiebreaks ────────────────────────────────────────────────

    def test_sorted_by_aggregate_desc(self) -> None:
        rows = [
            _trending_row(track_n=1, score=6),
            _trending_row(track_n=2, score=9),
            _trending_row(track_n=3, score=7),
        ]
        result = _compute_trending(rows, _CUTOFF_7, None, set(), 10)
        scores = [e.aggregate_score for e in result]
        assert scores == sorted(scores, reverse=True)
        assert scores == [9.0, 7.0, 6.0]

    def test_tiebreak_by_track_id_asc(self) -> None:
        """Identical aggregate scores → lower track_id first."""
        rows = [
            _trending_row(track_n=2, score=8),
            _trending_row(track_n=1, score=8),
        ]
        result = _compute_trending(rows, _CUTOFF_7, None, set(), 10)
        assert result[0].track.id == _track_id(1)
        assert result[1].track.id == _track_id(2)

    def test_tiebreak_is_deterministic_across_repeated_calls(self) -> None:
        rows = [
            _trending_row(track_n=3, score=8),
            _trending_row(track_n=1, score=8),
            _trending_row(track_n=2, score=8),
        ]
        first = _compute_trending(rows, _CUTOFF_7, None, set(), 10)
        second = _compute_trending(rows, _CUTOFF_7, None, set(), 10)
        assert [e.track.id for e in first] == [e.track.id for e in second]

    # ── Limit ─────────────────────────────────────────────────────────────────

    def test_limit_respected(self) -> None:
        rows = [_trending_row(track_n=n, score=n) for n in range(1, 6)]
        result = _compute_trending(rows, _CUTOFF_7, None, set(), 3)
        assert len(result) == 3

    def test_limit_one_returns_top_track(self) -> None:
        rows = [
            _trending_row(track_n=1, score=5),
            _trending_row(track_n=2, score=9),
        ]
        result = _compute_trending(rows, _CUTOFF_7, None, set(), 1)
        assert len(result) == 1
        assert result[0].track.id == _track_id(2)


# ── _compute_friends_top_tracks ───────────────────────────────────────────────


class TestComputeFriendsTopTracks:
    _viewer = _user_id(99)

    def test_empty_rows_returns_empty(self) -> None:
        assert _compute_friends_top_tracks([], _CUTOFF_30, self._viewer, 10) == []

    def test_single_public_row_in_window(self) -> None:
        rows = [_friend_row(friend_n=1, days_ago=1)]
        result = _compute_friends_top_tracks(rows, _CUTOFF_30, self._viewer, 10)
        assert len(result) == 1

    # ── Window boundary ───────────────────────────────────────────────────────

    def test_row_at_exact_cutoff_is_included(self) -> None:
        row = _friend_row()
        row.created_at = _CUTOFF_30
        result = _compute_friends_top_tracks([row], _CUTOFF_30, self._viewer, 10)
        assert len(result) == 1

    def test_row_one_microsecond_before_cutoff_is_excluded(self) -> None:
        row = _friend_row()
        row.created_at = _CUTOFF_30 - timedelta(microseconds=1)
        result = _compute_friends_top_tracks([row], _CUTOFF_30, self._viewer, 10)
        assert len(result) == 0

    # ── Self-exclusion ────────────────────────────────────────────────────────

    def test_viewer_own_ratings_never_appear_as_friend_entry(self) -> None:
        row = _friend_row(friend_n=1)
        row.friend_id = self._viewer  # viewer is the rater
        result = _compute_friends_top_tracks([row], _CUTOFF_30, self._viewer, 10)
        assert len(result) == 0

    # ── Top-track selection per friend ────────────────────────────────────────

    def test_one_entry_per_friend_even_with_multiple_tracks(self) -> None:
        rows = [
            _friend_row(friend_n=1, track_n=1, score=6),
            _friend_row(friend_n=1, track_n=2, score=9),
            _friend_row(friend_n=1, track_n=3, score=7),
        ]
        result = _compute_friends_top_tracks(rows, _CUTOFF_30, self._viewer, 10)
        assert len(result) == 1
        assert result[0].track.id == _track_id(2)  # highest score

    def test_tiebreak_by_most_recent_timestamp(self) -> None:
        """When two tracks tie on score, most recent rating wins."""
        rows = [
            _friend_row(friend_n=1, track_n=1, score=9, days_ago=10),
            _friend_row(friend_n=1, track_n=2, score=9, days_ago=1),
        ]
        result = _compute_friends_top_tracks(rows, _CUTOFF_30, self._viewer, 10)
        assert len(result) == 1
        assert result[0].track.id == _track_id(2)

    def test_tiebreak_final_by_track_id_asc(self) -> None:
        """When score and timestamp tie, lower track_id (UUID ASC) wins."""
        ts = _dt(1)
        rows = [
            _FriendRow(
                friend_id=_user_id(1),
                friend_username="f1",
                friend_display_name="F1",
                friend_avatar_url=None,
                track_id=_track_id(3),
                track_mbid="m3",
                track_title="T3",
                artist_name=None,
                cover_art_url=None,
                score=9,
                visibility="public",
                created_at=ts,
            ),
            _FriendRow(
                friend_id=_user_id(1),
                friend_username="f1",
                friend_display_name="F1",
                friend_avatar_url=None,
                track_id=_track_id(1),
                track_mbid="m1",
                track_title="T1",
                artist_name=None,
                cover_art_url=None,
                score=9,
                visibility="public",
                created_at=ts,
            ),
        ]
        result = _compute_friends_top_tracks(rows, _CUTOFF_30, self._viewer, 10)
        assert len(result) == 1
        assert result[0].track.id == _track_id(1)  # lower UUID wins

    def test_most_recent_per_friend_track_used_for_score(self) -> None:
        """A re-rated track only contributes the most recent score."""
        old = _friend_row(friend_n=1, track_n=1, score=2, days_ago=20)
        recent = _friend_row(friend_n=1, track_n=1, score=10, days_ago=1)
        result = _compute_friends_top_tracks([old, recent], _CUTOFF_30, self._viewer, 10)
        assert len(result) == 1
        assert result[0].score == 10

    # ── Multiple friends ──────────────────────────────────────────────────────

    def test_multiple_friends_one_entry_each(self) -> None:
        rows = [
            _friend_row(friend_n=1, track_n=1),
            _friend_row(friend_n=2, track_n=2),
            _friend_row(friend_n=3, track_n=3),
        ]
        result = _compute_friends_top_tracks(rows, _CUTOFF_30, self._viewer, 10)
        assert len(result) == 3
        friend_ids = {e.rated_by.id for e in result}
        assert len(friend_ids) == 3

    def test_entries_ordered_by_rating_timestamp_desc(self) -> None:
        """The overall list is ordered by each friend's selected track timestamp, newest first."""
        rows = [
            _friend_row(friend_n=1, track_n=1, days_ago=15),
            _friend_row(friend_n=2, track_n=2, days_ago=1),
        ]
        result = _compute_friends_top_tracks(rows, _CUTOFF_30, self._viewer, 10)
        assert result[0].rated_by.id == _user_id(2)  # more recent first
        assert result[1].rated_by.id == _user_id(1)

    # ── Limit ─────────────────────────────────────────────────────────────────

    def test_limit_respected(self) -> None:
        rows = [_friend_row(friend_n=n, track_n=n) for n in range(1, 6)]
        result = _compute_friends_top_tracks(rows, _CUTOFF_30, self._viewer, 3)
        assert len(result) == 3

    # ── Visibility (PRIVATE rows must not reach this function) ────────────────

    def test_public_rating_surfaces(self) -> None:
        rows = [_friend_row(visibility="public")]
        result = _compute_friends_top_tracks(rows, _CUTOFF_30, self._viewer, 10)
        assert len(result) == 1

    def test_friends_scoped_rating_surfaces(self) -> None:
        """FRIENDS-scoped ratings from mutual follows are already included by the SQL
        filter (which only excludes PRIVATE); the pure function does not re-check."""
        rows = [_friend_row(visibility="friends")]
        result = _compute_friends_top_tracks(rows, _CUTOFF_30, self._viewer, 10)
        assert len(result) == 1


# ── _safe_section ─────────────────────────────────────────────────────────────


class TestSafeSection:
    @pytest.mark.asyncio
    async def test_returns_result_on_success(self) -> None:
        async def ok() -> list[str]:
            return ["a", "b"]

        result = await _safe_section("test", ok())
        assert result == ["a", "b"]

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self) -> None:
        async def fail() -> list[str]:
            raise RuntimeError("boom")

        result = await _safe_section("test", fail())
        assert result is None

    @pytest.mark.asyncio
    async def test_one_section_failing_does_not_affect_another(self) -> None:
        """Verify that two _safe_section calls are truly independent."""

        async def trending_fail() -> list[str]:
            raise RuntimeError("trending down")

        async def friends_ok() -> list[str]:
            return ["track_x"]

        trending = await _safe_section("trending", trending_fail())
        friends = await _safe_section("friends", friends_ok())

        assert trending is None  # section failed
        assert friends == ["track_x"]  # other section unaffected
