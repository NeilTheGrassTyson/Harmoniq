# Music Catalog

> Feature Spec — Phase 1 / NOW tier
> Status: Approved — 2026-06-18

---

# Purpose

The Music Catalog is the shared data layer that every other Harmoniq feature
depends on. Without a normalized, persistent representation of tracks, albums,
and artists, there is nothing to rate, nothing to send as a Melody, and nothing
for the Home or Discovery surfaces to surface.

It solves a concrete problem: Harmoniq needs canonical, stable identifiers for
music entities so that a rating by one user, a Melody from another, and a
trending signal from a third all refer to unambiguously the same track —
regardless of what streaming service any individual user listens on.

The principle it strengthens is **Musical Identity**: the catalog is the
vocabulary through which users express taste. A rating is only meaningful if
the thing being rated is precisely identified and consistently represented
across the product.

---

# Scope

### In Scope

* Artist entity: name, MusicBrainz Artist ID (MBID), sort name, disambiguation
  string (e.g. "John Williams (guitarist)" vs "John Williams (conductor)"),
  cover image URL from Cover Art Archive or MusicBrainz artist image where
  available.
* Album (Release Group) entity: title, MBID, primary artist, release year,
  album art URL from Cover Art Archive, album type (album / single / EP /
  compilation).
* Track (Recording) entity: title, MBID, primary album, primary artist,
  duration in milliseconds, track number, disc number.
* On-demand ingestion: when a search query is issued and MusicBrainz returns
  results, those entities are written to the local DB before the response is
  returned to the client. Subsequent requests for the same entity are served
  from the local DB.
* Deduplication: if an entity with the same MBID already exists in the DB,
  the ingestion step updates it rather than inserting a duplicate.
* Detail pages for artists, albums, and tracks — each displaying the entity's
  metadata and artwork.
* Minimal search (this spec): a search input that queries MusicBrainz and
  returns matching tracks, albums, and artists. This is the search surface
  described in the ROADMAP NOW tier — scoped here because catalog and minimal
  search are inseparable at this layer. Full cross-entity ranked search is a
  NEXT-tier feature and is out of scope.

### Out of Scope

* Audio playback or preview (deferred to Demo + Open, Phase NEXT, using
  Deezer API per Phase 0 decisions).
* User-generated data attached to catalog entities (ratings, reviews, Melodies)
  — those are separate features that reference catalog entities by MBID.
* Playlist entities — not in the NOW tier.
* Multiple release versions of the same recording (e.g. remaster vs original) —
  the canonical Release Group MBID is sufficient for Phase 1; per-release
  disambiguation is a future refinement.
* Bulk import or pre-seeding of the catalog — the catalog grows on-demand only.
* MusicBrainz relationship data (e.g. "this artist is a member of that band") —
  not needed for Phase 1.
* Spotify metadata — per CLAUDE.md constraints, Spotify data may not feed the
  catalog or any downstream ML layer.

---

# Non-Goals

This feature is not intended to:

* Recommend music or rank results by popularity within Harmoniq.
* Mirror or replicate the complete MusicBrainz database.
* Serve as a discovery surface — it is a lookup and reference layer only.
* Support offline browsing.
* Replace or compete with a streaming platform's catalog.

---

# User Experience

**Entry point:** The user types into the search bar, which is accessible from
the main navigation on every page.

**Core flow (happy path):**
1. User types a query (e.g. "Radiohead", "Kid A", "Creep").
2. After a short debounce (~300ms), the frontend sends the query to the backend.
3. The backend calls the MusicBrainz API, ingests any new entities, and returns
   structured results grouped by type: Artists, Albums, Tracks.
4. Results appear in a grouped list beneath the search bar. Each result shows:
   - **Artist:** name, disambiguation string if present, small artist image.
   - **Album:** title, artist name, release year, album art thumbnail.
   - **Track:** title, artist name, album title, duration.
5. User taps/clicks a result and is taken to that entity's detail page.

**Detail page — Artist:**
Name, image, disambiguation, and a list of the artist's albums (those already
in the local DB from prior searches — not a complete discography pull).

**Detail page — Album:**
Art (large), title, artist, year, type, and a track listing (populated if those
tracks are in the local DB).

**Detail page — Track:**
Title, artist, album, duration, album art. No playback in Phase 1.

