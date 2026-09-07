"""
Symmetric encryption for external credentials at rest (Fernet).

Used for Spotify OAuth refresh tokens (spec: phase-1-spotify-listening.md).
The key comes from TOKEN_ENCRYPTION_KEY — optional at import, validated at
the call site per the house config pattern. Rotating or losing the key
orphans stored tokens (users simply reconnect).
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class TokenCryptoError(Exception):
    """Encryption/decryption failed or the key is not configured."""


def _fernet() -> Fernet:
    if not settings.token_encryption_key:
        raise TokenCryptoError("TOKEN_ENCRYPTION_KEY is not configured")
    try:
        return Fernet(settings.token_encryption_key.encode())
    except ValueError as exc:
        # A malformed key (not 32 url-safe base64 bytes) must fail the same
        # way as a missing one — callers only handle TokenCryptoError.
        raise TokenCryptoError("TOKEN_ENCRYPTION_KEY is malformed") from exc


def describe_key_problem() -> str | None:
    """Why the configured TOKEN_ENCRYPTION_KEY cannot be used, or None if it can.

    Presence is not validity, and this key is checked for presence in three
    places and for validity in none. On 2026-09-07 it was set to something
    that was not a Fernet key at all: every check passed, the boot log
    reported Spotify fully configured, both Spotify API calls succeeded, and
    the failure surfaced only when `encrypt_token` ran at the very end of the
    OAuth callback — as a 500 whose cause was, at the time, invisible.

    Validation is local and free: constructing a Fernet is pure parsing, no
    IO. Called at boot so a key that cannot work says so before anyone tries
    to connect an account.

    Deliberately returns a reason rather than raising: an unusable key must
    not stop the service booting. Every other feature still works, and
    refusing to start would turn a broken integration into an outage.
    """
    key = settings.token_encryption_key
    if not key:
        return None  # Absence is the caller's business, not this function's.
    try:
        Fernet(key.encode())
    except (ValueError, TypeError):
        # The length is the diagnosis and is safe to report: a valid key is
        # always 44 characters, and 43 means the trailing "=" was lost in a
        # copy — the single most common way this goes wrong. The key itself is
        # never included, here or anywhere.
        return (
            f"it is {len(key)} characters and is not a valid Fernet key "
            "(expected 44 url-safe base64 characters ending in '=')"
        )
    return None


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise TokenCryptoError("Stored token could not be decrypted") from exc
