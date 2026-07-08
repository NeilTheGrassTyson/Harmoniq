import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.core.enums import VisibilityScope

REVIEW_MIN_LENGTH = 15
REVIEW_MAX_LENGTH = 2000
ENTITY_TYPES: frozenset[str] = frozenset({"track", "album"})


# ── Request schemas ───────────────────────────────────────────────────────────


class RatingSubmitRequest(BaseModel):
    entity_type: str
    entity_mbid: str
    score: int
    review_text: str
    visibility: VisibilityScope = VisibilityScope.PUBLIC

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        if v not in ENTITY_TYPES:
            raise ValueError("entity_type must be 'track' or 'album'.")
        return v

    @field_validator("score")
    @classmethod
    def validate_score(cls, v: int) -> int:
        if v < 1 or v > 10:
            raise ValueError("Score must be between 1 and 10.")
        return v

    @field_validator("review_text")
    @classmethod
    def validate_review_text(cls, v: str) -> str:
        v = v.strip()
        if len(v) < REVIEW_MIN_LENGTH:
            raise ValueError(
                f"A few more words — reviews need at least "
                f"{REVIEW_MIN_LENGTH} characters."
            )
        if len(v) > REVIEW_MAX_LENGTH:
            raise ValueError(f"Review must be {REVIEW_MAX_LENGTH} characters or fewer.")
        return v


class VisibilityUpdateRequest(BaseModel):
    visibility: VisibilityScope


# ── Response schemas ──────────────────────────────────────────────────────────


class ReviewerInfo(BaseModel):
    username: str
    display_name: str
    avatar_url: str | None


class RatingRead(BaseModel):
    """A single rating+review, as shown in entity review lists."""

    id: uuid.UUID
    reviewer: ReviewerInfo
    score: int
    review_text: str
    visibility: VisibilityScope
    created_at: datetime
    # True only in the author's own view of a moderation-hidden review —
    # hidden reviews are never serialized for anyone else.
    hidden: bool = False


class EntityRatingListResponse(BaseModel):
    """Aggregate score + visible reviews for a track or album."""

    aggregate_score: float | None
    reviews: list[RatingRead]


class UserRatingRead(BaseModel):
    """A single rating+review from a user's history, includes entity context."""

    id: uuid.UUID
    entity_type: str
    entity_mbid: str | None
    entity_title: str | None
    score: int
    review_text: str
    visibility: VisibilityScope
    created_at: datetime
    hidden: bool = False


class UserRatingListResponse(BaseModel):
    reviews: list[UserRatingRead]
