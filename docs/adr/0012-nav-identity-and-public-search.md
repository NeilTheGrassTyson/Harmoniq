# ADR 0012 — The Nav Is Server-Resolved, and Search Is a Browse Surface

**Date:** 2026-08-29
**Status:** Accepted
**Deciders:** Founder

---

## Context

A frontend audit of `harmoniq.live` on 2026-08-29 started from a report of
"issues with routes" and found that production had been effectively down for
days. `NEXT_PUBLIC_API_URL` in the Vercel project was set to the Vercel
deployment-inspector URL — `https://vercel.com/<team>/<project>/<id>` — rather
than the Railway origin. Every path under it answers `404 text/html`, so every
API call failed, and the catalog pages translated that 404 into `notFound()`.
Radiohead's artist page, present in the backend, rendered "Nothing here."

That is the fourth incident of the shape ADR 0011 was written for, and it
slipped past ADR 0011's guard: the guard fires when the variable is **unset**,
and here it was set to the wrong thing. Set-and-wrong fails identically to
unset — every request resolves, answers 404, and the UI reports it as missing
content rather than as an outage.

Underneath the outage the audit found four bugs that were not caused by it,
three of which are about routing identity:

1. **The sidebar Profile link was built from Clerk's username.** Profiles are
   keyed by the _Harmoniq_ username, chosen at onboarding and editable later.
   The backend writes only `publicMetadata.onboarded` back to Clerk
   (`backend/app/api/v1/users.py`), never the handle, so the two diverge for
   anyone who picked something different — or who renamed themselves, since
   `ProfileHeader` correctly navigates to the new URL while the sidebar keeps
   pointing at the old one. The link led to a dead route, or to whoever had
   since claimed the freed handle. For a Clerk account with no username it
   disappeared entirely.
2. **Every page load shipped signed-out chrome.** `AppShell` derived both
   "am I signed in" and "what is my username" from `useUser()`, which is only
   populated after hydration. The server HTML for an authenticated `/melodies`
   request contained only Home, Search and Settings, and no notification bell.
3. **Typing in search pushed a history entry per debounce tick.** Three query
   refinements added three entries; Back walked the query backwards a few
   characters at a time instead of leaving the page. The header input also
   restored from the URL only at mount, so a history move left the field
   showing text the address bar no longer agreed with.
4. **Several surfaces reported a failed request as good news** — Home said
   "No songs are trending yet", the notification panel said "Nothing new", and
   Settings showed the inbound-Melody scope as **everyone**, the most
   permissive value, when it had failed to load the real one.

`/search` was also the only browse surface behind the auth gate, while
`/artist`, `/album`, `/track` and `/u` were public — so a shared
`/search?q=…` link bounced a logged-out visitor to sign-in.

## Decision

**1. The nav's identity comes from the server, and the username it uses is the
Harmoniq one.**

`lib/viewer.ts` resolves `{ signedIn, username }` in the root layout — deduped
per render with React `cache()` — and `ViewerProvider` carries it to the client
chrome. `AppShell`, `NavAuth` and `NotificationBell` read that instead of
Clerk. There is exactly one source of truth for the handle: the backend record
the `/u/` routes are keyed by.

Reading the username from the session token would cost nothing per request, and
was rejected: it means a second copy in Clerk that a failed rename can leave
stale, which is the bug being fixed.

**2. A resolution failure hides the Profile link rather than guessing.** The
lookup is bounded at 2.5s — shorter than the app-wide 10s, because chrome must
never be what holds a page up — and a timeout or error yields a null username.
Hiding the link is honest; linking somewhere wrong is not.

**3. `/search` is a public route.** It is a browse surface, like the catalog
and profile pages already are, and the backend already serves both search
endpoints without auth. **Settings**, an account page, is no longer offered in
the nav to signed-out visitors.

**4. A query refinement replaces the URL; it does not push it.** `/search` is
one destination whose parameters change, not a new destination per keystroke.
The field is seeded from `?q=` and adopts later URL changes it did not itself
write, so Back and Forward keep the input and the address bar agreeing.

