"""
Rating service: submission, aggregate calculation, visibility-enforced reads,
deletion, and reporting.

Visibility enforcement is always performed at this layer — never in the route
handler or on the frontend.

The profile-level visibility_ratings setting is a master switch: a rating's
effective visibility is the stricter of that setting and the rating's own
scope, on every surface. Aggregates count only effectively public ratings.
(Ratings spec, Amendments 2026-07-04.)
"""

import logging
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import VisibilityScope
from app.core.visibility import effective_scope, scope_allows
from app.models.catalog import Album, Track
from app.models.rating import Rating, Report
from app.models.user import User
from app.schemas.rating import (
    EntityRatingListResponse,
    RatingRead,
    ReviewerInfo,
    UserRatingListResponse,
    UserRatingRead,
)
from app.services import follow as follow_svc

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=UTC)


# ── Entity resolution (MBID → internal UUID) ──────────────────────────────────


async def resolve_entity(
    session: AsyncSession, entity_type: str, entity_mbid: str
) -> uuid.UUID | None:
    """Returns the internal UUID for the given entity MBID, or None if not found."""
    if entity_type == "track":
        result = await session.execute(
            select(Track.id).where(Track.mbid == entity_mbid)
        )
    else:
        result = await session.execute(
            select(Album.id).where(Album.mbid == entity_mbid)
        )
    return result.scalar_one_or_none()


# ── Mutual-follow check ───────────────────────────────────────────────────────


async def _is_friend(
    session: AsyncSession,
    viewer_id: uuid.UUID,
    subject_id: uuid.UUID,
) -> bool:
    return await follow_svc.is_mutual_follow(session, viewer_id, subject_id)


# ── Visibility gate ───────────────────────────────────────────────────────────


def _can_view(
    rating: Rating,
    rater_profile_scope: str,
    viewer_id: uuid.UUID | None,
    viewer_is_friend: bool,
) -> bool:
    is_owner = viewer_id is not None and viewer_id == rating.user_id
    # Moderation-hidden: visible only to the author (with a notice flag on
    # the schema), regardless of visibility scope.
    if rating.hidden_at is not None:
        return is_owner
    scope = effective_scope(rater_profile_scope, rating.visibility)
    return scope_allows(scope, is_owner=is_owner, is_friend=viewer_is_friend)


# ── Aggregate calculation ─────────────────────────────────────────────────────


async def get_aggregate(
    session: AsyncSession,
    entity_type: str,
    entity_id: uuid.UUID,
) -> float | None:
    """
    Average of each user's most recent effectively-public score for the
    given entity. Only ratings that are public at both the per-rating and
    profile level count — a private rating must never move a public number.
    """
    rn = (
        func.row_number()
        .over(
            partition_by=Rating.user_id,
            order_by=Rating.created_at.desc(),
        )
        .label("rn")
    )

    subq = (
        select(Rating.score, rn)
        .join(User, User.id == Rating.user_id)
        .where(
            Rating.entity_type == entity_type,
            Rating.entity_id == entity_id,
            Rating.visibility == VisibilityScope.PUBLIC.value,
            User.visibility_ratings == VisibilityScope.PUBLIC.value,
            Rating.hidden_at.is_(None),  # moderation-hidden never moves a number
        )
        .subquery()
    )

    result = await session.execute(select(func.avg(subq.c.score)).where(subq.c.rn == 1))
    raw = result.scalar_one_or_none()
    return float(raw) if raw is not None else None


# ── List reviews for an entity ────────────────────────────────────────────────


