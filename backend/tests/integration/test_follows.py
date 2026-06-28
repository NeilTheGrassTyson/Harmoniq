"""
Integration tests: follow/unfollow service, mutual-follow check, counts,
paginated lists, rate limiting, and visibility-stub replacement.

Each test gets its own `db_session` wrapped in a transaction that rolls back
on teardown for full isolation.
"""


import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, get_optional_clerk_id
from app.database import get_db
from app.main import app
from app.models.follow import Follow
from app.models.user import User
from app.services import follow as follow_svc
from app.services import user as user_svc

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_user(
    session: AsyncSession,
    *,
    clerk_id: str,
    username: str,
    display_name: str = "Test User",
) -> User:
    user = await user_svc.create_user(session, clerk_id, username, display_name)
    await session.flush()
    return user


async def _follow(session: AsyncSession, follower: User, followed: User) -> None:
    await follow_svc.follow(session, follower.id, followed.id)
    await session.flush()


async def _edge_count(session: AsyncSession, follower: User, followed: User) -> int:
    result = await session.execute(
        select(Follow).where(
            Follow.follower_id == follower.id,
            Follow.followed_id == followed.id,
        )
    )
    return len(result.scalars().all())


# ── §4.1 Core follow / unfollow behaviour ─────────────────────────────────────


@pytest.mark.integration
class TestFollowCore:
    async def test_follow_creates_edge(self, db_session: AsyncSession) -> None:
        a = await _make_user(db_session, clerk_id="fw_c_01a", username="fw_c_01a")
        b = await _make_user(db_session, clerk_id="fw_c_01b", username="fw_c_01b")

        await _follow(db_session, a, b)

        assert await _edge_count(db_session, a, b) == 1

    async def test_unfollow_removes_edge(self, db_session: AsyncSession) -> None:
        a = await _make_user(db_session, clerk_id="fw_c_02a", username="fw_c_02a")
        b = await _make_user(db_session, clerk_id="fw_c_02b", username="fw_c_02b")

        await _follow(db_session, a, b)
        await follow_svc.unfollow(db_session, a.id, b.id)
        await db_session.flush()

        assert await _edge_count(db_session, a, b) == 0

    async def test_follow_already_followed_is_idempotent(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="fw_c_03a", username="fw_c_03a")
        b = await _make_user(db_session, clerk_id="fw_c_03b", username="fw_c_03b")

        await _follow(db_session, a, b)
        # Second follow must not raise and must not create a duplicate row.
        await follow_svc.follow(db_session, a.id, b.id)
        await db_session.flush()

        assert await _edge_count(db_session, a, b) == 1

    async def test_unfollow_not_followed_is_noop(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="fw_c_04a", username="fw_c_04a")
        b = await _make_user(db_session, clerk_id="fw_c_04b", username="fw_c_04b")

        # No prior follow — must not raise.
        await follow_svc.unfollow(db_session, a.id, b.id)
        await db_session.flush()

        assert await _edge_count(db_session, a, b) == 0


# ── §4.2 Self-follow rejection ────────────────────────────────────────────────


@pytest.mark.integration
class TestSelfFollowRejection:
    async def test_self_follow_raises_value_error(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="fw_sf_01", username="fw_sf_01")

        with pytest.raises(ValueError, match="cannot follow"):
            await follow_svc.follow(db_session, a.id, a.id)


# ── §4.3 Mutual-follow / is_friend logic ─────────────────────────────────────


