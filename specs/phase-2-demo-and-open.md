# Demo + Open — Hear a Melody Before Answering It

> **Status: APPROVED by the Founder, 2026-09-28.** Tier 1 per WORKFLOW.md §1
> (net-new, user-facing feature; adds an external audio source). Not yet
> implemented. Drafted 2026-09-28 from the ROADMAP NEXT item "Demo + Open
> (Melody enhancement)"; all open questions resolved in the Founder's review
> the same day.
>
> **Implementation starts with "Required research before build" below.** The
> Founder was explicit: those steps are requirements, not suggestions. No
> implementation code is written until every one is done and its findings are
> recorded in this spec.

---

# Purpose

A Melody is one song from one person. Today its recipient can take it, open
it (go to the track page and on to a streaming service), or pass. What they
can't do is *hear* it where the gesture arrives, so answering honestly means
leaving Harmoniq first.

A short preview on the Melody card lets someone listen, then answer. The
Melody stays the gesture; the preview just lets the recipient meet it.

**Principle strengthened: Discovery Through People.** The recommendation came
from a person; this lets the recipient actually receive it.

---

# Scope

### In Scope

- A short audio preview on a received Melody card, in the inbox, where one
  exists for that track.
- A play button on every Melody on the Melodies page, received and sent, so a
  user can go back to an earlier Melody and hear its preview again (Founder
  review, 2026-09-28).
- Previews on track pages, and per track in an album page's tracklist. This
  also lets a sender check what they're about to send (Founder review,
  2026-09-28).
- Resolving a preview from a free, public preview source (see "Source").

### Out of Scope

- Full-length playback. Harmoniq is not a streaming platform
  (ENGINEERING_BIBLE §10).
- Recording a preview as a listen, or as an answer to the Melody (see the
  consent rule below).
- Previews anywhere else — Home, search, profiles, highlights. Those would be
  their own decision.
- Autoplay of any kind.

---

# The consent rule

From the roadmap: *preview playback shouldn't log as a "listen" in the
recipient's public history unless they actually accept.*

- Playing a preview writes nothing: no listen, no status change, no reaction,
  no notification, nothing the sender can see.
