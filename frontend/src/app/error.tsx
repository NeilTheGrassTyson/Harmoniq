"use client";

import Link from "next/link";
import AppShell from "@/components/AppShell";
import EqualizerGlyph from "@/components/EqualizerGlyph";

/**
 * Route-segment error boundary for everything under app/.
 *
 * Without this file any server-side throw fell through to Next's own
 * "Application error: a server-side exception has occurred" screen — unstyled,
 * unbranded, and with nothing for the reader to do. `error.js` does not wrap
 * the root layout, so AppShell is rendered here to keep navigation and search
 * available while a single route is broken.
 *
 * `unstable_retry` (not `reset`) is what re-fetches and re-renders the
 * segment in this version of Next; `reset` only clears the boundary state
 * without refetching, which would immediately fail again on a server error.
 */
export default function Error({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  return (
    <AppShell>
      <main role="alert" className="mx-auto flex max-w-2xl flex-col items-center px-4 py-24">
        <EqualizerGlyph size={36} className="text-secondary" />
        <h1 className="text-primary mt-4 text-lg font-light tracking-tight">
          This didn&rsquo;t load.
        </h1>
        <p className="text-tertiary mt-1 max-w-xs text-center text-sm">
          Something went wrong on our side. Trying again often works.
        </p>
        <div className="mt-6 flex items-center gap-2">
          <button
            type="button"
            onClick={() => unstable_retry()}
            className="border-hairline text-secondary hover:text-primary rounded-control border px-4 py-2 text-sm"
          >
            Try again
          </button>
          <Link
            href="/"
            className="text-tertiary hover:text-primary rounded-control px-4 py-2 text-sm"
          >
            Back to Home
          </Link>
        </div>
        {/* Production strips the message from server errors; the digest is the
            only handle that matches this failure to the server log. */}
        {error.digest && <p className="text-tertiary mt-8 text-xs">Reference: {error.digest}</p>}
      </main>
    </AppShell>
  );
}
