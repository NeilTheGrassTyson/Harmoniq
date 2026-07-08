"""
Unit tests for the Spotify service: OAuth state signing, authorize URL,
payload mapping, and the token-refresh flow (httpx mocked with respx).
No database required except the lightweight in-memory session stub used
for refresh-token persistence checks.
"""

import time
import uuid
from typing import Any

import pytest
import respx
from cryptography.fernet import Fernet
from httpx import Response

from app.config import settings
from app.core.crypto import decrypt_token, encrypt_token
from app.services import spotify as spotify_svc

_USER_ID = uuid.UUID("00000000-0000-0000-0002-000000000001")


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


# ── OAuth state ───────────────────────────────────────────────────────────────


class TestOAuthState:
    def test_round_trip_validates(self) -> None:
        state = spotify_svc.create_state(_USER_ID)
        assert spotify_svc.validate_state(state, _USER_ID) is True

    def test_tampered_signature_rejected(self) -> None:
        state = spotify_svc.create_state(_USER_ID)
        payload, _sig = state.split(".", 1)
        assert spotify_svc.validate_state(f"{payload}.AAAA", _USER_ID) is False

    def test_tampered_payload_rejected(self) -> None:
        state = spotify_svc.create_state(_USER_ID)
        _payload, sig = state.split(".", 1)
        other = spotify_svc._b64(f"{uuid.uuid4()}|{int(time.time()) + 600}|x".encode())
        assert spotify_svc.validate_state(f"{other}.{sig}", _USER_ID) is False

    def test_wrong_user_rejected(self) -> None:
        state = spotify_svc.create_state(_USER_ID)
        assert spotify_svc.validate_state(state, uuid.uuid4()) is False

    def test_expired_state_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        real_time = time.time
        monkeypatch.setattr(time, "time", lambda: real_time() - 3600)
        state = spotify_svc.create_state(_USER_ID)  # expiry in the past
        monkeypatch.setattr(time, "time", real_time)
        assert spotify_svc.validate_state(state, _USER_ID) is False

    def test_garbage_rejected(self) -> None:
        assert spotify_svc.validate_state("not-a-state", _USER_ID) is False
        assert spotify_svc.validate_state("", _USER_ID) is False


# ── Authorize URL ─────────────────────────────────────────────────────────────


class TestAuthorizeUrl:
    def test_contains_required_params(self) -> None:
        url = spotify_svc.build_authorize_url(_USER_ID)
        assert url.startswith("https://accounts.spotify.com/authorize?")
        assert "client_id=client-id" in url
        assert "response_type=code" in url
        assert "user-read-recently-played" in url
        assert "user-read-currently-playing" in url
        assert "state=" in url
        assert "127.0.0.1" in url

    def test_unconfigured_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "spotify_client_id", None)
        with pytest.raises(spotify_svc.SpotifyNotConfiguredError):
            spotify_svc.build_authorize_url(_USER_ID)


# ── Payload mapping ───────────────────────────────────────────────────────────


def _track_json(name: str = "Song", artist: str = "Artist") -> dict[str, Any]:
    return {
        "type": "track",
        "name": name,
        "artists": [{"name": artist}],
        "album": {
            "name": "Album",
            "images": [{"url": "https://i.scdn.co/image/abc"}],
        },
        "external_urls": {"spotify": "https://open.spotify.com/track/abc"},
    }


