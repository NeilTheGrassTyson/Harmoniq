"""
Spotify service: OAuth account linking and display-only listening data.

Constraints (spec: phase-1-spotify-listening.md, ENGINEERING_BIBLE §13):
- The only persisted Spotify data is the connection row (encrypted refresh
  token). Listening data is fetched live, cached briefly in process, and
  never written to the database or fed to any other subsystem.
- Visibility (the existing visibility_activity profile scope) is enforced
  here, at the service layer, on every request — the payload cache sits
  below the visibility decision, never above it.
"""

import base64
import hmac
import logging
import secrets
import time
import uuid
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.crypto import TokenCryptoError, decrypt_token, encrypt_token
from app.core.enums import VisibilityScope
from app.core.visibility import scope_allows
from app.models.spotify import SpotifyConnection
from app.models.user import User
from app.schemas.spotify import (
    ListeningResponse,
    ListeningTrack,
    RecentlyPlayedItem,
    SpotifyConnectionStatus,
)
from app.services import follow as follow_svc

logger = logging.getLogger(__name__)

_AUTH_URL = "https://accounts.spotify.com/authorize"
_TOKEN_URL = "https://accounts.spotify.com/api/token"  # noqa: S105 — endpoint URL, not a secret  # nosec B105
_API_BASE = "https://api.spotify.com/v1"

SCOPES = "user-read-recently-played user-read-currently-playing"

_STATE_TTL_SECONDS = 600
_LISTENING_CACHE_TTL = 60.0
_RECENT_LIMIT = 20
_REFRESH_EARLY_SECONDS = 60  # refresh before expiry to absorb clock skew

# In-process caches. Single-worker only — a shared cache is required before
# multi-worker deployment (recorded in the spec's known limitations).
_access_tokens: dict[
    uuid.UUID, tuple[str, float]
] = {}  # user_id -> (token, monotonic expiry)
_listening_cache: dict[uuid.UUID, tuple[float, dict[str, Any]]] = {}


class SpotifyNotConfiguredError(Exception):
    """Spotify env settings are missing."""


class SpotifyNotConnectedError(Exception):
    """The user has no (working) Spotify connection."""


class SpotifyAPIError(Exception):
    """Spotify returned an unexpected error."""


def _require_config() -> tuple[str, str, str]:
    if not (
        settings.spotify_client_id
        and settings.spotify_client_secret
        and settings.spotify_redirect_uri
        and settings.token_encryption_key
    ):
        raise SpotifyNotConfiguredError(
            "SPOTIFY_CLIENT_ID/SECRET, SPOTIFY_REDIRECT_URI, and "
            "TOKEN_ENCRYPTION_KEY must all be set"
        )
    return (
        settings.spotify_client_id,
        settings.spotify_client_secret,
        settings.spotify_redirect_uri,
    )


# ── OAuth state (HMAC-signed, time-limited, user-bound) ───────────────────────


def _state_key() -> bytes:
    if not settings.token_encryption_key:
        raise SpotifyNotConfiguredError("TOKEN_ENCRYPTION_KEY must be set")
    return settings.token_encryption_key.encode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def create_state(user_id: uuid.UUID) -> str:
    """Signed state binding the OAuth round-trip to one Harmoniq user."""
    payload = (
        f"{user_id}|{int(time.time()) + _STATE_TTL_SECONDS}|{secrets.token_urlsafe(8)}"
    )
    signature = hmac.digest(_state_key(), payload.encode(), sha256)
    return f"{_b64(payload.encode())}.{_b64(signature)}"


def validate_state(state: str, user_id: uuid.UUID) -> bool:
    """Check signature, expiry, and that the embedded user matches the caller."""
    try:
        payload_b64, sig_b64 = state.split(".", 1)
        payload = _unb64(payload_b64)
        expected = hmac.digest(_state_key(), payload, sha256)
        if not hmac.compare_digest(expected, _unb64(sig_b64)):
            return False
        embedded_user, expiry, _nonce = payload.decode().split("|", 2)
        if int(expiry) < int(time.time()):
            return False
        return embedded_user == str(user_id)
    except (ValueError, TypeError):
        return False


# ── OAuth flow ────────────────────────────────────────────────────────────────


def build_authorize_url(user_id: uuid.UUID) -> str:
    client_id, _, redirect_uri = _require_config()
    params = httpx.QueryParams(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
            "state": create_state(user_id),
        }
    )
    return f"{_AUTH_URL}?{params}"


