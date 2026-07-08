# SPEC — Phase 1: Moderation (Review & Action)

> Retroactive spec, written during the 2026-07-07 docs pass. Moderation
> was implemented and tested before this document existed; this spec
> records what was actually built.

---

# Title

Moderation — report review and action.

---

# Purpose

Report _intake_ (`POST /ratings/{id}/report`) shipped earlier, but a report
with nowhere to go isn't a safety mechanism — it's a formality. Moderation
closes the loop: a way for a designated moderator to review open reports
and act (hide content, suspend a user). This is a direct requirement of
HARMONIQ.md §5 (Security Is Foundational) — no outside tester should be
able to post user-generated content that no one can ever act on.

---

# Scope

### In Scope

- A moderator role (`users.is_moderator`), granted only via manual SQL.
- Report queue: list open/dismissed/actioned reports with full rating
  context.
- Three actions: dismiss a report, hide a rating (soft), suspend a user.
- Suspension enforcement: every write endpoint in the app blocked for a
  suspended user; reads remain available.
- Hidden-rating exclusion from every public surface, while remaining
  visible-with-notice to the rating's own author.

### Out of Scope

- An in-app moderator-grant flow (API-driven role assignment) — manual SQL
  only, permanently, per Founder decision.
- Unsuspend / appeal flow — manual SQL only; no in-app path.
- Warnings short of suspension (e.g. a formal strike system).
- Moderating anything other than ratings/reviews (no other UGC surface
  exists to moderate — Melody has no free text, see
  `specs/phase-1-melody.md` Known Limitations).
- Moderator-visible audit log UI (mutations are logged per
  ENGINEERING_BIBLE §8, but there is no dedicated log-viewing surface).

---

# User Experience

- **Entry point** — `/moderation`, a server component that checks
  `/users/me` and calls Next's `notFound()` for non-moderators. Not linked
  from `AppShell` navigation — deliberate existence-hiding parity with the
  backend's 404-not-403 pattern (a moderator navigates there directly).
- **Core flow** — moderator sees a queue of reports with full rating
  context (reporter, rating text, entity), and takes one of three actions
  per report/rating.
- **Empty state** — "No open reports" once the queue clears.
- **Loading state** — standard inline loading.
- **Error state** — inline error copy on action failure; a report already
  resolved by another moderator surfaces a 409.
- **Success state** — row updates/disappears from the open queue
  immediately on action.
- **Edge cases** — hiding a rating auto-resolves (marks `actioned`) every
  other open report against that same rating, not just the one being
  viewed; a moderator cannot suspend another moderator.

---

# Functional Requirements

- `CurrentModerator` returns **404**, not 403, for non-moderators and for
  suspended moderators — the existence of the moderation surface itself is
  hidden from anyone who shouldn't know it's there.
- `is_moderator` is never writable through any API — grantable only via a
  direct database `UPDATE`, documented in `docs/setup.md`.
- Suspension (`suspended_at` set) blocks all writes app-wide via a single
  shared `CurrentActiveUser` dependency (ratings, follows, profile
  updates, avatar upload, Melody send/respond) — reads remain unaffected.
- Hiding a rating (`hidden_at`/`hidden_by` set) must exclude it from every
  public read surface: entity aggregate, entity rating list, profile
  rating list/count, Home trending, Home friends' top songs — while the
  rating's own author still sees it, flagged.
- Dismissing a report moves it `open` → `dismissed`.
- Hiding a rating moves _all_ of that rating's open reports to `actioned`
  in the same action, not just the one report being viewed.
- Suspending a user refuses (409) if the target is already suspended, and
  refuses (403) if the target is a moderator.

---

# Acceptance Criteria

- [x] Every moderation endpoint returns 404 for a non-moderator.
- [x] A hidden rating is absent from: entity list, profile list, aggregate
      score, Home trending, Home friends' feed — for every user except the
      rating's own author, who sees it with a "hidden by moderation" notice.
- [x] Hiding a rating marks all of its open reports `actioned`.
- [x] Dismissing a report works and is idempotent-safe (already-resolved
      report returns 409, not a silent no-op).
- [x] Suspension matrix: every write endpoint returns 403 for a suspended
      user; every read endpoint returns 200; a suspended moderator gets 404 on
      moderation endpoints (suspension outranks moderator status).
- [x] A moderator cannot suspend another moderator.
- [x] Full test coverage in `backend/tests/integration/test_moderation.py`.

---

# Design Requirements

- Actions use an inline two-step confirm (not a modal), consistent with
  Harmoniq's no-modals idiom.
- Hidden-rating notice to the author: "Hidden by moderation — only you can
  see this." — calm, factual, no shame-language (BRAND_BIBLE tone).
- Moderation is not discoverable via navigation UI at all — a deliberate
  discoverability cost accepted in exchange for existence-hiding.

---

# Technical Notes

- Model changes: `users.is_moderator`/`suspended_at`,
  `ratings.hidden_at`/`hidden_by`, `reports.status`/`resolved_at`/
  `resolved_by` — see `backend/app/models/user.py`,
  `backend/app/models/rating.py`.
- Auth: `CurrentActiveUser` and `CurrentModerator` in
  `backend/app/api/v1/deps.py` are the two enforcement points — every
  write endpoint in the app was swept to depend on `CurrentActiveUser`
  instead of plain `CurrentUser`.
- Service: `backend/app/services/moderation.py`. Router:
  `backend/app/api/v1/moderation.py`. Hidden-rating filtering is applied
  directly in `backend/app/services/rating.py` (`get_aggregate`,
  `_can_view`, `list_for_entity`, `list_for_user`, `count_for_user`) and
  `backend/app/services/home.py` (trending + friends SQL).
- Migration: `add_moderation` (see `backend/alembic/versions/`).

---

# Rollback Plan

All new columns are additive and nullable/defaulted; reversible via
`alembic downgrade`. Reverting requires: removing the `moderation` router,
reverting the hidden-rating filters in `rating.py`/`home.py` back to their
pre-moderation queries, and swapping write endpoints from
`CurrentActiveUser` back to `CurrentUser` (or leaving `CurrentActiveUser`
in place — it degrades gracefully to "no one is ever suspended" once
`suspended_at` stops being settable, so a partial rollback is safe).

---

# Open Questions

None outstanding for what's shipped. Deferred to a future spec if ever
prioritized: a formal warning/strike system short of suspension, and a
self-service unsuspend/appeal flow.

---

# Known Limitations

**No unsuspend endpoint.** Manual SQL only, permanently, per Founder
decision — not a gap to close, a deliberate scope boundary for Phase 1.

**No appeal flow.** A suspended user has no in-app way to contest or ask
about their suspension; this must go through the Founder directly at
current scale.

**Moderator grant is entirely manual and undocumented in any in-app UI.**
Documented in `docs/setup.md` (added in this docs pass) as a raw SQL
statement — acceptable for a single Founder-moderator at friend-test scale,
would need a real admin surface before any larger cohort.