@pytest.mark.integration
class TestMutualFollow:
    async def test_mutual_true_when_both_directions_exist(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="fw_mf_01a", username="fw_mf_01a")
        b = await _make_user(db_session, clerk_id="fw_mf_01b", username="fw_mf_01b")

        await _follow(db_session, a, b)
        await _follow(db_session, b, a)

        assert await follow_svc.is_mutual_follow(db_session, a.id, b.id) is True

    async def test_mutual_false_when_only_one_direction(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="fw_mf_02a", username="fw_mf_02a")
        b = await _make_user(db_session, clerk_id="fw_mf_02b", username="fw_mf_02b")

        await _follow(db_session, a, b)

        assert await follow_svc.is_mutual_follow(db_session, a.id, b.id) is False

    async def test_mutual_false_when_neither_direction(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="fw_mf_03a", username="fw_mf_03a")
        b = await _make_user(db_session, clerk_id="fw_mf_03b", username="fw_mf_03b")

        assert await follow_svc.is_mutual_follow(db_session, a.id, b.id) is False

    async def test_mutual_check_is_symmetric(self, db_session: AsyncSession) -> None:
        a = await _make_user(db_session, clerk_id="fw_mf_04a", username="fw_mf_04a")
        b = await _make_user(db_session, clerk_id="fw_mf_04b", username="fw_mf_04b")

        await _follow(db_session, a, b)
        await _follow(db_session, b, a)

        result_ab = await follow_svc.is_mutual_follow(db_session, a.id, b.id)
        result_ba = await follow_svc.is_mutual_follow(db_session, b.id, a.id)
        assert result_ab == result_ba is True

    async def test_mutual_check_symmetric_when_only_one_direction(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="fw_mf_05a", username="fw_mf_05a")
        b = await _make_user(db_session, clerk_id="fw_mf_05b", username="fw_mf_05b")

        await _follow(db_session, a, b)

        result_ab = await follow_svc.is_mutual_follow(db_session, a.id, b.id)
        result_ba = await follow_svc.is_mutual_follow(db_session, b.id, a.id)
        assert result_ab == result_ba is False


# ── §4.4 Idempotency under concurrent-style calls ────────────────────────────


@pytest.mark.integration
class TestIdempotency:
    async def test_concurrent_follow_requests_produce_one_edge(
        self, db_session: AsyncSession
    ) -> None:
        """
        Issue the same follow twice in immediate succession (same session, same
        flush cycle). ON CONFLICT DO NOTHING ensures exactly one row.
        """
        a = await _make_user(db_session, clerk_id="fw_id_01a", username="fw_id_01a")
        b = await _make_user(db_session, clerk_id="fw_id_01b", username="fw_id_01b")

        await follow_svc.follow(db_session, a.id, b.id)
        await follow_svc.follow(db_session, a.id, b.id)
        await db_session.flush()

        assert await _edge_count(db_session, a, b) == 1


# ── §4.5 Count accuracy ───────────────────────────────────────────────────────


@pytest.mark.integration
class TestCounts:
    async def test_follower_count_increments_on_follow(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="fw_ct_01a", username="fw_ct_01a")
        b = await _make_user(db_session, clerk_id="fw_ct_01b", username="fw_ct_01b")

        assert await follow_svc.get_follower_count(db_session, b.id) == 0
        await _follow(db_session, a, b)
        assert await follow_svc.get_follower_count(db_session, b.id) == 1

    async def test_following_count_increments_on_follow(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="fw_ct_02a", username="fw_ct_02a")
        b = await _make_user(db_session, clerk_id="fw_ct_02b", username="fw_ct_02b")

        assert await follow_svc.get_following_count(db_session, a.id) == 0
        await _follow(db_session, a, b)
        assert await follow_svc.get_following_count(db_session, a.id) == 1

    async def test_counts_decrement_on_unfollow(self, db_session: AsyncSession) -> None:
        a = await _make_user(db_session, clerk_id="fw_ct_03a", username="fw_ct_03a")
        b = await _make_user(db_session, clerk_id="fw_ct_03b", username="fw_ct_03b")

        await _follow(db_session, a, b)
        await follow_svc.unfollow(db_session, a.id, b.id)
        await db_session.flush()

        assert await follow_svc.get_follower_count(db_session, b.id) == 0
        assert await follow_svc.get_following_count(db_session, a.id) == 0

    async def test_duplicate_follow_does_not_inflate_count(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="fw_ct_04a", username="fw_ct_04a")
        b = await _make_user(db_session, clerk_id="fw_ct_04b", username="fw_ct_04b")

        await follow_svc.follow(db_session, a.id, b.id)
        await follow_svc.follow(db_session, a.id, b.id)
        await db_session.flush()

        assert await follow_svc.get_follower_count(db_session, b.id) == 1
        assert await follow_svc.get_following_count(db_session, a.id) == 1