**Empty state:** If the query returns no results from MusicBrainz, display:
"No results for [query]." No suggestions, no algorithmic fallback.

**Loading state:** A subtle skeleton or spinner within the search results area.
The search bar itself remains interactive. No full-page loading state.

**Error state:** If the MusicBrainz API call fails (timeout, 5xx), display:
"Couldn't reach the music catalog right now. Try again in a moment." Log the
error server-side. Do not expose MusicBrainz error details to the client.

**Success state:** Results are visible. No confirmation toast or banner —
results appearing is the success signal.

**Edge cases:**
- Query with only whitespace: trim and treat as empty; do not call the API.
- Query shorter than 2 characters: do not call the API (wait for more input).
- MBID collision across entity types is not possible by MusicBrainz design, but
  the DB schema should namespace by entity type regardless.
- MusicBrainz rate limit: the API allows 1 request/second without an
  authenticated account. The backend must enforce this with a request queue or
  token bucket — never surface rate limit errors to the user as such.
- Disambiguation strings: always display them when present; never suppress them
  silently.

---

# Functional Requirements

**Search**
* User can search for artists, albums, and tracks from the main navigation
  search bar.
* Search input is debounced at ~300ms before triggering an API call.
* Search input shorter than 2 non-whitespace characters must not trigger a call.
* System must query MusicBrainz and return results grouped into three sections:
  Artists, Albums, Tracks — 5 results per section (15 total).
* System must ensure all returned entities are persisted to the local DB before
  the response is returned to the client. Whether persistence is implemented
  synchronously inline or via a fast background task is an engineering decision,
  provided the guarantee holds.
* System must not call MusicBrainz more than once per second (rate limit
  compliance).
* System should cache MusicBrainz responses for ~5 minutes so that rapid
  repeated identical queries do not re-hit the API.

**Ingestion & deduplication**
* System must upsert on MBID — if an entity already exists, update its fields;
  do not create a duplicate row.
* Data must store the MBID as the stable primary external identifier for every
  entity. Internal Postgres UUIDs are the primary key; MBID is a unique index.
* System must store Cover Art Archive URLs, not images themselves — artwork is
  served from Cover Art Archive's CDN, not proxied or stored in Harmoniq's
  infrastructure.
* System must record a `last_fetched_at` timestamp on every ingested entity so
  stale records can be refreshed in a future pass.

**Detail pages**
* The frontend must provide an artist detail page, an album detail page, and a
  track detail page, each reachable by MBID. Routing implementation is an
  engineering decision.
* Each detail page must display the entity's stored metadata and artwork.
* Artist detail page must list albums by that artist that exist in the local DB
  (not a complete discography fetch — no additional MusicBrainz calls on artist
  detail pages in Phase 1).
* Album detail page must list tracks on that album that exist in the local DB.
* If an entity MBID is not in the local DB (e.g. direct URL navigation to an
  unseen entity), the system silently attempts a single MusicBrainz lookup,
  ingests the entity, and renders the page. If the lookup returns no result or
  fails, the page displays a standard "Not found" state.
* A detail page load must not trigger more than one MusicBrainz API call.

**General**
* All catalog data is publicly readable — no authentication required to search
  or view catalog pages (auth is required for user-generated interactions, which
  are out of scope for this spec).
* System must never expose MusicBrainz API errors or internal stack traces to
  the client.

---

# Acceptance Criteria

* [ ] Searching "Radiohead" returns at least one Artist result, multiple Album
      results, and multiple Track results without error.
* [ ] Artist, album, and track entities returned by search are present in the
      local Postgres DB after the search completes.
* [ ] Searching the same query twice does not insert duplicate rows (upsert
      behavior confirmed by DB inspection).
* [ ] Navigating to an artist, album, and track detail page for an
      already-ingested entity renders correctly with metadata and artwork.
* [ ] Navigating directly to a detail page for an entity not yet in the DB
      triggers a MusicBrainz lookup and renders the page correctly.
* [ ] A search query of 1 character does not trigger a network request to the
      backend (confirmed via browser dev tools).
* [ ] Empty search results display the "No results" copy with the query echoed.
* [ ] A simulated MusicBrainz failure returns the error copy to the client with
      no stack trace or internal detail visible.
