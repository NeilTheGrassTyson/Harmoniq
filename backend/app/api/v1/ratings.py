import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, status

from app.api.v1.deps import CurrentUser, DbSession, OptionalClerkId
from app.core.enums import VisibilityScope
from app.core.rate_limit import limiter
from app.schemas.rating import (
    EntityRatingListResponse,
    RatingRead,
    RatingSubmitRequest,
    ReviewerInfo,
    UserRatingListResponse,
    VisibilityUpdateRequest,
)
from app.services import rating as rating_svc
from app.services import user as user_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ratings", tags=["ratings"])

_SUBMIT_ERROR = "Something went wrong. Your review wasn't saved. Try again."
_REPORT_ERROR = "Couldn't submit your report. Try again."


# ── Submit a rating+review ────────────────────────────────────────────────────


@router.post("/", response_model=RatingRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def submit_rating(
    request: Request,
    req: RatingSubmitRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> RatingRead:
    entity_id = await rating_svc.resolve_entity(
        session, req.entity_type, req.entity_mbid
    )
    if entity_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{req.entity_type.capitalize()} not found.",
        )
    try:
        rating = await rating_svc.submit(
            session,
            user_id=current_user.id,
            entity_type=req.entity_type,
            entity_id=entity_id,
            score=req.score,
            review_text=req.review_text,
            visibility=req.visibility,
        )
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.exception("Rating submission failed for user_id=%s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_SUBMIT_ERROR
        ) from exc
    return rating


# ── List reviews for an entity ────────────────────────────────────────────────


@router.get(
    "/entity/{entity_type}/{entity_mbid}", response_model=EntityRatingListResponse
)
async def list_entity_ratings(
    entity_type: str,
    entity_mbid: str,
    session: DbSession,
    viewer_clerk_id: OptionalClerkId,
) -> EntityRatingListResponse:
    if entity_type not in ("track", "album"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="entity_type must be 'track' or 'album'.",
        )
    entity_id = await rating_svc.resolve_entity(session, entity_type, entity_mbid)
    if entity_id is None:
        return EntityRatingListResponse(aggregate_score=None, reviews=[])
    viewer_id = None
    if viewer_clerk_id:
        viewer = await user_svc.get_by_clerk_id(session, viewer_clerk_id)
        if viewer:
            viewer_id = viewer.id
    return await rating_svc.list_for_entity(session, entity_type, entity_id, viewer_id)


# ── List reviews by a user ────────────────────────────────────────────────────


@router.get("/user/{username}", response_model=UserRatingListResponse)
async def list_user_ratings(
    username: str,
    session: DbSession,
    viewer_clerk_id: OptionalClerkId,
) -> UserRatingListResponse:
    profile_user = await user_svc.get_by_username(session, username)
    if profile_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )
    viewer_id = None
    if viewer_clerk_id:
        viewer = await user_svc.get_by_clerk_id(session, viewer_clerk_id)
        if viewer:
            viewer_id = viewer.id
    return await rating_svc.list_for_user(session, profile_user.id, viewer_id)


# ── Update visibility on own rating ──────────────────────────────────────────


@router.patch("/{rating_id}/visibility", response_model=RatingRead)
async def update_visibility(
    rating_id: uuid.UUID,
    req: VisibilityUpdateRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> RatingRead:
    rating = await rating_svc.update_visibility(
        session, rating_id, current_user.id, req.visibility
    )
    if rating is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found.",
        )
    await session.commit()
    return RatingRead(
        id=rating.id,
        reviewer=ReviewerInfo(
            username=current_user.username,
            display_name=current_user.display_name,
            avatar_url=current_user.avatar_url,
        ),
        score=rating.score,
        review_text=rating.review_text,
        visibility=VisibilityScope(rating.visibility),
        created_at=rating.created_at,
    )


# ── Delete own rating ─────────────────────────────────────────────────────────


@router.delete("/{rating_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rating(
    rating_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> None:
    deleted = await rating_svc.delete_rating(session, rating_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found.",
        )
    await session.commit()


# ── Report a review ───────────────────────────────────────────────────────────


@router.post("/{rating_id}/report", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def report_rating(
    request: Request,
    rating_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> None:
    success, error = await rating_svc.report_rating(session, current_user.id, rating_id)
    if not success:
        if "not found" in error.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)
        if "already reported" in error.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error)
        if "own review" in error.lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.exception(
            "Report commit failed: reporter_id=%s rating_id=%s",
            current_user.id,
            rating_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_REPORT_ERROR
        ) from exc
