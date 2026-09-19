# Highlights — The Curated Half of a Profile

> **Status: APPROVED WITH MODIFICATION — Founder, 2026-09-19.** Tier 1 per
> WORKFLOW.md §1 (net-new, user-facing feature; changes how user data is
> shared). Not yet implemented.
>
> **The modification:** a user may also highlight playlists they own on a
> connected streaming provider. Founder decisions, 2026-09-19 — playlists are a
> highlight *type* rather than a separate profile section, and **Spotify is the
> only provider in v1**. Specified under "Playlist highlights" below.
>
> Sibling to `specs/phase-2-listen-history.md`, which specifies the observed
> half of the same profile surface.
>
> **Revision note, 2026-09-19.** Rev 1 stated this spec "touches no provider
> data and no ToS boundary, so it can be approved and shipped without waiting
> on listen history." The modification ends that, and the claim is withdrawn
> rather than quietly left standing: playlist highlights read provider data and
> sit behind the same ToS boundary listen history does. The first-party half
> remains independent and can still ship first — see "Sequencing".

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
covers tracks, albums, artists **and** — per the 2026-09-19 modification —
playlists, so §3 must be widened to match. The amendment should also say
plainly that a playlist highlight is the first highlight type whose contents
are provider-derived rather than authored in Harmoniq, since §3's definition of
a highlight as "an intentional act of self-curation" is about the *act* of
highlighting, which still holds, and not about where the item came from. A
documentation change to make alongside implementation, per HARMONIQ.md §7.

---

# Purpose

A profile's observed listening is transient by nature — it is what someone
happened to play. It cannot say what someone stands behind.

Highlights are the deliberate half: up to 15 tracks, albums, artists or
playlists a user picks to represent their taste, permanent until they change
them, and public by default so that another person can read someone's taste at
a glance.

**Principle strengthened: Musical Identity**, and directly **Discovery Through
People**. Per HARMONIQ.md §2, a recommendation originating from a person must
be distinguishable from an algorithmic one; Highlights is the purest form of
the human-originated signal, and — as the Founder put it — the reference point
that drives the wider Harmoniq mechanism.

---

# Scope

### In Scope

- Up to **15** highlights per user — a combined cap across all types, not 15
  of each (Founder decision, 2026-09-06; extended to playlists 2026-09-19).
- **Playlists the user owns on a connected provider**, added one at a time.
  Spotify only in v1 (Founder decision, 2026-09-19).
- Unordered — no manual arrangement.
- The owner's own review displayed alongside a highlight when one exists.
- Public by default (a constitutional exception; see below).
- Rendering alongside observed listening on the profile.

### Out of Scope

- Observed listening — `specs/phase-2-listen-history.md`.
- Any computed Harmony signal (Melody acceptance rate, reputation).
- Ranking, scoring or sorting highlights across users. ENGINEERING_BIBLE §6's
  no-leaderboard constraint applies to anything profile-level of this kind.
- Using highlights as recommendation input. For the three first-party types
  this is permitted in principle — but it is a separate decision and a separate
  spec. For **playlist** highlights it is prohibited outright, not deferred;
  see "The ToS boundary" below.
- Providers other than Spotify. The model must not preclude them, but Apple
  Music in particular carries a paid dependency that is its own Tier 1 decision
  under WORKFLOW.md §1 and is not taken here.
- Copying playlist *contents* into Harmoniq as first-party data, and any
  playlist-building or write-back into the provider.

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
- **This bound is what keeps playlist highlights inside the exception.** The
  2026-09-19 modification was checked against the reevaluation condition below
  before being written in, and it survives that condition *only* because a
  playlist is added one at a time by deliberate choice. A bulk import, a "show
  all my playlists" toggle, or any provider-driven auto-suggestion would
  auto-populate a public-by-default surface and would trip the condition
  immediately. That is why "added one at a time" is a functional requirement
  below and not a UI preference.
- **Condition for reevaluation:** if highlights ever become auto-suggested,
  auto-populated, or derived from behaviour, the public default must be
  revisited immediately — at that point it would be publishing something the
  user did not deliberately choose.

