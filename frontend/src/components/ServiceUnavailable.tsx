import Link from "next/link";
import EqualizerGlyph from "@/components/EqualizerGlyph";

/**
 * Shown when the backend could not be reached or answered 5xx.
 *
 * Distinct from `not-found.tsx`, which means the thing genuinely isn't there.
 * This one says the opposite: it probably exists, we just couldn't ask. Pages
 * render it in place of throwing so the shell, navigation and search survive
 * an outage — before this, an unreachable API took the whole page down to an
 * unstyled crash screen.
 */
export default function ServiceUnavailable({ what = "this page" }: { what?: string }) {
  return (
    <main role="alert" className="mx-auto flex max-w-2xl flex-col items-center px-4 py-24">
      <EqualizerGlyph size={36} className="text-secondary" />
      <h1 className="text-primary mt-4 text-lg font-light tracking-tight">
        Couldn&rsquo;t load {what}.
      </h1>
      <p className="text-tertiary mt-1 max-w-xs text-center text-sm">
        Harmoniq is unreachable right now. This is usually brief.
      </p>
      <Link
        href="/"
        className="border-hairline text-secondary hover:text-primary rounded-control mt-6 border px-4 py-2 text-sm"
      >
        Back to Home
      </Link>
    </main>
  );
}
