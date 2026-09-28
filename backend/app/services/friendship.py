"""
Friendship service: explicit, symmetric friendship
(specs/phase-2-friend-requests.md).

This module owns the "is this viewer a friend?" decision behind every
friends-scoped visibility check. With FRIENDSHIPS_ENABLED off it falls back to
mutual follow, the Phase 1 definition, so rollback needs no data change.

A decline is silent: it notifies no one and the sender cannot observe it —
the rule ENGINEERING_BIBLE §3 sets for a rejected Melody. The sender never
sees their own outstanding request at all (Founder decision 2026-09-27), so
pending and declined look identical to them.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, delete, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.enums import (
    FriendshipState,
    FriendshipStatus,
    NotificationType,
)
from app.models.follow import Follow
from app.models.friendship import Friendship
from app.models.user import User
from app.schemas.friendship import FriendPerson, FriendsOverview
from app.services import follow as follow_svc
from app.services import notification as notification_svc

logger = logging.getLogger(__name__)

ERR_SELF = "You can't send a friend request to yourself."
# One message for every scope failure: the sender must never learn which
# setting refused them (HARMONIQ.md §6), mirroring Melody's accept scope.
ERR_SCOPE = "This member isn't accepting friend requests right now."
ERR_NO_REQUEST = "There's no pending request from this member."
ERR_RETRY = "Something went wrong. Try again."

_PENDING = FriendshipStatus.PENDING.value
_ACCEPTED = FriendshipStatus.ACCEPTED.value
_DECLINED = FriendshipStatus.DECLINED.value


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _pair(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """Canonical order. Python and Postgres both order UUIDs bytewise."""
    return (a, b) if a < b else (b, a)


async def _row(
    session: AsyncSession, a: uuid.UUID, b: uuid.UUID, *, lock: bool = False
) -> Friendship | None:
    low, high = _pair(a, b)
    stmt = select(Friendship).where(
        Friendship.user_low_id == low, Friendship.user_high_id == high
    )
    if lock:
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


# ── The friends decision ──────────────────────────────────────────────────────


async def are_friends(
    session: AsyncSession, user_a_id: uuid.UUID, user_b_id: uuid.UUID
) -> bool:
    """Symmetric. The only friends check any visibility decision should use."""
    if user_a_id == user_b_id:
        return False
    if not settings.friendships_enabled:
        return await follow_svc.is_mutual_follow(session, user_a_id, user_b_id)
    low, high = _pair(user_a_id, user_b_id)
    result = await session.execute(
        select(Friendship.status).where(
            Friendship.user_low_id == low,
            Friendship.user_high_id == high,
            Friendship.status == _ACCEPTED,
        )
    )
    return result.scalar_one_or_none() is not None


async def get_friend_ids(session: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    if not settings.friendships_enabled:
        return await follow_svc.get_mutual_follow_ids(session, user_id)
    rows = await session.execute(
        select(Friendship.user_low_id, Friendship.user_high_id).where(
            Friendship.status == _ACCEPTED,
            or_(Friendship.user_low_id == user_id, Friendship.user_high_id == user_id),
        )
    )
    return {high if low == user_id else low for low, high in rows.all()}


def _state_for(row: Friendship | None, viewer_id: uuid.UUID) -> FriendshipState:
    if row is None:
        return FriendshipState.NONE
    if row.status == _ACCEPTED:
        return FriendshipState.FRIENDS
    if row.requested_by == viewer_id:
        # The sender's own outstanding request, pending or declined: hidden.
        return FriendshipState.NONE
    if row.status == _PENDING:
        return FriendshipState.REQUEST_RECEIVED
    return FriendshipState.NONE  # a request this viewer declined


async def get_state(
    session: AsyncSession, viewer_id: uuid.UUID, other_id: uuid.UUID
) -> FriendshipState:
    return _state_for(await _row(session, viewer_id, other_id), viewer_id)


# ── Consent gate ──────────────────────────────────────────────────────────────


async def _may_request(session: AsyncSession, sender: User, recipient: User) -> bool:
    return await follow_svc.inbound_gesture_allowed(
        session, recipient.friend_request_scope, sender.id, recipient.id
    )


# ── Writes ────────────────────────────────────────────────────────────────────


async def _accept(
    session: AsyncSession, row: Friendship, accepter_id: uuid.UUID
) -> FriendshipState:
    requester_id = row.requested_by
    row.status = _ACCEPTED
    row.responded_at = _now()
    await session.flush()
    await notification_svc.create_friend_notification(
        session,
        user_id=requester_id,
        actor_id=accepter_id,
        notification_type=NotificationType.FRIEND_REQUEST_ACCEPTED,
    )
    logger.info(
        "Friendship accepted: requester_id=%s accepter_id=%s",
        requester_id,
        accepter_id,
    )
    return FriendshipState.FRIENDS


async def _notify_request(
    session: AsyncSession, sender_id: uuid.UUID, recipient_id: uuid.UUID
) -> None:
    await notification_svc.create_friend_notification(
        session,
        user_id=recipient_id,
        actor_id=sender_id,
        notification_type=NotificationType.FRIEND_REQUEST_RECEIVED,
    )
    logger.info(
        "Friend request sent: sender_id=%s recipient_id=%s", sender_id, recipient_id
    )


async def send_request(
    session: AsyncSession, sender: User, recipient: User
) -> tuple[FriendshipState | None, str]:
    """Returns (state, "") or (None, error). Idempotent for repeat sends."""
    if sender.id == recipient.id:
        return None, ERR_SELF
    row = await _row(session, sender.id, recipient.id, lock=True)
    if row is None:
        if not await _may_request(session, sender, recipient):
            return None, ERR_SCOPE
        low, high = _pair(sender.id, recipient.id)
        stmt = (
            pg_insert(Friendship)
            .values(
                user_low_id=low,
                user_high_id=high,
                status=_PENDING,
                requested_by=sender.id,
                created_at=_now(),
            )
            .on_conflict_do_nothing(index_elements=["user_low_id", "user_high_id"])
        )
        result = cast(CursorResult[Any], await session.execute(stmt))
        if result.rowcount == 1:
            await _notify_request(session, sender.id, recipient.id)
            return FriendshipState.REQUEST_SENT, ""
        # The other person's request landed first; treat it as below.
        row = await _row(session, sender.id, recipient.id, lock=True)
        if row is None:  # pragma: no cover — removed between the two statements
            return None, ERR_RETRY

    if row.status == _ACCEPTED:
        return FriendshipState.FRIENDS, ""
    if row.requested_by == sender.id:
        # Asked before, pending or declined: the same acknowledgement, no
        # change, and no second notification.
        return FriendshipState.REQUEST_SENT, ""
    if row.status == _PENDING:
        # They asked first; asking back accepts (spec requirement 2).
        return await _accept(session, row, accepter_id=sender.id), ""

    # The sender once declined this person and is now asking them instead.
    if not await _may_request(session, sender, recipient):
        return None, ERR_SCOPE
    row.status = _PENDING
    row.requested_by = sender.id
    row.created_at = _now()
    row.responded_at = None
    await session.flush()
    await _notify_request(session, sender.id, recipient.id)
    return FriendshipState.REQUEST_SENT, ""


async def accept_request(
    session: AsyncSession, user: User, requester: User
) -> tuple[FriendshipState | None, str]:
    row = await _row(session, user.id, requester.id, lock=True)
    if row is not None and row.status == _ACCEPTED:
        return FriendshipState.FRIENDS, ""
    if row is None or row.status != _PENDING or row.requested_by != requester.id:
        return None, ERR_NO_REQUEST
    return await _accept(session, row, accepter_id=user.id), ""


async def decline_request(
    session: AsyncSession, user: User, requester: User
) -> tuple[FriendshipState | None, str]:
    """Silent: no notification, and nothing the requester can observe."""
    row = await _row(session, user.id, requester.id, lock=True)
    if row is None or row.requested_by != requester.id or row.status == _ACCEPTED:
        return None, ERR_NO_REQUEST
    if row.status == _PENDING:
        row.status = _DECLINED
        row.responded_at = _now()
        await session.flush()
        logger.info(
            "Friend request declined: requester_id=%s decliner_id=%s",
            requester.id,
            user.id,
        )
    return FriendshipState.NONE, ""


async def remove_friend(
    session: AsyncSession, user: User, other: User
) -> FriendshipState:
    """Unilateral, immediate and silent. Every check reads live, so access
    ends with this statement (ENGINEERING_BIBLE §8.1)."""
    low, high = _pair(user.id, other.id)
    await session.execute(
        delete(Friendship).where(
            Friendship.user_low_id == low,
            Friendship.user_high_id == high,
            Friendship.status == _ACCEPTED,
        )
    )
    logger.info("Friendship removed: user_id=%s other_id=%s", user.id, other.id)
    return FriendshipState.NONE


# ── Owner-only overview ───────────────────────────────────────────────────────


async def overview(session: AsyncSession, user: User) -> FriendsOverview:
    rows = (
        (
            await session.execute(
                select(Friendship).where(
                    or_(
                        Friendship.user_low_id == user.id,
                        Friendship.user_high_id == user.id,
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    friend_ids: list[uuid.UUID] = []
    incoming_ids: list[uuid.UUID] = []
    for row in rows:
        other = row.user_high_id if row.user_low_id == user.id else row.user_low_id
        state = _state_for(row, user.id)
        if state is FriendshipState.FRIENDS:
            friend_ids.append(other)
        elif state is FriendshipState.REQUEST_RECEIVED:
            incoming_ids.append(other)

    ids = friend_ids + incoming_ids
    people: dict[uuid.UUID, User] = {}
    followed: set[uuid.UUID] = set()
    if ids:
        result = await session.execute(select(User).where(User.id.in_(ids)))
        people = {member.id: member for member in result.scalars()}
        follows = await session.execute(
            select(Follow.followed_id).where(
                Follow.follower_id == user.id, Follow.followed_id.in_(ids)
            )
        )
        followed = set(follows.scalars())

    def listed(members: list[uuid.UUID]) -> list[FriendPerson]:
        found = [
            FriendPerson(
                id=m.id,
                username=m.username,
                display_name=m.display_name,
                avatar_url=m.avatar_url,
                you_follow=m.id in followed,
            )
            for uid in members
            if (m := people.get(uid)) is not None
        ]
        return sorted(found, key=lambda p: (p.display_name.lower(), p.username))

    return FriendsOverview(friends=listed(friend_ids), incoming=listed(incoming_ids))
