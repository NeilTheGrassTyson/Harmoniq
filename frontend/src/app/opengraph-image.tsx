import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

// The card every shared Harmoniq link previews with. Worth building on a
// product whose central mechanic is sending someone a link: without this,
// every Melody pasted into a chat arrived as a bare URL.
//
// A Next metadata file convention — placing it in src/app/ is the whole
// wiring. Do not add <meta property="og:image"> by hand.

export const alt = "Harmoniq — a social music network built around trust and musical identity.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpengraphImage() {
  // Space Grotesk as font bytes, not as the webfont next/font serves: satori
  // needs a ttf/otf it can parse at build time, and the next/font cache is
  // woff2, which it does not accept. process.cwd() is the Next project root.
  // The file is a build input only — see docs/BRAND_ASSETS.md §2.
  const spaceGroteskMedium = await readFile(
    join(process.cwd(), "public/brand/fonts/SpaceGrotesk-Medium.ttf")
  );

  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        // The canvas token's value. Not var(--color-canvas): satori resolves
        // no cascade, and this renders outside the document entirely.
        background: "#0b0d12",
      }}
    >
      {/* The lockup at card scale — the word, then the octave beneath it,
            matched to the word's width the same way Wordmark does it. */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
        <div
          style={{
            fontFamily: "Space Grotesk",
            fontSize: 128,
            fontWeight: 500,
            letterSpacing: "-0.02em",
            color: "#f2f3f5",
            lineHeight: 1,
          }}
        >
          harmoniq
        </div>
        {/* Two waves an octave apart, as in OctaveMark: a fundamental of one
              period across the frame and an overtone at twice the frequency,
              meeting it at every node. */}
        <svg width="620" height="46" viewBox="0 0 400 40" fill="none" style={{ marginTop: 14 }}>
          <path
            d="M 4 20 Q 53 0 102 20 T 200 20 T 298 20 T 396 20"
            stroke="#19d8ff"
            strokeWidth={5}
            strokeLinecap="round"
          />
          <path
            d="M 4 20 Q 28.5 8 53 20 T 102 20 T 151 20 T 200 20 T 249 20 T 298 20 T 347 20 T 396 20"
            stroke="#19d8ff"
            strokeWidth={3.5}
            strokeLinecap="round"
            opacity={0.45}
          />
        </svg>
      </div>

      <div
        style={{
          fontFamily: "Space Grotesk",
          fontSize: 27,
          color: "#8b93a3",
          marginTop: 52,
        }}
      >
        Music discovery through people you trust
      </div>
    </div>,
    {
      ...size,
      fonts: [
        {
          name: "Space Grotesk",
          data: spaceGroteskMedium,
          style: "normal",
          weight: 500,
        },
      ],
    }
  );
}