async def list_for_entity(
    session: AsyncSession,
    entity_type: str,
    entity_id: uuid.UUID,
    viewer_id: uuid.UUID | None,
) -> EntityRatingListResponse:
    t0 = time.monotonic()
    aggregate = await get_aggregate(session, entity_type, entity_id)
    logger.debug(
        "Aggregate recalc entity=%s/%s aggregate=%s trigger=read duration_ms=%.1f",
        entity_type,
        entity_id,
        aggregate,
        (time.monotonic() - t0) * 1000,
    )

    rows_result = await session.execute(
        select(Rating, User)
        .join(User, Rating.user_id == User.id)
        .where(Rating.entity_type == entity_type, Rating.entity_id == entity_id)
        .order_by(Rating.created_at.desc(), Rating.id.asc())
    )
    rows = rows_result.all()

    # One mutual-follows fetch for the viewer instead of a per-row query.
    viewer_friend_ids: set[uuid.UUID] = set()
    if viewer_id is not None and rows:
        viewer_friend_ids = await follow_svc.get_mutual_follow_ids(session, viewer_id)

    visible: list[RatingRead] = []
    for rating, user in rows:
        is_friend = rating.user_id in viewer_friend_ids
        if not _can_view(rating, user.visibility_ratings, viewer_id, is_friend):
            continue
        visible.append(
            RatingRead(
                id=rating.id,
                reviewer=ReviewerInfo(
                    username=user.username,
                    display_name=user.display_name,
                    avatar_url=user.avatar_url,
                ),
                score=rating.score,
                review_text=rating.review_text,
                visibility=VisibilityScope(rating.visibility),
                created_at=rating.created_at,
                hidden=rating.hidden_at is not None,
            )
        )

    return EntityRatingListResponse(aggregate_score=aggregate, reviews=visible)


# ── List reviews by a user ────────────────────────────────────────────────────


async def list_for_user(
    session: AsyncSession,
    profile_user: User,
    viewer_id: uuid.UUID | None,
) -> UserRatingListResponse:
    is_friend = (
        await _is_friend(session, viewer_id, profile_user.id)
        if viewer_id is not None and viewer_id != profile_user.id
        else False
    )

    rows_result = await session.execute(
        select(Rating)
        .where(Rating.user_id == profile_user.id)
        .order_by(Rating.created_at.desc(), Rating.id.asc())
    )
    ratings = rows_result.scalars().all()

    visible_ratings = [
        r
        for r in ratings
        if _can_view(r, profile_user.visibility_ratings, viewer_id, is_friend)
    ]

    if not visible_ratings:
        return UserRatingListResponse(reviews=[])

    track_ids = [r.entity_id for r in visible_ratings if r.entity_type == "track"]
    album_ids = [r.entity_id for r in visible_ratings if r.entity_type == "album"]

    entity_lookup: dict[uuid.UUID, tuple[str, str]] = {}
    if track_ids:
        t_result = await session.execute(
            select(Track.id, Track.mbid, Track.title).where(Track.id.in_(track_ids))
        )
        for row in t_result.all():
            entity_lookup[row[0]] = (row[1], row[2])
    if album_ids:
        a_result = await session.execute(
            select(Album.id, Album.mbid, Album.title).where(Album.id.in_(album_ids))
        )
        for row in a_result.all():
            entity_lookup[row[0]] = (row[1], row[2])

    reviews = []
    for r in visible_ratings:
        info = entity_lookup.get(r.entity_id)
        reviews.append(
            UserRatingRead(
                id=r.id,
                entity_type=r.entity_type,
                entity_mbid=info[0] if info else None,
                entity_title=info[1] if info else None,
                score=r.score,
                review_text=r.review_text,
                visibility=VisibilityScope(r.visibility),
                created_at=r.created_at,
                hidden=r.hidden_at is not None,
            )
        )

    return UserRatingListResponse(reviews=reviews)


# ── Count current ratings for a user (profile display) ───────────────────────


async def count_for_user(
    session: AsyncSession,
    profile_user: User,
    viewer_id: uuid.UUID | None,
) -> int:
    """Count of ratings by user that are visible to viewer."""
    rows_result = await session.execute(
        select(Rating).where(Rating.user_id == profile_user.id)
    )
    ratings = rows_result.scalars().all()
    is_friend = (
        await _is_friend(session, viewer_id, profile_user.id)
        if viewer_id is not None and viewer_id != profile_user.id
        else False
    )
    return sum(
        1
        for r in ratings
        if _can_view(r, profile_user.visibility_ratings, viewer_id, is_friend)
    )


