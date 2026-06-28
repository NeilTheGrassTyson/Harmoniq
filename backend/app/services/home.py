"""
Home service: Trending and Top songs from friends computations.

Both queries are bounded (exactly N results, no pagination, no ranking function)
per ENGINEERING_BIBLE §5. The core business logic lives in pure helper functions
(_compute_trending, _compute_friends_top_tracks) so it can be tested without a
database; the async functions handle DB I/O and delegate to those helpers.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import VisibilityScope
from app.models.catalog import Album, Artist, Track
from app.models.rating import Rating
from app.models.user import User
from app.schemas.home import FriendEntry, TrackSummary, TrendingEntry, UserSummary

logger = logging.getLogger(__name__)

TRENDING_WINDOW_DAYS = 7
FRIENDS_WINDOW_DAYS = 30


def _now() -> datetime:
    return datetime.now(tz=UTC)


# ── Row types ─────────────────────────────────────────────────────────────────


@dataclass
class _TrendingRow:
    track_id: uuid.UUID
    user_id: uuid.UUID
    score: int
    visibility: str
    created_at: datetime
    mbid: str
    title: str
    artist_name: str | None
    cover_art_url: str | None


@dataclass
class _FriendRow:
    friend_id: uuid.UUID
    friend_username: str
    friend_display_name: str
    friend_avatar_url: str | None
    track_id: uuid.UUID
    track_mbid: str
    track_title: str
    artist_name: str | None
    cover_art_url: str | None
    score: int
    visibility: str
    created_at: datetime


# ── Pure helpers ──────────────────────────────────────────────────────────────


def _is_visible_to_viewer(
    visibility: str,
    rater_id: uuid.UUID,
    viewer_id: uuid.UUID | None,
    mutual_follow_ids: set[uuid.UUID],
) -> bool:
    """Return True if this rating is visible to viewer. No I/O."""
    if viewer_id is not None and rater_id == viewer_id:
        return True
    scope = VisibilityScope(visibility)
    if scope == VisibilityScope.PUBLIC:
        return True
    if scope == VisibilityScope.FRIENDS and rater_id in mutual_follow_ids:
        return True
    return False


def _compute_trending(
    rows: list[_TrendingRow],
    cutoff: datetime,
    viewer_id: uuid.UUID | None,
    mutual_follow_ids: set[uuid.UUID],
    limit: int,
) -> list[TrendingEntry]:
    """
    Pure computation: top-N tracks by aggregate rating in window, filtered by
    viewer visibility. Testable without a database.

    Aggregate = average of each user's most-recent rating per track.
    A track appears only if at least one of its qualifying ratings is visible
    to viewer — visibility does NOT affect which scores count toward the average.
    Tiebreak: aggregate DESC, then track_id ASC for full determinism.
    """
    in_window = [r for r in rows if r.created_at >= cutoff]
    if not in_window:
        return []

    # Per (track, user) keep only the most recent rating in the window.
    latest: dict[tuple[uuid.UUID, uuid.UUID], _TrendingRow] = {}
    track_info: dict[uuid.UUID, tuple[str, str, str | None, str | None]] = {}
    for row in in_window:
        key = (row.track_id, row.user_id)
        if key not in latest or row.created_at > latest[key].created_at:
            latest[key] = row
        if row.track_id not in track_info:
            track_info[row.track_id] = (
                row.mbid,
                row.title,
                row.artist_name,
                row.cover_art_url,
            )

    # Collect scores per track; mark tracks that have at least one visible rating.
    track_scores: dict[uuid.UUID, list[int]] = defaultdict(list)
    track_visible: set[uuid.UUID] = set()
    for (track_id, user_id), row in latest.items():
        track_scores[track_id].append(row.score)
        if _is_visible_to_viewer(row.visibility, user_id, viewer_id, mutual_follow_ids):
            track_visible.add(track_id)

    # Compute aggregates for visible tracks, then sort.
    entries: list[tuple[float, uuid.UUID]] = []
    for track_id in track_visible:
        scores = track_scores[track_id]
        entries.append((sum(scores) / len(scores), track_id))
    entries.sort(key=lambda x: (-x[0], x[1]))

    result = []
    for aggregate, track_id in entries[:limit]:
        mbid, title, artist_name, cover_art_url = track_info[track_id]
        result.append(
            TrendingEntry(
                track=TrackSummary(
                    id=track_id,
                    mbid=mbid,
                    title=title,
                    artist_name=artist_name,
                    cover_art_url=cover_art_url,
                ),
                aggregate_score=aggregate,
            )
        )
    return result


def _compute_friends_top_tracks(
    rows: list[_FriendRow],
    cutoff: datetime,
    viewer_id: uuid.UUID,
    limit: int,
) -> list[FriendEntry]:
    """
    Pure computation: each mutual-follow friend's single highest-rated track in
    the window. PRIVATE ratings must not be passed in (filter in the SQL query).
    Tiebreak within a friend's tracks: score DESC, created_at DESC, track_id ASC.
    Tiebreak across friends' entries: created_at DESC, track_id ASC.
    Testable without a database.
    """
    in_window = [r for r in rows if r.created_at >= cutoff and r.friend_id != viewer_id]
    if not in_window:
        return []

    # Per (friend, track) keep only the most recent rating.
    latest: dict[tuple[uuid.UUID, uuid.UUID], _FriendRow] = {}
    for row in in_window:
        key = (row.friend_id, row.track_id)
        if key not in latest or row.created_at > latest[key].created_at:
            latest[key] = row

    # Per friend, pick their single best track.
    friend_tracks: dict[uuid.UUID, list[_FriendRow]] = defaultdict(list)
    for row in latest.values():
        friend_tracks[row.friend_id].append(row)

    friend_top: list[_FriendRow] = []
    for track_rows in friend_tracks.values():
        # score DESC → created_at DESC → track_id ASC
        track_rows.sort(
            key=lambda r: (-r.score, -(r.created_at.timestamp()), r.track_id)
        )
        friend_top.append(track_rows[0])

    # Sort all friend entries: most recent timestamp first, track_id ASC tiebreak.
    friend_top.sort(key=lambda r: (-(r.created_at.timestamp()), r.track_id))

    return [
        FriendEntry(
            track=TrackSummary(
                id=row.track_id,
                mbid=row.track_mbid,
                title=row.track_title,
                artist_name=row.artist_name,
                cover_art_url=row.cover_art_url,
            ),
            score=row.score,
            rated_by=UserSummary(
                id=row.friend_id,
                username=row.friend_username,
                display_name=row.friend_display_name,
                avatar_url=row.friend_avatar_url,
            ),
        )
        for row in friend_top[:limit]
    ]


# ── Section independence helper ───────────────────────────────────────────────


async def _safe_section(name: str, coro: Awaitable[Any]) -> Any:
    """
    Awaits coro and returns its result. On any exception, logs and returns None
    so the caller can distinguish 'error' from 'genuinely empty list'.
    """
    try:
        return await coro
    except Exception:
        logger.exception("Home section %r failed to load", name)
        return None


# ── Public async API ──────────────────────────────────────────────────────────


async def get_trending(
    session: AsyncSession,
    viewer_id: uuid.UUID | None,
    limit: int,
) -> list[TrendingEntry]:
    """Fetch and compute Trending for the given viewer."""
    now = _now()
    cutoff = now - timedelta(days=TRENDING_WINDOW_DAYS)

    rows_result = await session.execute(
        select(
            Rating.entity_id.label("track_id"),
            Rating.user_id,
            Rating.score,
            Rating.visibility,
            Rating.created_at,
            Track.mbid,
            Track.title,
            Artist.name.label("artist_name"),
            Album.cover_art_url,
        )
        .join(Track, Track.id == Rating.entity_id)
        .outerjoin(Artist, Artist.id == Track.artist_id)
        .outerjoin(Album, Album.id == Track.album_id)
        .where(
            Rating.entity_type == "track",
            Rating.created_at >= cutoff,
        )
    )

    rows = [
        _TrendingRow(
            track_id=r.track_id,
            user_id=r.user_id,
            score=r.score,
            visibility=r.visibility,
            created_at=r.created_at,
            mbid=r.mbid,
            title=r.title,
            artist_name=r.artist_name,
            cover_art_url=r.cover_art_url,
        )
        for r in rows_result.all()
    ]

    mutual_follow_ids: set[uuid.UUID] = set()
    if viewer_id is not None:
        from app.services import follow as follow_svc

        mutual_follow_ids = await follow_svc.get_mutual_follow_ids(session, viewer_id)

    return _compute_trending(rows, cutoff, viewer_id, mutual_follow_ids, limit)


async def get_friends_top_tracks(
    session: AsyncSession,
    viewer_id: uuid.UUID,
    limit: int,
    mutual_follow_ids: set[uuid.UUID] | None = None,
) -> list[FriendEntry]:
    """Fetch and compute Top songs from friends for the given viewer."""
    if mutual_follow_ids is None:
        from app.services import follow as follow_svc

        mutual_follow_ids = await follow_svc.get_mutual_follow_ids(session, viewer_id)

    if not mutual_follow_ids:
        return []

    now = _now()
    cutoff = now - timedelta(days=FRIENDS_WINDOW_DAYS)

    rows_result = await session.execute(
        select(
            Rating.user_id.label("friend_id"),
            User.username.label("friend_username"),
            User.display_name.label("friend_display_name"),
            User.avatar_url.label("friend_avatar_url"),
            Rating.entity_id.label("track_id"),
            Track.mbid.label("track_mbid"),
            Track.title.label("track_title"),
            Artist.name.label("artist_name"),
            Album.cover_art_url,
            Rating.score,
            Rating.visibility,
            Rating.created_at,
        )
        .join(User, User.id == Rating.user_id)
        .join(Track, Track.id == Rating.entity_id)
        .outerjoin(Artist, Artist.id == Track.artist_id)
        .outerjoin(Album, Album.id == Track.album_id)
        .where(
            Rating.entity_type == "track",
            Rating.created_at >= cutoff,
            Rating.user_id.in_(mutual_follow_ids),
            Rating.visibility != VisibilityScope.PRIVATE.value,
        )
    )

    rows = [
        _FriendRow(
            friend_id=r.friend_id,
            friend_username=r.friend_username,
            friend_display_name=r.friend_display_name,
            friend_avatar_url=r.friend_avatar_url,
            track_id=r.track_id,
            track_mbid=r.track_mbid,
            track_title=r.track_title,
            artist_name=r.artist_name,
            cover_art_url=r.cover_art_url,
            score=r.score,
            visibility=r.visibility,
            created_at=r.created_at,
        )
        for r in rows_result.all()
    ]

    return _compute_friends_top_tracks(rows, cutoff, viewer_id, limit)
