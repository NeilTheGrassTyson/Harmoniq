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

const mockProfileHeaderProps = vi.fn();

vi.mock("@/components/ProfileHeader", () => ({
  default: (props: { autoOpenEdit?: boolean }) => {
    mockProfileHeaderProps(props);
    return <div data-testid="profile-header" />;
  },
}));

const mockGetProfile = vi.fn();
const mockGetUserRatings = vi.fn();
const mockGetListening = vi.fn();

vi.mock("@/lib/users", () => ({
  getProfile: (...args: unknown[]) => mockGetProfile(...args),
}));

vi.mock("@/lib/ratings", () => ({
  getUserRatings: (...args: unknown[]) => mockGetUserRatings(...args),
}));

vi.mock("@/lib/spotify", () => ({
  getListening: (...args: unknown[]) => mockGetListening(...args),
}));

vi.mock("@/components/ListeningSection", () => ({
  default: ({ initial }: { initial: { connected: boolean } }) => (
    <div data-testid="listening-section">
      {initial.connected ? "listening-data" : "not-connected"}
    </div>
  ),
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

async function renderPage(searchParams: { spotify?: string } = {}) {
  const jsx = await ProfilePage({
    params: Promise.resolve({ username: "testuser" }),
    searchParams: Promise.resolve(searchParams),
  });
  render(jsx);
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("Profile page — ProfileHeader wiring", () => {
  beforeEach(() => {
    mockGetProfile.mockResolvedValue(baseProfile);
    mockGetUserRatings.mockResolvedValue({ reviews: [] });
    mockProfileHeaderProps.mockReset();
  });

  it("renders ProfileHeader with the fetched profile", async () => {
    await renderPage();
    expect(screen.getByTestId("profile-header")).toBeTruthy();
    expect(mockProfileHeaderProps).toHaveBeenCalledWith(
      expect.objectContaining({ profile: baseProfile })
    );
  });

  it("does not auto-open edit when ?spotify=connected is absent", async () => {
    await renderPage();
    expect(mockProfileHeaderProps).toHaveBeenCalledWith(
      expect.objectContaining({ autoOpenEdit: false })
    );
  });

  it("auto-opens edit when ?spotify=connected and viewing own profile", async () => {
    mockGetProfile.mockResolvedValue({ ...baseProfile, is_own_profile: true });
    await renderPage({ spotify: "connected" });
    expect(mockProfileHeaderProps).toHaveBeenCalledWith(
      expect.objectContaining({ autoOpenEdit: true })
    );
  });

  it("does not auto-open edit for ?spotify=connected on someone else's profile", async () => {
    await renderPage({ spotify: "connected" }); // baseProfile.is_own_profile === false
    expect(mockProfileHeaderProps).toHaveBeenCalledWith(
      expect.objectContaining({ autoOpenEdit: false })
    );
  });
});

describe("Profile page — Listening section", () => {
  beforeEach(() => {
    mockGetUserRatings.mockResolvedValue({ reviews: [] });
    mockGetListening.mockReset();
  });

  it("renders no Listening section when activity is not visible", async () => {
    mockGetProfile.mockResolvedValue(baseProfile); // no activity_placeholder key
    await renderPage();
    expect(screen.queryByTestId("listening-section")).toBeNull();
    expect(mockGetListening).not.toHaveBeenCalled();
  });

  it("renders the Listening section from getListening when activity is visible", async () => {
    mockGetProfile.mockResolvedValue({ ...baseProfile, activity_placeholder: true });
    mockGetListening.mockResolvedValue({
      connected: true,
      now_playing: null,
      recently_played: [],
    });
    await renderPage();
    expect(screen.getByTestId("listening-section").textContent).toBe("listening-data");
  });

  it("renders nothing for the section when the listening fetch fails", async () => {
    mockGetProfile.mockResolvedValue({ ...baseProfile, activity_placeholder: true });
    mockGetListening.mockRejectedValue(new Error("boom"));
    await renderPage();
    expect(screen.queryByTestId("listening-section")).toBeNull();
  });
});
