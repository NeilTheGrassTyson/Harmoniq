"""Middleware order is load-bearing, and only one arrangement works.

`CORSMiddleware` answers an OPTIONS preflight itself and never calls the rest
of the stack. Anything registered *inside* it therefore never sees a
preflight — so an origin audit placed there would log a rejected GET and stay
silent on the rejected preflight that precedes every authenticated POST,
PUT, PATCH and DELETE. The audit would look like it worked while missing the
half of the traffic most likely to be reported as "the site is broken".

Starlette's `add_middleware` prepends, so the *last* one added is outermost.
That is a detail nobody re-derives when adding middleware later, and the
symptom of getting it wrong is silence — which is indistinguishable from
"there was nothing to report". Hence a test rather than a comment.

`tests/unit/test_cors.py` covers what the audit logs; this covers where it
sits.
"""

import logging

import pytest
from fastapi.middleware.cors import CORSMiddleware
from httpx import AsyncClient

from app.core.cors import OriginAuditMiddleware
from app.main import app


def _middleware_classes() -> list[type]:
    return [layer.cls for layer in app.user_middleware]


def test_origin_audit_is_the_outermost_middleware() -> None:
    assert _middleware_classes()[0] is OriginAuditMiddleware, (
        "OriginAuditMiddleware must be added last so it is outermost. Inside "
        "CORSMiddleware it never sees an OPTIONS preflight, which is how "
        "every authenticated mutation begins."
    )


def test_origin_audit_is_outside_cors() -> None:
    classes = _middleware_classes()
    assert classes.index(OriginAuditMiddleware) < classes.index(CORSMiddleware)


async def test_rejected_preflight_is_logged(
    http_client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    """The case that motivated the ordering: a preflight, not a simple request.

    A distinct origin per test because the audit dedupes per instance, and the
    app instance is shared across the whole session.
    """
    origin = "https://preflight-audit.invalid"

    with caplog.at_level(logging.WARNING, logger="app.core.cors"):
        response = await http_client.options(
            "/api/v1/users/me",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "authorization",
            },
        )

    assert origin in caplog.text
    # The audit observes only. CORSMiddleware still made the decision, and
    # still withheld the header that would have allowed the request.
    assert "access-control-allow-origin" not in response.headers


async def test_rejected_simple_request_is_logged(
    http_client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    origin = "https://simple-audit.invalid"

    with caplog.at_level(logging.WARNING, logger="app.core.cors"):
        response = await http_client.get("/api/v1/health", headers={"Origin": origin})

    assert origin in caplog.text
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
