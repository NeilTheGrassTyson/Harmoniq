"""
Prove the five R2 variables are correct, by using them.

`_log_feature_configuration` in app/main.py checks that the R2 group is
*present*. Presence is not correctness — that distinction is the whole reason
this script exists. TOKEN_ENCRYPTION_KEY was present, well-formed to the eye,
and wrong, and it cost a morning (ADR 0011). Every R2 variable can fail the
same way, and one of them cannot be validated by any amount of inspection:

    R2_PUBLIC_URL can point at a bucket that is not yours, or at nothing at
    all, and the upload will still succeed. The failure appears later, as an
    avatar that 404s for every user, with a green upload path behind it.

So this does a real round trip: HEAD the bucket, PUT a probe object, GET it
back over the public URL, DELETE it. Each step is attributed to the variable
it proves, so a failure names the variable to fix rather than reporting that
R2 "didn't work".

Usage, from backend/:

    poetry run python scripts/verify_r2.py

To check the production values before trusting them, pass them in rather than
editing .env — nothing is written anywhere:

    R2_ACCOUNT_ID=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... \
        R2_BUCKET_NAME=harmoniq-avatars R2_PUBLIC_URL=https://pub-x.r2.dev \
        poetry run python scripts/verify_r2.py

Exit code is 0 only if every check passed. No secret is ever printed: values
are reported by length and by a short prefix, never in full.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import httpx
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError

# Same shim as scripts/seed_catalog.py: running a file in scripts/ puts that
# directory on sys.path, not backend/, so `app` is not importable without it.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.services.storage import (  # noqa: E402
    _r2_client,
    describe_configuration_problems,
)

PROBE_BODY = b"harmoniq r2 verification probe\n"

OK = "  ok   "
BAD = " FAIL  "
WARN = " warn  "


def say(marker: str, message: str) -> None:
    print(f"[{marker}] {message}")


def check_shapes() -> list[str]:
    """Presence, then the shared shape rules from the storage service.

    The rules themselves live in `storage.describe_configuration_problems` so
    the boot log and this script cannot drift apart — two copies of a rule set
    is how the CI command set drifted from `npm run verify`, and the same trap
    applies here.
    """
    required = {
        "R2_ACCOUNT_ID": settings.r2_account_id,
        "R2_ACCESS_KEY_ID": settings.r2_access_key_id,
        "R2_SECRET_ACCESS_KEY": settings.r2_secret_access_key,
        "R2_BUCKET_NAME": settings.r2_bucket_name,
        "R2_PUBLIC_URL": settings.r2_public_url,
    }
    missing = [f"{name} is not set." for name, value in required.items() if not value]
    if missing:
        return missing
    return [f"{problem}." for problem in describe_configuration_problems()]


def main() -> int:
    print("Verifying R2 configuration\n")

    shape_problems = check_shapes()
    if shape_problems:
        for problem in shape_problems:
            say(BAD, problem)
        print("\nFailed before contacting R2. Fix the above and rerun.")
        return 1
    say(OK, "all five variables are set and well-formed")

    bucket = settings.r2_bucket_name
    assert bucket is not None
    client = _r2_client()
    key = f"_verify/r2-check-{uuid.uuid4()}.txt"

    # 1. Reach the endpoint and authenticate. Each error code below names a
    #    different variable, which is the point of doing this separately from
    #    the upload.
    try:
        client.head_bucket(Bucket=bucket)  # type: ignore[attr-defined]
    except EndpointConnectionError:
        say(
            BAD,
            f"Cannot reach https://{settings.r2_account_id}"
            ".r2.cloudflarestorage.com — R2_ACCOUNT_ID is almost certainly "
            "wrong (the hostname is built from it, so a bad id fails to "
            "resolve). Check it against the dashboard URL.",
        )
        return 1
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        blame = {
            "InvalidAccessKeyId": (
                "R2_ACCESS_KEY_ID is not a valid key for this account. If you "
                "rotated the token, the id changed too — both halves must come "
                "from the same token."
            ),
            "SignatureDoesNotMatch": (
                "R2_SECRET_ACCESS_KEY does not match R2_ACCESS_KEY_ID. These "
                "are shown together once, at token creation; a mismatched pair "
                "usually means one was copied from an older token."
            ),
            "NoSuchBucket": (
                f"Bucket {bucket!r} does not exist in this account. Check "
                "R2_BUCKET_NAME for a typo, and that the bucket lives in the "
                "account R2_ACCOUNT_ID names."
            ),
            "404": (
                f"Bucket {bucket!r} does not exist in this account (R2_BUCKET_NAME)."
            ),
            "AccessDenied": (
                "Credentials are valid but not allowed on this bucket. The "
                "token needs Object Read & Write, and if it was scoped to "
                "specific buckets, this one must be among them."
            ),
            "403": (
                "Credentials are valid but not allowed on this bucket "
                "(token needs Object Read & Write on it)."
            ),
        }.get(code)
        say(BAD, blame or f"R2 rejected the request: {code or exc}")
        return 1
    except BotoCoreError as exc:
        # Every other botocore failure — TLS, timeouts, proxies. Without this
        # arm the script dumps a 60-line traceback, which is precisely the
        # "reports nothing useful" behaviour it exists to replace.
        say(
            BAD,
            f"Could not complete the request to https://{settings.r2_account_id}"
            f".r2.cloudflarestorage.com — {type(exc).__name__}: {exc}. If the "
            "hostname looks wrong, R2_ACCOUNT_ID is the thing to check; "
            "otherwise this is a network, proxy or TLS problem between you and "
            "Cloudflare rather than a bad credential.",
        )
        return 1
    say(OK, f"endpoint, credentials and bucket {bucket!r} all check out")

    # 2. Write. Proves the token has write scope, which HeadBucket does not.
    try:
        client.put_object(  # type: ignore[attr-defined]
            Bucket=bucket, Key=key, Body=PROBE_BODY, ContentType="text/plain"
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        say(
            BAD,
            f"Upload failed ({code or exc}). The token can see the bucket but "
            "not write to it — it needs Object Read & Write, not Object Read "
            "Only. Avatar uploads would fail with a 500.",
        )
        return 1
    except BotoCoreError as exc:
        say(BAD, f"Upload failed — {type(exc).__name__}: {exc}")
        return 1
    say(OK, "wrote a probe object (token has write access)")

    # 3. Read it back the way a browser will. This is the only step that can
    #    validate R2_PUBLIC_URL, and the only one that catches a bucket whose
    #    public access was never switched on.
    public_url = f"{settings.r2_public_url}/{key}"
    verdict = 0
    try:
        response = httpx.get(public_url, timeout=15.0, follow_redirects=True)
        if response.status_code == 200 and response.content == PROBE_BODY:
            say(OK, "fetched it back over R2_PUBLIC_URL — public access works")
        elif response.status_code == 200:
            say(
                BAD,
                "R2_PUBLIC_URL returned 200 but not the bytes just uploaded. "
                "It points at a different bucket than R2_BUCKET_NAME.",
            )
            verdict = 1
        elif response.status_code in (401, 403):
            say(
                BAD,
                f"R2_PUBLIC_URL returned {response.status_code}. The bucket's "
                "public access is off — enable the r2.dev domain (or connect a "
                "custom domain) under Bucket → Settings → Public access. "
                "Uploads will succeed and every avatar will fail to load.",
            )
            verdict = 1
        elif response.status_code == 404:
            say(
                BAD,
                "R2_PUBLIC_URL returned 404 for an object that was just "
                "written. The URL points at the wrong bucket, or at a domain "
                "not bound to this one.",
            )
            verdict = 1
        else:
            say(BAD, f"R2_PUBLIC_URL returned {response.status_code}.")
            verdict = 1
    except httpx.HTTPError as exc:
        say(
            BAD,
            f"Could not reach R2_PUBLIC_URL ({settings.r2_public_url}): {exc}. "
            "Check the hostname.",
        )
        verdict = 1

    # 4. Clean up. A leftover probe is harmless but untidy, and a delete
    #    failure is worth knowing about on its own.
    try:
        client.delete_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
        say(OK, "removed the probe object")
    except (BotoCoreError, ClientError) as exc:
        say(
            WARN,
            f"Could not delete the probe object {key!r}: {exc}. Remove it by hand.",
        )

    if verdict == 0:
        print("\nAll five R2 variables are correct. Avatar upload will work.")
    else:
        print("\nSomething is wrong. See the FAIL line above.")
    return verdict


if __name__ == "__main__":
    sys.exit(main())
