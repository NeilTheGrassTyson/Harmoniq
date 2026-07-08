# SPEC — Phase 1: Melody

> Retroactive spec, written during the 2026-07-07 docs pass. Melody was
> implemented and tested before this document existed; this spec records
> what was actually built (source of truth: the implementation), not the
> original design draft. Where the shipped behavior differs from the
> initial plan, the difference is called out explicitly.

---

# Title

Melody — the atomic social recommendation object.

---

# Purpose

Melody is Harmoniq's core social mechanic: a directed recommendation of a
single track from one person to another. It solves the "how does discovery
actually happen through people" problem that HARMONIQ.md's Humans Before
Algorithms principle requires — without Melody, "discovery through trusted
people" is just a slogan with no concrete mechanism.

Melody strengthens **Trust Between Users** and **Discovery Through People**
directly (BRAND_BIBLE §3): every Melody is a specific human act, traceable
to a specific sender, and the system is architecturally forbidden from ever
generating one on a user's behalf (ENGINEERING_BIBLE §6).

---

# Scope

### In Scope

- Sending a Melody: one track, one sender, one recipient.
- Recipient responses: Accept, Open, Reject.
- A per-user consent setting (`melody_accept_scope`) gating who may send a
  user a Melody: everyone / follows / mutuals.
- A Melody inbox (received) and sent list, both cursor-paginated.
- Rate limiting and a duplicate-pending send guard.

### Out of Scope

- Any message/text field on a Melody (see Founder decision below).
- Sending an album or artist as a Melody — track only.
- System- or algorithm-generated Melodies (permanently out of scope per
  ENGINEERING_BIBLE §6, not just deferred).
- An "unsend" action.
- Melody reporting — see Known Limitations.

---

# User Experience

- **Entry point** — a "Send a Melody" control on a track page
  (`app/track/[mbid]/page.tsx`), sibling to the rating composer.
- **Core flow** — sender enters a recipient username, sees a live preview
  of the embed card that will be sent, and submits. Recipient sees it in
  their inbox (`/melodies`) and responds with Accept, Open, or Reject.
- **Empty state** — inbox and sent list each show a calm empty state for a
  brand-new account.
