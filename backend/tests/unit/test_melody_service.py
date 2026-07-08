"""
Unit tests for the pure Melody helpers: the transition matrix, the
sender-visible status collapse, and the accept-scope check. No database.
"""

import pytest

from app.core.enums import MelodyAcceptScope, MelodyStatus
from app.services.melody import (
    _can_transition,
    _scope_satisfied,
    _sender_visible_status,
)

_ALL = [s.value for s in MelodyStatus]

# The complete allowed set — everything else must be refused.
_ALLOWED: set[tuple[str, str]] = {
    ("sent", "accepted"),
    ("sent", "opened"),
    ("sent", "rejected"),
    ("received", "accepted"),
    ("received", "opened"),
    ("received", "rejected"),
    ("rejected", "accepted"),
    ("rejected", "opened"),
    ("accepted", "opened"),
}


class TestTransitionMatrix:
    @pytest.mark.parametrize("from_status", _ALL)
    @pytest.mark.parametrize("to_status", _ALL)
    def test_full_matrix(self, from_status: str, to_status: str) -> None:
        expected = (from_status, to_status) in _ALLOWED
        assert _can_transition(from_status, to_status) is expected

    def test_opened_is_terminal(self) -> None:
        assert all(not _can_transition("opened", to) for to in _ALL)

    def test_rejected_is_recoverable_but_not_rerejctable(self) -> None:
        assert _can_transition("rejected", "accepted")
        assert _can_transition("rejected", "opened")
        assert not _can_transition("rejected", "rejected")

    def test_unknown_status_fails_closed(self) -> None:
        assert not _can_transition("bogus", "accepted")


class TestSenderVisibleStatus:
    def test_received_collapses_to_sent(self) -> None:
        assert _sender_visible_status("received") is MelodyStatus.SENT

    @pytest.mark.parametrize("status", ["sent", "accepted", "opened", "rejected"])
    def test_other_statuses_pass_through(self, status: str) -> None:
        assert _sender_visible_status(status) is MelodyStatus(status)


class TestScopeSatisfied:
    @pytest.mark.parametrize("follows", [True, False])
    @pytest.mark.parametrize("mutual", [True, False])
    def test_everyone_always_allows(self, follows: bool, mutual: bool) -> None:
        assert _scope_satisfied(MelodyAcceptScope.EVERYONE.value, follows, mutual)

    def test_follows_requires_recipient_follows_sender(self) -> None:
        scope = MelodyAcceptScope.FOLLOWS.value
        assert _scope_satisfied(scope, True, False)
        assert _scope_satisfied(scope, True, True)
        assert not _scope_satisfied(scope, False, False)

    def test_mutuals_requires_mutual(self) -> None:
        scope = MelodyAcceptScope.MUTUALS.value
        assert _scope_satisfied(scope, True, True)
        assert not _scope_satisfied(scope, True, False)
        assert not _scope_satisfied(scope, False, False)

    def test_unknown_scope_fails_closed(self) -> None:
        assert not _scope_satisfied("bogus", True, True)
