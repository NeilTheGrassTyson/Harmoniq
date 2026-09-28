# Discovery — Music Through the People You Trust

> **Status: DRAFT — awaiting Founder approval.** Tier 1 per WORKFLOW.md §1
> (net-new surface; reads across many users' data at once; touches the
> recommendation boundary). Nothing here is implemented. Drafted 2026-09-28
> from the ROADMAP NEXT item "Discovery layer". This is the draft with the
> most open questions, deliberately: it is the first surface that could drift
> into algorithmic ranking, and the constitution is specific about how far it
> may go.

---

# Purpose

Home is fixed and minimal: trending, and top songs from friends
(ENGINEERING_BIBLE §5). There is nowhere to *explore* — to see what the
people you trust have been choosing, playing and sending.

Discovery is that place: an optional, scrollable surface built from the
trust graph, where every item says which person it came from.

**Principle strengthened: Discovery Through People** — by definition. Every
item is traceable to a person the viewer chose to trust (§1: "there must be a
traceable chain of trust… that explains why that content exists in front of
them").

---

# What the constitution already decides

- **Discovery is separate from Home**, with its own endpoint (§5, §7).
- **Social signals strictly dominate algorithmic adjustment**; ranking order is
  trusted users, then followed users, then similarity, then algorithmic
  candidates (§6).
- **No engagement optimisation** — no virality, click-through or
  time-on-platform (§5, §10).
- **Algorithmic items are never shown with equal or greater prominence than a
  person's, without the distinction being clear** (HARMONIQ.md §2).
- **Provider-sourced data never informs what a user is shown.** Stored
  Spotify listens and playlist highlights are display-only
  (`listens_svc.first_party_listens`, `highlight_svc.first_party_highlights`).

---

# Scope

### In Scope (v1)

A reverse-chronological feed — no ranking function — of things people the
viewer trusts have *chosen* or *done*, each visible to the viewer under that
person's own settings:

- **Highlights** added by friends, followed people and friends of friends.
- **Reviews** they wrote, subject to rating visibility.
- **Recent listening** they've made visible (their stored plays, shown as
  display, newest first — which the listen-history spec explicitly classes as
  display, not ranking).

Each item names its person, and shows why it's there ("Alex highlighted",
"Sam reviewed").

### Out of Scope (v1)

- **Any ranking function, similarity or algorithmic candidates.** §5 describes
  a ranking that blends trust strength, highlight weight, similarity and
  freshness — but trust scoring is undefined (§13) and similarity is deferred.
  v1 is chronological and filtered by relationship only; ranking is a later
  spec once trust scoring exists.
- **"Playlist-based suggestions"** (the roadmap's wording). Playlists here are
  Spotify playlists, which the ToS keeps out of anything that decides what a
  user sees. A friend's playlist *highlight* can appear as that friend's
  highlight; suggestions derived from playlists cannot.
- **"Listening-history-based suggestions"** from provider listens, for the same
  reason. First-party listens don't exist yet.
- Infinite scroll with engagement mechanics. Discovery paginates on request.

---

# Visibility

The first feature that reads across many users at once (roadmap security
note). Every item must pass its owner's scope **in the query**, not after:

- highlights by `visibility_highlights`,
- reviews by `rating_svc`'s rule (per-review scope under the profile master
  switch, moderation-hidden excluded),
- listening by `visibility_activity`,
- "friends" meaning `friendship_svc.are_friends`.

A revoked grant or a removed friendship takes effect on the next request;
nothing is served from a stale fan-out (§8.1). v1 therefore computes the feed
on read, not by fan-out on write.

---

# User Experience

- **Entry point:** a Discovery item in the sidebar. Never the landing page (§5).
- **Core flow:** a calm list of items, newest first, each with the person,
  what they did, and the music; "Show more" loads the next page.
- **Empty:** "When people you trust highlight, review or share listening,
  it'll show up here." plus a link to find people.
- **Loading / error:** section skeleton; a failure shows a retry, never an
  empty feed claiming nothing happened.

---

# Functional Requirements

1. `GET /discovery` (authenticated), cursor-paginated, separate from `/home`.
2. Sources: highlights, reviews and stored listens of the viewer's friends,
   followed users and friends of friends (public items only for the last),
   each gated by its own visibility in SQL. A friend-of-a-friend item never
   names the connecting friend.
3. Order: newest first. No weighting, scoring or personalisation.
4. Every item carries the person it came from and the kind of action.
5. No provider-sourced data is used to select or order items beyond showing
   it newest-first; a test pins that the query never consults provider data
   for anything but display.
6. Bounded page size; no infinite scroll.

---

# Acceptance Criteria

- [ ] A friend's public highlight, review and visible listening appear, newest
      first, each attributed.
- [ ] Private or friends-only items never reach a viewer outside their scope —
      verified per source by integration test.
- [ ] Unfriending removes that person's friends-scoped items on the next load.
- [ ] Items appear only from friends, follows and friends of friends; a
      friend-of-a-friend item is public and never names the connecting
      friend — verified by test.
- [ ] No ranking beyond recency — verified by test.
- [ ] Discovery is never the default route.

---

# Design Requirements

BRAND_BIBLE §7–8 and §13: optional, intent-driven, calm. Items are quiet rows
or tiles with the person first. No counts, streaks, "you might also like", or
urgency. It should feel like reading what friends left out for you, not like a
feed designed to keep you scrolling.

---

# Technical Notes

- A union query over three sources with keyset pagination on
  `(created_at, id)`; indexes exist on each source's user and time columns.
- Scale: bounded by the viewer's friends, follows and friends of friends; the
  second hop grows roughly with the square of friend count, so cap it per
  request and measure. At 100k users, a user
  following many people makes the union heavier; measure before adding a
  fan-out table, which would also complicate revocation.

---

# Rollback Plan

`DISCOVERY_ENABLED`, default off; off hides the nav item and the endpoint
returns 404. Read-only feature: nothing to preserve.

---

# Open Questions

_Founder decides._

1. ~~**Is a chronological, unranked v1 acceptable?**~~ **RESOLVED 2026-09-28 —
   yes, for now, and expected to change later.** The Founder plans a
   recommendation XP system that indicates how good someone is at
   recommending music: an accepted Melody earns some XP, a "send me more like
   this" endorsement earns the most, and a rejection earns nothing and costs
   nothing. XP needs a constitutional amendment and its own spec before it can
   inform Discovery's ordering; it builds on the XP proposal in
   `specs/phase-2-melody-reactions.md`.
2. ~~**Whose activity appears?**~~ **RESOLVED 2026-09-28 — friends, followed
   profiles, and friends of friends.** Two consent guardrails apply to friends
   of friends: only their *public* items appear (they aren't the owner's
   friends, so friends-scoped items never reach them), and an item reads
   "from your wider circle" without naming the connecting friend, because
   friend lists are owner-only (`GET /friends/me`) and naming the bridge would
   disclose a friendship neither person chose to show.
3. ~~**Should Melodies appear?**~~ **RESOLVED 2026-09-28 — no, Melodies are
   left out.** A follow-up is open with the Founder on the review page: whether
   site-wide popularity belongs to Home's trending section (as ENGINEERING_BIBLE
   §5 has it) or to Discovery.
4. **The roadmap's "playlist-based" and "listening-history-based suggestions"**
   can't be built from Spotify data under the ToS. Drop them from the roadmap
   item, or keep them for when first-party listening exists?
