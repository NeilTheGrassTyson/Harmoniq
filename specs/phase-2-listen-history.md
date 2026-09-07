# Listen History — Durable Recent Listening

> **Status: DRAFT rev 4 — all open questions resolved (2026-09-06);
> awaiting approval to implement.** Tier 1 per WORKFLOW.md §1 ("any change to
> how user data is collected, stored, or shared — including anything touching
> the recommendation engine's data pipeline"). Nothing here is implemented.
>
> Rev 4 drops the opt-in seed and specifies the latency requirement instead. The curated half is now specified
> separately in `specs/phase-2-highlights.md`.

---

# Purpose

A profile's Listening section shows whatever the provider's rolling window
happens to hold at the moment someone looks. Spotify returns roughly the last
50 plays; Apple Music returns about 30, without timestamps, and leaves stale
entries in place for days. Nothing is stored, so the section empties on its own
and a profile that was expressive yesterday is blank today.

This feature persists what we observe, so a profile keeps showing recent
listening between visits.

**Principle strengthened: Musical Identity.** A profile that forgets everything
between visits cannot express who someone is.

## The profile surface is two-part

Founder decision (Q1): both halves are wanted, and they are different in kind.

| | Source | Count | Lifetime |
| --- | --- | --- | --- |
| **Recent listening** | observed from the linked provider | ~20 | rolling; refreshed on view |
| **Highlights** | chosen by the user | up to 15 | permanent until the user changes them |

This resolves the tension flagged in rev 1. ENGINEERING_BIBLE §3 ranks
deliberate curation above listening signals, which it calls "noisy... meaningful
only when aggregated" — and that ranking is honoured by giving curated tracks
permanence while listening stays a rolling window. Activity is transient
because activity *is* transient; what a person chooses to stand behind is not.

**Scope note.** The curated half is Highlights, a first-class domain entity in
ENGINEERING_BIBLE §3, now specified in `specs/phase-2-highlights.md`: it has its own write path,
its own consent story, and — unlike this feature — touches no provider data and
no pipeline boundary. This spec fixes the *shape* of the combined surface so
both halves are designed against one agreement; the Highlights mechanism is
specced separately and can ship first, since nothing here blocks it.

---

# Scope

### In Scope

- A provider-agnostic `listens` table holding a capped, rolling window per user.
- Ingestion from Spotify's recently-played endpoint, behind a provider
  interface Apple Music can later implement.
- Serving the Listening section from stored rows; now-playing stays live.
- A separate opt-in for storage, and deletion of stored listens when it is
  withdrawn or the provider is disconnected.
- Rendering the curated half alongside recent listening.

### Out of Scope

- The Highlights write path — selection UI, ordering, limits. Its own spec.
- Apple Music itself. This spec only ensures the model does not preclude it.
- Any use of stored listens by recommendation, similarity, trending, or Home.
  A hard prohibition, not a sequencing decision — see the boundary below.
- Scrobbling to third parties; importing historical listening from a provider.

### Non-Goals

- Completeness. We record what we observe. Plays between views, or outside a
  linked provider, are not captured, and the UI must never imply otherwise.
- Replacing the live now-playing indicator.

---

# The boundary this feature must not cross

The most consequential requirement in this spec.

CLAUDE.md records that Spotify's developer policy **prohibits training ML
models on Spotify content or metadata**. ENGINEERING_BIBLE §13 restates it:
Spotify-derived data "may be displayed; it may not be used as training input,"
and the taste graph must be built from "listens logged inside our own app."

**Founder decision (Q5): display-only storage is accepted.** Storing
provider-derived listening in order to render it is treated as display, not
training input. This spec is built on that reading.

The risk is not the decision; it is the drift. A `listens` table is one
convenient join away from becoming a recommendation input, long after anyone
remembers why it must not be.

**Requirement: the boundary is enforced structurally, not by comment.**

- Every row carries a `source` discriminator (`spotify`, `apple_music`,
  `harmoniq`) recording where the observation came from.
- Recommendation, similarity, and trending may read only first-party rows.
- The restriction is a database view or a single service-layer accessor that
  recommendation code uses exclusively — not a `WHERE` clause each caller is
  trusted to remember.
- A test asserts provider-sourced rows are unreachable through the
  recommendation accessor. **That test is the real deliverable of this
  section.**

Selecting and ordering rows for display by recency is display. Any future
ranking that weighs listens to decide *what a user should see* has left display
and re-opens this question.

---

# User Experience

On a profile whose activity is visible: up to 20 recent tracks, newest first,
each with track, artist and a relative time. Now playing keeps its existing
distinct treatment above the list. Curated tracks render as their own group,
visually distinct from observed listening — a viewer must be able to tell what
someone chose from what someone merely did (HARMONIQ.md §2).

Rows persist between visits. A profile quiet for a week still shows last week's
listening, with honest relative timestamps that make staleness legible rather
than hidden.

**Consent (Q4 — Founder decision: a separate opt-in).** Storage is a distinct,
explicit choice, not bundled into the provider connection. A user may link
Spotify for now-playing and decline storage. The opt-in is provider-agnostic by
design, so linking Apple Music later reuses the same grant rather than asking
again. Withdrawing it deletes stored listens immediately.

---

# Functional Requirements

1. `listens` stores: user, track reference, `source`, `played_at`
   (provider-reported, **nullable**), `observed_at` (always present), and an
   idempotency key.
2. `played_at` is nullable because Apple Music does not supply it. Display
   degrades to `observed_at` without special-casing the provider at the call
   site.
3. **Ingestion merges; it never replaces.** On view, the fetched window is
   unioned with stored rows, deduplicated by idempotency key, sorted newest
   first, and trimmed to 20. A failed or empty provider response must leave
   stored rows untouched. *Replacing the window would reintroduce the exact
   blanking bug this feature exists to fix, the first time Spotify returned
   nothing.*
4. Ingestion is idempotent: re-observing a play creates no duplicate row.
5. The profile query returns at most 20 observed rows plus the curated set, and
   enforces `visibility_activity` at the data-access layer
   (ENGINEERING_BIBLE §8.1) — never in presentation.
6. **Visibility (Q6 — Founder decision):** stored listens inherit
   `visibility_activity`. No new scope.
7. Withdrawing the storage opt-in, or disconnecting the provider, deletes that
   user's rows for that `source` synchronously within the request.
8. Deleting a user deletes their listens (`ON DELETE CASCADE`).
9. Recommendation-facing accessors cannot return provider-sourced rows.
10. **Rendering never waits on a provider call.** The profile response is
    built from stored rows; ingestion runs outside the render path and its
    result is visible on a subsequent view. A provider timeout must degrade to
    stale rows, never to a slow or failed page.
11. Curated tracks are unaffected by every rule above: they are first-party,
    permanent, and independent of any provider connection.

---

# Acceptance Criteria

- A profile shows stored listens after the provider's window has moved past
  them.
- A provider response that is empty or fails leaves the stored list intact.
- Repeated views produce no duplicate rows and never exceed 20 stored per user.
- `visibility_activity = private` returns no listens to any other viewer,
  enforced in the query, verified by integration test.
- Withdrawing the storage opt-in leaves zero rows for that user and source.
- A recommendation accessor returns nothing provider-sourced, verified by test.
- Apple Music's shape is representable without schema change — demonstrated by
  a row with `played_at = NULL`.
- Curated tracks survive disconnecting the provider and withdrawing the opt-in.
- A profile view returns in normal page time with the provider unreachable,
  serving stored rows.

---

# Design Requirements

Per BRAND_BIBLE §8 and §10: calm and minimal, matching existing Listening rows.
Relative timestamps stay quiet and human ("3m ago", "Jun 30").

Curated and observed tracks must be visually distinguishable without a legend.
The list must never imply completeness; where the record is partial, the copy
should be honest that this is what we saw.

---

# Technical Notes

**Ingestion (Q2 — Founder decision: on-view capture).** No scheduler, no new
infrastructure. Two consequences to handle:

- *A visitor's request triggers a write and an outbound API call.* **Founder
  decision: anonymous views do trigger ingestion**, so a profile stays fresh
  even when only logged-out visitors read it. The cost is that an unauthenticated
  caller can cause work on the profile owner's behalf. Ingestion must therefore
  reuse the existing 60s payload cache as its floor, so repeated views cannot
  amplify into repeated Spotify calls, and the write must be cheap enough to sit
  in a page render. Rate limiting is a security-audit item (WORKFLOW.md §2.5),
  not an afterthought.
- *No separate seed.* **Founder decision (revised): load-on-visit is the
  seed.** The first view of a profile populates it; nothing extra is needed.
  The real concern behind the original question was **latency** — a profile
  view must not feel slow because it is waiting on Spotify.

**Latency requirement (this is the one that matters).** Rendering reads stored
rows only. Ingestion must never block the response: the page returns from the
database immediately, and the provider fetch happens outside the render path,
so a slow or hanging Spotify call costs a stale row, never a slow page. The
freshly fetched window lands for the next view. Combined with the 60s cache
floor, the common case makes no outbound call at all.

This also removes the worry about anonymous views: an unauthenticated visitor
triggers at most a background refresh, never a wait.
- *History quality depends on being looked at.* An unvisited profile stops
  updating. Accepted: with a 20-row cap the surface is "recent listening,"
  not an archive, and the merge rule means it degrades by going stale rather
  than by going blank.

**The 20-row cap simplifies scale considerably** versus rev 1's unbounded
table. Steady state is bounded at 20 rows per connected user — roughly 2M rows
at 100k users, not 10M/day. Partitioning is unnecessary; the cap *is* the
retention policy (Q3), enforced on write rather than by a cleanup job.

**Existing code touched:** `app/services/spotify.py` (fetch and mapping,
currently `_RECENT_LIMIT = 20`), `app/models/spotify.py` (whose docstring
asserts listening is never persisted and must be revised), `app/services/
user.py`, `app/api/v1/spotify.py`, and on the frontend `ListeningSection` plus
`usePolledListening`.

**Track identity.** Listens must reference the normalized track entity
(ENGINEERING_BIBLE §3), not a provider ID, or the table cannot serve Apple
Music without a migration. This likely means on-demand MusicBrainz resolution
during ingestion — a latency and failure mode that must not drop the listen.

**Migration:** purely additive. One new table, plus one column or row for the
storage opt-in.

---

# Rollback Plan

Ingestion sits behind a settings flag (`LISTEN_HISTORY_ENABLED`, default off),
following the `SEARCH_LOCAL_FIRST` precedent. Off restores the current
live-fetch path exactly, since the display code keeps the live fetch as its
fallback.

Stored rows are preserved on rollback and deletable per user. Nothing else
references the table, so dropping it is contained.

---

# Decision log

| Q | Question | Decision (2026-09-06) |
| --- | --- | --- |
| 1 | Is this the right feature, or Highlights instead? | **Both.** Two-part surface; Highlights gets its own spec. |
| 2 | Ingestion mechanism | **On-view capture.** No scheduler. |
| 3 | Retention | **20 observed, rolling; 10–15 curated, permanent.** |
| 4 | Consent granularity | **Separate opt-in**, provider-agnostic. |
| 5 | ToS position | **Display-only storage accepted.** |
| 6 | Default visibility | **Inherits `visibility_activity`.** |
| 7 | Do anonymous views trigger ingestion? | **Yes**, floored on the 60s cache. |
| 8 | First-time seed? | **No** — load-on-visit is the seed; latency is handled by never blocking the render. |
| 9 | Curated count / types | **Up to 15**, track \| album \| artist. See the Highlights spec. |
| 10 | Curated ordering | **Unordered**, with the owner's own review attached. |
| 11 | Curated default visibility | **Public** — a recorded constitutional exception. |
