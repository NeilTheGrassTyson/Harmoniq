import uuid
from base64 import b64decode, b64encode
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, field_validator

from app.core.enums import MelodyStatus
from app.schemas.home import TrackSummary, UserSummary

# ── Request schemas ───────────────────────────────────────────────────────────


class MelodySendRequest(BaseModel):
    recipient_username: str
    track_mbid: str

    @field_validator("recipient_username", "track_mbid")
    @classmethod
    def validate_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("This field cannot be empty.")
        return v


class MelodyRespondRequest(BaseModel):
    action: Literal["accept", "open", "reject"]


# ── Response schemas ──────────────────────────────────────────────────────────
# Two distinct item schemas so a sender-only field can never leak into the
# recipient view or vice versa. The sent view's status is the sender-visible
# status ('received' collapsed to 'sent' — no read receipts).


class MelodyInboxItem(BaseModel):
    """Recipient's view: true status, sender identity."""

    id: uuid.UUID
    sender: UserSummary
    track: TrackSummary
    status: MelodyStatus
    created_at: datetime
    responded_at: datetime | None


class MelodySentItem(BaseModel):
    """Sender's view: recipient identity, sender-visible status."""

    id: uuid.UUID
    recipient: UserSummary
    track: TrackSummary
    status: MelodyStatus
    created_at: datetime
    responded_at: datetime | None


class MelodyInboxResponse(BaseModel):
    items: list[MelodyInboxItem]
    next_cursor: str | None


class MelodySentResponse(BaseModel):
    items: list[MelodySentItem]
    next_cursor: str | None


# ── Cursor encoding / decoding ────────────────────────────────────────────────


class MelodyCursor(BaseModel):
    """Same base64 `created_at|uuid` shape as FollowCursor (schemas/follow.py)."""

    created_at: datetime
    melody_id: uuid.UUID

    def encode(self) -> str:
        raw = f"{self.created_at.isoformat()}|{self.melody_id}"
        return b64encode(raw.encode()).decode()

    @classmethod
    def decode(cls, token: str) -> Self:
        raw = b64decode(token.encode()).decode()
        ts_str, mid_str = raw.rsplit("|", 1)
        return cls(
            created_at=datetime.fromisoformat(ts_str), melody_id=uuid.UUID(mid_str)
        )
