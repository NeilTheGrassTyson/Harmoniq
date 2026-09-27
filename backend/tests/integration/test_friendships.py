"""Friend requests against a real database (specs/phase-2-friend-requests.md).

Each test names the acceptance criterion or requirement it pins. The decline
tests matter most: "the single most important behavioural rule in this spec".
"""

import importlib.util
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, get_optional_clerk_id
from app.config import settings
from app.core.enums import FriendshipState, VisibilityScope
from app.core.rate_limit import limiter
from app.database import get_db
from app.main import app
from app.models.follow import Follow
from app.models.friendship import Friendship
from app.models.notification import Notification
from app.models.user import User
from app.services import follow as follow_svc
from app.services import friendship as friendship_svc
from app.services import user as user_svc
from tests.integration.friends_helpers import make_friends

pytestmark = pytest.mark.integration


async def _user(session: AsyncSession, name: str) -> User:
    user = await user_svc.create_user(session, f"clerk_{name}", name, name.title())
    await session.flush()
    return user


async def _notifications(session: AsyncSession, user: User) -> list[str]:
    rows = await session.execute(
        select(Notification.type).where(Notification.user_id == user.id)
    )
    return sorted(rows.scalars().all())


def _client_as(session: AsyncSession, clerk_id: str | None) -> AsyncClient:
    async def _db():
        yield session

    async def _current() -> str:
        assert clerk_id is not None
        return clerk_id

    async def _optional() -> str | None:
        return clerk_id

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _current
    app.dependency_overrides[get_optional_clerk_id] = _optional
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ── Lifecycle ─────────────────────────────────────────────────────────────────


async def test_a_stranger_can_request_and_the_owner_is_notified(
    db_session: AsyncSession,
) -> None:
    owner, stranger = (
        await _user(db_session, "fr_own1"),
        await _user(db_session, "fr_str1"),
    )
    state, error = await friendship_svc.send_request(db_session, stranger, owner)
    assert state is FriendshipState.REQUEST_SENT and error == ""
    assert await _notifications(db_session, owner) == ["friend_request_received"]
    assert await friendship_svc.get_state(db_session, owner.id, stranger.id) is (
        FriendshipState.REQUEST_RECEIVED
    )
    assert not await friendship_svc.are_friends(db_session, owner.id, stranger.id)


async def test_decline_is_silent_and_leaves_no_trace_for_the_sender(
    db_session: AsyncSession,
) -> None:
    owner, asker = (
        await _user(db_session, "fr_own2"),
        await _user(db_session, "fr_ask2"),
    )
    await friendship_svc.send_request(db_session, asker, owner)
    # A sender never sees their own outstanding request, so a pending and a
    # declined one are identical from their side.
    pending_state = await friendship_svc.get_state(db_session, asker.id, owner.id)
    pending_overview = await friendship_svc.overview(db_session, asker)
    assert pending_state is FriendshipState.NONE
    assert pending_overview.friends == [] and pending_overview.incoming == []

    state, _ = await friendship_svc.decline_request(db_session, owner, asker)
    assert state is FriendshipState.NONE

    assert await _notifications(db_session, asker) == []
    assert (
        await friendship_svc.get_state(db_session, asker.id, owner.id) is pending_state
    )
    assert await friendship_svc.overview(db_session, asker) == pending_overview
    # Asking again changes nothing the sender can observe, and re-notifies no one.
    again, _ = await friendship_svc.send_request(db_session, asker, owner)
    assert again is FriendshipState.REQUEST_SENT
    assert await _notifications(db_session, owner) == ["friend_request_received"]
    # The decliner's own view simply has no pending request.
    assert await friendship_svc.get_state(db_session, owner.id, asker.id) is (
        FriendshipState.NONE
    )
    assert (await friendship_svc.overview(db_session, owner)).incoming == []


async def test_a_decline_is_recoverable_by_either_side(
    db_session: AsyncSession,
) -> None:
    owner, asker = (
        await _user(db_session, "fr_own3"),
        await _user(db_session, "fr_ask3"),
    )
    await friendship_svc.send_request(db_session, asker, owner)
    await friendship_svc.decline_request(db_session, owner, asker)
    # The decliner may change their mind by asking instead.
    state, _ = await friendship_svc.send_request(db_session, owner, asker)
    assert state is FriendshipState.REQUEST_SENT
    assert await friendship_svc.get_state(db_session, asker.id, owner.id) is (
        FriendshipState.REQUEST_RECEIVED
    )


async def test_accept_notifies_the_requester_and_creates_no_follow(
    db_session: AsyncSession,
) -> None:
    a, b = await _user(db_session, "fr_a4"), await _user(db_session, "fr_b4")
    await make_friends(db_session, a, b)
    assert await _notifications(db_session, a) == ["friend_request_accepted"]
    assert await friendship_svc.are_friends(db_session, a.id, b.id)
    assert await friendship_svc.are_friends(db_session, b.id, a.id)
    follows = await db_session.execute(select(func.count()).select_from(Follow))
    assert follows.scalar_one() == 0
    overview = await friendship_svc.overview(db_session, a)
    assert [p.username for p in overview.friends] == [b.username]