async def _token_request(data: dict[str, str]) -> httpx.Response:
    client_id, client_secret, _ = _require_config()
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient() as client:
        return await client.post(
            _TOKEN_URL,
            data=data,
            headers={"Authorization": f"Basic {basic}"},
            timeout=10.0,
        )


async def _exchange_code(code: str) -> dict[str, Any]:
    _, _, redirect_uri = _require_config()
    resp = await _token_request(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
    )
    if resp.status_code != 200:
        logger.warning("Spotify code exchange failed: status=%s", resp.status_code)
        raise SpotifyAPIError("Code exchange failed")
    return resp.json()  # type: ignore[no-any-return]


async def _fetch_spotify_profile(access_token: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_API_BASE}/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
    if resp.status_code != 200:
        raise SpotifyAPIError("Could not fetch Spotify profile")
    return str(resp.json().get("id", ""))


async def connect(
    session: AsyncSession,
    user: User,
    code: str,
    state: str,
) -> SpotifyConnectionStatus:
    """Validate state, exchange the code, and upsert the connection row."""
    if not validate_state(state, user.id):
        raise SpotifyAPIError("Invalid or expired state")

    tokens = await _exchange_code(code)
    refresh_token = tokens.get("refresh_token")
    access_token = tokens.get("access_token")
    if not refresh_token or not access_token:
        raise SpotifyAPIError("Token response missing tokens")

    spotify_user_id = await _fetch_spotify_profile(access_token)

    now = datetime.now(tz=UTC)
    stmt = (
        pg_insert(SpotifyConnection)
        .values(
            id=uuid.uuid4(),
            user_id=user.id,
            spotify_user_id=spotify_user_id,
            refresh_token_encrypted=encrypt_token(refresh_token),
            scopes=tokens.get("scope", SCOPES),
            connected_at=now,
        )
        .on_conflict_do_update(
            index_elements=["user_id"],
            set_={
                "spotify_user_id": spotify_user_id,
                "refresh_token_encrypted": encrypt_token(refresh_token),
                "scopes": tokens.get("scope", SCOPES),
                "connected_at": now,
            },
        )
    )
    await session.execute(stmt)

    # Prime the access-token cache; expires_in is seconds from now.
    expires_in = float(tokens.get("expires_in", 3600))
    _access_tokens[user.id] = (
        access_token,
        time.monotonic() + expires_in - _REFRESH_EARLY_SECONDS,
    )
    _listening_cache.pop(user.id, None)

    logger.info("Spotify connected internal_id=%s", user.id)
    return SpotifyConnectionStatus(
        connected=True, spotify_user_id=spotify_user_id, connected_at=now
    )


async def disconnect(session: AsyncSession, user: User) -> None:
    """Delete the connection and drop all in-memory state immediately."""
    await session.execute(
        delete(SpotifyConnection).where(SpotifyConnection.user_id == user.id)
    )
    _access_tokens.pop(user.id, None)
    _listening_cache.pop(user.id, None)
    logger.info("Spotify disconnected internal_id=%s", user.id)


