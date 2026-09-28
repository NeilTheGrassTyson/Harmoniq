"""
Spotify service: OAuth account linking and display-only listening data.

Constraints (spec: phase-1-spotify-listening.md, ENGINEERING_BIBLE §13):
- By default the only persisted Spotify data is the connection row
  (encrypted refresh token); listening is fetched live and cached briefly in
  process. With LISTEN_HISTORY_ENABLED on, a user who opts in also keeps up
  to 20 recent plays as display-only rows (phase-2-listen-history.md) —
  written through app/services/listens.py and never fed to recommendation.
- Visibility (the existing visibility_activity profile scope) is enforced
  here, at the service layer, on every request — the payload cache sits
  below the visibility decision, never above it.
"""

import base64
import hmac
import logging
import re
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
from app.database import AsyncSessionLocal
from app.models.highlight import Highlight
from app.models.spotify import SpotifyConnection
from app.models.user import User
from app.schemas.spotify import (
    ListeningResponse,
    ListeningTrack,
    RecentlyPlayedItem,
    SpotifyConnectionStatus,
)
from app.services import friendship as friendship_svc
from app.services import listens as listens_svc

logger = logging.getLogger(__name__)

_AUTH_URL = "https://accounts.spotify.com/authorize"
_TOKEN_URL = "https://accounts.spotify.com/api/token"  # noqa: S105 — endpoint URL, not a secret  # nosec B105
_API_BASE = "https://api.spotify.com/v1"

SCOPES = "user-read-recently-played user-read-currently-playing"
# Reading a user's own playlists, for playlist highlights. Requested only while
# PLAYLIST_HIGHLIGHTS_ENABLED is on, so nobody is asked to re-authorize for a
# feature that is switched off (specs/phase-2-highlights.md).
PLAYLIST_SCOPE = "playlist-read-private"
_PLAYLIST_ID = re.compile(r"^[A-Za-z0-9]{22}$")


def requested_scopes() -> str:
    if settings.playlist_highlights_enabled:
        return f"{SCOPES} {PLAYLIST_SCOPE}"
    return SCOPES


def has_playlist_access(conn: SpotifyConnection) -> bool:
    """Whether the stored grant includes playlist reading. Read from what
    Spotify reported granting, never assumed from what was requested."""
    return PLAYLIST_SCOPE in conn.scopes.split()


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
# History mode: one background refresh per user at a time, and a remembered
# unusable connection so a stored-rows response can still say "reconnect".
_refreshing: set[uuid.UUID] = set()
_needs_reconnect: set[uuid.UUID] = set()


class SpotifyNotConfiguredError(Exception):
    """Spotify env settings are missing."""


class SpotifyNotConnectedError(Exception):
    """The user has no (working) Spotify connection."""


class SpotifyAPIError(Exception):
    """Spotify returned an unexpected error."""


# Every variable the integration needs, in the order an operator sets them.
# TOKEN_ENCRYPTION_KEY is here despite not being a Spotify credential: without
# it a stored refresh token cannot be decrypted, so a connection exists and
# cannot be used.
_REQUIRED_SETTINGS = (
    "spotify_client_id",
    "spotify_client_secret",
    "spotify_redirect_uri",
    "token_encryption_key",
)


def _require_config() -> tuple[str, str, str]:
    client_id = settings.spotify_client_id
    client_secret = settings.spotify_client_secret
    redirect_uri = settings.spotify_redirect_uri
    # Read into locals and tested as a chain so the return type narrows; the
    # per-variable report below is only built on the failure path.
    if not (client_id and client_secret and redirect_uri):
        raise SpotifyNotConfiguredError(_missing_settings_message())
    if not settings.token_encryption_key:
        raise SpotifyNotConfiguredError(_missing_settings_message())
    return client_id, client_secret, redirect_uri


def _missing_settings_message() -> str:
    """Name the variables that are actually missing, not the whole group.

    The 503 body deliberately names none of them, so this message is the
    entire diagnosis and it only reaches Deploy Logs. "One of these four"
    costs a round of guessing against a platform UI where all four look
    present — which is exactly how 2026-09-06 went.

    Names only. It is logged at ERROR on every 503.
    """
    missing = [
        name.upper() for name in _REQUIRED_SETTINGS if not getattr(settings, name)
    ]
    return f"not configured — missing or empty: {', '.join(missing)}"


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
            "scope": requested_scopes(),
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


