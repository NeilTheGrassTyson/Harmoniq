"""
Melody service: send, inbox/sent listing, and the respond state machine.

Lifecycle per ENGINEERING_BIBLE §3: sent → received (system, on inbox fetch),
then accepted / opened / rejected by the recipient. Rejected is recoverable
(→ accepted/opened); accepted may upgrade to opened; opened is terminal.
Rejection never produces a notification and is visible only to the sender.

The pure helpers (_can_transition, _sender_visible_status, _scope_satisfied)
hold the business rules and are unit-testable without a database; the async
functions handle I/O and delegate to them (home.py pattern).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import MelodyAcceptScope, MelodyStatus
from app.models.catalog import Album, Artist, Track
from app.models.follow import Follow
from app.models.melody import Melody
from app.models.user import User
from app.schemas.home import TrackSummary, UserSummary
from app.schemas.melody import (
    MelodyCursor,
    MelodyInboxItem,
    MelodyInboxResponse,
    MelodySentItem,
    MelodySentResponse,
)
from app.services import notification as notification_svc

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 20

_ERR_RECIPIENT_NOT_FOUND = "Recipient not found."
_ERR_TRACK_NOT_FOUND = "Track not found."
_ERR_SELF_SEND = "You can't send a Melody to yourself."
# Deliberately identical wording for 'follows' and 'mutuals' failures —
# the sender must never learn the recipient's setting (consent, HARMONIQ §6).
_ERR_SCOPE = "This member isn't receiving Melodies right now."
_ERR_DUPLICATE = "You've already sent this track to them."
_ERR_NOT_FOUND = "Melody not found."
_ERR_ALREADY_RESPONDED = "You've already responded to this Melody."

_RESPOND_ACTIONS: dict[str, MelodyStatus] = {
    "accept": MelodyStatus.ACCEPTED,
    "open": MelodyStatus.OPENED,
    "reject": MelodyStatus.REJECTED,
}

# Recipient-triggered transitions only. sent → received is a system
# transition handled in list_inbox, never through _can_transition.
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    MelodyStatus.SENT.value: frozenset(
        {
            MelodyStatus.ACCEPTED.value,
            MelodyStatus.OPENED.value,
            MelodyStatus.REJECTED.value,
        }
    ),
    MelodyStatus.RECEIVED.value: frozenset(
        {
            MelodyStatus.ACCEPTED.value,
            MelodyStatus.OPENED.value,
            MelodyStatus.REJECTED.value,
        }
    ),
    # Rejected is recoverable: the recipient may still take or listen later.
    MelodyStatus.REJECTED.value: frozenset(
        {MelodyStatus.ACCEPTED.value, MelodyStatus.OPENED.value}
    ),
    # Engagement upgrade: took it, later listened.
    MelodyStatus.ACCEPTED.value: frozenset({MelodyStatus.OPENED.value}),
    MelodyStatus.OPENED.value: frozenset(),
}


def _now() -> datetime:
    return datetime.now(tz=UTC)


# ── Pure helpers ──────────────────────────────────────────────────────────────


def _can_transition(from_status: str, to_status: str) -> bool:
    return to_status in _ALLOWED_TRANSITIONS.get(from_status, frozenset())


def _sender_visible_status(status: str) -> MelodyStatus:
    """Collapse 'received' to 'sent' — the sender gets outcomes, not read receipts."""
    if status == MelodyStatus.RECEIVED.value:
        return MelodyStatus.SENT
    return MelodyStatus(status)


def _scope_satisfied(
    scope: str,
    recipient_follows_sender: bool,
    is_mutual: bool,
) -> bool:
    """May a sender reach a recipient with this melody_accept_scope?"""
    if scope == MelodyAcceptScope.EVERYONE.value:
        return True
    if scope == MelodyAcceptScope.FOLLOWS.value:
        return recipient_follows_sender
    if scope == MelodyAcceptScope.MUTUALS.value:
        return is_mutual
    return False  # unknown scope: fail closed


# ── Internal query helpers ────────────────────────────────────────────────────

_TRACK_COLS = (
    Track.id.label("track_id"),
    Track.mbid.label("track_mbid"),
    Track.title.label("track_title"),
    Artist.name.label("artist_name"),
    Album.cover_art_url,
)


def _track_summary_from_row(row: object) -> TrackSummary:
    return TrackSummary(
        id=row.track_id,  # type: ignore[attr-defined]
        mbid=row.track_mbid,  # type: ignore[attr-defined]
        title=row.track_title,  # type: ignore[attr-defined]
        artist_name=row.artist_name,  # type: ignore[attr-defined]
        cover_art_url=row.cover_art_url,  # type: ignore[attr-defined]
    )


async def _get_track_summary(
    session: AsyncSession, track_id: uuid.UUID
) -> TrackSummary | None:
    result = await session.execute(
        select(*_TRACK_COLS)
        .outerjoin(Artist, Artist.id == Track.artist_id)
        .outerjoin(Album, Album.id == Track.album_id)
        .where(Track.id == track_id)
    )
    row = result.one_or_none()
    return _track_summary_from_row(row) if row is not None else None


def _user_summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
    )


async def _recipient_follows_sender(
    session: AsyncSession, recipient_id: uuid.UUID, sender_id: uuid.UUID
) -> bool:
    result = await session.execute(
        select(func.count())
        .select_from(Follow)
        .where(Follow.follower_id == recipient_id, Follow.followed_id == sender_id)
    )
    return result.scalar_one() > 0


# ── Public async API ──────────────────────────────────────────────────────────


async def send_melody(
    session: AsyncSession,
    sender: User,
    recipient_username: str,
    track_mbid: str,
) -> tuple[MelodySentItem | None, str]:
    """Returns (item, "") on success or (None, error_message) on failure."""
    recipient_result = await session.execute(
        select(User).where(User.username == recipient_username.lower())
    )
    recipient = recipient_result.scalar_one_or_none()
    if recipient is None:
        return None, _ERR_RECIPIENT_NOT_FOUND
    if recipient.id == sender.id:
        return None, _ERR_SELF_SEND

    track_result = await session.execute(
        select(Track.id).where(Track.mbid == track_mbid)
    )
    track_id = track_result.scalar_one_or_none()
    if track_id is None:
        return None, _ERR_TRACK_NOT_FOUND

    if recipient.melody_accept_scope != MelodyAcceptScope.EVERYONE.value:
        recipient_follows = await _recipient_follows_sender(
            session, recipient.id, sender.id
        )
        is_mutual = False
        if recipient_follows:
            is_mutual = await _recipient_follows_sender(
                session, sender.id, recipient.id
            )
        if not _scope_satisfied(
            recipient.melody_accept_scope, recipient_follows, is_mutual
        ):
            return None, _ERR_SCOPE

    # Friendly pre-check; the partial unique index is the race-proof backstop.
    dup_result = await session.execute(
        select(func.count())
        .select_from(Melody)
        .where(
            Melody.sender_id == sender.id,
            Melody.recipient_id == recipient.id,
            Melody.track_id == track_id,
            Melody.status.in_([MelodyStatus.SENT.value, MelodyStatus.RECEIVED.value]),
        )
    )
    if dup_result.scalar_one() > 0:
        return None, _ERR_DUPLICATE

    melody = Melody(
        sender_id=sender.id,
        recipient_id=recipient.id,
        track_id=track_id,
        status=MelodyStatus.SENT.value,
        created_at=_now(),
    )
    session.add(melody)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return None, _ERR_DUPLICATE

    # Same transaction as the send — no Melody without its notification.
    await notification_svc.create_melody_notification(
        session, recipient_id=recipient.id, actor_id=sender.id, melody_id=melody.id
    )

    logger.info(
        "Melody sent: id=%s sender_id=%s recipient_id=%s track_id=%s",
        melody.id,
        sender.id,
        recipient.id,
        track_id,
    )

    track = await _get_track_summary(session, track_id)
    if track is None:  # pragma: no cover — track existed moments ago
        return None, _ERR_TRACK_NOT_FOUND
    return (
        MelodySentItem(
            id=melody.id,
            recipient=_user_summary(recipient),
            track=track,
            status=_sender_visible_status(melody.status),
            created_at=melody.created_at,
            responded_at=melody.responded_at,
        ),
        "",
    )


async def list_inbox(
    session: AsyncSession,
    recipient_id: uuid.UUID,
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> MelodyInboxResponse:
    """
    Recipient's inbox, newest first. Marks undelivered rows received first —
    delivery in a web app is the fetch itself; no separate ack endpoint.
    """
    await session.execute(
        update(Melody)
        .where(
            Melody.recipient_id == recipient_id,
            Melody.status == MelodyStatus.SENT.value,
        )
        .values(status=MelodyStatus.RECEIVED.value, received_at=_now())
    )

    base = (
        select(
            Melody.id,
            Melody.status,
            Melody.created_at,
            Melody.responded_at,
            User.id.label("user_id"),
            User.username,
            User.display_name,
            User.avatar_url,
            *_TRACK_COLS,
        )
        .join(User, User.id == Melody.sender_id)
        .join(Track, Track.id == Melody.track_id)
        .outerjoin(Artist, Artist.id == Track.artist_id)
        .outerjoin(Album, Album.id == Track.album_id)
        .where(Melody.recipient_id == recipient_id)
    )

    if cursor is not None:
        c = MelodyCursor.decode(cursor)
        base = base.where(
            or_(
                Melody.created_at < c.created_at,
                and_(Melody.created_at == c.created_at, Melody.id > c.melody_id),
            )
        )

    base = base.order_by(Melody.created_at.desc(), Melody.id.asc()).limit(limit + 1)
    rows = (await session.execute(base)).all()

    has_more = len(rows) > limit
    page = rows[:limit]

    items = [
        MelodyInboxItem(
            id=row.id,
            sender=UserSummary(
                id=row.user_id,
                username=row.username,
                display_name=row.display_name,
                avatar_url=row.avatar_url,
            ),
            track=_track_summary_from_row(row),
            status=MelodyStatus(row.status),
            created_at=row.created_at,
            responded_at=row.responded_at,
        )
        for row in page
    ]

    next_cursor: str | None = None
    if has_more and page:
        last = page[-1]
        next_cursor = MelodyCursor(
            created_at=last.created_at, melody_id=last.id
        ).encode()

    return MelodyInboxResponse(items=items, next_cursor=next_cursor)


async def list_sent(
    session: AsyncSession,
    sender_id: uuid.UUID,
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> MelodySentResponse:
    """Sender's sent list, newest first, with sender-visible statuses."""
    base = (
        select(
            Melody.id,
            Melody.status,
            Melody.created_at,
            Melody.responded_at,
            User.id.label("user_id"),
            User.username,
            User.display_name,
            User.avatar_url,
            *_TRACK_COLS,
        )
        .join(User, User.id == Melody.recipient_id)
        .join(Track, Track.id == Melody.track_id)
        .outerjoin(Artist, Artist.id == Track.artist_id)
        .outerjoin(Album, Album.id == Track.album_id)
        .where(Melody.sender_id == sender_id)
    )

    if cursor is not None:
        c = MelodyCursor.decode(cursor)
        base = base.where(
            or_(
                Melody.created_at < c.created_at,
                and_(Melody.created_at == c.created_at, Melody.id > c.melody_id),
            )
        )

    base = base.order_by(Melody.created_at.desc(), Melody.id.asc()).limit(limit + 1)
    rows = (await session.execute(base)).all()

    has_more = len(rows) > limit
    page = rows[:limit]

    items = [
        MelodySentItem(
            id=row.id,
            recipient=UserSummary(
                id=row.user_id,
                username=row.username,
                display_name=row.display_name,
                avatar_url=row.avatar_url,
            ),
            track=_track_summary_from_row(row),
            status=_sender_visible_status(row.status),
            created_at=row.created_at,
            responded_at=row.responded_at,
        )
        for row in page
    ]

    next_cursor: str | None = None
    if has_more and page:
        last = page[-1]
        next_cursor = MelodyCursor(
            created_at=last.created_at, melody_id=last.id
        ).encode()

    return MelodySentResponse(items=items, next_cursor=next_cursor)


