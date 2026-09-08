"""Real database coverage for reception, recipient isolation and consent."""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, event, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import settings
from app.models.catalog import Track
from app.models.melody import Melody
from app.models.notification import Notification
from app.models.user import User
from app.schemas.harmony import HarmonyOwn
from app.schemas.melody import MelodyReaction
from app.services import follow, harmony, melody

pytestmark = pytest.mark.integration
NOW = datetime(2026, 9, 8, tzinfo=UTC)


async def seed(
    session: AsyncSession, clerk_id: str = "recipient"
) -> tuple[User, User, Track]:
    sender = User(clerk_id="sender", username="sender", display_name="Sender")
    recipient = User(clerk_id=clerk_id, username="recipient", display_name="Recipient")
    track = Track(mbid=str(uuid.uuid4()), title="Only Shallow", last_fetched_at=NOW)
    session.add_all([sender, recipient, track])
    await session.flush()
    return sender, recipient, track


async def sent(
    session: AsyncSession,
    sender: User,
    recipient: User,
    track: Track,
    status: str = "sent",
    created_at: datetime = NOW,
) -> Melody:
    row = Melody(
        sender_id=sender.id,
        recipient_id=recipient.id,
        track_id=track.id,
        status=status,
        created_at=created_at,
    )
    session.add(row)
    await session.flush()
    return row


@pytest.mark.parametrize(
    ("status", "reaction", "expected_status"),
    [
        ("sent", "not_for_me", "rejected"),
        ("sent", "liked", "accepted"),
        ("sent", "loved", "accepted"),
        ("received", "loved", "accepted"),
        ("accepted", "not_for_me", "rejected"),
        ("rejected", "loved", "accepted"),
        ("opened", "not_for_me", "opened"),
    ],
)
async def test_reaction_transitions_cover_every_status_and_reaction(
    db_session: AsyncSession,
    status: str,
    reaction: MelodyReaction,
    expected_status: str,
) -> None:
    sender, recipient, track = await seed(db_session)
    row = await sent(db_session, sender, recipient, track, status)
    item, error = await melody.react(db_session, row.id, recipient.id, reaction)
    assert not error and item and item.reaction == reaction
    assert item.status == expected_status


async def test_feedback_is_editable_idempotent_visible_and_silent(
    db_session: AsyncSession,
) -> None:
    sender, recipient, track = await seed(db_session)
    row = await sent(db_session, sender, recipient, track)
    item, error = await melody.react(db_session, row.id, recipient.id, "liked")
    assert not error and item and item.reaction == "liked"
    timestamp = row.reacted_at
    await melody.react(db_session, row.id, recipient.id, "liked")
    assert row.reacted_at == timestamp
    updated, error = await melody.react(db_session, row.id, recipient.id, "not_for_me")
    assert not error and updated and updated.reaction == "not_for_me"
    assert (
        await db_session.execute(select(func.count()).select_from(Notification))
    ).scalar_one() == 0
    assert (await melody.list_sent(db_session, sender.id)).items[
        0
    ].reaction == updated.reaction
    assert (await melody.list_inbox(db_session, recipient.id)).items[
        0
    ].reaction == updated.reaction


async def test_owner_includes_history_once_and_explicit_opinion_wins(
    db_session: AsyncSession,
) -> None:
    sender, recipient, track = await seed(db_session)
    old = await sent(
        db_session,
        sender,
        recipient,
        track,
        "accepted",
        datetime(2020, 1, 1, tzinfo=UTC),
    )
    rejected = await sent(db_session, sender, recipient, track, "rejected")
    opened = await sent(db_session, sender, recipient, track, "opened")
    await sent(db_session, sender, recipient, track)
    own = await harmony.get_harmony(
        db_session, sender.username, sender.clerk_id, now=NOW
    )
    assert isinstance(own, HarmonyOwn)
    assert (
        own.positive_count,
        own.resolved_count,
        own.acceptance_percent,
        own.active_sending_months,
    ) == (2, 3, 67, 1)
    await melody.respond(db_session, old.id, recipient.id, "open")
    await melody.react(db_session, opened.id, recipient.id, "not_for_me")
    await melody.react(db_session, rejected.id, recipient.id, "loved")
    own = await harmony.get_harmony(
        db_session, sender.username, sender.clerk_id, now=NOW
    )
    assert isinstance(own, HarmonyOwn)
    assert (own.positive_count, own.resolved_count, own.acceptance_percent) == (
        2,
        3,
        67,
    )
    # An old client opening a rejected, explicitly disliked Melody cannot change its opinion.
    disliked = await sent(db_session, sender, recipient, track, "rejected")
    await melody.react(db_session, disliked.id, recipient.id, "not_for_me")
    await melody.respond(db_session, disliked.id, recipient.id, "open")
    assert disliked.reaction == "not_for_me"
    own = await harmony.get_harmony(
        db_session, sender.username, sender.clerk_id, now=NOW
    )
    assert isinstance(own, HarmonyOwn) and own.acceptance_percent == 50


