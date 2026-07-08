"""
Shared visibility decision logic.

Two rules, used by the user, rating, follow, home, and spotify services so
the consent semantics live in exactly one place (ENGINEERING_BIBLE §8.1):

- effective_scope: a profile-level setting acts as a master switch over any
  per-item scope — the stricter of the two wins (ratings spec amendment A1,
  2026-07-04).
- scope_allows: whether a resolved scope admits a given viewer.
"""

from app.core.enums import VisibilityScope

_STRICTNESS: dict[VisibilityScope, int] = {
    VisibilityScope.PRIVATE: 0,
    VisibilityScope.FRIENDS: 1,
    VisibilityScope.PUBLIC: 2,
}


def effective_scope(
    profile_scope: str | VisibilityScope,
    item_scope: str | VisibilityScope,
) -> VisibilityScope:
    """Return the stricter of a profile-level scope and a per-item scope."""
    profile = VisibilityScope(profile_scope)
    item = VisibilityScope(item_scope)
    return profile if _STRICTNESS[profile] <= _STRICTNESS[item] else item


def scope_allows(
    scope: str | VisibilityScope,
    is_owner: bool,
    is_friend: bool,
) -> bool:
    """Return True if the given scope admits this viewer. Owner always may."""
    if is_owner:
        return True
    resolved = VisibilityScope(scope)
    if resolved == VisibilityScope.PUBLIC:
        return True
    return resolved == VisibilityScope.FRIENDS and is_friend
