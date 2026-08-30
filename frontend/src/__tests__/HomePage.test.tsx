import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// ── Module mocks ──────────────────────────────────────────────────────────────

const mockAuth = vi.fn();
vi.mock("@clerk/nextjs/server", () => ({
  auth: () => mockAuth(),
}));

const mockGetHome = vi.fn();
vi.mock("@/lib/home", () => ({
  getHome: (...args: unknown[]) => mockGetHome(...args),
}));

vi.mock("@/components/AppShell", () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/TrackTile", () => ({
  default: ({ title }: { title: string }) => <span>{title}</span>,
}));

vi.mock("@/components/EqualizerGlyph", () => ({
  default: () => <span data-testid="equalizer-glyph" />,
}));

import Home from "@/app/page";

const signedIn = { userId: "user_1", getToken: async () => "mock-token" };

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("Home", () => {
  beforeEach(() => {
    mockAuth.mockReset();
    mockGetHome.mockReset();
    mockAuth.mockResolvedValue(signedIn);
  });

  // The catch used to swallow the failure and leave the error flags false, so
  // a total backend outage rendered as "No songs are trending yet" — a claim
  // about the catalog made having heard nothing back.
  it("reports a failed home request instead of an empty catalog", async () => {
    mockGetHome.mockRejectedValue(new Error("network"));
    render(await Home());

    expect(screen.getAllByText(/Couldn’t load this right now/)).toHaveLength(2);
    expect(screen.queryByText(/No songs are trending yet/)).toBeNull();
    expect(screen.queryByText(/Follow some people/)).toBeNull();
  });

  it("still shows the empty states when the server genuinely returns nothing", async () => {
    mockGetHome.mockResolvedValue({
      trending: [],
      trending_error: false,
      friends: [],
      friends_error: false,
      has_mutual_follows: false,
    });
    render(await Home());

    expect(screen.getByText(/No songs are trending yet/)).toBeDefined();
    expect(screen.getByText(/Follow some people/)).toBeDefined();
    expect(screen.queryByText(/Couldn’t load this right now/)).toBeNull();
  });
});
