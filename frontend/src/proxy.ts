import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isPublicRoute = createRouteMatcher([
  "/",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/sso-callback(.*)",
  // Spotify OAuth return. Public because Spotify redirects to the loopback
  // IP literal (127.0.0.1) where no Clerk dev session exists — the page
  // forwards itself to localhost and only then performs the authed exchange
  // (the backend requires auth + a user-bound signed state regardless).
  "/spotify-callback(.*)",
  // Catalog pages — publicly readable
  "/artist/(.*)",
  "/album/(.*)",
  "/track/(.*)",
  // Profile pages — publicly readable
  "/u/(.*)",
]);

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// True/false when the backend answered definitively, null when it couldn't
// (no token, network failure, 5xx, rate limit) so the caller can fail open.
async function harmoniqAccountExists(token: string | null): Promise<boolean | null> {
  if (!token) return null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/users/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (res.ok) return true;
    if (res.status === 403 || res.status === 404) return false;
    return null;
  } catch {
    return null;
  }
}

export default clerkMiddleware(async (auth, request) => {
  // Requests on the 127.0.0.1 origin (Spotify's OAuth return target) are
  // bounced to localhost here, as a tiny HTML page that client-side
  // replaces the location. A redirect response can't do it — Next
  // relativizes same-origin Location headers, which loops against the
  // browser's 127.0.0.1 origin — and an inline <script> in the root layout
  // triggers React 19 script-in-component warnings on every page. The
  // /spotify-callback page keeps its own client-side bounce as a fallback.
  // Checked via the raw Host header — Next normalizes nextUrl.hostname in
  // dev, so it never reads "127.0.0.1" even when the browser is there.
  const host = request.headers.get("host") ?? "";
  if (host.startsWith("127.0.0.1")) {
    const target = `http://localhost${host.slice("127.0.0.1".length)}${request.nextUrl.pathname}${request.nextUrl.search}`;
    return new NextResponse(
      `<!doctype html><meta charset="utf-8"><script>location.replace(${JSON.stringify(target)})</script>`,
      { headers: { "content-type": "text/html; charset=utf-8" } }
    );
  }

  const { userId, sessionClaims, getToken } = await auth();

  // Authenticated users who haven't completed onboarding are gated to
  // /onboarding. The `onboarded` flag is set in Clerk's publicMetadata when
  // the Harmoniq user record is created. The Clerk session token must be
  // customized with `"metadata": "{{user.public_metadata}}"` — NO spaces
  // inside the braces; the spaced form is passed through as a literal
  // string, not interpolated. Configure it in: Clerk Dashboard → Configure
  // → Sessions → Customize session token. See docs/setup.md §5.
  if (userId) {
    const rawMetadata: unknown = sessionClaims?.metadata;
    const metadata =
      typeof rawMetadata === "object" && rawMetadata !== null
        ? (rawMetadata as Record<string, unknown>)
        : undefined;
    const isOnboarded = metadata?.onboarded === true;
    const pathname = request.nextUrl.pathname;
    const onOnboardingRoute = pathname.startsWith("/onboarding");

    if (isOnboarded) {
      // A completed account never sees the onboarding form again.
      if (onOnboardingRoute) {
        return NextResponse.redirect(new URL("/", request.url));
      }
    } else if (onOnboardingRoute || !isPublicRoute(request)) {
      // The claim is false, absent, or a leftover "{{ … }}" string
      // (dashboard misconfiguration) — but it can also simply be stale for
      // a short window right after onboarding, before the JWT refreshes.
      // The backend user record is the source of truth, so ask it before
      // redirecting either way. Public browse routes (/, /u/*, /artist/*,
      // /spotify-callback, etc.) stay readable before onboarding completes,
      // which also keeps the onboarding redirect from bouncing the OAuth
      // return and burning the single-use code.
      const accountExists = await harmoniqAccountExists(await getToken().catch(() => null));

      if (accountExists === true && onOnboardingRoute) {
        return NextResponse.redirect(new URL("/", request.url));
      }
      if (accountExists === false && !onOnboardingRoute) {
        return NextResponse.redirect(new URL("/onboarding", request.url));
      }
      // accountExists === null (backend unreachable / indeterminate): fail
      // open. Bouncing every signed-in user through /onboarding forever is
      // a far worse failure than not gating a brand-new account.
    }
  }

  if (!isPublicRoute(request)) {
    await auth.protect();
  }
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
