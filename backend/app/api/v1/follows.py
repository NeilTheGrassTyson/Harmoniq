"""
Follows API: follow, unfollow, follower list, following list.

Rate limiting on write endpoints matches the abuse-prevention pattern
established in Feature 3 (ratings).
"""

import logging

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.v1.deps import CurrentUser, DbSession, OptionalClerkId
from app.core.rate_limit import limiter
from app.schemas.follow import FollowListResponse, FollowState
from app.services import follow as follow_svc
from app.services import user as user_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/follows", tags=["follows"])

_FOLLOW_ERROR = "Something went wrong. Try again."


# ── Follow a user ─────────────────────────────────────────────────────────────


@router.post("/{username}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def follow_user(
    request: Request,
    username: str,
    session: DbSession,
    current_user: CurrentUser,
) -> None:
    target = await user_svc.get_by_username(session, username)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot follow yourself.",
        )

    try:
        await follow_svc.follow(session, current_user.id, target.id)
        await session.commit()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except Exception as exc:
        await session.rollback()
        logger.exception(
            "Follow failed: follower=%s target=%s", current_user.id, target.id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_FOLLOW_ERROR
        ) from exc


# ── Unfollow a user ───────────────────────────────────────────────────────────


@router.delete("/{username}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def unfollow_user(
    request: Request,
    username: str,
    session: DbSession,
    current_user: CurrentUser,
) -> None:
    target = await user_svc.get_by_username(session, username)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    try:
        await follow_svc.unfollow(session, current_user.id, target.id)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.exception(
            "Unfollow failed: follower=%s target=%s", current_user.id, target.id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_FOLLOW_ERROR
        ) from exc


# ── Follow state for a profile (viewer → profile owner) ──────────────────────


@router.get("/{username}/state", response_model=FollowState)
async def get_follow_state(
    username: str,
    session: DbSession,
    viewer_clerk_id: OptionalClerkId,
) -> FollowState:
    target = await user_svc.get_by_username(session, username)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    if viewer_clerk_id is None:
        return FollowState(is_following=False, follows_you=False, is_friend=False)

    viewer = await user_svc.get_by_clerk_id(session, viewer_clerk_id)
    if viewer is None or viewer.id == target.id:
        return FollowState(is_following=False, follows_you=False, is_friend=False)

    return await follow_svc.get_follow_state(session, viewer.id, target.id)


# ── Follower list ─────────────────────────────────────────────────────────────


@router.get("/{username}/followers", response_model=FollowListResponse)
async def list_followers(
    username: str,
    session: DbSession,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> FollowListResponse:
    target = await user_svc.get_by_username(session, username)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    return await follow_svc.get_followers(
        session, target.id, cursor=cursor, limit=limit
    )


# ── Following list ────────────────────────────────────────────────────────────


@router.get("/{username}/following", response_model=FollowListResponse)
async def list_following(
    username: str,
    session: DbSession,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> FollowListResponse:
    target = await user_svc.get_by_username(session, username)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    return await follow_svc.get_following(
        session, target.id, cursor=cursor, limit=limit
    )
