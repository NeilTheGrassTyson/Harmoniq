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

_LUCENE_SPECIAL_CHARS = set('+-&|!(){}[]^"~*?:\\')


def _escape_lucene(query: str) -> str:
    """Backslash-escape Lucene query syntax so user input is treated as
    literal text. Two-char operators (&&, ||) are covered by escaping each
    character individually."""
    return "".join(f"\\{ch}" if ch in _LUCENE_SPECIAL_CHARS else ch for ch in query)


async def search_artists(query: str, limit: int = 20) -> list[dict[str, Any]]:
    # Field-qualified query so both the canonical name and alias indexes are
    # searched (aliases cover translations, transliterations, and common
    # abbreviations like "GY!BE"). The input is escaped and phrase-quoted:
    # unquoted, Lucene tokenizes on punctuation/whitespace and only the first
    # token stays field-scoped, degrading the match to generic term hits.
    escaped = _escape_lucene(query)
    lucene_query = f'artist:"{escaped}" OR alias:"{escaped}"'
    data = await _get("artist", {"query": lucene_query, "limit": str(limit)})
    return data.get("artists", [])  # type: ignore[no-any-return]


async def search_release_groups(query: str, limit: int = 20) -> list[dict[str, Any]]:
    data = await _get("release-group", {"query": query, "limit": str(limit)})
    return data.get("release-groups", [])  # type: ignore[no-any-return]


async def search_recordings(query: str, limit: int = 20) -> list[dict[str, Any]]:
    data = await _get("recording", {"query": query, "limit": str(limit)})
    return data.get("recordings", [])  # type: ignore[no-any-return]


# ── Browse endpoints ───────────────────────────────────────────────────────────

_BROWSE_PAGE_SIZE = 100  # MusicBrainz maximum per request


async def browse_release_groups(artist_mbid: str) -> list[dict[str, Any]]:
    """Fetch all release groups (albums, singles, EPs) credited to an artist,
    paginating past the 100-per-page MusicBrainz cap. Each page goes through
    _get, so it respects the shared rate limiter and 5-minute cache."""
    results: list[dict[str, Any]] = []
    offset = 0
    while True:
        data = await _get(
            "release-group",
            {
                "artist": artist_mbid,
                "type": "album|single|ep",
                "limit": str(_BROWSE_PAGE_SIZE),
                "offset": str(offset),
            },
        )
        page = data.get("release-groups", [])
        results.extend(page)
        total = data.get("release-group-count", 0)
        offset += len(page)
        if not page or offset >= total:
            break
    return results


# ── Lookup endpoints (single entity by MBID) ──────────────────────────────────


async def lookup_artist(mbid: str) -> dict[str, Any] | None:
    try:
        return await _get(f"artist/{mbid}", {})
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (400, 404):  # 400 = malformed MBID
            return None
        raise


async def lookup_release_group(mbid: str) -> dict[str, Any] | None:
    # inc=artists is required for the artist-credit to be present on a bare
    # lookup — without it, cold album ingestion can't resolve the artist.
    # inc=releases exposes the release list so the tracklist sync can pick a
    # canonical release without a second round-trip.
    try:
        return await _get(f"release-group/{mbid}", {"inc": "artists+releases"})
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (400, 404):  # 400 = malformed MBID
            return None
        raise


async def lookup_release(mbid: str) -> dict[str, Any] | None:
    """Fetch a single release with its media/track/recording tree."""
    try:
        return await _get(f"release/{mbid}", {"inc": "recordings"})
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (400, 404):  # 400 = malformed MBID
            return None
        raise


async def lookup_recording(mbid: str) -> dict[str, Any] | None:
    try:
        return await _get(f"recording/{mbid}", {})
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (400, 404):  # 400 = malformed MBID
            return None
        raise
