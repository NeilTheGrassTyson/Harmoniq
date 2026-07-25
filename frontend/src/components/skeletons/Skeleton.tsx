interface SkeletonProps {
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Placeholder block for content that hasn't arrived yet.
 *
 * Fill is `--color-surface-tile` — the same value CoverArt already uses for a
 * missing image, so a skeleton and an artwork fallback read as one material.
 * The pulse is functional motion (it signals work in progress), not decoration;
 * it's defined as `.skeleton-pulse` in globals.css and disabled under
 * prefers-reduced-motion. See DESIGN_SYSTEM.md §8.
 */
export default function Skeleton({ className = "", style }: SkeletonProps) {
  return <div aria-hidden="true" className={`bg-tile skeleton-pulse ${className}`} style={style} />;
}
