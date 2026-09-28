# Spotify Starter Import — A Head Start, Chosen by You

> **Status: DRAFT — awaiting Founder approval.** Tier 1 per WORKFLOW.md §1
> (changes how user data is collected; widens the Spotify grant). Nothing here
> is implemented. Drafted 2026-09-28 from the ROADMAP NEXT item "Spotify
> starter-library import".

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
- **Core flow:** a picker with two short lists — top artists, top tracks —
  each with art and a Highlight button, and a link to the Harmoniq page.
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

_Founder decides._

1. ~~**Is "import as suggestions" what you meant by a starter library?**~~
   **RESOLVED 2026-09-28 — yes.** A user with Spotify connected gets a quick
   way to populate their profile with highlights drawn from their streaming
   data, choosing each one themselves.
2. **Top items, saved tracks, or both?** Top items are a better "this is me"
   signal and a narrower grant; saved tracks are larger and noisier.
3. **Should suggestions include "rate this"** as well as highlight, or stay
   highlight-only to keep the picker light?
4. **Verify before build:** that the top-items endpoints work for a
   development-mode app under the 5-user cap.
5. **How quick is "quick"?** Raised by the answer to question 1. One tap per
   suggestion is the draft. The faster option: tick several suggestions, then
   one "Add to highlights". Each remains the user's explicit choice and
   nothing is pre-ticked, so the "nothing auto-populated" exception holds; the
   15 cap applies to the batch. Recommended: allow ticking several.
