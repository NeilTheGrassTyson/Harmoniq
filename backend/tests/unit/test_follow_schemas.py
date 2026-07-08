"""Unit tests for follow schema validation and cursor encoding — no database required."""

import uuid
from datetime import UTC, datetime

import pytest

from app.schemas.follow import FollowCursor, FollowState, FollowSummary


class TestFollowState:
    def test_all_false_when_no_relationship(self) -> None:
        state = FollowState(is_following=False, follows_you=False, is_friend=False)
        assert state.is_following is False
        assert state.follows_you is False
        assert state.is_friend is False

    def test_is_friend_true_when_mutual(self) -> None:
        state = FollowState(is_following=True, follows_you=True, is_friend=True)
        assert state.is_friend is True

    def test_is_friend_false_when_only_one_direction(self) -> None:
        state = FollowState(is_following=True, follows_you=False, is_friend=False)
        assert state.is_friend is False


class TestFollowSummary:
    def test_avatar_url_can_be_none(self) -> None:
        summary = FollowSummary(
            user_id=uuid.uuid4(),
            username="testuser",
            display_name="Test User",
            avatar_url=None,
        )
        assert summary.avatar_url is None

    def test_fields_preserved(self) -> None:
        uid = uuid.uuid4()
        summary = FollowSummary(
            user_id=uid,
            username="alice",
            display_name="Alice",
            avatar_url="https://example.com/avatar.png",
        )
        assert summary.user_id == uid
        assert summary.username == "alice"
        assert summary.display_name == "Alice"
        assert summary.avatar_url == "https://example.com/avatar.png"


class TestFollowCursor:
    def test_roundtrip_encode_decode(self) -> None:
        uid = uuid.uuid4()
        dt = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
        cursor = FollowCursor(created_at=dt, user_id=uid)
        token = cursor.encode()
        decoded = FollowCursor.decode(token)
        assert decoded.user_id == uid
        assert decoded.created_at == dt

    def test_different_cursors_produce_different_tokens(self) -> None:
        uid1 = uuid.uuid4()
        uid2 = uuid.uuid4()
        dt = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
        token1 = FollowCursor(created_at=dt, user_id=uid1).encode()
        token2 = FollowCursor(created_at=dt, user_id=uid2).encode()
        assert token1 != token2

    def test_decode_garbage_raises(self) -> None:
        import binascii

        # A valid base64 token that decodes to something unparseable as a cursor
        # should raise ValueError (bad UUID) or binascii.Error (bad base64).
        with pytest.raises((ValueError, binascii.Error)):
            FollowCursor.decode("dGhpcyBpcyBub3QgYSBjdXJzb3I=")
