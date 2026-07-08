# ROADMAP.md
## Harmoniq — Dev Roadmap (v0.4)

> This is a build roadmap, not a restatement of the constitution: what
> features exist now, what comes next, and what's deliberately deferred.
>
> Security and consent aren't a separate phase — they're a line item under
> each feature, because Principle 5 (Security Is Foundational) means
> designed-in, not reviewed-in-after.
>
> Design consistency isn't a separate phase either. Every feature is
> expected to follow `BRAND_BIBLE.md` as it's built. A polish pass may
> still happen before public release, but it's not where design
> correctness comes from.

**Revision 2026-07-07:** Restructured the NOW tier into a shipped/remaining
split so the Phase 1 → Phase 2 boundary (ENGINEERING_BIBLE.md §11) is a
checklist, not prose. Corrected the moderation item: report *intake* on
ratings already ships (`POST /ratings/{id}/report`); what remains is the
review/action side. Added a Deployment Verification item — hosting is
decided and configured (ADR 0005) but a live deploy has not been confirmed.

---

## 0. Infra & Stack Decisions (prerequisite) 

***✅ COMPLETE***

**⛔ Plan-mode gate — research and get sign-off before writing code.**

- **Database / backend framework / frontend framework** — chosen for a
  solo builder using AI tooling, not a team.
- **Auth / identity provider** — hardest decision to walk back later
  (migrating auth = migrating every account), gets its own research pass.
- **Hosting / deploy platform** — doesn't block early feature work, but
  needs to be settled before anything in "Next" ships to real users.
- **Canonical music database** — the source the Music Catalog feature
  below is built on top of; chosen here, used everywhere downstream.

---

## NOW (build first — the core loop has to work end to end)

> Phase 1 (ENGINEERING_BIBLE.md §11) closes when every item below is
> shipped and the Public Alpha Criteria checklist at the bottom of this
> file is checked off. The **Shipped** items are done; the **Remaining**
> items are sequenced — do them in order, since later ones depend on
> earlier ones existing (Notifications is inert without Melody; the
> Visibility Audit needs Melody + Notifications as surfaces to check).

### Shipped

### ✅ Music Catalog
Searchable songs, albums, artists, and artwork, sourced from the canonical
music database chosen in infra planning.
*Security: music metadata is public information; only user-generated
interactions (ratings, listens, Melodies, playlists) require visibility
controls.*

### ✅ User accounts & profiles
Basic signup, login, profile page.
*Security: visibility of any profile field (history, ratings) defaults to
private until the user explicitly opens it up — opt-in, not opt-out.*

### ✅ Search (minimal)
Just enough to find a song to rate or a person to follow. Not unified,
not ranked — a real cross-entity search engine is a Next-tier feature.
*Security: search only returns what the requesting user is permitted to
see. Per ADR 0008 (2026-07-04), every profile is discoverable — search
exposes only identity-card fields (username, display name, avatar); it is
page content that is visibility-scoped.*

### ✅ Ratings & reviews
Rate and review songs/albums — the RateYourMusic backbone.
*Security: reviews are user-generated content tied to an identity; needs
basic abuse/report handling from day one, not bolted on later.*

### ✅ Follow / following
The social graph Melody and Harmony both depend on.
*Security: a follow request itself reveals nothing about the followed
user's activity — following ≠ automatic visibility into their data.*

### ✅ Home (minimal entry layer)
Trending (global) + top songs from people you follow. Two sources, no
more. Built here, before Melody, because it's a read-only aggregation
over data that already exists once ratings and follows are in place.
*Security: "top songs from friends" can only pull from listens/ratings
the friend has marked visible to followers — never a backend join that
ignores their visibility setting.*

### ✅ Spotify integration (supplementary) — account linking + listening display
*Pulled forward from NEXT by Founder decision, 2026-07-04, to populate the
profile's listening section (see specs/phase-1-spotify-listening.md).
Scope here is account linking, "currently playing," and recently-played
display only — starter-library import stays in NEXT.*
*Security/compliance: nothing from this integration may be used to train
or inform the recommendation layer — a Spotify ToS constraint, not just a
privacy one. Also capped at 5 dev-mode users until extended access is
granted.*

### Remaining

Items 1–3 below are shipped, tested, and documented (specs now exist at
the paths noted). Items 4–5 are what's left before the Public Alpha gate
closes.

#### 1. Melody (core flow: send, receive, Accept, Open, Reject) — ✅ shipped
**Spec: `specs/phase-1-melody.md`**
The atomic social object — one song, one sender, one recipient. Ships as
a message-less interactive embed card (cover art, track, artist, sender
identity) per Founder decision 2026-07-07 — see
`docs/adr/0009-melody-no-message-embed-card.md`.
*Security: Reject is invisible to anyone but the sender, with zero
exceptions — verified in `test_melodies.py`.*

