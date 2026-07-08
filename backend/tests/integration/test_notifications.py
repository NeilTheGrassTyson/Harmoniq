"""
Integration tests: notification creation on melody send and follow,
rejection-never-notifies, idempotency, listing, unread count, mark read.

The constitutional rule under test (ENGINEERING_BIBLE §3): a rejected Melody
must never produce a notification — for anyone, under any circumstances.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import NotificationType
from app.models.catalog import Track
from app.models.notification import Notification
from app.models.user import User
from app.services import follow as follow_svc
from app.services import melody as melody_svc
from app.services import notification as notification_svc
from app.services import user as user_svc

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_user(session: AsyncSession, *, clerk_id: str, username: str) -> User:
    user = await user_svc.create_user(session, clerk_id, username, "Test User")
    await session.flush()
    return user


async def _make_track(session: AsyncSession, *, mbid: str) -> Track:
    track = Track(
        id=uuid.uuid4(),
        mbid=mbid,
        title="Test Track",
        last_fetched_at=datetime.now(UTC),
    )
    session.add(track)
    await session.flush()
    return track


async def _notifications_for(
    session: AsyncSession, user_id: uuid.UUID
) -> list[Notification]:
    result = await session.execute(
        select(Notification).where(Notification.user_id == user_id)
    )
    return list(result.scalars().all())


# ── Creation ──────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestNotificationCreation:
    async def test_melody_send_creates_exactly_one(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="ntf_c_01a", username="ntf_c_01a")
        b = await _make_user(db_session, clerk_id="ntf_c_01b", username="ntf_c_01b")
        track = await _make_track(db_session, mbid="mbid-ntf-c-01")

        item, error = await melody_svc.send_melody(
            db_session, sender=a, recipient_username=b.username, track_mbid=track.mbid
        )
        assert error == "" and item is not None

        rows = await _notifications_for(db_session, b.id)
        assert len(rows) == 1
        assert rows[0].type == NotificationType.MELODY_RECEIVED.value
        assert rows[0].actor_id == a.id
        assert rows[0].melody_id == item.id
        # The sender got nothing.
        assert await _notifications_for(db_session, a.id) == []

    async def test_rejection_creates_zero_notifications(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="ntf_c_02a", username="ntf_c_02a")
        b = await _make_user(db_session, clerk_id="ntf_c_02b", username="ntf_c_02b")
        track = await _make_track(db_session, mbid="mbid-ntf-c-02")

        item, _ = await melody_svc.send_melody(
            db_session, sender=a, recipient_username=b.username, track_mbid=track.mbid
        )
        assert item is not None
        before_a = len(await _notifications_for(db_session, a.id))
        before_b = len(await _notifications_for(db_session, b.id))

        _, error = await melody_svc.respond(
            db_session, melody_id=item.id, recipient_id=b.id, action="reject"
        )
        assert error == ""

        # Zero new notifications for anyone — constitutional, no exceptions.
        assert len(await _notifications_for(db_session, a.id)) == before_a
        assert len(await _notifications_for(db_session, b.id)) == before_b

    async def test_follow_creates_one_and_refollow_does_not_duplicate(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="ntf_c_03a", username="ntf_c_03a")
        b = await _make_user(db_session, clerk_id="ntf_c_03b", username="ntf_c_03b")

        created = await follow_svc.follow(db_session, a.id, b.id)
        assert created is True
        await notification_svc.create_follower_notification(
            db_session, user_id=b.id, actor_id=a.id
        )

        # Unfollow, re-follow: edge is new again, but the partial unique
        # index swallows the duplicate notification.
        await follow_svc.unfollow(db_session, a.id, b.id)
        created = await follow_svc.follow(db_session, a.id, b.id)
        assert created is True
        await notification_svc.create_follower_notification(
            db_session, user_id=b.id, actor_id=a.id
        )

        rows = await _notifications_for(db_session, b.id)
        assert len(rows) == 1
        assert rows[0].type == NotificationType.NEW_FOLLOWER.value

    async def test_duplicate_follow_returns_false(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="ntf_c_04a", username="ntf_c_04a")
        b = await _make_user(db_session, clerk_id="ntf_c_04b", username="ntf_c_04b")

        assert await follow_svc.follow(db_session, a.id, b.id) is True
        assert await follow_svc.follow(db_session, a.id, b.id) is False


# ── Listing / unread / mark read ──────────────────────────────────────────────


@pytest.mark.integration
class TestNotificationReads:
    async def _setup(self, session: AsyncSession, tag: str) -> tuple[User, User]:
        a = await _make_user(
            session, clerk_id=f"ntf_r_{tag}a", username=f"ntf_r_{tag}a"
        )
        b = await _make_user(
            session, clerk_id=f"ntf_r_{tag}b", username=f"ntf_r_{tag}b"
        )
        return a, b

    async def test_list_includes_melody_ref_and_actor(
        self, db_session: AsyncSession
    ) -> None:
        a, b = await self._setup(db_session, "01")
        track = await _make_track(db_session, mbid="mbid-ntf-r-01")
        item, _ = await melody_svc.send_melody(
            db_session, sender=a, recipient_username=b.username, track_mbid=track.mbid
        )
        assert item is not None

        listing = await notification_svc.list_notifications(db_session, b.id)

        assert len(listing.items) == 1
        n = listing.items[0]
        assert n.type is NotificationType.MELODY_RECEIVED
        assert n.actor.username == a.username
        assert n.melody is not None and n.melody.track.mbid == track.mbid
        assert n.read is False

    async def test_unread_count_and_mark_read(self, db_session: AsyncSession) -> None:
        a, b = await self._setup(db_session, "02")
        for i in range(3):
            track = await _make_track(db_session, mbid=f"mbid-ntf-r-02-{i}")
            await melody_svc.send_melody(
                db_session,
                sender=a,
                recipient_username=b.username,
                track_mbid=track.mbid,
            )

        assert await notification_svc.unread_count(db_session, b.id) == 3

        listing = await notification_svc.list_notifications(db_session, b.id)
        marked = await notification_svc.mark_read(
            db_session, user_id=b.id, notification_id=listing.items[0].id
        )
        assert marked is True
        assert await notification_svc.unread_count(db_session, b.id) == 2

        await notification_svc.mark_all_read(db_session, b.id)
        assert await notification_svc.unread_count(db_session, b.id) == 0

    async def test_cross_user_mark_read_refused(self, db_session: AsyncSession) -> None:
        a, b = await self._setup(db_session, "03")
        track = await _make_track(db_session, mbid="mbid-ntf-r-03")
        await melody_svc.send_melody(
            db_session, sender=a, recipient_username=b.username, track_mbid=track.mbid
        )
        listing = await notification_svc.list_notifications(db_session, b.id)

        # The actor (or anyone else) cannot mark the recipient's notification.
        marked = await notification_svc.mark_read(
            db_session, user_id=a.id, notification_id=listing.items[0].id
        )
        assert marked is False
        assert await notification_svc.unread_count(db_session, b.id) == 1

    async def test_pagination(self, db_session: AsyncSession) -> None:
        a, b = await self._setup(db_session, "04")
        for i in range(5):
            track = await _make_track(db_session, mbid=f"mbid-ntf-r-04-{i}")
            await melody_svc.send_melody(
                db_session,
                sender=a,
                recipient_username=b.username,
                track_mbid=track.mbid,
            )

        page1 = await notification_svc.list_notifications(db_session, b.id, limit=3)
        assert len(page1.items) == 3 and page1.next_cursor is not None
        page2 = await notification_svc.list_notifications(
            db_session, b.id, cursor=page1.next_cursor, limit=3
        )
        all_ids = [n.id for n in page1.items + page2.items]
        assert len(all_ids) == len(set(all_ids)) == 5
        assert page2.next_cursor is None
