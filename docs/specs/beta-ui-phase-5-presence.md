# Beta UI Phase 5 addendum — Friends rail and Online presence

> Tier 1 per WORKFLOW.md §1: a change to how user data is collected. Addendum
> to `docs/specs/beta-ui-implementation.md` Phase 5, which it narrows rather
> than replaces. Drafted 2026-09-27 after the Founder chose real Online
> presence over a Listening-now-only rail. **Status: awaiting Founder
> approval — no code before it.**

---

# Purpose

- **Problem:** the Melodies page has no sense of who, among the people you
  trust, is around right now. The beta-ui mockup (`.design/logo/MelodiesBeta.dc.html`)
  adds a right-hand rail: **Listening now → Online → Offline**.
- **Why it belongs in Harmoniq:** Trust Between People and Humans Before
  Algorithms (HARMONIQ.md) — the rail is the most direct "discovery through
  people" surface there is: the people you mutually follow, and what they are
  playing, with a one-step way to send them something.
- **Why it needs care:** "Online" does not exist anywhere today. Building it is
  new collection of behavioural data, so HARMONIQ.md §6 (Consent Before
  Visibility) governs every choice below.

# Scope

### In Scope

- A friends rail on the Melodies page, desktop widths (`lg`, ≥1024px).
- **Friends = mutual follows** — the definition every other surface uses
  (`services/follow.py` `get_mutual_follow_ids`). No one else ever appears.
- Three groups, in this order, each alphabetical by display name:
  1. **Listening now** — a Spotify currently-playing track, shown only when the
     friend's existing `visibility_activity` admits friends. Row subtitle:
     "Track — Artist". This is the signal the profile's listening section
     already shows; no new consent is needed for it.
  2. **Online** — the friend has Harmoniq open right now, shown only when their
     **new** `visibility_presence` setting admits friends.
  3. **Offline** — every other friend.
- A new per-user setting, **"Online status"**, in the profile's existing
  visibility panel beside "Listening activity": **Private** (default) or
  **Friends**.
- One row action: **Send**, revealed on hover and on keyboard focus.

### Out of Scope

- Status text, "last seen", idle / away timers, typing indicators, and any
  sort by a measure of a person (activity, Harmony, follower count). Omitted
  from the mockup deliberately; they stay omitted.
- Presence anywhere but this rail — not on profiles, search, or any other
  payload.
- A mobile rail. Below `lg` the rail is not rendered.
- Shared presence storage (Redis or similar). A new paid service is its own
  Tier 1 decision; see Technical Notes for the single-process constraint this
  implies.

# User Experience

- A friend who sets Online status to **Private** — the default — appears in
  **Offline** whether or not they are online. Private and offline are
  deliberately indistinguishable: a separate "hidden" state would itself
  reveal that someone chose to hide.
- Listening now does not depend on Online status: it is governed by the
  existing listening-activity setting, exactly as on the profile.
- A group with no one in it is not rendered. With no friends at all, the rail
  shows one quiet line pointing to people you follow, not an empty frame.
- Group headers carry the group's size ("Online 3"), as in the mockup. That is
  a count of your friends, not a measure of any one of them.

# Functional Requirements

1. **Heartbeat.** While a Harmoniq tab is open *and visible* (Page Visibility
   API), the client sends `POST /api/v1/presence/heartbeat` every **60s**, and
   once immediately on becoming visible. A hidden tab sends nothing.
2. **Only consenting users are recorded.** The server drops the heartbeat of
   anyone whose `visibility_presence` is Private — nothing is kept about people
   who haven't opted in. The client also doesn't send one in that case.
3. **Storage is memory only.** `user_id → last-seen monotonic time`, in
   process. Never written to the database, never logged per heartbeat,
   cleared on restart. An entry older than the window is treated as absent and
   pruned.
4. **Online = a heartbeat within the last 120s.** Two missed beats and you are
   offline. No time value is ever returned — only the group.
5. **Rail read.** `GET /api/v1/presence/friends` returns the viewer's mutual
   follows, each with `username`, `display_name`, `avatar_url`, `state`
   (`listening` | `online` | `offline`) and, for `listening` only, `track`
   (`title`, `artist_name`). Grouping and ordering happen server-side; the
   client renders the order it receives.
