# Listen History — Durable Recent Listening

> **Status: DRAFT — awaiting Founder approval.** Tier 1 per WORKFLOW.md §1
> ("any change to how user data is collected, stored, or shared — including
> anything touching the recommendation engine's data pipeline"). Nothing in
> here is implemented.

---

# Purpose

A profile's Listening section currently shows whatever the provider's rolling
window happens to hold at the moment someone looks. Spotify returns roughly the
last 50 plays; Apple Music returns about 30, without timestamps, and leaves
stale entries in place for days. Nothing is stored, so the section empties on
its own and a profile that was expressive yesterday is blank today.

This feature persists what we observe, so a profile can show a durable list of
roughly the last 25 tracks a person actually played.

**Principle strengthened: Musical Identity.** A profile that forgets everything
between visits cannot express who someone is.

**An honest caveat the Founder should weigh.** ENGINEERING_BIBLE §3 ranks
*highlights* — deliberate self-curation — above listening signals, which it
calls "noisy... meaningful only when aggregated." This feature makes activity
legible, not curated. If the real goal is "songs that represent me," Highlights
(specced in §3, entirely unbuilt) is the more direct answer and does not touch
the data pipeline at all. This spec is worth building if the goal is *activity
over time*; it is the wrong tool if the goal is *identity by choice*. See Open
Questions.

---

# Scope

### In Scope

- A provider-agnostic `listens` table recording observed plays.
- Ingestion from Spotify's recently-played endpoint, behind a provider
  interface that Apple Music can later implement.
- Serving the profile's Listening section from stored rows rather than a live
  fetch, with the existing now-playing behaviour unchanged.
- Explicit consent for storage at connect time, and deletion of stored listens
  on disconnect.
- Retention policy and its enforcement.

### Out of Scope

- Apple Music itself. This spec only ensures the model does not preclude it.
- Any use of stored listens by recommendation, similarity, trending, or the
  Home feed. See the boundary below — this is a hard prohibition, not a
  sequencing decision.
- Highlights (ENGINEERING_BIBLE §3) — a separate, unbuilt feature.
- Scrobbling to third parties; import of historical listening from any
  provider.

### Non-Goals

- Completeness. We record what we observe. Plays that happen between polls, or
  outside a linked provider, are simply not captured, and the UI must never
  imply the list is exhaustive.
- Replacing the live now-playing indicator, which stays fetch-on-view.

---

# The boundary this feature must not cross

This is the most consequential thing in the spec.

CLAUDE.md records that Spotify's developer policy **prohibits training ML
models on Spotify content or metadata**. ENGINEERING_BIBLE §13 restates it:
Spotify-derived data "may be displayed; it may not be used as training input,"
and the taste graph must be built from "listens logged inside our own app."

A `listens` table filled by polling Spotify is Spotify-derived data. Displaying
it is permitted. The same table quietly becoming an input to similarity or
recommendation is the violation — and it is the kind that happens by accident,
one convenient join at a time, long after anyone remembers why the rule
existed.

**Requirement: the boundary is enforced structurally, not by comment.**

- Every row carries a `source` discriminator (`spotify`, `apple_music`,
  `harmoniq`) recording where the observation came from.
- Recommendation, similarity, and trending code may read only rows whose
  `source` is first-party. Provider-derived rows are display-only.
- The restriction is expressed as a database view or a service-layer accessor
  that recommendation code uses exclusively — not as a `WHERE` clause each
  caller is trusted to remember.
- A test asserts that provider-sourced rows are unreachable through the
  recommendation accessor. That test is the real deliverable of this section.

---

# User Experience

On a profile whose activity is visible, the Listening section shows up to 25
recent tracks, newest first, each with the track, artist, and a relative time.
Now playing keeps its existing distinct treatment above the list.

Rows persist between visits. A profile that has been quiet for a week still
shows last week's listening, with honest relative timestamps that make the
staleness legible rather than hidden.

At connect time the user is told, plainly, that linking will record what they
play so it can appear on their profile — and that disconnecting deletes it.
This is a materially larger ask than the current display-only link, and the
consent copy must not be inherited from it.

Disconnecting deletes stored listens immediately, not on a schedule.

---

# Functional Requirements

1. A `listens` table stores: user, track reference, `source`, `played_at`
   (provider-reported, **nullable**), `observed_at` (when we recorded it,
   always present), and an idempotency key.
2. `played_at` is nullable specifically because Apple Music does not supply it.
   Display logic must degrade to `observed_at` without special-casing the
   provider at the call site.
3. Ingestion is idempotent: re-observing the same play must not create a
   duplicate row.
4. The profile query returns at most 25 rows, newest first, and respects
   `visibility_activity` at the data-access layer (ENGINEERING_BIBLE §8.1) —
   not in the presentation layer.
5. Disconnecting a provider deletes that user's rows for that `source`
   synchronously, within the disconnect request.
6. Deleting a user deletes their listens (`ON DELETE CASCADE`).
7. Retention is enforced by a scheduled job, not left to grow unbounded.
8. Recommendation-facing accessors cannot return provider-sourced rows.

---

# Acceptance Criteria

- A profile shows stored listens after the provider's rolling window has moved
  past them.
- Polling the same provider window repeatedly produces no duplicate rows.
- A user with `visibility_activity = private` returns no listens to any other
  viewer, enforced in the query, verified by an integration test.
- Disconnecting Spotify leaves zero rows for that user and source.
- A recommendation accessor asked for a user's listens returns nothing
  provider-sourced, verified by test.
- Apple Music's shape (no timestamps) is representable without schema change —
  demonstrated by a test constructing a row with `played_at = NULL`.

---

# Design Requirements

Per BRAND_BIBLE §8 and §10: calm and minimal, matching the existing Listening
rows. Relative timestamps stay quiet and human ("3m ago", "Jun 30").

The list must never imply completeness. Where the record is partial — a gap
between polls, a provider linked yesterday — the copy should be honest that
this is what we saw, not everything that happened.

---

# Technical Notes

**Ingestion mechanism is the main open cost.** Today listening is fetch-on-view
with a 60s cache. Persisting on view means a person's history is only captured
when someone happens to look at their profile — so an unvisited profile records
nothing, and history quality depends on popularity. That is a strange property
for an identity surface.

The alternative is a scheduled per-user poll, which means new infrastructure:
a worker or cron on Railway, plus rate-limit budgeting across connected users.
Spotify's recently-played returns up to 50 items, so a poll interval under the
time it takes a heavy listener to play 50 tracks is sufficient to avoid loss.
This is the single largest implementation decision and is not resolved here.

**Existing code this touches:** `app/services/spotify.py` (fetch and mapping,
currently `_RECENT_LIMIT = 20`), `app/models/spotify.py` (whose docstring
asserts listening is never persisted and must be revised), `app/services/
user.py` (profile assembly), `app/api/v1/spotify.py`, and on the frontend
`ListeningSection` plus `usePolledListening`.

**Track identity.** Listens must reference the normalized track entity
(ENGINEERING_BIBLE §3), not a provider ID, or the table cannot serve Apple
Music without a migration. This likely requires on-demand MusicBrainz
resolution during ingestion, which is a latency and failure-mode concern the
implementation must handle without dropping the listen.

**Scale** (WORKFLOW.md §2.3). At 100 users with a 15-minute poll, roughly 10k
rows/day. At 100k users, ~10M rows/day — partitioning and aggressive retention
become mandatory. Retention policy should be chosen with the 100k case in mind
even though it is far off.

**Migration:** purely additive — one new table, no changes to existing ones.

---

# Rollback Plan

Ingestion sits behind a settings flag (`LISTEN_HISTORY_ENABLED`, default off),
following the `SEARCH_LOCAL_FIRST` precedent. Off restores the current
live-fetch path exactly, since the display code keeps the live fetch as its
fallback.

Stored rows are preserved on rollback and are deletable per user without
touching anything else. Dropping the table is reversible in the sense that no
other entity references it.

---

# Open Questions

_Founder decides; do not answer these in implementation._

1. **Is this the right feature at all?** Highlights (ENGINEERING_BIBLE §3) is
   the specced-but-unbuilt mechanism for "songs that represent me," and it is
   curation rather than derivation — closer to HARMONIQ §2, Humans Before
   Algorithms. Should Highlights come first, with listen history deferred until
   there is a concrete need for it?
2. **Ingestion mechanism:** scheduled per-user polling (accurate, new
   infrastructure) or on-view capture (no new infrastructure, history biased by
   who visits you)?
3. **Retention:** how long do stored listens live? A rolling window (90 days?),
   a fixed row cap per user, or indefinite until disconnect?
4. **Consent granularity:** is storage bundled into the existing Spotify
   connection, or a separate opt-in a user can decline while still showing
   now-playing?
5. **Does storing provider-derived listening change the ToS position at all?**
   This spec assumes display-only storage is permitted and only *training* is
   prohibited, reading ENGINEERING_BIBLE §13 literally. If that reading is
   wrong, the feature cannot be built as described. Worth confirming against
   the current Spotify Developer Terms before implementation begins.
6. **Default visibility** for stored listens — inherit `visibility_activity`,
   or introduce a separate scope, given that a persistent record is a larger
   disclosure than an ephemeral one?