async def test_opposite_requests_become_one_friendship(
    db_session: AsyncSession,
) -> None:
    a, b = await _user(db_session, "fr_a5"), await _user(db_session, "fr_b5")
    await friendship_svc.send_request(db_session, a, b)
    state, _ = await friendship_svc.send_request(db_session, b, a)
    assert state is FriendshipState.FRIENDS
    rows = await db_session.execute(select(func.count()).select_from(Friendship))
    assert rows.scalar_one() == 1


async def test_no_self_friendship_and_no_duplicate_pair(
    db_session: AsyncSession,
) -> None:
    a, b = await _user(db_session, "fr_a6"), await _user(db_session, "fr_b6")
    state, error = await friendship_svc.send_request(db_session, a, a)
    assert state is None and error == friendship_svc.ERR_SELF
    assert not await friendship_svc.are_friends(db_session, a.id, a.id)
    low, high = sorted((a.id, b.id))
    with pytest.raises(Exception, match="ck_friendships_canonical_order"):
        async with db_session.begin_nested():
            db_session.add(
                Friendship(
                    user_low_id=high,
                    user_high_id=low,
                    status="pending",
                    requested_by=a.id,
                )
            )
            await db_session.flush()


async def test_repeat_requests_never_re_notify(db_session: AsyncSession) -> None:
    a, b = await _user(db_session, "fr_a7"), await _user(db_session, "fr_b7")
    for _ in range(3):
        state, _ = await friendship_svc.send_request(db_session, a, b)
        assert state is FriendshipState.REQUEST_SENT
    assert await _notifications(db_session, b) == ["friend_request_received"]


async def test_overview_offers_follow_back_only_where_not_following(
    db_session: AsyncSession,
) -> None:
    me = await _user(db_session, "fr_me12")
    followed, unfollowed, asker = (
        await _user(db_session, "fr_fol12"),
        await _user(db_session, "fr_unf12"),
        await _user(db_session, "fr_ask12"),
    )
    await make_friends(db_session, followed, me)
    await make_friends(db_session, unfollowed, me)
    await follow_svc.follow(db_session, me.id, followed.id)
    await friendship_svc.send_request(db_session, asker, me)
    overview = await friendship_svc.overview(db_session, me)
    assert {(p.username, p.you_follow) for p in overview.friends} == {
        (followed.username, True),
        (unfollowed.username, False),
    }
    assert [(p.username, p.you_follow) for p in overview.incoming] == [
        (asker.username, False)
    ]


# ── Access follows friendship on every surface ───────────────────────────────


async def test_accepting_grants_and_removing_revokes_friends_scoped_access(
    db_session: AsyncSession,
) -> None:
    owner, viewer = (
        await _user(db_session, "fr_own8"),
        await _user(db_session, "fr_view8"),
    )
    owner.bio = "Friends only"
    owner.visibility_bio = VisibilityScope.FRIENDS.value
    owner.visibility_follows = VisibilityScope.FRIENDS.value
    await db_session.flush()

    async def sees() -> tuple[bool, bool, bool]:
        profile = await user_svc.get_profile(
            db_session, owner.username, viewer.clerk_id
        )
        assert profile is not None
        lists = await follow_svc.can_view_follow_lists(db_session, owner, viewer)
        home = viewer.id in await friendship_svc.get_friend_ids(db_session, owner.id)
        return "bio" in profile.model_fields_set, lists, home

    assert await sees() == (False, False, False)
    await make_friends(db_session, viewer, owner)
    assert await sees() == (True, True, True)
    profile = await user_svc.get_profile(db_session, owner.username, viewer.clerk_id)
    assert profile and profile.friendship is FriendshipState.FRIENDS
    assert profile.follow and profile.follow.is_friend is True

    await friendship_svc.remove_friend(db_session, owner, viewer)
    assert await sees() == (False, False, False)
    assert await _notifications(db_session, owner) == ["friend_request_received"]


