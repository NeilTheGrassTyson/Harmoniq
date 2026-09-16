from fastapi import APIRouter, HTTPException, Request, Response

from app.api.v1.deps import CurrentActiveUser, DbSession, OptionalClerkId
from app.config import settings
from app.core.rate_limit import limiter
from app.schemas.harmony import HarmonyResponse, HarmonyVisibilityRequest
from app.services import harmony as harmony_svc

router = APIRouter(prefix="/harmony", tags=["harmony"])


@router.patch("/me", response_model=HarmonyVisibilityRequest)
@limiter.limit("10/minute")
async def update_visibility(
    request: Request,
    response: Response,
    req: HarmonyVisibilityRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> HarmonyVisibilityRequest:
    if not settings.harmony_enabled:
        raise HTTPException(404, "Harmony is unavailable.")
    response.headers["Cache-Control"] = "private, no-store"
    await harmony_svc.set_visibility(session, current_user, req.visibility)
    await session.commit()
    return req


@router.get("/{username}", response_model=HarmonyResponse)
async def get_harmony(
    username: str,
    response: Response,
    session: DbSession,
    viewer_clerk_id: OptionalClerkId,
) -> HarmonyResponse:
    if not settings.harmony_enabled:
        raise HTTPException(404, "Harmony is unavailable.")
    response.headers["Cache-Control"] = "private, no-store"
    result = await harmony_svc.get_harmony(session, username, viewer_clerk_id)
    if result is None:
        raise HTTPException(404, "User not found.")
    return result