def _token_error_detail(resp: httpx.Response) -> str:
    """Spotify's own reason for refusing a token request.

    Only ever called on a non-200: a failed token response carries
    `{"error": ..., "error_description": ...}` and no credentials, while a
    successful one carries the tokens themselves and must never be logged.

    Without this the log said "status=400" and nothing else, which does not
    distinguish the three things a 400 here actually means — a code that was
    already used or expired (`invalid_grant`, retry the flow), a client id
    and secret from different Spotify apps (`invalid_client`), or a
    redirect_uri that does not match the one sent to /authorize. Each has a
    different fix and the status code alone picks none of them.
    """
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:200] or "<empty body>"
    if not isinstance(body, dict):
        return str(body)[:200]
    # The token endpoint's error shape is flat: {"error", "error_description"}.
    # The nested {"error": {"status", "message"}} form belongs to the Web API
    # endpoints, which never reach this helper.
    parts = (body.get("error"), body.get("error_description"))
    detail = " — ".join(str(part) for part in parts if part)
    return detail[:200] or "<no error field>"


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
        logger.warning(
            "Spotify code exchange failed: status=%s — %s (redirect_uri sent: "
            "%s; it must match the one registered in the Spotify dashboard "
            "exactly, and the authorize call that issued the code)",
            resp.status_code,
            _token_error_detail(resp),
            redirect_uri,
        )
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
            # "" when Spotify omits it: what was requested is no proof of grant.
            scopes=tokens.get("scope", ""),
            connected_at=now,
        )
        .on_conflict_do_update(
            index_elements=["user_id"],
            set_={
                "spotify_user_id": spotify_user_id,
                "refresh_token_encrypted": encrypt_token(refresh_token),
                "scopes": tokens.get("scope", ""),
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
    _needs_reconnect.discard(user.id)

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
    _needs_reconnect.discard(user.id)
    # Disconnecting the provider deletes what was stored from it, synchronously
    # (phase-2-listen-history.md requirement 7).
    await listens_svc.forget(session, user.id, "spotify")
    await _forget_playlist_highlights(session, user.id)
    logger.info("Spotify disconnected internal_id=%s", user.id)


async def _forget_playlist_highlights(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    """Playlist highlights are provider-backed: when the grant ends, they go."""
    await session.execute(
        delete(Highlight).where(
            Highlight.user_id == user_id, Highlight.provider == "spotify"
        )
    )


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
            "Spotify refresh rejected (revoked?) internal_id=%s status=%s — %s",
            conn.user_id,
            resp.status_code,
            _token_error_detail(resp),
        )
        user_id = conn.user_id
        await session.execute(
            delete(SpotifyConnection).where(SpotifyConnection.user_id == user_id)
        )
        _access_tokens.pop(user_id, None)
        _listening_cache.pop(user_id, None)
        await listens_svc.forget(session, user_id, "spotify")
        await _forget_playlist_highlights(session, user_id)
        raise SpotifyNotConnectedError("Spotify grant revoked")
    if resp.status_code != 200:
        logger.warning(
            "Spotify token refresh failed: internal_id=%s status=%s — %s",
            conn.user_id,
            resp.status_code,
            _token_error_detail(resp),
        )
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


def _observed(entry: dict[str, Any]) -> listens_svc.ObservedListen | None:
    """A recently-played entry as a storable observation, or None."""
    item = entry.get("track") or {}
    track = _map_track(item)
    played_at = entry.get("played_at")
    if track is None or not played_at:
        return None
    track_id = item.get("id")
    isrc = (item.get("external_ids") or {}).get("isrc")
    return listens_svc.ObservedListen(
        source="spotify",
        # One play = one track at one moment; re-observing it is a no-op.
        idempotency_key=f"{track_id or track.track_name}|{played_at}",
        track_name=track.track_name,
        artist_name=track.artist_name,
        album_name=track.album_name,
        album_art_url=track.album_art_url,
        provider_url=track.spotify_url,
        isrc=str(isrc).upper() if isrc else None,
        played_at=datetime.fromisoformat(str(played_at).replace("Z", "+00:00")),
    )


def history_active(user: User) -> bool:
    return settings.listen_history_enabled and user.store_listening


def _fresh_payload(user_id: uuid.UUID) -> dict[str, Any] | None:
    cached = _listening_cache.get(user_id)
    if cached is not None and (time.monotonic() - cached[0]) < _LISTENING_CACHE_TTL:
        return cached[1]
    return None


async def _history_response(
    session: AsyncSession, user_id: uuid.UUID
) -> ListeningResponse:
    """Built from stored rows only — never waits on Spotify (requirement 10).
    Now playing comes from the 60s cache when warm; otherwise a background
    refresh is due and the client checks again shortly."""
    payload = _fresh_payload(user_id)
    stored = await listens_svc.recent_for_display(session, user_id)
    now_playing = _payload_to_response(payload).now_playing if payload else None
    return ListeningResponse(
        connected=True,
        needs_reconnect=user_id in _needs_reconnect,
        now_playing=now_playing,
        recently_played=[
            RecentlyPlayedItem(
                track_name=listen.track_name,
                artist_name=listen.artist_name,
                album_name=listen.album_name,
                album_art_url=listen.album_art_url,
                spotify_url=listen.provider_url,
                played_at=listen.played_at or listen.observed_at,
                track_mbid=mbid,
            )
            for listen, mbid in stored
        ],
        history=True,
        refreshing=payload is None and user_id not in _needs_reconnect,
    )


async def refresh_history(
    session: AsyncSession, user: User, conn: SpotifyConnection
) -> None:
    """Fetch the window (filling the 60s cache) and merge it into storage.
    A failed or empty fetch stores nothing and deletes nothing."""
    try:
        payload = await _fetch_listening_payload(session, conn)
    except SpotifyNotConnectedError:
        _needs_reconnect.add(user.id)
        logger.warning("Listening refresh: connection unusable internal_id=%s", user.id)
        return
    except (SpotifyAPIError, SpotifyNotConfiguredError, httpx.HTTPError):
        logger.exception("Listening refresh failed internal_id=%s", user.id)
        # Floor retries at the cache TTL: views keep serving stored rows and
        # stop reporting a refresh in progress, so clients don't re-poll fast.
        _listening_cache[user.id] = (time.monotonic(), {"now": None, "recent": []})
        return
    _needs_reconnect.discard(user.id)
    if not history_active(user):
        return
    observed = [o for e in payload.get("recent", []) if (o := _observed(e))]
    await listens_svc.record(session, user.id, observed)
    await listens_svc.link_some(session)


async def refresh_in_background(user_id: uuid.UUID) -> None:
    """Runs after the response is sent, on its own session. At most one per
    user at a time, so a burst of views can't multiply Spotify calls."""
    if user_id in _refreshing:
        return
    _refreshing.add(user_id)
    try:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            conn = await get_connection(session, user_id)
            if user is not None and conn is not None:
                await refresh_history(session, user, conn)
                await session.commit()
    except Exception:
        logger.exception("Background listening refresh failed user_id=%s", user_id)
    finally:
        _refreshing.discard(user_id)


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
        is_friend = await friendship_svc.are_friends(
            session, viewer.id, profile_user.id
        )
    if not scope_allows(scope, is_owner=is_owner, is_friend=is_friend):
        return None

    conn = await get_connection(session, profile_user.id)
    if conn is None:
        return ListeningResponse(connected=False)

    if history_active(profile_user):
        return await _history_response(session, profile_user.id)

    try:
        payload = await _fetch_listening_payload(session, conn)
    except SpotifyNotConnectedError as exc:
        # A linked account whose token is unusable. Logged because it is
        # otherwise invisible: the revoked-grant branch below deletes the row
        # and logs, while this one used to leave a connection the settings
        # page still calls "connected" and say nothing anywhere.
        logger.warning(
            "Listening unavailable for internal_id=%s — connection present but "
            "unusable (%s). The user must reconnect Spotify.",
            profile_user.id,
            exc,
        )
        return ListeningResponse(connected=True, needs_reconnect=True)
    except (SpotifyAPIError, SpotifyNotConfiguredError, httpx.HTTPError):
        logger.exception(
            "Listening fetch failed internal_id=%s — rendering empty", profile_user.id
        )
        return ListeningResponse(connected=True)

    return _payload_to_response(payload)


# ── Playlists (for playlist highlights) ───────────────────────────────────────


def _playlist_display(item: dict[str, Any]) -> dict[str, Any] | None:
    playlist_id = item.get("id")
    name = item.get("name")
    if not isinstance(playlist_id, str) or not _PLAYLIST_ID.match(playlist_id):
        return None
    if not name:
        return None
    images = item.get("images") or []
    image = images[0].get("url") if images and isinstance(images[0], dict) else None
    return {
        "id": playlist_id,
        "name": str(name),
        "image_url": image if isinstance(image, str) else None,
        "owner_id": (item.get("owner") or {}).get("id"),
    }


async def list_owned_playlists(
    session: AsyncSession, conn: SpotifyConnection
) -> list[dict[str, Any]]:
    """The user's own playlists (not followed ones), newest first as Spotify
    lists them. Raises SpotifyNotConnectedError / SpotifyAPIError."""
    access_token = await _get_access_token(session, conn)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_API_BASE}/me/playlists",
            params={"limit": 50},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
    if resp.status_code != 200:
        raise SpotifyAPIError(f"Playlist list failed: {resp.status_code}")
    owned = []
    for item in resp.json().get("items") or []:
        display = _playlist_display(item) if isinstance(item, dict) else None
        if display and display["owner_id"] == conn.spotify_user_id:
            owned.append(display)
    return owned


async def get_owned_playlist(
    session: AsyncSession, conn: SpotifyConnection, playlist_id: str
) -> dict[str, Any] | None:
    """Current name and art of one of the user's own playlists. None when it
    no longer exists, isn't theirs, or can't be read under the grant — a
    definite answer. Transient failures raise instead."""
    if not _PLAYLIST_ID.match(playlist_id):
        return None
    access_token = await _get_access_token(session, conn)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_API_BASE}/playlists/{playlist_id}",
            params={"fields": "id,name,images,owner(id)"},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
    if resp.status_code in (403, 404):
        return None
    if resp.status_code != 200:
        raise SpotifyAPIError(f"Playlist fetch failed: {resp.status_code}")
    display = _playlist_display(resp.json())
    if display is None or display["owner_id"] != conn.spotify_user_id:
        return None
    return display
