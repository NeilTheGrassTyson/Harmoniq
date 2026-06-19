"""
Clerk webhook handler.

All payloads are verified against Clerk's Svix signing secret before
processing. Unverified payloads are rejected with 400 and logged.

This endpoint must NOT use the get_current_user JWT dependency — Clerk sends
webhooks with Svix signatures, not Bearer tokens.
"""

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services import user as user_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

# Webhooks are verified against a 5-minute timestamp window to prevent replays.
_TIMESTAMP_TOLERANCE_SECONDS = 300


def _verify_svix_signature(
    body: bytes,
    svix_id: str,
    svix_timestamp: str,
    svix_signature: str,
) -> None:
    """
    Verifies a Svix (Clerk webhook) signature.
    Raises ValueError with a descriptive message on any verification failure.
    """
    try:
        ts = int(svix_timestamp)
    except ValueError as exc:
        raise ValueError("Missing or non-numeric svix-timestamp header") from exc

    if abs(time.time() - ts) > _TIMESTAMP_TOLERANCE_SECONDS:
        raise ValueError("Webhook timestamp is outside the 5-minute tolerance window")

    if not settings.clerk_webhook_secret:
        raise ValueError(
            "Clerk webhook secret is not configured (CLERK_WEBHOOK_SECRET)."
        )
    secret = settings.clerk_webhook_secret
    if secret.startswith("whsec_"):
        secret = secret[6:]
    try:
        secret_bytes = base64.b64decode(secret)
    except Exception as exc:
        raise ValueError("Clerk webhook secret is not valid base64") from exc

    signed_content = f"{svix_id}.{svix_timestamp}.{body.decode('utf-8')}"
    expected = hmac.digest(
        secret_bytes, signed_content.encode("utf-8"), hashlib.sha256
    )
    expected_b64 = base64.b64encode(expected).decode()

    for sig in svix_signature.split(" "):
        if sig.startswith("v1,") and hmac.compare_digest(expected_b64, sig[3:]):
            return

    raise ValueError("No matching signature found in svix-signature header")


@router.post("/clerk", status_code=status.HTTP_200_OK)
async def clerk_webhook(
    request: Request,
    session: DbSession,
) -> dict[str, bool]:
    body = await request.body()
    svix_id = request.headers.get("svix-id", "")
    svix_timestamp = request.headers.get("svix-timestamp", "")
    svix_signature = request.headers.get("svix-signature", "")

    try:
        _verify_svix_signature(body, svix_id, svix_timestamp, svix_signature)
    except ValueError as exc:
        logger.warning("Clerk webhook verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload.",
        ) from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        ) from exc

    event_type: str = payload.get("type", "")
    data: dict[str, Any] = payload.get("data", {})

    logger.info("Clerk webhook received event_type=%s", event_type)

    if event_type == "user.updated":
        await _handle_user_updated(session, data)

    return {"received": True}


async def _handle_user_updated(session: DbSession, data: dict[str, Any]) -> None:
    clerk_id: str | None = data.get("id")
    if not clerk_id:
        logger.warning("user.updated webhook missing user ID")
        return

    first = (data.get("first_name") or "").strip()
    last = (data.get("last_name") or "").strip()
    display_name = f"{first} {last}".strip() or None
    avatar_url: str | None = data.get("image_url") or None

    await user_svc.sync_from_clerk(session, clerk_id, display_name, avatar_url)
    await session.commit()
