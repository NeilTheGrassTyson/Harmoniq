# Local-First Catalog Search

> **Status: Approved by Founder 2026-08-01.** Written 2026-08-01 from
> instrumented measurements against production Neon and live MusicBrainz
> (appendix at the bottom). Open questions resolved with the recommended
> defaults recorded inline (single blended response; tracks local-only on
> strong artist match; thresholds as proposed; one-time seeding at
> approval).

---

# Purpose

Search is the front door to every identity act in Harmoniq — rating,
reviewing, highlighting, sending a Melody all start by finding the music.
Today that front door is slow and unreliable in exactly the way that
matters: an uncached search takes 3.3s in the best case, 7–16s typically,
and fails outright with a 503 when one MusicBrainz call exceeds its 10s
timeout (observed twice in a single measurement session). Every uncached
query is fully hostage to MusicBrainz latency.

Worse, the results themselves are wrong for the most common query shape.
MusicBrainz's Lucene score rewards *title* matches, so searching an artist
name returns tribute junk: for "phoebe bridgers" the album category
contains "Lullaby Versions of Phoebe Bridgers" while her actual albums
(scored 44, below the 50 threshold) are filtered out; for "radiohead"
every album and track returned is a random release *titled* "Radiohead."
The artist row is right; the rest of the page undermines it.

Local-first search fixes both: results come from our own Postgres catalog
(fast, always available), and because the local catalog knows entity
relationships, an artist-name query can return *that artist's* albums and
tracks — which no amount of MusicBrainz score tuning can do.

**Core principle strengthened: Musical Identity.** Search is how a user
reaches the music that expresses who they are; a search that returns 8-bit
covers instead of the artist's discography actively corrodes that. It also
serves Quality Before Speed's intent (HARMONIQ.md §3) in the literal sense:
this is the considered fix, not the quick patch.

---

# Scope

### In Scope

- Postgres-first search over locally ingested artists, albums, and tracks,
  with fuzzy matching (`pg_trgm` trigram indexes — purely additive
  migration: `CREATE EXTENSION` + three GIN indexes, no table changes).
- Entity-aware local ranking: when the query strongly matches an artist,
  that artist's own albums and tracks populate those categories (joined by
  `artist_id`), ranked above incidental title matches.
- MusicBrainz fallback when local results are thin (threshold below), going
  through the existing search path, whose background ingestion then widens
  the local catalog — a miss today is a local hit tomorrow.
- One-time seeding via the existing `backend/scripts/seed_catalog.py`
  (~330 curated artists with full discographies; smoke-tested 2026-08-01:
  `--limit 3` seeded 3/3, incl. 103 Bad Bunny albums). Seeding is what
  makes local-first pay off on day one.
- Frontend request hygiene in `SearchBar`/`SearchPage`: abort in-flight
  requests on new keystrokes (`AbortController`), so abandoned prefix
  queries ("ra", "rad", "radi"…) stop queueing 3 MusicBrainz calls each
  behind the process-global 1 req/s limiter.
- A config flag to fall back to the current MusicBrainz-first behavior
  (rollback path).

### Out of Scope

- Any change to the `SearchResponse` API contract or to the split between
  the Home and Discovery surfaces.
- Staleness/refresh policy for local rows (`last_fetched_at` exists;
  a refresh pass is future work).
- People search (`searchUsers`) — already local and fast.
- Detail pages (already local-first).
- Cover-art sourcing/verification (explicitly excluded per Amendment C2).
- Any recommendation-engine or taste-graph use of this data. This spec
  changes *when* public catalog metadata is read, not *what* is collected
  about users — nothing here touches user data collection or sharing.

---

# User Experience

- **Entry point** — unchanged: the header search bar (dropdown) and the
  /search page.
- **Core flow** — user types; results appear in well under a second for
  anything in the local catalog (a local trigram query against Neon is a
  single round-trip, ~70–150ms). For an artist-name query, the Albums and
  Tracks sections show that artist's actual work.
