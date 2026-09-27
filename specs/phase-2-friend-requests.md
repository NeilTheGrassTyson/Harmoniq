# Friend Requests — Making Friendship Explicit

> **Status: APPROVED — Founder, 2026-09-19; open questions resolved
> 2026-09-27.** Tier 1 per WORKFLOW.md §1 (net-new, user-facing feature;
> changes how user data is shared). Implemented on
> `claude/astra-harmoniq-v1-eval-6hkz4x`, awaiting Founder review.
>
> Prerequisite for `specs/phase-2-rating-visibility-split.md`, whose
> friends-only commentary is only meaningful if a viewer can actually become a
> friend. Founder decision, 2026-09-06: model it on Steam.

---

# This implements the Bible; it does not amend it

Worth stating up front, because it was initially mischaracterised in
discussion.

**ENGINEERING_BIBLE §3 already names explicit friendship as its own
relationship type:**

> The social graph is not binary. Relationships exist as **explicit
> friendships, one-directional follows**, and trust relationships representing
> perceived taste alignment... These are first-class data, not incidental
> metadata.

The current implementation has only one of those three. It has one-directional
follows, and derives "friend" from mutuality (`follow_svc.is_mutual_follow`).
That was a reasonable Phase 1 shortcut, but it is not what §3 describes, and it
is why friendship is currently something that *happens to you* rather than
something anyone can ask for.

So no amendment is needed. This closes a gap between the Bible and the code.

---

# Purpose

A stranger who wants to read someone's friends-only content today has no move
available. They can follow, but "friend" means *mutual* follow, and only the
profile owner can complete that — the viewer cannot ask, and the owner is never
told anyone wants in.

Friend requests make the relationship explicit and symmetric: a request is
sent, and accepted or declined. This is what makes every friends-only scope in
the product — listening activity, review commentary, bio, follow lists — into a
door rather than a wall.

**Principle strengthened: Trust Between People.** A mutual, opt-in relationship
is the unit Harmoniq's visibility model already assumes; this gives users a way
to actually form one.

---

# Scope

### In Scope

- A `friendships` table with an explicit request lifecycle.
- Send, accept, decline, and remove.
- Re-pointing every friends-scoped check from mutual-follow to friendship.
- Migrating existing mutual follows.
- Notifications for received and accepted requests.

### Out of Scope

- Follows. They remain, unchanged and one-directional — "I want to see your
  taste" is a different statement from "we trust each other," and §3 wants
  both.
- Blocking. Steam has it; Harmoniq does not, and it is its own feature with its
  own moderation implications.
- Trust scores (§4). Still deferred, still unformulated.
- The rating visibility split itself.

---

# Model

Friendship is symmetric and stored once per pair, not twice.

**Lifecycle:** `pending` → `accepted`, or `pending` → `declined`.

Following the Melody precedent (ENGINEERING_BIBLE §3), which is the closest
existing analogue of an inbound gesture with an accept/reject outcome:

- **A decline is silent.** §3 requires that a rejected Melody "must never
  produce a notification or penalty visible to anyone else," and is visible
  only to its sender. A declined friend request follows the same rule: the
  sender is not notified, nothing is surfaced to anyone, and the recipient is
  not put in the position of having visibly refused someone. This is the single
  most important behavioural rule in this spec.
- **A decline is recoverable.** As with Melody, declining does not permanently
  bar a future request. Rate limiting, not permanence, prevents harassment.

**Follows and friendship are independent.** You may follow without being
friends, be friends without following, or both. Nothing about accepting a
friend request creates a follow, and unfollowing does not end a friendship.

---

# Consent: who may send a request

An inbound gesture needs a consent gate. The codebase already has the pattern:
`MelodyAcceptScope` (`everyone` | `follows` | `mutuals`) governs who may send a
Melody, deliberately typed as its own enum because "it gates an inbound
gesture, not visibility of owned data" (`models/user.py`).

Friend requests need the equivalent — `FriendRequestScope` — with the same
reasoning and the same shape. Default is an open question below.

Rate limiting is required, not optional: unbounded requests are a harassment
vector, and a silent decline means the recipient has no other lever.

---

# Migration: existing mutual follows

**Every existing mutual-follow pair converts to an accepted friendship.**

This is safe and is the recommended approach: both parties have already taken
an affirmative action toward each other, and both already have friends-scoped
access to the other's content today. Converting grants nothing new and removes
nothing — it re-labels a relationship both people already chose.

The alternative — requiring everyone to re-request — would silently revoke
access that currently works, which is a worse outcome than the disclosure risk
it avoids (there is none).

**Seven call sites** currently derive friendship from mutual follow and must be
re-pointed, all of them visibility-critical:

| File | Use |
| --- | --- |
| `services/user.py:39` | profile field visibility |
| `services/rating.py:70`, `:161` | review visibility, friends' reviews |
| `services/spotify.py:414` | listening activity visibility |
| `services/home.py:278`, `api/v1/home.py:33` | friends' top tracks |
| `services/follow.py:96` | follow-list visibility |

Each is a place where getting it wrong means showing private content to the
wrong person. They should move together, in one change, with the existing
visibility integration tests re-run against the new definition — not
opportunistically as each is touched.