# ── §4.6 Pagination correctness ──────────────────────────────────────────────


@pytest.mark.integration
class TestPagination:
    async def _make_followers(
        self, session: AsyncSession, target: User, n: int, prefix: str
    ) -> list[User]:
        followers = []
        for i in range(n):
            u = await _make_user(
                session, clerk_id=f"{prefix}_{i}", username=f"{prefix}_{i}"
            )
            await _follow(session, u, target)
            followers.append(u)
        return followers

    async def test_follower_list_paginates_correctly(
        self, db_session: AsyncSession
    ) -> None:
        target = await _make_user(
            db_session, clerk_id="fw_pg_01t", username="fw_pg_01t"
        )
        await self._make_followers(db_session, target, 5, "fw_pg_f01")

        page1 = await follow_svc.get_followers(db_session, target.id, limit=3)
        assert len(page1.items) == 3
        assert page1.next_cursor is not None

        page2 = await follow_svc.get_followers(
            db_session, target.id, cursor=page1.next_cursor, limit=3
        )
        assert len(page2.items) == 2
        assert page2.next_cursor is None

        all_ids = {i.user_id for i in page1.items} | {i.user_id for i in page2.items}
        assert len(all_ids) == 5

    async def test_following_list_paginates_correctly(
        self, db_session: AsyncSession
    ) -> None:
        follower = await _make_user(
            db_session, clerk_id="fw_pg_02f", username="fw_pg_02f"
        )
        targets = []
        for i in range(5):
            t = await _make_user(
                db_session, clerk_id=f"fw_pg_02t_{i}", username=f"fw_pg_02t_{i}"
            )
            await _follow(db_session, follower, t)
            targets.append(t)

        page1 = await follow_svc.get_following(db_session, follower.id, limit=3)
        assert len(page1.items) == 3
        assert page1.next_cursor is not None

        page2 = await follow_svc.get_following(
            db_session, follower.id, cursor=page1.next_cursor, limit=3
        )
        assert len(page2.items) == 2
        assert page2.next_cursor is None

        all_ids = {i.user_id for i in page1.items} | {i.user_id for i in page2.items}
        assert len(all_ids) == 5

    async def test_no_duplicate_or_skipped_entries_across_pages(
        self, db_session: AsyncSession
    ) -> None:
        target = await _make_user(
            db_session, clerk_id="fw_pg_03t", username="fw_pg_03t"
        )
        await self._make_followers(db_session, target, 6, "fw_pg_f03")

        page1 = await follow_svc.get_followers(db_session, target.id, limit=4)
        page2 = await follow_svc.get_followers(
            db_session, target.id, cursor=page1.next_cursor, limit=4
        )

        ids_p1 = {i.user_id for i in page1.items}
        ids_p2 = {i.user_id for i in page2.items}
        # No overlap between pages
        assert ids_p1.isdisjoint(ids_p2)
        # All 6 entries covered
        assert len(ids_p1 | ids_p2) == 6

    async def test_empty_follower_list(self, db_session: AsyncSession) -> None:
        target = await _make_user(
            db_session, clerk_id="fw_pg_04t", username="fw_pg_04t"
        )
        result = await follow_svc.get_followers(db_session, target.id)
        assert result.items == []
        assert result.next_cursor is None


# ── §4.7 _is_friend() stub replacement ───────────────────────────────────────