- **Empty state** — unchanged copy ("No results for …") — but it should now
  be rare for real music, since thin local results trigger the MusicBrainz
  fallback before giving up.
- **Loading state** — unchanged ("Searching…"); on the fallback path it can
  last several seconds, same as every search does today.
- **Error state** — MusicBrainz failures only surface when the fallback was
  needed *and* failed; a local hit renders even if MusicBrainz is down.
  Same calm copy as today.
- **Success state** — results render; no new UI.
- **Edge cases** — disambiguation: two artists named the same (e.g.
  "Nirvana") must both surface, with their disambiguation strings, as
  MusicBrainz results do today. Misspellings ride on trigram similarity
  rather than Lucene fuzziness; quality parity here is an explicit
  acceptance criterion.

---

# Functional Requirements

- System should query the local catalog first for all three categories,
  using trigram similarity on `artists.name` (and aliases), `albums.title`,
  `tracks.title`.
- System should treat a strong artist match as an intent signal: that
  artist's own albums and tracks (via `artist_id`) rank above unrelated
  title matches in their categories.
- System should fall back to the current MusicBrainz search when local
  results are thin (proposed: no artist above similarity 0.4 AND fewer
  than 3 total local hits — threshold is a module constant, tunable).
- System should never block the response on ingestion (preserved from
  Amendment D1).
- System should keep serving search when MusicBrainz is unavailable, for
  any query the local catalog can answer.
- Data must be filtered by the same quality gates that govern ingestion
  today (housekeeping names, standard release groups only, no videos), so
  local-first never *widens* what search shows.
- Feature should never order results by popularity or engagement signals —
  ranking is text-match quality plus entity relationships, consistent with
  the "No engagement patterns" rule (phase-1-catalog.md).
- Feature should never auto-generate social objects from search activity
  (no interaction with Melody/Harmony).
- Frontend must abort superseded in-flight search requests on new input.
- A config flag (`search_local_first`, default on once approved) must
  restore the MusicBrainz-first path without a deploy rollback.

---

# Acceptance Criteria

- [ ] A query matching a seeded artist returns in < 500ms server-side
      (vs. 3.3–16s today), measured against production Neon.
- [ ] "radiohead" returns Radiohead's own albums (e.g. OK Computer,
      In Rainbows) in the Albums section — not releases titled "Radiohead"
      by other artists. Same class of check for tracks.
- [ ] With MusicBrainz unreachable (simulated), a seeded-artist query still
      returns full results; an unseeded query fails with today's 503 copy.
- [ ] An unseeded query falls back to MusicBrainz, returns results, and a
      repeat of that query after background ingest completes is served
      locally.
- [ ] A misspelled seeded-artist query ("radiohed") still finds the artist.
- [ ] Homonymous artists both appear with disambiguation strings.
- [ ] Typing "radiohead" letter-by-letter issues at most one in-flight
      catalog request at a time (aborted predecessors observable in dev
      tools).
- [ ] The migration is purely additive and reversible (`DROP INDEX`,
      extension left in place).
- [ ] Full check suites pass; relevance-filter tests extended to cover
      local ranking.

---

# Design Requirements

No new UI. The existing search surfaces keep their layout, copy, loading
and empty states (BRAND_BIBLE §7–8: calm, not demanding). The design-level
change is result *quality*: categories that respect artist intent read as
curated rather than scraped — consistency over novelty.

---

# Technical Notes

- Touches `app/services/catalog.py` (new local query path + fallback
  orchestration), `app/services/musicbrainz.py` (unchanged client), one
  Alembic migration (`pg_trgm` + 3 GIN indexes), `SearchBar.tsx` /
  `search/page.tsx` / `lib/catalog.ts` (AbortController).
- Neon supports `pg_trgm` natively; `CREATE EXTENSION IF NOT EXISTS` is
  allowed on the current plan.
