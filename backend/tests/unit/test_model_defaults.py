"""Column defaults that HARMONIQ.md governs, pinned so drift is deliberate.

HARMONIQ.md §6, Consent Before Visibility: visibility "should be explicit,
specific, and revocable", defaulting to the most private option
(ENGINEERING_BIBLE §8.1). Two columns already depart from that, each a
Founder-ratified constitutional exception recorded in a spec.

The exceptions are the reason this test exists. They are legitimate and they
are also a precedent — the next `visibility_*` column is one copy-paste away
from `PUBLIC.value`, and nothing about that diff looks wrong in review. Here
it fails until someone adds the column to the table below, which is a place
that asks for the ratifying document by name.

A default that is merely *wrong* is a quiet bug: `visibility_activity`
defaulting to private is correct and still cost a session, because a profile
that looked empty read as "listening isn't persisting" rather than as
"nobody is allowed to see it".
"""

import pytest
from sqlalchemy import inspect

from app.core.enums import MelodyAcceptScope, VisibilityScope
from app.models.user import User

# Every visibility column whose default is *not* the most private option, with
# where the exception is ratified. Adding a row here is the deliberate act.
_RATIFIED_PUBLIC_DEFAULTS = {
    "visibility_ratings": "specs/phase-1-ratings-reviews.md, Amendments 2026-07-04",
    "visibility_follows": (
        "specs/phase-1-user-accounts-profiles.md, Amendments 2026-07-04"
    ),
}


def _default_of(column_name: str) -> object:
    column = inspect(User).columns[column_name]
    assert column.default is not None, f"{column_name} has no Python-side default"
    return column.default.arg


def _visibility_columns() -> list[str]:
    return [c.name for c in inspect(User).columns if c.name.startswith("visibility_")]


def test_there_are_visibility_columns_to_check() -> None:
    """Guards the sweep below against silently checking nothing."""
    assert _visibility_columns()


@pytest.mark.parametrize("column", _visibility_columns())
def test_visibility_defaults_are_private_unless_ratified(column: str) -> None:
    default = _default_of(column)

    if column in _RATIFIED_PUBLIC_DEFAULTS:
        assert default == VisibilityScope.PUBLIC.value, (
            f"{column} is recorded as a public-default exception "
            f"({_RATIFIED_PUBLIC_DEFAULTS[column]}) but no longer defaults to "
            "public. If the exception was withdrawn, remove the row."
        )
        return

    assert default == VisibilityScope.PRIVATE.value, (
        f"{column} defaults to {default!r}. HARMONIQ.md §6 requires the most "
        "private default. A public default is a constitutional exception "
        "requiring Founder ratification, documented reasoning and a condition "
        "for reevaluation — record it in a spec and add it to "
        "_RATIFIED_PUBLIC_DEFAULTS with that reference."
    )


@pytest.mark.parametrize("column", _visibility_columns())
def test_visibility_defaults_are_valid_scopes(column: str) -> None:
    """A typo'd default is accepted by the String column and fails later."""
    VisibilityScope(_default_of(column))


def test_melody_accept_scope_is_not_a_visibility_scope() -> None:
    """It gates an inbound gesture, not visibility of owned data.

    Typed separately on purpose (`models/user.py`), so the §6 private-default
    rule above does not apply to it and it is not swept in by the name
    prefix. Asserted rather than assumed, because renaming it into the
    `visibility_` namespace would silently change which rule governs it.
    """
    assert "melody_accept_scope" not in _visibility_columns()
    assert _default_of("melody_accept_scope") == MelodyAcceptScope.EVERYONE.value


def test_moderator_is_not_granted_by_default() -> None:
    """No API path writes is_moderator; it is granted by manual SQL only."""
    assert _default_of("is_moderator") is False
