"""per_session — the presence routes' rate-limit key (beta-ui Phase 5)."""

from starlette.requests import Request

from app.core.rate_limit import per_session


def _req(auth: str | None, host: str = "10.0.0.7") -> Request:
    headers = [(b"authorization", auth.encode())] if auth else []
    return Request({"type": "http", "headers": headers, "client": (host, 1234)})


def test_people_behind_one_address_get_separate_budgets() -> None:
    a, b = per_session(_req("Bearer token-a")), per_session(_req("Bearer token-b"))
    assert a != b
    assert a == per_session(_req("Bearer token-a", host="10.9.9.9"))


def test_the_credential_itself_never_appears_in_the_key() -> None:
    assert "token-a" not in per_session(_req("Bearer token-a"))


def test_no_credential_falls_back_to_the_address() -> None:
    assert per_session(_req(None)) == "10.0.0.7"
