# Highlights — The Curated Half of a Profile

> **Status: DRAFT — awaiting Founder approval.** Tier 1 per WORKFLOW.md §1
> (net-new, user-facing feature; changes how user data is shared). Nothing
> here is implemented.
>
> Sibling to `specs/phase-2-listen-history.md`, which specifies the observed
> half of the same profile surface. This spec is deliberately independent: it
> touches no provider data and no ToS boundary, so it can be approved and
> shipped without waiting on listen history.

---

# Naming — resolved

The Founder initially referred to this feature as a user's **"harmony."** That
name is already taken, and the collision was raised and settled on 2026-09-06:
**this feature is Highlights; Harmony remains the reputation signal.**

For the record, since the overlap is easy to re-introduce:

**ENGINEERING_BIBLE §3 defines Harmony** as a profile-level *signal* with two
parts kept deliberately separate — a computed component (derived from Melody
acceptance rate and sustained positive reception, owned by the recommendation
service) and a cosmetic one (theme, theme song). §6 forbids exposing it as a
leaderboard or sortable ranking. §11 lists it as a Phase 1 pillar.

**§3 also already defines this feature**, precisely: *Highlighted songs* — "the
most important expression of identity... an intentional act of self-curation —
what a user chooses to surface as representative of their taste."

Both will eventually sit on the same profile, so one word could not carry both.

**One amendment is still required.** §3 says "highlighted *songs*." This spec
covers tracks, albums **and** artists, so §3 must be widened to match — a
documentation change to make alongside implementation, per HARMONIQ.md §7.

---

# Purpose

A profile's observed listening is transient by nature — it is what someone
happened to play. It cannot say what someone stands behind.

Highlights are the deliberate half: up to 15 tracks, albums or artists a user
picks to represent their taste, permanent until they change them, and public by
default so that another person can read someone's taste at a glance.

**Principle strengthened: Musical Identity**, and directly **Discovery Through
People**. Per HARMONIQ.md §2, a recommendation originating from a person must
be distinguishable from an algorithmic one; Highlights is the purest form of
the human-originated signal, and — as the Founder put it — the reference point
that drives the wider Harmoniq mechanism.

---

# Scope

### In Scope

- Up to **15** highlights per user — a combined cap across all three types,
  not 15 of each (Founder decision, 2026-09-06).
- Unordered — no manual arrangement.
- The owner's own review displayed alongside a highlight when one exists.
- Public by default (a constitutional exception; see below).
- Rendering alongside observed listening on the profile.

### Out of Scope

- Observed listening — `specs/phase-2-listen-history.md`.
- Any computed Harmony signal (Melody acceptance rate, reputation).
- Ranking, scoring or sorting highlights across users. ENGINEERING_BIBLE §6's
  no-leaderboard constraint applies to anything profile-level of this kind.
- Using highlights as recommendation input. First-party data, so unlike
  listens this is permitted in principle — but it is a separate decision and a
  separate spec.

---

# Constitutional exception: public by default

**HARMONIQ.md §6 requires visibility to default to the most private option.**
This feature defaults to public. That is a constitutional exception and is
recorded as one, per HARMONIQ.md's Constitutional Debt section.

- **Approved by:** Founder, 2026-09-06.
- **Reasoning:** highlights exist to be read by other people. A private-by-
  default curated set is inert — nobody can use it to understand anyone's
  taste, which is the entire mechanism. This follows the precedent already set
  for `visibility_ratings` and `visibility_follows`
  (`backend/app/models/user.py`, Amendments 2026-07-04), where a private
  default would have nullified the feature it governed.
- **Bounded by:** the act of adding a highlight is always explicit. Nothing is
  auto-populated, so a public default exposes only what a user deliberately
  chose to put there. Highlights are **encouraged but optional** — a user who
  adds none discloses nothing.
- **Condition for reevaluation:** if highlights ever become auto-suggested,
  auto-populated, or derived from behaviour, the public default must be
  revisited immediately — at that point it would be publishing something the
  user did not deliberately choose.

The scope remains user-changeable to friends or private at any time, and takes
effect immediately (ENGINEERING_BIBLE §8.1).

---

# User Experience

Highlights render as their own group on the profile, visually distinct from
observed listening — a viewer must be able to tell what someone chose from what
someone merely played (HARMONIQ.md §2).

Each highlight shows its cover art and title. **When the owner has written a
review of that item, their own review appears with it** — in the footer or
beneath the thumbnail.

Review resolution, in order:

1. The owner's review of the highlighted item.
2. For a **track** highlight with no track review: the owner's review of that
   track's album.
