"""Public recording links only. Never fetch or redirect through arbitrary URLs."""

import asyncio
import re
import time
from collections import OrderedDict
from urllib.parse import parse_qs, quote, urlencode, urlsplit, urlunsplit

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Artist, Track
from app.schemas.streaming import Provider, StreamingLink, StreamingResponse
from app.services import musicbrainz

PROVIDERS: dict[Provider, str] = {
    "spotify": "Spotify",
    "apple": "Apple Music",
    "youtube": "YouTube Music",
    "tidal": "TIDAL",
    "deezer": "Deezer",
    "amazon": "Amazon Music",
}
_AMAZON_HOSTS = frozenset(
    "music.amazon." + suffix
    for suffix in (
        "com",
        "co.uk",
        "de",
        "fr",
        "it",
        "es",
        "co.jp",
        "com.au",
        "ca",
        "com.br",
        "in",
        "com.mx",
    )
)
_CACHE_LIMIT = 1000
_CACHE_TTL = 21600.0
_INFLIGHT_LIMIT = 32
_cache: OrderedDict[str, tuple[float, dict[Provider, str]]] = OrderedDict()
_inflight: dict[str, asyncio.Task[dict[Provider, str] | None]] = {}


def exact_link(raw: str) -> tuple[Provider, str] | None:
    """Normalize a known song route, removing tracking/redirect parameters.

    URL parsing alone is insufficient: reject control characters, escapes in
    paths, userinfo, ports and ambiguous IDs before allowing browser navigation.
    """
    if (
        len(raw) > 2048
        or any(ord(c) <= 32 or ord(c) == 127 for c in raw)
        or "\\" in raw
    ):
        return None
    try:
        url = urlsplit(raw)
        if (
            url.scheme != "https"
            or url.username
            or url.password
            or url.port is not None
        ):
            return None
    except ValueError:
        return None
    host, path = url.netloc, url.path
    query = parse_qs(url.query)
    provider: Provider
    clean_query = ""
    if host == "open.spotify.com" and re.fullmatch(
        r"/(?:intl-[a-z]{2}/)?track/[A-Za-z0-9]{22}", path
    ):
        provider = "spotify"
        path = "/track/" + path.rsplit("/", 1)[1]
    elif host == "music.apple.com" and re.fullmatch(
        r"/[a-z]{2}/song/(?:[^/%]+/)?[0-9]+", path
    ):
        provider = "apple"
    elif host == "music.apple.com" and re.fullmatch(
        r"/[a-z]{2}/album/(?:[^/%]+/)?[0-9]+", path
    ):
        ids = query.get("i", [])
        if len(ids) != 1 or not re.fullmatch(r"[0-9]+", ids[0]):
            return None  # an album by itself is never a track match
        provider = "apple"
        clean_query = urlencode({"i": ids[0]})
    elif host == "music.youtube.com" and path == "/watch":
        ids = query.get("v", [])
        if len(ids) != 1 or not re.fullmatch(r"[A-Za-z0-9_-]{11}", ids[0]):
            return None
        provider = "youtube"
        clean_query = urlencode({"v": ids[0]})
    elif host in ("tidal.com", "www.tidal.com", "listen.tidal.com") and re.fullmatch(
        r"/(?:browse/)?track/[0-9]+", path
    ):
        provider = "tidal"
        host = "tidal.com"
        path = "/track/" + path.rsplit("/", 1)[1]
    elif host in ("deezer.com", "www.deezer.com") and re.fullmatch(
        r"/(?:[a-z]{2}/)?track/[0-9]+", path
    ):
        provider = "deezer"
        host = "www.deezer.com"
        path = "/track/" + path.rsplit("/", 1)[1]
    elif host in _AMAZON_HOSTS and re.fullmatch(r"/tracks/[A-Z0-9]{10}", path):
        provider = "amazon"
    elif host in _AMAZON_HOSTS and re.fullmatch(r"/albums/[A-Z0-9]{10}", path):
        ids = query.get("trackAsin", [])
        if len(ids) != 1 or not re.fullmatch(r"[A-Z0-9]{10}", ids[0]):
            return None
        provider = "amazon"
        clean_query = urlencode({"trackAsin": ids[0]})
    else:
        return None
    return provider, urlunsplit(("https", host, path, clean_query, ""))


def search_links(title: str, artist: str | None) -> dict[Provider, str]:
    term = " ".join(part for part in (title, artist) if part)
    encoded = quote(term, safe="")
    return {
        "spotify": f"https://open.spotify.com/search/{encoded}",
        "apple": "https://music.apple.com/us/search?" + urlencode({"term": term}),
        "youtube": "https://music.youtube.com/search?" + urlencode({"q": term}),
        "tidal": "https://listen.tidal.com/search?" + urlencode({"q": term}),
        "deezer": f"https://www.deezer.com/search/{encoded}",
        "amazon": f"https://music.amazon.com/search/{encoded}",
    }


async def _lookup(mbid: str) -> dict[Provider, str] | None:
    try:
        async with asyncio.timeout(4):
            data = await musicbrainz.lookup_recording_links(mbid)
        if not isinstance(data, dict):
            return None
        relations = data.get("relations", [])
        if not isinstance(relations, list):
            return None
        matches: dict[Provider, set[str]] = {}
        for relation in relations:
            if not isinstance(relation, dict) or relation.get("target-type") != "url":
                continue
            if relation.get("type") not in ("streaming", "free streaming"):
                continue
            url = relation.get("url")
            raw = url.get("resource") if isinstance(url, dict) else None
            match = exact_link(raw) if isinstance(raw, str) else None
            if match:
                provider, clean = match
                matches.setdefault(provider, set()).add(clean)
        # Conflicting links are ambiguous; let the listener select in search.
        result = {
            provider: next(iter(urls))
            for provider, urls in matches.items()
            if len(urls) == 1
        }
        _cache[mbid] = (time.monotonic(), result)
        _cache.move_to_end(mbid)
        while len(_cache) > _CACHE_LIMIT:
            _cache.popitem(last=False)
        return result
    except (httpx.HTTPError, TimeoutError, ValueError, TypeError):
        return None
    finally:
        _inflight.pop(mbid, None)


async def mappings(mbid: str) -> dict[Provider, str] | None:
    cached = _cache.get(mbid)
    if cached and time.monotonic() - cached[0] < _CACHE_TTL:
        _cache.move_to_end(mbid)
        return cached[1]
    if mbid not in _inflight:
        if len(_inflight) >= _INFLIGHT_LIMIT:
            return None
        _inflight[mbid] = asyncio.create_task(_lookup(mbid))
    # A canceled page request must not cancel another caller's shared lookup.
    return await asyncio.shield(_inflight[mbid])


async def get_links(session: AsyncSession, mbid: str) -> StreamingResponse | None:
    row = (
        await session.execute(
            select(Track.title, Artist.name)
            .outerjoin(Artist, Artist.id == Track.artist_id)
            .where(Track.mbid == mbid)
        )
    ).one_or_none()
    if row is None:
        return None
    exact = await mappings(mbid)
    searches = search_links(row.title, row.name)
    return StreamingResponse(
        links=[
            StreamingLink(
                provider=provider,
                name=name,
                url=exact[provider]
                if exact and provider in exact
                else searches[provider],
                kind="exact" if exact and provider in exact else "search",
            )
            for provider, name in PROVIDERS.items()
        ],
        mapping_status="available" if exact is not None else "unavailable",
    )
