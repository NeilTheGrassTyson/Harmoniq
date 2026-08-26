# ADR 0011 — Configuration That Can Break Every Request Must Say So

**Date:** 2026-08-22
**Status:** Accepted
**Deciders:** Founder

---

## Context

A third person invited to try Harmoniq could not create an account. On
`/onboarding` he saw "Couldn't check that username. You can continue — we'll
confirm it when you finish.", and then a bare **"Load failed"** when he
pressed Continue. Search was broken on the same domain at the same time.

Neither message was about his username. Both requests — the unauthenticated
`GET /check-username` and the authenticated `POST /users/` — failed at the
network layer. `harmoniq.live` had been added to Vercel as a custom domain
but never added to the backend's `CORS_ALLOWED_ORIGINS`, so `CORSMiddleware`
rejected every browser request from it.

That rejection is invisible from both ends:

- **Server-side**, nothing is logged. `CORSMiddleware` answers normally and
  simply omits the `access-control-allow-origin` header. The response is a
  200. Railway's logs show a healthy service.
- **Client-side**, the browser discards the response and throws a bare
  `TypeError` — `"Load failed"` in Safari, `"Failed to fetch"` in Chrome —
  with nothing in the console explaining why.
- **Server-rendered pages keep working**, because server-side requests carry
  no `Origin` and are not subject to CORS at all. The site looks alive while
  every interactive feature is dead.

This is the third session lost to this class of failure. `docs/deployment.md`
already recorded two: a trailing slash in the same variable (2026-07-08), and
a placeholder `CLERK_JWKS_URL` whose 500 lost its CORS headers and surfaced as
the same opaque `TypeError`. Each time the code was correct and the
environment was wrong, and each time the diagnosis started from a user report
of an unrelated-looking symptom.

## Decision

**A configuration value that can silently break every browser request must
log when it rejects one.**

Concretely:

1. `OriginAuditMiddleware` (`app/core/cors.py`) sits outside `CORSMiddleware`
   and logs one warning per distinct rejected origin, naming that origin and
   the configured allow-list. It must be outermost: `CORSMiddleware` answers
   `OPTIONS` preflights itself without ever calling the app, so a middleware
   registered inside it never sees a rejected authenticated request.
2. On startup the backend logs the resolved allow-list and the resolved
   `APP_ENV`, and warns when the two contradict each other: `APP_ENV=production`
   with an allow-list of only development origins, or `APP_ENV=development` with
   an allow-list of only remote `https://` origins. The second direction matters
   because `APP_ENV` has a default, so an **unset** variable is indistinguishable
   from a deliberate `development` — and it boots cleanly while serving `/docs`
   and `/redoc` publicly and echoing every SQL statement to the logs. A
   developer's machine always needs a localhost origin, so an allow-list without
   one is a deployed service whose `APP_ENV` went missing.
3. The frontend logs an error when `NEXT_PUBLIC_API_URL` is unset and the page
   is not on localhost — the mirror-image failure, where the build inlines the
   localhost fallback and nothing is reachable.

And the corresponding user-facing rule:

4. **A raw `fetch` rejection is never shown to a user.** `friendlyError()`
   (`lib/apiBase.ts`) maps an error with no `status` to "Couldn't reach
   Harmoniq. Check your connection and try again." Errors that carry a
   `status` came from the server, whose `detail` messages are already written
   for users, and pass through unchanged.

## Rationale

- **Security Is Foundational / Consent Before Visibility** (HARMONIQ.md §5,
  §6) mean the origin allow-list stays strict. This ADR does not loosen it —
  the middleware only observes; `CORSMiddleware` still decides. Nothing about
  what is permitted changes.
- **Quality Before Speed** (§3). The alternative — remembering to check the
  variable — has now failed three times. A log line costs nothing per request
  and turns a multi-session hunt into a five-minute fix.
- **Design Is a Feature** (§8). "Load failed" is not a message; it is an
  implementation detail leaking through a form. The person on the other end
  was trying to join, and what he had to work with was a stray Safari string
  and a guess that his name was taken.
- **Simplicity Before Complexity** (§4). One pass-through middleware and one
  error-mapping function, each explicable in a sentence. No retry logic, no
  fallback origin handling, no attempt to recover automatically from a
  misconfiguration — just make it visible and let the operator fix it.

## Consequences

- Rejected origins are logged once each, capped at 20 distinct values, so an
  unauthenticated caller cycling the `Origin` header cannot flood the log or
  grow the dedupe set without bound.
- The audit reads `settings.cors_origins_list` per request rather than
  snapshotting it, so it cannot drift from what `CORSMiddleware` was given.
- Errors thrown by the API helpers now carry a meaningful contract: `status`
  present means the server answered, absent means it was never reached. Any
  new helper that builds an error from a response must attach `status`, or
  its failures will be reported to users as connection problems.
- The resolved `APP_ENV` is logged on every boot, not only when it looks
  wrong. Absence was invisible precisely because nothing ever named the value;
  a line in Railway's Deploy Logs is what makes "it was never set" checkable
  without reproducing a user-facing symptom first.
- Timeouts (10s) were added to the onboarding calls. Previously a hung backend
  left Continue reading "Creating account…" indefinitely; an aborted request
  now lands in the same network-error path.
