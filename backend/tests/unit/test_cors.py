"""The origin audit turns a silent CORS rejection into a log line.

CORSMiddleware answers a disallowed origin without the allow-origin header
and without any server-side trace. Nothing here changes that decision — these
tests only assert that the operator finds out.
"""

import logging

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.cors import OriginAuditMiddleware


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    class _Settings:
        cors_origins_list = ["https://harmoniq.live"]

    monkeypatch.setattr("app.core.cors.settings", _Settings())

    app = FastAPI()
    app.add_middleware(OriginAuditMiddleware)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_disallowed_origin_is_logged(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="app.core.cors"):
        response = await client.get("/ping", headers={"Origin": "https://evil.test"})

    # The audit observes only — the request itself is untouched.
    assert response.status_code == 200
    assert "https://evil.test" in caplog.text
    assert "CORS_ALLOWED_ORIGINS" in caplog.text


async def test_allowed_origin_is_not_logged(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="app.core.cors"):
        await client.get("/ping", headers={"Origin": "https://harmoniq.live"})

    assert caplog.records == []


async def test_request_without_origin_is_not_logged(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    # Server-to-server callers send no Origin and are not subject to CORS.
    with caplog.at_level(logging.WARNING, logger="app.core.cors"):
        await client.get("/ping")

    assert caplog.records == []


async def test_same_origin_is_logged_only_once(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="app.core.cors"):
        for _ in range(5):
            await client.get("/ping", headers={"Origin": "https://evil.test"})

    assert len(caplog.records) == 1


async def test_reported_origins_are_bounded(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    # An unauthenticated caller cycling the Origin header must not be able to
    # grow the dedupe set without limit or flood the log.
    with caplog.at_level(logging.WARNING, logger="app.core.cors"):
        for i in range(50):
            await client.get("/ping", headers={"Origin": f"https://{i}.test"})

    assert len(caplog.records) == 20
