"""Unit tests for settings parsing that has bitten a live deploy before."""

import logging

import pytest
from pydantic import ValidationError

from app.config import Settings


def _settings(origins: str = "http://localhost:3000", **overrides: object) -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://u:p@localhost/db",
        clerk_jwks_url="https://example.clerk.accounts.dev/.well-known/jwks.json",
        musicbrainz_user_agent="Harmoniq/0.1.0 test@example.com",
        cors_allowed_origins=origins,
        **overrides,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("https://app.example.com", ["https://app.example.com"]),
        # A trailing slash never matches an Origin header, which is always a
        # bare scheme://host[:port].
        ("https://app.example.com/", ["https://app.example.com"]),
        (
            "https://app.example.com/, http://localhost:3000",
            ["https://app.example.com", "http://localhost:3000"],
        ),
        # A trailing comma or stray whitespace must not yield an empty origin,
        # which would be compared against every request and never match.
        ("https://app.example.com, ", ["https://app.example.com"]),
        ("https://app.example.com,/", ["https://app.example.com"]),
    ],
)
def test_cors_origins_are_normalised(configured: str, expected: list[str]) -> None:
    assert _settings(configured).cors_origins_list == expected


# ── APP_ENV ───────────────────────────────────────────────────────────────────
# app_env gates /docs and /redoc in main.py. A bare str let "prod" or
# "Production" fail the `!= "production"` check silently and serve the API docs
# publicly, so the value is constrained and an invalid one must not start.


@pytest.mark.parametrize("value", ["development", "test", "production"])
def test_valid_app_env_is_accepted(value: str) -> None:
    assert _settings(app_env=value).app_env == value


@pytest.mark.parametrize("value", ["prod", "Production", "PRODUCTION", "staging", ""])
def test_invalid_app_env_is_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        _settings(app_env=value)


@pytest.mark.parametrize(
    ("app_env", "expected"),
    [
        ("development", True),
        # Not derived as `!= "production"`: that would turn SQLAlchemy echo on
        # in CI, which runs APP_ENV=test.
        ("test", False),
        ("production", False),
    ],
)
def test_debug_is_derived_from_app_env(app_env: str, expected: bool) -> None:
    assert _settings(app_env=app_env).debug is expected


# ── APP_ENV startup guard ─────────────────────────────────────────────────────
# A missing APP_ENV is indistinguishable from APP_ENV=development: it boots
# cleanly, serves /docs and /redoc, and turns SQLAlchemy echo on. The one
# combination that is never legitimate is a development environment with no
# localhost origin, because a developer's machine always needs one.


@pytest.mark.parametrize(
    ("origins", "expected"),
    [
        ("https://harmoniq.live,https://www.harmoniq.live", True),
        ("https://harmoniq.live", True),
        # A localhost origin, on any scheme, means a developer's machine.
        ("https://harmoniq.live,http://localhost:3000", False),
        ("https://localhost:3000", False),
        ("http://localhost:3000", False),
        # Plain http:// is never a production origin.
        ("http://harmoniq.live", False),
        ("https://harmoniq.live,http://harmoniq.live", False),
        # An empty allow-list is a different misconfiguration, and `all()` over
        # nothing is vacuously true — it must not be reported as production.
        ("", False),
        (" , ", False),
    ],
)
def test_cors_origins_look_like_production(origins: str, expected: bool) -> None:
    assert _settings(origins).cors_origins_look_like_production is expected


@pytest.mark.parametrize(
    ("app_env", "origins", "warns"),
    [
        # The incident: APP_ENV absent, so development, on a real deployment.
        ("development", "https://harmoniq.live", True),
        # Declared correctly — nothing to say.
        ("production", "https://harmoniq.live", False),
        # An actual development machine.
        ("development", "http://localhost:3000", False),
        ("development", "https://harmoniq.live,http://localhost:3000", False),
        # CI runs APP_ENV=test and must stay quiet.
        ("test", "https://harmoniq.live", False),
    ],
)
def test_implausible_app_env_is_warned_about_at_startup(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    app_env: str,
    origins: str,
    warns: bool,
) -> None:
    from app import main

    monkeypatch.setattr(main, "settings", _settings(origins, app_env=app_env))

    with caplog.at_level(logging.WARNING, logger="app.main"):
        main._log_app_env_configuration()

    assert bool(caplog.records) is warns
    if warns:
        assert "APP_ENV" in caplog.text


def test_resolved_app_env_is_always_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Absence was invisible because nothing ever named the value. The log line
    # is the fix, so it must appear even when the configuration is correct.
    from app import main

    monkeypatch.setattr(main, "settings", _settings(app_env="production"))

    with caplog.at_level(logging.INFO, logger="app.main"):
        main._log_app_env_configuration()

    assert "APP_ENV: production" in caplog.text
