"""
The in-memory presence store (beta-ui Phase 5). Consent decides whether a beat
is kept at all; the window decides how long it counts.
"""

import uuid
from types import SimpleNamespace

import pytest

from app.services import presence as presence_svc


@pytest.fixture(autouse=True)
def _fresh_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(presence_svc, "_last_seen", {})
    now = [1000.0]
    monkeypatch.setattr(presence_svc, "_clock", lambda: now[0])
    presence_svc._test_now = now  # type: ignore[attr-defined]


def _user(scope: str) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), visibility_presence=scope)


def _advance(seconds: float) -> None:
    presence_svc._test_now[0] += seconds  # type: ignore[attr-defined]


def test_private_beats_are_not_kept() -> None:
    user = _user("private")
    assert presence_svc.heartbeat(user) is False  # type: ignore[arg-type]
    assert user.id not in presence_svc._last_seen
    assert presence_svc.is_online(user.id) is False


@pytest.mark.parametrize("scope", ["friends", "public"])
def test_sharing_beats_are_kept(scope: str) -> None:
    user = _user(scope)
    assert presence_svc.heartbeat(user) is True  # type: ignore[arg-type]
    assert presence_svc.is_online(user.id) is True


def test_online_lasts_the_window_and_no_longer() -> None:
    user = _user("friends")
    presence_svc.heartbeat(user)  # type: ignore[arg-type]
    _advance(presence_svc.ONLINE_WINDOW_SECONDS)
    assert presence_svc.is_online(user.id) is True
    _advance(1)
    assert presence_svc.is_online(user.id) is False
    # Expired entries are dropped, not kept around as a "last seen".
    assert user.id not in presence_svc._last_seen


def test_going_private_forgets_immediately() -> None:
    user = _user("friends")
    presence_svc.heartbeat(user)  # type: ignore[arg-type]
    user.visibility_presence = "private"
    presence_svc.heartbeat(user)  # type: ignore[arg-type]
    assert user.id not in presence_svc._last_seen


def test_prune_drops_only_expired_entries() -> None:
    stale, fresh = _user("friends"), _user("friends")
    presence_svc.heartbeat(stale)  # type: ignore[arg-type]
    _advance(presence_svc.ONLINE_WINDOW_SECONDS + 5)
    presence_svc.heartbeat(fresh)  # type: ignore[arg-type]
    presence_svc._prune()
    assert stale.id not in presence_svc._last_seen
    assert fresh.id in presence_svc._last_seen
