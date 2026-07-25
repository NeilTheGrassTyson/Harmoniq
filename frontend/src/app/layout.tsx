import type { Metadata } from "next";
import { Space_Grotesk } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { SpeedInsights } from "@vercel/speed-insights/next";
import QueryProvider from "@/components/QueryProvider";
import "./globals.css";

// No Geist/Inter here deliberately: the body face is the system font stack
// and the display face is Space Grotesk (DESIGN_SYSTEM.md §3, §9).
const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Harmoniq",
  description: "A social music discovery network built around trust and musical identity.",
};

// The 127.0.0.1 → localhost bounce (Spotify OAuth return, Clerk dev-session
// origin mismatch) lives in proxy.ts as an HTML response — any script tag
// rendered from a React component triggers React 19 dev warnings.

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en" className={`${spaceGrotesk.variable} h-full`}>
        <body className="bg-canvas text-primary h-full antialiased">
          <QueryProvider>{children}</QueryProvider>
          {/* Anonymous Core Web Vitals only — no identity, no behaviour
              tracking. Inert outside Vercel, so local dev sends nothing. */}
          <SpeedInsights />
        </body>
      </html>
    </ClerkProvider>
  );
}
