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


class FriendRequestScope(StrEnum):
    """Who may send this user a friend request. Same shape as MelodyAcceptScope:
    an inbound gesture, not visibility of owned data. 'follows' = people this
    user follows."""

    EVERYONE = "everyone"
    FOLLOWS = "follows"
    MUTUALS = "mutuals"


class FriendshipStatus(StrEnum):
    """pending → accepted | declined. A decline is silent and recoverable."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class FriendshipState(StrEnum):
    """The relationship as one viewer sees it. A sender never sees their own
    outstanding request (Founder decision 2026-09-27), so pending and declined
    are indistinguishable to them: both read as none. request_sent is only the
    acknowledgement returned by the send itself."""

    NONE = "none"
    FRIENDS = "friends"
    REQUEST_SENT = "request_sent"
    REQUEST_RECEIVED = "request_received"


class NotificationType(StrEnum):
    """
    In-app notification events. Deliberately narrow: never any event for a
    rejected Melody (ENGINEERING_BIBLE §3), and a notification must never
    reference activity its recipient couldn't otherwise see.
    """

    MELODY_RECEIVED = "melody_received"
    NEW_FOLLOWER = "new_follower"
    # Deliberately no friend_request_declined: a decline notifies no one.
    FRIEND_REQUEST_RECEIVED = "friend_request_received"
    FRIEND_REQUEST_ACCEPTED = "friend_request_accepted"


class ReportStatus(StrEnum):
    OPEN = "open"
    DISMISSED = "dismissed"
    ACTIONED = "actioned"
