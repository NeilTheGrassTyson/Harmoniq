"""Unit tests for rating schema validators and the _can_view visibility gate — no database required."""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.core.enums import VisibilityScope
from app.models.rating import Rating
from app.schemas.rating import REVIEW_MAX_LENGTH, REVIEW_MIN_LENGTH, RatingSubmitRequest
from app.services.rating import _can_view

# ── RatingSubmitRequest validation ────────────────────────────────────────────


class TestRatingSubmitRequestValidation:
    def test_score_at_minimum_accepted(self) -> None:
        req = RatingSubmitRequest(
            entity_type="track",
            entity_mbid="abc",
            score=1,
            review_text="x" * REVIEW_MIN_LENGTH,
        )
        assert req.score == 1

    def test_score_at_maximum_accepted(self) -> None:
        req = RatingSubmitRequest(
            entity_type="track",
            entity_mbid="abc",
            score=10,
            review_text="x" * REVIEW_MIN_LENGTH,
        )
        assert req.score == 10

    def test_score_below_minimum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RatingSubmitRequest(
                entity_type="track",
                entity_mbid="abc",
                score=0,
                review_text="x" * REVIEW_MIN_LENGTH,
            )

    def test_score_above_maximum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RatingSubmitRequest(
                entity_type="track",
                entity_mbid="abc",
                score=11,
                review_text="x" * REVIEW_MIN_LENGTH,
            )

    def test_entity_type_track_accepted(self) -> None:
        req = RatingSubmitRequest(
            entity_type="track",
            entity_mbid="abc",
            score=5,
            review_text="x" * REVIEW_MIN_LENGTH,
        )
        assert req.entity_type == "track"

    def test_entity_type_album_accepted(self) -> None:
        req = RatingSubmitRequest(
            entity_type="album",
            entity_mbid="abc",
            score=5,
            review_text="x" * REVIEW_MIN_LENGTH,
        )
        assert req.entity_type == "album"

    def test_entity_type_unknown_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RatingSubmitRequest(
                entity_type="artist",
                entity_mbid="abc",
                score=5,
                review_text="x" * REVIEW_MIN_LENGTH,
            )

    def test_review_text_at_minimum_length_accepted(self) -> None:
        text = "a" * REVIEW_MIN_LENGTH
        req = RatingSubmitRequest(
            entity_type="track",
            entity_mbid="abc",
            score=5,
            review_text=text,
        )
        assert req.review_text == text

    def test_review_text_below_minimum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RatingSubmitRequest(
                entity_type="track",
                entity_mbid="abc",
                score=5,
                review_text="a" * (REVIEW_MIN_LENGTH - 1),
            )

    def test_review_text_at_maximum_length_accepted(self) -> None:
        req = RatingSubmitRequest(
            entity_type="track",
            entity_mbid="abc",
            score=5,
            review_text="a" * REVIEW_MAX_LENGTH,
        )
        assert len(req.review_text) == REVIEW_MAX_LENGTH

    def test_review_text_over_maximum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RatingSubmitRequest(
                entity_type="track",
                entity_mbid="abc",
                score=5,
                review_text="a" * (REVIEW_MAX_LENGTH + 1),
            )

    def test_review_text_stripped_before_length_check(self) -> None:
        padded = "  " + "a" * REVIEW_MIN_LENGTH + "  "
        req = RatingSubmitRequest(
            entity_type="track",
            entity_mbid="abc",
            score=5,
            review_text=padded,
        )
        assert req.review_text == "a" * REVIEW_MIN_LENGTH

    def test_whitespace_only_review_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RatingSubmitRequest(
                entity_type="track",
                entity_mbid="abc",
                score=5,
                review_text=" " * 50,
            )

    def test_default_visibility_is_public(self) -> None:
        req = RatingSubmitRequest(
            entity_type="track",
            entity_mbid="abc",
            score=5,
            review_text="x" * REVIEW_MIN_LENGTH,
        )
        assert req.visibility == VisibilityScope.PUBLIC


