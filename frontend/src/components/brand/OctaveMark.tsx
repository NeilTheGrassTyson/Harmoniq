interface OctaveMarkProps {
  size?: number;
  className?: string;
  /**
   * Drops the overtone and thickens the fundamental. Below ~20px the second
   * wave renders under a pixel and reads as noise rather than as a second
   * voice, so the small mark is a redraw, not the same paths scaled.
   */
  compact?: boolean;
  /**
   * Draws the two waves in on mount, fundamental first. Functional, not
   * decorative: reserved for the moment a Melody arrives, where the motion
   * is what distinguishes "someone sent you this" from "this was already
   * here" (DESIGN_SYSTEM §8). Respects prefers-reduced-motion via
   * .octave-draw in globals.css.
   */
  animated?: boolean;
}

/**
 * The Harmoniq logomark: two waves an octave apart (2:1), crossing the
 * centreline together at shared nodes. Flat stroke, no gradient and no glow
 * (DESIGN_SYSTEM §2).
 *
 * Wired into the AppShell header below `sm`, where the wordmark would
 * compete with the search field. See ADR 0013 and DESIGN_SYSTEM.md §6.1.
 */
export default function OctaveMark({
  size = 24,
  className = "",
  compact = false,
  animated = false,
}: OctaveMarkProps) {
  const pathClassName = animated ? "octave-draw" : undefined;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      {/* pathLength normalises both curves to 1 so the draw-in dash maths in
          .octave-draw is independent of their very different arc lengths. */}
      <path
        d="M 12 60 Q 36 16 60 60 T 108 60"
        stroke="currentColor"
        strokeWidth={compact ? 15 : 10}
        strokeLinecap="round"
        pathLength={1}
        className={pathClassName}
      />
      {!compact && (
        <path
          d="M 12 60 Q 24 30 36 60 T 60 60 T 84 60 T 108 60"
          stroke="currentColor"
          strokeWidth={7}
          strokeLinecap="round"
          opacity={0.45}
          pathLength={1}
          className={pathClassName}
        />
      )}
    </svg>
  );
}
