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


def _log_clerk_configuration() -> None:
    """Record the resolved JWKS URL, and flag one that can't be right.

    A CLERK_JWKS_URL pointing at a *different* Clerk instance than the one
    issuing tokens fails in the least legible way available: the fetch
    succeeds, the JWKS parses, and every authenticated request comes back
    401 "JWT key not found" while unauthenticated ones keep working. The site
    browses fine and nothing a signed-in user does succeeds (2026-08-30).

    Clerk's development instances live on *.clerk.accounts.dev and its
    production instances on the app's own domain, so a dev host in a
    production deployment is the shape to catch. The resolved value is logged
    unconditionally so it is greppable in Deploy Logs (ADR 0011).
    """
    logger.info("Clerk JWKS URL: %s", settings.clerk_jwks_url)

    if settings.app_env != "production":
        return
    if ".clerk.accounts.dev" not in settings.clerk_jwks_url:
        return
    logger.warning(
        "APP_ENV=production but CLERK_JWKS_URL (%s) is a Clerk *development* "
        "instance. Tokens minted by the production instance will be rejected "
        "with 401 'JWT key not found' — every authenticated request fails "
        "while public pages keep working. See docs/deployment.md.",
        settings.clerk_jwks_url,
    )


def _log_clerk_secret_key_configuration() -> None:
    """Flag a test-mode Clerk secret key in a production deployment.

    The two Clerk variables are set together and go wrong together: an
    instance mix-up in CLERK_JWKS_URL usually means CLERK_SECRET_KEY is from
    the same wrong instance. That one fails even more quietly — the Management
    API call marking a new account `onboarded` is deliberately non-fatal, so
    signup succeeds, the flag is never written, and `proxy.ts` falls back to
    asking the backend on every navigation forever after.

    Only the key's prefix is ever logged; the key itself never is.
    """
    key = settings.clerk_secret_key
    if not key:
        return
    # Clerk keys are sk_<mode>_<random>. Anything else is logged as
    # unrecognised rather than partially printed — never risk the key itself.
    parts = key.split("_")
    prefix = "_".join(parts[:2]) if len(parts) >= 3 else "<unrecognised format>"
    logger.info("Clerk secret key: %s… (%d chars)", prefix, len(key))

    # A Clerk secret key is sk_test_… or sk_live_… and nothing else, so a value
    # that is neither is some *other* credential in the slot — a publishable
    # key, the webhook signing secret, a URL. That fails the same silent way as
    # a wrong-instance key and is worth naming in any environment.
    if not key.startswith(("sk_test_", "sk_live_")):
        logger.warning(
            "CLERK_SECRET_KEY does not look like a Clerk secret key (expected "
            "sk_test_… or sk_live_…, got %s…). Whatever is in the slot, the "
            "Management API call that writes publicMetadata.onboarded on a new "
            "account will fail — silently, because it is deliberately "
            "non-fatal. See docs/deployment.md.",
            prefix,
        )
        return

    if settings.app_env != "production":
        return
    if not key.startswith("sk_test_"):
        return
    logger.warning(
        "APP_ENV=production but CLERK_SECRET_KEY is a test-mode key "
        "(sk_test_…). New accounts will be created without "
        "publicMetadata.onboarded, because the Management API call is scoped "
        "to a different Clerk instance. See docs/deployment.md."
    )


_log_cors_configuration()
_log_app_env_configuration()
_log_clerk_configuration()
_log_clerk_secret_key_configuration()

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
