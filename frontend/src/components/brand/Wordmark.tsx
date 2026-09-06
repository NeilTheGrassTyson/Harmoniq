interface WordmarkProps {
  /** Font size of the word in px; the wave scales from it. */
  size?: number;
  className?: string;
}

/**
 * The Harmoniq wordmark: the name in the display face with the octave wave
 * running beneath it, matched to the word's width.
 *
 * This is a component rather than an .svg asset on purpose. The wave is
 * geometry, but the word is live text in Space Grotesk — which next/font
 * already loads (layout.tsx). An .svg file would either depend on the font
 * being installed on the viewer's machine, or need the letterforms converted
 * to outlines, which no tooling in this repo can do. For anything leaving the
 * app (press, social, a partner's site), export a PNG or have the wordmark
 * outlined in a vector editor once — see docs/BRAND_ASSETS.md.
 *
 * Not yet wired into the app shell — see ADR 0013.
 */
export default function Wordmark({ size = 14, className = "" }: WordmarkProps) {
  // The wave sits under the word and inherits its width. It is absolutely
  // positioned so it contributes nothing to the container's intrinsic width —
  // a percentage-width SVG inside a shrink-to-fit box otherwise resolves
  // circularly and can snap to the viewBox width instead of the word's.
  const waveHeight = Math.max(3, Math.round(size * 0.36));

  // Four humps read as a wave at display sizes; below ~24px they collapse into
  // a fuzzy line, so the small lockup drops to two.
  const dense = size >= 24;

  return (
    <span className={`inline-block ${className}`}>
      <span
        className="font-display text-primary block leading-none font-medium select-none"
        style={{ fontSize: size, letterSpacing: "-0.02em" }}
      >
        harmoniq
      </span>
      <span className="relative block" style={{ height: waveHeight, marginTop: size * 0.06 }}>
        <svg
          viewBox="0 0 400 40"
          fill="none"
          preserveAspectRatio="none"
          className="absolute inset-0 block h-full w-full"
          aria-hidden="true"
        >
          {dense ? (
            <>
              <path
                d="M 4 20 Q 53 0 102 20 T 200 20 T 298 20 T 396 20"
                stroke="currentColor"
                strokeWidth={5}
                strokeLinecap="round"
              />
              <path
                d="M 4 20 Q 28.5 8 53 20 T 102 20 T 151 20 T 200 20 T 249 20 T 298 20 T 347 20 T 396 20"
                stroke="currentColor"
                strokeWidth={3.5}
                strokeLinecap="round"
                opacity={0.45}
              />
            </>
          ) : (
            <path
              d="M 6 20 Q 103 2 200 20 T 394 20"
              stroke="currentColor"
              strokeWidth={12}
              strokeLinecap="round"
            />
          )}
        </svg>
      </span>
    </span>
  );
}
