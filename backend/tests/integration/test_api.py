"""
Integration tests: API-level happy and error paths through the ASGI client.

Auth dependencies are overridden via fixture (`authed_client`, `anon_client`).
No real Clerk JWTs are minted; no live MusicBrainz calls are made.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import VisibilityScope
from app.services import user as user_svc

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _create_user(
    session: AsyncSession,
    *,
    clerk_id: str,
    username: str,
    display_name: str = "Test User",
    bio: str | None = None,
    visibility_bio: VisibilityScope = VisibilityScope.PRIVATE,
    visibility_activity: VisibilityScope = VisibilityScope.PRIVATE,
    visibility_ratings: VisibilityScope = VisibilityScope.PRIVATE,
) -> None:
    user = await user_svc.create_user(session, clerk_id, username, display_name)
    user.bio = bio
    user.visibility_bio = visibility_bio.value
    user.visibility_activity = visibility_activity.value
    user.visibility_ratings = visibility_ratings.value
    await session.flush()


# ── §3.7 Profile retrieval ────────────────────────────────────────────────────


@pytest.mark.integration
class TestGetProfileEndpoint:
    async def test_public_profile_returns_200(
        self, anon_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await _create_user(
            db_session,
            clerk_id="clerk_api_01",
            username="api_public",
            bio="Hello world",
            visibility_bio=VisibilityScope.PUBLIC,
        )

        resp = await anon_client.get("/api/v1/users/api_public")
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "api_public"

    async def test_nonexistent_username_returns_404(
        self, anon_client: AsyncClient
    ) -> None:
        resp = await anon_client.get("/api/v1/users/definitely_does_not_exist_xyz")
        assert resp.status_code == 404

    async def test_anonymous_cannot_see_private_bio_in_response(
        self, anon_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await _create_user(
            db_session,
            clerk_id="clerk_api_02",
            username="api_private_bio",
            bio="Secret",
            visibility_bio=VisibilityScope.PRIVATE,
        )

        resp = await anon_client.get("/api/v1/users/api_private_bio")
        assert resp.status_code == 200
        body = resp.json()
        # response_model_exclude_unset=True means absent field is absent, not null.
        assert "bio" not in body

    async def test_public_bio_appears_in_response(
        self, anon_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await _create_user(
            db_session,
            clerk_id="clerk_api_03",
            username="api_public_bio",
            bio="I am public",
            visibility_bio=VisibilityScope.PUBLIC,
        )

        resp = await anon_client.get("/api/v1/users/api_public_bio")
        assert resp.status_code == 200
        assert resp.json()["bio"] == "I am public"

    async def test_own_profile_is_flagged_correctly(
        self, authed_client: tuple[AsyncClient, str], db_session: AsyncSession
    ) -> None:
        ac, clerk_id = authed_client
        await _create_user(db_session, clerk_id=clerk_id, username="api_selfview")

        resp = await ac.get("/api/v1/users/api_selfview")
        assert resp.status_code == 200
        assert resp.json()["is_own_profile"] is True

    async def test_stranger_profile_is_not_own(
        self, authed_client: tuple[AsyncClient, str], db_session: AsyncSession
    ) -> None:
        ac, clerk_id = authed_client
        await _create_user(db_session, clerk_id=clerk_id, username="api_viewer_s")
        await _create_user(
            db_session, clerk_id="clerk_other_api", username="api_other_s"
        )

        resp = await ac.get("/api/v1/users/api_other_s")
        assert resp.status_code == 200
        assert resp.json()["is_own_profile"] is False


# ── §3.7 Own profile endpoint (GET /me) ──────────────────────────────────────


@pytest.mark.integration
class TestGetOwnProfileEndpoint:
    async def test_get_me_returns_own_profile(
        self, authed_client: tuple[AsyncClient, str], db_session: AsyncSession
    ) -> None:
        ac, clerk_id = authed_client
        await _create_user(
            db_session,
            clerk_id=clerk_id,
            username="api_me_user",
            display_name="Me User",
        )

        resp = await ac.get("/api/v1/users/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "api_me_user"
        assert body["display_name"] == "Me User"
        # OwnProfileResponse always includes visibility fields
        assert "visibility_bio" in body

    async def test_get_me_returns_404_when_not_onboarded(
        self, authed_client: tuple[AsyncClient, str]
    ) -> None:
        """If the authed user has no Harmoniq record, /me returns 404."""
        ac, _ = authed_client
        # No user record created for this clerk_id.
        resp = await ac.get("/api/v1/users/me")
        assert resp.status_code == 404


# ── §3.7 Username availability check ─────────────────────────────────────────


@pytest.mark.integration
class TestUsernameCheckEndpoint:
    async def test_available_username_returns_true(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/users/check-username", params={"q": "available_name_xyz"}
        )
        assert resp.status_code == 200
        assert resp.json()["available"] is True

    async def test_taken_username_returns_false(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await _create_user(db_session, clerk_id="clerk_check_01", username="takencheck")

        resp = await client.get(
            "/api/v1/users/check-username", params={"q": "takencheck"}
        )
        assert resp.status_code == 200
        assert resp.json()["available"] is False

    async def test_invalid_format_returns_unavailable(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(
            "/api/v1/users/check-username", params={"q": "bad user!"}
        )
        assert resp.status_code == 200
        assert resp.json()["available"] is False

    async def test_reserved_username_returns_unavailable(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/api/v1/users/check-username", params={"q": "admin"})
        assert resp.status_code == 200
        assert resp.json()["available"] is False


# ── §3.7 Catalog search (mocked MB) ──────────────────────────────────────────


@pytest.mark.integration
class TestCatalogSearchEndpoint:
    async def test_search_returns_structured_response(
        self, client: AsyncClient
    ) -> None:
        mock_artist = {
            "id": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
            "name": "Radiohead",
            "sort-name": "Radiohead",
            "disambiguation": None,
        }
        with (
            patch(
                "app.services.catalog.mb.search_artists",
                new=AsyncMock(return_value=[mock_artist]),
            ),
            patch(
                "app.services.catalog.mb.search_release_groups",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.catalog.mb.search_recordings",
                new=AsyncMock(return_value=[]),
            ),
        ):
            resp = await client.get(
                "/api/v1/catalog/search",
                params={"q": "radiohead_api_test_q1"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert "artists" in body
        assert "albums" in body
        assert "tracks" in body
        assert body["artists"][0]["name"] == "Radiohead"

    async def test_search_query_too_short_returns_422(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/api/v1/catalog/search", params={"q": "a"})
        assert resp.status_code == 422

    async def test_catalog_artist_not_found_returns_404(
        self, client: AsyncClient
    ) -> None:
        with patch(
            "app.services.catalog.mb.lookup_artist",
            new=AsyncMock(return_value=None),
        ):
            resp = await client.get(
                "/api/v1/catalog/artists/00000000-0000-0000-0000-000000000000"
            )
        assert resp.status_code == 404

    async def test_catalog_album_not_found_returns_404(
        self, client: AsyncClient
    ) -> None:
        with patch(
            "app.services.catalog.mb.lookup_release_group",
            new=AsyncMock(return_value=None),
        ):
            resp = await client.get(
                "/api/v1/catalog/albums/00000000-0000-0000-0000-000000000000"
            )
        assert resp.status_code == 404
