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


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise TokenCryptoError("Stored token could not be decrypted") from exc
