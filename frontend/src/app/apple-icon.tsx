import { ImageResponse } from "next/og";

// iOS home-screen icon. Generated at build time rather than committed as a
// binary: nothing in this repo's toolchain can rasterise an SVG, and Apple
// touch icons must be PNG (unlike icon.svg, which browsers accept as vector).
//
// iOS applies its own rounded-rect mask, so this is drawn square and opaque —
// a transparent icon renders black on the home screen.

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#05070a",
        }}
      >
        {/* Compact mark: fundamental only. The overtone is under a pixel at
            this size and reads as noise — see OctaveMark's `compact`. */}
        <svg width="140" height="140" viewBox="0 0 120 120" fill="none">
          <path
            d="M 12 60 Q 36 16 60 60 T 108 60"
            stroke="#19d8ff"
            strokeWidth="14"
            strokeLinecap="round"
          />
        </svg>
      </div>
    ),
    size,
  );
}
