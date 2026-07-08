import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { NotificationItem } from "@/types";

// ── Module mocks ──────────────────────────────────────────────────────────────

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

// Stable getToken identity — a fresh function per render would retrigger the
// component's poll effect on every state change and re-fetch the count.
const stableGetToken = async () => "test-token";
vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: stableGetToken, isSignedIn: true }),
}));

const mockGetUnreadCount = vi.fn();
const mockGetNotifications = vi.fn();
const mockMarkRead = vi.fn();
const mockMarkAllRead = vi.fn();
vi.mock("@/lib/notifications", () => ({
  getUnreadCount: (...args: unknown[]) => mockGetUnreadCount(...args),
  getNotifications: (...args: unknown[]) => mockGetNotifications(...args),
  markNotificationRead: (...args: unknown[]) => mockMarkRead(...args),
  markAllNotificationsRead: (...args: unknown[]) => mockMarkAllRead(...args),
}));

vi.mock("@/components/CoverArt", () => ({
  default: () => <div data-testid="cover" />,
}));

import NotificationBell from "@/components/NotificationBell";

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeNotification(
  overrides: Partial<NotificationItem> & { id: string }
): NotificationItem {
  return {
    type: "melody_received",
    actor: { id: "u1", username: "alice", display_name: "Alice", avatar_url: null },
    melody: {
      id: "m1",
      track: {
        id: "t1",
        mbid: "mbid-1",
        title: "Only Shallow",
        artist_name: "My Bloody Valentine",
        cover_art_url: null,
      },
    },
    read: false,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

beforeEach(() => {
  mockGetUnreadCount.mockReset();
  mockGetNotifications.mockReset();
  mockMarkRead.mockReset();
  mockMarkAllRead.mockReset();
});

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("NotificationBell", () => {
  it("shows a quiet dot — never a number — when there are unread notifications", async () => {
    mockGetUnreadCount.mockResolvedValue({ count: 3 });
    render(<NotificationBell />);

    await waitFor(() => {
      expect(screen.getByTestId("unread-dot")).toBeDefined();
    });
    // The count is never rendered as text.
    expect(screen.queryByText("3")).toBeNull();
  });

  it("shows no dot when everything is read", async () => {
    mockGetUnreadCount.mockResolvedValue({ count: 0 });
    render(<NotificationBell />);

    await waitFor(() => expect(mockGetUnreadCount).toHaveBeenCalled());
    expect(screen.queryByTestId("unread-dot")).toBeNull();
  });

  it("opens the panel and lists melody and follower rows", async () => {
    mockGetUnreadCount.mockResolvedValue({ count: 2 });
    mockGetNotifications.mockResolvedValue({
      items: [
        makeNotification({ id: "n1" }),
        makeNotification({
          id: "n2",
          type: "new_follower",
          melody: null,
          actor: { id: "u2", username: "bob", display_name: "Bob", avatar_url: null },
        }),
      ],
      next_cursor: null,
    });
    render(<NotificationBell />);

    await act(async () => {
      fireEvent.click(screen.getByTestId("notification-bell"));
    });

    await waitFor(() => {
      expect(screen.getByText(/sent you a Melody/)).toBeDefined();
      expect(screen.getByText(/Bob followed you/)).toBeDefined();
    });
  });

  it("clicking a melody row marks it read and navigates to /melodies", async () => {
    mockGetUnreadCount.mockResolvedValue({ count: 1 });
    mockGetNotifications.mockResolvedValue({
      items: [makeNotification({ id: "n1" })],
      next_cursor: null,
    });
    mockMarkRead.mockResolvedValue(undefined);
    render(<NotificationBell />);

    await act(async () => {
      fireEvent.click(screen.getByTestId("notification-bell"));
    });
    await waitFor(() => expect(screen.getByText(/sent you a Melody/)).toBeDefined());

    await act(async () => {
      fireEvent.click(screen.getByText(/sent you a Melody/));
    });

    await waitFor(() => {
      expect(mockMarkRead).toHaveBeenCalledWith("test-token", "n1");
      expect(mockPush).toHaveBeenCalledWith("/melodies");
    });
  });

  it("mark all read clears the dot", async () => {
    mockGetUnreadCount.mockResolvedValue({ count: 2 });
    mockGetNotifications.mockResolvedValue({
      items: [makeNotification({ id: "n1" })],
      next_cursor: null,
    });
    mockMarkAllRead.mockResolvedValue(undefined);
    render(<NotificationBell />);

    await waitFor(() => expect(screen.getByTestId("unread-dot")).toBeDefined());
    await act(async () => {
      fireEvent.click(screen.getByTestId("notification-bell"));
    });
    await waitFor(() => expect(screen.getByText("Mark all read")).toBeDefined());

    await act(async () => {
      fireEvent.click(screen.getByText("Mark all read"));
    });

    await waitFor(() => {
      expect(mockMarkAllRead).toHaveBeenCalled();
      expect(screen.queryByTestId("unread-dot")).toBeNull();
    });
  });
});
