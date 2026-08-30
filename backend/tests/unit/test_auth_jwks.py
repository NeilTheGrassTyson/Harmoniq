"""
Unit tests for the Clerk JWKS cache — no network, no database.

The cache was `@lru_cache`d for the process lifetime, so a Clerk key rotation
took every authenticated request down until somebody restarted the service,
and an unknown `kid` was rejected without a word in the log. On 2026-08-30 a
CLERK_JWKS_URL pointing at the wrong Clerk instance produced exactly that
symptom: public pages fine, every signed-in action 401.
"""

import pytest

from app import auth


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    """The cache is module state, so each test starts from cold."""
    auth._jwks_cache = None
    auth._jwks_fetched_at = 0.0
    auth._jwks_last_forced_at = 0.0


def _install(monkeypatch: pytest.MonkeyPatch, payloads: list[dict]) -> list[int]:
    """Serve `payloads` in order, repeating the last, and count the calls."""
    calls = [0]

    def fake_get(url: str, timeout: int = 10) -> _FakeResponse:
        index = min(calls[0], len(payloads) - 1)
        calls[0] += 1
        return _FakeResponse(payloads[index])

    monkeypatch.setattr(auth.httpx, "get", fake_get)
    return calls


KEY_A = {"keys": [{"kid": "ins_aaa", "kty": "RSA"}]}
KEY_B = {"keys": [{"kid": "ins_bbb", "kty": "RSA"}]}


class TestJwksCache:
    def test_serves_from_cache_within_the_ttl(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _install(monkeypatch, [KEY_A])
        assert auth._fetch_jwks() == KEY_A
        assert auth._fetch_jwks() == KEY_A
        assert calls[0] == 1

    def test_refetches_once_the_ttl_has_passed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _install(monkeypatch, [KEY_A, KEY_B])
        assert auth._fetch_jwks() == KEY_A
        # Age the cache past the TTL rather than sleeping through it.
        auth._jwks_fetched_at -= auth._JWKS_TTL_SECONDS + 1
        assert auth._fetch_jwks() == KEY_B
        assert calls[0] == 2

    def test_force_refetches_immediately(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = _install(monkeypatch, [KEY_A, KEY_B])
        auth._fetch_jwks()
        assert auth._fetch_jwks(force=True) == KEY_B
        assert calls[0] == 2

    def test_force_is_rate_limited(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A caller spraying tokens with unknown kids must not be able to turn
        # each one into an outbound request to Clerk.
        calls = _install(monkeypatch, [KEY_A, KEY_B])
        auth._fetch_jwks()
        auth._fetch_jwks(force=True)
        for _ in range(20):
            auth._fetch_jwks(force=True)
        assert calls[0] == 2


class TestFindKey:
    def test_finds_a_matching_kid(self) -> None:
        assert auth._find_key(KEY_A, "ins_aaa") == KEY_A["keys"][0]

    def test_returns_none_for_an_unknown_kid(self) -> None:
        assert auth._find_key(KEY_A, "ins_zzz") is None

    def test_returns_none_when_the_jwks_has_no_keys(self) -> None:
        assert auth._find_key({}, "ins_aaa") is None