The scope remains user-changeable to friends or private at any time, and takes
effect immediately (ENGINEERING_BIBLE §8.1).

---

# Playlist highlights

Added by Founder modification, 2026-09-19. A user may highlight playlists they
own on a connected streaming provider. **Spotify is the only provider in v1**;
the model must not preclude others, but none are built here.

## Consent: this widens a grant users already gave

`app/services/spotify.py` currently requests exactly
`user-read-recently-played user-read-currently-playing`. Reading playlists
needs an additional scope, and that has three consequences which are
requirements, not implementation detail:

1. **Every already-connected user must re-authorize.** Their existing consent
   was given for a narrow, display-only grant that does not cover playlists.
   Carrying it over silently would fail HARMONIQ.md §6, which requires a
   visibility grant to be "explicit, specific, and revocable."
2. **Declining must cost nothing.** A user who re-links but refuses the
   playlist scope keeps now-playing and recently-played working exactly as
   before. The connection tolerates a partial grant rather than treating it as
   broken. This is detectable from data already stored — the token exchange
   persists the granted `scopes` string on the connection row, so the service
   can read what was actually granted instead of assuming `SCOPES`.
3. **Disconnecting removes the playlist highlights.** They are provider-backed;
   when the grant ends they stop rendering. First-party highlights are
   untouched.

## The ToS boundary

CLAUDE.md records Spotify's prohibition on using Spotify content or metadata to
train or inform the recommendation layer. Playlists are the richest taste
signal this product will ever hold, which makes them simultaneously the most
tempting thing to feed a recommender and the most important to fence off.

`specs/phase-2-listen-history.md` already established the mechanism, and this
spec reuses it rather than inventing a second one: provider-sourced rows carry
a `source` discriminator, recommendation-facing accessors cannot return
provider-sourced rows, and a test pins that. Playlist highlights inherit the
guard unchanged.

Display is permitted. Input to ranking is not.

## What is stored

Only a reference — provider, provider playlist ID, and the display fields
needed to render the card. Playlist *contents* are never copied into Harmoniq
as first-party data. This holds the same "display, not pipeline" position
listen history takes, and keeps the bounded per-user scale note true.

## Cap

A playlist occupies **one** of the 15 slots regardless of how many tracks it
contains. The cap counts highlights, not songs.

## Visibility

Playlist highlights follow `visibility_highlights` like every other type. Note
that a playlist being public *on Spotify* is not consent to publish it on
Harmoniq — the two audiences are different, and §6 requires the sharing
decision to be made here. Adding the highlight is that decision.

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

**Artist and playlist highlights never carry a review.** Ratings in this
codebase are polymorphic over tracks and albums only
(`backend/app/models/rating.py`), so there is no artist or playlist review to
resolve. This is a property of the ratings model, not an omission here.

A playlist card must also be readable *as* a playlist — a viewer should not
mistake it for an album. It is the one highlight type that points outside
Harmoniq, and the one whose contents can change after it was chosen.

---

# Functional Requirements

1. A `highlights` table: user, `entity_type` (`track` | `album` | `artist` |
   `playlist`), polymorphic entity reference, `created_at`. Follows the
   existing polymorphic pattern in `models/rating.py`. A `playlist` row
   references a provider plus that provider's playlist ID rather than a catalog
   entity, since MusicBrainz has no equivalent to point at.
2. Maximum 15 per user **combined across track, album, artist and playlist**,
   enforced server-side, not only in the UI. A playlist counts as one.
3. No ordering field. Display order is stable and derived (by `created_at`);
   the user does not arrange them.
4. Deleting a user deletes their highlights (`ON DELETE CASCADE`).
5. A highlight whose underlying entity disappears must not break the profile.
6. Highlights carry `visibility_highlights`, defaulting to `public`, honoured
   at the data-access layer (ENGINEERING_BIBLE §8.1).
7. **The attached review is gated independently by `visibility_ratings`.** See
   below — this is the requirement most likely to be got wrong.
8. Playlist highlights are added **one at a time by explicit user action**. No
   bulk import, no "add all", no auto-suggestion — this is what keeps the
   public-by-default exception intact, per its Bounded-by clause above.
