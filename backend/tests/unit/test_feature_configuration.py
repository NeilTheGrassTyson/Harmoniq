"""The optional-feature boot log, and what it must never print.

Four separate incidents share one shape: a variable is missing, an optional
feature fails deep inside a request handler, the body deliberately does not
name the cause, and the symptom the user reports points somewhere else —
"search is broken" (CORS), "profiles won't load" (APP_ENV), "Spotify says
it isn't connected" (Spotify credentials or the Fernet key).

None of them were answerable from Deploy Logs. `_log_feature_configuration`
is the answer at boot, before anyone opens the app, so these tests pin both
halves of its contract: it names every incomplete group, and it never prints
a value.
"""

import logging

import pytest

from app import main
from app.config import Settings

_SPOTIFY_FIELDS = (
    "spotify_client_id",
    "spotify_client_secret",
    "spotify_redirect_uri",
    "token_encryption_key",
)
_R2_FIELDS = (
    "r2_account_id",
    "r2_access_key_id",
    "r2_secret_access_key",
    "r2_bucket_name",
    "r2_public_url",
)
_ALL_OPTIONAL = (
    _SPOTIFY_FIELDS
    + _R2_FIELDS
    + (
        "clerk_secret_key",
        "clerk_webhook_secret",
    )
)

# Values that must never reach a log line. Distinctive enough that a substring
# search over the whole log is meaningful.
_SECRET = "s3cret-value-that-must-not-be-logged"


def _settings(**overrides: object) -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://u:p@localhost/db",
        clerk_jwks_url="https://example.clerk.accounts.dev/.well-known/jwks.json",
        musicbrainz_user_agent="Harmoniq/0.1.0 test@example.com",
        **overrides,  # type: ignore[arg-type]
    )


def _fully_configured(**overrides: object) -> Settings:
    values: dict[str, object] = {field: _SECRET for field in _ALL_OPTIONAL}
    values.update(overrides)
    return _settings(**values)


def _log(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    settings: Settings,
) -> str:
    monkeypatch.setattr(main, "settings", settings)
    with caplog.at_level(logging.INFO, logger="app.main"):
        main._log_feature_configuration()
    return caplog.text


def test_nothing_configured_names_every_group(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    text = _log(monkeypatch, caplog, _settings())

    assert "Spotify" in text
    assert "R2" in text
    assert "Clerk management API" in text
    assert "Clerk webhooks" in text
    # The point of the line is that each one fails *silently* at request time.
    assert "silently" in text


def test_fully_configured_is_reported_too(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """ADR 0011: a state nothing ever prints is a state nobody can check."""
    text = _log(monkeypatch, caplog, _fully_configured())

    assert "all configured" in text
    assert caplog.records[0].levelno == logging.INFO


@pytest.mark.parametrize("missing", _SPOTIFY_FIELDS)
def test_any_missing_spotify_field_reports_spotify(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, missing: str
) -> None:
    """Every credential counts, the Fernet key included.

    The key is the one most easily overlooked — it is not a Spotify
    credential and lives under its own heading in `.env.example` — yet
    without it a stored refresh token cannot be decrypted and the connection
    is unusable. The parametrisation exists so a fifth field added to the
    group cannot be added to the check by accident only.
    """
    text = _log(monkeypatch, caplog, _fully_configured(**{missing: None}))

    assert "Spotify" in text
    # Only the incomplete group is named — noise trains operators to skip it.
    assert "R2" not in text


@pytest.mark.parametrize("missing", _R2_FIELDS)
def test_any_missing_r2_field_reports_r2(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, missing: str
) -> None:
    text = _log(monkeypatch, caplog, _fully_configured(**{missing: None}))

    assert "R2" in text
    assert "Spotify" not in text


def test_empty_string_counts_as_unconfigured(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A variable set to "" is the common shape of this failure.

    A platform's UI happily stores an empty value, and `is not None` would
    call that configured — which is exactly the reading that makes a broken
    deployment look healthy.
    """
    text = _log(monkeypatch, caplog, _fully_configured(spotify_client_secret=""))

    assert "Spotify" in text


def test_no_secret_value_is_ever_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Observability must not turn Deploy Logs into a place secrets live."""
    text = _log(monkeypatch, caplog, _fully_configured())

    assert _SECRET not in text


def test_partial_configuration_logs_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """INFO is filtered out of most log views; the actionable case is WARNING."""
    _log(monkeypatch, caplog, _fully_configured(spotify_client_id=None))

    assert caplog.records[0].levelno == logging.WARNING
