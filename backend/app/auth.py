"""
Clerk JWT verification.

Every protected route depends on `get_current_user`, which extracts and
verifies the Clerk session token. The backend never stores sessions —
verification is stateless against Clerk's public JWKS endpoint.
"""
import logging
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from jose.exceptions import JWKError

from app.config import settings

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer()


@lru_cache(maxsize=1)
def _fetch_jwks() -> dict:  # type: ignore[type-arg]
    """
    Fetches Clerk's public JWKS and caches it for the process lifetime.
    In production, a key rotation would require a process restart — acceptable
    given Clerk's key rotation cadence. A TTL cache can be added if needed.
    """
    response = httpx.get(settings.clerk_jwks_url, timeout=10)
    response.raise_for_status()
    return response.json()  # type: ignore[no-any-return]


def _verify_clerk_token(token: str) -> dict:  # type: ignore[type-arg]
    try:
        jwks = _fetch_jwks()
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        key = next(
            (k for k in jwks.get("keys", []) if k.get("kid") == kid), None
        )
        if key is None:
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