async def test_a_mutual_follow_alone_is_no_longer_friendship(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = await _user(db_session, "fr_a9"), await _user(db_session, "fr_b9")
    await follow_svc.follow(db_session, a.id, b.id)
    await follow_svc.follow(db_session, b.id, a.id)
    assert not await friendship_svc.are_friends(db_session, a.id, b.id)
    # Rollback: switching the feature off restores the Phase 1 definition.
    monkeypatch.setattr(settings, "friendships_enabled", False)
    assert await friendship_svc.are_friends(db_session, a.id, b.id)
    assert await friendship_svc.get_friend_ids(db_session, a.id) == {b.id}


# ── Consent gate ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("scope", ["follows", "mutuals"])
async def test_scope_refusals_share_one_message(
    db_session: AsyncSession, scope: str
) -> None:
    owner, asker = (
        await _user(db_session, f"fr_o_{scope}"),
        await _user(db_session, f"fr_s_{scope}"),
    )
    owner.friend_request_scope = scope
    await db_session.flush()
    state, error = await friendship_svc.send_request(db_session, asker, owner)
    assert state is None and error == friendship_svc.ERR_SCOPE
    await follow_svc.follow(db_session, owner.id, asker.id)
    if scope == "mutuals":
        state, error = await friendship_svc.send_request(db_session, asker, owner)
        assert state is None and error == friendship_svc.ERR_SCOPE
        await follow_svc.follow(db_session, asker.id, owner.id)
    state, _ = await friendship_svc.send_request(db_session, asker, owner)
    assert state is FriendshipState.REQUEST_SENT


async def test_new_accounts_accept_requests_from_everyone(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session, "fr_new10")
    await db_session.refresh(user)
    assert user.friend_request_scope == "everyone"


# ── Migration ─────────────────────────────────────────────────────────────────


async def test_existing_mutual_follows_convert_to_accepted_friendships(
    db_session: AsyncSession,
) -> None:
    path = next(Path(__file__).parents[2].glob("alembic/versions/*_add_friendships.py"))
    spec = importlib.util.spec_from_file_location("add_friendships", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    early, late, one_way = (
        await _user(db_session, "fr_mig_a"),
        await _user(db_session, "fr_mig_b"),
        await _user(db_session, "fr_mig_c"),
    )
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    db_session.add_all(
        [
            Follow(follower_id=early.id, followed_id=late.id, created_at=t0),
            Follow(
                follower_id=late.id,
                followed_id=early.id,
                created_at=t0 + timedelta(days=3),
            ),
            Follow(follower_id=one_way.id, followed_id=early.id, created_at=t0),
        ]
    )
    await db_session.flush()
    await db_session.execute(text(migration.CONVERT_MUTUAL_FOLLOWS))
    await db_session.execute(text(migration.CONVERT_MUTUAL_FOLLOWS))  # idempotent

    rows = (await db_session.execute(select(Friendship))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.status == "accepted" and row.requested_by == early.id
    assert row.responded_at == t0 + timedelta(days=3)
    assert await friendship_svc.are_friends(db_session, early.id, late.id)
    assert not await friendship_svc.are_friends(db_session, one_way.id, early.id)


def test_canonical_order_matches_postgres_uuid_order() -> None:
    ids = [uuid.uuid4() for _ in range(50)]
    assert sorted(ids) == sorted(ids, key=lambda u: u.bytes)


# ── API ───────────────────────────────────────────────────────────────────────


async def test_api_round_trip_is_private_and_refuses_suspended_senders(
    db_session: AsyncSession,
) -> None:
    a, b = await _user(db_session, "fr_api_a"), await _user(db_session, "fr_api_b")

    async with _client_as(db_session, a.clerk_id) as client:
        sent = await client.post(f"/api/v1/friends/{b.username}/request")
        self_req = await client.post(f"/api/v1/friends/{a.username}/request")
        missing = await client.post("/api/v1/friends/nobody_here/request")
    app.dependency_overrides.clear()
    assert sent.status_code == 200 and sent.json() == {"state": "request_sent"}
    assert sent.headers["cache-control"] == "private, no-store"
    assert self_req.status_code == 400 and missing.status_code == 404

    async with _client_as(db_session, b.clerk_id) as client:
        overview = await client.get("/api/v1/friends/me")
        accepted = await client.post(f"/api/v1/friends/{a.username}/accept")
        profile = await client.get(f"/api/v1/users/{a.username}")
    app.dependency_overrides.clear()
    assert [p["username"] for p in overview.json()["incoming"]] == [a.username]
    assert accepted.json() == {"state": "friends"}
    assert profile.json()["friendship"] == "friends"

    b.suspended_at = datetime.now(tz=UTC)
    await db_session.flush()
    c = await _user(db_session, "fr_api_c")
    async with _client_as(db_session, b.clerk_id) as client:
        refused = await client.post(f"/api/v1/friends/{c.username}/request")
    app.dependency_overrides.clear()
    assert refused.status_code == 403


async def test_anonymous_viewers_see_no_relationship(db_session: AsyncSession) -> None:
    a = await _user(db_session, "fr_anon_a")
    async with _client_as(db_session, None) as client:
        profile = await client.get(f"/api/v1/users/{a.username}")
    app.dependency_overrides.clear()
    assert "friendship" not in profile.json()


async def test_switching_the_feature_off_hides_the_endpoints_and_state(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = await _user(db_session, "fr_off_a"), await _user(db_session, "fr_off_b")
    monkeypatch.setattr(settings, "friendships_enabled", False)
    async with _client_as(db_session, a.clerk_id) as client:
        sent = await client.post(f"/api/v1/friends/{b.username}/request")
        profile = await client.get(f"/api/v1/users/{b.username}")
    app.dependency_overrides.clear()
    assert sent.status_code == 404
    assert "friendship" not in profile.json()


def test_sending_is_rate_limited_per_the_spec() -> None:
    limits = limiter._route_limits["app.api.v1.friends.send_request"]
    assert [str(limit.limit) for limit in limits] == ["5 per 1 minute", "30 per 1 day"]