3. Otherwise: no review shown. The highlight stands alone.

**Only the owner's own review is ever shown here.** This is that person's
statement about their own taste; another user's review of the same album is
someone else's voice and does not belong on this surface.

**Artist highlights never carry a review.** Ratings in this codebase are
polymorphic over tracks and albums only (`backend/app/models/rating.py`), so
there is no artist review to resolve. This is a property of the ratings model,
not an omission here.

---

# Functional Requirements

1. A `highlights` table: user, `entity_type` (`track` | `album` | `artist`),
   polymorphic entity reference, `created_at`. Follows the existing polymorphic
   pattern in `models/rating.py`.
2. Maximum 15 per user **combined across track, album and artist**, enforced
   server-side, not only in the UI.
3. No ordering field. Display order is stable and derived (by `created_at`);
   the user does not arrange them.
4. Deleting a user deletes their highlights (`ON DELETE CASCADE`).
5. A highlight whose underlying entity disappears must not break the profile.
6. Highlights carry `visibility_highlights`, defaulting to `public`, honoured
   at the data-access layer (ENGINEERING_BIBLE §8.1).
7. **The attached review is gated independently by `visibility_ratings`.** See
   below — this is the requirement most likely to be got wrong.

---

# The review-visibility trap

A highlight is public by default. A review is governed separately by the user.
**Attaching a review to a public highlight must not publish a review the author
did not intend to publish.** The two scopes are independent and must both be
satisfied: a viewer permitted the highlight but not the commentary sees the
highlight *without* it — not redacted, not an error.

This is easy to get wrong because the natural implementation joins highlights
to ratings and returns both. Enforcement belongs in the query, and an
integration test must pin it. The album fallback inherits the rule: falling
back from a track to its album review must re-check against the *album's*
review, not the track's.

**Dependency.** How rating visibility works is being changed —
`specs/phase-2-rating-visibility-split.md` proposes an always-public score with
friends-only commentary, which requires a constitutional amendment and a
migration decision. Highlights consumes that model; it does not define it.

Under the proposed model this surface becomes: **score always shown, commentary
only for mutual follows, a Follow control in its place otherwise.** Highlights
should not ship its own interpretation of rating visibility — it should call
whatever `app/services/rating.py` enforces, so there is exactly one place where
this rule lives.

---

# Acceptance Criteria

- A user can add up to 15 highlights across tracks, albums and artists; the
  16th is refused by the API, not just the UI.
- A track highlight shows the owner's track review; with none, the owner's
  album review; with neither, no review.
- An artist highlight never shows a review.
- A stranger sees no commentary on a public highlight when the owner has not
  made commentary visible to them — verified by integration test.
- A stranger sees no highlights at all when `visibility_highlights` is private.
- Another user's review of the same album never appears on this surface.
- Highlights survive disconnecting a music provider — they are first-party and
  independent of any integration.
- A user with zero highlights renders a calm empty state, not an error.

---

# Design Requirements

Per BRAND_BIBLE §8 and §10 — calm, minimal, no urgency. Highlights are the
emotional centre of a profile and should feel composed rather than dense.

Highlights must be visually distinguishable from observed listening without a
legend. Mixed entity types (track, album, artist) need a consistent treatment;
artist artwork is circular per DESIGN_SYSTEM §4 while album and track art is
not, so the grouping must tolerate both shapes without looking accidental.

Empty state should invite rather than nag — highlights are encouraged but
optional, and the copy must not imply a profile is incomplete without them.

---

# Technical Notes

- New table, new `visibility_highlights` column on `users`. Purely additive.
- Polymorphic entity reference follows `models/rating.py`, including its
  existing approach to the un-constrained FK.
- The profile query already assembles visibility-gated fields in
  `app/services/user.py`; highlights join that pattern rather than inventing
  one.
- Reviews come from `app/services/rating.py`, which already enforces
  visibility at the data layer — reuse it rather than re-implementing the check.
- **Scale:** bounded at 15 rows per user. Trivial at any size in the roadmap.

---

# Rollback Plan

Behind a settings flag, default off, following the `SEARCH_LOCAL_FIRST`
precedent. Off hides the surface; rows are preserved and reappear when
re-enabled. Nothing else references the table.

---

# Open Questions

_Founder decides._

1. **Can a user highlight something they have not rated?** Assumed yes — a
   highlight is a statement of taste, and requiring a review first would make
   the feature much harder to start using.
2. **Should the empty state be shown to visitors, or only to the owner?**
   Showing "no highlights yet" to a stranger advertises an absence; hiding the
   section entirely may read as a missing feature.
