"""
Listens service: durable recent listening (specs/phase-2-listen-history.md).

Merge, never replace. An observed window is unioned with stored rows and
trimmed to the newest 20, so an empty or failed provider response can never
blank a profile — the bug this feature exists to fix.

The boundary: Spotify forbids using its data to train or inform
recommendations. Provider rows exist for display only.
`first_party_listens` is the one accessor recommendation, similarity or
trending code may use, and it cannot return a provider-sourced row.
"""

import asyncio
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Track
from app.models.listen import Listen
from app.services import catalog as catalog_svc
from app.services import musicbrainz as mb

logger = logging.getLogger(__name__)

STORED_LIMIT = 20
FIRST_PARTY_SOURCE = "harmoniq"
# MusicBrainz is shared at 1 request/second with search; linking is a
# background nicety, so each refresh resolves only a few ISRCs.
_LINKS_PER_REFRESH = 3
_LINK_TIMEOUT_SECONDS = 4


@dataclass(frozen=True)
class ObservedListen:
    source: str
    idempotency_key: str
    track_name: str
    artist_name: str
    album_name: str | None = None
    album_art_url: str | None = None
    provider_url: str | None = None
    isrc: str | None = None
    played_at: datetime | None = None


def _now() -> datetime:
    return datetime.now(tz=UTC)


_recency = func.coalesce(Listen.played_at, Listen.observed_at)


async def record(
    session: AsyncSession, user_id: uuid.UUID, observed: list[ObservedListen]
) -> None:
    """Merge an observed window into storage. Idempotent; an empty window is
    a no-op, never a deletion."""
    if not observed:
        return
    now = _now()
    stmt = (
        pg_insert(Listen)
        .values(
            [
                {
                    **asdict(o),
                    "id": uuid.uuid4(),
                    "user_id": user_id,
                    "observed_at": now,
                }
                for o in observed
            ]
        )
        .on_conflict_do_nothing(constraint="uq_listens_observation")
    )
    await session.execute(stmt)
    newest = (
        select(Listen.id)
        .where(Listen.user_id == user_id)
        .order_by(_recency.desc(), Listen.id)
        .limit(STORED_LIMIT)
    )
    await session.execute(
        delete(Listen).where(Listen.user_id == user_id, Listen.id.not_in(newest))
    )


async def recent_for_display(
    session: AsyncSession, user_id: uuid.UUID
) -> list[tuple[Listen, str | None]]:
    """Newest first, with the linked catalog track's MBID when known.
    Callers must have already applied visibility_activity."""
    rows = await session.execute(
        select(Listen, Track.mbid)
        .outerjoin(Track, Track.id == Listen.track_id)
        .where(Listen.user_id == user_id)
        .order_by(_recency.desc(), Listen.id)
        .limit(STORED_LIMIT)
    )
    return [(listen, mbid) for listen, mbid in rows.all()]


async def forget(
    session: AsyncSession, user_id: uuid.UUID, source: str | None = None
) -> None:
    """Delete a user's stored listens — all of them, or one source's."""
    stmt = delete(Listen).where(Listen.user_id == user_id)
    if source is not None:
        stmt = stmt.where(Listen.source == source)
    await session.execute(stmt)
    logger.info(
        "Listens deleted: user_id=%s source=%s", user_id, source or "all sources"
    )


async def first_party_listens(
    session: AsyncSession, user_id: uuid.UUID
) -> list[Listen]:
    """The ONLY accessor recommendation, similarity or trending code may use.
    Provider-sourced rows are unreachable through it by construction."""
    rows = await session.execute(
        select(Listen).where(
            Listen.user_id == user_id, Listen.source == FIRST_PARTY_SOURCE
        )
    )
    return list(rows.scalars())


async def link_some(session: AsyncSession, limit: int = _LINKS_PER_REFRESH) -> int:
    """Link a few unlinked listens to catalog tracks by ISRC. A listen that
    can't be linked stays a snapshot; only a definite answer is recorded, so
    an outage is retried on a later refresh. Returns the ISRCs settled."""
    pending = await session.execute(
        select(Listen.isrc)
        .where(
            Listen.track_id.is_(None),
            Listen.isrc.is_not(None),
            Listen.link_checked_at.is_(None),
        )
        .distinct()
        .limit(limit)
    )
    settled = 0
    for isrc in pending.scalars():
        if isrc is None:  # pragma: no cover — filtered in the query
            continue
        try:
            # A savepoint per ISRC, so a failed ingestion rolls back only
            # its own writes and the session stays usable for the next one.
            async with session.begin_nested():
                track_id = await _resolve_isrc(session, isrc)
        except (httpx.HTTPError, TimeoutError):
            logger.info("ISRC link deferred: isrc=%s", isrc)
            continue
        except Exception:
            # Not an outage: retrying would fail the same way on every
            # refresh, so record it as settled-without-a-link.
            logger.exception("ISRC link failed, not retrying: isrc=%s", isrc)
            track_id = None
        await session.execute(
            update(Listen)
            .where(Listen.isrc == isrc, Listen.track_id.is_(None))
            .values(track_id=track_id, link_checked_at=_now())
        )
        settled += 1
    return settled


async def _resolve_isrc(session: AsyncSession, isrc: str) -> uuid.UUID | None:
    # Only the lookup is bounded: once a recording is found, ingestion and
    # the database work run to completion rather than being cut off midway.
    async with asyncio.timeout(_LINK_TIMEOUT_SECONDS):
        data = await mb.lookup_isrc(isrc)
    recordings = (data or {}).get("recordings") or []
    if not recordings or not recordings[0].get("id"):
        return None
    mbid = str(recordings[0]["id"])
    # Ingests the recording into the catalog if it isn't there yet.
    if await catalog_svc.get_track(mbid, session) is None:
        return None
    result = await session.execute(select(Track.id).where(Track.mbid == mbid))
    return result.scalar_one_or_none()
