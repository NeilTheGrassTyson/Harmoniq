import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

// --- Mocks ---

const mockUsePathname = vi.fn(() => "/");
vi.mock("next/navigation", () => ({
  usePathname: () => mockUsePathname(),
}));

const mockUseUser = vi.fn();
const mockUseAuth = vi.fn();
vi.mock("@clerk/nextjs", () => ({
  useUser: () => mockUseUser(),
  useAuth: () => mockUseAuth(),
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

const signedIn = {
  isLoaded: true,
  isSignedIn: true as const,
  user: { username: "testuser" },
};

const signedOut = {
  isLoaded: true,
  isSignedIn: false as const,
  user: null,
};

// --- Tests ---

describe("AppShell sidebar navigation", () => {
  beforeEach(() => {
    mockUsePathname.mockReturnValue("/");
    mockUseUser.mockReturnValue(signedIn);
    mockUseAuth.mockReturnValue({ isLoaded: true, isSignedIn: true, getToken: vi.fn() });
  });

  it("renders all five nav links when signed in", () => {
    render(<AppShell>content</AppShell>);
    expect(screen.getByRole("link", { name: "Home" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Search" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Melodies" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Profile" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Settings" })).toBeDefined();
  });

  it("hides the Profile and Melodies links when signed out", () => {
    mockUseUser.mockReturnValue(signedOut);
    mockUseAuth.mockReturnValue({ isLoaded: true, isSignedIn: false, getToken: vi.fn() });
    render(<AppShell>content</AppShell>);
    expect(screen.queryByRole("link", { name: "Profile" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Melodies" })).toBeNull();
    // Other links are still present
    expect(screen.getByRole("link", { name: "Home" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Settings" })).toBeDefined();
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
    expect(screen.getByRole("link", { name: "Settings" }).getAttribute("aria-current")).toBe("page");
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
