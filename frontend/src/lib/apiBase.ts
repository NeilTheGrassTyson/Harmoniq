/**
 * The backend origin, and the error helpers that go with talking to it.
 *
 * `NEXT_PUBLIC_API_URL` is inlined at build time, so a production build made
 * without it — or with the wrong value in it — silently sends every request
 * somewhere unreachable, and the pages report that as missing content rather
 * than as an outage. This module is the one place that can notice, so it says
 * so once, loudly, in the console. See ADR 0011 and ADR 0012.
 */

const configured = process.env.NEXT_PUBLIC_API_URL;

export const API_BASE = configured ?? "http://localhost:8000";

/** True when this is a browser on something other than a local dev origin. */
function isDeployedBrowser(): boolean {
  if (typeof window === "undefined") return false;
  const { hostname } = window.location;
  return hostname !== "localhost" && hostname !== "127.0.0.1";
}

/**
 * Why a configured `NEXT_PUBLIC_API_URL` cannot be the backend's origin, or
 * null when nothing is obviously wrong with it.
 *
 * ADR 0011 made an *unset* variable observable. It could not catch a variable
 * that is set to the wrong thing, which fails identically: every request
 * resolves, answers 404 or refuses, and the pages translate that into "Nothing
 * here." Three of the four recorded incidents were of that shape — a trailing
 * slash, a placeholder, and (2026-08-29) the Vercel deployment-inspector URL
 * pasted in place of the Railway origin, which took production down for days
 * while the site looked alive.
 *
 * The checks are deliberately about *shape*, not reachability: this module has
 * no business making a network request, and a value that cannot possibly be an
 * API origin is worth naming before anything is attempted.
 */
export function misconfigurationReason(value: string): string | null {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return "it is not an absolute URL";
  }

  if (url.protocol !== "https:" && url.protocol !== "http:") {
    return `its scheme is "${url.protocol}" rather than http/https`;
  }
  if (url.hostname === "vercel.com" || url.hostname.endsWith(".vercel.com")) {
    // The dashboard URL for a deployment looks plausible and is one copy away
    // from the deploy screen. It serves 404 HTML for every /api/v1 path.
    return "vercel.com is the Vercel dashboard, not an API origin";
  }
  if (value.endsWith("/")) {
    // Every helper builds `${API_BASE}/api/v1/…`, so a trailing slash produces
    // a double slash the backend answers with a redirect or a 404.
    return "it ends in a slash — the value must be a bare origin";
  }
  if (url.pathname !== "/") {
    return `it carries a path ("${url.pathname}") — the value must be a bare origin`;
  }
  if (url.search || url.hash) {
    return "it carries a query string or fragment";
  }
  if (typeof window !== "undefined" && url.origin === window.location.origin) {
    return "it points back at this site, which does not serve the API";
  }
  return null;
}

const CONFIG_HINT =
  "Set it in the Vercel project's environment variables and trigger a new " +
  "build — the value is inlined at build time, so redeploying an existing " +
  "build will not pick it up.";

if (isDeployedBrowser()) {
  if (!configured) {
    console.error(
      "[Harmoniq] NEXT_PUBLIC_API_URL is not set, so API calls are going to " +
        `${API_BASE}, which is unreachable from this page. ${CONFIG_HINT}`
    );
  } else {
    const reason = misconfigurationReason(configured);
    if (reason) {
      console.error(
        `[Harmoniq] NEXT_PUBLIC_API_URL is "${configured}", which cannot be ` +
          `the backend: ${reason}. Every API call from this page will fail, ` +
          `and pages will report it as missing content. ${CONFIG_HINT}`
      );
    } else {
      // Named on every deployed load, not only when it looks wrong. ADR 0011:
      // a value nothing ever prints is a value nobody can check without first
      // reproducing a user-facing symptom.
      console.info(`[Harmoniq] API base: ${API_BASE}`);
    }
  }
}

/**
 * True when a request never got a response at all — offline, DNS failure, a
 * CORS rejection, or an aborted timeout.
 *
 * The API helpers attach `status` to every error built from an HTTP response,
 * so its absence is what distinguishes "the server said no" from "the server
 * was never reached".
 */
export function isNetworkError(err: unknown): boolean {
  return !(typeof err === "object" && err !== null && "status" in err);
}

/** The HTTP status an error came from, or undefined if it never got a response. */
export function errorStatus(err: unknown): number | undefined {
  if (typeof err === "object" && err !== null && "status" in err) {
    const { status } = err as { status: unknown };
    return typeof status === "number" ? status : undefined;
  }
  return undefined;
}

/**
 * True when the failure is the backend's, not the caller's — either it never
 * answered at all (no status) or it answered 5xx.
 *
 * Pages use this to tell "Harmoniq is unreachable" apart from a genuine 404
 * and from an unexpected error worth surfacing through the error boundary.
 */
export function isUpstreamFailure(err: unknown): boolean {
  const status = errorStatus(err);
  return status === undefined || status >= 500;
}

/**
 * A message safe to show a user.
 *
 * Never surface a raw `fetch` rejection: Safari's reads "Load failed" and
 * Chrome's "Failed to fetch", neither of which means anything to the person
 * reading it. Server-sent `detail` messages are already written for users
 * ("That username is taken.") and pass through unchanged.
 *
 * `fallback` is the caller's own copy for an error carrying no usable message
 * — it should say what didn't happen ("Couldn't delete. Try again."), which a
 * generic string can't.
 */
export function friendlyError(err: unknown, fallback?: string): string {
  if (isNetworkError(err)) {
    return "Couldn't reach Harmoniq. Check your connection and try again.";
  }
  const message = err instanceof Error ? err.message : "";
  return message || fallback || "Something went wrong. Please try again.";
}

/** How long to wait for the backend before treating a request as failed. */
export const REQUEST_TIMEOUT_MS = 10_000;
