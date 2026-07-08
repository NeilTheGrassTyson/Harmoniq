"""Unit tests for Pydantic schema validators — no database required."""

import pytest
from pydantic import ValidationError

from app.core.enums import VisibilityScope
from app.schemas.user import (
    RESERVED_USERNAMES,
    OnboardingRequest,
    ProfileUpdateRequest,
)

# ── Username validation ───────────────────────────────────────────────────────


class TestUsernameValidation:
    def test_valid_username_is_lowercased(self) -> None:
        req = OnboardingRequest(username="Alice123", display_name="Alice")
        assert req.username == "alice123"

    def test_username_too_short_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OnboardingRequest(username="ab", display_name="Alice")

    def test_username_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OnboardingRequest(username="a" * 31, display_name="Alice")

    def test_username_at_min_boundary_accepted(self) -> None:
        req = OnboardingRequest(username="abc", display_name="Alice")
        assert req.username == "abc"

    def test_username_at_max_boundary_accepted(self) -> None:
        req = OnboardingRequest(username="a" * 30, display_name="Alice")
        assert len(req.username) == 30

    def test_username_with_hyphen_and_underscore(self) -> None:
        req = OnboardingRequest(username="my-user_name", display_name="Alice")
        assert req.username == "my-user_name"

    def test_username_with_space_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OnboardingRequest(username="bad user", display_name="Alice")

    def test_username_with_special_chars_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OnboardingRequest(username="user@name!", display_name="Alice")

    def test_reserved_usernames_all_rejected(self) -> None:
        # Short reserved names (e.g. "me") fail format validation first; longer
        # ones reach the reserved check. Either way the name must be rejected.
        for name in RESERVED_USERNAMES:
            with pytest.raises(ValidationError):
                OnboardingRequest(username=name, display_name="Alice")

    def test_reserved_username_case_insensitive_rejection(self) -> None:
        with pytest.raises(ValidationError):
            OnboardingRequest(username="ME", display_name="Alice")

    def test_profile_update_username_none_allowed(self) -> None:
        req = ProfileUpdateRequest(username=None)
        assert req.username is None

    def test_profile_update_username_validated_and_lowercased(self) -> None:
        req = ProfileUpdateRequest(username="NewName")
        assert req.username == "newname"


# ── Display name validation ───────────────────────────────────────────────────


class TestDisplayNameValidation:
    def test_display_name_preserved(self) -> None:
        req = OnboardingRequest(username="alice", display_name="Alice Smith")
        assert req.display_name == "Alice Smith"

    def test_display_name_stripped(self) -> None:
        req = OnboardingRequest(username="alice", display_name="  Alice  ")
        assert req.display_name == "Alice"

    def test_empty_display_name_rejected(self) -> None:
        with pytest.raises(ValidationError, match="cannot be empty"):
            OnboardingRequest(username="alice", display_name="")

    def test_whitespace_only_display_name_rejected(self) -> None:
        with pytest.raises(ValidationError, match="cannot be empty"):
            OnboardingRequest(username="alice", display_name="   ")

    def test_display_name_at_max_length(self) -> None:
        req = OnboardingRequest(username="alice", display_name="A" * 50)
        assert len(req.display_name) == 50

    def test_display_name_over_max_rejected(self) -> None:
        with pytest.raises(ValidationError, match="50 characters"):
            OnboardingRequest(username="alice", display_name="A" * 51)

    def test_profile_update_display_name_none_allowed(self) -> None:
        req = ProfileUpdateRequest(display_name=None)
        assert req.display_name is None


# ── Bio validation ────────────────────────────────────────────────────────────


class TestBioValidation:
    def test_bio_at_max_length(self) -> None:
        req = ProfileUpdateRequest(bio="x" * 280)
        assert len(req.bio) == 280  # type: ignore[arg-type]

    def test_bio_over_max_rejected(self) -> None:
        with pytest.raises(ValidationError, match="280 characters"):
            ProfileUpdateRequest(bio="x" * 281)

    def test_empty_bio_normalised_to_none(self) -> None:
        req = ProfileUpdateRequest(bio="")
        assert req.bio is None

    def test_whitespace_bio_normalised_to_none(self) -> None:
        req = ProfileUpdateRequest(bio="   ")
        assert req.bio is None

    def test_none_bio_stays_none(self) -> None:
        req = ProfileUpdateRequest(bio=None)
        assert req.bio is None

    def test_valid_bio_preserved(self) -> None:
        req = ProfileUpdateRequest(bio="I love music.")
        assert req.bio == "I love music."


# ── VisibilityScope enum ──────────────────────────────────────────────────────


class TestVisibilityScope:
    def test_private_accepted(self) -> None:
        assert VisibilityScope("private") == VisibilityScope.PRIVATE

    def test_friends_accepted(self) -> None:
        assert VisibilityScope("friends") == VisibilityScope.FRIENDS

    def test_public_accepted(self) -> None:
        assert VisibilityScope("public") == VisibilityScope.PUBLIC

    def test_unknown_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            VisibilityScope("all")

    def test_visibility_in_profile_update_request(self) -> None:
        req = ProfileUpdateRequest(
            visibility_bio="public",
            visibility_activity="friends",
            visibility_ratings="private",
        )
        assert req.visibility_bio == VisibilityScope.PUBLIC
        assert req.visibility_activity == VisibilityScope.FRIENDS
        assert req.visibility_ratings == VisibilityScope.PRIVATE

    def test_invalid_visibility_in_profile_update_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProfileUpdateRequest(visibility_bio="anyone")