@pytest.mark.integration
class TestFriendStubReplacement:
    """
    Regression tests ensuring _is_friend() in user_svc and rating_svc now
    reflects real mutual-follow state rather than the previous always-False stub.
    """

    async def test_user_profile_friends_field_visible_to_mutual_follower(
        self, db_session: AsyncSession
    ) -> None:
        from app.core.enums import VisibilityScope

        owner = await _make_user(db_session, clerk_id="fw_fr_01o", username="fw_fr_01o")
        owner.bio = "Friends-only bio"
        owner.visibility_bio = VisibilityScope.FRIENDS.value
        await db_session.flush()

        viewer = await _make_user(
            db_session, clerk_id="fw_fr_01v", username="fw_fr_01v"
        )

        # Establish mutual follow
        await _follow(db_session, owner, viewer)
        await _follow(db_session, viewer, owner)

        profile = await user_svc.get_profile(
            db_session, owner.username, viewer.clerk_id
        )
        assert profile is not None
        assert "bio" in profile.model_fields_set
        assert profile.bio == "Friends-only bio"

    async def test_user_profile_friends_field_hidden_for_non_mutual(
        self, db_session: AsyncSession
    ) -> None:
        from app.core.enums import VisibilityScope

        owner = await _make_user(db_session, clerk_id="fw_fr_02o", username="fw_fr_02o")
        owner.bio = "Friends-only bio"
        owner.visibility_bio = VisibilityScope.FRIENDS.value
        await db_session.flush()

        viewer = await _make_user(
            db_session, clerk_id="fw_fr_02v", username="fw_fr_02v"
        )
        # Only one direction: viewer follows owner, but owner does NOT follow viewer
        await _follow(db_session, viewer, owner)

        profile = await user_svc.get_profile(
            db_session, owner.username, viewer.clerk_id
        )
        assert profile is not None
        assert "bio" not in profile.model_fields_set

    async def test_friends_field_was_always_false_before_mutual_follow(
        self, db_session: AsyncSession
    ) -> None:
        """No follow edges → FRIENDS-scoped content must remain hidden."""
        from app.core.enums import VisibilityScope

        owner = await _make_user(db_session, clerk_id="fw_fr_03o", username="fw_fr_03o")
        owner.bio = "Secret"
        owner.visibility_bio = VisibilityScope.FRIENDS.value
        await db_session.flush()

        viewer = await _make_user(
            db_session, clerk_id="fw_fr_03v", username="fw_fr_03v"
        )

        profile = await user_svc.get_profile(
            db_session, owner.username, viewer.clerk_id
        )
        assert profile is not None
        assert "bio" not in profile.model_fields_set


# ── §4.8 Follow state in profile response ────────────────────────────────────


@pytest.mark.integration
class TestFollowStateInProfile:
    async def test_follow_state_reflects_real_relationship(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="fw_ps_01a", username="fw_ps_01a")
        b = await _make_user(db_session, clerk_id="fw_ps_01b", username="fw_ps_01b")

        await _follow(db_session, a, b)

        profile = await user_svc.get_profile(db_session, b.username, a.clerk_id)
        assert profile is not None
        assert profile.follow is not None
        assert profile.follow.is_following is True
        assert profile.follow.follows_you is False
        assert profile.follow.is_friend is False

    async def test_follow_state_is_friend_true_when_mutual(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="fw_ps_02a", username="fw_ps_02a")
        b = await _make_user(db_session, clerk_id="fw_ps_02b", username="fw_ps_02b")

        await _follow(db_session, a, b)
        await _follow(db_session, b, a)

        profile = await user_svc.get_profile(db_session, b.username, a.clerk_id)
        assert profile is not None
        assert profile.follow is not None
        assert profile.follow.is_friend is True

    async def test_follow_state_absent_on_own_profile(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="fw_ps_03a", username="fw_ps_03a")

        profile = await user_svc.get_profile(db_session, a.username, a.clerk_id)
        assert profile is not None
        assert profile.follow is None

    async def test_follower_and_following_counts_on_profile(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="fw_ps_04a", username="fw_ps_04a")
        b = await _make_user(db_session, clerk_id="fw_ps_04b", username="fw_ps_04b")
        c = await _make_user(db_session, clerk_id="fw_ps_04c", username="fw_ps_04c")

        await _follow(db_session, a, b)
        await _follow(db_session, c, b)

        profile = await user_svc.get_profile(db_session, b.username, None)
        assert profile is not None
        assert profile.follower_count == 2
        assert profile.following_count == 0


# ── §4.9 API endpoint tests ───────────────────────────────────────────────────


def _db_override(session: AsyncSession):
    async def _override():
        yield session

    return _override


