import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from app.api.v1.deps import CurrentActiveUser, CurrentUser, DbSession
from app.core.rate_limit import limiter
from app.schemas.melody import (
    MelodyInboxItem,
    MelodyInboxResponse,
    MelodyRespondRequest,
    MelodySendRequest,
    MelodySentItem,
    MelodySentResponse,
)
from app.services import melody as melody_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/melodies", tags=["melodies"])

_SEND_ERROR = "Something went wrong. Your Melody wasn't sent. Try again."
_RESPOND_ERROR = "Something went wrong. Try again."


def _error_status(error: str) -> int:
    lowered = error.lower()
    if "not found" in lowered:
        return status.HTTP_404_NOT_FOUND
    if "already" in lowered:
        return status.HTTP_409_CONFLICT
    if "isn't receiving" in lowered:
        return status.HTTP_403_FORBIDDEN
    return status.HTTP_400_BAD_REQUEST


# ── Send a Melody ─────────────────────────────────────────────────────────────


@router.post("", response_model=MelodySentItem, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute;60/day")
async def send_melody(
    request: Request,
    response: Response,
    req: MelodySendRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> MelodySentItem:
    item, error = await melody_svc.send_melody(
        session,
        sender=current_user,
        recipient_username=req.recipient_username,
        track_mbid=req.track_mbid,
    )
    if item is None:
        raise HTTPException(status_code=_error_status(error), detail=error)
    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.exception("Melody send commit failed: sender_id=%s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_SEND_ERROR
        ) from exc
    return item


# ── Inbox / sent lists ────────────────────────────────────────────────────────


@router.get("/inbox", response_model=MelodyInboxResponse)
async def get_inbox(
    session: DbSession,
    current_user: CurrentUser,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=melody_svc.DEFAULT_PAGE_SIZE, ge=1, le=50),
) -> MelodyInboxResponse:
    result = await melody_svc.list_inbox(
        session, recipient_id=current_user.id, cursor=cursor, limit=limit
    )
    # list_inbox marks newly delivered rows as received — persist that.
    await session.commit()
    return result


@router.get("/sent", response_model=MelodySentResponse)
async def get_sent(
    session: DbSession,
    current_user: CurrentUser,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=melody_svc.DEFAULT_PAGE_SIZE, ge=1, le=50),
) -> MelodySentResponse:
    return await melody_svc.list_sent(
        session, sender_id=current_user.id, cursor=cursor, limit=limit
    )


# ── Respond (accept / open / reject) ──────────────────────────────────────────


@router.post("/{melody_id}/respond", response_model=MelodyInboxItem)
@limiter.limit("30/minute")
async def respond_to_melody(
    request: Request,
    response: Response,
    melody_id: uuid.UUID,
    req: MelodyRespondRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> MelodyInboxItem:
    item, error = await melody_svc.respond(
        session,
        melody_id=melody_id,
        recipient_id=current_user.id,
        action=req.action,
    )
    if item is None:
        raise HTTPException(status_code=_error_status(error), detail=error)
    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.exception(
            "Melody respond commit failed: melody_id=%s user_id=%s",
            melody_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_RESPOND_ERROR
        ) from exc
    return item
