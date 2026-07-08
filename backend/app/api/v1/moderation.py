"""
Moderation API. Every endpoint requires CurrentModerator, which returns 404
(not 403) for non-moderators — the surface's existence is hidden. Moderator
status is granted only via manual SQL; the frontend reads it from /users/me.
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from app.api.v1.deps import CurrentModerator, DbSession
from app.core.enums import ReportStatus
from app.core.rate_limit import limiter
from app.schemas.moderation import ReportQueueResponse
from app.services import moderation as moderation_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/moderation", tags=["moderation"])

_ACTION_ERROR = "Something went wrong. Try again."

# Module-level singleton so the Query() call isn't evaluated per-signature (B008).
_STATUS_QUERY = Query(default=ReportStatus.OPEN, alias="status")


def _error_status(error: str) -> int:
    lowered = error.lower()
    if "not found" in lowered:
        return status.HTTP_404_NOT_FOUND
    if "already" in lowered:
        return status.HTTP_409_CONFLICT
    if "can't be suspended" in lowered:
        return status.HTTP_403_FORBIDDEN
    return status.HTTP_400_BAD_REQUEST


async def _commit_or_500(session: DbSession, context: str) -> None:
    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.exception("Moderation commit failed: %s", context)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_ACTION_ERROR
        ) from exc


@router.get("/reports", response_model=ReportQueueResponse)
async def list_reports(
    session: DbSession,
    moderator: CurrentModerator,
    report_status: ReportStatus | None = _STATUS_QUERY,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=moderation_svc.DEFAULT_PAGE_SIZE, ge=1, le=50),
) -> ReportQueueResponse:
    return await moderation_svc.list_reports(
        session,
        status_filter=report_status.value if report_status is not None else None,
        cursor=cursor,
        limit=limit,
    )


@router.post("/reports/{report_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def dismiss_report(
    request: Request,
    response: Response,
    report_id: uuid.UUID,
    session: DbSession,
    moderator: CurrentModerator,
) -> None:
    success, error = await moderation_svc.dismiss_report(
        session, moderator_id=moderator.id, report_id=report_id
    )
    if not success:
        raise HTTPException(status_code=_error_status(error), detail=error)
    await _commit_or_500(session, f"dismiss report_id={report_id}")


@router.post("/ratings/{rating_id}/hide", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def hide_rating(
    request: Request,
    response: Response,
    rating_id: uuid.UUID,
    session: DbSession,
    moderator: CurrentModerator,
) -> None:
    success, error = await moderation_svc.hide_rating(
        session, moderator_id=moderator.id, rating_id=rating_id
    )
    if not success:
        raise HTTPException(status_code=_error_status(error), detail=error)
    await _commit_or_500(session, f"hide rating_id={rating_id}")


@router.post("/users/{username}/suspend", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def suspend_user(
    request: Request,
    response: Response,
    username: str,
    session: DbSession,
    moderator: CurrentModerator,
) -> None:
    success, error = await moderation_svc.suspend_user(
        session, moderator_id=moderator.id, username=username
    )
    if not success:
        raise HTTPException(status_code=_error_status(error), detail=error)
    await _commit_or_500(session, f"suspend username={username}")
