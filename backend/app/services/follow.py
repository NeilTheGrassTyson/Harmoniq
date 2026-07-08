"""
Follow service: follow/unfollow, mutual-follow check, counts, and paginated lists.

All writes use ON CONFLICT DO NOTHING (follow) or plain DELETE (unfollow) so
repeated requests are naturally idempotent without application-level locking.
"""

import logging
import uuid
from typing import Any, cast

from sqlalchemy import CursorResult, and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import VisibilityScope
from app.core.visibility import scope_allows
from app.models.follow import Follow
from app.models.user import User
from app.schemas.follow import (
    FollowCursor,
    FollowListResponse,
    FollowState,
    FollowSummary,
)

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 20


# ── Core write operations ─────────────────────────────────────────────────────


async def follow(
    session: AsyncSession,
    follower_id: uuid.UUID,
    followed_id: uuid.UUID,
) -> bool:
    """
    Returns True when a new edge was created, False when it already existed
    (so callers can skip side effects like notifications on re-follows).
    Raises ValueError on self-follow.
    """
    if follower_id == followed_id:
        raise ValueError("A user cannot follow themselves.")
    stmt = (
        pg_insert(Follow)
        .values(follower_id=follower_id, followed_id=followed_id)
        .on_conflict_do_nothing(index_elements=["follower_id", "followed_id"])
    )
    result = cast(CursorResult[Any], await session.execute(stmt))
    created = result.rowcount > 0
    logger.info(
        "Follow: follower_id=%s → followed_id=%s created=%s",
        follower_id,
        followed_id,
        created,
    )
    return created


async def unfollow(
    session: AsyncSession,
    follower_id: uuid.UUID,
    followed_id: uuid.UUID,
) -> None:
    """Remove a follow edge. No-op if it doesn't exist."""
    stmt = delete(Follow).where(
        Follow.follower_id == follower_id,
        Follow.followed_id == followed_id,
    )
    await session.execute(stmt)
    logger.info("Unfollow: follower_id=%s → followed_id=%s", follower_id, followed_id)


# ── Follow-list visibility ────────────────────────────────────────────────────


async def can_view_follow_lists(
    session: AsyncSession,
    owner: User,
    viewer: User | None,
) -> bool:
    """
    True if viewer may see owner's follower/following lists, per the owner's
    visibility_follows scope. Owner always may. Enforced here, at the
    data-access layer, per ENGINEERING_BIBLE §8.1.
    """
    is_owner = viewer is not None and viewer.id == owner.id
    if is_owner:
        return True
    scope = VisibilityScope(owner.visibility_follows)
    is_friend = False
    if scope == VisibilityScope.FRIENDS and viewer is not None:
        is_friend = await is_mutual_follow(session, viewer.id, owner.id)
    return scope_allows(scope, is_owner=False, is_friend=is_friend)


# ── Mutual-follow check ───────────────────────────────────────────────────────


async def is_mutual_follow(
    session: AsyncSession,
    user_a_id: uuid.UUID,
    user_b_id: uuid.UUID,
) -> bool:
    """
    Returns True iff A follows B and B follows A.
    Symmetric: argument order does not affect the result.
    """
    result = await session.execute(
        select(func.count())
        .select_from(Follow)
        .where(
            or_(
                and_(Follow.follower_id == user_a_id, Follow.followed_id == user_b_id),
                and_(Follow.follower_id == user_b_id, Follow.followed_id == user_a_id),
            )
        )
    )
    count = result.scalar_one()
    return count == 2


# ── Counts ────────────────────────────────────────────────────────────────────


async def get_mutual_follow_ids(
    session: AsyncSession,
    viewer_id: uuid.UUID,
) -> set[uuid.UUID]:
    """Return the set of user IDs who are mutual follows (friends) of viewer."""
    following_viewer = select(Follow.follower_id).where(Follow.followed_id == viewer_id)
    result = await session.execute(
        select(Follow.followed_id)
        .where(Follow.follower_id == viewer_id)
        .where(Follow.followed_id.in_(following_viewer))
    )
    return {row[0] for row in result.all()}


