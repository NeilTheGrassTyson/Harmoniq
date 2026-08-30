import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";

// --- Mocks ---

const mockUsePathname = vi.fn(() => "/");
vi.mock("next/navigation", () => ({
  usePathname: () => mockUsePathname(),
}));

// The nav reads the server-resolved viewer, never Clerk directly. Clerk stays
// mocked so an accidental reintroduction of useUser() here would be visible.
const mockUseViewer = vi.fn();
vi.mock("@/components/ViewerProvider", () => ({
  useViewer: () => mockUseViewer(),
}));

vi.mock("@clerk/nextjs", () => ({
  useUser: () => {
    throw new Error("AppShell must not read Clerk directly — use the server-resolved viewer");
  },
  useAuth: () => ({ isLoaded: true, isSignedIn: true, getToken: vi.fn() }),
  SignInButton: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  UserButton: () => <span data-testid="user-button" />,
}));

// Render next/link as a plain <a> so href and aria-current are queryable
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

vi.mock("@/components/SearchBar", () => ({
  default: () => <input placeholder="search" />,
  SearchBarFallback: () => <input placeholder="search" readOnly />,
}));

vi.mock("@/components/NavAuth", () => ({
  default: () => <span data-testid="nav-auth" />,
}));

vi.mock("@/components/EqualizerGlyph", () => ({
  default: () => <span data-testid="equalizer-glyph" />,
}));

vi.mock("@/components/NotificationBell", () => ({
  default: () => <span data-testid="notification-bell" />,
}));

// Must import AppShell after mocks are registered
import AppShell from "@/components/AppShell";

// --- Fixtures ---

// `username` is the Harmoniq handle — the one /u/ routes are keyed by.
const signedIn = { signedIn: true, username: "testuser" };
const signedOut = { signedIn: false, username: null };

// --- Tests ---

describe("AppShell sidebar navigation", () => {
  beforeEach(() => {
    mockUsePathname.mockReturnValue("/");
    mockUseViewer.mockReturnValue(signedIn);
  });

  it("renders all five nav links when signed in", () => {
    render(<AppShell>content</AppShell>);
    expect(screen.getByRole("link", { name: "Home" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Search" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Melodies" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Profile" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Settings" })).toBeDefined();
  });

  it("shows only the browse links when signed out", () => {
    mockUseViewer.mockReturnValue(signedOut);
    render(<AppShell>content</AppShell>);
    expect(screen.queryByRole("link", { name: "Profile" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Melodies" })).toBeNull();
    // Settings is an account page — offering it only leads to the sign-in wall.
    expect(screen.queryByRole("link", { name: "Settings" })).toBeNull();
    // Browse surfaces stay open to everyone (ADR 0012).
    expect(screen.getByRole("link", { name: "Home" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Search" })).toBeDefined();
  });

  // The regression this whole change exists for: the link used to be built
  // from Clerk's username, which the backend never syncs, so anyone whose
  // Harmoniq handle differed was sent to a dead route — or to whoever had
  // since claimed their old one.
  it("builds the Profile link from the Harmoniq username", () => {
    mockUseViewer.mockReturnValue({ signedIn: true, username: "harmoniq-handle" });
    render(<AppShell>content</AppShell>);
    expect(screen.getByRole("link", { name: "Profile" }).getAttribute("href")).toBe(
      "/u/harmoniq-handle"
    );
  });

  it("hides the Profile link when the username could not be resolved", () => {
    mockUseViewer.mockReturnValue({ signedIn: true, username: null });
    render(<AppShell>content</AppShell>);
    // Hiding it is honest; linking somewhere wrong is not.
    expect(screen.queryByRole("link", { name: "Profile" })).toBeNull();
    expect(screen.getByRole("link", { name: "Melodies" })).toBeDefined();
  });

  it("marks Home as active on /", () => {
    mockUsePathname.mockReturnValue("/");
    render(<AppShell>content</AppShell>);
    expect(screen.getByRole("link", { name: "Home" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Search" }).getAttribute("aria-current")).toBeNull();
    expect(screen.getByRole("link", { name: "Settings" }).getAttribute("aria-current")).toBeNull();
  });

  it("marks Search as active on /search", () => {
    mockUsePathname.mockReturnValue("/search");
    render(<AppShell>content</AppShell>);
    expect(screen.getByRole("link", { name: "Search" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Home" }).getAttribute("aria-current")).toBeNull();
  });

  it("marks Settings as active on /settings", () => {
    mockUsePathname.mockReturnValue("/settings");
    render(<AppShell>content</AppShell>);
    expect(screen.getByRole("link", { name: "Settings" }).getAttribute("aria-current")).toBe(
      "page"
    );
    expect(screen.getByRole("link", { name: "Home" }).getAttribute("aria-current")).toBeNull();
  });

  it("marks Profile as active on own profile route", () => {
    mockUsePathname.mockReturnValue("/u/testuser");
    render(<AppShell>content</AppShell>);
    expect(screen.getByRole("link", { name: "Profile" }).getAttribute("aria-current")).toBe("page");
  });

  it("marks Profile as active on /u/[username]/followers", () => {
    mockUsePathname.mockReturnValue("/u/testuser/followers");
    render(<AppShell>content</AppShell>);
    expect(screen.getByRole("link", { name: "Profile" }).getAttribute("aria-current")).toBe("page");
  });

  it("does not mark Profile as active on a different user's profile", () => {
    mockUsePathname.mockReturnValue("/u/otheruser");
    render(<AppShell>content</AppShell>);
    expect(screen.getByRole("link", { name: "Profile" }).getAttribute("aria-current")).toBeNull();
  });
});

describe("AppShell sidebar open state", () => {
  beforeEach(() => {
    mockUsePathname.mockReturnValue("/");
    mockUseViewer.mockReturnValue(signedIn);
  });

  // The panel must ship with no data-open so the CSS breakpoint decides. If
  // this attribute is ever present on first render, server-rendered HTML is
  // asserting a width it cannot know, and phones get a sidebar that covers
  // half the screen until hydration corrects it.
  it("leaves the breakpoint default in force until the user toggles", () => {
    const { container } = render(<AppShell>content</AppShell>);
    const panel = container.querySelector(".sidebar-panel");
    expect(panel).not.toBeNull();
    expect(panel!.hasAttribute("data-open")).toBe(false);
  });

  it("pins an explicit state on the panel once toggled", () => {
    const { container } = render(<AppShell>content</AppShell>);
    const panel = container.querySelector(".sidebar-panel")!;

    // matchMedia is stubbed to match, so the effective state starts open.
    fireEvent.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(panel.getAttribute("data-open")).toBe("false");

    fireEvent.click(screen.getByRole("button", { name: "Expand sidebar" }));
    expect(panel.getAttribute("data-open")).toBe("true");
  });

  it("reports the sidebar state through aria-expanded", () => {
    render(<AppShell>content</AppShell>);
    const toggle = screen.getByRole("button", { name: "Collapse sidebar" });
    expect(toggle.getAttribute("aria-expanded")).toBe("true");

    fireEvent.click(toggle);
    expect(
      screen.getByRole("button", { name: "Expand sidebar" }).getAttribute("aria-expanded")
    ).toBe("false");
  });
});
