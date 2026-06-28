import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// ── Module mocks — must be declared before the dynamic import ─────────────────

vi.mock("@clerk/nextjs/server", () => ({
  auth: () =>
    Promise.resolve({
      getToken: () => Promise.resolve(null),
    }),
}));

vi.mock("next/navigation", () => ({
  notFound: () => {
    throw new Error("not found");
  },
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    className,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} className={className} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/components/AppShell", () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/AvatarImage", () => ({
  default: () => <span data-testid="avatar" />,
}));

vi.mock("@/components/FollowButton", () => ({
  default: () => <button>Follow</button>,
}));

const mockGetProfile = vi.fn();
const mockGetUserRatings = vi.fn();

vi.mock("@/lib/users", () => ({
  getProfile: (...args: unknown[]) => mockGetProfile(...args),
}));

vi.mock("@/lib/ratings", () => ({
  getUserRatings: (...args: unknown[]) => mockGetUserRatings(...args),
}));

// ── Import after mocks ────────────────────────────────────────────────────────

import ProfilePage from "@/app/u/[username]/page";

// ── Fixtures ──────────────────────────────────────────────────────────────────

const baseProfile = {
  username: "testuser",
  display_name: "Test User",
  avatar_url: null,
  is_own_profile: false,
  follower_count: 5,
  following_count: 3,
  follow: { is_following: false, follows_you: false, is_friend: false },
};

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("Profile page — follower/following links", () => {
  beforeEach(() => {
    mockGetProfile.mockResolvedValue(baseProfile);
    mockGetUserRatings.mockResolvedValue({ reviews: [] });
  });

  async function renderPage() {
    const jsx = await ProfilePage({
      params: Promise.resolve({ username: "testuser" }),
    });
    render(jsx);
  }

  it("renders follower count as a link to /u/[username]/followers", async () => {
    await renderPage();
    const link = screen.getByRole("link", { name: /5 followers/ });
    expect(link.getAttribute("href")).toBe("/u/testuser/followers");
  });

  it("renders following count as a link to /u/[username]/following", async () => {
    await renderPage();
    const link = screen.getByRole("link", { name: /3 following/ });
    expect(link.getAttribute("href")).toBe("/u/testuser/following");
  });

  it("follower link has hover:text-accent class for accent hover colour", async () => {
    await renderPage();
    const link = screen.getByRole("link", { name: /5 followers/ });
    expect(link.getAttribute("class")).toContain("hover:text-accent");
  });

  it("following link has hover:text-accent class for accent hover colour", async () => {
    await renderPage();
    const link = screen.getByRole("link", { name: /3 following/ });
    expect(link.getAttribute("class")).toContain("hover:text-accent");
  });
});