- **Loading state** — standard inline loading, no skeleton complexity.
- **Error state** — backend error copy is shown verbatim inline; the scope
  rejection is deliberately neutral ("This member isn't receiving Melodies
  right now.") regardless of which scope failed, so a sender can never
  infer the recipient's specific setting.
- **Success state** — "Melody sent to @name."
- **Edge cases** — self-send blocked (400); duplicate pending send blocked
  (409, "You've already sent this track to them."); re-send allowed once
  the prior Melody has been responded to; Reject is recoverable (a
  recipient can still Accept or Open a previously rejected Melody).

---

# Functional Requirements

- A Melody carries a sender, a recipient, a track, and a timestamp — no
  message field (Founder decision, see below).
- System must never create a Melody except as a direct result of a
  recipient-targeted send action taken by the sending user.
- Lifecycle is `sent` → `received` (automatic, on inbox fetch) → exactly
  one of `accepted` / `opened` / `rejected`. From `rejected`, a recipient
  can still move to `accepted` or `opened` (rejection is recoverable).
  `accepted` and `opened` are terminal.
- The sender's own view of a Melody they sent never shows `received` as a
  distinct state — it collapses to `sent` (no read receipts).
- Reject must be visible only to the sender; it must never notify anyone
  or appear on any surface the recipient or a third party can see it
  changed.
- `melody_accept_scope` (everyone / follows / mutuals, default everyone)
  is checked before allowing a send; scope-failure and self-send messaging
  must not reveal which specific rule was violated.
- Send is rate-limited (`10/minute;60/day`); respond is rate-limited
  (`30/minute`).
- Suspended users (`CurrentActiveUser`) cannot send or respond, but a
  suspended user's existing Melodies remain visible to others as normal.

---

# Acceptance Criteria

- [x] Sending a track to a valid, scope-permitting recipient returns 201
      and the item appears in the recipient's inbox.
- [x] Self-send returns 400.
- [x] Scope violation returns 403 with neutral copy, identical wording
      regardless of which scope (`follows`/`mutuals`) blocked it.
- [x] Duplicate pending send returns 409; re-send after a response
      succeeds.
- [x] Inbox fetch auto-transitions `sent` → `received` in the same
      transaction.
- [x] `respond` supports accept/open/reject; illegal transitions return
      409; responding as a non-recipient (or to a nonexistent id) returns 404.
- [x] `rejected` → `accepted`/`opened` succeeds (recoverable); `accepted`
      → `rejected` fails (409).
- [x] Sender's sent-list view never displays `received` as distinct from
      `sent`.
- [x] Full test coverage in `backend/tests/integration/test_melodies.py`
      and `backend/tests/unit/test_melody_transitions.py` /
      `test_melody_scope.py`.

---

# Design Requirements

- Melody renders as an interactive **embed card** (`MelodyCard.tsx`):
  cover art, track title, artist, "From \<sender\>" — no text composer
  anywhere in the send flow. This is BRAND_BIBLE §5's "social gesture
  encoded as music" made literal.
- Copy stays calm and socially neutral throughout — rejection language
  ("Not for me") never implies penalty or failure (BRAND_BIBLE §5.2).
- No numeric badges anywhere in the Melody flow (consistent with the
  Notifications design requirement below).

---

# Technical Notes

- Model: `backend/app/models/melody.py`. Service:
  `backend/app/services/melody.py`. Schemas: `backend/app/schemas/melody.py`.
  Router: `backend/app/api/v1/melodies.py`.
- `track_id` is a real FK to `tracks.id` — a deliberate deviation from
  `Rating`'s polymorphic `(entity_type, entity_id)` pair, since Melody is
  track-only and needs no polymorphism.
- Duplicate-pending guard: partial unique index
  `uq_melodies_pending_dedup` on `(sender_id, recipient_id, track_id)`
  WHERE `status IN ('sent','received')` — the service pre-checks for a
  friendly 409, the index is the race-proof backstop.
- Migration: `add_melodies` (see `backend/alembic/versions/`).

---

# Rollback Plan

The `melodies` table and `users.melody_accept_scope` column are additive.
Reversible via `alembic downgrade`; removing the `melodies` router from
`app/api/v1/router.py` and reverting the migration restores the pre-Melody
state without affecting any other feature (Notifications' `melody_id` FK
would need to be dropped first — see `specs/phase-1-notifications.md`
Rollback Plan for the coupled order).

---

# Open Questions

None outstanding — all Founder decisions for this feature were made and
recorded during implementation (see `docs/adr/0009-melody-no-message-embed-card.md`
and the ENGINEERING_BIBLE/BRAND_BIBLE amendment in
`docs/reviews/engineering-bible-4be872d-to-docs-pass.md`).

---

# Known Limitations

**No message field, by design.** Founder decision, 2026-07-07 (see ADR 0009) — not a limitation to be resolved, a permanent scope boundary. Noted
here because it's the single most consequential change from the original
design draft.

**No unsend.** A sent Melody cannot be recalled. Acceptable at this scale;
revisit only if abuse patterns emerge.

**No melody-report path.** Because Melody carries no free text, there is
nothing on a Melody itself to report beyond the track metadata (already
reportable through the existing catalog-data-issue path, not a Melody
concern). If a future feature reintroduces any free text on Melody, a
report path must be designed alongside it — do not ship free text without
one.

**Sender sees `accepted` vs `opened` as distinct outcomes.** Kept granular
deliberately as a Harmony-scoring seam (ENGINEERING_BIBLE §3) — collapsing
them into one "positive" outcome later is a one-line change if ever
desired; the reverse (recovering the distinction after collapsing) is not
possible without a data gap.
