"""TOKEN_ENCRYPTION_KEY is checked for presence in three places, validity in none.

The 2026-09-07 incident, and the last member of a family of four that all
shared one shape: a variable that was set, looked right, and was wrong.

The key was set to something that is not a Fernet key. Every presence check
passed. `_log_feature_configuration` reported Spotify fully configured. The
`/authorize` redirect worked, the token exchange returned 200, `/v1/me`
returned 200 — and then `encrypt_token` raised at the very last step of the
OAuth callback, after the user had already authorised, as a 500 whose cause
was invisible.

Validity here is exact rather than heuristic: either the key parses as a
Fernet key or it does not, and checking costs nothing — constructing a Fernet
is pure parsing with no IO.
"""

import logging

import pytest
from cryptography.fernet import Fernet

from app import main
from app.config import Settings
from app.core import crypto

_VALID = Fernet.generate_key().decode()


def _settings(key: str | None) -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://u:p@localhost/db",
        clerk_jwks_url="https://example.clerk.accounts.dev/.well-known/jwks.json",
        musicbrainz_user_agent="Harmoniq/0.1.0 test@example.com",
        token_encryption_key=key,
    )


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch):
    def _apply(key: str | None) -> None:
        settings = _settings(key)
        monkeypatch.setattr(main, "settings", settings)
        monkeypatch.setattr(crypto, "settings", settings)

    return _apply


# ── The helper ────────────────────────────────────────────────────────────────


def test_a_generated_key_is_accepted(configured) -> None:
    """The shape the documented generate command produces must pass."""
    configured(_VALID)

    assert crypto.describe_key_problem() is None


@pytest.mark.parametrize(
    ("label", "key"),
    [
        # The likeliest way this goes wrong: a copy that loses the trailing
        # "=". A valid key is always 44 characters; 43 is this.
        ("padding stripped", _VALID[:-1]),
        # Right length, not decodable — e.g. a hand-typed placeholder.
        ("not base64", "a" * 44),
        # Another credential pasted into the wrong field.
        ("a Clerk secret key", "sk_live_" + "x" * 40),
        ("too short", "short"),
        # Whitespace is NOT in this list on purpose — see the test below.
    ],
)
def test_an_unusable_key_is_reported(configured, label: str, key: str) -> None:
    configured(key)
    problem = crypto.describe_key_problem()

    assert problem is not None, label
    # The length is the diagnosis: 43 says the padding was lost.
    assert str(len(key)) in problem


def test_a_trailing_space_is_tolerated_by_fernet(configured) -> None:
    """Documents a real surprise, so nobody chases whitespace unnecessarily.

    Fernet accepts a valid key with trailing whitespace. That means whitespace
    is *not* a cause of this failure, and a key that fails validation is
    genuinely not a Fernet key rather than a good one that got mangled by a
    stray space.
    """
    configured(_VALID + " ")

    assert crypto.describe_key_problem() is None


def test_an_unset_key_is_not_this_functions_business(configured) -> None:
    """Absence is reported by _log_feature_configuration; two reports are noise."""
    configured(None)
    assert crypto.describe_key_problem() is None

    configured("")
    assert crypto.describe_key_problem() is None


# ── The boot log ──────────────────────────────────────────────────────────────


def _log(configured, caplog: pytest.LogCaptureFixture, key: str | None) -> str:
    configured(key)
    with caplog.at_level(logging.INFO, logger="app.main"):
        main._log_token_encryption_configuration()
    return caplog.text


def test_unusable_key_logs_an_error(configured, caplog) -> None:
    text = _log(configured, caplog, _VALID[:-1])

    assert caplog.records[0].levelno == logging.ERROR
    assert "TOKEN_ENCRYPTION_KEY" in text
    # Says what breaks, and when — the failure is at the *end* of the OAuth
    # flow, after the user has already authorised, which is why it reads as a
    # bug rather than a configuration problem.
    assert "authorised" in text
    # And how to fix it, without leaving the log line.
    assert "Fernet.generate_key()" in text


def test_valid_key_is_reported_too(configured, caplog) -> None:
    # ADR 0011: a state nothing ever prints is one nobody can check without
    # first reproducing a user-facing symptom.
    text = _log(configured, caplog, _VALID)

    assert "TOKEN_ENCRYPTION_KEY: valid" in text
    assert caplog.records[0].levelno == logging.INFO


def test_unset_key_says_nothing_here(configured, caplog) -> None:
    _log(configured, caplog, None)

    assert caplog.records == []


@pytest.mark.parametrize("key", [_VALID, _VALID[:-1], "sk_live_" + "x" * 40])
def test_the_key_is_never_logged(configured, caplog, key: str) -> None:
    """Valid or not, it may be a real secret from somewhere.

    A malformed value is often another credential pasted into the wrong
    field, so this must hold on the error path too — which is the path that
    actually prints something.
    """
    text = _log(configured, caplog, key)

    assert key not in text
