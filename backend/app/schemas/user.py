import re

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.enums import VisibilityScope
from app.schemas.follow import FollowState

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,30}$")

# Usernames that cannot be registered — they conflict with app routes or
# reserved paths in the /api/v1/users router.
RESERVED_USERNAMES: frozenset[str] = frozenset(
    {
        "me",
        "admin",
        "api",
        "settings",
        "onboarding",
        "check-username",
        "staff",
        "support",
        "help",
        "about",
        "terms",
        "privacy",
    }
)


def _validate_username_value(v: str) -> str:
    if not _USERNAME_RE.match(v):
        raise ValueError(
            "Usernames can only contain letters, numbers, underscores, and hyphens"
            " (3–30 characters)."
        )
    if v.lower() in RESERVED_USERNAMES:
        raise ValueError("That username is reserved.")
    return v.lower()


def _validate_display_name_value(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("Display name cannot be empty.")
    if len(v) > 50:
        raise ValueError("Display name must be 50 characters or fewer.")
    return v


# ── Request schemas ───────────────────────────────────────────────────────────


class OnboardingRequest(BaseModel):
    username: str
    display_name: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        return _validate_username_value(v)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        return _validate_display_name_value(v)


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = None
    username: str | None = None
    bio: str | None = None
    visibility_bio: VisibilityScope | None = None
    visibility_activity: VisibilityScope | None = None
    visibility_ratings: VisibilityScope | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validate_username_value(v)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validate_display_name_value(v)

    @field_validator("bio")
    @classmethod
    def validate_bio(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if len(v) > 280:
            raise ValueError("Bio must be 280 characters or fewer.")
        return v or None  # empty string after strip → treat as cleared


# ── Response schemas ──────────────────────────────────────────────────────────


class ProfileResponse(BaseModel):
    """
    Public or viewer-scoped profile. Fields gated by VisibilityScope are
    absent from the response (not null) when the viewer is not permitted to
    see them. Use response_model_exclude_unset=True on the endpoint and build
    instances with model_construct() to leverage this.
    """

    model_config = ConfigDict(populate_by_name=True)

    username: str
    display_name: str
    avatar_url: str | None  # None = no avatar; always present
    is_own_profile: bool
    follower_count: int = 0
    following_count: int = 0
    # follow is present only when the viewer is authenticated and not the owner:
    follow: FollowState | None = None
    # The following are present only when visibility allows:
    bio: str | None = None
    activity_placeholder: bool | None = None  # True = show placeholder section
    ratings_count: int | None = None


class OwnProfileResponse(BaseModel):
    """Full profile view for the authenticated owner, including visibility settings."""

    username: str
    display_name: str
    avatar_url: str | None
    bio: str | None
    visibility_bio: VisibilityScope
    visibility_activity: VisibilityScope
    visibility_ratings: VisibilityScope


class UsernameCheckResponse(BaseModel):
    available: bool


class AvatarUploadResponse(BaseModel):
    avatar_url: str


class UserSearchResult(BaseModel):
    """Minimal public user card returned by GET /users/search. No sensitive fields."""

    username: str
    display_name: str
    avatar_url: str | None
