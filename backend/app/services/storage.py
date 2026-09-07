"""
Cloudflare R2 storage service for avatar uploads.

Files are uploaded directly from the backend (not via presigned URL) so that
server-side content validation can be performed before persisting anything.
The DB stores the resulting public URL only; raw bytes never touch Postgres.
"""

import asyncio
import logging
import re
import uuid
from functools import lru_cache, partial

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings

logger = logging.getLogger(__name__)

# Mapping of validated MIME type → file extension used in the R2 key.
_CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset(_CONTENT_TYPE_TO_EXT)

MAX_AVATAR_BYTES: int = 5 * 1024 * 1024  # 5 MB

# Cloudflare account ids are 32 lowercase hex characters.
_ACCOUNT_ID_RE = re.compile(r"[0-9a-f]{32}")


def detect_image_content_type(data: bytes) -> str | None:
    """
    Determine image type by inspecting magic bytes.
    Returns the MIME type string, or None if unrecognised.
    Independent of file extension and Content-Type header.
    """
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def describe_configuration_problems() -> list[str]:
    """Why the configured R2 variables cannot work, or an empty list.

    Sibling of `crypto.describe_key_problem`, and here for the same reason:
    `_log_feature_configuration` checks this group for presence, and presence
    is not validity. Every failure in the 2026-09-07 family was a variable
    that was set, looked right, and was wrong (ADR 0011).

    Only the checks that are free and certain live here — no network, no
    credentials sent anywhere, so this is safe to call at boot. Anything
    needing a round trip (does the bucket exist, does R2_PUBLIC_URL actually
    serve it) belongs in scripts/verify_r2.py, which uses this first.

    Absence is deliberately not reported: that is
    `_log_feature_configuration`'s job, and duplicating it would mean an
    unconfigured deployment logs the same complaint twice.

    Returns reasons rather than raising. A broken R2 config must not stop the
    service booting — avatars are one feature, and refusing to start would
    turn a broken integration into an outage.
    """
    values = {
        "R2_ACCOUNT_ID": settings.r2_account_id,
        "R2_ACCESS_KEY_ID": settings.r2_access_key_id,
        "R2_SECRET_ACCESS_KEY": settings.r2_secret_access_key,
        "R2_BUCKET_NAME": settings.r2_bucket_name,
        "R2_PUBLIC_URL": settings.r2_public_url,
    }
    if not all(values.values()):
        return []

    problems: list[str] = []

    for name, value in values.items():
        # `value` is known non-empty from the all() guard above; the truthiness
        # test re-narrows it for mypy without an `assert`, which Bandit flags
        # under B101 because -O strips it out of the running service.
        # Unlike Fernet, which accepts a key with trailing whitespace, an S3
        # signature does not — a stray space silently invalidates the secret,
        # and no dashboard will show it to you.
        if value and value != value.strip():
            problems.append(f"{name} has leading or trailing whitespace")

    account_id = settings.r2_account_id or ""
    if not _ACCOUNT_ID_RE.fullmatch(account_id):
        problems.append(
            f"R2_ACCOUNT_ID is {len(account_id)} characters and not 32 lowercase "
            "hex — it is the id from the dashboard URL, not an API token"
        )

    public_url = settings.r2_public_url or ""
    if not public_url.startswith("https://"):
        problems.append("R2_PUBLIC_URL does not start with https://")
    if public_url.endswith("/"):
        problems.append(
            "R2_PUBLIC_URL ends with a slash, which yields a double slash in "
            "every avatar URL this service returns"
        )
    if ".r2.cloudflarestorage.com" in public_url:
        problems.append(
            "R2_PUBLIC_URL points at the S3 API endpoint, which requires signed "
            "requests — every avatar would 401 for end users"
        )

    return problems


@lru_cache(maxsize=1)
def _r2_client() -> object:
    missing = not (
        settings.r2_account_id
        and settings.r2_access_key_id
        and settings.r2_secret_access_key
    )
    if missing:
        raise StorageError(
            "R2 credentials are not configured"
            " (R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY)."
        )
    return boto3.client(
        "s3",
        endpoint_url=(f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"),
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def _do_put_object(
    client: object,
    bucket: str,
    key: str,
    data: bytes,
    content_type: str,
) -> None:
    client.put_object(  # type: ignore[attr-defined]
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


async def upload_avatar(data: bytes, content_type: str) -> str:
    """
    Upload validated avatar bytes to R2 and return the public URL.
    Raises StorageError on upload failure.
    """
    if not (settings.r2_bucket_name and settings.r2_public_url):
        raise StorageError(
            "R2 bucket is not configured (R2_BUCKET_NAME / R2_PUBLIC_URL)."
        )
    ext = _CONTENT_TYPE_TO_EXT[content_type]
    key = f"avatars/{uuid.uuid4()}.{ext}"
    client = _r2_client()
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(
            None,
            partial(
                _do_put_object,
                client,
                settings.r2_bucket_name,
                key,
                data,
                content_type,
            ),
        )
    except (BotoCoreError, ClientError) as exc:
        logger.error("R2 upload failed for key=%s: %s", key, exc)
        raise StorageError("Avatar upload failed.") from exc
    return f"{settings.r2_public_url}/{key}"


class StorageError(Exception):
    """Raised when an R2 operation fails."""
