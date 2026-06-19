import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isPublicRoute = createRouteMatcher([
  "/",
  "/sign-in(.*)",
  "/sign-up(.*)",
  // Catalog pages — publicly readable
  "/artist/(.*)",
  "/album/(.*)",
  "/track/(.*)",
  // Profile pages — publicly readable
  "/u/(.*)",
]);

export default clerkMiddleware(async (auth, request) => {
  const { userId, sessionClaims } = await auth();

  // Authenticated users who haven't completed onboarding are gated to
  // /onboarding. The `onboarded` flag is set in Clerk's publicMetadata when
  // the Harmoniq user record is created. The Clerk JWT template must include
  // `"metadata": "{{ user.public_metadata }}"` for this check to work.
  // Configure it in: Clerk Dashboard → Configure → Sessions → Customize session token.
  if (userId) {
    const metadata = sessionClaims?.metadata as
      | Record<string, unknown>
      | undefined;
    const isOnboarded = metadata?.onboarded === true;
    const pathname = request.nextUrl.pathname;

    if (!isOnboarded && !pathname.startsWith("/onboarding")) {
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