6. **Enforcement at the data-access layer.** The read resolves each friend's
   settings *at request time*. A friend who isn't admitted is `offline` in the
   payload itself — the client is never handed state it must hide.
7. **Revocation is immediate.** Switching Online status to Private deletes the
   in-memory entry in the same request that saves the setting, and the read
   path re-checks the setting on every request. Unfollowing removes someone
   from both rails on the next read, because mutuality is computed per request.
8. **Refresh.** The rail re-reads every **30s** while visible — the same
   cadence class as the profile's listening poll (25s) — and stops when hidden.
9. **Send** opens `/search?to=<username>`; choosing a track there opens its page
   with the Send Melody panel's recipient pre-filled. No new composer.

# Acceptance Criteria

- [ ] A new account's Online status is **Private**; existing accounts are
      migrated to Private.
- [ ] With Online status Private, a user never appears as Online to anyone,
      and their heartbeats leave no server-side record.
- [ ] Switching to Private removes someone from friends' Online group on the
      friends' next read, without waiting for the 120s window.
- [ ] Only mutual follows appear. A one-way follow in either direction shows
      nothing.
- [ ] Listening now respects `visibility_activity`; Online respects
      `visibility_presence`; neither leaks the other.
- [ ] No presence field appears in any payload other than
      `GET /presence/friends` — checked against the profile, search, home and
      Melody responses.
- [ ] No timestamp, duration, "last seen" or idle value appears anywhere in the
      rail or its payload.
- [ ] Groups in order Listening now → Online → Offline; alphabetical within each.
- [ ] A hidden tab sends no heartbeat and does not poll the rail.
- [ ] Backend integration tests cover each rule above; `npm run verify` and the
      backend CI command pass.

# Design Requirements

- Follows the mockup's rail: sidebar surface (`bg-sidebar`), hairline left
  border, Space Mono group labels, avatar + name + track subtitle rows.
- **The mockup's cyan is not used.** Its Send chip and group counts use
  `#19d8ff`, which is logo-only (`--color-brand`). They use the UI accent.
- Listening rows may carry the `.eq-bar` pulse — a sanctioned motion, stilled
  under `prefers-reduced-motion`. No other motion.
- Rows are people; the track is a subtitle, never a headline (spec Phase 5).
- Works in all three Website Appearance themes.

# Technical Notes

- **Additive migration:** `users.visibility_presence VARCHAR NOT NULL DEFAULT
  'private'` with a CHECK for `private | friends`. `public` is not offered:
  presence has no audience beyond friends, and a "public" choice would
  promise one. Downgrade drops the column.
- **Single process.** In-memory presence is only correct while the backend runs
  one process on one replica — which it does today (`Procfile`,
  `railway.json`: a single `uvicorn` with no `--workers`), and which the
  Spotify listening cache already depends on. If the backend ever scales out,
  presence must move to a shared store first. Recorded as an ADR with this
  phase.
- **Spotify cost.** Listening state reuses `services/spotify.py`'s 60s cache,
  one call per connected friend per minute at most. Spotify's dev-mode cap
  (5 users) bounds this today. At 1,000+ connected users it wants a background
  refresher — deferred and noted, not solved now (WORKFLOW.md §2.3).
- **Load.** One heartbeat per visible tab per minute plus one rail read per 30s
  — about 3 requests/minute for an active user. Both endpoints sit behind the
  existing rate limiter.
- No new dependency and no new paid service.

# Rollback Plan

- Revert the phase: the rail, both endpoints and the setting UI go together.
  Presence lives only in memory, so a deploy leaves no data behind.
- The migration's `downgrade()` drops `visibility_presence`. Per spec Phase 5,
  the rail and the query that serves presence must be removed together — never
  the rail alone.

# Open Questions

_For the Founder, before any code:_

1. Setting values — **Private / Friends** (recommended) or also **Public**?
2. What **Send** does — prefill the recipient through search (recommended), no
   Send in v1, or an inline track picker in the rail (a new composer)?
