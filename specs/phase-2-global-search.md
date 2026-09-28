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
  kind; Enter or "See all" opens `/search` with full grouped results.
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
4. `top` is set only when one result clearly outranks the rest (threshold an
   open question); otherwise it is absent.
5. Relationship data is read through `friendship_svc` and the follow service,
   and used for ordering only.
6. The existing endpoints stay until the frontend no longer calls them.

---

# Acceptance Criteria

- [ ] One request returns ranked people and music.
- [ ] An exact username match ranks first.
- [ ] Among equal matches, a friend ranks above a followed user above a
      stranger — verified by test.
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

1. **Should relationship ordering apply at all?** It surfaces people you know
   first, but it means search results differ by viewer. The alternative is
   pure match-quality ranking for everyone.
2. **Top result threshold** — always show the best match as "top", or only
   when it is clearly ahead?
3. **Should people and music be interleaved** into one ranked list, or stay
   grouped by kind? Grouped is what exists and is calmer; interleaved is more
   "one search".
