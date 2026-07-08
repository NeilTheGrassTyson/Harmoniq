from enum import StrEnum


class VisibilityScope(StrEnum):
    PRIVATE = "private"
    FRIENDS = "friends"
    PUBLIC = "public"


class MelodyStatus(StrEnum):
    """
    Melody lifecycle per ENGINEERING_BIBLE §3: sent → received, then exactly
    one of accepted / opened / rejected. Rejected is recoverable (the
    recipient may still accept or open later); opened is terminal.
    """

    SENT = "sent"
    RECEIVED = "received"
    ACCEPTED = "accepted"
    OPENED = "opened"
    REJECTED = "rejected"


class MelodyAcceptScope(StrEnum):
    """Who may send this user a Melody. 'follows' = people this user follows."""

    EVERYONE = "everyone"
    FOLLOWS = "follows"
    MUTUALS = "mutuals"


class NotificationType(StrEnum):
    """
    In-app notification events. Deliberately narrow: never any event for a
    rejected Melody (ENGINEERING_BIBLE §3), and a notification must never
    reference activity its recipient couldn't otherwise see.
    """

    MELODY_RECEIVED = "melody_received"
    NEW_FOLLOWER = "new_follower"


class ReportStatus(StrEnum):
    OPEN = "open"
    DISMISSED = "dismissed"
    ACTIONED = "actioned"