- Implementation note (2026-08-01): aliases are matched via
  `array_to_string` in the query but not indexed — `array_to_string` is
  STABLE, not IMMUTABLE, so an expression index would require a custom
  wrapper function (rejected per HARMONIQ.md §4). Artists is the smallest
  catalog table; revisit if artist-search latency grows with scale.
- The search endpoint reacquires a DB session dependency (dropped in D1) —
  local-first queries need one; ingestion stays on its own background
  session.
- Local ranking sketch: `GREATEST(similarity(name, :q), exact-prefix
  boost)`, artists first; albums/tracks = owned-by-matched-artist when a
  strong artist match exists, otherwise title-similarity ≥ 0.3, capped at 5.
- Implementation note (2026-08-01): the original sketch unioned title
  matches behind the artist's own releases as filler. Live verification
  showed that padding a sparse artist (e.g. seeded without tracklists)
  re-admits the title-junk this spec exists to kill, so on a strong artist
  match the albums/tracks categories are relationship-only — title
  similarity applies only when no artist matched strongly.
- MusicBrainz remains the source of truth for *existence*; local Postgres
  is a cache with relationships, not a fork of the database. No MusicBrainz
  data is used for model training (ENGINEERING_BIBLE §13) — this spec
  changes read paths only.

---

# Rollback Plan

- `search_local_first: bool` in `app/config.py` (env-driven). Off →
  exactly today's behavior (MusicBrainz-first, background ingest).
- The migration is additive; rollback is `DROP INDEX` × 3. No data is
  transformed or deleted. Seeded rows are ordinary catalog rows created by
  the existing ingestion path and stay valid regardless of the flag.

---

# Open Questions

1. **Fallback threshold.** Is "no artist ≥ 0.4 similarity AND < 3 local
   hits" the right definition of *thin*? Too eager re-introduces
   MusicBrainz latency; too lazy hides real music that isn't seeded yet.
2. **Two-phase results.** Should thin local results render immediately with
   MusicBrainz results streamed in after (faster perceived, more moving
   parts), or should the fallback stay a single blended response
   (recommended for v1 — simpler, and only the long tail pays the wait)?
3. **Track-category fallback.** Given the measured junk in MusicBrainz
   recording search for artist-name queries, should the fallback populate
   Tracks at all when the query matched a local artist, or leave Tracks
   local-only in that case? (Recommended: local-only on strong artist
   match.)
4. **Seeding cadence.** Run `seed_catalog.py` once at approval (~30–60 min,
   rate-limited), or also on a schedule to pick up new releases? (Refresh
   policy is otherwise out of scope.)

---

# Appendix — Measurements (2026-08-01, production Neon + live MusicBrainz)

One uncached `search_and_ingest`, instrumented (limiter wait / HTTP /
per-statement DB time), before the D1 change:

| query | total | limiter wait | MB network (3 calls) | ingest DB | statements |
| --- | --- | --- | --- | --- | --- |
| phoebe bridgers | 15.9s | 86ms | 11.2s (recording: 9.7s) | 3.7s | 38 |
| big thief | 7.1s | 93ms | 2.7s | 3.2s | 33 |
| radiohead (MB warm) | 9.2s | 0ms | 4.0s | 4.5s | 49 |

- "radiohead" recording search twice exceeded the 10s client timeout →
  whole search 503s. MusicBrainz tail latency, not the 1 req/s limiter, is
  the dominant risk: measured limiter wait never exceeded 93ms because MB
  itself is usually slower than the 1s interval.
- Ingest was 33–49 sequential statements at ~70ms Neon round-trip each —
  removed from the response path by Amendment D1 (committed): response now
  ~3.3s uncached, all of it the three sequential MusicBrainz calls.
  Local-first is the remaining lever for sub-second search.
- Relevancy: see Purpose. Raw data: artist-name queries return
  title-matching junk in Albums/Tracks; the artist's real releases score
  below the `_MIN_RELEVANCE_SCORE = 50` threshold (e.g. 44) because the
  match is on the artist field, not the title.

---

Once approved, this spec moves into implementation under the standard
process defined in **WORKFLOW.md**.
