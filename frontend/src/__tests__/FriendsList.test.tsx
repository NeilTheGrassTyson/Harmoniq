import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery } from "@/__tests__/test-utils";
import FriendsList from "@/components/FriendsList";
import type { FriendPerson } from "@/types";

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ getToken: async () => "token" }) }));
vi.mock("@/components/AvatarImage", () => ({ default: () => null }));
vi.mock("@/components/FollowButton", () => ({
  default: ({ username }: { username: string }) => <button>Follow {username}</button>,
}));

const api = vi.hoisted(() => ({ accept: vi.fn(), decline: vi.fn(), remove: vi.fn() }));
vi.mock("@/lib/friends", () => ({
  acceptFriendRequest: api.accept,
  declineFriendRequest: api.decline,
  removeFriend: api.remove,
}));

const person = (username: string, you_follow = false): FriendPerson => ({
  id: username,
  username,
  display_name: username.toUpperCase(),
  avatar_url: null,
  you_follow,
});

beforeEach(() => Object.values(api).forEach((fn) => fn.mockReset().mockResolvedValue("none")));

describe("FriendsList", () => {
  it("offers follow-back only for people the owner doesn't follow", () => {
    renderWithQuery(
      <FriendsList initial={{ friends: [person("amy", true), person("bo")], incoming: [] }} />
    );
    expect(screen.queryByRole("button", { name: "Follow amy" })).toBeNull();
    expect(screen.getByRole("button", { name: "Follow bo" })).toBeDefined();
  });

  it("moves an accepted request into friends, keeping the follow-back", async () => {
    api.accept.mockResolvedValue("friends");
    renderWithQuery(<FriendsList initial={{ friends: [], incoming: [person("cy")] }} />);
    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    await waitFor(() => expect(screen.queryByRole("heading", { name: "Requests" })).toBeNull());
    const friends = screen.getByRole("region", { name: "Friends" });
    expect(within(friends).getByText("CY")).toBeDefined();
    expect(within(friends).getByRole("button", { name: "Follow cy" })).toBeDefined();
  });

  it("offers no follow on a pending request, keeping the choice neutral", () => {
    renderWithQuery(<FriendsList initial={{ friends: [], incoming: [person("fi")] }} />);
    expect(screen.queryByRole("button", { name: "Follow fi" })).toBeNull();
  });

  it("declining quietly removes the request", async () => {
    renderWithQuery(<FriendsList initial={{ friends: [], incoming: [person("di")] }} />);
    fireEvent.click(screen.getByRole("button", { name: "Not now" }));
    await waitFor(() => expect(screen.queryByText("DI")).toBeNull());
    expect(api.decline).toHaveBeenCalledWith("token", "di");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("has no list of requests the owner has sent", () => {
    renderWithQuery(<FriendsList initial={{ friends: [], incoming: [] }} />);
    expect(screen.queryByText(/sent|pending|outgoing/i)).toBeNull();
    expect(screen.getByText(/No friends yet/)).toBeDefined();
  });

  it("removes a friend after confirmation", async () => {
    renderWithQuery(<FriendsList initial={{ friends: [person("ed")], incoming: [] }} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove ED from friends" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(screen.queryByText("ED")).toBeNull());
    expect(api.remove).toHaveBeenCalledWith("token", "ed");
  });
});
