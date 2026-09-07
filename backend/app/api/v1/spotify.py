"""
Spotify API: OAuth connect/callback/disconnect and the listening display.

Routes are thin — OAuth mechanics, token handling, and visibility
enforcement all live in app/services/spotify.py.
"""

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.v1.deps import CurrentUser, DbSession, OptionalClerkId
from app.core.rate_limit import limiter
from app.schemas.spotify import (
    ConnectUrlResponse,
    ListeningResponse,
    SpotifyCallbackRequest,
    SpotifyConnectionStatus,
)
from app.services import spotify as spotify_svc
from app.services import user as user_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/spotify", tags=["spotify"])

_NOT_CONFIGURED = "Spotify integration isn't available right now."
_CALLBACK_ERROR = "Couldn't connect your Spotify account. Try again."
_LISTENING_PRIVATE = "Listening activity is private."


# ── Connect URL ───────────────────────────────────────────────────────────────


@router.get("/connect-url", response_model=ConnectUrlResponse)
async def get_connect_url(current_user: CurrentUser) -> ConnectUrlResponse:
    try:
        url = spotify_svc.build_authorize_url(current_user.id)
    except spotify_svc.SpotifyNotConfiguredError as exc:
        # The exception names which variables are missing; the 503 body
        # deliberately does not, so without this line the operator sees a
        # bare "503" in the access log and nothing else. Deploy Logs are the
        # only place this can be answered from.
        logger.error("Spotify connect unavailable — %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_NOT_CONFIGURED
        ) from exc
    return ConnectUrlResponse(url=url)


# ── OAuth callback ────────────────────────────────────────────────────────────


@router.post("/callback", response_model=SpotifyConnectionStatus)
@limiter.limit("10/minute")
async def spotify_callback(
    request: Request,
    response: Response,
    req: SpotifyCallbackRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> SpotifyConnectionStatus:
    # Captured before the transaction can be rolled back. `rollback()`
    # expires every ORM object in the session (independent of
    # expire_on_commit), so reading an attribute afterwards issues a
    # refresh SELECT — sync IO in an async context, which raises
    # MissingGreenlet from inside the error handler and destroys the
    # original exception before it can be logged.
    user_id = current_user.id
    try:
        result = await spotify_svc.connect(session, current_user, req.code, req.state)
        await session.commit()
    except spotify_svc.SpotifyNotConfiguredError as exc:
        logger.error("Spotify callback unavailable — %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_NOT_CONFIGURED
        ) from exc
    except spotify_svc.SpotifyAPIError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=_CALLBACK_ERROR
        ) from exc
    except Exception as exc:
        await session.rollback()
        logger.exception("Spotify callback failed internal_id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_CALLBACK_ERROR
        ) from exc
    return result


# ── Connection status / disconnect ────────────────────────────────────────────


@router.get("/connection", response_model=SpotifyConnectionStatus)
async def get_connection_status(
    session: DbSession, current_user: CurrentUser
) -> SpotifyConnectionStatus:
    return await spotify_svc.get_status(session, current_user)


@router.delete("/connection", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_spotify(session: DbSession, current_user: CurrentUser) -> None:
    await spotify_svc.disconnect(session, current_user)
    await session.commit()


# ── Listening display ─────────────────────────────────────────────────────────


@router.get("/listening/{username}", response_model=ListeningResponse)
async def get_listening(
    username: str,
    session: DbSession,
    viewer_clerk_id: OptionalClerkId,
) -> ListeningResponse:
    profile_user = await user_svc.get_by_username(session, username)
    if profile_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    viewer = None
    if viewer_clerk_id:
        viewer = await user_svc.get_by_clerk_id(session, viewer_clerk_id)

    result = await spotify_svc.get_listening(session, profile_user, viewer)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=_LISTENING_PRIVATE
        )
    return result