9. A playlist highlight renders from a provider reference. A provider call that
   fails or times out degrades that one card without failing the profile,
   matching listen history's rule that rendering never waits on a provider.
10. A playlist the user no longer owns, has deleted, or can no longer be read
    under the granted scopes stops rendering without breaking the surface —
    requirement 5 applied to the provider-backed type.

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
- **First-party** highlights (track, album, artist) survive disconnecting a
  music provider — they remain independent of any integration. **Playlist**
  highlights stop rendering when the provider is disconnected or the playlist
  scope is refused, leaving the rest of the profile intact.
- A user who re-links Spotify but declines the playlist scope keeps
  now-playing and recently-played working — verified by test, since this is the
  path most likely to regress quietly.
- A playlist occupies one of the 15 slots; a user holding 15 highlights cannot
  add a playlist as a 16th, refused by the API and not only the UI.
- No recommendation-facing accessor can return a provider-sourced playlist —
  verified by the same class of test listen history requires.
- A user with zero highlights renders a calm empty state, not an error.

---

# Design Requirements

Per BRAND_BIBLE §8 and §10 — calm, minimal, no urgency. Highlights are the
emotional centre of a profile and should feel composed rather than dense.

Highlights must be visually distinguishable from observed listening without a
legend. Mixed entity types (track, album, artist, playlist) need a consistent
treatment; artist artwork is circular per DESIGN_SYSTEM §4 while album, track
and playlist art is not, so the grouping must tolerate both shapes without
looking accidental.

Playlist cards carry provider identity honestly but quietly — enough that a
viewer knows where the playlist lives before clicking, without the profile
turning into a Spotify surface. BRAND_BIBLE §8's calm-over-urgency rule governs
here; a provider logo is an attribution, not a badge.

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
- **Spotify scope widening** is the only change to the existing integration.
  `SCOPES` in `app/services/spotify.py` gains a playlist read scope. The
  connection row already persists the scope string returned by the token
  exchange, so a partial grant is detectable from stored data rather than
  needing a new column — but the code currently falls back to the requested
  `SCOPES` when the provider omits the field, and that fallback must not be
  read as proof a scope was granted.
- Playlist fetches sit behind the same provider-call discipline listen history
  specifies — outside the render path, with a timeout and a degraded card on
  failure — rather than a second, parallel approach.

---

# Rollback Plan

Behind a settings flag, default off, following the `SEARCH_LOCAL_FIRST`
precedent. Off hides the surface; rows are preserved and reappear when
re-enabled. Nothing else references the table.

Playlist highlights sit behind a **second, independent flag**, so the
provider-backed half can be withdrawn — on a ToS question, a Spotify outage, or
a consent problem — without taking the first-party half down with it.

---

# Sequencing

The first-party half (track, album, artist) has no provider dependency and can
ship on its own. The playlist half depends on the Spotify scope widening and
its re-consent flow, and on the `source`-discriminator guard that
`specs/phase-2-listen-history.md` introduces.

Shipping first-party first is therefore possible and is the lower-risk order,
though not mandatory. What *is* mandatory: the re-consent flow ships **with**
the playlist half, never after it.

---

# Open Questions

_Founder decides._

1. **Can a user highlight something they have not rated?** Assumed yes — a
   highlight is a statement of taste, and requiring a review first would make
   the feature much harder to start using.
2. **Should the empty state be shown to visitors, or only to the owner?**
   Showing "no highlights yet" to a stranger advertises an absence; hiding the
   section entirely may read as a missing feature.
3. **Does a playlist highlight snapshot, or follow the provider live?** A
   playlist's contents keep changing after it is highlighted. Following live
   keeps the card honest, but it publishes changes the user never re-affirmed
   on a public-by-default surface. Snapshotting title and art at add-time is
   the safer consent position but drifts toward showing something that no
   longer matches reality. Suggested: follow live, since the user can remove
   the highlight at any moment and a stale card is its own failure — but this
   is a §6 judgement and therefore the Founder's.
4. **Does a playlist highlight carry a review?** Assumed no. Ratings are
   polymorphic over tracks and albums only, so there is no playlist review to
   resolve — the same reasoning that leaves artist highlights review-less.
