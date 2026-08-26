import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.config import settings
from app.core.cors import OriginAuditMiddleware
from app.core.rate_limit import limiter
from app.core.security import SecurityHeadersMiddleware

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)


def _log_cors_configuration() -> None:
    """Record the resolved allow-list, and flag one that can't be right.

    A production deployment whose only allowed origins are http:// or
    localhost is one where CORS_ALLOWED_ORIGINS was never updated for the
    real domain — the exact state that breaks every browser request while
    leaving server-rendered pages working.
    """
    origins = settings.cors_origins_list
    logger.info("CORS allowed origins: %s", ", ".join(origins) or "<empty>")

    if settings.app_env != "production":
        return
    local = [o for o in origins if o.startswith("http://") or "localhost" in o]
    if local:
        logger.warning(
            "CORS: APP_ENV=production but the allow-list contains development "
            "origins (%s). If the production domain is missing from "
            "CORS_ALLOWED_ORIGINS, every browser request from it fails. See "
            "docs/deployment.md.",
            ", ".join(local),
        )


def _log_app_env_configuration() -> None:
    """Record the resolved APP_ENV, and flag one that was probably never set.

    APP_ENV has a default, so an unset variable is indistinguishable from a
    deliberate APP_ENV=development: the service boots cleanly, serves /docs
    and /redoc, and turns `debug` on, which puts SQLAlchemy echo — every SQL
    statement — into the logs. The variable went missing from Railway once
    already and nothing said so (ADR 0011).

    The resolved value is logged unconditionally so it is greppable in Deploy
    Logs. The warning fires on the one combination that is never legitimate:
    a development environment whose allow-list has no localhost origin, which
    only a deployed service has.
    """
    logger.info("APP_ENV: %s (debug=%s)", settings.app_env, settings.debug)

    if settings.app_env != "development":
        return
    if not settings.cors_origins_look_like_production:
        return
    logger.warning(
        "APP_ENV=development but every allowed origin is a remote https:// "
        "domain (%s). If APP_ENV is unset it defaults to development, which "
        "serves /docs and /redoc publicly and logs every SQL statement. Set "
        "APP_ENV=production. See docs/deployment.md.",
        ", ".join(settings.cors_origins_list),
    )


_log_cors_configuration()
_log_app_env_configuration()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
)

# ── Rate limiting ─────────────────────────────────────────────────────────────
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Rate limit exceeded. Please slow down."},
    )


# ── Security headers ──────────────────────────────────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Added last, so it is the outermost middleware and sees every request before
# CORSMiddleware does — including the OPTIONS preflights CORSMiddleware answers
# itself without ever calling the app. It only observes; CORSMiddleware still
# decides. A rejection it makes silently now leaves a log line naming the
# origin to add.
app.add_middleware(OriginAuditMiddleware)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(api_router)