# ── Submit a rating ───────────────────────────────────────────────────────────


async def submit(
    session: AsyncSession,
    user_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    score: int,
    review_text: str,
    visibility: VisibilityScope,
) -> RatingRead:
    rating = Rating(
        id=uuid.uuid4(),
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        score=score,
        review_text=review_text,
        visibility=visibility.value,
        created_at=_now(),
    )
    session.add(rating)
    await session.flush()

    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()

    logger.info(
        "Rating submitted user_id=%s entity=%s/%s rating_id=%s",
        user_id,
        entity_type,
        entity_id,
        rating.id,
    )

    return RatingRead(
        id=rating.id,
        reviewer=ReviewerInfo(
            username=user.username,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
        ),
        score=rating.score,
        review_text=rating.review_text,
        visibility=VisibilityScope(rating.visibility),
        created_at=rating.created_at,
    )


# ── Update visibility ─────────────────────────────────────────────────────────


async def update_visibility(
    session: AsyncSession,
    rating_id: uuid.UUID,
    user_id: uuid.UUID,
    visibility: VisibilityScope,
) -> Rating | None:
    result = await session.execute(select(Rating).where(Rating.id == rating_id))
    rating = result.scalar_one_or_none()
    if rating is None or rating.user_id != user_id:
        return None
    rating.visibility = visibility.value
    await session.flush()
    return rating


# ── Delete a rating ───────────────────────────────────────────────────────────


async def delete_rating(
    session: AsyncSession,
    rating_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Returns True if deleted, False if not found or not owned by user_id."""
    result = await session.execute(select(Rating).where(Rating.id == rating_id))
    rating = result.scalar_one_or_none()

    if rating is None:
        return False
    if rating.user_id != user_id:
        logger.warning(
            "Unauthorized delete attempt: user_id=%s tried to delete "
            "rating_id=%s owned by user_id=%s",
            user_id,
            rating_id,
            rating.user_id,
        )
        return False

    entity_type = rating.entity_type
    entity_id = rating.entity_id
    await session.delete(rating)
    await session.flush()

    logger.info("Rating deleted user_id=%s rating_id=%s", user_id, rating_id)

    t0 = time.monotonic()
    new_agg = await get_aggregate(session, entity_type, entity_id)
    logger.debug(
        "Aggregate recalc entity=%s/%s aggregate=%s trigger=delete duration_ms=%.1f",
        entity_type,
        entity_id,
        new_agg,
        (time.monotonic() - t0) * 1000,
    )

    return True


# ── Report a rating ───────────────────────────────────────────────────────────


async def report_rating(
    session: AsyncSession,
    reporter_id: uuid.UUID,
    rating_id: uuid.UUID,
) -> tuple[bool, str]:
    """
    Returns (success, error_message).
    False when: rating not found, self-report, or duplicate report.
    """
    result = await session.execute(select(Rating).where(Rating.id == rating_id))
    rating = result.scalar_one_or_none()

    if rating is None:
        return False, "Review not found."

    if rating.user_id == reporter_id:
        logger.debug(
            "Self-report rejected: reporter_id=%s rating_id=%s", reporter_id, rating_id
        )
        return False, "You cannot report your own review."

    report = Report(
        id=uuid.uuid4(),
        reporter_id=reporter_id,
        rating_id=rating_id,
        created_at=_now(),
    )
    session.add(report)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        logger.debug(
            "Duplicate report rejected: reporter_id=%s rating_id=%s",
            reporter_id,
            rating_id,
        )
        return False, "You have already reported this review."

    logger.info("Report submitted reporter_id=%s rating_id=%s", reporter_id, rating_id)
    return True, ""
