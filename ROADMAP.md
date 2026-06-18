# ROADMAP.md
## Harmoniq — Dev Roadmap (v0.3)

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

---

## 0. Infra & Stack Decisions (prerequisite)
**⛔ Plan-mode gate — research and get sign-off before writing code.**

- **Database / backend framework / frontend framework** — chosen for a
  solo builder using AI tooling, not a team.
- **Auth / identity provider** — hardest decision to walk back later
  (migrating auth = migrating every account), gets its own research pass.
- **Hosting / deploy platform** — doesn't block early feature work, but
  needs to be settled before anything in "Next" ships to real users.
- **Canonical music database** — the source the Music Catalog feature
  below is built on top of; chosen here, used everywhere downstream.

## ✅ COMPELTE

---

## NOW (build first — the core loop has to work end to end)

### Music Catalog
Searchable songs, albums, artists, and artwork, sourced from the canonical
music database chosen in infra planning.
*Security: music metadata is public information; only user-generated
interactions (ratings, listens, Melodies, playlists) require visibility
controls.*

### User accounts & profiles
Basic signup, login, profile page.
*Security: visibility of any profile field (history, ratings) defaults to
private until the user explicitly opens it up — opt-in, not opt-out.*

### Search (minimal)
Just enough to find a song to rate or a person to follow. Not unified,
not ranked — a real cross-entity search engine is a Next-tier feature.
*Security: search only returns what the requesting user is permitted to
see — private profiles stay undiscoverable even by exact-name search.*

### Ratings & reviews
Rate and review songs/albums — the RateYourMusic backbone.
*Security: reviews are user-generated content tied to an identity; needs
basic abuse/report handling from day one, not bolted on later.*

### Follow / following
The social graph Melody and Harmony both depend on.
*Security: a follow request itself reveals nothing about the followed
user's activity — following ≠ automatic visibility into their data.*

### Home (minimal entry layer)
Trending (global) + top songs from people you follow. Two sources, no
more. Built here, before Melody, because it's a read-only aggregation
over data that already exists once ratings and follows are in place.
*Security: "top songs from friends" can only pull from listens/ratings
the friend has marked visible to followers — never a backend join that
ignores their visibility setting.*

### Melody (core flow: send, receive, Open, Reject)
The atomic social object — one song, one sender, one recipient. The
riskiest, most novel mechanic in the product, which is why it's still
built early even though Home ships first. Demo + Open preview can wait;
Open/Reject is the minimum to test whether the mechanic works.
*Security: Reject must be invisible to anyone but the sender, with zero
exceptions — this is a brand requirement that's also a privacy guarantee.*

### Notifications
Minimal in-app notification center for Melodies and follows. Without
this, Melody has no way of actually reaching anyone.
*Security: a notification must never reveal activity the recipient
wouldn't otherwise have permission to see — the notification itself is
subject to the same visibility rules as the data it references.*

---

## NEXT (soon after the core loop is live)

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

### Spotify integration (supplementary)
Account linking, "currently playing," optional starter-library import.
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

What "Now" needs to deliver before opening the product to outside testers:

- Account creation
- Music catalog
- Search (minimal)
- Ratings & reviews
- Following
- Home
- Melody
- Notifications
- Basic moderation / reporting on user-generated content
- Stable deployment
- Visibility defaults from every item above confirmed working end to end
  — not assumed, checked.

---

## Notes

Visibility rules are product rules, not UI rules. Every query that reads
user-generated data must enforce visibility at the data-access layer,
regardless of which feature initiated the request. That's the one thing
worth re-checking every time this list changes.
