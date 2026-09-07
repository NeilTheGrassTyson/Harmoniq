"""Notifications are a closed set, and one omission from it is constitutional.

ENGINEERING_BIBLE §3, on the Melody lifecycle:

    `rejected` is recoverable and visible only to the sender — it must never
    produce a notification or penalty visible to anyone else.

`specs/phase-2-friend-requests.md` carries the same rule forward: a declined
friend request notifies no one, "the single most important behavioural rule
in this spec".

Both rules are enforced today by an absence — no rejection event exists in
`NotificationType`, so none can be created. An absence is the one kind of
invariant that nothing fails to uphold and nothing reports: adding
`MELODY_REJECTED` alongside the others is a one-line diff that reads as
completing an enum, passes every existing test, and quietly makes declining
someone visible to them.

So the enum is pinned. A new member fails here, which is a place that states
what the rule is and which document it comes from — the check is on the
addition being deliberate, not on it being forbidden.
"""

import pytest

from app.core.enums import NotificationType

# The complete set, as ratified. Adding to this is the deliberate act.
_RATIFIED_TYPES = {
    "melody_received": "ENGINEERING_BIBLE §3 — the Melody arrives for its recipient",
    "new_follower": "phase-1 follows — someone followed you",
}

# Substrings describing an outcome its subject is not entitled to learn about.
# Not exhaustive, and not meant to be: it catches the obvious spelling of a
# mistake whose careful spelling is caught by the exact-set check above.
_FORBIDDEN_SUBSTRINGS = (
    "reject",
    "decline",
    "refus",
    "deni",
    "denied",
    "ignore",
    "block",
)


def test_notification_types_are_exactly_the_ratified_set() -> None:
    assert {t.value for t in NotificationType} == set(_RATIFIED_TYPES), (
        "NotificationType changed. Every member must be an event its recipient "
        "is entitled to see (ENGINEERING_BIBLE §3, HARMONIQ.md §6). Add it to "
        "_RATIFIED_TYPES with the document that ratifies it, or remove it."
    )


@pytest.mark.parametrize("forbidden", _FORBIDDEN_SUBSTRINGS)
def test_no_notification_reports_a_refusal(forbidden: str) -> None:
    """A refusal must never reach the person refused.

    §3 makes a decline recoverable precisely because it is invisible: nobody
    is put in the position of having visibly refused someone, and nobody
    learns they were refused. A notification is the most direct way to break
    that, and it would look like a feature.
    """
    offenders = [t.value for t in NotificationType if forbidden in t.value.lower()]

    assert offenders == [], (
        f"{offenders} name a refusal. ENGINEERING_BIBLE §3 forbids a rejected "
        "Melody producing any notification, and the friend-requests spec "
        "extends that to a declined request. If an exception is genuinely "
        "intended it needs Founder ratification, not a new enum member."
    )


def test_notification_types_are_lowercase_snake_case() -> None:
    """They are persisted as strings; a rename is a data migration."""
    for notification_type in NotificationType:
        assert notification_type.value == notification_type.value.lower()
        assert " " not in notification_type.value
