"""Unit tests for settings parsing that has bitten a live deploy before."""

import pytest

from app.config import Settings


def _settings(origins: str) -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://u:p@localhost/db",
        clerk_jwks_url="https://example.clerk.accounts.dev/.well-known/jwks.json",
        musicbrainz_user_agent="Harmoniq/0.1.0 test@example.com",
        cors_allowed_origins=origins,
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
