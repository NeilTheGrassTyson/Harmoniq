# SPEC — Phase 1: Notifications

> Retroactive spec, written during the 2026-07-07 docs pass. Notifications
> was implemented and tested before this document existed; this spec
> records what was actually built.

---

# Title

Notifications — minimal in-app notification center.

---

# Purpose

Without a way to surface a Melody or a new follower, Melody has no way of
actually reaching anyone — the mechanic exists but no one finds out about
it. Notifications closes that gap with the smallest possible surface: two
event types, no feed, no real-time push. This strengthens **Trust Between
Users** by making a human-originated action (a Melody, a follow) visible to
its recipient without turning into an engagement loop — HARMONIQ.md's
Non-Goals explicitly rule out virality/engagement optimization, so this
spec is deliberately minimal by constitutional constraint, not oversight.

---

# Scope

### In Scope

- Two notification types: `melody_received`, `new_follower`.
- Unread count, mark-one-read, mark-all-read.
- A bell icon + dropdown panel in `AppShell`, polled (not real-time).

### Out of Scope

- Any notification type beyond the two above (e.g. rating likes/comments —
  don't exist as features yet).
- Push notifications (browser or mobile).
- Real-time delivery (WebSocket/SSE) — explicitly non-goal per
  ENGINEERING_BIBLE §9 ("Feed updates and ranking changes are explicitly
  non-real-time, by design, to preserve calm system behavior").
- Notification preferences/settings (e.g. muting a type) — everything is
  always on for the two shipped types.
- A rejected-Melody notification — permanently out of scope, not deferred
  (ENGINEERING_BIBLE §3: rejection "must never produce a notification or
  penalty visible to anyone else").

---

# User Experience

- **Entry point** — bell icon in the `AppShell` header, next to `NavAuth`.
- **Core flow** — unread count polled on mount + every 60s; a quiet 2px
  accent dot appears if `count > 0` (never a number). Clicking the bell
  opens a popover with recent notifications; clicking a row marks it read
  and navigates (Melody rows → `/melodies`, follow rows → the follower's
  profile).
- **Empty state** — calm "No notifications yet" copy.
- **Loading state** — standard inline loading in the popover.
- **Error state** — silent retry on next poll interval; no error toast (a
  failed poll is not urgent enough to interrupt the user).
- **Success state** — dot disappears once everything is read; "Mark all
  read" footer link available.
- **Edge cases** — a re-follow (unfollow then follow again) does not
  re-notify (idempotency guard); a Melody notifies exactly once regardless
  of retries.

---

# Functional Requirements

- A notification is created synchronously, in the same transaction as its
  trigger (Melody send; follow insert) — never as a background job.
- A notification must never reveal activity the recipient wouldn't
  otherwise have permission to see — the payload embeds only actor summary
  and (for Melody) track summary, never rating/activity content.
- Idempotency is enforced at the database level via partial unique indexes
  - `ON CONFLICT DO NOTHING`, not application-level checks: a re-follow
    never re-notifies; a given Melody notifies at most once.
- All four endpoints are usable while the calling user is suspended
  (`CurrentUser`, not `CurrentActiveUser`) — a suspended user can still see
  and clear their notifications, just not act on them elsewhere.
- No numeric badge anywhere — dot only.

---

# Acceptance Criteria

- [x] Sending a Melody creates exactly one notification for the recipient.
- [x] Rejecting a Melody creates zero notifications.
- [x] Following, then unfollowing, then following again creates exactly
      one `new_follower` notification total.
- [x] Unread count reflects only unread rows; mark-one-read and
      mark-all-read both work and are idempotent.
- [x] A user can never mark another user's notification as read (404 on
      cross-user attempt).
- [x] Full test coverage in `backend/tests/integration/test_notifications.py`.

---

# Design Requirements

- Dot indicator only, never a numeric badge — consistent with
  HARMONIQ.md's Non-Goals (no engagement-loop optimization) and Melody's
  own no-badge-anxiety requirement.
- The dropdown popover is a **documented deviation** from Harmoniq's
  general no-modals idiom: BRAND_BIBLE explicitly wants a
  notification-style pop-up here. It is non-blocking and anchored, not a
  modal overlay. If this pattern is ever rejected on review, the fallback
  is a dedicated `/notifications` page instead of a popover.
- No quick actions inside the panel — the Melody inbox (`/melodies`) is
  the single action surface; the panel only links out to it.

---

# Technical Notes

- Model: `backend/app/models/notification.py`. Service:
  `backend/app/services/notification.py`. Schemas:
  `backend/app/schemas/notification.py`. Router:
  `backend/app/api/v1/notifications.py`.
- Coupling note: notification creation is inline in the melody-send and
  follow services, not an event bus. This is a deliberate simplicity
  tradeoff (HARMONIQ.md §4) for two event types; if a third event type is
  added, revisit whether an outbox table is warranted before adding a
  third inline call site.
- Migration: `add_notifications` (see `backend/alembic/versions/`);
  depends on `melodies` existing first (FK on `melody_id`).

---

# Rollback Plan

Additive table, reversible via `alembic downgrade`. Must be downgraded
_before_ the `melodies` migration if both are being rolled back together
(FK dependency: `notifications.melody_id` → `melodies.id`). Removing the
`notifications` router and the two inline creation call sites in
`melody_svc.send_melody` and `follow_svc.follow` fully disables the
feature without affecting Melody or Follow's core behavior.

---

# Open Questions

None outstanding.

---

# Known Limitations

**Unbounded retention.** Notifications are never pruned or archived. Fine
at alpha/friend-test scale; revisit with a retention policy (e.g. auto-clear
after 90 days) before any larger rollout — flagged as an ops note, not a
blocker.

**Polling, not push.** 60-second poll interval means a notification can be
up to a minute stale. This is intentional (ENGINEERING_BIBLE §9), not a
bug — do not "fix" this with WebSockets without a Founder-approved
architectural change.