**5. No surface reports an unanswered request as an answer.** Extending ADR
0011's user-facing rule from error _messages_ to empty _states_: "no results",
"nothing new" and "no songs yet" are claims about the world, and may only be
made once the server has actually answered. This binds hardest on consent —
the inbound-Melody scope now shows no value until the real one loads, because
displaying `everyone` was telling someone they had opened their inbox to
everybody when nobody had asked them (HARMONIQ.md §6).

**6. ADR 0011's config guard extends to values that are set and wrong.**
`lib/apiBase.ts` now rejects a configured `NEXT_PUBLIC_API_URL` that carries a
path, ends in a slash, points at `vercel.com`, or matches the page's own
origin — and names the resolved value on every deployed load, not only when it
looks wrong.

**7. The same rule applies to `CLERK_JWKS_URL`.** Correcting the API URL
uncovered a second variable failing the same way: it pointed at a different
Clerk instance, so the fetch succeeded, the JWKS parsed, and every
authenticated request returned `401 "JWT key not found"` while public pages
browsed normally. The backend now logs the resolved JWKS URL and the Clerk
secret key's *mode* (never the key) on boot, warns when either is a
development instance under `APP_ENV=production`, and names the unrecognised
`kid` next to the ones it holds. The JWKS cache also gained a TTL and a
single rate-limited re-fetch on an unknown `kid`, so a genuine Clerk key
rotation heals itself — it was previously cached for the process lifetime,
which made rotation an outage lasting until somebody restarted the service.

## Rationale

- **Identity Before Engagement** (HARMONIQ.md §1). A profile URL is the most
  basic expression of identity the product has. Deriving it from an unsynced
  copy in a third-party auth provider meant a user's own handle could stop
  pointing at them.
- **Consent Before Visibility** (§6). Rendering the most permissive Melody
  scope as a fallback is a statement about someone's consent that nobody made.
  The default when the answer is unknown must be no answer, never the most open
  one.
- **Design Is a Feature** (§8). Chrome that changes shape a beat after every
  navigation is not calm, and a Back button that takes six presses to leave a
  page is not either.
- **Quality Before Speed** (§3). The `getViewer` round trip is a real per-render
  cost, accepted to keep one source of truth for the username. If it is ever
  measured to matter, that is a later optimisation with data behind it — not a
  reason to reintroduce a second copy now.
- **Simplicity Before Complexity** (§4). One resolver, one provider, one
  context read. Each is a sentence.

## Consequences

- **Every route is now server-rendered on demand.** The root layout calls
  `auth()`, so `/_not-found` and the auth pages are no longer statically
  generated and the 404 page is no longer edge-cacheable. Every other route
  already returned `Cache-Control: private, no-cache, no-store`, so this is a
  change for the 404 and sign-in pages only.
- **One additional backend request per render for signed-in viewers**, deduped
  across the tree by `cache()` and bounded at 2.5s.
- Any new client component needing "who is looking" reads `useViewer()`.
  `useUser()` / `useAuth()` in the chrome is now a regression, and
  `AppShell.test.tsx` fails loudly if it reappears.
- `authedGet` in `lib/users.ts` accepts an optional `AbortSignal`; callers that
  pass none are unchanged.
- The JWKS is re-fetched at most once an hour per process, plus at most once a
  minute when an unknown `kid` arrives. `_fetch_jwks` is module state rather
  than an `lru_cache`, so tests reset it directly
  (`backend/tests/unit/test_auth_jwks.py`).
- **Soft 404s were investigated and deliberately left alone.** `notFound()` on
  `/artist/[mbid]`, `/album/[mbid]`, `/track/[mbid]` and `/u/[username]`
  returns HTTP 200, because each route has a `loading.tsx` and the response has
  already begun streaming when the status would be set. Next's documentation
  covers this case directly: it injects `<meta name="robots" content="noindex">`
  into the streamed HTML, which is present on these routes and is what prevents
  indexation. Recovering the status code would mean dropping the loading
  skeletons or adding a backend existence check to the proxy on every catalog
  view. Neither is worth a status code that already carries `noindex`.
