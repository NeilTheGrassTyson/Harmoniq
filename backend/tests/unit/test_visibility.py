"""Unit tests for the shared visibility decision logic — no database required."""

import pytest

from app.core.enums import VisibilityScope
from app.core.visibility import effective_scope, scope_allows

PRIVATE = VisibilityScope.PRIVATE
FRIENDS = VisibilityScope.FRIENDS
PUBLIC = VisibilityScope.PUBLIC


class TestEffectiveScope:
    @pytest.mark.parametrize(
        ("profile", "item", "expected"),
        [
            (PRIVATE, PRIVATE, PRIVATE),
            (PRIVATE, FRIENDS, PRIVATE),
            (PRIVATE, PUBLIC, PRIVATE),
            (FRIENDS, PRIVATE, PRIVATE),
            (FRIENDS, FRIENDS, FRIENDS),
            (FRIENDS, PUBLIC, FRIENDS),
            (PUBLIC, PRIVATE, PRIVATE),
            (PUBLIC, FRIENDS, FRIENDS),
            (PUBLIC, PUBLIC, PUBLIC),
        ],
    )
    def test_stricter_scope_wins(
        self,
        profile: VisibilityScope,
        item: VisibilityScope,
        expected: VisibilityScope,
    ) -> None:
        assert effective_scope(profile, item) == expected

    def test_accepts_raw_strings(self) -> None:
        assert effective_scope("public", "friends") == FRIENDS

    def test_invalid_scope_raises(self) -> None:
        with pytest.raises(ValueError):
            effective_scope("everyone", "public")


class TestScopeAllows:
    def test_owner_always_allowed(self) -> None:
        for scope in (PRIVATE, FRIENDS, PUBLIC):
            assert scope_allows(scope, is_owner=True, is_friend=False) is True

    @pytest.mark.parametrize(
        ("scope", "is_friend", "expected"),
        [
            (PUBLIC, False, True),
            (PUBLIC, True, True),
            (FRIENDS, True, True),
            (FRIENDS, False, False),
            (PRIVATE, True, False),
            (PRIVATE, False, False),
        ],
    )
    def test_non_owner_matrix(
        self, scope: VisibilityScope, is_friend: bool, expected: bool
    ) -> None:
        assert scope_allows(scope, is_owner=False, is_friend=is_friend) is expected

    def test_accepts_raw_strings(self) -> None:
        assert scope_allows("friends", is_owner=False, is_friend=True) is True
