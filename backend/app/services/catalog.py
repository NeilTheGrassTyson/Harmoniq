"""
Catalog service: ingestion, upsert, and data retrieval for music entities.

All three entity types (artist, album, track) are keyed on their MusicBrainz ID
(MBID) which is stored as a unique index alongside an internal UUID primary key.
Ingestion is always upsert-on-MBID: existing rows are updated, not duplicated.
"""

import logging
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.musicbrainz as mb
import app.services.rating as rating_svc
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


async def search_and_ingest(query: str, session: AsyncSession) -> SearchResponse:
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

    # ── Ingest artists ────────────────────────────────────────────────────────
    artist_rows: list[Artist] = []
    for raw in raw_artists:
        try:
            artist_rows.append(await _upsert_artist(session, raw))
        except Exception:
            logger.error(
                "Failed to ingest artist mbid=%s", raw.get("id"), exc_info=True
            )

    # ── Ingest albums ─────────────────────────────────────────────────────────
    album_rows: list[Album] = []
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
            album_rows.append(await _upsert_album(session, raw, artist_id))
        except Exception:
            logger.error("Failed to ingest album mbid=%s", raw.get("id"), exc_info=True)

    # ── Ingest tracks ─────────────────────────────────────────────────────────
    track_rows: list[Track] = []
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

            track_rows.append(await _upsert_track(session, raw, artist_id, album_id))
        except Exception:
            logger.error("Failed to ingest track mbid=%s", raw.get("id"), exc_info=True)

    await session.flush()

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
