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
 *
 * Rendering in place costs the error status code: every route that uses this
 * has a loading.tsx, which wraps the page in a Suspense boundary, and once
 * that fallback flushes the response has committed to 200 and the status can
 * no longer be changed. So this carries its own `noindex` — the same remedy
 * Next applies to a notFound() that fires mid-stream. Without it a crawler
 * reaching a public profile or catalog page during an outage could index
 * “Couldn't load this page” as the page's real content.
 */
export default function ServiceUnavailable({ what = "this page" }: { what?: string }) {
  return (
    <main role="alert" className="mx-auto flex max-w-2xl flex-col items-center px-4 py-24">
      <meta name="robots" content="noindex" />
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
