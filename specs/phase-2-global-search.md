# Global Search — One Search Across People and Music

> **Status: DRAFT — awaiting Founder approval.** Tier 1 per WORKFLOW.md §1
> (net-new, user-facing behaviour; changes what search exposes about people).
> Nothing here is implemented. Drafted 2026-09-28 from the ROADMAP NEXT item
> "Global Search (full)".

---

# Purpose

Search today is two searches side by side: people by username or display name
(`GET /users/search`, a substring match ordered alphabetically, 20 results),
and the catalog (`GET /catalog/search`, local-first with pg_trgm, grouped into
artists, albums and tracks). The `/search` page shows both halves, and the
nav's SearchBar shows a grouped dropdown. Nothing ranks people, and the two
halves never inform each other.

Full search makes it one question — "find this" — with results ordered by
how likely they are to be what the person meant, and with the people they
already trust surfaced first when a name is ambiguous.

**Principle strengthened: Discovery Through People.** When "Alex" matches
forty people, the Alex you're friends with should come first.

---

# Scope

### In Scope

- A single search endpoint returning people, artists, albums and tracks, each
  ranked, in one response.
- Ranking people by match quality, then by relationship to the viewer
  (friends, then people you follow, then everyone).
- Ranking music by match quality, reusing local-first search's scoring.
- A "top result" when one match is clearly strongest.
- The `/search` page and the SearchBar dropdown moving to it.

### Out of Scope

- Searching reviews, highlights, Melodies or listening. Each is a
  visibility-scoped surface and would be its own decision.
- Personalising music results by the viewer's taste. That is recommendation,
  deferred (ROADMAP LATER) and ToS-sensitive.
- Popularity signals in ranking (follower counts, rating counts). §6: popularity
  alone never qualifies content for surfacing.
- Search history or suggestions.

---

# Visibility

Search stays a browse surface (ADR 0012) and keeps ADR 0008's rule: every
profile is discoverable, and search exposes only identity-card fields
(username, display name, avatar). Ranking by relationship must not leak the
relationship to anyone else:

- The viewer's friends and follows are used only to order *that viewer's*
  results. No result carries a "friend" or "follows you" marker unless the
  viewer could already see it on the profile.
- Anonymous viewers get match-quality ranking only.
- Suspended users stay out of results exactly as `filter_discoverable_users`
  does today.

---

# User Experience

- **Entry point:** the nav SearchBar and `/search`.
- **Core flow:** type; the dropdown shows a top result then a few of each
  kind; Enter or "See all" opens `/search` on its **All** tab. Tabs for
  **Artists**, **Albums**, **Tracks** and **People** show one kind each, with
  "Show more" paging; the active tab is kept in the URL.
- **Empty:** "No results for …" with nothing else.
- **Partial failure:** as today — if one half fails, say so and show the other.
- **Loading:** the existing debounced skeleton.

---

# Functional Requirements

1. One endpoint, `GET /search?q=`, returning `{top, people, artists, albums,
   tracks}`, each capped.
2. People ranked by: exact username or display-name match, then prefix, then
   trigram similarity; ties broken by friend, then followed, then alphabetical.
3. Music ranked by local-first search's existing scoring; MusicBrainz is
   consulted only when the local catalog can't answer, as today.
4. `top` is always set when there are results: the single most relevant
   item across every kind (relevance signals: open question 4).
5. Relationship data is read through `friendship_svc` and the follow service,
   and used for ordering only.
6. `GET /search?q=&type=` narrows the response to one kind
   (`artists | albums | tracks | people`) and pages it by cursor, for the
   kind tabs. Without `type`, the All view's capped groups are returned.
7. The existing endpoints stay until the frontend no longer calls them.

---

# Acceptance Criteria

- [ ] One request returns ranked people and music.
- [ ] An exact username match ranks first.
- [ ] Among equal matches, a friend ranks above a followed user above a
      stranger; a stranger with a stronger match still ranks above a friend
      with a weaker one — both verified by test.
- [ ] A viewer's relationships never change what another viewer sees or learns.
- [ ] Anonymous search works and ranks by match only.
- [ ] Suspended users never appear.
- [ ] Search response time at least as good as today's two calls combined.

---

# Design Requirements

BRAND_BIBLE §7–8: the dropdown stays calm and grouped (DESIGN_SYSTEM §§ on
search results: circular art for people and artists). A top result, when
present, is set apart by position and size, not colour or badges.

---

# Technical Notes

- pg_trgm is already installed (migration `f8a9b0c1d2e3`); a trigram index on
  `users.username` and `users.display_name` would be additive.
- `app/services/catalog.py` local-first search is reused, not rewritten.
- The `filter_discoverable_users` stub in `ARCHITECTURE.md` stays the single
  place discoverability is decided.

---

# Rollback Plan

`GLOBAL_SEARCH_ENABLED`, default off; the frontend falls back to the two
existing endpoints when the new one answers 404. No data changes.

---

# Open Questions

_Founder decides._

1. ~~**Should relationship ordering apply at all?**~~ **RESOLVED 2026-09-28 —
   match quality first, people the searcher knows second.** A relationship
   only reorders equally good matches (friend, then followed, then everyone)
   and never lifts a weaker match above a stronger one — which is
   requirement 2 as written.
2. ~~**Top result threshold**~~ **RESOLVED 2026-09-28 — always show a top
   result, modelled on Spotify's:** the single most *relevant* item across
   every kind, not merely the closest text match, followed by the grouped
   sections. What "relevant" means is question 4.
3. ~~**Should people and music be interleaved**~~ **RESOLVED 2026-09-28 —
   grouped, never interleaved.** Artists, albums, tracks and people stay
   cleanly separate, and `/search` gets tabs: **All** (top result, then a few
   of each kind), **Artists**, **Albums**, **Tracks**, **People**. Each kind
   tab shows only that kind with "Show more" paging; the active tab is in the
   URL (`/search?q=…&type=albums`). The nav dropdown stays a grouped preview
   without tabs.
4. **What makes a result "relevant" beyond its text match?** Raised by the
   answer to question 2. Spotify leans on popularity ("Taylor" finds Taylor
   Swift, not the closest-spelled artist); this spec's Out of Scope currently
   excludes popularity (ENGINEERING_BIBLE §6).
   - **A (recommended):** match quality, then activity from people you know
     (friends' and follows' ratings and highlights), then Harmoniq-wide
     first-party activity. Closest to Spotify's feel, inside our own data and
     led by people; needs the Out of Scope line narrowed.
   - **B:** A plus an open external popularity source such as ListenBrainz.
     Best at finding the famous thing on day one; adds a dependency.
   - **C:** match quality and people you know only. No popularity at all.
