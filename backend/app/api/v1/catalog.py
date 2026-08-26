import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.catalog import AlbumDetail, ArtistDetail, SearchResponse, TrackDetail
from app.services import catalog as catalog_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["catalog"])

_CATALOG_ERROR = "Couldn't reach the music catalog right now. Try again in a moment."

DbSession = Annotated[AsyncSession, Depends(get_db)]

# Every response in this module is viewer-independent catalog metadata, so all
# of it is publicly cacheable. Reviews are deliberately NOT part of these
# payloads — they are visibility-scoped per viewer and live behind
# GET /ratings/entity/{type}/{mbid}, which is never cached
# (ENGINEERING_BIBLE.md §8.1). Anything viewer-varying added here in future
# must drop the header, not just narrow it.
_CACHE_SEARCH = "public, max-age=120, stale-while-revalidate=600"
_CACHE_ARTIST = "public, max-age=300, stale-while-revalidate=3600"
_CACHE_DETAIL = "public, max-age=300, stale-while-revalidate=3600"


# Local-first: the session serves the Postgres query path. The MusicBrainz
# fallback still ingests via a background task with its own session, never
# on the response path.
@router.get("/search", response_model=SearchResponse)
async def search(
    session: DbSession,
    response: Response,
    q: str = Query(min_length=2, description="Search query"),
) -> SearchResponse:
    try:
        result = await catalog_svc.search(q, session)
        response.headers["Cache-Control"] = _CACHE_SEARCH
        return result
    except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.exception("MusicBrainz request failed during search")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_CATALOG_ERROR,
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during catalog search")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_CATALOG_ERROR,
        ) from exc


@router.get("/artists/{mbid}", response_model=ArtistDetail)
async def get_artist(mbid: str, session: DbSession, response: Response) -> ArtistDetail:
    try:
        detail = await catalog_svc.get_artist(mbid, session)
    except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.exception("MusicBrainz request failed for artist mbid=%s", mbid)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_CATALOG_ERROR,
        ) from exc
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artist not found."
        )
    response.headers["Cache-Control"] = _CACHE_ARTIST
    return detail


@router.get("/albums/{mbid}", response_model=AlbumDetail)
async def get_album(mbid: str, session: DbSession, response: Response) -> AlbumDetail:
    try:
        detail = await catalog_svc.get_album(mbid, session)
    except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.exception("MusicBrainz request failed for album mbid=%s", mbid)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_CATALOG_ERROR,
        ) from exc
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Album not found."
        )
    response.headers["Cache-Control"] = _CACHE_DETAIL
    return detail


@router.get("/tracks/{mbid}", response_model=TrackDetail)
async def get_track(mbid: str, session: DbSession, response: Response) -> TrackDetail:
    try:
        detail = await catalog_svc.get_track(mbid, session)
    except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.exception("MusicBrainz request failed for track mbid=%s", mbid)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_CATALOG_ERROR,
        ) from exc
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Track not found."
        )
    response.headers["Cache-Control"] = _CACHE_DETAIL
    return detail
