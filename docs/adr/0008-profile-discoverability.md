# ADR 0008 — Profile Discoverability: Every Profile Findable, Content Private

**Date:** 2026-07-04
**Status:** Accepted
**Deciders:** Founder

---

## Context

User search (`GET /api/v1/users/search`) currently returns any account
matching the query. `app/services/user.py::filter_discoverable_users` is a
documented pass-through — scaffolding for a future WHERE clause — meaning
there is no way to be excluded from search results. Meanwhile ROADMAP.md's
Search (minimal) entry promised "private profiles stay undiscoverable even
by exact-name search."

The 2026-07-02 repo audit flagged this as a stance that existed only in a
code comment. A decision was required: is universal discoverability the
product's intent, or an interim gap?

## Decision

**Every profile is discoverable.** Search may return any account's
username, display name, and avatar. Privacy applies to the *content* of a
profile page — follow lists, reviews, ratings counts, listening activity —
each governed by its own owner-set visibility scope, not to the profile's
existence.

This is the Instagram model: an account can always be found; what a visitor
sees once they arrive is what the owner chose to share.

`filter_discoverable_users` remains in place as the single enforcement
point should this decision ever be reversed.

## Rationale

- Harmoniq's mission is discovery through people (HARMONIQ.md §Mission);
  a person who cannot be found cannot be followed or trusted.
- Search exposes only identity-card fields (username, display name,
  avatar) that are already visible on every profile page unconditionally.
  No visibility-scoped data leaks through search.
- Consent (HARMONIQ.md §6) is preserved where it matters: every piece of
  profile *content* carries an owner-controlled scope, enforced at the
  data-access layer per ENGINEERING_BIBLE.md §8.1.

## Consequences

- ROADMAP.md's Search (minimal) security note is superseded by this ADR:
  the guarantee is "search never returns content the viewer isn't permitted
  to see," not "profiles can be undiscoverable."
- A future full-privacy account mode (undiscoverable profiles) would be a
  Tier 1 feature with its own spec and would implement its WHERE clause in
  `filter_discoverable_users`.

## Reevaluation condition

Revisit if abuse patterns emerge where discoverability itself becomes a
harassment vector (e.g. block/mute tooling proves insufficient), or if a
regulatory requirement demands an undiscoverable-account option.