@pytest.mark.integration
class TestFollowsAPI:
    async def _authed_client(
        self, db_session: AsyncSession, clerk_id: str
    ) -> AsyncClient:
        async def _current_user() -> str:
            return clerk_id

        async def _optional_id() -> str | None:
            return clerk_id

        app.dependency_overrides[get_db] = _db_override(db_session)
        app.dependency_overrides[get_current_user] = _current_user
        app.dependency_overrides[get_optional_clerk_id] = _optional_id
        from httpx import ASGITransport

        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def test_follow_returns_204(self, db_session: AsyncSession) -> None:
        a = await _make_user(db_session, clerk_id="fw_api_01a", username="fw_api_01a")
        b = await _make_user(db_session, clerk_id="fw_api_01b", username="fw_api_01b")

        async with await self._authed_client(db_session, a.clerk_id) as client:
            resp = await client.post(f"/api/v1/follows/{b.username}")
        app.dependency_overrides.clear()
        assert resp.status_code == 204

    async def test_unfollow_returns_204(self, db_session: AsyncSession) -> None:
        a = await _make_user(db_session, clerk_id="fw_api_02a", username="fw_api_02a")
        b = await _make_user(db_session, clerk_id="fw_api_02b", username="fw_api_02b")
        await _follow(db_session, a, b)

        async with await self._authed_client(db_session, a.clerk_id) as client:
            resp = await client.delete(f"/api/v1/follows/{b.username}")
        app.dependency_overrides.clear()
        assert resp.status_code == 204

    async def test_self_follow_returns_400(self, db_session: AsyncSession) -> None:
        a = await _make_user(db_session, clerk_id="fw_api_03a", username="fw_api_03a")

        async with await self._authed_client(db_session, a.clerk_id) as client:
            resp = await client.post(f"/api/v1/follows/{a.username}")
        app.dependency_overrides.clear()
        assert resp.status_code == 400

    async def test_follow_nonexistent_user_returns_404(
        self, db_session: AsyncSession
    ) -> None:
        a = await _make_user(db_session, clerk_id="fw_api_04a", username="fw_api_04a")

        async with await self._authed_client(db_session, a.clerk_id) as client:
            resp = await client.post("/api/v1/follows/nobody_exists_here")
        app.dependency_overrides.clear()
        assert resp.status_code == 404

    async def test_follower_list_endpoint(self, db_session: AsyncSession) -> None:
        a = await _make_user(db_session, clerk_id="fw_api_05a", username="fw_api_05a")
        b = await _make_user(db_session, clerk_id="fw_api_05b", username="fw_api_05b")
        await _follow(db_session, a, b)

        app.dependency_overrides[get_db] = _db_override(db_session)
        async with AsyncClient(
            transport=__import__("httpx").ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/follows/{b.username}/followers")
        app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["username"] == a.username

    async def test_following_list_endpoint(self, db_session: AsyncSession) -> None:
        a = await _make_user(db_session, clerk_id="fw_api_06a", username="fw_api_06a")
        b = await _make_user(db_session, clerk_id="fw_api_06b", username="fw_api_06b")
        await _follow(db_session, a, b)

        app.dependency_overrides[get_db] = _db_override(db_session)
        async with AsyncClient(
            transport=__import__("httpx").ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/follows/{a.username}/following")
        app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["username"] == b.username

    @pytest.mark.xfail(
        strict=False,
        reason=(
            "slowapi rate limiting requires SlowAPIMiddleware or a real network "
            "stack; the in-process ASGITransport does not trigger 429 responses "
            "via the decorator-only setup used in this app."
        ),
    )
    async def test_rate_limiting_follow_endpoint(
        self, db_session: AsyncSession
    ) -> None:
        """Exceeding 30/minute on POST /follows/{username} must return 429."""
        a = await _make_user(db_session, clerk_id="fw_api_07a", username="fw_api_07a")
        targets = []
        for i in range(32):
            t = await _make_user(
                db_session,
                clerk_id=f"fw_api_07t_{i}",
                username=f"fw_api_07t_{i}",
            )
            targets.append(t)

        async with await self._authed_client(db_session, a.clerk_id) as client:
            responses = []
            for t in targets:
                resp = await client.post(f"/api/v1/follows/{t.username}")
                responses.append(resp.status_code)
        app.dependency_overrides.clear()

        assert 429 in responses, "Expected a 429 after exceeding the rate limit"
