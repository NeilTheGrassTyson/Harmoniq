# Third-Party Song Access from Harmoniq

> **Status: APPROVED — Founder decision 4, 2026-09-08.**
> Founder request: offer an add-to-playlist / liked-songs action where feasible;
> a direct route to the item in the streaming app is an acceptable baseline.
> Six-service links and optional Spotify saving are approved under WORKFLOW.md
> §1. Saving remains contingent on verified write capability; links are the
> accepted baseline without additional account consent or test credentials.

## Purpose

Let someone act on a human recommendation in their own music service, without
turning Harmoniq into a streaming platform. This strengthens Discovery Through
People (HARMONIQ.md §2; BRAND_BIBLE.md §3 and §14).

## Scope

### In scope

- A compact “Listen on” area on track pages, reachable from every Melody.
- Direct song URLs for Spotify, Apple Music, YouTube Music, TIDAL, Deezer,
  and Amazon Music when a reliable mapping exists.
- Clearly labeled provider searches when the exact track is not mapped;
  never present a search URL as a confirmed song match.
- Make the already-returned Spotify URL actionable on visible listening rows.
- An optional Spotify save-to-liked-songs and owned-playlist picker, only
  after explicit additional account consent and verified write capability.
  The link route remains usable if these actions are unavailable.

### Out of scope

- New paid provider enrollment, purchases, subscriptions, or playback SDKs.
- Apple/Google/TIDAL/Deezer/Amazon account linking and write integrations in
  this first slice. Their links are the baseline accepted in the request.
- Playlist import/sync, new playlists, bulk writes, and silently choosing a
  destination playlist. No changes to existing listening-data retention.
- Audio downloads, scraped previews, proxy streaming, recommendation training,
  autoplay, or claims that opening a link proves the song was played.

## User experience

On a track page, a keyboard-accessible list shows the available services.
An exact match says “Open in Spotify” (or the service name). When no exact
mapping exists, a separate “Search Spotify” option makes the fallback clear.
Provider pages may open the installed app through the provider's supported
HTTPS route, or remain in the browser. Harmoniq must not promise app launch.

Links require no Harmoniq account. No external service is contacted by the
browser merely because the buttons render. Loading or failure of mappings
does not delay ratings, the track heading, or sending a Melody.

For Spotify saves, the signed-in user chooses either Liked Songs or a specific
owned playlist. Existing listening-only connections are retained; additional
permission is requested explicitly when the user chooses to enable saving.
Canceling consent leaves the original connection usable. Show a confirmed
success only after the provider confirms it. On failure, retain the song link
and explain what can be retried or needs reconnecting.

## Functional requirements

1. MusicBrainz remains canonical. Resolve public streaming relationships
   through the backend's existing MusicBrainz adapter and rate limiter. A
   recording relationship is a song link; an album/release URL is not a song
   match. Validate every returned relationship and permitted provider path.
2. If a provider mapping is absent or ambiguous, use an explicitly labeled
   title/artist search. Do not invent IDs or choose a version from fuzzy title
   similarity alone. Missing, malformed, and upstream-error states differ.
3. Only allow HTTPS URLs on exact recognized provider hosts, with expected
   song paths/IDs. Reject userinfo, custom ports, executable schemes, IP
   literals, lookalike hosts, protocol-relative URLs, and unsafe redirects.
   Never fetch an arbitrary user-supplied URL to resolve a song.
4. Build fallback URLs with URL/query encoding. Outgoing anchors use safe
   opener and referrer handling. No Harmoniq username, token, playlist name,
   private history, or Melody ID enters a public resolver request or link.
5. Cache public mapping data with bounds and expiry, coalesce duplicate
   requests, and use a short timeout. Errors must not become permanent
   negative mappings. Separate the mapping endpoint from catalog detail so
   an upstream lookup cannot make an otherwise cached track page unavailable.
6. Spotify save endpoints require the current active user and that user's
   existing encrypted connection, correct granted scopes, a validated exact
   track ID, rate limiting, and an explicit action. Never accept a user ID or
   raw access token from the client as authority.
7. List only playlists the authenticated Spotify account owns in this slice.
   Paginate rather than silently cutting the list off. Recheck ownership at
   write time; following or reading a playlist does not authorize writing it.
