"""
Online presence for the friends rail (docs/specs/beta-ui-phase-5-presence.md).

Presence is ephemeral by design: a map of user id → the monotonic time of
their last heartbeat, in this process's memory. It is never written to the
database, never logged per beat, and gone on restart. Only users whose Online
status admits anyone are recorded at all.

Correct only while the backend runs a single process — true today (Procfile,
railway.json), and the same constraint the Spotify listening cache carries.
ADR 0016 records it; scaling out means moving this to a shared store first.
"""

import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.visibility import scope_allows
from app.models.user import User
from app.schemas.presence import (
    FriendPresence,
    FriendsPresenceResponse,
    PresenceState,
    PresenceTrack,
)
from app.services import follow as follow_svc
from app.services import spotify as spotify_svc

# Two missed beats (the client sends one every 60s while visible) and you are
# offline. Only the resulting group is ever exposed, never a time.
ONLINE_WINDOW_SECONDS = 120.0
_PRUNE_EVERY = 256

_last_seen: dict[uuid.UUID, float] = {}
_beats_since_prune = 0


def _clock() -> float:
    return time.monotonic()


def _prune() -> None:
    cutoff = _clock() - ONLINE_WINDOW_SECONDS
    for user_id in [u for u, t in _last_seen.items() if t < cutoff]:
        _last_seen.pop(user_id, None)


def forget(user_id: uuid.UUID) -> None:
    """Drop any record of this user — used the moment they go Private."""
    _last_seen.pop(user_id, None)


def is_online(user_id: uuid.UUID) -> bool:
    seen = _last_seen.get(user_id)
    if seen is None:
        return False
    if _clock() - seen > ONLINE_WINDOW_SECONDS:
        _last_seen.pop(user_id, None)
        return False
    return True


def _shares_presence_with_friends(user: User) -> bool:
    return scope_allows(user.visibility_presence, is_owner=False, is_friend=True)


def heartbeat(user: User) -> bool:
    """Record that `user` has Harmoniq open. Returns whether it was kept."""
    global _beats_since_prune
    if not _shares_presence_with_friends(user):
        forget(user.id)
        return False
    _last_seen[user.id] = _clock()
    _beats_since_prune += 1
    if _beats_since_prune >= _PRUNE_EVERY:
        _beats_since_prune = 0
        _prune()
    return True


_GROUP_ORDER: dict[PresenceState, int] = {
    "listening": 0,
    "online": 1,
    "offline": 2,
    None: 3,
}


async def friends_presence(
    session: AsyncSession, viewer: User
) -> FriendsPresenceResponse:
    """
    The viewer's mutual follows, each resolved against *their* settings at
    request time — enforcement here, never in the client (ENGINEERING_BIBLE
    §8.1). A friend the viewer may not see listening or online is returned as
    `offline` (shares status, isn't online) or `None` (shares none).
    """
    friend_ids = await follow_svc.get_mutual_follow_ids(session, viewer.id)
    if not friend_ids:
        return FriendsPresenceResponse(friends=[])

    friends = (
        (await session.execute(select(User).where(User.id.in_(friend_ids))))
        .scalars()
        .all()
    )

    rows: list[FriendPresence] = []
    for friend in friends:
        state: PresenceState = None
        track: PresenceTrack | None = None

        # Listening now: the profile's existing consent, checked inside
        # get_listening on every call; only the raw Spotify payload is cached.
        listening = await spotify_svc.get_listening(session, friend, viewer)
        if listening is not None and listening.now_playing is not None:
            state = "listening"
            track = PresenceTrack(
                title=listening.now_playing.track_name,
                artist_name=listening.now_playing.artist_name,
            )
        elif _shares_presence_with_friends(friend):
            state = "online" if is_online(friend.id) else "offline"

        rows.append(
            FriendPresence(
                username=friend.username,
                display_name=friend.display_name,
                avatar_url=friend.avatar_url,
                state=state,
                track=track,
            )
        )

    rows.sort(
        key=lambda r: (_GROUP_ORDER[r.state], r.display_name.casefold(), r.username)
    )
    return FriendsPresenceResponse(friends=rows)
