interface SectionLabelProps {
  children: React.ReactNode;
  /** Extra classes — spacing only. The face, size, weight and tracking are fixed. */
  className?: string;
}

/**
 * The uppercase micro-label that heads a section: label face (Space Mono),
 * 10.5px / 700 / 1.1px tracking, 14px to its content (DESIGN_SYSTEM.md §3, §5).
 *
 * Shared rather than redeclared per surface because the settings headings had
 * already drifted apart from Home's — one uppercase at 12px, one sentence case
 * at 14px — for a label that is meant to read as the same object everywhere.
 *
 * Mono runs wide, so it sits a step below the old Grotesk labels in size and
 * gains tracking to compensate.
 */
export default function SectionLabel({ children, className = "" }: SectionLabelProps) {
  return (
    <h2
      className={`font-label text-tertiary mb-[14px] text-[10.5px] font-bold tracking-[1.1px] uppercase ${className}`}
    >
      {children}
    </h2>
  );
}