8. Keep access tokens, playlist payloads, and save responses private and
   non-cacheable. Keep the existing disconnect cleanup semantics. Do not
   persist library contents or use them as Harmony input.
9. Disable repeated clicks while a mutation is pending. Library saving is
   idempotent; playlist appends are not. Do not automatically retry an append
   after a timeout of unknown outcome. Report uncertainty honestly.
10. Provider 401/403/429/5xx, revoked consent, partial scopes, missing tracks,
    and expired tokens must preserve normal Harmoniq functionality and the
    direct link fallback. Do not broaden scopes on ordinary listening refresh.

## Acceptance criteria

- [ ] Exact links and labeled search fallbacks render correctly for all six
      proposed providers, including punctuation and non-Latin titles.
- [ ] A track lacking relations remains rateable/shareable; resolver failure
      never breaks its main page or Melody inbox.
- [ ] Safe-URL tests reject hostile host/path/scheme combinations.
- [ ] Spotify links on listening rows remain subject to the existing
      server-enforced activity visibility.
- [ ] Spotify saving, if included, passes account isolation, consent upgrade,
      revoked-token, ownership, pagination, duplicate-click, and uncertain
      outcome tests against mocked provider contracts and a disposable DB.
- [ ] Real-account Spotify write validation uses a designated test account
      and test playlist; if unavailable, saving is not described as verified.
- [ ] Browser tests cover desktop/mobile, keyboard use, new-tab behavior,
      exact vs search labeling, loading/failure, and navigation from Melody.
- [ ] Full backend and frontend gates pass and existing social flows remain
      covered. Provider read-only smoke checks are recorded separately.

## Design requirements

Use the current buttons, spacing, typography, focus styles, and restrained
copy (BRAND_BIBLE.md §7–§10). Service names identify destinations. No default
provider preference is inferred from listening history. Avoid service logos
unless their current branding requirements are satisfied.

## Technical notes and verified provider constraints

- MusicBrainz supports recording-to-URL streaming relationships and API
  relationship includes. Reuse this public catalog source before adding a
  separate commercial matching service. Mapping coverage is not universal.
  Sources: [recording streaming relationship](https://musicbrainz.org/relationship/b5f3058a-666c-406f-aafb-f9249fc7b122),
  [MusicBrainz API](https://musicbrainz.org/doc/MusicBrainz_API).
- Spotify's current library save route is `PUT /me/library`; track saves need
  `user-library-modify`. Playlist append is `POST /playlists/{id}/items`,
  with the appropriate private/public playlist-modification scope. Listing
  private playlists requires its read scope. The existing five-user
  development limit and app-owner Premium requirement apply.
  Sources: [library save](https://developer.spotify.com/documentation/web-api/reference/save-library-items),
  [playlist append](https://developer.spotify.com/documentation/web-api/reference/add-items-to-playlist),
  [playlist listing](https://developer.spotify.com/documentation/web-api/reference/get-a-list-of-current-users-playlists),
  [2026 migration guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide).
- Apple supports library/playlist actions through MusicKit with developer
  credentials and user authorization. This is a separate integration, not a
  universal write URL. Sources: [MusicKit](https://developer.apple.com/musickit/),
  [user authentication](https://developer.apple.com/documentation/applemusicapi/user-authentication-for-musickit).
- YouTube playlist writes require OAuth and consume API quota; YouTube Data
  API support is not evidence of full YouTube Music feature parity.
  Source: [playlistItems.insert](https://developers.google.com/youtube/v3/docs/playlistItems/insert).
- Do not infer write support for the remaining services from the existence of
  a public song URL. Additional integrations need their own verified scope.

## Rollback plan

Independent switches for streaming links and Spotify saves. Disabling saving
leaves current Spotify listening connections intact. Disabling links restores
the current track layout. Do not downgrade away existing connection data.
Explain that a successful external playlist/library write is external state:
rolling back Harmoniq code does not undo that user's explicit save.

## Founder decision and external verification dependency

1. Six-service coverage with exact-link/search distinction and optional Spotify
   saving approved. Ship links independently of account-write verification.
2. A designated, allowlisted Spotify test account and owned test playlist are
   needed before claiming live save/playlist functionality is verified. No
   account credentials or user playlists have been accessed or modified.

The end-to-end and rollout plan is in `docs/reviews/phase-2-v1-test-plan.md`.
