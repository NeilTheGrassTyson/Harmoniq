/**
 * The two error boundaries, and the one thing about them that cannot be seen
 * by looking.
 *
 * Next 16 passes the recovery callback as `unstable_retry`. Next 15 called it
 * `reset`, and every example still in circulation uses that name. A boundary
 * written against `reset` renders identically — same heading, same styling,
 * same "Try again" button — and the button does nothing, because the prop it
 * calls was never passed. Nothing catches that: it type-checks against a
 * hand-written prop type, it lints clean, it builds, and it only shows up
 * when someone hits an error and the recovery button silently fails them.
 *
 * (`reset` also merely cleared the boundary state without refetching, so even
 * wired up correctly it would fail again immediately on a server error.
 * Verified against node_modules/next/dist/docs — per frontend/AGENTS.md, this
 * is not the Next.js in anyone's training data.)
 *
 * These tests pass the props Next actually passes and click the button. A
 * boundary that reverts to `reset` fails here.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/components/ViewerProvider", () => ({
  useViewer: () => ({ signedIn: false, username: null }),
}));

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ isLoaded: true, isSignedIn: false, getToken: vi.fn() }),
  useUser: () => ({ isLoaded: true, isSignedIn: false, user: null }),
  SignInButton: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  UserButton: () => <span data-testid="user-button" />,
}));

vi.mock("next/link", () => ({
  default: function MockLink({
    href,
    children,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & {
    href: string;
    children: React.ReactNode;
  }) {
    return (
      <a href={href} {...props}>
        {children}
      </a>
    );
  },
}));

const RouteError = (await import("@/app/error")).default;
const GlobalError = (await import("@/app/global-error")).default;

const retry = vi.fn();

beforeEach(() => {
  retry.mockReset();
});

describe("route error boundary", () => {
  it("recovers through the prop Next actually passes", () => {
    // Deliberately *only* `unstable_retry`. A boundary written against
    // `reset` renders the same button and throws on click.
    render(<RouteError error={new Error("boom")} unstable_retry={retry} />);

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("says something a reader can act on", () => {
    render(<RouteError error={new Error("boom")} unstable_retry={retry} />);

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("didn");
    // Never the raw throw: production strips it anyway, and it means nothing
    // to the person reading it.
    expect(alert.textContent).not.toContain("boom");
  });

  it("shows the digest, which is the only handle into the server log", () => {
    const error = Object.assign(new Error("boom"), { digest: "abc123" });
    render(<RouteError error={error} unstable_retry={retry} />);

    expect(screen.getByText(/abc123/)).toBeTruthy();
  });

  it("omits the reference line when there is no digest", () => {
    render(<RouteError error={new Error("boom")} unstable_retry={retry} />);

    expect(screen.queryByText(/Reference:/)).toBeNull();
  });

  it("keeps navigation available while one route is broken", () => {
    // error.js does not wrap the root layout, so the shell is rendered here
    // on purpose — a broken route must not strip the site's navigation.
    render(<RouteError error={new Error("boom")} unstable_retry={retry} />);

    expect(screen.getByRole("link", { name: "Back to Home" })).toBeTruthy();
  });
});

describe("global error boundary", () => {
  it("recovers through the prop Next actually passes", () => {
    render(<GlobalError error={new Error("boom")} unstable_retry={retry} />);

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("renders without the root layout it replaces", () => {
    // It stands in for the root layout, so AppShell, ClerkProvider and the
    // fonts are all unavailable by definition. Anything it imports is
    // something that can break it — this test renders it with every one of
    // those mocked away and it must still come up.
    render(<GlobalError error={new Error("boom")} unstable_retry={retry} />);

    expect(screen.getByRole("alert").textContent).toContain("Harmoniq");
  });

  it("shows the digest", () => {
    const error = Object.assign(new Error("boom"), { digest: "xyz789" });
    render(<GlobalError error={error} unstable_retry={retry} />);

    expect(screen.getByText(/xyz789/)).toBeTruthy();
  });
});
