from fastapi import APIRouter, Request, Response

from app.api.v1.deps import CurrentActiveUser, CurrentUser, DbSession
from app.core.rate_limit import limiter, per_session
from app.schemas.presence import FriendsPresenceResponse, HeartbeatResponse
from app.services import presence as presence_svc

router = APIRouter(prefix="/presence", tags=["presence"])

# `response` is unused here but required: the limiter injects X-RateLimit-*
# headers into it, and 500s on any decorated route that doesn't take one.


# One beat a minute per visible tab is expected; the headroom covers tabs
# being shown and hidden. Keyed per session, not per IP — see per_session.
# A suspended account broadcasts nothing.
@router.post("/heartbeat", response_model=HeartbeatResponse)
@limiter.limit("12/minute", key_func=per_session)
async def heartbeat(
    request: Request, response: Response, current_user: CurrentActiveUser
) -> HeartbeatResponse:
    return HeartbeatResponse(recorded=presence_svc.heartbeat(current_user))


# The rail re-reads every 30s while visible.
@router.get("/friends", response_model=FriendsPresenceResponse)
@limiter.limit("12/minute", key_func=per_session)
async def friends(
    request: Request,
    response: Response,
    session: DbSession,
    current_user: CurrentUser,
) -> FriendsPresenceResponse:
    return await presence_svc.friends_presence(session, current_user)
