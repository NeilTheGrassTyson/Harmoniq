"""
Highlights API (specs/phase-2-highlights.md).

Reads are visibility-gated before anything is loaded; writes need an active
account. HIGHLIGHTS_ENABLED=false turns the whole surface off (404) while
keeping every row, and PLAYLIST_HIGHLIGHTS_ENABLED gates the playlist half on
its own.
"""

import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Request,
    Response,
    status,
)

from app.api.v1.deps import CurrentActiveUser, CurrentUser, DbSession, OptionalClerkId
from app.config import settings
from app.core.rate_limit import limiter
from app.schemas.highlight import (
    AddHighlightRequest,
    HighlightItem,
    HighlightsResponse,
    PlaylistPickerResponse,
)
from app.services import highlight as highlight_svc
from app.services import user as user_svc

router = APIRouter(prefix="/highlights", tags=["highlights"])

_PRIVATE = "Highlights are private."


def _require_enabled(response: Response) -> None:
    if not settings.highlights_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Highlights are unavailable.")
    response.headers["Cache-Control"] = "private, no-store"


@router.get("/playlists", response_model=PlaylistPickerResponse)
async def list_playlists(
    response: Response, session: DbSession, current_user: CurrentUser
) -> PlaylistPickerResponse:
    _require_enabled(response)
    return await highlight_svc.playlist_options(session, current_user)


@router.get("/user/{username}", response_model=HighlightsResponse)
async def get_highlights(
    username: str,
    response: Response,
    session: DbSession,
    viewer_clerk_id: OptionalClerkId,
    background: BackgroundTasks,
) -> HighlightsResponse:
    _require_enabled(response)
    owner = await user_svc.get_by_username(session, username)
    if owner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    viewer = (
        await user_svc.get_by_clerk_id(session, viewer_clerk_id)
        if viewer_clerk_id
        else None
    )
    result, refresh = await highlight_svc.list_for(session, owner, viewer)
    if result is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, _PRIVATE)
    if refresh:
        # Playlist cards follow Spotify, but a view never waits on it.
        background.add_task(highlight_svc.refresh_playlists_in_background, owner.id)
    return result


@router.post("", response_model=HighlightItem, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def add_highlight(
    request: Request,
    response: Response,
    req: AddHighlightRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> HighlightItem:
    _require_enabled(response)
    try:
        item = await highlight_svc.add(session, current_user, req)
    except highlight_svc.HighlightError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    await session.commit()
    return item


@router.delete("/{highlight_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def remove_highlight(
    request: Request,
    response: Response,
    highlight_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> None:
    _require_enabled(response)
    await highlight_svc.remove(session, current_user, highlight_id)
    await session.commit()
