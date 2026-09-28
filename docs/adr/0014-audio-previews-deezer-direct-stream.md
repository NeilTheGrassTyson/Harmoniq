# ADR 0014 — Audio Previews Come from Deezer and Stream Straight from Its CDN

**Date:** 2026-09-28
**Status:** Accepted for now. The Founder expects to revisit it as Harmoniq
grows; see "When to revisit".
**Deciders:** Founder

---

## Context

`specs/phase-2-demo-and-open.md` adds 30-second previews to Melody cards, the
Melodies page, track pages and album tracklists. That raises two questions:
where the audio comes from, and how it reaches the listener.

**Source.** Spotify stopped returning `preview_url` to apps created after
27 November 2024, so our Spotify app can't supply previews. Deezer's public
API returns a 30-second preview URL per track without a user login, and can
look tracks up by ISRC. Apple's iTunes Search API also has keyless previews,
but its terms allow them only to promote store purchases: a store badge
beside the clip, "provided courtesy of iTunes", and no standalone
entertainment use. That doesn't fit a Melody card.

**Delivery.** ENGINEERING_BIBLE §7 says the frontend never talks to external
music providers directly. There are two ways to deliver the audio:

- **Direct.** The backend resolves a preview URL and the browser's `<audio>`
  element fetches the file from Deezer's CDN.
- **Proxied.** The backend fetches the audio and relays it to the browser.

Research for this decision came from search results; the session's network
policy blocked opening Deezer's and Spotify's pages directly. Deezer's terms
must be read at the source before build (see "Conditions").

## Decision

1. **Deezer is the preview source.** The backend resolves a track's ISRC
   (via MusicBrainz) to a Deezer track and its preview URL. It falls back to
   an artist + title search when the ISRC doesn't match.
2. **Audio streams directly from Deezer's CDN to the browser.** The backend
   hands out a fresh, short-lived URL per play and never stores or relays
   the audio.
3. **This reading of ENGINEERING_BIBLE §7 is explicit.** The frontend still
   never calls a provider's API, holds a provider token, or decides what to
   fetch. It only plays a media URL the backend chose, the same way it loads
   Cover Art Archive images today. Any call to Deezer's API stays on the
   backend.

## Tradeoffs

| | Direct from Deezer's CDN (chosen) | Proxied through our backend |
| --- | --- | --- |
| Complexity | An `<audio>` tag and one backend lookup | A streaming endpoint with range requests, timeouts and back-pressure |
| Cost | No audio bandwidth on Railway | Every second of preview audio passes through Railway |
| Latency | Deezer's CDN, close to the listener | An extra hop through one region |
| Privacy | The listener's IP address and user agent reach Deezer's CDN when they press play | Only our backend talks to Deezer |
| ENGINEERING_BIBLE §7 | Relies on the reading above | Satisfies the strictest reading |
| Deezer's terms | Streams without storing, which is what third-party summaries say the terms want | Relaying may count as redistribution; unclear |
| Failure | A dead URL fails in the browser; the card stays usable | We own retries and error mapping |

## Conditions

- **Deezer's terms are read at the source before build**, covering
  commercial use, caching and attribution.
- **A small, visible Deezer mark sits by the play control**, as Deezer's logo
  guidelines require. It stays quiet, per BRAND_BIBLE §7–8.
- **Nothing reaches Deezer until the user presses play.** The request carries
  no referrer (`referrerpolicy="no-referrer"`), so Deezer's CDN never learns
  which Harmoniq page or profile the listener was on.
- **The content security policy lists Deezer's audio host by name** under
  `media-src`, not a wildcard.

## When to revisit

Any one of these reopens the decision:

- Deezer changes its terms, withdraws public previews, or starts requiring an
  app key. New app registration has been paused since at least 2024.
- Harmoniq starts earning money. Third-party summaries say previews are for
  non-commercial use.
- The privacy cost of the listener's IP reaching Deezer is judged too high,
  for instance if previews become a large share of what people do here.
  Proxying is the answer to that.
- A licensed source becomes available, such as extended Spotify access or a
  catalogue deal.
- The ISRC match rate on our catalog turns out too low to be worth the
  feature.

## Consequences

- One new outbound dependency on the backend (Deezer's API), and one on the
  browser (Deezer's audio CDN).
- Previews can be turned off entirely with `PREVIEWS_ENABLED`. Nothing is
  stored, so switching sources later touches one service module and the CSP
  entry.