# ── _can_view logic ───────────────────────────────────────────────────────────


def _make_rating(*, owner_id: uuid.UUID, visibility: str) -> Rating:
    return Rating(
        id=uuid.uuid4(),
        user_id=owner_id,
        entity_type="track",
        entity_id=uuid.uuid4(),
        score=7,
        review_text="Decent record, rewards repeated listening.",
        visibility=visibility,
        created_at=datetime.now(UTC),
    )


class TestCanViewLogic:
    """_can_view(rating, rater_profile_scope, viewer_id, viewer_is_friend).

    The profile-level scope is a master switch: the stricter of it and the
    per-rating scope governs (ratings spec, Amendments 2026-07-04).
    """

    def test_owner_sees_own_private_rating(self) -> None:
        owner_id = uuid.uuid4()
        assert _can_view(
            _make_rating(owner_id=owner_id, visibility="private"),
            "public",
            owner_id,
            False,
        )

    def test_owner_sees_own_rating_even_when_profile_private(self) -> None:
        owner_id = uuid.uuid4()
        assert _can_view(
            _make_rating(owner_id=owner_id, visibility="public"),
            "private",
            owner_id,
            False,
        )

    def test_public_visible_to_anonymous(self) -> None:
        assert _can_view(
            _make_rating(owner_id=uuid.uuid4(), visibility="public"),
            "public",
            None,
            False,
        )

    def test_public_visible_to_stranger(self) -> None:
        assert _can_view(
            _make_rating(owner_id=uuid.uuid4(), visibility="public"),
            "public",
            uuid.uuid4(),
            False,
        )

    def test_private_hidden_from_anonymous(self) -> None:
        assert not _can_view(
            _make_rating(owner_id=uuid.uuid4(), visibility="private"),
            "public",
            None,
            False,
        )

    def test_private_hidden_from_stranger(self) -> None:
        assert not _can_view(
            _make_rating(owner_id=uuid.uuid4(), visibility="private"),
            "public",
            uuid.uuid4(),
            False,
        )

    def test_friends_hidden_from_anonymous(self) -> None:
        assert not _can_view(
            _make_rating(owner_id=uuid.uuid4(), visibility="friends"),
            "public",
            None,
            False,
        )

    def test_friends_hidden_from_non_friend(self) -> None:
        assert not _can_view(
            _make_rating(owner_id=uuid.uuid4(), visibility="friends"),
            "public",
            uuid.uuid4(),
            False,
        )

    def test_friends_visible_when_is_friend_true(self) -> None:
        assert _can_view(
            _make_rating(owner_id=uuid.uuid4(), visibility="friends"),
            "public",
            uuid.uuid4(),
            True,
        )

    # ── Master switch: profile scope caps per-rating scope ────────────────────

    def test_profile_private_hides_public_rating_from_stranger(self) -> None:
        assert not _can_view(
            _make_rating(owner_id=uuid.uuid4(), visibility="public"),
            "private",
            uuid.uuid4(),
            False,
        )

    def test_profile_private_hides_public_rating_even_from_friend(self) -> None:
        assert not _can_view(
            _make_rating(owner_id=uuid.uuid4(), visibility="public"),
            "private",
            uuid.uuid4(),
            True,
        )

    def test_profile_friends_caps_public_rating_to_friends(self) -> None:
        rating = _make_rating(owner_id=uuid.uuid4(), visibility="public")
        assert not _can_view(rating, "friends", uuid.uuid4(), False)
        assert _can_view(rating, "friends", uuid.uuid4(), True)

    def test_rating_private_stays_private_when_profile_public(self) -> None:
        assert not _can_view(
            _make_rating(owner_id=uuid.uuid4(), visibility="private"),
            "public",
            uuid.uuid4(),
            True,
        )
