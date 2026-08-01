"""
Catalog service: ingestion, upsert, and data retrieval for music entities.

All three entity types (artist, album, track) are keyed on their MusicBrainz ID
(MBID) which is stored as a unique index alongside an internal UUID primary key.
Ingestion is always upsert-on-MBID: existing rows are updated, not duplicated.
"""

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, case, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.musicbrainz as mb
import app.services.rating as rating_svc
from app.config import settings
from app.database import AsyncSessionLocal
from app.models.catalog import Album, Artist, Track
from app.schemas.catalog import (
    AlbumDetail,
    AlbumResult,
    ArtistDetail,
    ArtistResult,
    SearchResponse,
    TrackDetail,
    TrackResult,
)
from app.services import user as user_svc

logger = logging.getLogger(__name__)

_SEARCH_CACHE_TTL = 300.0  # 5 minutes — matches MB client TTL
_search_cache: dict[str, tuple[float, SearchResponse]] = {}

# Discography sync freshness, keyed on artist MBID. Guards the whole browse +
# upsert pass, not just the HTTP fetch: a prolific artist has hundreds of
# release groups, and re-writing them on every page view is the expensive
# part, not the (already cached) MusicBrainz requests.
_DISCOGRAPHY_SYNC_TTL = 300.0
_discography_sync_cache: dict[str, float] = {}

# Search relevance filtering (specs/phase-1-catalog.md, Amendments 2026-07-05).
# MusicBrainz's `score` (0-100 Lucene relevance) is never surfaced by the raw
# client — thresholded and ranked here instead. Tunable later; not API-exposed.
_MIN_RELEVANCE_SCORE = 50
_MAX_RESULTS_PER_CATEGORY = 5

_CAA_URL = "https://coverartarchive.org/release-group/{mbid}/front"

_ALBUM_TYPE_MAP: dict[str, str] = {
    "album": "album",
    "single": "single",
    "ep": "ep",
    "compilation": "compilation",
    "broadcast": "other",
    "other": "other",
}

# Discography quality gate (Founder direction, 2026-07-07): only recorded
# singles, EPs, and albums belong on artist pages and in search. MusicBrainz
# marks live bootlegs, compilations, remixes, etc. as *secondary* types on a
# release group whose primary type still reads Album/Single/EP — so both
# axes must be checked. Excluded release groups are stored with
# album_type='other' so display queries can skip them without a delete
# (existing ratings may reference those rows).
_ALLOWED_PRIMARY_TYPES = frozenset({"album", "single", "ep"})
_EXCLUDED_SECONDARY_TYPES = frozenset(
    {
        "live",
        "compilation",
        "remix",
        "dj-mix",
        "mixtape/street",
        "demo",
        "soundtrack",
        "spokenword",
        "interview",
        "audiobook",
        "audio drama",
        "field recording",
    }
)
_DISPLAY_ALBUM_TYPES = ("album", "ep", "single")


def _secondary_types(raw: dict[str, Any]) -> set[str]:
    return {
        str(t).lower() for t in raw.get("secondary-types", []) if isinstance(t, str)
    }


