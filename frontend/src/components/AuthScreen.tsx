import EqualizerGlyph from "@/components/EqualizerGlyph";

interface AuthScreenProps {
  /** One calm line of orientation. Guides without persuading (BRAND_BIBLE §10.2). */
  caption: string;
  children: React.ReactNode;
}

/**
 * Shared frame for the Clerk-hosted auth screens.
 *
 * Clerk renders the form itself; this supplies the surrounding identity so the
 * first screen a user meets reads as Harmoniq rather than as a vendor widget on
 * a dark background. Card chrome is deliberately absent — the mark, the line,
 * and the form stack in whitespace (DESIGN_SYSTEM.md §1).
 */
export default function AuthScreen({ caption, children }: AuthScreenProps) {
  return (
    <main className="bg-canvas flex min-h-screen flex-col items-center justify-center px-6 py-16">
      <div className="mb-7 flex flex-col items-center gap-3">
        <EqualizerGlyph size={28} className="text-accent" />
        <span className="font-display text-primary text-sm font-medium select-none">harmoniq</span>
        <p className="text-secondary max-w-[26ch] text-center text-[13px] text-balance">
          {caption}
        </p>
      </div>
      {children}
    </main>
  );
}
