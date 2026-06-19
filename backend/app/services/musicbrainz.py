"""
MusicBrainz API client.

Rate limit: 1 unauthenticated request/second (MetaBrainz ToS).
A simple token-bucket enforces this server-side via asyncio so the
frontend never sees rate-limit errors.

Responses are cached in-process for 5 minutes to absorb repeated
identical queries without re-hitting the API.
"""

import asyncio
import logging
import time
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_MB_BASE = "https://musicbrainz.org/ws/2"
_CACHE_TTL = 300.0  # seconds
_REQUEST_INTERVAL = 1.0  # seconds between MB requests

_cache: dict[str, tuple[float, Any]] = {}


class _RateLimiter:
    def __init__(self, interval: float) -> None:
        self._interval = interval
        self._last_at: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._interval - (now - self._last_at)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_at = time.monotonic()


_limiter = _RateLimiter(_REQUEST_INTERVAL)


def _cache_key(path: str, params: dict[str, str]) -> str:
    sorted_params = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return f"{path}?{sorted_params}"


async def _get(path: str, params: dict[str, str]) -> dict[str, Any]:
    params = {**params, "fmt": "json"}
    key = _cache_key(path, params)

    cached = _cache.get(key)
    if cached is not None:
        cached_at, data = cached
        if time.monotonic() - cached_at < _CACHE_TTL:
            logger.debug("MB cache hit: %s", key)
            return data  # type: ignore[no-any-return]
        logger.debug("MB cache stale: %s", key)
    else:
        logger.debug("MB cache miss: %s", key)

    await _limiter.acquire()

    url = f"{_MB_BASE}/{path}"
    headers = {"User-Agent": settings.musicbrainz_user_agent}
    t0 = time.monotonic()

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, headers=headers, timeout=10.0)
        response.raise_for_status()

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    logger.debug("MB %s → %dms", path, elapsed_ms)

    result: dict[str, Any] = response.json()
    _cache[key] = (time.monotonic(), result)
    return result


# ── Search endpoints ───────────────────────────────────────────────────────────


async def search_artists(query: str, limit: int = 5) -> list[dict[str, Any]]:
    data = await _get("artist", {"query": query, "limit": str(limit)})
    return data.get("artists", [])  # type: ignore[no-any-return]


async def search_release_groups(query: str, limit: int = 5) -> list[dict[str, Any]]:
    data = await _get("release-group", {"query": query, "limit": str(limit)})
    return data.get("release-groups", [])  # type: ignore[no-any-return]


async def search_recordings(query: str, limit: int = 5) -> list[dict[str, Any]]:
    data = await _get("recording", {"query": query, "limit": str(limit)})
    return data.get("recordings", [])  # type: ignore[no-any-return]


# ── Lookup endpoints (single entity by MBID) ──────────────────────────────────


async def lookup_artist(mbid: str) -> dict[str, Any] | None:
    try:
        return await _get(f"artist/{mbid}", {})
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise


async def lookup_release_group(mbid: str) -> dict[str, Any] | None:
    try:
        return await _get(f"release-group/{mbid}", {})
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise


async def lookup_recording(mbid: str) -> dict[str, Any] | None:
    try:
        return await _get(f"recording/{mbid}", {})
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise
