interface EqualizerGlyphProps {
  fill?: string;
  size?: number;
  className?: string;
}

export default function EqualizerGlyph({
  fill = "currentColor",
  size = 20,
  className = "",
}: EqualizerGlyphProps) {
  return (
    <svg
      width={size}
      height={Math.round(size * 0.8)}
      viewBox="0 0 20 16"
      fill={fill}
      className={className}
      aria-hidden="true"
    >
      {/* Three vertical bars — classic equalizer shape, flat fill, no gradient */}
      <rect x="1" y="8" width="4" height="8" rx="1" />
      <rect x="8" y="2" width="4" height="14" rx="1" />
      <rect x="15" y="6" width="4" height="10" rx="1" />
    </svg>
  );
}