async def test_empty_and_pending_are_not_zero(db_session: AsyncSession) -> None:
    sender, recipient, track = await seed(db_session)
    for pending in (False, True):
        if pending:
            await sent(db_session, sender, recipient, track)
        own = await harmony.get_harmony(
            db_session, sender.username, sender.clerk_id, now=NOW
        )
        assert isinstance(own, HarmonyOwn)
        assert own.acceptance_percent is None and own.resolved_count == 0
        assert own.visibility == "private"


async def test_private_denial_precedes_aggregation(db_session: AsyncSession) -> None:
    sender, _, _ = await seed(db_session)
    statements: list[str] = []
    engine = db_session.bind
    assert engine is not None
    sync = engine.sync_connection

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(sync, "before_cursor_execute", capture)
    try:
        response = await harmony.get_harmony(db_session, sender.username, None)
    finally:
        event.remove(sync, "before_cursor_execute", capture)
    assert response and response.model_dump() == {"kind": "hidden"}
    assert not any("melodies" in statement.lower() for statement in statements)


async def test_public_rejection_has_no_payload_delta_and_revocation_is_immediate(
    db_session: AsyncSession,
) -> None:
    sender, recipient, track = await seed(db_session)
    sender.visibility_harmony = "public"
    await sent(db_session, sender, recipient, track, "opened")
    pending = await sent(db_session, sender, recipient, track)
    before = await harmony.get_harmony(db_session, sender.username, None, now=NOW)
    await melody.react(db_session, pending.id, recipient.id, "not_for_me")
    after = await harmony.get_harmony(db_session, sender.username, None, now=NOW)
    assert before and after
    assert (
        before.model_dump()
        == after.model_dump()
        == {"kind": "shared", "summary": "listeners"}
    )
    sender.visibility_harmony = "friends"
    await db_session.flush()
    assert (
        await harmony.get_harmony(db_session, sender.username, None)
    ).kind == "hidden"
    await follow.follow(db_session, sender.id, recipient.id)
    assert (
        await harmony.get_harmony(db_session, sender.username, recipient.clerk_id)
    ).kind == "hidden"
    await follow.follow(db_session, recipient.id, sender.id)
    assert (
        await harmony.get_harmony(db_session, sender.username, recipient.clerk_id)
    ).kind == "shared"
    await follow.unfollow(db_session, recipient.id, sender.id)
    assert (
        await harmony.get_harmony(db_session, sender.username, recipient.clerk_id)
    ).kind == "hidden"


async def test_sustained_requires_three_months_and_three_distinct_recipients(
    db_session: AsyncSession,
) -> None:
    sender, recipient, track = await seed(db_session)
    sender.visibility_harmony = "public"
    # April through September inclusive. March is outside; future rows excluded.
    for month in (3, 4, 5, 6, 10):
        await sent(
            db_session,
            sender,
            recipient,
            track,
            "accepted",
            datetime(2026, month, 1, tzinfo=UTC),
        )
    own = await harmony.get_harmony(
        db_session, sender.username, sender.clerk_id, now=NOW
    )
    assert isinstance(own, HarmonyOwn) and own.active_sending_months == 3
    shared = await harmony.get_harmony(db_session, sender.username, None, now=NOW)
    assert shared and shared.model_dump() == {"kind": "shared", "summary": "listeners"}
    for number in range(2):
        other = User(
            clerk_id=f"other{number}", username=f"other{number}", display_name="Other"
        )
        db_session.add(other)
        await db_session.flush()
        await sent(db_session, sender, other, track, "opened")
    shared = await harmony.get_harmony(db_session, sender.username, None, now=NOW)
    assert shared and shared.model_dump() == {"kind": "shared", "summary": "sustained"}


