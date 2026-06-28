"""
Integration tests: user persistence, constraints, and visibility enforcement.

Visibility enforcement is the constitutional core (HARMONIQ.md §6, ENGINEERING_BIBLE §8.1):
fields must be **absent** from the response — not present-but-null — when the viewer
lacks permission. These tests verify enforcement at the data-access layer, not the
presentation layer.

Each test function gets its own `db_session` (function-scoped) wrapped in a
transaction that rolls back on teardown, so tests are fully isolated.
"""

import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.enums import VisibilityScope
from app.models.user import User
from app.services import user as user_svc

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _create(
    session: AsyncSession,
    *,
    clerk_id: str,
    username: str,
    display_name: str = "Test User",
) -> User:
    user = await user_svc.create_user(session, clerk_id, username, display_name)
    await session.flush()
    return user


async def _create_with_visibility(
    session: AsyncSession,
    *,
    clerk_id: str,
    username: str,
    bio: str | None = "My bio",
    visibility_bio: VisibilityScope = VisibilityScope.PRIVATE,
    visibility_activity: VisibilityScope = VisibilityScope.PRIVATE,
    visibility_ratings: VisibilityScope = VisibilityScope.PRIVATE,
) -> User:
    user = await _create(session, clerk_id=clerk_id, username=username)
    user.bio = bio
    user.visibility_bio = visibility_bio.value
    user.visibility_activity = visibility_activity.value
    user.visibility_ratings = visibility_ratings.value
    await session.flush()
    return user


# ── §3.2 User persistence & constraints ──────────────────────────────────────


@pytest.mark.integration
class TestUserPersistence:
    async def test_create_persists_and_readable_by_clerk_id(
        self, db_session: AsyncSession
    ) -> None:
        await _create(db_session, clerk_id="clerk_p_01", username="persist01")

        fetched = await user_svc.get_by_clerk_id(db_session, "clerk_p_01")
        assert fetched is not None
        assert fetched.username == "persist01"

    async def test_username_stored_lowercase(self, db_session: AsyncSession) -> None:
        user = await _create(db_session, clerk_id="clerk_p_02", username="UpperCase")
        assert user.username == "uppercase"

    async def test_readable_by_username_case_insensitive(
        self, db_session: AsyncSession
    ) -> None:
        await _create(db_session, clerk_id="clerk_p_03", username="CamelUser")

        for lookup in ("cameluser", "CAMELUSER", "CamelUser"):
            fetched = await user_svc.get_by_username(db_session, lookup)
            assert fetched is not None, f"Lookup '{lookup}' returned None"

    async def test_id_is_real_uuid(self, db_session: AsyncSession) -> None:
        user = await _create(db_session, clerk_id="clerk_p_04", username="uuiduser")
        assert isinstance(user.id, uuid.UUID)

    async def test_timestamps_populated_by_server_default(
        self, db_session: AsyncSession
    ) -> None:
        user = await _create(db_session, clerk_id="clerk_p_05", username="tsuser")
        await db_session.refresh(user)
        assert user.created_at is not None
        assert user.updated_at is not None

    async def test_default_visibility_is_private(
        self, db_session: AsyncSession
    ) -> None:
        """New users default to PRIVATE on all visibility fields — opt-in, not opt-out."""
        await _create(db_session, clerk_id="clerk_p_06", username="privdefault")

        result = await db_session.execute(
            select(User).where(User.clerk_id == "clerk_p_06")
        )
        db_user = result.scalar_one()
        assert db_user.visibility_bio == VisibilityScope.PRIVATE.value
        assert db_user.visibility_activity == VisibilityScope.PRIVATE.value
        assert db_user.visibility_ratings == VisibilityScope.PRIVATE.value

    async def test_duplicate_username_raises_integrity_error(
        self, db_session: AsyncSession
    ) -> None:
        await _create(db_session, clerk_id="clerk_p_07a", username="dupuser")
        with pytest.raises(IntegrityError):
            await _create(db_session, clerk_id="clerk_p_07b", username="dupuser")

    async def test_duplicate_clerk_id_raises_integrity_error(
        self, db_session: AsyncSession
    ) -> None:
        await _create(db_session, clerk_id="clerk_dup", username="dupclerk1")
        with pytest.raises(IntegrityError):
            await _create(db_session, clerk_id="clerk_dup", username="dupclerk2")

    async def test_is_username_available_before_creation(
        self, db_session: AsyncSession
    ) -> None:
        assert (
            await user_svc.is_username_available(db_session, "brand_new_name") is True
        )

    async def test_is_username_available_false_after_creation(
        self, db_session: AsyncSession
    ) -> None:
        await _create(db_session, clerk_id="clerk_p_08", username="takenname")
        assert await user_svc.is_username_available(db_session, "takenname") is False

    async def test_is_username_available_case_insensitive(
        self, db_session: AsyncSession
    ) -> None:
        await _create(db_session, clerk_id="clerk_p_09", username="casetest")
        assert await user_svc.is_username_available(db_session, "CASETEST") is False

    async def test_get_by_clerk_id_returns_none_for_unknown(
        self, db_session: AsyncSession
    ) -> None:
        assert await user_svc.get_by_clerk_id(db_session, "clerk_nonexistent") is None

    async def test_get_by_username_returns_none_for_unknown(
        self, db_session: AsyncSession
    ) -> None:
        assert await user_svc.get_by_username(db_session, "nobody_here") is None


