"""
Shared FastAPI dependencies for v1 routes.

Import DbSession, ClerkUserId, OptionalClerkId, and CurrentUser from here
rather than re-declaring them per-file.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, get_optional_clerk_id
from app.database import get_db
from app.models.user import User
from app.services import user as user_svc

DbSession = Annotated[AsyncSession, Depends(get_db)]
ClerkUserId = Annotated[str, Depends(get_current_user)]
OptionalClerkId = Annotated[str | None, Depends(get_optional_clerk_id)]


async def _get_current_user_record(
    clerk_id: ClerkUserId,
    session: DbSession,
) -> User:
    user = await user_svc.get_by_clerk_id(session, clerk_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user


CurrentUser = Annotated[User, Depends(_get_current_user_record)]


async def _get_current_active_user(current_user: CurrentUser) -> User:
    """
    The single suspension-enforcement point. Every write endpoint depends on
    this instead of CurrentUser; reads keep CurrentUser so a suspended user
    can still browse (Founder decision 2026-07-07 — writes blocked, reads OK).
    """
    if current_user.suspended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Your account is suspended. You can browse, but you can't"
                " post, follow, or send right now."
            ),
        )
    return current_user


CurrentActiveUser = Annotated[User, Depends(_get_current_active_user)]


async def _get_current_moderator(current_user: CurrentUser) -> User:
    """
    404 (not 403) for non-moderators and suspended moderators: the moderation
    surface's existence is hidden from probing users. The frontend learns
    moderator status from /users/me instead.
    """
    if not current_user.is_moderator or current_user.suspended_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    return current_user


CurrentModerator = Annotated[User, Depends(_get_current_moderator)]
