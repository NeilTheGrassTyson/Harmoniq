import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import OptionalClerkId
from app.database import get_db
from app.schemas.catalog import AlbumDetail, ArtistDetail, SearchResponse, TrackDetail
from app.services import catalog as catalog_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["catalog"])

_CATALOG_ERROR = "Couldn't reach the music catalog right now. Try again in a moment."

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/search", response_model=SearchResponse)
async def search(
    session: DbSession,
    q: str = Query(min_length=2, description="Search query"),
) -> SearchResponse:
    try:
        return await catalog_svc.search_and_ingest(q, session)
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
async def get_artist(mbid: str, session: DbSession) -> ArtistDetail:
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
    return detail


@router.get("/albums/{mbid}", response_model=AlbumDetail)
async def get_album(
    mbid: str, session: DbSession, viewer_clerk_id: OptionalClerkId
) -> AlbumDetail:
    try:
        detail = await catalog_svc.get_album(mbid, session, viewer_clerk_id)
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
    return detail


@router.get("/tracks/{mbid}", response_model=TrackDetail)
async def get_track(
    mbid: str, session: DbSession, viewer_clerk_id: OptionalClerkId
) -> TrackDetail:
    try:
        detail = await catalog_svc.get_track(mbid, session, viewer_clerk_id)
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
    return detail
