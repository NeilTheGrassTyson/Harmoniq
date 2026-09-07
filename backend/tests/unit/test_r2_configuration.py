"""R2 was the last feature group whose only signal was presence.

`_log_feature_configuration` reports the five R2 variables as configured when
all five are non-empty. That is the same check that reported Spotify fully
configured while TOKEN_ENCRYPTION_KEY was set to something that was not a
Fernet key at all — a variable that was present, plausible, and wrong
(ADR 0011, and tests/unit/test_token_key_configuration.py).

Four of the five fail that way. The fifth is worse: R2_PUBLIC_URL can point at
a different bucket, or at the signed S3 API endpoint, and the *upload still
succeeds* — the failure surfaces later as avatars that 404 for every user,
with a green upload path behind them. No presence check can catch that, and
neither can this file; proving it needs a round trip, which is what
scripts/verify_r2.py does.

What is pinned here is the cheap half: the shape rules that are free and
certain, shared by the boot log and that script so the two cannot drift apart.
"""

import logging

import pytest

from app import main
from app.config import Settings
from app.services import storage

_VALID_ACCOUNT = "0123456789abcdef0123456789abcdef"
_S3_ENDPOINT = f"https://{_VALID_ACCOUNT}.r2.cloudflarestorage.com"
_NAMES = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_PUBLIC_URL")


def _settings(**overrides: str | None) -> Settings:
    values: dict[str, str | None] = {
        "r2_account_id": _VALID_ACCOUNT,
        "r2_access_key_id": "a" * 32,
        "r2_secret_access_key": "b" * 64,
        "r2_bucket_name": "harmoniq-avatars",
        "r2_public_url": "https://pub-abc123.r2.dev",
    }
    values.update(overrides)
    return Settings(
        database_url="postgresql+asyncpg://u:p@localhost/db",
        clerk_jwks_url="https://example.clerk.accounts.dev/.well-known/jwks.json",
        musicbrainz_user_agent="Harmoniq/0.1.0 test@example.com",
        **values,  # type: ignore[arg-type]
    )


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch):
    def _apply(**overrides: str | None) -> None:
        settings = _settings(**overrides)
        monkeypatch.setattr(main, "settings", settings)
        monkeypatch.setattr(storage, "settings", settings)

    return _apply


def test_a_correct_configuration_reports_nothing(configured) -> None:
    """The shape a real Cloudflare setup produces must pass cleanly."""
    configured()

    assert storage.describe_configuration_problems() == []


def test_absence_is_not_this_functions_business(configured) -> None:
    """An unconfigured deployment must not be complained about twice.

    `_log_feature_configuration` already names every group that is not set. If
    this function also reported absence, every boot of a deployment without R2
    would log the same problem from two places, and the operator would learn
    to skim both.
    """
    configured(r2_account_id=None)

    assert storage.describe_configuration_problems() == []


@pytest.mark.parametrize(
    ("label", "overrides", "expected"),
    [
        # storage.py builds URLs as f"{r2_public_url}/{key}". A trailing slash
        # is invisible in a dashboard and yields "https://host//avatars/...".
        (
            "trailing slash",
            {"r2_public_url": "https://pub-abc123.r2.dev/"},
            "double slash",
        ),
        # The S3 endpoint requires signed requests, so every avatar 401s for
        # end users while uploads keep succeeding.
        (
            "public URL set to the S3 API endpoint",
            {"r2_public_url": _S3_ENDPOINT},
            "signed",
        ),
        (
            "public URL not https",
            {"r2_public_url": "http://pub-abc.r2.dev"},
            "https://",
        ),
        # The likeliest account-id mistake: pasting the bucket name, an API
        # token, or the token id instead of the account id.
        (
            "account id is not hex",
            {"r2_account_id": "harmoniq-avatars"},
            "32 lowercase",
        ),
        (
            "account id too short",
            {"r2_account_id": "0123456789abcdef"},
            "32 lowercase",
        ),
        # Unlike Fernet, an S3 signature does not tolerate whitespace: the
        # secret is silently wrong and nothing anywhere shows it.
        (
            "secret with a trailing newline",
            {"r2_secret_access_key": "b" * 64 + "\n"},
            "whitespace",
        ),
        (
            "access key id with a leading space",
            {"r2_access_key_id": " " + "a" * 32},
            "whitespace",
        ),
    ],
)
def test_a_broken_value_is_named(configured, label, overrides, expected) -> None:
    """Each problem must name the variable and say what is wrong with it.

    "R2 is misconfigured" would be no better than the silence it replaces.
    """
    configured(**overrides)

    problems = storage.describe_configuration_problems()

    assert problems, f"{label} produced no problem"
    joined = " ".join(problems)
    assert expected in joined, f"{label}: {joined!r} does not explain the problem"
    assert any(name in joined for name in _NAMES), f"{label}: no variable named"


def test_boot_logs_the_problem_as_an_error(configured, caplog) -> None:
    """A misconfiguration must be visible in Railway's Deploy Logs.

    The whole point of ADR 0011: a variable that cannot work says so at boot,
    rather than failing per-request inside a handler whose response body does
    not name it.
    """
    configured(r2_public_url="https://pub-abc123.r2.dev/")

    with caplog.at_level(logging.ERROR, logger=main.logger.name):
        main._log_r2_configuration()

    assert "R2 is configured but unusable" in caplog.text
    assert "double slash" in caplog.text
    assert "verify_r2.py" in caplog.text, "must point at the tool that checks the rest"


def test_boot_is_silent_when_r2_is_correct(configured, caplog) -> None:
    """A correct configuration logs nothing, so the errors stay meaningful."""
    configured()

    with caplog.at_level(logging.ERROR, logger=main.logger.name):
        main._log_r2_configuration()

    assert caplog.text == ""
