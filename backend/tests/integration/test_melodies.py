"""
Integration tests: Melody send (scope + duplicate guards), inbox delivery,
sent-view status collapse, and the respond state machine.

The consent rules under test are constitutional (HARMONIQ.md §6): the
accept-scope failure message must be neutral and identical across scopes,
and a rejection must be visible to no one but the sender.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import MelodyAcceptScope, MelodyStatus
from app.models.catalog import Track
from app.models.melody import Melody
from app.models.user import User
from app.services import follow as follow_svc
from app.services import melody as melody_svc
from app.services import user as user_svc

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_user(
    session: AsyncSession,
    *,
    clerk_id: str,
    username: str,
    accept_scope: MelodyAcceptScope = MelodyAcceptScope.EVERYONE,
) -> User:
    user = await user_svc.create_user(session, clerk_id, username, "Test User")
    user.melody_accept_scope = accept_scope.value
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


async def _send(
    session: AsyncSession, sender: User, recipient: User, track: Track
) -> Melody:
    item, error = await melody_svc.send_melody(
        session,
        sender=sender,
        recipient_username=recipient.username,
        track_mbid=track.mbid,
    )
    assert error == "", f"unexpected send error: {error}"
    assert item is not None
    result = await session.execute(select(Melody).where(Melody.id == item.id))
    return result.scalar_one()


# ── Send ──────────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestMelodySend:
    async def test_send_creates_row_with_sent_status(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="mel_s_01a", username="mel_s_01a")
        b = await _make_user(db_session, clerk_id="mel_s_01b", username="mel_s_01b")
        track = await _make_track(db_session, mbid="mbid-mel-s-01")

        melody = await _send(db_session, a, b, track)

        assert melody.status == MelodyStatus.SENT.value
        assert melody.sender_id == a.id
        assert melody.recipient_id == b.id
        assert melody.responded_at is None

    async def test_self_send_refused(self, db_session: AsyncSession) -> None:
        a = await _make_user(db_session, clerk_id="mel_s_02a", username="mel_s_02a")
        track = await _make_track(db_session, mbid="mbid-mel-s-02")

        item, error = await melody_svc.send_melody(
            db_session, sender=a, recipient_username=a.username, track_mbid=track.mbid
        )

        assert item is None
        assert "yourself" in error

    async def test_unknown_recipient_and_track(self, db_session: AsyncSession) -> None:
        a = await _make_user(db_session, clerk_id="mel_s_03a", username="mel_s_03a")
        track = await _make_track(db_session, mbid="mbid-mel-s-03")

        item, error = await melody_svc.send_melody(
            db_session,
            sender=a,
            recipient_username="nobody-here",
            track_mbid=track.mbid,
        )
        assert item is None and error == "Recipient not found."

        b = await _make_user(db_session, clerk_id="mel_s_03b", username="mel_s_03b")
        item, error = await melody_svc.send_melody(
            db_session,
            sender=a,
            recipient_username=b.username,
            track_mbid="no-such-mbid",
        )
        assert item is None and error == "Track not found."

    async def test_duplicate_pending_refused_then_allowed_after_response(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="mel_s_04a", username="mel_s_04a")
        b = await _make_user(db_session, clerk_id="mel_s_04b", username="mel_s_04b")
        track = await _make_track(db_session, mbid="mbid-mel-s-04")

        melody = await _send(db_session, a, b, track)

        item, error = await melody_svc.send_melody(
            db_session, sender=a, recipient_username=b.username, track_mbid=track.mbid
        )
        assert item is None
        assert "already sent" in error

        # After the recipient responds, re-sending the same track is allowed.
        _, error = await melody_svc.respond(
            db_session, melody_id=melody.id, recipient_id=b.id, action="accept"
        )
        assert error == ""
        item, error = await melody_svc.send_melody(
            db_session, sender=a, recipient_username=b.username, track_mbid=track.mbid
        )
        assert error == "" and item is not None


# ── Accept scope (consent guard) ──────────────────────────────────────────────


@pytest.mark.integration
class TestMelodyAcceptScope:
    _NEUTRAL = "This member isn't receiving Melodies right now."

    async def test_follows_scope_blocks_stranger_with_neutral_error(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="mel_sc_01a", username="mel_sc_01a")
        b = await _make_user(
            db_session,
            clerk_id="mel_sc_01b",
            username="mel_sc_01b",
            accept_scope=MelodyAcceptScope.FOLLOWS,
        )
        track = await _make_track(db_session, mbid="mbid-mel-sc-01")

        item, error = await melody_svc.send_melody(
            db_session, sender=a, recipient_username=b.username, track_mbid=track.mbid
        )

        assert item is None
        assert error == self._NEUTRAL

    async def test_follows_scope_allows_when_recipient_follows_sender(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="mel_sc_02a", username="mel_sc_02a")
        b = await _make_user(
            db_session,
            clerk_id="mel_sc_02b",
            username="mel_sc_02b",
            accept_scope=MelodyAcceptScope.FOLLOWS,
        )
        track = await _make_track(db_session, mbid="mbid-mel-sc-02")
        await follow_svc.follow(db_session, b.id, a.id)  # recipient follows sender
        await db_session.flush()

        item, error = await melody_svc.send_melody(
            db_session, sender=a, recipient_username=b.username, track_mbid=track.mbid
        )
        assert error == "" and item is not None

    async def test_mutuals_scope_blocks_one_way_with_identical_neutral_error(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="mel_sc_03a", username="mel_sc_03a")
        b = await _make_user(
            db_session,
            clerk_id="mel_sc_03b",
            username="mel_sc_03b",
            accept_scope=MelodyAcceptScope.MUTUALS,
        )
        track = await _make_track(db_session, mbid="mbid-mel-sc-03")
        await follow_svc.follow(db_session, b.id, a.id)  # one-way only
        await db_session.flush()

        item, error = await melody_svc.send_melody(
            db_session, sender=a, recipient_username=b.username, track_mbid=track.mbid
        )

        assert item is None
        # Identical wording across scopes: the sender must never be able to
        # infer the recipient's setting from the error text.
        assert error == self._NEUTRAL

    async def test_mutuals_scope_allows_friends(self, db_session: AsyncSession) -> None:
        a = await _make_user(db_session, clerk_id="mel_sc_04a", username="mel_sc_04a")
        b = await _make_user(
            db_session,
            clerk_id="mel_sc_04b",
            username="mel_sc_04b",
            accept_scope=MelodyAcceptScope.MUTUALS,
        )
        track = await _make_track(db_session, mbid="mbid-mel-sc-04")
        await follow_svc.follow(db_session, a.id, b.id)
        await follow_svc.follow(db_session, b.id, a.id)
        await db_session.flush()

        item, error = await melody_svc.send_melody(
            db_session, sender=a, recipient_username=b.username, track_mbid=track.mbid
        )
        assert error == "" and item is not None


# ── Inbox delivery + sent view ────────────────────────────────────────────────


@pytest.mark.integration
class TestMelodyLists:
    async def test_inbox_fetch_marks_received(self, db_session: AsyncSession) -> None:
        a = await _make_user(db_session, clerk_id="mel_l_01a", username="mel_l_01a")
        b = await _make_user(db_session, clerk_id="mel_l_01b", username="mel_l_01b")
        track = await _make_track(db_session, mbid="mbid-mel-l-01")
        melody = await _send(db_session, a, b, track)

        inbox = await melody_svc.list_inbox(db_session, recipient_id=b.id)

        assert len(inbox.items) == 1
        assert inbox.items[0].status is MelodyStatus.RECEIVED
        await db_session.refresh(melody)
        assert melody.status == MelodyStatus.RECEIVED.value
        assert melody.received_at is not None

    async def test_sent_view_collapses_received_and_shows_rejected(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="mel_l_02a", username="mel_l_02a")
        b = await _make_user(db_session, clerk_id="mel_l_02b", username="mel_l_02b")
        t1 = await _make_track(db_session, mbid="mbid-mel-l-02a")
        t2 = await _make_track(db_session, mbid="mbid-mel-l-02b")
        await _send(db_session, a, b, t1)
        m2 = await _send(db_session, a, b, t2)

        # Delivery happens (b fetches inbox), then b rejects one.
        await melody_svc.list_inbox(db_session, recipient_id=b.id)
        _, error = await melody_svc.respond(
            db_session, melody_id=m2.id, recipient_id=b.id, action="reject"
        )
        assert error == ""

        sent = await melody_svc.list_sent(db_session, sender_id=a.id)
        by_id = {item.id: item for item in sent.items}

        # 'received' collapses to 'sent' — no read receipts for the sender.
        assert by_id[m2.id].status is MelodyStatus.REJECTED
        others = [i for i in sent.items if i.id != m2.id]
        assert others[0].status is MelodyStatus.SENT

    async def test_inbox_is_recipient_only(self, db_session: AsyncSession) -> None:
        a = await _make_user(db_session, clerk_id="mel_l_03a", username="mel_l_03a")
        b = await _make_user(db_session, clerk_id="mel_l_03b", username="mel_l_03b")
        c = await _make_user(db_session, clerk_id="mel_l_03c", username="mel_l_03c")
        track = await _make_track(db_session, mbid="mbid-mel-l-03")
        await _send(db_session, a, b, track)

        assert (await melody_svc.list_inbox(db_session, recipient_id=c.id)).items == []
        assert (await melody_svc.list_sent(db_session, sender_id=c.id)).items == []

    async def test_inbox_pagination_cursor(self, db_session: AsyncSession) -> None:
        a = await _make_user(db_session, clerk_id="mel_l_04a", username="mel_l_04a")
        b = await _make_user(db_session, clerk_id="mel_l_04b", username="mel_l_04b")
        for i in range(5):
            track = await _make_track(db_session, mbid=f"mbid-mel-l-04-{i}")
            await _send(db_session, a, b, track)

        page1 = await melody_svc.list_inbox(db_session, recipient_id=b.id, limit=2)
        assert len(page1.items) == 2 and page1.next_cursor is not None

        page2 = await melody_svc.list_inbox(
            db_session, recipient_id=b.id, cursor=page1.next_cursor, limit=2
        )
        page3 = await melody_svc.list_inbox(
            db_session, recipient_id=b.id, cursor=page2.next_cursor, limit=2
        )

        all_ids = [i.id for i in page1.items + page2.items + page3.items]
        assert len(all_ids) == len(set(all_ids)) == 5
        assert page3.next_cursor is None


# ── Respond state machine ─────────────────────────────────────────────────────


@pytest.mark.integration
class TestMelodyRespond:
    async def _setup(
        self, session: AsyncSession, tag: str
    ) -> tuple[User, User, Melody]:
        a = await _make_user(
            session, clerk_id=f"mel_r_{tag}a", username=f"mel_r_{tag}a"
        )
        b = await _make_user(
            session, clerk_id=f"mel_r_{tag}b", username=f"mel_r_{tag}b"
        )
        track = await _make_track(session, mbid=f"mbid-mel-r-{tag}")
        melody = await _send(session, a, b, track)
        return a, b, melody

    async def test_accept_then_open_upgrade(self, db_session: AsyncSession) -> None:
        _, b, melody = await self._setup(db_session, "01")

        item, error = await melody_svc.respond(
            db_session, melody_id=melody.id, recipient_id=b.id, action="accept"
        )
        assert error == "" and item is not None
        assert item.status is MelodyStatus.ACCEPTED
        assert item.responded_at is not None

        item, error = await melody_svc.respond(
            db_session, melody_id=melody.id, recipient_id=b.id, action="open"
        )
        assert error == "" and item is not None
        assert item.status is MelodyStatus.OPENED

    async def test_rejected_is_recoverable(self, db_session: AsyncSession) -> None:
        _, b, melody = await self._setup(db_session, "02")

        _, error = await melody_svc.respond(
            db_session, melody_id=melody.id, recipient_id=b.id, action="reject"
        )
        assert error == ""

        item, error = await melody_svc.respond(
            db_session, melody_id=melody.id, recipient_id=b.id, action="open"
        )
        assert error == "" and item is not None
        assert item.status is MelodyStatus.OPENED

    async def test_opened_is_terminal(self, db_session: AsyncSession) -> None:
        _, b, melody = await self._setup(db_session, "03")

        _, error = await melody_svc.respond(
            db_session, melody_id=melody.id, recipient_id=b.id, action="open"
        )
        assert error == ""

        for action in ("accept", "open", "reject"):
            item, error = await melody_svc.respond(
                db_session, melody_id=melody.id, recipient_id=b.id, action=action
            )
            assert item is None
            assert "already" in error

    async def test_accepted_cannot_be_rejected(self, db_session: AsyncSession) -> None:
        _, b, melody = await self._setup(db_session, "04")

        _, error = await melody_svc.respond(
            db_session, melody_id=melody.id, recipient_id=b.id, action="accept"
        )
        assert error == ""

        item, error = await melody_svc.respond(
            db_session, melody_id=melody.id, recipient_id=b.id, action="reject"
        )
        assert item is None and "already" in error

    async def test_non_recipient_gets_not_found(self, db_session: AsyncSession) -> None:
        a, _, melody = await self._setup(db_session, "05")

        # The sender themselves cannot respond — and learns nothing.
        item, error = await melody_svc.respond(
            db_session, melody_id=melody.id, recipient_id=a.id, action="accept"
        )
        assert item is None
        assert error == "Melody not found."

    async def test_unknown_melody_not_found(self, db_session: AsyncSession) -> None:
        _, b, _ = await self._setup(db_session, "06")

        item, error = await melody_svc.respond(
            db_session, melody_id=uuid.uuid4(), recipient_id=b.id, action="accept"
        )
        assert item is None and error == "Melody not found."