async def get_follower_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count()).select_from(Follow).where(Follow.followed_id == user_id)
    )
    return result.scalar_one()


async def get_following_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count()).select_from(Follow).where(Follow.follower_id == user_id)
    )
    return result.scalar_one()


# ── Follow state (for profile responses) ─────────────────────────────────────


async def get_follow_state(
    session: AsyncSession,
    viewer_id: uuid.UUID,
    profile_id: uuid.UUID,
) -> FollowState:
    """
    Returns the follow relationship between viewer and profile owner.
    viewer_id must not equal profile_id (callers should not call this on own profiles).
    """
    rows = await session.execute(
        select(Follow.follower_id, Follow.followed_id).where(
            or_(
                and_(Follow.follower_id == viewer_id, Follow.followed_id == profile_id),
                and_(Follow.follower_id == profile_id, Follow.followed_id == viewer_id),
            )
        )
    )
    edges = {(r.follower_id, r.followed_id) for r in rows}
    is_following = (viewer_id, profile_id) in edges
    follows_you = (profile_id, viewer_id) in edges
    return FollowState(
        is_following=is_following,
        follows_you=follows_you,
        is_friend=is_following and follows_you,
    )


# ── Paginated lists ───────────────────────────────────────────────────────────


async def get_followers(
    session: AsyncSession,
    user_id: uuid.UUID,
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> FollowListResponse:
    """
    Returns the paginated list of users who follow `user_id`.
    Ordered: most-recently-followed first, follower_id ASC as tiebreak.
    """
    base = (
        select(Follow.follower_id, Follow.created_at, User)
        .join(User, User.id == Follow.follower_id)
        .where(Follow.followed_id == user_id)
    )

    if cursor is not None:
        c = FollowCursor.decode(cursor)
        base = base.where(
            or_(
                Follow.created_at < c.created_at,
                and_(Follow.created_at == c.created_at, Follow.follower_id > c.user_id),
            )
        )

    base = base.order_by(Follow.created_at.desc(), Follow.follower_id.asc()).limit(
        limit + 1
    )
    rows = (await session.execute(base)).all()

    has_more = len(rows) > limit
    page = rows[:limit]

    items = [
        FollowSummary(
            user_id=row.follower_id,
            username=row.User.username,
            display_name=row.User.display_name,
            avatar_url=row.User.avatar_url,
        )
        for row in page
    ]

    next_cursor: str | None = None
    if has_more and page:
        last = page[-1]
        next_cursor = FollowCursor(
            created_at=last.created_at, user_id=last.follower_id
        ).encode()

    return FollowListResponse(items=items, next_cursor=next_cursor)


async def get_following(
    session: AsyncSession,
    user_id: uuid.UUID,
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> FollowListResponse:
    """
    Returns the paginated list of users that `user_id` follows.
    Ordered: most-recently-followed first, followed_id ASC as tiebreak.
    """
    base = (
        select(Follow.followed_id, Follow.created_at, User)
        .join(User, User.id == Follow.followed_id)
        .where(Follow.follower_id == user_id)
    )

    if cursor is not None:
        c = FollowCursor.decode(cursor)
        base = base.where(
            or_(
                Follow.created_at < c.created_at,
                and_(Follow.created_at == c.created_at, Follow.followed_id > c.user_id),
            )
        )

    base = base.order_by(Follow.created_at.desc(), Follow.followed_id.asc()).limit(
        limit + 1
    )
    rows = (await session.execute(base)).all()

    has_more = len(rows) > limit
    page = rows[:limit]

    items = [
        FollowSummary(
            user_id=row.followed_id,
            username=row.User.username,
            display_name=row.User.display_name,
            avatar_url=row.User.avatar_url,
        )
        for row in page
    ]

    next_cursor: str | None = None
    if has_more and page:
        last = page[-1]
        next_cursor = FollowCursor(
            created_at=last.created_at, user_id=last.followed_id
        ).encode()

    return FollowListResponse(items=items, next_cursor=next_cursor)