async def test_reaction_api_recipient_isolation_validation_and_suspension(
    db_session: AsyncSession,
    authed_client: tuple[AsyncClient, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, clerk_id = authed_client
    sender, recipient, track = await seed(db_session, clerk_id)
    row = await sent(db_session, sender, recipient, track)
    foreign = await sent(db_session, recipient, sender, track)
    path = f"/api/v1/melodies/{row.id}/react"
    assert (
        await client.post(
            f"/api/v1/melodies/{foreign.id}/react", json={"reaction": "loved"}
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/melodies/{uuid.uuid4()}/react", json={"reaction": "loved"}
        )
    ).status_code == 404
    assert (await client.post(path, json={"reaction": "five_stars"})).status_code == 422
    response = await client.post(path, json={"reaction": "loved"})
    assert response.status_code == 200 and response.json()["reaction"] == "loved"
    assert response.headers["cache-control"] == "private, no-store"
    recipient.suspended_at = NOW
    await db_session.flush()
    assert (await client.post(path, json={"reaction": "liked"})).status_code == 403
    recipient.suspended_at = None
    await db_session.flush()
    monkeypatch.setattr(settings, "melody_reactions_enabled", False)
    assert (await client.post(path, json={"reaction": "liked"})).status_code == 404
    inbox = (await client.get("/api/v1/melodies/inbox")).json()
    assert not inbox["reactions_enabled"] and inbox["items"][0]["reaction"] == "loved"


async def test_harmony_api_owner_only_setting_and_no_store(
    db_session: AsyncSession,
    authed_client: tuple[AsyncClient, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, clerk_id = authed_client
    sender, recipient, _ = await seed(db_session, clerk_id)
    response = await client.patch(
        "/api/v1/harmony/me", json={"visibility": "public", "user_id": str(sender.id)}
    )
    assert response.status_code == 200
    assert (
        recipient.visibility_harmony == "public"
        and sender.visibility_harmony == "private"
    )
    assert (
        await client.patch("/api/v1/harmony/me", json={"visibility": "everyone"})
    ).status_code == 422
    own = await client.get("/api/v1/harmony/recipient")
    assert own.status_code == 200 and own.json()["kind"] == "owner"
    assert own.headers["cache-control"] == "private, no-store"
    assert (await client.get("/api/v1/harmony/sender")).json() == {"kind": "hidden"}
    recipient.suspended_at = NOW
    await db_session.flush()
    assert (
        await client.patch("/api/v1/harmony/me", json={"visibility": "friends"})
    ).status_code == 403
    assert (await client.get("/api/v1/harmony/recipient")).status_code == 200
    monkeypatch.setattr(settings, "harmony_enabled", False)
    assert (await client.get("/api/v1/harmony/recipient")).status_code == 404


async def test_anonymous_cannot_write_feedback_or_visibility(
    db_session: AsyncSession, anon_client: AsyncClient
) -> None:
    sender, recipient, track = await seed(db_session)
    row = await sent(db_session, sender, recipient, track)
    assert (
        await anon_client.post(
            f"/api/v1/melodies/{row.id}/react", json={"reaction": "loved"}
        )
    ).status_code in (401, 403)
    assert (
        await anon_client.patch("/api/v1/harmony/me", json={"visibility": "public"})
    ).status_code in (401, 403)
    assert row.reaction is None


async def test_concurrent_open_waits_for_reaction_and_retains_opinion(
    migrated_engine: AsyncEngine,
) -> None:
    factory = async_sessionmaker(migrated_engine, expire_on_commit=False)
    async with factory() as session:
        sender, recipient, track = await seed(session, "concurrent_recipient")
        row = await sent(session, sender, recipient, track)
        ids = (sender.id, recipient.id, track.id, row.id)
        await session.commit()
    try:
        async with factory() as first, factory() as second:
            updated, error = await melody.react(first, ids[3], ids[1], "not_for_me")
            assert updated and not error
            # First transaction deliberately holds the row lock while the other
            # connection tries to open; assert it cannot update an old snapshot.
            opening = asyncio.create_task(
                melody.respond(second, ids[3], ids[1], "open")
            )
            await asyncio.sleep(0.1)
            assert not opening.done()
            await first.commit()
            opened, error = await asyncio.wait_for(opening, timeout=5)
            assert opened and not error and opened.reaction == "not_for_me"
            await second.commit()
        async with factory() as session:
            saved = await session.get(Melody, ids[3])
            assert saved and saved.status == "opened" and saved.reaction == "not_for_me"
    finally:
        # Only this test's committed fixtures; never a shared/production DB.
        async with factory() as session:
            await session.execute(delete(Melody).where(Melody.id == ids[3]))
            await session.execute(delete(Track).where(Track.id == ids[2]))
            await session.execute(delete(User).where(User.id.in_(ids[:2])))
            await session.commit()
