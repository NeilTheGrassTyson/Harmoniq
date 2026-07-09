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
checklist, not prose. Corrected the moderation item: report _intake_ on
ratings already ships (`POST /ratings/{id}/report`); what remains is the
review/action side. Added a Deployment Verification item — hosting is
decided and configured (ADR 0005) but a live deploy has not been confirmed.

---

## 0. Infra & Stack Decisions (prerequisite)

_**✅ COMPLETE**_

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
_Security: music metadata is public information; only user-generated
interactions (ratings, listens, Melodies, playlists) require visibility
controls._

### ✅ User accounts & profiles

Basic signup, login, profile page.
_Security: visibility of any profile field (history, ratings) defaults to
private until the user explicitly opens it up — opt-in, not opt-out._

### ✅ Search (minimal)

Just enough to find a song to rate or a person to follow. Not unified,
not ranked — a real cross-entity search engine is a Next-tier feature.
_Security: search only returns what the requesting user is permitted to
see. Per ADR 0008 (2026-07-04), every profile is discoverable — search
exposes only identity-card fields (username, display name, avatar); it is
page content that is visibility-scoped._

### ✅ Ratings & reviews

Rate and review songs/albums — the RateYourMusic backbone.
_Security: reviews are user-generated content tied to an identity; needs
basic abuse/report handling from day one, not bolted on later._

### ✅ Follow / following

The social graph Melody and Harmony both depend on.
_Security: a follow request itself reveals nothing about the followed
user's activity — following ≠ automatic visibility into their data._

### ✅ Home (minimal entry layer)

Trending (global) + top songs from people you follow. Two sources, no
more. Built here, before Melody, because it's a read-only aggregation
over data that already exists once ratings and follows are in place.
_Security: "top songs from friends" can only pull from listens/ratings
the friend has marked visible to followers — never a backend join that
ignores their visibility setting._

### ✅ Spotify integration (supplementary) — account linking + listening display

_Pulled forward from NEXT by Founder decision, 2026-07-04, to populate the
profile's listening section (see specs/phase-1-spotify-listening.md).
Scope here is account linking, "currently playing," and recently-played
display only — starter-library import stays in NEXT._
_Security/compliance: nothing from this integration may be used to train
or inform the recommendation layer — a Spotify ToS constraint, not just a
privacy one. Also capped at 5 dev-mode users until extended access is
granted._

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
_Security: Reject is invisible to anyone but the sender, with zero
exceptions — verified in `test_melodies.py`._

#### 2. Notifications — ✅ shipped

**Spec: `specs/phase-1-notifications.md`**
Minimal in-app notification center for Melodies and follows.
_Security: a notification never reveals activity the recipient wouldn't
otherwise have permission to see — verified in `test_notifications.py`._

#### 3. Moderation — review & action — ✅ shipped

**Spec: `specs/phase-1-moderation.md`**
Report intake plus review/action: dismiss report, hide rating (soft),
suspend user. `CurrentModerator` 404s (not 403s) for non-moderators,
hiding the surface's existence.
_Security: `is_moderator` is granted only via manual SQL, never via API —
verified in `test_moderation.py`'s non-moderator 404 matrix._

#### 4. Visibility Audit (Tier 2 — run as a full Security Audit, `WORKFLOW.md` §2.5) — ✅ shipped

Completed 2026-07-09 against the live production deploy, across anonymous,
authenticated-non-owner, and structural tiers — see
`docs/reviews/visibility-audit-live-2026-07-09.md` for method, results
matrix, and the one (non-visibility) robustness finding it produced. The
friends-scope admittance branch is covered by the integration suite rather
than live mutation of production accounts.

#### 5. Deployment Verification (Tier 2) — ✅ shipped

ADR 0005 is accepted; production Vercel + Railway + Neon confirmed live
end to end 2026-07-08 (fresh signup → onboarding → profile). Founder
decision: deploy directly to production for this closed friends-test round
rather than standing up the documented `staging` Neon branch first — a
`staging` branch remains the plan for the next environment tier once
outside (non-friend) testers are in scope. Real-world round-trip smoke
tests (rating, Melody, follow notification) are still pending against the
live URL — tracked as part of item 4's Visibility Audit, since both need
a second live test account. See `docs/deployment.md` Troubleshooting for
config gotchas hit during the first live deploy.

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
_Security: computed from a user's own Melody history — no cross-user
data gets exposed in the calculation itself._