class TestPayloadMapping:
    def test_now_playing_mapped_when_playing(self) -> None:
        payload = {
            "now": {"is_playing": True, "item": _track_json("Current")},
            "recent": [],
        }
        resp = spotify_svc._payload_to_response(payload)
        assert resp.now_playing is not None
        assert resp.now_playing.track_name == "Current"
        assert resp.now_playing.artist_name == "Artist"
        assert resp.now_playing.album_art_url == "https://i.scdn.co/image/abc"

    def test_paused_playback_not_shown_as_now_playing(self) -> None:
        payload = {
            "now": {"is_playing": False, "item": _track_json()},
            "recent": [],
        }
        resp = spotify_svc._payload_to_response(payload)
        assert resp.now_playing is None

    def test_episode_item_skipped(self) -> None:
        payload = {
            "now": {"is_playing": True, "item": {"type": "episode", "name": "Pod"}},
            "recent": [],
        }
        resp = spotify_svc._payload_to_response(payload)
        assert resp.now_playing is None

    def test_recently_played_mapped_with_timestamps(self) -> None:
        payload = {
            "now": None,
            "recent": [
                {"track": _track_json("One"), "played_at": "2026-07-04T10:00:00Z"},
                {"track": _track_json("Two"), "played_at": "2026-07-04T09:00:00Z"},
            ],
        }
        resp = spotify_svc._payload_to_response(payload)
        assert [t.track_name for t in resp.recently_played] == ["One", "Two"]
        assert resp.recently_played[0].played_at.year == 2026

    def test_malformed_recent_entry_skipped(self) -> None:
        payload = {
            "now": None,
            "recent": [
                {"track": {}, "played_at": "2026-07-04T10:00:00Z"},
                {"track": _track_json("Good")},  # missing played_at
                {"track": _track_json("Kept"), "played_at": "2026-07-04T08:00:00Z"},
            ],
        }
        resp = spotify_svc._payload_to_response(payload)
        assert [t.track_name for t in resp.recently_played] == ["Kept"]

    def test_multiple_artists_joined(self) -> None:
        item = _track_json()
        item["artists"] = [{"name": "A"}, {"name": "B"}]
        track = spotify_svc._map_track(item)
        assert track is not None
        assert track.artist_name == "A, B"


# ── Token refresh flow ────────────────────────────────────────────────────────


class _FakeConn:
    """Duck-typed SpotifyConnection for refresh tests."""

    def __init__(self, refresh_token: str) -> None:
        self.user_id = _USER_ID
        self.spotify_user_id = "spotify-user"
        self.refresh_token_encrypted = encrypt_token(refresh_token)
        self.scopes = spotify_svc.SCOPES


class _FakeSession:
    """Records execute/flush calls; enough for the refresh paths under test."""

    def __init__(self) -> None:
        self.executed: list[Any] = []
        self.flushed = False

    async def execute(self, stmt: Any) -> None:
        self.executed.append(stmt)

    async def flush(self) -> None:
        self.flushed = True


@pytest.mark.asyncio
class TestTokenRefresh:
    @respx.mock
    async def test_refresh_success_caches_token(self) -> None:
        respx.post(spotify_svc._TOKEN_URL).mock(
            return_value=Response(
                200, json={"access_token": "fresh-token", "expires_in": 3600}
            )
        )
        conn = _FakeConn("refresh-me")
        session = _FakeSession()

        token = await spotify_svc._get_access_token(session, conn)  # type: ignore[arg-type]

        assert token == "fresh-token"
        assert spotify_svc._access_tokens[_USER_ID][0] == "fresh-token"
        # Second call must hit the cache, not the (now unmocked) network.
        token2 = await spotify_svc._get_access_token(session, conn)  # type: ignore[arg-type]
        assert token2 == "fresh-token"

    @respx.mock
    async def test_invalid_grant_deletes_connection_and_raises(self) -> None:
        respx.post(spotify_svc._TOKEN_URL).mock(
            return_value=Response(400, json={"error": "invalid_grant"})
        )
        conn = _FakeConn("revoked")
        session = _FakeSession()

        with pytest.raises(spotify_svc.SpotifyNotConnectedError):
            await spotify_svc._get_access_token(session, conn)  # type: ignore[arg-type]

        assert len(session.executed) == 1  # the DELETE
        assert _USER_ID not in spotify_svc._access_tokens

    @respx.mock
    async def test_rotated_refresh_token_persisted(self) -> None:
        respx.post(spotify_svc._TOKEN_URL).mock(
            return_value=Response(
                200,
                json={
                    "access_token": "fresh-token",
                    "expires_in": 3600,
                    "refresh_token": "rotated-refresh",
                },
            )
        )
        conn = _FakeConn("old-refresh")
        session = _FakeSession()

        await spotify_svc._get_access_token(session, conn)  # type: ignore[arg-type]

        assert session.flushed is True
        assert decrypt_token(conn.refresh_token_encrypted) == "rotated-refresh"

    @respx.mock
    async def test_server_error_raises_api_error(self) -> None:
        respx.post(spotify_svc._TOKEN_URL).mock(return_value=Response(500))
        conn = _FakeConn("refresh-me")
        session = _FakeSession()

        with pytest.raises(spotify_svc.SpotifyAPIError):
            await spotify_svc._get_access_token(session, conn)  # type: ignore[arg-type]
