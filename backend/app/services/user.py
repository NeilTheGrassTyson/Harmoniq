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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import VisibilityScope
from app.models.user import User
from app.schemas.user import OwnProfileResponse, ProfileResponse

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=UTC)


# ── Friends check (stub) ──────────────────────────────────────────────────────


async def _is_friend(
    _session: AsyncSession,
    _viewer_id: uuid.UUID,
    _profile_id: uuid.UUID,
) -> bool:
    # Stub: follows table not yet implemented. Until it exists, FRIENDS-scoped
    # fields behave as PRIVATE for non-owners — no special-casing required.
    return False


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

    fields: dict[str, Any] = {
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "is_own_profile": is_own,
    }

    # Bio: include for own profile (even if null, for "Add a bio" prompt) or
    # when viewer has permission AND bio has a value.
    if can_see(user.visibility_bio):
        if is_own or user.bio is not None:
            fields["bio"] = user.bio

    # Listening activity: Phase 1 — always a placeholder when visible.
    if can_see(user.visibility_activity):
        fields["activity_placeholder"] = True

    # Ratings count: queried live from ratings table (Phase 1: always 0).
    if can_see(user.visibility_ratings):
        # TODO: replace with an actual count query when the ratings table exists.
        fields["ratings_count"] = 0

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
        user.username = username
        logger.info(
            "Username changed internal_id=%s old=%s new=%s",
            user.id,
            old_username,
            username,
        )

    # bio=None means "clear the field"; the validator converts empty string to None.
    # We only apply the update when the key is explicitly included in the request.
    # This check is performed in the route handler via request.model_fields_set.
    if bio is not None or bio == user.bio:
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
