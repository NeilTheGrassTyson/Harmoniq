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

  const { userId, sessionClaims } = await auth();

  // Authenticated users who haven't completed onboarding are gated to
  // /onboarding. The `onboarded` flag is set in Clerk's publicMetadata when
  // the Harmoniq user record is created. The Clerk session token must be
  // customized with `"metadata": "{{user.public_metadata}}"` — NO spaces
  // inside the braces; the spaced form is passed through as a literal
  // string, not interpolated. Configure it in: Clerk Dashboard → Configure
  // → Sessions → Customize session token. See docs/setup.md §5.
  if (userId) {
    // Trust the claim only when it interpolated into a real object. When it
    // is absent or a leftover "{{ … }}" string (dashboard misconfiguration),
    // skip the gate: bouncing every signed-in user through /onboarding
    // forever is a far worse failure than not gating a brand-new account.
    const rawMetadata: unknown = sessionClaims?.metadata;
    const metadata =
      typeof rawMetadata === "object" && rawMetadata !== null
        ? (rawMetadata as Record<string, unknown>)
        : undefined;
    const claimAvailable = metadata !== undefined;
    const isOnboarded = metadata?.onboarded === true;
    const pathname = request.nextUrl.pathname;

    // Only gate private routes on the onboarded flag. Public browse routes
    // (/, /u/*, /artist/*, /spotify-callback, etc.) are readable before
    // onboarding completes — this also avoids a JWT-propagation race after
    // the onboarding form submits, and keeps the onboarding redirect from
    // bouncing the OAuth return and burning the single-use code.
    if (
      claimAvailable &&
      !isOnboarded &&
      !pathname.startsWith("/onboarding") &&
      !isPublicRoute(request)
    ) {
      return NextResponse.redirect(new URL("/onboarding", request.url));
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
