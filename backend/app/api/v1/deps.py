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