- The Melody's status still changes only through the recipient's explicit
  Take it / Listen / Pass and reactions (ENGINEERING_BIBLE §3, and
  `specs/phase-2-melody-reactions.md`: "Listening/opening and reacting are
  separate actions").
- A preview never counts toward Harmony.

---

# Source

Spotify withdrew 30-second preview clips from the Web API for new apps in
late 2024 (to verify before build — see Open Questions), so Harmoniq's
Spotify connection can't supply them. The candidate is **Deezer's public API**,
which offers 30-second previews without a user account and supports lookup by
ISRC (also to verify). `ARCHITECTURE.md` already names Deezer as the planned
preview source.

Resolution path, reusing what exists:

1. The track's MusicBrainz recording → its ISRC(s), via the existing
   rate-limited MusicBrainz client.
2. ISRC → Deezer track → preview URL.
3. Cached per track like the streaming links (`app/services/streaming.py`):
   bounded, with a timeout, failure isolated from the card.

Preview URLs from Deezer are signed and expire, so the backend should return
a fresh one per request rather than store it.

---

# User Experience

- **Entry point:** a received Melody in the inbox.
- **Core flow:** a small play control beside each playable track: on a
  Melody card next to its existing actions, on a track page, and on each row
  of an album's tracklist. Tap to hear 30 seconds; tap to stop.
- **No preview available:** the control simply isn't there. No "unavailable"
  message on every card.
- **Loading:** the control shows a quiet busy state; the card stays usable.
- **Error:** playback fails quietly back to the idle control.
- **Accessibility:** a real button with a label naming the track; keyboard
  operable; no autoplay; stops when the card leaves the screen or another
  preview starts.

---

# Functional Requirements

1. The Melodies page (inbox and sent), track pages and album tracklists can
   request a preview for a track by its MBID.
2. The backend resolves it (ISRC → Deezer) behind a timeout and a bounded
   cache, and returns either a playable URL or nothing.
3. Playing a preview makes no write of any kind.
4. Only one preview plays at a time across the page.
5. No preview request happens until the user presses play — nothing is
   fetched just because a card is on screen.
6. A preview failure never affects the Melody card or its actions.

---

# Acceptance Criteria

- [ ] A resolvable preview plays 30 seconds on demand from a received or sent
      Melody, a track page, and an album's tracklist.
- [ ] Playing it changes no status, reaction, listen, notification or Harmony
      value — verified by test.
- [ ] A Melody with no preview shows no control and no error.
- [ ] A slow or failing preview source leaves the inbox fully usable.
- [ ] No request to the preview source is made until play is pressed, so an
      album page makes no preview calls on load.
- [ ] Keyboard and screen-reader operable; never autoplays.

---

# Design Requirements

BRAND_BIBLE §7–8: calm, minimal. The play control is small and quiet, never
the loudest thing on the card — the Melody's sender and track are. No
waveform animation or progress spectacle; the existing `EqualizerGlyph` idle
state is the natural visual language if any is needed.

---

# Technical Notes

- New service module beside `app/services/streaming.py`, reusing its cache,
  timeout and failure-isolation pattern.
- MusicBrainz: recording lookup with `inc=isrcs` (existing client and 1 req/s
  limiter).
- New outbound host: the Deezer API, and its audio CDN for playback.
- **ENGINEERING_BIBLE §7 says the frontend never talks to external music
  providers directly.** Playing a CDN audio URL in an `<audio>` element is the
  browser fetching a file, like cover art from Cover Art Archive today — but
  it is a judgement call, so it's an open question below.

---

# Rollback Plan

`PREVIEWS_ENABLED`, default off. Off hides the control and the endpoint
returns 404. Nothing is stored, so there is nothing to preserve.

---

# Required research before build

_Founder direction, 2026-09-28: these are requirements, not suggestions._
Each step's findings are written into this spec (or ADR 0014, where noted)
before any implementation code. If a finding contradicts the approved
design, stop and bring it to the Founder rather than working around it.

1. **Read Deezer's developer terms in full**, at
   https://developers.deezer.com/termsofuse, plus its logo guidelines. The
   2026-09-28 review only saw excerpts, because the session's network policy
   blocked the page. Confirm: non-commercial use, no storage or downloads of
   audio, logo placement, rate limits, and anything on previews specifically.
   Update ADR 0014's Conditions with the confirmed wording.
2. **Research how comparable social music apps present previews**, starting
   with Airbuds. Record where their clips come from where that can be found,
   how long clips are, how attribution is shown, and how the app hands off to
   a full-length service. Record what Harmoniq adopts or deliberately doesn't.
3. **Measure the ISRC match rate** against Harmoniq's catalog: take a sample
   of catalog tracks, resolve each ISRC through Deezer, and record how many
   return a preview. Record the artist + title fallback's rate separately.
   ADR 0014 treats a low rate as a reason to revisit.
4. **Confirm the preview mechanics directly.** Check that Deezer's preview
   URLs are time-limited, that `/track/isrc:<ISRC>` behaves as described, and
   that Spotify returns no `preview_url` for this app.

---

# Open Questions

_All resolved in the Founder's review, 2026-09-28._

1. ~~**Is Deezer acceptable as a preview source?**~~ **RESOLVED — yes, for
   now**, under the conditions and revisit triggers in
   `docs/adr/0014-audio-previews-deezer-direct-stream.md`. Deezer's terms, from
   excerpts: free for non-commercial use only, no storage or downloads of
   audio, and a visible Deezer logo. Confirming them in full is required
   research step 1.
2. ~~**Should audio stream from the provider's CDN directly, or be proxied?**~~
   **RESOLVED — directly, for now**, recorded with its tradeoffs and revisit
   conditions in ADR 0014.
3. ~~**Verify before build.**~~ **Folded into "Required research before
   build"** (steps 1, 3 and 4). Spotify's withdrawal of previews for apps
   created after 27 November 2024 is confirmed by Spotify's announcement.
4. ~~**Should senders hear the preview too** (track page), or only
   recipients?~~ **RESOLVED — yes**, on the track page and from their sent
   Melodies.
