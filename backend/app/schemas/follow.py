import uuid
from base64 import b64decode, b64encode
from datetime import datetime
from typing import Self

from pydantic import BaseModel

# ── Relationship state ────────────────────────────────────────────────────────


class FollowState(BaseModel):
    """Describes the follow relationship between a viewer and a profile owner."""

    is_following: bool
    follows_you: bool
    is_friend: bool


# ── Compact user reference for list entries ───────────────────────────────────


class FollowSummary(BaseModel):
    """Compact user reference used in follower / following list entries."""

    user_id: uuid.UUID
    username: str
    display_name: str
    avatar_url: str | None


# ── Paginated list responses ──────────────────────────────────────────────────


class FollowListResponse(BaseModel):
    items: list[FollowSummary]
    next_cursor: str | None


# ── Cursor encoding / decoding ────────────────────────────────────────────────


class FollowCursor(BaseModel):
    created_at: datetime
    user_id: uuid.UUID

    def encode(self) -> str:
        raw = f"{self.created_at.isoformat()}|{self.user_id}"
        return b64encode(raw.encode()).decode()

    @classmethod
    def decode(cls, token: str) -> Self:
        raw = b64decode(token.encode()).decode()
        ts_str, uid_str = raw.rsplit("|", 1)
        return cls(
            created_at=datetime.fromisoformat(ts_str), user_id=uuid.UUID(uid_str)
        )
