"""
Integration tests: Spotify connection persistence (encrypted at rest),
callback state validation, disconnect, and listening visibility enforcement.

External Spotify HTTP calls are monkeypatched — these tests exercise the
database and visibility layers, not Spotify itself.
"""

from typing import Any

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.crypto import decrypt_token
from app.core.enums import VisibilityScope
from app.models.spotify import SpotifyConnection
from app.models.user import User
from app.services import follow as follow_svc
from app.services import spotify as spotify_svc
from app.services import user as user_svc

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_user(
    session: AsyncSession,
    *,
    clerk_id: str,
    username: str,
) -> User:
    user = await user_svc.create_user(session, clerk_id, username, "Test User")
    await session.flush()
    return user


@pytest.fixture(autouse=True)
def spotify_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "spotify_client_id", "client-id")
    monkeypatch.setattr(settings, "spotify_client_secret", "client-secret")
    monkeypatch.setattr(
        settings, "spotify_redirect_uri", "http://127.0.0.1:3000/spotify-callback"
    )
    monkeypatch.setattr(
        settings, "token_encryption_key", Fernet.generate_key().decode()
    )
    spotify_svc._access_tokens.clear()
    spotify_svc._listening_cache.clear()


def _mock_exchange(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_exchange(code: str) -> dict[str, Any]:
        assert code == "auth-code"
        return {
            "access_token": "access-token",
            "refresh_token": "refresh-token-plaintext",
            "expires_in": 3600,
            "scope": spotify_svc.SCOPES,
        }

    async def _fake_profile(access_token: str) -> str:
        return "spotify-user-42"

    monkeypatch.setattr(spotify_svc, "_exchange_code", _fake_exchange)
    monkeypatch.setattr(spotify_svc, "_fetch_spotify_profile", _fake_profile)


# ── Connection lifecycle ──────────────────────────────────────────────────────


@pytest.mark.integration
class TestSpotifyConnectionAPI:
    async def test_connect_url_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/spotify/connect-url")
        assert resp.status_code in (401, 403)

    async def test_connect_url_returns_authorize_url(
        self, authed_client: tuple[AsyncClient, str], db_session: AsyncSession
    ) -> None:
        ac, clerk_id = authed_client
        await _make_user(db_session, clerk_id=clerk_id, username="sp_u1")

        resp = await ac.get("/api/v1/spotify/connect-url")

        assert resp.status_code == 200
        assert resp.json()["url"].startswith("https://accounts.spotify.com/authorize")

    async def test_callback_invalid_state_returns_400(
        self, authed_client: tuple[AsyncClient, str], db_session: AsyncSession
    ) -> None:
        ac, clerk_id = authed_client
        await _make_user(db_session, clerk_id=clerk_id, username="sp_u2")

        resp = await ac.post(
            "/api/v1/spotify/callback",
            json={"code": "auth-code", "state": "tampered.state"},
        )

        assert resp.status_code == 400

    async def test_callback_happy_path_stores_encrypted_token(
        self,
        authed_client: tuple[AsyncClient, str],
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ac, clerk_id = authed_client
        user = await _make_user(db_session, clerk_id=clerk_id, username="sp_u3")
        _mock_exchange(monkeypatch)
        state = spotify_svc.create_state(user.id)

        resp = await ac.post(
            "/api/v1/spotify/callback",
            json={"code": "auth-code", "state": state},
        )

        assert resp.status_code == 200
        assert resp.json()["connected"] is True
        assert resp.json()["spotify_user_id"] == "spotify-user-42"

        row = (
            await db_session.execute(
                select(SpotifyConnection).where(SpotifyConnection.user_id == user.id)
            )
        ).scalar_one()
        assert row.refresh_token_encrypted != "refresh-token-plaintext"
        assert row.refresh_token_encrypted.startswith("gAAAA")
        assert decrypt_token(row.refresh_token_encrypted) == "refresh-token-plaintext"

    async def test_callback_state_for_other_user_rejected(
        self,
        authed_client: tuple[AsyncClient, str],
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ac, clerk_id = authed_client
        await _make_user(db_session, clerk_id=clerk_id, username="sp_u4")
        other = await _make_user(
            db_session, clerk_id="clerk_sp_other", username="sp_u4o"
        )
        _mock_exchange(monkeypatch)
        state_for_other = spotify_svc.create_state(other.id)

        resp = await ac.post(
            "/api/v1/spotify/callback",
            json={"code": "auth-code", "state": state_for_other},
        )

        assert resp.status_code == 400

    async def test_reconnect_replaces_existing_row(
        self,
        authed_client: tuple[AsyncClient, str],
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ac, clerk_id = authed_client
        user = await _make_user(db_session, clerk_id=clerk_id, username="sp_u5")
        _mock_exchange(monkeypatch)

        for _ in range(2):
            state = spotify_svc.create_state(user.id)
            resp = await ac.post(
                "/api/v1/spotify/callback",
                json={"code": "auth-code", "state": state},
            )
            assert resp.status_code == 200

        rows = (
            (
                await db_session.execute(
                    select(SpotifyConnection).where(
                        SpotifyConnection.user_id == user.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1

    async def test_status_and_disconnect(
        self,
        authed_client: tuple[AsyncClient, str],
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ac, clerk_id = authed_client
        user = await _make_user(db_session, clerk_id=clerk_id, username="sp_u6")

        before = await ac.get("/api/v1/spotify/connection")
        assert before.json()["connected"] is False

        _mock_exchange(monkeypatch)
        state = spotify_svc.create_state(user.id)
        await ac.post(
            "/api/v1/spotify/callback", json={"code": "auth-code", "state": state}
        )

        connected = await ac.get("/api/v1/spotify/connection")
        assert connected.json()["connected"] is True

        gone = await ac.delete("/api/v1/spotify/connection")
        assert gone.status_code == 204

        after = await ac.get("/api/v1/spotify/connection")
        assert after.json()["connected"] is False


# ── Listening visibility enforcement ──────────────────────────────────────────


@pytest.mark.integration
class TestListeningVisibility:
    """visibility_activity gates listening at the service layer (EB §8.1)."""

    @staticmethod
    def _mock_payload(monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_payload(
            session: AsyncSession, conn: SpotifyConnection
        ) -> dict[str, Any]:
            return {
                "now": None,
                "recent": [
                    {
                        "track": {
                            "type": "track",
                            "name": "Recent Song",
                            "artists": [{"name": "Artist"}],
                            "album": {"name": "Album", "images": []},
                            "external_urls": {},
                        },
                        "played_at": "2026-07-04T10:00:00Z",
                    }
                ],
            }

        monkeypatch.setattr(spotify_svc, "_fetch_listening_payload", _fake_payload)

    async def _connect(self, db_session: AsyncSession, user: User) -> None:
        db_session.add(
            SpotifyConnection(
                user_id=user.id,
                spotify_user_id="spotify-user",
                refresh_token_encrypted="unused-in-these-tests",
                scopes=spotify_svc.SCOPES,
            )
        )
        await db_session.flush()

    async def test_owner_always_sees_own_listening(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        owner = await _make_user(db_session, clerk_id="sp_vis_01", username="sp_vis_01")
        # visibility_activity defaults to private — owner must still see it.
        await self._connect(db_session, owner)
        self._mock_payload(monkeypatch)

        result = await spotify_svc.get_listening(db_session, owner, viewer=owner)

        assert result is not None
        assert result.connected is True
        assert result.recently_played[0].track_name == "Recent Song"

    async def test_private_hidden_from_stranger_and_anonymous(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        owner = await _make_user(
            db_session, clerk_id="sp_vis_02o", username="sp_vis_02o"
        )
        stranger = await _make_user(
            db_session, clerk_id="sp_vis_02s", username="sp_vis_02s"
        )
        await self._connect(db_session, owner)
        self._mock_payload(monkeypatch)

        assert (
            await spotify_svc.get_listening(db_session, owner, viewer=stranger) is None
        )
        assert await spotify_svc.get_listening(db_session, owner, viewer=None) is None

    async def test_public_visible_to_anonymous(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        owner = await _make_user(db_session, clerk_id="sp_vis_03", username="sp_vis_03")
        owner.visibility_activity = VisibilityScope.PUBLIC.value
        await self._connect(db_session, owner)
        self._mock_payload(monkeypatch)

        result = await spotify_svc.get_listening(db_session, owner, viewer=None)

        assert result is not None
        assert result.connected is True

    async def test_friends_scope_allows_mutual_follow_only(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        owner = await _make_user(
            db_session, clerk_id="sp_vis_04o", username="sp_vis_04o"
        )
        friend = await _make_user(
            db_session, clerk_id="sp_vis_04f", username="sp_vis_04f"
        )
        stranger = await _make_user(
            db_session, clerk_id="sp_vis_04s", username="sp_vis_04s"
        )
        owner.visibility_activity = VisibilityScope.FRIENDS.value
        await follow_svc.follow(db_session, owner.id, friend.id)
        await follow_svc.follow(db_session, friend.id, owner.id)
        await self._connect(db_session, owner)
        self._mock_payload(monkeypatch)

        assert (
            await spotify_svc.get_listening(db_session, owner, viewer=friend)
            is not None
        )
        assert (
            await spotify_svc.get_listening(db_session, owner, viewer=stranger) is None
        )

    async def test_visible_but_not_connected_returns_connected_false(
        self, db_session: AsyncSession
    ) -> None:
        owner = await _make_user(db_session, clerk_id="sp_vis_05", username="sp_vis_05")
        owner.visibility_activity = VisibilityScope.PUBLIC.value

        result = await spotify_svc.get_listening(db_session, owner, viewer=None)

        assert result is not None
        assert result.connected is False
        assert result.recently_played == []

    async def test_listening_endpoint_403_when_private(
        self, anon_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        owner = await _make_user(db_session, clerk_id="sp_vis_06", username="sp_vis_06")
        await self._connect(db_session, owner)

        resp = await anon_client.get(f"/api/v1/spotify/listening/{owner.username}")

        assert resp.status_code == 403

    async def test_listening_endpoint_unknown_user_404(
        self, anon_client: AsyncClient
    ) -> None:
        resp = await anon_client.get("/api/v1/spotify/listening/nobody_xyz")
        assert resp.status_code == 404
