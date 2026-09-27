import uuid

from fastapi import APIRouter, HTTPException, Request, Response

from app.api.v1.deps import DbSession
from app.config import settings
from app.core.rate_limit import limiter
from app.schemas.streaming import StreamingResponse
from app.services import streaming as streaming_svc

router = APIRouter(prefix="/streaming", tags=["streaming"])


@router.get("/{mbid}", response_model=StreamingResponse)
@limiter.limit("30/minute")
async def get_streaming_links(
    request: Request,
    response: Response,
    mbid: uuid.UUID,
    session: DbSession,
) -> StreamingResponse:
    if not settings.streaming_links_enabled:
        raise HTTPException(404, "Streaming links are unavailable.")
    result = await streaming_svc.get_links(session, str(mbid))
    if result is None:
        raise HTTPException(404, "Track not found.")
    response.headers["Cache-Control"] = (
        "public, max-age=300" if result.mapping_status == "available" else "no-store"
    )
    return result
