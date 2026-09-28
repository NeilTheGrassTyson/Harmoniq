import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery } from "@/__tests__/test-utils";
import FriendButton from "@/components/FriendButton";

const mockRefresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: mockRefresh }) }));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ getToken: async () => "token" }) }));

const api = vi.hoisted(() => ({
  send: vi.fn(),
  accept: vi.fn(),
  decline: vi.fn(),
  remove: vi.fn(),
}));
vi.mock("@/lib/friends", () => ({
  sendFriendRequest: api.send,
  acceptFriendRequest: api.accept,
  declineFriendRequest: api.decline,
  removeFriend: api.remove,
}));

beforeEach(() => {
  Object.values(api).forEach((fn) => fn.mockReset());
  mockRefresh.mockReset();
});

describe("FriendButton", () => {
  it("acknowledges a sent request once and returns to its normal state", async () => {
    api.send.mockResolvedValue("request_sent");
    renderWithQuery(<FriendButton username="bob" initialState="none" />);
    fireEvent.click(screen.getByRole("button", { name: "Add friend" }));
    await screen.findByText("Request sent.");
    expect(screen.getByRole("button", { name: "Add friend" })).toBeDefined();
    expect(api.send).toHaveBeenCalledWith("token", "bob");
    expect(mockRefresh).not.toHaveBeenCalled();
  });

  it("never shows a sender their own outstanding request", () => {
    renderWithQuery(<FriendButton username="bob" initialState="request_sent" />);
    expect(screen.getByRole("button", { name: "Add friend" })).toBeDefined();
    expect(screen.queryByText(/sent|pending/i)).toBeNull();
  });

  it("asking someone who already asked makes you friends", async () => {
    api.send.mockResolvedValue("friends");
    renderWithQuery(<FriendButton username="bob" initialState="none" />);
    fireEvent.click(screen.getByRole("button", { name: "Add friend" }));
    await screen.findByRole("button", { name: /Friends/ });
    expect(mockRefresh).toHaveBeenCalled();
  });

  it("offers accept and decline with equal weight, and declining says nothing", async () => {
    api.decline.mockResolvedValue("none");
    renderWithQuery(<FriendButton username="bob" initialState="request_received" />);
    const accept = screen.getByRole("button", { name: "Accept" });
    const decline = screen.getByRole("button", { name: "Not now" });
    expect(accept.className).toBe(decline.className);
    fireEvent.click(decline);
    await screen.findByRole("button", { name: "Add friend" });
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.queryByText(/declin|reject/i)).toBeNull();
  });

  it("accepting refreshes the page so friends-only content appears", async () => {
    api.accept.mockResolvedValue("friends");
    renderWithQuery(<FriendButton username="bob" initialState="request_received" />);
    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    await screen.findByRole("button", { name: /Friends/ });
    expect(mockRefresh).toHaveBeenCalledTimes(1);
  });

  it("removes a friend only after a quiet confirmation", async () => {
    api.remove.mockResolvedValue("none");
    renderWithQuery(<FriendButton username="bob" initialState="friends" />);
    fireEvent.click(screen.getByRole("button", { name: /Friends/ }));
    fireEvent.click(screen.getByRole("button", { name: "Keep" }));
    expect(api.remove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Friends/ }));
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await screen.findByRole("button", { name: "Add friend" });
    expect(mockRefresh).toHaveBeenCalled();
  });

  it("shows the server's consent message when a request is refused", async () => {
    api.send.mockRejectedValue(
      Object.assign(new Error("This member isn't accepting friend requests right now."), {
        status: 403,
      })
    );
    renderWithQuery(<FriendButton username="bob" initialState="none" />);
    fireEvent.click(screen.getByRole("button", { name: "Add friend" }));
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toBe(
        "This member isn't accepting friend requests right now."
      )
    );
  });
});
