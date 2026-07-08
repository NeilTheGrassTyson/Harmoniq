import uuid
from base64 import b64decode, b64encode
from datetime import datetime
from typing import Self

from pydantic import BaseModel

from app.core.enums import NotificationType
from app.schemas.home import TrackSummary, UserSummary


class NotificationMelodyRef(BaseModel):
    """Just enough to render a compact Melody embed — never rating/activity data."""

    id: uuid.UUID
    track: TrackSummary


class NotificationItem(BaseModel):
    id: uuid.UUID
    type: NotificationType
    actor: UserSummary
    melody: NotificationMelodyRef | None
    read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationItem]
    next_cursor: str | None


class UnreadCountResponse(BaseModel):
    count: int


class NotificationCursor(BaseModel):
    """Same base64 `created_at|uuid` shape as FollowCursor (schemas/follow.py)."""

    created_at: datetime
    notification_id: uuid.UUID

    def encode(self) -> str:
        raw = f"{self.created_at.isoformat()}|{self.notification_id}"
        return b64encode(raw.encode()).decode()

    @classmethod
    def decode(cls, token: str) -> Self:
        raw = b64decode(token.encode()).decode()
        ts_str, nid_str = raw.rsplit("|", 1)
        return cls(
            created_at=datetime.fromisoformat(ts_str),
            notification_id=uuid.UUID(nid_str),
        )
