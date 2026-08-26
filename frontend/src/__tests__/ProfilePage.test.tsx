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
  default: (props: unknown) => {
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

async function renderPage() {
  const jsx = await ProfilePage({
    params: Promise.resolve({ username: "testuser" }),
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

// ── Backend failure handling ──────────────────────────────────────────────────
// Regression: an unreachable backend used to rethrow, and with no error.tsx in
// the app it surfaced as Next's unstyled "Application error" screen. The 404
// path must still reach notFound(); genuinely unexpected errors must still
// escape to the error boundary rather than being flattened into "unreachable".

describe("Profile page — backend failures", () => {
  beforeEach(() => {
    mockGetUserRatings.mockResolvedValue({ reviews: [] });
    mockGetProfile.mockReset();
  });

  it("renders the unavailable state when the backend can't be reached", async () => {
    // A fetch that never got a response: no status.
    mockGetProfile.mockRejectedValue(new TypeError("Load failed"));

    await renderPage();

    // Asserted through the alert's text content: the heading interpolates
    // the subject and uses a typographic apostrophe, so it spans text nodes.
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("this profile");
    expect(alert.textContent).toContain("unreachable");
    expect(screen.queryByTestId("profile-header")).toBeNull();
  });

  it("renders the unavailable state on a 5xx", async () => {
    mockGetProfile.mockRejectedValue(
      Object.assign(new Error("Internal Server Error"), { status: 503 })
    );

    await renderPage();

    expect(screen.getByRole("alert").textContent).toContain("this profile");
  });

  it("still calls notFound() for a missing profile", async () => {
    mockGetProfile.mockRejectedValue(Object.assign(new Error("Not Found"), { status: 404 }));

    await expect(renderPage()).rejects.toThrow("not found");
  });

  it("lets an unexpected error reach the error boundary", async () => {
    // 403 is not an outage — it means something we did not anticipate here,
    // and flattening it into "unreachable" would hide it.
    mockGetProfile.mockRejectedValue(Object.assign(new Error("Forbidden"), { status: 403 }));

    await expect(renderPage()).rejects.toThrow("Forbidden");
  });
});
