import { screen, waitFor, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderWithQuery } from "./test-utils";
import type { FriendPresence } from "@/types";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: async () => "test-token", isSignedIn: true }),
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));
vi.mock("@/components/AvatarImage", () => ({ default: () => <span data-testid="avatar" /> }));

const mockGet = vi.fn();
vi.mock("@/lib/presence", () => ({
  getFriendsPresence: (...args: unknown[]) => mockGet(...args),
}));

import FriendsRail from "@/components/FriendsRail";

const friend = (o: Partial<FriendPresence> & { username: string }): FriendPresence => ({
  display_name: o.username,
  avatar_url: null,
  state: null,
  track: null,
  ...o,
});

describe("FriendsRail", () => {
  // Braces matter: a function returned from beforeEach is run as teardown.
  beforeEach(() => {
    mockGet.mockReset();
  });

  it("groups in the server's order, with a count, skipping empty groups", async () => {
    mockGet.mockResolvedValue({
      friends: [
        friend({
          username: "ana",
          state: "listening",
          track: { title: "Xtal", artist_name: "Aphex Twin" },
        }),
        friend({ username: "cy", state: "offline" }),
        friend({ username: "abe", state: null }),
      ],
    });
    renderWithQuery(<FriendsRail />);

    const headings = await screen.findAllByRole("heading");
    expect(headings.map((h) => h.textContent)).toEqual(["Listening now", "Offline", "Friends"]);
    const listening = screen.getByRole("region", { name: "Listening now" });
    expect(within(listening).getByText("1")).toBeDefined();
    expect(within(listening).getByText("Xtal — Aphex Twin")).toBeDefined();
  });

  // Founder, 2026-09-27: Private is its own state — never shown as Offline.
  it("never files a friend with no shared status under Offline", async () => {
    mockGet.mockResolvedValue({ friends: [friend({ username: "abe", state: null })] });
    renderWithQuery(<FriendsRail />);

    const group = await screen.findByRole("region", { name: "Friends" });
    expect(within(group).getByText("abe")).toBeDefined();
    expect(screen.queryByRole("heading", { name: "Offline" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Online" })).toBeNull();
  });

  it("offers Send as a link that carries the friend into search", async () => {
    mockGet.mockResolvedValue({
      friends: [friend({ username: "jules", display_name: "Jules", state: "online" })],
    });
    renderWithQuery(<FriendsRail />);

    const send = await screen.findByRole("link", { name: "Send Jules a Melody" });
    expect(send.getAttribute("href")).toBe("/search?to=jules");
  });

  it("says who shows up here when there is no one yet", async () => {
    mockGet.mockResolvedValue({ friends: [] });
    renderWithQuery(<FriendsRail />);

    await waitFor(() => expect(screen.getByText(/follow each other/)).toBeDefined());
  });

  it("says so quietly when the rail can't load", async () => {
    mockGet.mockImplementation(async () => {
      throw new Error("down");
    });
    renderWithQuery(<FriendsRail />);

    await waitFor(() => expect(screen.getByText(/Couldn.t load your friends/)).toBeDefined());
  });
});
