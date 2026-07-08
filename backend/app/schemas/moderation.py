import uuid
from base64 import b64decode, b64encode
from datetime import datetime
from typing import Self

from pydantic import BaseModel

from app.core.enums import ReportStatus
from app.schemas.home import UserSummary


class ReportedRating(BaseModel):
    """Full rating context for the queue — moderators see hidden state too."""

    id: uuid.UUID
    entity_type: str
    score: int
    review_text: str
    hidden: bool
    author: UserSummary
    author_suspended: bool


class ReportQueueItem(BaseModel):
    id: uuid.UUID
    status: ReportStatus
    created_at: datetime
    reporter: UserSummary
    rating: ReportedRating
    open_report_count: int


class ReportQueueResponse(BaseModel):
    items: list[ReportQueueItem]
    next_cursor: str | None


class ReportCursor(BaseModel):
    """Same base64 `created_at|uuid` shape as FollowCursor (schemas/follow.py)."""

    created_at: datetime
    report_id: uuid.UUID

    def encode(self) -> str:
        raw = f"{self.created_at.isoformat()}|{self.report_id}"
        return b64encode(raw.encode()).decode()

    @classmethod
    def decode(cls, token: str) -> Self:
        raw = b64decode(token.encode()).decode()
        ts_str, rid_str = raw.rsplit("|", 1)
        return cls(
            created_at=datetime.fromisoformat(ts_str), report_id=uuid.UUID(rid_str)
        )