### Demo + Open (Melody enhancement)

Preview a song before accepting the recommendation.
_Security: preview playback shouldn't log as a "listen" in the
recipient's public history unless they actually accept._

### Global Search (full)

Upgrade from minimal search to unified, ranked search across people,
songs, artists, and albums.
_Security: same permission rules as minimal search, now enforced across
a much larger result surface — worth a dedicated pass rather than
assuming the minimal version's rules just scale._

### Discovery layer

Browsing surface: listening-history-based and playlist-based suggestions,
plus "what trusted connections are listening to."
_Security: the first feature that reads across multiple users' data at
once — visibility flags need to be enforced at the query level here, not
just at the profile-page level._

### Spotify starter-library import

Account linking and listening display moved to NOW (Founder decision,
2026-07-04). What remains here is the optional starter-library import.
_Security/compliance: nothing from this integration may be used to train
or inform the recommendation layer — a Spotify ToS constraint, not just a
privacy one. Also capped at 5 dev-mode users until extended access is
granted._

---

## LATER (deliberately deferred)

### AI-driven recommendation layer

**⛔ Plan-mode gate — this changes how user data is used, per CLAUDE.md.**
Built only from data collected in "Now"/"Next" (ratings, reviews, follows,
listens) — never from Spotify content or metadata.
_Security: needs its own data-handling review before build, since it
aggregates across the whole user base rather than one relationship at a
time._

### Harmony v2 (customization)

Custom themes, theme song, featured recent activity.
_Security: each new visible field needs the same opt-in-by-default
treatment as the original profile fields._

### Expanded Discovery sources

Deeper playlist-based recs, broader "trusted connections" signal.
_Security: same query-level enforcement requirement as Discovery v1, just
against more data sources._

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
- [x] Deployment verified live — production Vercel (`harmoniq-two.vercel.app`)
      + Railway (`harmoniq-production-ac1f.up.railway.app`) + Neon confirmed
      end to end 2026-07-08 (fresh signup → onboarding → live profile). See
      `docs/deployment.md`'s Troubleshooting section for the real gotchas
      hit getting here — none were code bugs, all were environment config.
- [x] Visibility defaults from every item above confirmed working end to end
      — not assumed, checked. Live-deploy audit completed 2026-07-09 across
      anonymous, authenticated-non-owner, and structural tiers:
      `docs/reviews/visibility-audit-live-2026-07-09.md`. One adjacent
      robustness bug found and fixed (malformed `TOKEN_ENCRYPTION_KEY`
      500'd the listening endpoint instead of degrading gracefully).

---

## Operational TODOs before inviting friends

Not feature gaps — scope/ops decisions the Founder made 2026-07-08 that
still need follow-through before invites go out. Not part of the five-item
Phase 1 → Phase 2 gate above; these are invite-readiness, not build-phase.

- **Seed data** — Founder decision: pre-seed rather than rely on cold
  on-demand ingestion. Script exists: `backend/scripts/seed_catalog.py`
  (~100 present-day + ~200 all-time artists, full discographies, via the
  normal ingestion path — idempotent, per-artist retries, smoke-tested
  locally 2026-07-09; see docs/setup.md "Seeding the catalog"). Remaining:
  run it once against the **production** DB before invites
  (`DATABASE_URL=<prod pooled string> poetry run python
  scripts/seed_catalog.py` from `backend/` — expect ~30-60 min at
  MusicBrainz's 1 req/s limit).
- **Spotify integration — stays in scope.** Founder decision: friends use
  different streaming services and may write their own provider
  integrations later, so Spotify linking should keep working for whoever
  does use it. Dev-mode 5-user cap applies — each friend's Spotify account
  email needs manual allowlisting in the Spotify Developer Dashboard before
  they can connect.
- **Moderator grant — TBD.** No username chosen yet. Grant via the manual
  SQL in `docs/setup.md`'s "Granting moderator access" section once
  decided; don't grant beyond the Founder without re-reading
  `specs/phase-1-moderation.md`'s Known Limitations (no unsuspend/appeal
  flow yet).

---

## Notes

Visibility rules are product rules, not UI rules. Every query that reads
user-generated data must enforce visibility at the data-access layer,
regardless of which feature initiated the request. That's the one thing
worth re-checking every time this list changes.