async def get_connection(
    session: AsyncSession, user_id: uuid.UUID
) -> SpotifyConnection | None:
    result = await session.execute(
        select(SpotifyConnection).where(SpotifyConnection.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_status(session: AsyncSession, user: User) -> SpotifyConnectionStatus:
    conn = await get_connection(session, user.id)
    if conn is None:
        return SpotifyConnectionStatus(connected=False)
    return SpotifyConnectionStatus(
        connected=True,
        spotify_user_id=conn.spotify_user_id,
        connected_at=conn.connected_at,
    )


# ── Access-token management ───────────────────────────────────────────────────


async def _get_access_token(session: AsyncSession, conn: SpotifyConnection) -> str:
    cached = _access_tokens.get(conn.user_id)
    if cached is not None and time.monotonic() < cached[1]:
        return cached[0]

    try:
        refresh_token = decrypt_token(conn.refresh_token_encrypted)
    except TokenCryptoError as exc:
        raise SpotifyNotConnectedError("Stored token unusable") from exc

    resp = await _token_request(
        {"grant_type": "refresh_token", "refresh_token": refresh_token}
    )
    if resp.status_code in (400, 403):
        # invalid_grant → the user revoked access; treat as disconnected.
        logger.info(
            "Spotify refresh rejected (revoked?) internal_id=%s status=%s",
            conn.user_id,
            resp.status_code,
        )
        user_id = conn.user_id
        await session.execute(
            delete(SpotifyConnection).where(SpotifyConnection.user_id == user_id)
        )
        _access_tokens.pop(user_id, None)
        _listening_cache.pop(user_id, None)
        raise SpotifyNotConnectedError("Spotify grant revoked")
    if resp.status_code != 200:
        raise SpotifyAPIError("Token refresh failed")

    tokens = resp.json()
    access_token = str(tokens["access_token"])
    expires_in = float(tokens.get("expires_in", 3600))
    _access_tokens[conn.user_id] = (
        access_token,
        time.monotonic() + expires_in - _REFRESH_EARLY_SECONDS,
    )

    # Spotify may rotate the refresh token — persist the new one if present.
    new_refresh = tokens.get("refresh_token")
    if new_refresh:
        conn.refresh_token_encrypted = encrypt_token(new_refresh)
        await session.flush()

    return access_token


# ── Listening data (display-only) ─────────────────────────────────────────────


def _map_track(item: dict[str, Any]) -> ListeningTrack | None:
    """Map a Spotify track object to our display schema. None for non-tracks."""
    if not item or item.get("type") not in (None, "track"):
        return None
    name = item.get("name")
    artists = item.get("artists") or []
    if not name or not artists:
        return None
    album = item.get("album") or {}
    images = album.get("images") or []
    return ListeningTrack(
        track_name=str(name),
        artist_name=", ".join(a.get("name", "") for a in artists if a.get("name")),
        album_name=album.get("name"),
        album_art_url=images[0].get("url") if images else None,
        spotify_url=(item.get("external_urls") or {}).get("spotify"),
    )


async def _fetch_listening_payload(
    session: AsyncSession, conn: SpotifyConnection
) -> dict[str, Any]:
    """Fetch currently-playing + recently-played raw payloads (with TTL cache)."""
    cached = _listening_cache.get(conn.user_id)
    if cached is not None and (time.monotonic() - cached[0]) < _LISTENING_CACHE_TTL:
        return cached[1]

    access_token = await _get_access_token(session, conn)
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient() as client:
        now_resp = await client.get(
            f"{_API_BASE}/me/player/currently-playing", headers=headers, timeout=10.0
        )
        recent_resp = await client.get(
            f"{_API_BASE}/me/player/recently-played",
            params={"limit": _RECENT_LIMIT},
            headers=headers,
            timeout=10.0,
        )

    payload: dict[str, Any] = {"now": None, "recent": []}
    if now_resp.status_code == 200:
        payload["now"] = now_resp.json()
    # 204 = nothing playing — expected, not an error.
    if recent_resp.status_code == 200:
        payload["recent"] = recent_resp.json().get("items", [])

    _listening_cache[conn.user_id] = (time.monotonic(), payload)
    return payload


def _payload_to_response(payload: dict[str, Any]) -> ListeningResponse:
    now_playing: ListeningTrack | None = None
    now = payload.get("now")
    if now and now.get("is_playing"):
        now_playing = _map_track(now.get("item") or {})

    recent: list[RecentlyPlayedItem] = []
    for entry in payload.get("recent", []):
        track = _map_track(entry.get("track") or {})
        played_at = entry.get("played_at")
        if track is None or played_at is None:
            continue
        recent.append(RecentlyPlayedItem(**track.model_dump(), played_at=played_at))

    return ListeningResponse(
        connected=True, now_playing=now_playing, recently_played=recent
    )


async def get_listening(
    session: AsyncSession,
    profile_user: User,
    viewer: User | None,
) -> ListeningResponse | None:
    """
    Listening data for profile_user, or None when the viewer is not allowed
    to see it (visibility_activity scope — checked on every request; only
    the raw Spotify payload is cached, never the visibility decision).
    """
    is_owner = viewer is not None and viewer.id == profile_user.id
    scope = VisibilityScope(profile_user.visibility_activity)
    is_friend = False
    if not is_owner and scope == VisibilityScope.FRIENDS and viewer is not None:
        is_friend = await follow_svc.is_mutual_follow(
            session, viewer.id, profile_user.id
        )
    if not scope_allows(scope, is_owner=is_owner, is_friend=is_friend):
        return None

    conn = await get_connection(session, profile_user.id)
    if conn is None:
        return ListeningResponse(connected=False)

    try:
        payload = await _fetch_listening_payload(session, conn)
    except SpotifyNotConnectedError:
        return ListeningResponse(connected=False)
    except (SpotifyAPIError, SpotifyNotConfiguredError, httpx.HTTPError):
        logger.exception(
            "Listening fetch failed internal_id=%s — rendering empty", profile_user.id
        )
        return ListeningResponse(connected=True)

    return _payload_to_response(payload)