* [ ] MusicBrainz rate limit (1 req/sec) is not exceeded under rapid repeated
      searches (confirmed by request log inspection).
* [ ] Cover Art Archive image URLs are stored in the DB; no artwork binary data
      is stored in Harmoniq's own infrastructure.
* [ ] All new DB migrations run cleanly via Alembic on a fresh schema.
* [ ] Backend static analysis (ruff, mypy) passes clean.
* [ ] Frontend static analysis (tsc, eslint, prettier) passes clean.

---

# Design Requirements

**Minimal and intentional (BRAND_BIBLE §7, §8):**
Search results must not feel like a content feed. The grouped list (Artists /
Albums / Tracks) is a structured lookup tool, not a discovery surface. No
"trending searches," no promoted results, no "you might also like" injected into
the results. The catalog is infrastructure — it should feel like a precise
instrument, not a recommendation engine.

**Artwork display:**
Album art and artist images should be displayed cleanly with consistent
proportional sizing. No carousel, no hero imagery, no animated transitions.
A cover that loads slowly should degrade to a neutral placeholder — never a
broken image icon.

**Typography and copy (BRAND_BIBLE §10):**
- Disambiguation strings are displayed in a secondary/muted typographic weight
  directly beneath the artist name. Do not suppress or truncate them.
- Duration on track results is formatted as `m:ss` (e.g. `4:02`), not raw
  milliseconds.
- "No results for [query]" — echo the actual query string, quoted. No emoji, no
  suggestions.
- Error copy: "Couldn't reach the music catalog right now. Try again in a
  moment." — calm, not alarming.

**No engagement patterns:**
No "popular on Harmoniq," no sort-by-popularity in search results. Results are
ordered by MusicBrainz relevance score as returned — that's a search-quality
signal, not a social one.

---

# Technical Notes

**Data relationships:**
- One artist may have many albums; one album may contain many tracks.
- A recording may exist on multiple MusicBrainz releases, but Phase 1
  intentionally stores only the canonical Release Group relationship.
  Per-release disambiguation is explicitly deferred.
- `album_id` on the tracks table is nullable: a track may be ingested from a
  search result before its parent album has been ingested.

**MusicBrainz API:**
- Base URL: `https://musicbrainz.org/ws/2/`
- Required header: `User-Agent: Harmoniq/0.1 (<MUSICBRAINZ_CONTACT_EMAIL>)` —
  MusicBrainz requires this; requests without it will be rejected. The contact
  email is read from the `MUSICBRAINZ_CONTACT_EMAIL` environment variable (set
  in `.env` / Railway config) — it is never hardcoded.
- Endpoints used: `/recording` (tracks), `/release-group` (albums), `/artist`.
- Response format: JSON (`fmt=json` query param).
- Returns 5 results per entity type (5 Artists, 5 Albums, 5 Tracks = 15 total).
- Rate limit: 1 unauthenticated request/second. Implement a backend token bucket
  or request queue — do not rely on the frontend to throttle.
- MusicBrainz search uses Lucene-style syntax internally but accepts plain
  string queries fine for Phase 1.

**Cover Art Archive:**
- Artwork URL pattern: `https://coverartarchive.org/release-group/[mbid]/front`
- This URL redirects to the actual image. Store the canonical CAA URL, not the
  redirect target (redirect targets are CDN-ephemeral).
- Not every release group has cover art — handle the 404 case gracefully with a
  neutral placeholder.

**Database schema (new tables — Alembic migration required):**
```
artists
  id            UUID PK
  mbid          VARCHAR UNIQUE NOT NULL
  name          VARCHAR NOT NULL
  sort_name     VARCHAR
  disambiguation VARCHAR
  image_url     VARCHAR
  last_fetched_at TIMESTAMPTZ NOT NULL

albums (release groups)
  id            UUID PK
  mbid          VARCHAR UNIQUE NOT NULL
  title         VARCHAR NOT NULL
  artist_id     UUID FK → artists.id
  release_year  INTEGER
  album_type    VARCHAR  -- 'album' | 'single' | 'ep' | 'compilation' | 'other'
  cover_art_url VARCHAR
  last_fetched_at TIMESTAMPTZ NOT NULL

tracks (recordings)
  id            UUID PK
  mbid          VARCHAR UNIQUE NOT NULL
  title         VARCHAR NOT NULL
  artist_id     UUID FK → artists.id
  album_id      UUID FK → albums.id  -- nullable (track may appear before album
                                     -- is ingested)
  duration_ms   INTEGER
  track_number  INTEGER
  disc_number   INTEGER
  last_fetched_at TIMESTAMPTZ NOT NULL
```

