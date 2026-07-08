import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.v1.deps import CurrentUser, DbSession
from app.schemas.notification import (
    NotificationListResponse,
    UnreadCountResponse,
)
from app.services import notification as notification_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    session: DbSession,
    current_user: CurrentUser,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=notification_svc.DEFAULT_PAGE_SIZE, ge=1, le=50),
) -> NotificationListResponse:
    return await notification_svc.list_notifications(
        session, user_id=current_user.id, cursor=cursor, limit=limit
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    session: DbSession,
    current_user: CurrentUser,
) -> UnreadCountResponse:
    count = await notification_svc.unread_count(session, current_user.id)
    return UnreadCountResponse(count=count)


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_read(
    notification_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> None:
    marked = await notification_svc.mark_read(
        session, user_id=current_user.id, notification_id=notification_id
    )
    if not marked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found."
        )
    await session.commit()


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_notifications_read(
    session: DbSession,
    current_user: CurrentUser,
) -> None:
    await notification_svc.mark_all_read(session, current_user.id)
    await session.commit()
