"""
Integration tests: Spotify connection persistence (encrypted at rest),
callback state validation, disconnect, and listening visibility enforcement.

External Spotify HTTP calls are monkeypatched — these tests exercise the
database and visibility layers, not Spotify itself.
"""

import logging
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

    async def test_unexpected_failure_returns_a_clean_500(
        self,
        authed_client: tuple[AsyncClient, str],
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The 500 path must report the fault, not become a second one.

        Regression, 2026-09-07. The handler read `current_user.id` to build
        its log message *after* `await session.rollback()`. rollback() expires
        every ORM object in the session, so that read issued a refresh SELECT
        — synchronous IO in an async context — and SQLAlchemy raised
        MissingGreenlet while evaluating the arguments to `logger.exception`.

        The logging call therefore never ran: the original exception was
        destroyed, and the client got an unhandled crash instead of the 500
        the handler was written to return. In production this hid a
        TokenCryptoError behind a stack trace about greenlets.

        `tests/unit/test_error_handler_safety.py` pins the shape across every
        handler; this pins the behaviour on the one that failed.
        """
        ac, clerk_id = authed_client
        user = await _make_user(db_session, clerk_id=clerk_id, username="sp_u500")
        state = spotify_svc.create_state(user.id)

        async def _boom(*_args: object, **_kwargs: object) -> None:
            # Stands in for the real fault (a malformed TOKEN_ENCRYPTION_KEY),
            # which is neither SpotifyAPIError nor SpotifyNotConfiguredError
            # and so lands in the bare `except Exception` handler.
            raise RuntimeError("token encryption failed")

        monkeypatch.setattr(spotify_svc, "connect", _boom)

        resp = await ac.post(
            "/api/v1/spotify/callback",
            json={"code": "auth-code", "state": state},
        )

        # A JSON 500 the frontend can render — not an unhandled exception.
        assert resp.status_code == 500
        assert (
            resp.json()["detail"] == "Couldn't connect your Spotify account. Try again."
        )

    async def test_unexpected_failure_logs_the_original_exception(
        self,
        authed_client: tuple[AsyncClient, str],
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """The point of the handler is the log line; assert it survives.

        A 500 that reaches the client correctly but logs nothing would pass
        the test above and still leave the fault undiagnosable — which is
        exactly the state this regression created.
        """
        ac, clerk_id = authed_client
        user = await _make_user(db_session, clerk_id=clerk_id, username="sp_u501")
        state = spotify_svc.create_state(user.id)

        async def _boom(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("token encryption failed")

        monkeypatch.setattr(spotify_svc, "connect", _boom)

        with caplog.at_level(logging.ERROR, logger="app.api.v1.spotify"):
            await ac.post(
                "/api/v1/spotify/callback",
                json={"code": "auth-code", "state": state},
            )

        assert "Spotify callback failed" in caplog.text
        # The original exception, with its traceback — the thing that was lost.
        assert "token encryption failed" in caplog.text
        assert "MissingGreenlet" not in caplog.text

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

    async def test_unusable_token_reports_needs_reconnect(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A linked account whose token will not decrypt is not "disconnected".

        Regression: this returned connected=False, so the profile told the user
        to connect Spotify while the settings page — which only checks that a
        connection row exists — said they already had. The two surfaces
        contradicted each other and the state never resolved itself.
        """
        owner = await _make_user(db_session, clerk_id="sp_vis_09", username="sp_vis_09")
        await self._connect(db_session, owner)

        async def _unusable(*_args: object, **_kwargs: object) -> None:
            raise spotify_svc.SpotifyNotConnectedError("Stored token unusable")

        monkeypatch.setattr(spotify_svc, "_fetch_listening_payload", _unusable)

        result = await spotify_svc.get_listening(db_session, owner, viewer=owner)

        assert result is not None
        assert result.needs_reconnect is True
        # Still "connected": the row is there, and saying otherwise is what
        # sent the user to a settings page that disagreed.
        assert result.connected is True

    async def test_no_connection_is_not_needs_reconnect(
        self, db_session: AsyncSession
    ) -> None:
        """A genuinely unlinked account must stay distinguishable."""
        owner = await _make_user(db_session, clerk_id="sp_vis_10", username="sp_vis_10")

        result = await spotify_svc.get_listening(db_session, owner, viewer=owner)

        assert result is not None
        assert result.connected is False
        assert result.needs_reconnect is False

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