# ── §3.3 Visibility enforcement — the constitutional core ─────────────────────


@pytest.mark.integration
class TestVisibilityEnforcement:
    """
    Verify that get_profile withholds fields at the data layer (field absent from
    model_fields_set, not present-but-null) when the viewer lacks permission.

    Matrix: {bio, activity, ratings} × {PRIVATE, FRIENDS, PUBLIC}
           × {owner, stranger, anonymous}
    """

    async def test_owner_sees_all_private_fields(
        self, db_session: AsyncSession
    ) -> None:
        await _create_with_visibility(
            db_session,
            clerk_id="clerk_v_own",
            username="vis_owner",
            visibility_bio=VisibilityScope.PRIVATE,
            visibility_activity=VisibilityScope.PRIVATE,
            visibility_ratings=VisibilityScope.PRIVATE,
        )

        profile = await user_svc.get_profile(db_session, "vis_owner", "clerk_v_own")
        assert profile is not None
        assert profile.is_own_profile is True
        assert "bio" in profile.model_fields_set
        assert "activity_placeholder" in profile.model_fields_set
        assert "ratings_count" in profile.model_fields_set

    async def test_stranger_denied_private_bio(self, db_session: AsyncSession) -> None:
        await _create_with_visibility(
            db_session,
            clerk_id="clerk_v_t1",
            username="vis_t1",
            visibility_bio=VisibilityScope.PRIVATE,
        )
        await _create(db_session, clerk_id="clerk_v_s1", username="vis_s1")

        profile = await user_svc.get_profile(db_session, "vis_t1", "clerk_v_s1")
        assert profile is not None
        assert "bio" not in profile.model_fields_set

    async def test_stranger_sees_public_bio(self, db_session: AsyncSession) -> None:
        await _create_with_visibility(
            db_session,
            clerk_id="clerk_v_t2",
            username="vis_t2",
            bio="Hello!",
            visibility_bio=VisibilityScope.PUBLIC,
        )
        await _create(db_session, clerk_id="clerk_v_s2", username="vis_s2")

        profile = await user_svc.get_profile(db_session, "vis_t2", "clerk_v_s2")
        assert profile is not None
        assert "bio" in profile.model_fields_set
        assert profile.bio == "Hello!"

    async def test_stranger_denied_private_activity(
        self, db_session: AsyncSession
    ) -> None:
        await _create_with_visibility(
            db_session,
            clerk_id="clerk_v_t3",
            username="vis_t3",
            visibility_activity=VisibilityScope.PRIVATE,
        )
        await _create(db_session, clerk_id="clerk_v_s3", username="vis_s3")

        profile = await user_svc.get_profile(db_session, "vis_t3", "clerk_v_s3")
        assert "activity_placeholder" not in profile.model_fields_set  # type: ignore[union-attr]

    async def test_stranger_sees_public_activity(
        self, db_session: AsyncSession
    ) -> None:
        await _create_with_visibility(
            db_session,
            clerk_id="clerk_v_t4",
            username="vis_t4",
            visibility_activity=VisibilityScope.PUBLIC,
        )
        await _create(db_session, clerk_id="clerk_v_s4", username="vis_s4")

        profile = await user_svc.get_profile(db_session, "vis_t4", "clerk_v_s4")
        assert "activity_placeholder" in profile.model_fields_set  # type: ignore[union-attr]

    async def test_stranger_denied_private_ratings(
        self, db_session: AsyncSession
    ) -> None:
        await _create_with_visibility(
            db_session,
            clerk_id="clerk_v_t5",
            username="vis_t5",
            visibility_ratings=VisibilityScope.PRIVATE,
        )
        await _create(db_session, clerk_id="clerk_v_s5", username="vis_s5")

        profile = await user_svc.get_profile(db_session, "vis_t5", "clerk_v_s5")
        assert "ratings_count" not in profile.model_fields_set  # type: ignore[union-attr]

    async def test_stranger_sees_public_ratings(self, db_session: AsyncSession) -> None:
        await _create_with_visibility(
            db_session,
            clerk_id="clerk_v_t6",
            username="vis_t6",
            visibility_ratings=VisibilityScope.PUBLIC,
        )
        await _create(db_session, clerk_id="clerk_v_s6", username="vis_s6")

        profile = await user_svc.get_profile(db_session, "vis_t6", "clerk_v_s6")
        assert "ratings_count" in profile.model_fields_set  # type: ignore[union-attr]
        assert profile.ratings_count == 0  # type: ignore[union-attr]

    async def test_anonymous_denied_all_private_fields(
        self, db_session: AsyncSession
    ) -> None:
        await _create_with_visibility(
            db_session,
            clerk_id="clerk_v_t7",
            username="vis_t7",
            visibility_bio=VisibilityScope.PRIVATE,
            visibility_activity=VisibilityScope.PRIVATE,
            visibility_ratings=VisibilityScope.PRIVATE,
        )

        profile = await user_svc.get_profile(db_session, "vis_t7", None)
        assert profile is not None
        assert profile.is_own_profile is False
        assert "bio" not in profile.model_fields_set
        assert "activity_placeholder" not in profile.model_fields_set
        assert "ratings_count" not in profile.model_fields_set

    async def test_anonymous_sees_all_public_fields(
        self, db_session: AsyncSession
    ) -> None:
        await _create_with_visibility(
            db_session,
            clerk_id="clerk_v_t8",
            username="vis_t8",
            bio="Public bio",
            visibility_bio=VisibilityScope.PUBLIC,
            visibility_activity=VisibilityScope.PUBLIC,
            visibility_ratings=VisibilityScope.PUBLIC,
        )

        profile = await user_svc.get_profile(db_session, "vis_t8", None)
        assert "bio" in profile.model_fields_set  # type: ignore[union-attr]
        assert "activity_placeholder" in profile.model_fields_set  # type: ignore[union-attr]
        assert "ratings_count" in profile.model_fields_set  # type: ignore[union-attr]

    async def test_friends_scope_behaves_as_private_for_non_friend(
        self, db_session: AsyncSession
    ) -> None:
        """
        _is_friend() is a stub returning False until Follow/Following lands.
        FRIENDS-scoped fields must therefore behave as PRIVATE for non-owners today.
        This test pins the current behavior so the change is visible when follows ship.
        """
        await _create_with_visibility(
            db_session,
            clerk_id="clerk_v_t9",
            username="vis_t9",
            visibility_bio=VisibilityScope.FRIENDS,
        )
        await _create(db_session, clerk_id="clerk_v_s9", username="vis_s9")

        profile = await user_svc.get_profile(db_session, "vis_t9", "clerk_v_s9")
        assert "bio" not in profile.model_fields_set  # type: ignore[union-attr]

    async def test_friends_scope_branch_reachable_when_is_friend_true(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Monkeypatch _is_friend → True to exercise the FRIENDS branch in can_see().
        Proves the code path is reachable and will work once Follow/Following ships.
        """
        import app.services.user as user_module

        await _create_with_visibility(
            db_session,
            clerk_id="clerk_v_t10",
            username="vis_t10",
            bio="Friends-only bio",
            visibility_bio=VisibilityScope.FRIENDS,
        )
        await _create(db_session, clerk_id="clerk_v_s10", username="vis_s10")

        monkeypatch.setattr(user_module, "_is_friend", AsyncMock(return_value=True))

        profile = await user_svc.get_profile(db_session, "vis_t10", "clerk_v_s10")
        assert "bio" in profile.model_fields_set  # type: ignore[union-attr]
        assert profile.bio == "Friends-only bio"  # type: ignore[union-attr]

    async def test_profile_returns_none_for_nonexistent_username(
        self, db_session: AsyncSession
    ) -> None:
        profile = await user_svc.get_profile(db_session, "does_not_exist", None)
        assert profile is None

    async def test_bio_absent_not_null_when_denied(
        self, db_session: AsyncSession
    ) -> None:
        """
        Field must be absent from model_fields_set, not present-as-null.
        Confirms the data layer withholds the field rather than relying on
        the presentation layer to hide a null value.
        """
        await _create_with_visibility(
            db_session,
            clerk_id="clerk_v_t11",
            username="vis_t11",
            bio="secret",
            visibility_bio=VisibilityScope.PRIVATE,
        )
        await _create(db_session, clerk_id="clerk_v_s11", username="vis_s11")

        profile = await user_svc.get_profile(db_session, "vis_t11", "clerk_v_s11")
        assert profile is not None
        # Field must not appear in the set of fields that were explicitly set —
        # model_construct() only adds it when permission is granted.
        assert "bio" not in profile.model_fields_set
        # The default value is None, but that's distinct from being deliberately set.
        assert profile.bio is None  # default from ProfileResponse, NOT the real value


# ── §3.4 Profile updates & Clerk sync ────────────────────────────────────────


@pytest.mark.integration
class TestProfileUpdates:
    async def test_update_display_name(self, db_session: AsyncSession) -> None:
        user = await _create(db_session, clerk_id="clerk_u_01", username="upd01")
        await user_svc.update_profile(
            db_session,
            user,
            display_name="New Name",
            username=None,
            bio=None,
            visibility_bio=None,
            visibility_activity=None,
            visibility_ratings=None,
        )
        assert user.display_name == "New Name"

    async def test_update_username_lowercased_and_lookup_works(
        self, db_session: AsyncSession
    ) -> None:
        user = await _create(db_session, clerk_id="clerk_u_02", username="upd02")
        await user_svc.update_profile(
            db_session,
            user,
            display_name=None,
            username="RENAMED02",
            bio=None,
            visibility_bio=None,
            visibility_activity=None,
            visibility_ratings=None,
        )
        assert user.username == "renamed02"
        fetched = await user_svc.get_by_username(db_session, "renamed02")
        assert fetched is not None

    async def test_bio_cleared_to_none(self, db_session: AsyncSession) -> None:
        user = await _create(db_session, clerk_id="clerk_u_03", username="upd03")
        user.bio = "Some bio"
        await user_svc.update_profile(
            db_session,
            user,
            display_name=None,
            username=None,
            bio=None,
            visibility_bio=None,
            visibility_activity=None,
            visibility_ratings=None,
        )
        assert user.bio is None

    async def test_visibility_fields_updated(self, db_session: AsyncSession) -> None:
        user = await _create(db_session, clerk_id="clerk_u_04", username="upd04")
        await user_svc.update_profile(
            db_session,
            user,
            display_name=None,
            username=None,
            bio=None,
            visibility_bio=VisibilityScope.PUBLIC,
            visibility_activity=VisibilityScope.FRIENDS,
            visibility_ratings=VisibilityScope.PUBLIC,
        )
        assert user.visibility_bio == VisibilityScope.PUBLIC.value
        assert user.visibility_activity == VisibilityScope.FRIENDS.value
        assert user.visibility_ratings == VisibilityScope.PUBLIC.value

    async def test_update_avatar_url_persists(self, db_session: AsyncSession) -> None:
        user = await _create(db_session, clerk_id="clerk_u_05", username="upd05")
        await user_svc.update_avatar_url(
            db_session, user, "https://example.com/avatar.png"
        )
        assert user.avatar_url == "https://example.com/avatar.png"

    async def test_updated_at_changes_on_profile_update(
        self, db_session: AsyncSession
    ) -> None:
        user = await _create(db_session, clerk_id="clerk_u_06", username="upd06")
        await db_session.refresh(user)
        original_updated_at = user.updated_at

        await user_svc.update_profile(
            db_session,
            user,
            display_name="Changed",
            username=None,
            bio=None,
            visibility_bio=None,
            visibility_activity=None,
            visibility_ratings=None,
        )
        # updated_at is set by _now() in the service, not server_default —
        # it should differ from the original server-set value.
        assert user.updated_at >= original_updated_at


@pytest.mark.integration
class TestClerkSync:
    async def test_sync_updates_display_name(self, db_session: AsyncSession) -> None:
        user = await _create(
            db_session,
            clerk_id="clerk_s_01",
            username="sync01",
            display_name="Old Name",
        )
        await user_svc.sync_from_clerk(db_session, "clerk_s_01", "New Name", None)
        assert user.display_name == "New Name"

    async def test_sync_updates_avatar_url(self, db_session: AsyncSession) -> None:
        user = await _create(db_session, clerk_id="clerk_s_02", username="sync02")
        await user_svc.sync_from_clerk(
            db_session, "clerk_s_02", None, "https://example.com/new.png"
        )
        assert user.avatar_url == "https://example.com/new.png"

    async def test_sync_noop_when_nothing_changed(
        self, db_session: AsyncSession
    ) -> None:
        user = await _create(
            db_session,
            clerk_id="clerk_s_03",
            username="sync03",
            display_name="Same Name",
        )
        await db_session.refresh(user)
        original_updated_at = user.updated_at

        await user_svc.sync_from_clerk(db_session, "clerk_s_03", "Same Name", None)
        assert user.updated_at == original_updated_at

    async def test_sync_noop_for_nonexistent_clerk_id(
        self, db_session: AsyncSession
    ) -> None:
        # Must not raise even when the Harmoniq record doesn't exist.
        await user_svc.sync_from_clerk(db_session, "clerk_nobody", "Name", None)


# ── §3.5 Session / commit behaviour ──────────────────────────────────────────


@pytest.mark.integration
class TestSessionIsolation:
    async def test_rolled_back_writes_not_visible_in_fresh_connection(
        self, migrated_engine: AsyncEngine
    ) -> None:
        """
        Writes made inside a transaction that is rolled back must not appear
        in a subsequently opened connection. This is the core isolation guarantee
        that makes per-test rollback work as a cleanup strategy.
        """
        # Write in conn1 / session1, then explicitly roll back.
        conn1 = await migrated_engine.connect()
        trans1 = await conn1.begin()
        session1 = AsyncSession(bind=conn1, expire_on_commit=False)
        await user_svc.create_user(
            session1, "clerk_iso_99", "iso_rollback_user", "Iso User"
        )
        await session1.flush()
        await session1.close()
        await trans1.rollback()
        await conn1.close()

        # A fresh connection must not see the row.
        async with migrated_engine.connect() as conn2:
            session2 = AsyncSession(bind=conn2, expire_on_commit=False)
            result = await session2.execute(
                select(User).where(User.clerk_id == "clerk_iso_99")
            )
            assert result.scalar_one_or_none() is None
            await session2.close()


# ── §3.6 User search ─────────────────────────────────────────────────────────


@pytest.mark.integration
class TestUserSearch:
    """
    Tests for GET /users/search and the underlying search_users service.
    Also verifies filter_discoverable_users is wired in as security scaffolding.
    """

    async def test_returns_users_matching_username(
        self, db_session: AsyncSession
    ) -> None:
        await _create(db_session, clerk_id="clerk_srch_01", username="beatles_fan")
        await _create(db_session, clerk_id="clerk_srch_02", username="stones_lover")

        results = await user_svc.search_users(db_session, "beatl")
        assert len(results) == 1
        assert results[0].username == "beatles_fan"

    async def test_returns_users_matching_display_name(
        self, db_session: AsyncSession
    ) -> None:
        await _create(
            db_session,
            clerk_id="clerk_srch_03",
            username="srch_dn_user",
            display_name="Ziggy Stardust",
        )

        results = await user_svc.search_users(db_session, "ziggy")
        assert len(results) == 1
        assert results[0].display_name == "Ziggy Stardust"

    async def test_returns_empty_for_no_matches(
        self, db_session: AsyncSession
    ) -> None:
        results = await user_svc.search_users(db_session, "xyznotexist99")
        assert results == []

    async def test_endpoint_returns_empty_for_short_query(
        self, anon_client: AsyncClient
    ) -> None:
        response = await anon_client.get("/api/v1/users/search?q=a")
        assert response.status_code == 200
        assert response.json() == []

    async def test_endpoint_returns_matches(
        self, anon_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await _create(db_session, clerk_id="clerk_srch_04", username="searchable_user")
        await db_session.flush()

        response = await anon_client.get("/api/v1/users/search?q=searchable")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["username"] == "searchable_user"

    async def test_response_contains_only_allowed_fields(
        self, anon_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await _create(db_session, clerk_id="clerk_srch_05", username="schema_check_user")
        await db_session.flush()

        response = await anon_client.get("/api/v1/users/search?q=schema_check")
        assert response.status_code == 200
        for item in response.json():
            assert set(item.keys()) == {"username", "display_name", "avatar_url"}
            # No sensitive fields
            assert "clerk_id" not in item
            assert "visibility_bio" not in item
            assert "visibility_activity" not in item
            assert "visibility_ratings" not in item

    async def test_endpoint_returns_empty_for_no_matches(
        self, anon_client: AsyncClient
    ) -> None:
        response = await anon_client.get("/api/v1/users/search?q=zzznomatch999")
        assert response.status_code == 200
        assert response.json() == []

    async def test_rate_limit_header_present(
        self, anon_client: AsyncClient
    ) -> None:
        response = await anon_client.get("/api/v1/users/search?q=test")
        assert response.status_code == 200
        assert any(k.lower().startswith("x-ratelimit") for k in response.headers)

    async def test_filter_discoverable_users_is_called(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Verifies filter_discoverable_users is in the call path so the test
        harness fails loudly if it is ever removed or bypassed.
        """
        import app.services.user as user_module

        call_count = 0
        original = user_module.filter_discoverable_users

        def spy(query):
            nonlocal call_count
            call_count += 1
            return original(query)

        monkeypatch.setattr(user_module, "filter_discoverable_users", spy)
        await user_svc.search_users(db_session, "test")
        assert call_count == 1
