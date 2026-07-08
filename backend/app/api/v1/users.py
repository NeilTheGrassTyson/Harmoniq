import logging

import httpx
from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.v1.deps import (
    ClerkUserId,
    CurrentActiveUser,
    CurrentUser,
    DbSession,
    OptionalClerkId,
)
from app.config import settings
from app.core.rate_limit import limiter
from app.schemas.user import (
    AvatarUploadResponse,
    OnboardingRequest,
    OwnProfileResponse,
    ProfileResponse,
    ProfileUpdateRequest,
    UsernameCheckResponse,
    UserSearchResult,
)
from app.services import storage
from app.services import user as user_svc
from app.services.storage import StorageError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

_SAVE_ERROR = "Something went wrong. Your changes weren't saved."
_AVATAR_ERROR = "Couldn't upload your photo. Try again."


# ── Clerk Management API ──────────────────────────────────────────────────────


async def _mark_onboarded_in_clerk(clerk_id: str) -> None:
    """Sets publicMetadata.onboarded = true in Clerk so the JWT gate works."""
    if not settings.clerk_secret_key:
        logger.warning(
            "CLERK_SECRET_KEY not set — onboarding flag will not be synced to Clerk"
        )
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"https://api.clerk.com/v1/users/{clerk_id}",
                headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
                json={"public_metadata": {"onboarded": True}},
            )
            resp.raise_for_status()
    except Exception:
        # Non-fatal: the user record exists in our DB; the JWT will refresh
        # and pick up the flag on the next Clerk token issuance.
        logger.error(
            "Failed to set onboarded flag in Clerk — user record still created"
        )


# ── Onboarding ────────────────────────────────────────────────────────────────


@router.post(
    "/",
    response_model=OwnProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    req: OnboardingRequest,
    session: DbSession,
    clerk_id: ClerkUserId,
) -> OwnProfileResponse:
    existing = await user_svc.get_by_clerk_id(session, clerk_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already exists.",
        )

    if not await user_svc.is_username_available(session, req.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username is taken.",
        )

    user = await user_svc.create_user(session, clerk_id, req.username, req.display_name)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        logger.debug("Username uniqueness conflict at write time: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username is taken.",
        ) from exc

    await _mark_onboarded_in_clerk(clerk_id)
    return user_svc.build_own_profile(user)


# ── Username availability (registered before /{username} catch-all) ───────────


@router.get("/check-username", response_model=UsernameCheckResponse)
@limiter.limit("20/minute")  # advisory check — rate-limited to limit enumeration
async def check_username(
    request: Request,
    response: Response,
    q: str,
    session: DbSession,
) -> UsernameCheckResponse:
    from app.schemas.user import _USERNAME_RE, RESERVED_USERNAMES

    if not _USERNAME_RE.match(q):
        return UsernameCheckResponse(available=False)
    if q.lower() in RESERVED_USERNAMES:
        return UsernameCheckResponse(available=False)
    available = await user_svc.is_username_available(session, q)
    return UsernameCheckResponse(available=available)


# ── Own profile ───────────────────────────────────────────────────────────────


@router.get("/me", response_model=OwnProfileResponse)
async def get_own_profile(
    current_user: CurrentUser,
) -> OwnProfileResponse:
    return user_svc.build_own_profile(current_user)


@router.patch("/me", response_model=OwnProfileResponse)
@limiter.limit("10/minute")
async def update_profile(
    request: Request,
    response: Response,
    req: ProfileUpdateRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> OwnProfileResponse:
    # Determine which bio update to apply based on what was sent in the request.
    # req.bio == None can mean "not included" or "clear it" — use fields_set to
    # distinguish. If "bio" is in the request payload, apply it (even if null).
    bio_update = req.bio if "bio" in req.model_fields_set else current_user.bio

    if req.username is not None and req.username != current_user.username:
        if not await user_svc.is_username_available(session, req.username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That username is taken.",
            )

    try:
        result = await user_svc.update_profile(
            session,
            current_user,
            display_name=req.display_name,
            username=req.username,
            bio=bio_update,
            visibility_bio=req.visibility_bio,
            visibility_activity=req.visibility_activity,
            visibility_ratings=req.visibility_ratings,
            visibility_follows=req.visibility_follows,
            melody_accept_scope=req.melody_accept_scope,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        logger.debug("Username conflict on update: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username is taken.",
        ) from exc
    except Exception as exc:
        await session.rollback()
        logger.exception("Profile update failed for internal_id=%s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_SAVE_ERROR,
        ) from exc

    return result


@router.post("/me/avatar", response_model=AvatarUploadResponse)
@limiter.limit("5/minute")
async def upload_avatar(
    request: Request,
    response: Response,
    file: UploadFile,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> AvatarUploadResponse:
    # Client-side validation catches most issues; server-side is authoritative.
    data = await file.read(storage.MAX_AVATAR_BYTES + 1)
    if len(data) > storage.MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 5 MB limit.",
        )

    content_type = storage.detect_image_content_type(data)
    if content_type is None or content_type not in storage.ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported file type. Upload a JPEG, PNG, or WebP image.",
        )

    try:
        avatar_url = await storage.upload_avatar(data, content_type)
    except StorageError as exc:
        logger.error(
            "Avatar upload failed for internal_id=%s: %s", current_user.id, exc
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_AVATAR_ERROR,
        ) from exc

    await user_svc.update_avatar_url(session, current_user, avatar_url)
    try:
        await session.commit()
    except Exception as exc:
        logger.exception(
            "DB update failed after avatar upload for internal_id=%s", current_user.id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_AVATAR_ERROR,
        ) from exc

    return AvatarUploadResponse(avatar_url=avatar_url)


# ── User search (must be registered before /{username} catch-all) ────────────


@router.get("/search", response_model=list[UserSearchResult])
@limiter.limit("20/minute")
async def search_users(
    request: Request,
    response: Response,
    q: str,
    session: DbSession,
) -> list[UserSearchResult]:
    if len(q) < 2:
        return []
    return await user_svc.search_users(session, q)


# ── Public profile (must be registered last — catches /{username}) ─────────────


@router.get(
    "/{username}",
    response_model=ProfileResponse,
    response_model_exclude_unset=True,
)
async def get_profile(
    username: str,
    session: DbSession,
    viewer_clerk_id: OptionalClerkId,
) -> JSONResponse:
    profile = await user_svc.get_profile(session, username, viewer_clerk_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    # model_construct was used to set only visible fields; serialize with
    # exclude_unset so absent fields don't appear as null in the JSON.
    return JSONResponse(
        content=profile.model_dump(exclude_unset=True),
        status_code=200,
    )
