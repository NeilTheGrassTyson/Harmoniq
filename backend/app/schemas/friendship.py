import uuid

from pydantic import BaseModel

from app.core.enums import FriendshipState


class FriendshipStateResponse(BaseModel):
    state: FriendshipState


class FriendPerson(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    avatar_url: str | None
    # Drives the one-tap follow-back offered beside a friend (Founder decision
    # 2026-09-27): friendship never creates a follow by itself.
    you_follow: bool


class FriendsOverview(BaseModel):
    """Owner-only. Deliberately no outgoing list: a sender never sees their
    own outstanding requests, which keeps a decline invisible."""

    friends: list[FriendPerson]
    incoming: list[FriendPerson]
