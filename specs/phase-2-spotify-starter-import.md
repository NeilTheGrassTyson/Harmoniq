# Spotify Starter Import — A Head Start, Chosen by You

> **Status: APPROVED by the Founder, 2026-09-28.** Tier 1 per WORKFLOW.md §1
> (changes how user data is collected; widens the Spotify grant). Not yet
> implemented. Drafted 2026-09-28 from the ROADMAP NEXT item "Spotify
> starter-library import"; all open questions resolved in the Founder's review
> the same day. Its review-nudge idea became an addition to
> `specs/phase-2-highlights.md`.

---

# Purpose

A new Harmoniq profile starts empty. Someone who has years of listening in
Spotify has to rebuild their taste here by hand, one highlight and one rating
at a time — which is slow enough that many won't.

A starter import shows a new user what Spotify knows they love — their top
artists and tracks — and lets them *pick* what to bring across. Nothing is
added on their behalf.

**Principle strengthened: Musical Identity.** It shortens the distance between
having a taste and expressing it here.

---

# The decision this spec rests on

Harmoniq has no "library". So "import a starter library" has to become
something that already exists — and whatever it becomes must not be
auto-populated:

- **Highlights** are public by default under a constitutional exception that
  holds *only* because nothing is auto-populated
  (`specs/phase-2-highlights.md`). An import that created highlights would
  trip that exception's reevaluation condition.
- **Ratings** are a person's judgement; importing them would fabricate scores.

So this draft proposes an **import as suggestions**: a one-time picker that
lists the user's Spotify top artists and tracks, already resolved to Harmoniq
catalog pages, from which they highlight (one at a time, as elsewhere) or
visit and rate. The import writes nothing to their profile by itself.

---

# Scope

### In Scope

- A "Start from Spotify" picker, offered to users with Spotify connected — on
  their own empty Highlights section and in settings.
- Reading the user's top artists and top tracks from Spotify.
- Resolving them to catalog entities via ISRC / MusicBrainz (the same path
  listen history uses to link plays).
- Highlight and "open" actions per suggestion.

### Out of Scope

- Creating any highlight, rating, follow or listen automatically.
- Saved-library ("Liked Songs") import. Top items are enough for a start and
  need a narrower grant.
- Storing the imported lists. They are fetched when the picker opens and
  discarded.
- Using imported data for recommendation — prohibited (Spotify ToS; CLAUDE.md).

---

# Consent

- Top items need Spotify's `user-top-read` scope, a further widening of the
  grant. ROADMAP records that whichever of this and playlist highlights ships
  first owns the re-consent flow — playlist highlights shipped it (the
  picker's "Allow access" through Spotify's consent screen), so this reuses
  it: the scope is requested only while `STARTER_IMPORT_ENABLED` is on, access
  is read from the scope Spotify reports granting, and declining changes
  nothing else.
- Nothing is visible to anyone until the user chooses a highlight — at which
  point the usual highlight rules apply.

---

# User Experience

- **Entry point:** on your own empty Highlights section, "Start from your
  Spotify favourites", and in Settings under Spotify.
- **Core flow:** one button opens a picker of suggestions — top artists and
  top tracks — each with art, a link to its Harmoniq page, and two choices:
  **Add** (to highlights) or **Ignore**.
- **Unresolvable items:** shown without a Highlight button and a quiet
  "Not in the Harmoniq catalog yet".
- **Empty:** "Spotify doesn't have enough listening to suggest from yet."
- **Needs permission:** the same "Allow access" flow as playlists.

---

# Functional Requirements

1. `GET /import/spotify/suggestions` (owner only) returns top artists and
   tracks, each resolved to a catalog MBID where possible.
2. Resolution uses ISRC (tracks) and name + MusicBrainz lookup (artists),
   bounded per request so the shared 1 req/s MusicBrainz limit isn't swamped;
   items that can't be resolved in time are shown unresolved.
3. Nothing is written except through the existing highlight endpoint when the
   user presses Highlight.
4. The scope is requested only while the feature is on.
5. The fetched lists are not persisted.

---

# Acceptance Criteria

- [ ] A connected user sees their Spotify top artists and tracks, resolved to
      Harmoniq pages where possible.
- [ ] Opening the picker writes nothing — verified by test.
- [ ] Highlighting from it creates exactly one highlight per press, and
      respects the 15 cap.
- [ ] Declining the widened grant leaves listening and playlists working.
- [ ] No imported item is stored or used for recommendation.

---

# Design Requirements

BRAND_BIBLE §7–8: an invitation, not a setup wizard. It must never imply a
profile is incomplete without it, and must not pre-select anything.

---

# Technical Notes

- Spotify endpoints: top artists and top tracks for the current user (verify
  availability for development-mode apps before build).
- Reuses `app/services/listens.py`'s ISRC → catalog linking and the playlist
  re-consent flow in `PlaylistPicker`.
- New scope constant beside `PLAYLIST_SCOPE` in `app/services/spotify.py`.

---

# Rollback Plan

`STARTER_IMPORT_ENABLED`, default off. Off hides the entry points and stops
requesting the scope. Nothing is stored, so nothing to preserve.

---

# Open Questions

_All resolved in the Founder's review, 2026-09-28._

1. ~~**Is "import as suggestions" what you meant by a starter library?**~~
   **RESOLVED 2026-09-28 — yes.** A user with Spotify connected gets a quick
   way to populate their profile with highlights drawn from their streaming
   data, choosing each one themselves.
2. ~~**Top items, saved tracks, or both?**~~ **RESOLVED 2026-09-28 — top items
   only.** Saved tracks stay out of scope, keeping the narrower
   `user-top-read` grant.
3. ~~**Should suggestions include "rate this"?**~~ **RESOLVED 2026-09-28 —
   the idea moves to Highlights instead.** The picker stays highlight-only;
   any highlight without a review, whether added here or by hand, gets an
   owner-only nudge to review it. Specified in `specs/phase-2-highlights.md`,
   "Addition 2026-09-28: review nudge".
4. ~~**Verify before build**~~ **RESEARCHED 2026-09-28 — should work.** No
   Spotify change (Nov 2024; Feb–Mar 2026) lists `GET /me/top/{artists,tracks}`
   as removed — "not removed" by absence from those lists, from search
   snippets because the session's network policy blocked the pages. Since Feb
   2026 a development-mode app needs its owner on Spotify Premium (existing
   apps grandfathered), so the owner account must keep Premium active. Quota
   is per developer account and shared across its apps (429
   `QUOTA_EXCEEDED` when exceeded): the picker makes two calls per open, with
   no retry loop. Use `time_range=medium_term`, 20 of each. Still unconfirmed:
   whether `limit` still allows 50 and whether fields such as genres survived
   2026 — neither is needed. The first real call against the Founder's account
   settles it before build.
   Sources: developer.spotify.com/blog/2024-11-27-changes-to-the-web-api,
   developer.spotify.com/blog/2026-02-06-update-on-developer-access-and-platform-security,
   developer.spotify.com/blog/2026-07-23-web-api-quota-updates,
   github.com/ramsayleung/rspotify/issues/550.
5. ~~**How quick is "quick"?**~~ **RESOLVED 2026-09-28 — one button opens a
   series of suggestions, each with Add or Ignore.** Nothing is pre-selected
   and nothing is written until the user presses Add; they are suggestions,
   never de facto writes. Ignore only hides a suggestion in the open picker
   and isn't stored (the fetched lists are never persisted), so it may
   reappear next time.
