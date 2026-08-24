"""
Origin auditing for CORS.

`CORSMiddleware` rejects a disallowed origin silently: it simply omits the
`access-control-allow-origin` header, the request is answered normally, and
the browser discards the response. Server-side callers (Next middleware, RSC)
bypass CORS entirely and keep working, so the site looks healthy from the
server while every interactive feature is dead in the browser.

That asymmetry has cost this project three live debugging sessions
(docs/deployment.md, docs/adr/0011-misconfiguration-must-be-observable.md).
This middleware makes it visible: one warning naming the rejected origin and
the configured allow-list, which is everything an operator needs to fix the
environment variable.
"""

import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from app.config import settings

logger = logging.getLogger(__name__)

# Log each distinct rejected origin once. Bounded so an unauthenticated
# caller cycling the Origin header cannot grow the set or flood the log.
_MAX_REPORTED_ORIGINS = 20


class OriginAuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._reported: set[str] = set()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        origin = request.headers.get("origin")
        if origin is not None:
            allowed = settings.cors_origins_list
            if origin not in allowed and "*" not in allowed:
                self._report(origin, allowed)
        return await call_next(request)

    def _report(self, origin: str, allowed: list[str]) -> None:
        if origin in self._reported:
            return
        if len(self._reported) >= _MAX_REPORTED_ORIGINS:
            return
        self._reported.add(origin)
        logger.warning(
            "CORS: rejecting browser requests from origin %r — it is not in "
            "CORS_ALLOWED_ORIGINS (%s). Every fetch from that origin fails as "
            "an opaque network error in the browser; server-rendered pages are "
            "unaffected. Add the origin exactly as shown, with no trailing "
            "slash. See docs/deployment.md.",
            origin,
            ", ".join(allowed) or "<empty>",
        )