**Backend modules touched:**
- New: `app/services/musicbrainz.py` — MusicBrainz API client + rate limiter.
- New: `app/services/catalog.py` — ingestion + upsert logic.
- New: `app/api/v1/catalog.py` — search and detail endpoints, registered on the
  existing v1 router.
- New: `app/models/catalog.py` — SQLAlchemy models for the three tables.
- New: `app/schemas/catalog.py` — Pydantic request/response schemas.
- New: `alembic/versions/[hash]_add_catalog_tables.py` — migration.

**Frontend capabilities required:**
- Search interface accessible from main navigation.
- Artist detail page, reachable by MBID.
- Album detail page, reachable by MBID.
- Track detail page, reachable by MBID.
- Typed API client functions for all catalog endpoints.
- Artist, Album, and Track types added to the shared type definitions.

Implementation location and file structure for the above is left to engineering.

**No new paid dependencies introduced by this feature.**

---

# Observability

* MusicBrainz API requests and responses must be logged at debug level,
  including endpoint, query, and response time.
* Cache hits and cache misses on search queries must be logged at debug level.
* Ingestion failures (upsert errors, malformed MusicBrainz responses) must be
  logged at error level with enough context to reproduce the failure.
* Stack traces and internal error detail must never be logged in a way that
  surfaces to the client.
* User-sensitive data (search queries may be personal — treat them as such)
  must not be logged at info level or above in production.

---

# Rollback Plan

- The three new DB tables (`artists`, `albums`, `tracks`) are additive — no
  existing tables are modified. The Alembic migration is reversible via
  `alembic downgrade`.
- The catalog API endpoints are new routes; removing them does not affect any
  existing endpoint.
- If the MusicBrainz integration proves unreliable in production, the search
  endpoint can return an empty result set with the error copy without breaking
  any other feature (no other Phase 1 feature yet depends on catalog data
  existing).
- No feature flag is strictly required given the above; the entire feature can
  be disabled by removing the catalog router from `app/api/v1/router.py` and
  reverting the migration.

---

# Open Questions

None.

---

*Approved 2026-06-18. Implementation proceeds under the standard Review Workflow in WORKFLOW.md.*

---

# Amendments — 2026-07-05 (Founder-approved)

## C1. Search relevance filtering

Search results were previously unfiltered by relevance: `app/services/musicbrainz.py`'s
three search functions returned raw MusicBrainz hits verbatim, and only
artists were screened for MusicBrainz's "Special Purpose" housekeeping
entries (`[unknown]`, `[data]`, etc.) — never albums or tracks, even though
those carry the same problem one level deeper (a legitimately-titled
release credited to a housekeeping artist).

`app/services/catalog.py` now applies, for all three categories:

* A minimum relevance threshold on MusicBrainz's own `score` field
  (0–100 Lucene relevance) — `_MIN_RELEVANCE_SCORE = 50`, a module
  constant, tunable later, not exposed via the API.
* The housekeeping-name filter, extended to albums and tracks by checking
  the *artist-credit* name (via the existing `_primary_artist_name`
  helper) rather than the release/recording title — the bracketed-name
  problem lives on the artist, not the album/track title.
* Results sorted by score descending and capped at
  `_MAX_RESULTS_PER_CATEGORY = 5` (matching the prior de facto count, now
  chosen deliberately from a larger, ranked pool rather than incidentally
  from an unranked one).

To give the filter enough headroom, `search_artists`/`search_release_groups`/
`search_recordings` now request `limit=20` from MusicBrainz by default
(previously `5`), still filtered back down to 5 before returning.

## C2. Cover art explicitly out of scope

This amendment does **not** touch cover-art sourcing or verification —
`_CAA_URL` is still built unconditionally from the MBID with no existence
check, per an explicit Founder decision to scope this pass to search
relevance only. Any cover-art fix remains a separate, future piece of work.
