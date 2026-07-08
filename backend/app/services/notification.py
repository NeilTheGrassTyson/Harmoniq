"""
Notification service: creation (idempotent), listing, unread count, mark read.

Creation is synchronous, in the same transaction as its trigger (melody send,
follow) — atomic in a monolith, no queue infrastructure. If Phase 2 grows the
event set, this call-site coupling is the seam to replace with an outbox.

There is deliberately no creation path for melody rejection: ENGINEERING_BIBLE
§3 — rejection must never produce a notification visible to anyone.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, and_, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import NotificationType
from app.models.catalog import Album, Artist, Track
from app.models.melody import Melody
from app.models.notification import Notification
from app.models.user import User
from app.schemas.home import TrackSummary, UserSummary
from app.schemas.notification import (
    NotificationCursor,
    NotificationItem,
    NotificationListResponse,
    NotificationMelodyRef,
)

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 20


def _now() -> datetime:
    return datetime.now(tz=UTC)


# ── Creation (idempotent via partial unique indexes) ──────────────────────────


async def create_melody_notification(
    session: AsyncSession,
    recipient_id: uuid.UUID,
    actor_id: uuid.UUID,
    melody_id: uuid.UUID,
) -> None:
    stmt = (
        pg_insert(Notification)
        .values(
            id=uuid.uuid4(),
            user_id=recipient_id,
            type=NotificationType.MELODY_RECEIVED.value,
            actor_id=actor_id,
            melody_id=melody_id,
            created_at=_now(),
        )
        .on_conflict_do_nothing(
            index_elements=["melody_id"],
            index_where=text("melody_id IS NOT NULL"),
        )
    )
    await session.execute(stmt)


async def create_follower_notification(
    session: AsyncSession,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    stmt = (
        pg_insert(Notification)
        .values(
            id=uuid.uuid4(),
            user_id=user_id,
            type=NotificationType.NEW_FOLLOWER.value,
            actor_id=actor_id,
            created_at=_now(),
        )
        .on_conflict_do_nothing(
            index_elements=["user_id", "actor_id"],
            index_where=text("type = 'new_follower'"),
        )
    )
    await session.execute(stmt)


# ── Reads ─────────────────────────────────────────────────────────────────────


async def list_notifications(
    session: AsyncSession,
    user_id: uuid.UUID,
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> NotificationListResponse:
    base = (
        select(
            Notification.id,
            Notification.type,
            Notification.read_at,
            Notification.created_at,
            User.id.label("actor_uid"),
            User.username,
            User.display_name,
            User.avatar_url,
            Melody.id.label("melody_id"),
            Track.id.label("track_id"),
            Track.mbid.label("track_mbid"),
            Track.title.label("track_title"),
            Artist.name.label("artist_name"),
            Album.cover_art_url,
        )
        .join(User, User.id == Notification.actor_id)
        .outerjoin(Melody, Melody.id == Notification.melody_id)
        .outerjoin(Track, Track.id == Melody.track_id)
        .outerjoin(Artist, Artist.id == Track.artist_id)
        .outerjoin(Album, Album.id == Track.album_id)
        .where(Notification.user_id == user_id)
    )

    if cursor is not None:
        c = NotificationCursor.decode(cursor)
        base = base.where(
            or_(
                Notification.created_at < c.created_at,
                and_(
                    Notification.created_at == c.created_at,
                    Notification.id > c.notification_id,
                ),
            )
        )

    base = base.order_by(Notification.created_at.desc(), Notification.id.asc()).limit(
        limit + 1
    )
    rows = (await session.execute(base)).all()

    has_more = len(rows) > limit
    page = rows[:limit]

    items = []
    for row in page:
        melody_ref = None
        if row.melody_id is not None and row.track_id is not None:
            melody_ref = NotificationMelodyRef(
                id=row.melody_id,
                track=TrackSummary(
                    id=row.track_id,
                    mbid=row.track_mbid,
                    title=row.track_title,
                    artist_name=row.artist_name,
                    cover_art_url=row.cover_art_url,
                ),
            )
        items.append(
            NotificationItem(
                id=row.id,
                type=row.type,
                actor=UserSummary(
                    id=row.actor_uid,
                    username=row.username,
                    display_name=row.display_name,
                    avatar_url=row.avatar_url,
                ),
                melody=melody_ref,
                read=row.read_at is not None,
                created_at=row.created_at,
            )
        )

    next_cursor: str | None = None
    if has_more and page:
        last = page[-1]
        next_cursor = NotificationCursor(
            created_at=last.created_at, notification_id=last.id
        ).encode()

    return NotificationListResponse(items=items, next_cursor=next_cursor)


async def unread_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
    return result.scalar_one()


# ── Mark read ─────────────────────────────────────────────────────────────────


async def mark_read(
    session: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID
) -> bool:
    """Returns False when the notification doesn't exist or isn't the caller's."""
    result = cast(
        CursorResult[Any],
        await session.execute(
            update(Notification)
            .where(Notification.id == notification_id, Notification.user_id == user_id)
            .values(read_at=_now())
        ),
    )
    return result.rowcount > 0


async def mark_all_read(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=_now())
    )
