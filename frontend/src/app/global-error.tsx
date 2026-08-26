"use client";

import "./globals.css";

/**
 * Last-resort boundary for failures in the root layout itself.
 *
 * This file replaces the root layout when active, so it must supply its own
 * <html> and <body> and its own styles — AppShell, ClerkProvider and the font
 * setup are all unavailable here by definition. Deliberately dependency-free:
 * anything it imports is something that can break it.
 */
export default function GlobalError({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  return (
    <html lang="en">
      <body className="bg-canvas text-primary antialiased">
        <title>Harmoniq</title>
        <main
          role="alert"
          className="mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center px-4"
        >
          <h1 className="text-primary text-lg font-light tracking-tight">
            Harmoniq didn&rsquo;t load.
          </h1>
          <p className="text-tertiary mt-1 max-w-xs text-center text-sm">
            Something went wrong on our side. Trying again often works.
          </p>
          <button
            type="button"
            onClick={() => unstable_retry()}
            className="border-hairline text-secondary hover:text-primary rounded-control mt-6 border px-4 py-2 text-sm"
          >
            Try again
          </button>
          {error.digest && <p className="text-tertiary mt-8 text-xs">Reference: {error.digest}</p>}
        </main>
      </body>
    </html>
  );
}
