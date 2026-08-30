"""
Clerk JWT verification.

Every protected route depends on `get_current_user`, which extracts and
verifies the Clerk session token. The backend never stores sessions —
verification is stateless against Clerk's public JWKS endpoint.
"""

import logging
import time
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from jose.exceptions import JWKError

from app.config import settings

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer()
_optional_bearer = HTTPBearer(auto_error=False)


# How long a fetched JWKS is trusted before it is fetched again.
_JWKS_TTL_SECONDS = 3600.0

# Floor between forced refetches, so a caller presenting a stream of tokens
# with unknown `kid`s cannot turn this into an outbound request flood.
_JWKS_REFETCH_MIN_INTERVAL_SECONDS = 60.0

_jwks_cache: dict | None = None  # type: ignore[type-arg]
_jwks_fetched_at = 0.0
_jwks_last_forced_at = 0.0


def _fetch_jwks(force: bool = False) -> dict:  # type: ignore[type-arg]
    """
    Fetches Clerk's public JWKS, cached for `_JWKS_TTL_SECONDS`.

    This was `@lru_cache`d for the process lifetime, which made a Clerk key
    rotation an outage lasting until somebody thought to restart the service.
    `force` re-fetches early — see `_verify_clerk_token`, which uses it to
    recover from a rotation on the first token signed by the new key.
    """
    global _jwks_cache, _jwks_fetched_at, _jwks_last_forced_at
    now = time.monotonic()

    if force:
        if now - _jwks_last_forced_at < _JWKS_REFETCH_MIN_INTERVAL_SECONDS:
            return _jwks_cache or {}
        _jwks_last_forced_at = now
    elif _jwks_cache is not None and now - _jwks_fetched_at < _JWKS_TTL_SECONDS:
        return _jwks_cache

    response = httpx.get(settings.clerk_jwks_url, timeout=10)
    response.raise_for_status()
    _jwks_cache = response.json()
    _jwks_fetched_at = now
    return _jwks_cache


def _find_key(jwks: dict, kid: str | None) -> dict | None:  # type: ignore[type-arg]
    return next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)


def _verify_clerk_token(token: str) -> dict:  # type: ignore[type-arg]
    try:
        jwks = _fetch_jwks()
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        key = _find_key(jwks, kid)
        if key is None:
            # An unrecognised `kid` is one of two things: a rotation this
            # process has not picked up, or a JWKS from a different Clerk
            # instance than the one issuing tokens. Re-fetch once — that makes
            # a rotation self-healing — and if the key is still absent, say so
            # with both sides named. Clerk's `kid` is the instance id, so a
            # mismatch here is a mismatch of instances, which is a
            # CLERK_JWKS_URL pointing at the wrong one (2026-08-30; see
            # docs/deployment.md).
            jwks = _fetch_jwks(force=True)
            key = _find_key(jwks, kid)
        if key is None:
            logger.warning(
                "JWT key not found: token kid=%s is absent from the JWKS at "
                "%s, which offers [%s]. If those are different Clerk "
                "instances, CLERK_JWKS_URL is pointing at the wrong one.",
                kid,
                settings.clerk_jwks_url,
                ", ".join(str(k.get("kid")) for k in jwks.get("keys", [])) or "<none>",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT key not found",
            )
        payload: dict = jwt.decode(  # type: ignore[type-arg]
            token,
            key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        return payload
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from exc
    except (JWTError, JWKError) as exc:
        logger.warning("JWT verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> str:
    """
    FastAPI dependency that returns the Clerk user ID (the `sub` claim).
    Raises 401 if the token is missing, expired, or invalid.
    """
    payload = _verify_clerk_token(credentials.credentials)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )
    return user_id


async def get_optional_clerk_id(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_optional_bearer)
    ],
) -> str | None:
    """
    FastAPI dependency that returns the Clerk user ID when a valid Bearer token
    is present, or None when no token is provided. Used for public endpoints
    that personalise their response based on the viewer's identity.
    """
    if credentials is None:
        return None
    try:
        payload = _verify_clerk_token(credentials.credentials)
        return payload.get("sub")
    except HTTPException:
        return None