#### 2. Notifications — ✅ shipped
**Spec: `specs/phase-1-notifications.md`**
Minimal in-app notification center for Melodies and follows.
*Security: a notification never reveals activity the recipient wouldn't
otherwise have permission to see — verified in `test_notifications.py`.*

#### 3. Moderation — review & action — ✅ shipped
**Spec: `specs/phase-1-moderation.md`**
Report intake plus review/action: dismiss report, hide rating (soft),
suspend user. `CurrentModerator` 404s (not 403s) for non-moderators,
hiding the surface's existence.
*Security: `is_moderator` is granted only via manual SQL, never via API —
verified in `test_moderation.py`'s non-moderator 404 matrix.*

#### 4. Visibility Audit (Tier 2 — run as a full Security Audit, `WORKFLOW.md` §2.5)
Confirm every visibility scope end to end with a non-owner test account,
across every surface that now exists (profile fields, ratings, Melody
inbox, notifications). Do this after items 1–3, once Melody, Notifications,
and Moderation all exist to test against — ROADMAP's Public Alpha Criteria
calls this out as "confirmed working end to end — not assumed, checked."

#### 5. Deployment Verification (Tier 2)
ADR 0005 is accepted and `Procfile` / `railway.json` exist, but a live
Vercel + Railway deployment has not been confirmed end to end. Smoke-test
prod (sign-in, one full rating round-trip, one Melody round-trip) before
calling "stable deployment" done.

---

## Phase 1 → Phase 2 boundary

Phase 2 (below, "NEXT") does not start on any individual feature until
**all five Remaining items above are done** and the Public Alpha Criteria
checklist is fully checked. This is a hard gate, not a soft preference —
Harmony v1 explicitly builds on Melody's acceptance data, so starting it
early would mean building on an unstable foundation.

---

## NEXT (soon after the core loop is live — Phase 2)

### Harmony v1
Acceptance rate + reception signal, profile-level display only.
*Security: computed from a user's own Melody history — no cross-user
data gets exposed in the calculation itself.*

### Demo + Open (Melody enhancement)
Preview a song before accepting the recommendation.
*Security: preview playback shouldn't log as a "listen" in the
recipient's public history unless they actually accept.*

### Global Search (full)
Upgrade from minimal search to unified, ranked search across people,
songs, artists, and albums.
*Security: same permission rules as minimal search, now enforced across
a much larger result surface — worth a dedicated pass rather than
assuming the minimal version's rules just scale.*

### Discovery layer
Browsing surface: listening-history-based and playlist-based suggestions,
plus "what trusted connections are listening to."
*Security: the first feature that reads across multiple users' data at
once — visibility flags need to be enforced at the query level here, not
just at the profile-page level.*

### Spotify starter-library import
Account linking and listening display moved to NOW (Founder decision,
2026-07-04). What remains here is the optional starter-library import.
*Security/compliance: nothing from this integration may be used to train
or inform the recommendation layer — a Spotify ToS constraint, not just a
privacy one. Also capped at 5 dev-mode users until extended access is
granted.*

---

## LATER (deliberately deferred)

### AI-driven recommendation layer
**⛔ Plan-mode gate — this changes how user data is used, per CLAUDE.md.**
Built only from data collected in "Now"/"Next" (ratings, reviews, follows,
listens) — never from Spotify content or metadata.
*Security: needs its own data-handling review before build, since it
aggregates across the whole user base rather than one relationship at a
time.*

### Harmony v2 (customization)
Custom themes, theme song, featured recent activity.
*Security: each new visible field needs the same opt-in-by-default
treatment as the original profile fields.*

### Expanded Discovery sources
Deeper playlist-based recs, broader "trusted connections" signal.
*Security: same query-level enforcement requirement as Discovery v1, just
against more data sources.*

---

## Public Alpha Criteria

What Phase 1 needs to deliver before opening the product to outside
testers — the checklist form of the NOW tier above.

- [x] Account creation
- [x] Music catalog
- [x] Search (minimal)
- [x] Ratings & reviews
- [x] Following
- [x] Home
- [x] Spotify integration (account linking + listening display)
- [x] Melody
- [x] Notifications
- [x] Moderation review & action
- [ ] Deployment verified live (Vercel + Railway configured; not yet
      smoke-tested end to end in production)
- [ ] Visibility defaults from every item above confirmed working end to end
      — not assumed, checked.

---

## Notes

Visibility rules are product rules, not UI rules. Every query that reads
user-generated data must enforce visibility at the data-access layer,
regardless of which feature initiated the request. That's the one thing
worth re-checking every time this list changes.
