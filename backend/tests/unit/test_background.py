"""Unit tests for app.core.background.run_exclusive. No database."""

import uuid
from typing import Any

import pytest

from app.core import background

_KEY = uuid.UUID("00000000-0000-0000-0009-000000000001")


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch) -> _FakeSession:
    fake = _FakeSession()
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: fake)
    return fake


@pytest.mark.asyncio
async def test_runs_and_commits_then_releases_the_key(session: _FakeSession) -> None:
    running: set[uuid.UUID] = set()
    seen: list[bool] = []

    async def work(_s: Any) -> None:
        seen.append(_KEY in running)

    await background.run_exclusive(running, _KEY, work, "test")
    assert seen == [True] and session.committed and running == set()


@pytest.mark.asyncio
async def test_a_run_already_in_flight_is_not_repeated(session: _FakeSession) -> None:
    calls: list[int] = []

    async def work(_s: Any) -> None:
        calls.append(1)

    await background.run_exclusive({_KEY}, _KEY, work, "test")
    assert calls == [] and not session.committed


@pytest.mark.asyncio
async def test_a_failure_is_swallowed_uncommitted_and_releases_the_key(
    session: _FakeSession,
) -> None:
    running: set[uuid.UUID] = set()

    async def work(_s: Any) -> None:
        raise RuntimeError("provider exploded")

    await background.run_exclusive(running, _KEY, work, "test")
    assert not session.committed and running == set()