async def respond(
    session: AsyncSession,
    melody_id: uuid.UUID,
    recipient_id: uuid.UUID,
    action: str,
) -> tuple[MelodyInboxItem | None, str]:
    """
    Apply a recipient response. Returns (updated item, "") or (None, error).
    'Not found' covers both a missing Melody and a caller who isn't the
    recipient — existence-hiding. Never creates a notification (reject
    included: ENGINEERING_BIBLE §3, zero exceptions).
    """
    result = await session.execute(
        select(Melody).where(
            Melody.id == melody_id, Melody.recipient_id == recipient_id
        )
    )
    melody = result.scalar_one_or_none()
    if melody is None:
        return None, _ERR_NOT_FOUND

    target = _RESPOND_ACTIONS[action]
    if not _can_transition(melody.status, target.value):
        return None, _ERR_ALREADY_RESPONDED

    now = _now()
    melody.status = target.value
    melody.responded_at = now
    if melody.received_at is None:
        melody.received_at = now
    await session.flush()

    logger.info(
        "Melody respond: id=%s recipient_id=%s action=%s",
        melody.id,
        recipient_id,
        action,
    )

    sender_result = await session.execute(
        select(User).where(User.id == melody.sender_id)
    )
    sender = sender_result.scalar_one()
    track = await _get_track_summary(session, melody.track_id)
    if track is None:  # pragma: no cover
        return None, _ERR_NOT_FOUND

    return (
        MelodyInboxItem(
            id=melody.id,
            sender=_user_summary(sender),
            track=track,
            status=MelodyStatus(melody.status),
            created_at=melody.created_at,
            responded_at=melody.responded_at,
        ),
        "",
    )
