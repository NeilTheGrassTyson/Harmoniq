"""
User service: creation, profile retrieval with visibility enforcement,
profile updates, and Clerk webhook sync.

Visibility enforcement is always performed at this layer — never in the
route handler or on the frontend.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import VisibilityScope
from app.models.user import User
from app.schemas.follow import FollowState
from app.schemas.user import OwnProfileResponse, ProfileResponse, UserSearchResult
from app.services import follow as follow_svc
from app.services import rating as rating_svc

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=UTC)


# ── Friends check ─────────────────────────────────────────────────────────────


async def _is_friend(
    session: AsyncSession,
    viewer_id: uuid.UUID,
    profile_id: uuid.UUID,
) -> bool:
    return await follow_svc.is_mutual_follow(session, viewer_id, profile_id)


# ── Basic lookups ─────────────────────────────────────────────────────────────


async def get_by_clerk_id(session: AsyncSession, clerk_id: str) -> User | None:
    result = await session.execute(select(User).where(User.clerk_id == clerk_id))
    return result.scalar_one_or_none()


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(
        select(User).where(User.username == username.lower())
    )
    return result.scalar_one_or_none()


async def is_username_available(session: AsyncSession, username: str) -> bool:
    result = await session.execute(
        select(User.id).where(User.username == username.lower())
    )
    return result.scalar_one_or_none() is None


# ── Creation ──────────────────────────────────────────────────────────────────


async def create_user(
    session: AsyncSession,
    clerk_id: str,
    username: str,
    display_name: str,
) -> User:
    user = User(
        id=uuid.uuid4(),
        clerk_id=clerk_id,
        username=username.lower(),
        display_name=display_name,
        avatar_url=None,
        bio=None,
        visibility_bio=VisibilityScope.PRIVATE.value,
        visibility_activity=VisibilityScope.PRIVATE.value,
        visibility_ratings=VisibilityScope.PRIVATE.value,
    )
    session.add(user)
    logger.info("Created Harmoniq user internal_id=%s", user.id)
    return user


# ── Profile views ─────────────────────────────────────────────────────────────


def build_own_profile(user: User) -> OwnProfileResponse:
    return OwnProfileResponse(
        username=user.username,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        bio=user.bio,
        visibility_bio=VisibilityScope(user.visibility_bio),
        visibility_activity=VisibilityScope(user.visibility_activity),
        visibility_ratings=VisibilityScope(user.visibility_ratings),
    )


async def get_profile(
    session: AsyncSession,
    username: str,
    viewer_clerk_id: str | None,
) -> ProfileResponse | None:
    user = await get_by_username(session, username)
    if user is None:
        return None

    is_own = False
    is_friend = False
    viewer: User | None = None

    if viewer_clerk_id:
        viewer = await get_by_clerk_id(session, viewer_clerk_id)
        if viewer is not None:
            is_own = viewer.id == user.id
            if not is_own:
                is_friend = await _is_friend(session, viewer.id, user.id)

    def can_see(scope_str: str) -> bool:
        scope = VisibilityScope(scope_str)
        if is_own:
            return True
        if scope == VisibilityScope.PUBLIC:
            return True
        if scope == VisibilityScope.FRIENDS and is_friend:
            return True
        logger.debug(
            "Visibility: field scope=%s viewer_is_own=%s viewer_is_friend=%s → denied",
            scope_str,
            is_own,
            is_friend,
        )
        return False

    follower_count = await follow_svc.get_follower_count(session, user.id)
    following_count = await follow_svc.get_following_count(session, user.id)

    follow_state: FollowState | None = None
    if not is_own and viewer is not None:
        follow_state = await follow_svc.get_follow_state(session, viewer.id, user.id)

    fields: dict[str, Any] = {
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "is_own_profile": is_own,
        "follower_count": follower_count,
        "following_count": following_count,
    }
    if follow_state is not None:
        fields["follow"] = follow_state

    # Bio: include for own profile (even if null, for "Add a bio" prompt) or
    # when viewer has permission AND bio has a value.
    if can_see(user.visibility_bio):
        if is_own or user.bio is not None:
            fields["bio"] = user.bio

    # Listening activity: Phase 1 — always a placeholder when visible.
    if can_see(user.visibility_activity):
        fields["activity_placeholder"] = True

    # Ratings count: queried live from ratings table.
    if can_see(user.visibility_ratings):
        viewer_id = viewer.id if viewer is not None else None
        fields["ratings_count"] = await rating_svc.count_for_user(
            session, user.id, viewer_id
        )

    return ProfileResponse.model_construct(**fields)


# ── Updates ───────────────────────────────────────────────────────────────────


async def update_profile(
    session: AsyncSession,
    user: User,
    display_name: str | None,
    username: str | None,
    bio: str | None,
    visibility_bio: VisibilityScope | None,
    visibility_activity: VisibilityScope | None,
    visibility_ratings: VisibilityScope | None,
) -> OwnProfileResponse:
    if display_name is not None:
        user.display_name = display_name

    if username is not None and username != user.username:
        old_username = user.username
        user.username = username.lower()
        logger.info(
            "Username changed internal_id=%s old=%s new=%s",
            user.id,
            old_username,
            username,
        )

    # bio=None means "clear the field". The route handler resolves model_fields_set
    # before calling here, so bio already holds the correct value to apply.
    user.bio = bio

    if visibility_bio is not None:
        old = user.visibility_bio
        user.visibility_bio = visibility_bio.value
        if old != visibility_bio.value:
            logger.info(
                "Visibility changed internal_id=%s field=bio %s→%s",
                user.id,
                old,
                visibility_bio.value,
            )

    if visibility_activity is not None:
        old = user.visibility_activity
        user.visibility_activity = visibility_activity.value
        if old != visibility_activity.value:
            logger.info(
                "Visibility changed internal_id=%s field=activity %s→%s",
                user.id,
                old,
                visibility_activity.value,
            )

    if visibility_ratings is not None:
        old = user.visibility_ratings
        user.visibility_ratings = visibility_ratings.value
        if old != visibility_ratings.value:
            logger.info(
                "Visibility changed internal_id=%s field=ratings %s→%s",
                user.id,
                old,
                visibility_ratings.value,
            )

    user.updated_at = _now()
    return build_own_profile(user)


async def update_avatar_url(
    session: AsyncSession,
    user: User,
    avatar_url: str,
) -> str:
    user.avatar_url = avatar_url
    user.updated_at = _now()
    logger.info("Avatar updated internal_id=%s", user.id)
    return avatar_url


# ── User search ───────────────────────────────────────────────────────────────


def filter_discoverable_users(query):
    # Currently a pass-through — all users are discoverable at launch.
    # This function is security scaffolding: when private profiles ship (e.g. a
    # future visibility_profile column), add the WHERE clause here rather than
    # scattering it across callers. This keeps enforcement at the service layer
    # per ENGINEERING_BIBLE §8.1. The stub exists now so the test harness is
    # in place and the change surface is predictable.
    return query


async def search_users(session: AsyncSession, q: str) -> list[UserSearchResult]:
    pattern = f"%{q}%"
    stmt = (
        select(User)
        .where(or_(User.username.ilike(pattern), User.display_name.ilike(pattern)))
        .order_by(User.username)
        .limit(20)
    )
    stmt = filter_discoverable_users(stmt)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        UserSearchResult(
            username=u.username,
            display_name=u.display_name,
            avatar_url=u.avatar_url,
        )
        for u in rows
    ]


# ── Clerk webhook sync ────────────────────────────────────────────────────────


async def sync_from_clerk(
    session: AsyncSession,
    clerk_id: str,
    display_name: str | None,
    avatar_url: str | None,
) -> None:
    user = await get_by_clerk_id(session, clerk_id)
    if user is None:
        logger.debug("Clerk webhook: no Harmoniq record for clerk_id (redacted)")
        return

    changed = False
    if display_name and display_name != user.display_name:
        user.display_name = display_name
        changed = True
    if avatar_url is not None and avatar_url != user.avatar_url:
        user.avatar_url = avatar_url or None
        changed = True

    if changed:
        user.updated_at = _now()
        logger.info(
            "Clerk webhook synced display_name/avatar for internal_id=%s", user.id
        )
    else:
        logger.debug("Clerk webhook: no changes for internal_id=%s", user.id)
