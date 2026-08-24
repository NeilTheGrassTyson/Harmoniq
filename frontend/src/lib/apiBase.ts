/**
 * The backend origin, and the error helpers that go with talking to it.
 *
 * `NEXT_PUBLIC_API_URL` is inlined at build time, so a production build made
 * without it silently bakes in the localhost fallback and every browser call
 * fails as an opaque network error. This module is the one place that can
 * notice, so it says so once, loudly, in the console.
 */

const configured = process.env.NEXT_PUBLIC_API_URL;

export const API_BASE = configured ?? "http://localhost:8000";

/** True when this is a browser on something other than a local dev origin. */
function isDeployedBrowser(): boolean {
  if (typeof window === "undefined") return false;
  const { hostname } = window.location;
  return hostname !== "localhost" && hostname !== "127.0.0.1";
}

if (!configured && isDeployedBrowser()) {
  console.error(
    "[Harmoniq] NEXT_PUBLIC_API_URL is not set, so API calls are going to " +
      `${API_BASE}, which is unreachable from this page. Set it in the Vercel ` +
      "project's environment variables and trigger a new build — the value is " +
      "inlined at build time, so redeploying an existing build will not pick it up."
  );
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