---

# Functional Requirements

1. A `friendships` table: the two user ids stored in a canonical order so a
   pair cannot be duplicated, `status`, `requested_by`, `created_at`,
   `responded_at`.
2. A user cannot friend themselves; a pair cannot have two concurrent pending
   requests in opposite directions — the second should accept the first.
3. Declining notifies no one and surfaces nowhere.
4. Accepting notifies the requester.
5. Receiving a request notifies the recipient, subject to their
   `FriendRequestScope`.
6. Removing a friendship is unilateral, immediate, and silent.
7. Removal revokes friends-scoped access immediately, including from any cache
   (ENGINEERING_BIBLE §8.1 — no serving past a revoked grant).
8. All friends-scoped visibility checks read friendship, never mutual follow.
9. Existing mutual follows are migrated to accepted friendships.
10. Request sending is rate-limited per sender.

---

# Acceptance Criteria

- A stranger on a profile can send a request; the owner is notified.
- Declining produces no notification and no visible trace to the sender.
- Accepting immediately grants friends-scoped access on every surface —
  profile, listening, reviews, follow lists, Home.
- Removing a friendship immediately revokes all of it, cache included.
- Every pre-existing mutual follow is a friendship after migration, with no
  user losing access they had the day before.
- A user cannot be friends with themselves, nor hold duplicate rows for a pair.
- Requests beyond the rate limit are refused.
- Existing visibility integration tests pass unchanged against the new
  definition of friend — that suite is the real safety net for this migration.

---

# Design Requirements

Per BRAND_BIBLE §8 and §10 — calm, no urgency, no pressure. A pending request
is a quiet state, not a badge demanding attention. Nothing about the UI should
push a user toward accepting.

Declining must be as easy and unremarkable as accepting, and must not be
presented as rejection. Consistent with §3's treatment of a declined Melody,
which is deliberately invisible.

---

# Technical Notes

- New table plus a `friend_request_scope` column on `users`. Additive.
- `NotificationType` gains request-received and request-accepted. Deliberately
  **not** request-declined, per the rule above.
- Canonical pair ordering (`least(user_a, user_b)`) with a unique constraint is
  the simplest way to prevent duplicate pairs; the alternative — two rows per
  friendship — makes every query and every deletion a chance to leave a
  half-friendship behind.
- **Scale:** a friends-of-user lookup sits in the hot path of profile
  visibility. Index accordingly; this replaces a mutual-follow join that is
  currently doing the same work, so it should be no worse and probably better.

---

# Rollback Plan

Behind a settings flag. Off reverts every friends-scoped check to
`is_mutual_follow`, which is why the migration must be additive: friendship
rows are created *alongside* follows, never in place of them, so the old
definition keeps working untouched.

Friendship rows survive a rollback and are correct again when re-enabled.

---

# Open Questions — resolved

_Founder decisions, 2026-09-27._

1. **Default `FriendRequestScope` — `everyone`.** Matches the Melody default.
   Users can narrow it to people they follow, or to mutual follows, in
   settings. Every refusal returns the same message, so a sender never learns
   which setting refused them.
2. **Accepting does not create follows — but following back is one tap.**
   Friendship and follows stay independent, as the Model section already says.
   Beside each friend the owner does not already follow, their friends list
   shows a one-tap Follow (the Instagram "follow back" pattern), so accepting
   moves the new friend there with the follow-back ready. It is not offered on
   a pending request, where it would be the loudest control and outweigh the
   Accept / "Not now" choice the Design Requirements keep neutral.
3. **A sender never sees their own outstanding request.** After sending, the
   profile control returns to its normal state and no outgoing list exists, so
   there is also no withdraw action. A pending request and a declined one are
   therefore indistinguishable to the sender, which is the strongest form of
   the silent-decline rule. The send itself returns a one-time
   acknowledgement; asking again is accepted, changes nothing, and never
   re-notifies.
4. **No friend count anywhere.** A user's friends list is visible only to
   them, on their own friends page (ENGINEERING_BIBLE §6).

# Implementation decisions

Recorded here because they affect future work, per WORKFLOW.md §3.

- **One friends check.** `app/services/friendship.py::are_friends` is the only
  friends decision any visibility code calls. It covers the seven call sites
  listed above plus Harmony's summary visibility, which shipped after this
  spec was written. With `FRIENDSHIPS_ENABLED=false` it falls back to mutual
  follow.
- **A pair is notified once per notification type.** A partial unique index
  means asking again never re-notifies, mirroring the existing rule that a
  re-follow never re-notifies. The incoming list, not the notification, is the
  source of truth for pending requests.
- **Rate limit: 5 per minute and 30 per day on sending**, keyed like every
  other limit in the app (by client address, not account). Accept, decline
  and remove carry the ordinary 30-per-minute write limit.
- **Migration attribution.** A converted mutual-follow pair records the
  earlier follower as the requester and the later follow's time as the
  acceptance time.
- **Home's `has_mutual_follows`** is kept as a deprecated alias of the new
  `has_friends`, so a frontend and backend deployed out of order still agree.
