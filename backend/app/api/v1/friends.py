"""
Friends API: request, accept, decline, remove, and the owner's overview.
There is no withdraw: a sender never sees their own outstanding request
(specs/phase-2-friend-requests.md, Founder decision 2026-09-27).

Every response is private and uncached — a relationship is between the two
people in it. Writes require an active (unsuspended) account.
"""

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.v1.deps import CurrentActiveUser, CurrentUser, DbSession
from app.config import settings
from app.core.rate_limit import limiter
from app.models.user import User
from app.schemas.friendship import FriendshipStateResponse, FriendsOverview
from app.services import friendship as friendship_svc
from app.services import user as user_svc

router = APIRouter(prefix="/friends", tags=["friends"])


def _require_enabled(response: Response) -> None:
    if not settings.friendships_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Friends are unavailable.")
    response.headers["Cache-Control"] = "private, no-store"


async def _other(session: DbSession, username: str) -> User:
    other = await user_svc.get_by_username(session, username)
    if other is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    return other


@router.get("/me", response_model=FriendsOverview)
async def get_overview(
    response: Response, session: DbSession, current_user: CurrentUser
) -> FriendsOverview:
    _require_enabled(response)
    return await friendship_svc.overview(session, current_user)


# Sending is the only gesture that reaches another person, so it carries the
# tight limit: a silent decline leaves the recipient no other lever.
@router.post("/{username}/request", response_model=FriendshipStateResponse)
@limiter.limit("5/minute;30/day")
async def send_request(
    request: Request,
    response: Response,
    username: str,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> FriendshipStateResponse:
    _require_enabled(response)
    other = await _other(session, username)
    state, error = await friendship_svc.send_request(session, current_user, other)
    if state is None:
        code = (
            status.HTTP_400_BAD_REQUEST
            if error == friendship_svc.ERR_SELF
            else status.HTTP_403_FORBIDDEN
        )
        raise HTTPException(code, error)
    await session.commit()
    return FriendshipStateResponse(state=state)


@router.post("/{username}/accept", response_model=FriendshipStateResponse)
@limiter.limit("30/minute")
async def accept_request(
    request: Request,
    response: Response,
    username: str,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> FriendshipStateResponse:
    _require_enabled(response)
    other = await _other(session, username)
    state, error = await friendship_svc.accept_request(session, current_user, other)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, error)
    await session.commit()
    return FriendshipStateResponse(state=state)


@router.post("/{username}/decline", response_model=FriendshipStateResponse)
@limiter.limit("30/minute")
async def decline_request(
    request: Request,
    response: Response,
    username: str,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> FriendshipStateResponse:
    _require_enabled(response)
    other = await _other(session, username)
    state, error = await friendship_svc.decline_request(session, current_user, other)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, error)
    await session.commit()
    return FriendshipStateResponse(state=state)


@router.delete("/{username}", response_model=FriendshipStateResponse)
@limiter.limit("30/minute")
async def remove_friend(
    request: Request,
    response: Response,
    username: str,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> FriendshipStateResponse:
    _require_enabled(response)
    other = await _other(session, username)
    state = await friendship_svc.remove_friend(session, current_user, other)
    await session.commit()
    return FriendshipStateResponse(state=state)
