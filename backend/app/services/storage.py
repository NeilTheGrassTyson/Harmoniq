"""
Cloudflare R2 storage service for avatar uploads.

Files are uploaded directly from the backend (not via presigned URL) so that
server-side content validation can be performed before persisting anything.
The DB stores the resulting public URL only; raw bytes never touch Postgres.
"""

import asyncio
import logging
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
        endpoint_url=(
            f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
        ),
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
