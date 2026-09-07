"""The boot check for a SPOTIFY_REDIRECT_URI left over from development.

The failure this exists to prevent, on 2026-09-07: all four Spotify variables
were set, so the boot log reported Spotify fully configured — and the redirect
URI was still `http://127.0.0.1:3000/spotify-callback`, straight out of
`.env.example`.

Nothing errors in that state. Spotify sends the browser to whatever we pass,
so the user logs in successfully and is redirected to 127.0.0.1 — their own
device — where nothing is listening. The server never sees the callback, so
it has nothing to report. It took a round trip through Spotify on a phone to
find, and the fix was one variable.

Presence checks cannot catch this: the variable is set, and its value is
well-formed. Only its *plausibility for this environment* is wrong, which is
exactly what `_log_cors_configuration` already checks for the allow-list.
"""

import logging

import pytest

from app import main
from app.config import Settings

_PROD_ORIGINS = "https://harmoniq.live,https://www.harmoniq.live"
_DEV_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def _settings(**overrides: object) -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://u:p@localhost/db",
        clerk_jwks_url="https://example.clerk.accounts.dev/.well-known/jwks.json",
        musicbrainz_user_agent="Harmoniq/0.1.0 test@example.com",
        **overrides,  # type: ignore[arg-type]
    )


def _log(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    settings: Settings,
) -> str:
    monkeypatch.setattr(main, "settings", settings)
    with caplog.at_level(logging.INFO, logger="app.main"):
        main._log_spotify_configuration()
    return caplog.text


def _warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.levelno >= logging.WARNING]


# ── The incident ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "redirect_uri",
    [
        # The exact value from .env.example, and the one that shipped.
        "http://127.0.0.1:3000/spotify-callback",
        "http://localhost:3000/spotify-callback",
        "http://[::1]:3000/spotify-callback",
        # https to a loopback host is still a development value.
        "https://localhost:3000/spotify-callback",
        # Plain http to a real domain: Spotify rejects it, and it is not ours.
        "http://harmoniq.live/spotify-callback",
    ],
)
def test_development_redirect_uri_warns_in_production(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    redirect_uri: str,
) -> None:
    text = _log(
        monkeypatch,
        caplog,
        _settings(
            app_env="production",
            cors_allowed_origins=_PROD_ORIGINS,
            spotify_redirect_uri=redirect_uri,
        ),
    )

    assert _warnings(caplog)
    assert "SPOTIFY_REDIRECT_URI" in text
    # The value itself, so the log says what to change it from.
    assert redirect_uri in text


def test_production_redirect_uri_is_accepted(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _log(
        monkeypatch,
        caplog,
        _settings(
            app_env="production",
            cors_allowed_origins=_PROD_ORIGINS,
            spotify_redirect_uri="https://harmoniq.live/spotify-callback",
        ),
    )

    assert _warnings(caplog) == []


def test_loopback_is_correct_on_a_development_machine(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Spotify requires a loopback IP literal for http — this is right locally.

    The check must not nag a developer whose configuration is correct, or it
    becomes noise and stops being read.
    """
    _log(
        monkeypatch,
        caplog,
        _settings(
            app_env="development",
            cors_allowed_origins=_DEV_ORIGINS,
            spotify_redirect_uri="http://127.0.0.1:3000/spotify-callback",
        ),
    )

    assert _warnings(caplog) == []


# ── The apex/www trap ─────────────────────────────────────────────────────────


def test_redirect_origin_outside_the_allow_list_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The callback is a frontend page, so its origin should be a frontend one.

    A www/apex mismatch sends the user to an origin that does not hold their
    session, which fails in a way that looks nothing like a configuration
    problem.
    """
    text = _log(
        monkeypatch,
        caplog,
        _settings(
            app_env="production",
            cors_allowed_origins="https://harmoniq.live",
            spotify_redirect_uri="https://www.harmoniq.live/spotify-callback",
        ),
    )

    assert _warnings(caplog)
    assert "CORS_ALLOWED_ORIGINS" in text


def test_matching_origin_does_not_warn(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _log(
        monkeypatch,
        caplog,
        _settings(
            app_env="production",
            cors_allowed_origins=_PROD_ORIGINS,
            spotify_redirect_uri="https://www.harmoniq.live/spotify-callback",
        ),
    )

    assert _warnings(caplog) == []


# ── Boundaries ────────────────────────────────────────────────────────────────


def test_unset_redirect_uri_says_nothing_here(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Absence belongs to _log_feature_configuration; two reports would be noise."""
    _log(monkeypatch, caplog, _settings(app_env="production"))

    assert caplog.records == []


def test_resolved_value_is_always_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # ADR 0011: a value nothing ever prints is one nobody can check without
    # first reproducing a user-facing symptom.
    text = _log(
        monkeypatch,
        caplog,
        _settings(
            app_env="production",
            cors_allowed_origins=_PROD_ORIGINS,
            spotify_redirect_uri="https://harmoniq.live/spotify-callback",
        ),
    )

    assert "https://harmoniq.live/spotify-callback" in text