def _is_standard_release_group(raw: dict[str, Any]) -> bool:
    """True for a plain recorded Album/EP/Single with no excluding secondary type."""
    primary = (raw.get("primary-type") or "").lower()
    if primary not in _ALLOWED_PRIMARY_TYPES:
        return False
    return not (_secondary_types(raw) & _EXCLUDED_SECONDARY_TYPES)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _parse_release_year(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        return int(date_str[:4])
    except (ValueError, IndexError):
        return None


def _primary_artist_name(raw: dict[str, Any]) -> str | None:
    artist_credits = raw.get("artist-credit", [])
    if artist_credits and isinstance(artist_credits[0], dict):
        artist = artist_credits[0].get("artist", {})
        return artist.get("name")  # type: ignore[no-any-return]
    return None


def _primary_artist_mbid(raw: dict[str, Any]) -> str | None:
    artist_credits = raw.get("artist-credit", [])
    if artist_credits and isinstance(artist_credits[0], dict):
        return artist_credits[0].get("artist", {}).get("id")  # type: ignore[no-any-return]
    return None


def _release_group_mbid(raw_recording: dict[str, Any]) -> str | None:
    """Extract the canonical release-group MBID from a recording."""
    releases = raw_recording.get("releases", [])
    if not releases:
        return None
    rg = releases[0].get("release-group", {})
    return rg.get("id")  # type: ignore[no-any-return]


def _alias_names(raw: dict[str, Any]) -> list[str]:
    """Extract alias display names from a MusicBrainz artist payload."""
    return [
        alias["name"]
        for alias in raw.get("aliases", [])
        if isinstance(alias, dict) and alias.get("name")
    ]


def _is_housekeeping_name(name: str) -> bool:
    """True for MusicBrainz bracketed placeholder names like '[unknown]', '[data]'."""
    return name.startswith("[") and name.endswith("]")


def _hit_score(raw: dict[str, Any]) -> int:
    """MusicBrainz 'score' is an int on some endpoints, a numeric string on
    others; missing or unparseable → 0 (no confidence, filtered out by the
    threshold rather than crashing)."""
    try:
        return int(raw.get("score", 0))
    except (TypeError, ValueError):
        return 0


def _filter_and_rank(
    raw_hits: list[dict[str, Any]],
    *,
    name_fn: Callable[[dict[str, Any]], str | None],
    type_check: Callable[[dict[str, Any]], bool] | None = None,
) -> list[dict[str, Any]]:
    """Drop housekeeping names and sub-threshold-relevance hits, sort by
    MusicBrainz score descending, and cap at _MAX_RESULTS_PER_CATEGORY."""
    filtered = []
    for hit in raw_hits:
        name = name_fn(hit) or ""
        if _is_housekeeping_name(name):
            continue
        if type_check is not None and not type_check(hit):
            continue
        if _hit_score(hit) < _MIN_RELEVANCE_SCORE:
            continue
        filtered.append(hit)
    filtered.sort(key=_hit_score, reverse=True)
    return filtered[:_MAX_RESULTS_PER_CATEGORY]


# ── Upsert helpers ─────────────────────────────────────────────────────────────


async def _upsert_artist(session: AsyncSession, raw: dict[str, Any]) -> Artist:
    mbid: str = raw["id"]
    now = _now()

    result = await session.execute(select(Artist).where(Artist.mbid == mbid))
    artist = result.scalar_one_or_none()

    name = raw.get("name") or ""
    sort_name = raw.get("sort-name") or None
    disambiguation = raw.get("disambiguation") or None
    aliases = _alias_names(raw) or None

    if artist is None:
        artist = Artist(
            id=uuid.uuid4(),
            mbid=mbid,
            name=name,
            sort_name=sort_name,
            disambiguation=disambiguation,
            aliases=aliases,
            image_url=None,
            last_fetched_at=now,
        )
        session.add(artist)
    else:
        artist.name = name
        artist.sort_name = sort_name
        artist.disambiguation = disambiguation
        # Lookup responses omit aliases entirely (no inc=aliases); only
        # overwrite when MB actually sent the key so a detail-page refresh
        # doesn't wipe aliases ingested via search.
        if "aliases" in raw:
            artist.aliases = aliases
        artist.last_fetched_at = now

    return artist


def _album_fields(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a MusicBrainz release-group payload to Album column values."""
    raw_type = (raw.get("primary-type") or "").lower()
    if raw_type and not _is_standard_release_group(raw):
        # Live/compilation/remix etc. — kept in the DB (ratings may point at
        # it) but demoted out of the display types.
        album_type: str | None = "other"
    else:
        album_type = _ALBUM_TYPE_MAP.get(raw_type, "other") if raw_type else None
    return {
        "title": raw.get("title") or "",
        "release_year": _parse_release_year(
            raw.get("first-release-date") or raw.get("date")
        ),
        "album_type": album_type,
        "cover_art_url": _CAA_URL.format(mbid=raw["id"]),
    }


def _apply_album(
    album: Album | None,
    raw: dict[str, Any],
    artist_id: uuid.UUID | None,
    now: datetime,
) -> Album:
    """Create a new Album from the raw payload, or refresh an existing one.
    A new object still needs session.add()."""
    fields = _album_fields(raw)
    if album is None:
        return Album(
            id=uuid.uuid4(),
            mbid=raw["id"],
            artist_id=artist_id,
            last_fetched_at=now,
            **fields,
        )
    album.title = fields["title"]
    album.release_year = fields["release_year"]
    album.album_type = fields["album_type"]
    album.cover_art_url = fields["cover_art_url"]
    album.last_fetched_at = now
    if artist_id is not None and album.artist_id is None:
        album.artist_id = artist_id
    return album


async def _upsert_album(
    session: AsyncSession,
    raw: dict[str, Any],
    artist_id: uuid.UUID | None = None,
) -> Album:
    mbid: str = raw["id"]

    result = await session.execute(select(Album).where(Album.mbid == mbid))
    existing = result.scalar_one_or_none()

    album = _apply_album(existing, raw, artist_id, _now())
    if existing is None:
        session.add(album)
    return album


async def _upsert_track(
    session: AsyncSession,
    raw: dict[str, Any],
    artist_id: uuid.UUID | None = None,
    album_id: uuid.UUID | None = None,
    track_number: int | None = None,
    disc_number: int | None = None,
) -> Track:
    mbid: str = raw["id"]
    now = _now()

    result = await session.execute(select(Track).where(Track.mbid == mbid))
    track = result.scalar_one_or_none()

    title = raw.get("title") or ""
    duration_ms: int | None = raw.get("length")

    if track is None:
        track = Track(
            id=uuid.uuid4(),
            mbid=mbid,
            title=title,
            artist_id=artist_id,
            album_id=album_id,
            duration_ms=duration_ms,
            track_number=track_number,
            disc_number=disc_number,
            last_fetched_at=now,
        )
        session.add(track)
    else:
        track.title = title
        track.duration_ms = duration_ms
        track.last_fetched_at = now
        if artist_id is not None and track.artist_id is None:
            track.artist_id = artist_id
        if album_id is not None and track.album_id is None:
            track.album_id = album_id
        if track_number is not None:
            track.track_number = track_number
        if disc_number is not None:
            track.disc_number = disc_number

    return track


# ── Artist resolution helper ───────────────────────────────────────────────────


async def _resolve_artist_id(
    session: AsyncSession, artist_mbid: str | None, raw_artist: dict[str, Any] | None
) -> uuid.UUID | None:
    """
    Given a MusicBrainz artist MBID, return the internal UUID, ingesting the
    artist if needed. Returns None when the MBID is absent.
    """
    if not artist_mbid:
        return None
    result = await session.execute(select(Artist).where(Artist.mbid == artist_mbid))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing.id
    if raw_artist:
        ingested = await _upsert_artist(session, raw_artist)
        return ingested.id
    return None


# ── Search ─────────────────────────────────────────────────────────────────────

# Background ingest tasks hold their own session and commit independently of
# any request. The lock serializes them: search ingestion is cache-warming,
# not response data, so there is no reason to hold multiple Neon connections
# for it — and serializing avoids duplicate-MBID insert races between
# overlapping searches. The set keeps strong references so tasks aren't
# garbage-collected mid-flight.
_ingest_lock = asyncio.Lock()
_ingest_tasks: set[asyncio.Task[None]] = set()


def _schedule_ingest(
    raw_artists: list[dict[str, Any]],
    raw_albums: list[dict[str, Any]],
    raw_tracks: list[dict[str, Any]],
) -> None:
    task = asyncio.create_task(
        _ingest_in_background(raw_artists, raw_albums, raw_tracks)
    )
    _ingest_tasks.add(task)
    task.add_done_callback(_ingest_tasks.discard)


async def wait_for_pending_ingests() -> None:
    """Await any scheduled background ingests. For scripts and tests that
    need search ingestion to have completed before touching the same rows."""
    if _ingest_tasks:
        await asyncio.gather(*list(_ingest_tasks))


async def _ingest_in_background(
    raw_artists: list[dict[str, Any]],
    raw_albums: list[dict[str, Any]],
    raw_tracks: list[dict[str, Any]],
) -> None:
    async with _ingest_lock:
        try:
            async with AsyncSessionLocal() as session:
                await _ingest_search_results(
                    session, raw_artists, raw_albums, raw_tracks
                )
                await session.commit()
        except Exception:
            # Best-effort by design: the response was already served from the
            # MusicBrainz payload; a failed ingest only delays local caching
            # until the next search or detail-page visit.
            logger.exception("Background ingest of search results failed")


async def _ingest_search_results(
    session: AsyncSession,
    raw_artists: list[dict[str, Any]],
    raw_albums: list[dict[str, Any]],
    raw_tracks: list[dict[str, Any]],
) -> None:
    # ── Ingest artists ────────────────────────────────────────────────────────
    for raw in raw_artists:
        try:
            await _upsert_artist(session, raw)
        except Exception:
            logger.error(
                "Failed to ingest artist mbid=%s", raw.get("id"), exc_info=True
            )

    # ── Ingest albums ─────────────────────────────────────────────────────────
    for raw in raw_albums:
        try:
            artist_mbid = _primary_artist_mbid(raw)
            raw_artist_credit = (
                raw.get("artist-credit", [{}])[0].get("artist")
                if raw.get("artist-credit")
                else None
            )
            artist_id = await _resolve_artist_id(
                session, artist_mbid, raw_artist_credit
            )
            await _upsert_album(session, raw, artist_id)
        except Exception:
            logger.error("Failed to ingest album mbid=%s", raw.get("id"), exc_info=True)

    # ── Ingest tracks ─────────────────────────────────────────────────────────
    for raw in raw_tracks:
        try:
            artist_mbid = _primary_artist_mbid(raw)
            raw_artist_credit = (
                raw.get("artist-credit", [{}])[0].get("artist")
                if raw.get("artist-credit")
                else None
            )
            artist_id = await _resolve_artist_id(
                session, artist_mbid, raw_artist_credit
            )

            rg_mbid = _release_group_mbid(raw)
            album_id: uuid.UUID | None = None
            if rg_mbid:
                alb_result = await session.execute(
                    select(Album).where(Album.mbid == rg_mbid)
                )
                alb = alb_result.scalar_one_or_none()
                album_id = alb.id if alb else None

            await _upsert_track(session, raw, artist_id, album_id)
        except Exception:
            logger.error("Failed to ingest track mbid=%s", raw.get("id"), exc_info=True)

    await session.flush()


async def search_and_ingest(query: str) -> SearchResponse:
    cache_key = query.strip().lower()
    cached = _search_cache.get(cache_key)
    if cached is not None:
        cached_at, response = cached
        if time.monotonic() - cached_at < _SEARCH_CACHE_TTL:
            logger.debug("search cache hit: %s", cache_key)
            return response
        logger.debug("search cache stale: %s", cache_key)

    raw_artists: list[dict[str, Any]] = []
    raw_albums: list[dict[str, Any]] = []
    raw_tracks: list[dict[str, Any]] = []
    try:
        raw_artists = await mb.search_artists(query)
        raw_albums = await mb.search_release_groups(query)
        raw_tracks = await mb.search_recordings(query)
    except Exception:
        logger.exception("MusicBrainz search failed for query (redacted in prod)")
        raise

    # Strip MusicBrainz "Special Purpose" housekeeping entries ([unknown],
    # [no artist], etc.) and low-relevance noise; rank by score and cap per
    # category (specs/phase-1-catalog.md, Amendments 2026-07-05). Albums and
    # tracks are filtered on their *artist-credit* name — a legitimately
    # titled release by a "[unknown]" artist is the same housekeeping problem
    # the artist filter already catches, just one level deeper.
    raw_artists = _filter_and_rank(
        raw_artists,
        name_fn=lambda a: a.get("name"),
        type_check=lambda a: a.get("type") != "Special Purpose",
    )
    # Albums must be standard recorded releases (no live/compilation/etc.);
    # tracks must be audio recordings, not videos.
    raw_albums = _filter_and_rank(
        raw_albums,
        name_fn=_primary_artist_name,
        type_check=_is_standard_release_group,
    )
    raw_tracks = _filter_and_rank(
        raw_tracks,
        name_fn=_primary_artist_name,
        type_check=lambda t: not t.get("video"),
    )

    # Ingestion happens off the response path: it never feeds the response
    # below (built from the raw MusicBrainz payload), and measured 3-4.5s of
    # sequential Neon round-trips when it ran inline.
    if raw_artists or raw_albums or raw_tracks:
        _schedule_ingest(raw_artists, raw_albums, raw_tracks)

    # ── Build response from raw MB data (no extra DB round-trip) ─────────────
    artist_results = [
        ArtistResult(
            mbid=a.get("id", ""),
            name=a.get("name", ""),
            disambiguation=a.get("disambiguation") or None,
            image_url=None,
        )
        for a in raw_artists
    ]

    album_results = [
        AlbumResult(
            mbid=a.get("id", ""),
            title=a.get("title", ""),
            artist_name=_primary_artist_name(a),
            release_year=_parse_release_year(a.get("first-release-date")),
            album_type=_ALBUM_TYPE_MAP.get((a.get("primary-type") or "").lower()),
            cover_art_url=_CAA_URL.format(mbid=a.get("id", "")),
        )
        for a in raw_albums
    ]

    track_results = [
        TrackResult(
            mbid=t.get("id", ""),
            title=t.get("title", ""),
            artist_name=_primary_artist_name(t),
            album_title=(
                t.get("releases", [{}])[0].get("title") if t.get("releases") else None
            ),
            album_mbid=_release_group_mbid(t),
            duration_ms=t.get("length"),
        )
        for t in raw_tracks
    ]

    result = SearchResponse(
        artists=artist_results,
        albums=album_results,
        tracks=track_results,
    )
    _search_cache[cache_key] = (time.monotonic(), result)
    return result


# ── Local-first search (specs/local-first-search.md, approved 2026-08-01) ─────

# A query "strongly" matches an artist at this trigram similarity; that
# artist's own albums and tracks then populate those categories (entity-aware
# ranking — the fix for title-match junk on artist-name queries).
_STRONG_ARTIST_SIMILARITY = 0.4
# Local results below this total (with no strong artist) are "thin" and fall
# back to MusicBrainz.
_MIN_LOCAL_RESULTS = 3
# An exact prefix match ranks near the top even when the query is a short
# fragment with weak trigram overlap ("rad" → "Radiohead").
_PREFIX_BOOST = 0.9
# Title-similarity candidacy for albums/tracks rides on the `%` operator,
# which enforces pg_trgm's similarity_threshold (default 0.3) and is the
# form the GIN trigram indexes accelerate.


def _not_housekeeping(column: Any) -> Any:
    """SQL predicate mirroring _is_housekeeping_name for local rows."""
    return not_(and_(column.like("[%"), column.like("%]")))


async def search(query: str, session: AsyncSession) -> SearchResponse:
    """Local-first search: serve from Postgres when the catalog can answer,
    fall back to MusicBrainz (which background-ingests, widening the local
    catalog) when results are thin."""
    cache_key = query.strip().lower()
    cached = _search_cache.get(cache_key)
    if cached is not None:
        cached_at, response = cached
        if time.monotonic() - cached_at < _SEARCH_CACHE_TTL:
            logger.debug("search cache hit: %s", cache_key)
            return response

    if settings.search_local_first:
        local = await _search_local(session, query)
        if local is not None:
            _search_cache[cache_key] = (time.monotonic(), local)
            return local

    return await search_and_ingest(query)


async def _search_local(session: AsyncSession, query: str) -> SearchResponse | None:
    """Query the local catalog. Returns None when results are too thin to
    serve (the caller then falls back to MusicBrainz)."""
    q = query.strip()
    if not q:
        return None

    # ── Artists: trigram on name + flattened aliases, prefix-boosted ─────────
    alias_text = func.array_to_string(Artist.aliases, " ")
    # LIKE wildcards in user input are literal characters, not patterns —
    # the trigram operators treat them literally already.
    escaped = q.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    prefix = escaped + "%"
    score = func.greatest(
        func.similarity(Artist.name, q),
        func.similarity(alias_text, q),
        case(
            (func.lower(Artist.name).like(prefix, escape="\\"), _PREFIX_BOOST),
            else_=0.0,
        ),
    ).label("score")

    artist_rows = (
        await session.execute(
            select(Artist, score)
            .where(
                or_(
                    Artist.name.op("%")(q),
                    func.lower(Artist.name).like(prefix, escape="\\"),
                    alias_text.op("%")(q),
                ),
                _not_housekeeping(Artist.name),
            )
            .order_by(score.desc(), Artist.name.asc())
            .limit(_MAX_RESULTS_PER_CATEGORY)
        )
    ).all()

    strong_ids = [
        artist.id
        for artist, sim in artist_rows
        if sim is not None and sim >= _STRONG_ARTIST_SIMILARITY
    ]

    # ── Albums: the matched artists' own releases, or title matches ──────────
    # On a strong artist match the category is relationship-only: padding a
    # sparse discography with title-similarity hits would re-admit exactly
    # the "release titled like the artist" junk this path exists to kill
    # (verified live 2026-08-01: seeded artists without local tracklists got
    # title-junk tracks under the union approach).
    album_rows: list[tuple[Album, str | None]] = []
    if strong_ids:
        album_rows = [
            (album, artist_name)
            for album, artist_name in (
                await session.execute(
                    select(Album, Artist.name)
                    .join(Artist, Album.artist_id == Artist.id)
                    .where(
                        Album.artist_id.in_(strong_ids),
                        Album.album_type.in_(_DISPLAY_ALBUM_TYPES),
                    )
                    .order_by(Album.release_year.desc().nulls_last(), Album.title.asc())
                    .limit(_MAX_RESULTS_PER_CATEGORY)
                )
            ).all()
        ]
    else:
        album_rows = [
            (album, artist_name)
            for album, artist_name in (
                await session.execute(
                    select(Album, Artist.name)
                    .outerjoin(Artist, Album.artist_id == Artist.id)
                    .where(
                        Album.title.op("%")(q),
                        Album.album_type.in_(_DISPLAY_ALBUM_TYPES),
                        or_(
                            Artist.name.is_(None),
                            _not_housekeeping(Artist.name),
                        ),
                    )
                    .order_by(func.similarity(Album.title, q).desc(), Album.title.asc())
                    .limit(_MAX_RESULTS_PER_CATEGORY)
                )
            ).all()
        ]

    # ── Tracks: same relationship-or-title shape as albums ───────────────────
    track_cols = (Track, Artist.name, Album.title, Album.mbid)
    track_rows: list[tuple[Track, str | None, str | None, str | None]] = []
    if strong_ids:
        track_rows = [
            tuple(row)
            for row in (
                await session.execute(
                    select(*track_cols)
                    .join(Artist, Track.artist_id == Artist.id)
                    .outerjoin(Album, Track.album_id == Album.id)
                    .where(Track.artist_id.in_(strong_ids))
                    .order_by(
                        Album.release_year.desc().nulls_last(),
                        Track.disc_number.asc().nulls_last(),
                        Track.track_number.asc().nulls_last(),
                        Track.title.asc(),
                    )
                    .limit(_MAX_RESULTS_PER_CATEGORY)
                )
            ).all()
        ]
    else:
        track_rows = [
            tuple(row)
            for row in (
                await session.execute(
                    select(*track_cols)
                    .outerjoin(Artist, Track.artist_id == Artist.id)
                    .outerjoin(Album, Track.album_id == Album.id)
                    .where(
                        Track.title.op("%")(q),
                        or_(
                            Artist.name.is_(None),
                            _not_housekeeping(Artist.name),
                        ),
                    )
                    .order_by(func.similarity(Track.title, q).desc(), Track.title.asc())
                    .limit(_MAX_RESULTS_PER_CATEGORY)
                )
            ).all()
        ]

    # A strong artist match with no local releases is a half-ingested artist
    # (e.g. a failed discography sync during seeding): a bare artist row
    # would render worse than the MusicBrainz fallback, which also
    # re-ingests and heals the gap.
    if strong_ids and not album_rows and not track_rows:
        return None

    total = len(artist_rows) + len(album_rows) + len(track_rows)
    if not strong_ids and total < _MIN_LOCAL_RESULTS:
        return None

    return SearchResponse(
        artists=[
            ArtistResult(
                mbid=artist.mbid,
                name=artist.name,
                disambiguation=artist.disambiguation,
                image_url=artist.image_url,
            )
            for artist, _ in artist_rows
        ],
        albums=[
            AlbumResult(
                mbid=album.mbid,
                title=album.title,
                artist_name=artist_name,
                release_year=album.release_year,
                album_type=album.album_type,
                cover_art_url=album.cover_art_url,
            )
            for album, artist_name in album_rows
        ],
        tracks=[
            TrackResult(
                mbid=track.mbid,
                title=track.title,
                artist_name=artist_name,
                album_title=album_title,
                album_mbid=album_mbid,
                duration_ms=track.duration_ms,
            )
            for track, artist_name, album_title, album_mbid in track_rows
        ],
    )


# ── Discography sync ───────────────────────────────────────────────────────────


async def _sync_artist_discography(session: AsyncSession, artist: Artist) -> None:
    """Ingest the artist's full release-group list from MusicBrainz.

    Batched on purpose: one IN-query preloads every existing row, then a
    single flush writes all inserts/updates via executemany. Going through
    _upsert_album per release group issues a SELECT each (plus an autoflushed
    write), which measured ~80s for a prolific artist against Neon.
    Skipped entirely while the artist's sync is fresh.
    """
    last_synced = _discography_sync_cache.get(artist.mbid)
    if (
        last_synced is not None
        and time.monotonic() - last_synced < _DISCOGRAPHY_SYNC_TTL
    ):
        return

    raw_rgs = await mb.browse_release_groups(artist.mbid)
    by_mbid = {raw["id"]: raw for raw in raw_rgs if raw.get("id")}

    if by_mbid:
        result = await session.execute(
            select(Album).where(Album.mbid.in_(list(by_mbid)))
        )
        existing = {album.mbid: album for album in result.scalars()}

        now = _now()
        for rg_mbid, raw in by_mbid.items():
            album = _apply_album(existing.get(rg_mbid), raw, artist.id, now)
            if rg_mbid not in existing:
                session.add(album)
        await session.flush()

    _discography_sync_cache[artist.mbid] = time.monotonic()


# ── Tracklist sync ─────────────────────────────────────────────────────────────

_TRACKLIST_SYNC_TTL = 300.0
_tracklist_sync_cache: dict[str, float] = {}


def _pick_canonical_release(releases: list[dict[str, Any]]) -> str | None:
    """Choose the release whose tracklist represents the release group:
    prefer official status, then earliest date, then first listed."""
    if not releases:
        return None

    def sort_key(rel: dict[str, Any]) -> tuple[int, str]:
        official = 0 if (rel.get("status") or "").lower() == "official" else 1
        # ISO dates compare lexicographically; empty sorts last.
        date = rel.get("date") or "9999"
        return (official, date)

    best = min(releases, key=sort_key)
    return best.get("id")


async def _sync_album_tracklist(session: AsyncSession, album: Album) -> None:
    """Ingest the album's tracklist from its canonical MusicBrainz release.

    Skipped while fresh (TTL) so repeated album-page views don't re-hit
    MusicBrainz. Failures degrade to whatever tracks are already stored —
    the page renders without a tracklist rather than erroring.
    """
    last_synced = _tracklist_sync_cache.get(album.mbid)
    if last_synced is not None and time.monotonic() - last_synced < _TRACKLIST_SYNC_TTL:
        return

    raw_rg = await mb.lookup_release_group(album.mbid)
    if raw_rg is None:
        return
    release_mbid = _pick_canonical_release(raw_rg.get("releases", []))
    if release_mbid is None:
        return
    raw_release = await mb.lookup_release(release_mbid)
    if raw_release is None:
        return

    for medium in raw_release.get("media", []):
        disc_number = medium.get("position")
        for raw_track in medium.get("tracks", []):
            recording = raw_track.get("recording")
            if not recording or not recording.get("id"):
                continue
            # The track position/length live on the tracklist entry; the
            # recording payload carries the MBID and canonical title.
            merged = {**recording}
            if raw_track.get("length") and not merged.get("length"):
                merged["length"] = raw_track["length"]
            await _upsert_track(
                session,
                merged,
                artist_id=album.artist_id,
                album_id=album.id,
                track_number=raw_track.get("position"),
                disc_number=disc_number,
            )

    await session.flush()
    _tracklist_sync_cache[album.mbid] = time.monotonic()


# ── Detail views ───────────────────────────────────────────────────────────────


async def get_artist(mbid: str, session: AsyncSession) -> ArtistDetail | None:
    result = await session.execute(select(Artist).where(Artist.mbid == mbid))
    artist = result.scalar_one_or_none()

    if artist is None:
        raw = await mb.lookup_artist(mbid)
        if raw is None:
            return None
        artist = await _upsert_artist(session, raw)
        await session.flush()

    # Sync the full discography on demand (skipped while fresh, see
    # _sync_artist_discography). A sync failure degrades to whatever albums
    # are already stored locally rather than failing the page.
    try:
        await _sync_artist_discography(session, artist)
    except Exception:
        logger.error(
            "Failed to sync discography for artist mbid=%s", mbid, exc_info=True
        )

    # Display only standard recorded release groups, newest first. Demoted
    # rows (album_type='other'/'compilation'/NULL) stay in the DB for any
    # ratings that reference them but never render on the artist page.
    alb_result = await session.execute(
        select(Album)
        .where(
            Album.artist_id == artist.id,
            Album.album_type.in_(_DISPLAY_ALBUM_TYPES),
        )
        .order_by(Album.release_year.desc().nulls_last(), Album.title.asc())
    )
    albums = alb_result.scalars().all()

    return ArtistDetail(
        mbid=artist.mbid,
        name=artist.name,
        sort_name=artist.sort_name,
        disambiguation=artist.disambiguation,
        image_url=artist.image_url,
        albums=[
            AlbumResult(
                mbid=a.mbid,
                title=a.title,
                artist_name=artist.name,
                release_year=a.release_year,
                album_type=a.album_type,
                cover_art_url=a.cover_art_url,
            )
            for a in albums
        ],
    )


async def get_album(
    mbid: str, session: AsyncSession, viewer_clerk_id: str | None = None
) -> AlbumDetail | None:
    result = await session.execute(select(Album).where(Album.mbid == mbid))
    album = result.scalar_one_or_none()

    if album is None:
        raw = await mb.lookup_release_group(mbid)
        if raw is None:
            return None
        artist_mbid = _primary_artist_mbid(raw)
        raw_artist_credit = (
            raw.get("artist-credit", [{}])[0].get("artist")
            if raw.get("artist-credit")
            else None
        )
        artist_id = await _resolve_artist_id(session, artist_mbid, raw_artist_credit)
        album = await _upsert_album(session, raw, artist_id)
        await session.flush()

    # Sync the tracklist on demand (TTL-guarded). A failure degrades to the
    # locally stored tracks rather than failing the page.
    try:
        await _sync_album_tracklist(session, album)
    except Exception:
        logger.error("Failed to sync tracklist for album mbid=%s", mbid, exc_info=True)

    # Resolve artist name for response
    artist_name: str | None = None
    artist_mbid_out: str | None = None
    if album.artist_id is not None:
        art_result = await session.execute(
            select(Artist).where(Artist.id == album.artist_id)
        )
        art = art_result.scalar_one_or_none()
        if art:
            artist_name = art.name
            artist_mbid_out = art.mbid

    trk_result = await session.execute(
        select(Track)
        .where(Track.album_id == album.id)
        .order_by(
            Track.disc_number.asc().nulls_last(),
            Track.track_number.asc().nulls_last(),
            Track.title.asc(),
        )
    )
    tracks = trk_result.scalars().all()

    viewer_id = None
    if viewer_clerk_id:
        viewer = await user_svc.get_by_clerk_id(session, viewer_clerk_id)
        if viewer:
            viewer_id = viewer.id
    ratings = await rating_svc.list_for_entity(session, "album", album.id, viewer_id)

    return AlbumDetail(
        mbid=album.mbid,
        title=album.title,
        artist_name=artist_name,
        artist_mbid=artist_mbid_out,
        release_year=album.release_year,
        album_type=album.album_type,
        cover_art_url=album.cover_art_url,
        tracks=[
            TrackResult(
                mbid=t.mbid,
                title=t.title,
                artist_name=artist_name,
                album_title=album.title,
                album_mbid=album.mbid,
                duration_ms=t.duration_ms,
            )
            for t in tracks
        ],
        aggregate_score=ratings.aggregate_score,
        reviews=ratings.reviews,
    )


async def get_track(
    mbid: str, session: AsyncSession, viewer_clerk_id: str | None = None
) -> TrackDetail | None:
    result = await session.execute(select(Track).where(Track.mbid == mbid))
    track = result.scalar_one_or_none()

    if track is None:
        raw = await mb.lookup_recording(mbid)
        if raw is None:
            return None
        artist_mbid = _primary_artist_mbid(raw)
        raw_artist_credit = (
            raw.get("artist-credit", [{}])[0].get("artist")
            if raw.get("artist-credit")
            else None
        )
        artist_id = await _resolve_artist_id(session, artist_mbid, raw_artist_credit)
        rg_mbid = _release_group_mbid(raw)
        album_id: uuid.UUID | None = None
        if rg_mbid:
            alb_r = await session.execute(select(Album).where(Album.mbid == rg_mbid))
            alb = alb_r.scalar_one_or_none()
            album_id = alb.id if alb else None
        track = await _upsert_track(session, raw, artist_id, album_id)
        await session.flush()

    artist_name: str | None = None
    artist_mbid_out: str | None = None
    if track.artist_id is not None:
        art_r = await session.execute(
            select(Artist).where(Artist.id == track.artist_id)
        )
        art = art_r.scalar_one_or_none()
        if art:
            artist_name = art.name
            artist_mbid_out = art.mbid

    album_title: str | None = None
    album_mbid_out: str | None = None
    cover_art_url: str | None = None
    if track.album_id is not None:
        alb_r = await session.execute(select(Album).where(Album.id == track.album_id))
        alb = alb_r.scalar_one_or_none()
        if alb:
            album_title = alb.title
            album_mbid_out = alb.mbid
            cover_art_url = alb.cover_art_url

    viewer_id = None
    if viewer_clerk_id:
        viewer = await user_svc.get_by_clerk_id(session, viewer_clerk_id)
        if viewer:
            viewer_id = viewer.id
    ratings = await rating_svc.list_for_entity(session, "track", track.id, viewer_id)

    return TrackDetail(
        mbid=track.mbid,
        title=track.title,
        artist_name=artist_name,
        artist_mbid=artist_mbid_out,
        album_title=album_title,
        album_mbid=album_mbid_out,
        cover_art_url=cover_art_url,
        duration_ms=track.duration_ms,
        track_number=track.track_number,
        disc_number=track.disc_number,
        aggregate_score=ratings.aggregate_score,
        reviews=ratings.reviews,
    )
