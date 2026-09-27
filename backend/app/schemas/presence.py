from typing import Literal

from pydantic import BaseModel

# `None` means "shares no online status" — deliberately not a value that
# names the choice (docs/specs/beta-ui-phase-5-presence.md).
PresenceState = Literal["listening", "online", "offline"] | None


class HeartbeatResponse(BaseModel):
    """Whether this beat was kept. False means Online status is Private."""

    recorded: bool


class PresenceTrack(BaseModel):
    title: str
    artist_name: str


class FriendPresence(BaseModel):
    """A mutual follow, as the viewer may see them. No times, ever."""

    username: str
    display_name: str
    avatar_url: str | None
    state: PresenceState
    track: PresenceTrack | None = None


class FriendsPresenceResponse(BaseModel):
    """Ordered for display: listening, online, offline, then no status."""

    friends: list[FriendPresence]
