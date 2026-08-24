"""Unit tests for settings parsing that has bitten a live deploy before."""

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
