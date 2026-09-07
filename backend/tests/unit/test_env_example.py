"""`.env.example` must stay in step with `Settings`.

Both directions of drift have already cost real time:

* A field added to `Settings` and not to `.env.example` is invisible.
  `SEARCH_LOCAL_FIRST`, `HOME_TRENDING_COUNT` and `HOME_FRIENDS_COUNT` were
  all in this state, and `APP_ENV` — undocumented and defaulted — went
  missing from Railway with nothing to say so, serving `/docs` publicly and
  turning SQLAlchemy echo on (ADR 0011).
* A key left in `.env.example` after its field is deleted is worse than
  useless: `pydantic-settings` defaults to ``extra="forbid"``, so anyone who
  copies the file to `.env` gets a `ValidationError` at import and a server
  that will not boot. `RATE_LIMIT_DEFAULT` and `DEBUG` were both stale.

The asymmetry worth remembering, and the reason the first case is not caught
by the second: an undeclared *OS* environment variable is silently ignored,
while an undeclared key in a `.env` *file* raises. Neither one tells the
operator that a variable they set is doing nothing.
"""

import re
from pathlib import Path

import pytest

from app.config import Settings

_ENV_EXAMPLE = Path(__file__).parent.parent.parent / ".env.example"

# `KEY=` at the start of a line. Comments and blank lines are skipped, and a
# commented-out example (`# CORS_ALLOWED_ORIGINS=...`) is documentation rather
# than a declared key.
_KEY_RE = re.compile(r"^([A-Z][A-Z0-9_]*)=")


def _documented_keys() -> set[str]:
    return {
        match.group(1)
        for line in _ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
        if (match := _KEY_RE.match(line))
    }


def _settings_keys() -> set[str]:
    return {name.upper() for name in Settings.model_fields}


def test_env_example_exists() -> None:
    assert _ENV_EXAMPLE.is_file(), f"{_ENV_EXAMPLE} is the setup contract"


@pytest.mark.parametrize("field", sorted(_settings_keys()))
def test_every_setting_is_documented(field: str) -> None:
    """A field nobody knows to set is a field that goes missing unnoticed."""
    assert field in _documented_keys(), (
        f"{field} is a Settings field but is absent from .env.example. "
        "Add it, with a comment saying what breaks when it is unset — an "
        "undeclared OS environment variable is silently ignored, so nothing "
        "else will report it."
    )


@pytest.mark.parametrize("key", sorted(_documented_keys()))
def test_every_documented_key_is_a_setting(key: str) -> None:
    """A stale key stops the server booting for anyone who copies the file."""
    assert key in _settings_keys(), (
        f"{key} is in .env.example but is not a Settings field. Settings uses "
        'extra="forbid", so a .env carrying this key raises ValidationError '
        "at import and the server will not start."
    )


def test_derived_properties_are_not_documented_as_variables() -> None:
    """`debug` is derived from `app_env`; a DEBUG variable would contradict it.

    It was a real variable once, and the two could disagree — hence the
    property. Re-adding it to `.env.example` would reintroduce the ambiguity
    without reintroducing the field, so no test above would catch it.
    """
    assert "DEBUG" not in _documented_keys()
    assert "debug" not in Settings.model_fields
