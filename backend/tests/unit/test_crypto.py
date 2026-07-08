"""Unit tests for the Fernet token-encryption helpers — no database required."""

import pytest
from cryptography.fernet import Fernet

from app.config import settings
from app.core.crypto import TokenCryptoError, decrypt_token, encrypt_token


@pytest.fixture
def fernet_key(monkeypatch: pytest.MonkeyPatch) -> str:
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "token_encryption_key", key)
    return key


class TestTokenCrypto:
    def test_round_trip(self, fernet_key: str) -> None:
        ciphertext = encrypt_token("refresh-token-value")
        assert ciphertext != "refresh-token-value"
        assert ciphertext.startswith("gAAAA")
        assert decrypt_token(ciphertext) == "refresh-token-value"

    def test_tampered_ciphertext_raises(self, fernet_key: str) -> None:
        ciphertext = encrypt_token("refresh-token-value")
        tampered = ciphertext[:-4] + "AAAA"
        with pytest.raises(TokenCryptoError):
            decrypt_token(tampered)

    def test_wrong_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        key_a = Fernet.generate_key().decode()
        monkeypatch.setattr(settings, "token_encryption_key", key_a)
        ciphertext = encrypt_token("refresh-token-value")

        key_b = Fernet.generate_key().decode()
        monkeypatch.setattr(settings, "token_encryption_key", key_b)
        with pytest.raises(TokenCryptoError):
            decrypt_token(ciphertext)

    def test_missing_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "token_encryption_key", None)
        with pytest.raises(TokenCryptoError):
            encrypt_token("anything")
