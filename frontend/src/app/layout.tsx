import type { Metadata } from "next";
import { Space_Grotesk, Space_Mono } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { Analytics } from "@vercel/analytics/next";
import { SpeedInsights } from "@vercel/speed-insights/next";
import QueryProvider from "@/components/QueryProvider";
import { ViewerProvider } from "@/components/ViewerProvider";
import { getViewer } from "@/lib/viewer";
import { clerkAppearance } from "@/lib/clerkAppearance";
import "./globals.css";

// No Geist/Inter here deliberately: the body face is the system font stack
// and the display face is Space Grotesk (DESIGN_SYSTEM.md §3, §9).
const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
  weight: ["400", "500"],
});

// Label face: section labels, strand labels, timestamps (DESIGN_SYSTEM.md §3).
// Space Grotesk was derived from Space Mono — both Colophon — so this is the
// wordmark's own sibling rather than a third voice.
const spaceMono = Space_Mono({
  variable: "--font-space-mono",
  subsets: ["latin"],
  weight: ["400", "700"],
});

export const metadata: Metadata = {
  // The origin og:image and twitter:image are resolved against. Unset, Next
  // falls back to VERCEL_PROJECT_PRODUCTION_URL — the *.vercel.app name, not
  // the custom domain — and to http://localhost:3000 anywhere that variable
  // is absent, with only a build-log warning to show for it. A wrong value is
  // invisible from inside the app and only surfaces in someone else's chat
  // window, which is ADR 0011's class of bug.
  //
  // Hardcoded rather than read from an env var: an unset variable would
  // reintroduce exactly the silent fallback this line exists to close.
  // Vercel preview deployments still override it with their own URL (Next
  // prefers VERCEL_BRANCH_URL when VERCEL_ENV is "preview"), so a preview's
  // card is its own, and dev always resolves to localhost by design.
  metadataBase: new URL("https://harmoniq.live"),
  title: "Harmoniq",
  description: "A social music discovery network built around trust and musical identity.",
};

// The 127.0.0.1 → localhost bounce (Spotify OAuth return, Clerk dev-session
// origin mismatch) lives in proxy.ts as an HTML response — any script tag
// rendered from a React component triggers React 19 dev warnings.

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Resolved here, once, so the nav's first paint already knows who is looking
  // and what their profile URL is — see ViewerProvider for what that fixes.
  const viewer = await getViewer();

  // appearance is set once here so every Clerk surface — the hosted
  // sign-in/sign-up pages, the <SignInButton> modal, and <UserButton> —
  // picks up Harmoniq's tokens without per-call-site theming.
  return (
    <ClerkProvider appearance={clerkAppearance}>
      <html lang="en" className={`${spaceGrotesk.variable} ${spaceMono.variable} h-full`}>
        <body className="bg-canvas text-primary h-full antialiased">
          <ViewerProvider value={viewer}>
            <QueryProvider>{children}</QueryProvider>
          </ViewerProvider>
          <Analytics />
          {/* Core Web Vitals only, and a route pattern rather than a URL:
              the /next entrypoint templatises dynamic segments before
              reporting, so a profile visit is recorded as "/u/[username]",
              never as the username itself, and query strings are never sent.
              Inert outside Vercel, so local dev reports nothing. */}
          <SpeedInsights />
        </body>
      </html>
    </ClerkProvider>
  );
}
