import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ListenHistorySetting from "@/components/ListenHistorySetting";

// Stable like Clerk's own getToken, which the load effect depends on.
const auth = vi.hoisted(() => ({ getToken: async () => "token" }));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth }));
const users = vi.hoisted(() => ({ getOwnProfile: vi.fn(), updateProfile: vi.fn() }));
vi.mock("@/lib/users", () => users);

beforeEach(() => {
  users.getOwnProfile.mockReset();
  users.updateProfile.mockReset().mockResolvedValue({});
});

describe("ListenHistorySetting", () => {
  it("is absent while the backend has the feature off", async () => {
    users.getOwnProfile.mockResolvedValue({ store_listening: null });
    const { container } = render(<ListenHistorySetting />);
    await waitFor(() => expect(users.getOwnProfile).toHaveBeenCalled());
    await waitFor(() => expect(container.innerHTML).toBe(""));
  });

  it("shows no switch until the real value has loaded", () => {
    users.getOwnProfile.mockReturnValue(new Promise(() => {}));
    render(<ListenHistorySetting />);
    expect(screen.queryByRole("switch")).toBeNull();
  });

  it("opts in, and explains that opting out deletes the plays", async () => {
    users.getOwnProfile.mockResolvedValue({ store_listening: false });
    render(<ListenHistorySetting />);
    const toggle = await screen.findByRole("switch", {
      name: "Keep your recent listening on your profile",
    });
    expect((toggle as HTMLInputElement).checked).toBe(false);
    expect(screen.getByText(/Turning this off deletes them/)).toBeDefined();
    fireEvent.click(toggle);
    await waitFor(() =>
      expect(users.updateProfile).toHaveBeenCalledWith("token", { store_listening: true })
    );
    expect((toggle as HTMLInputElement).checked).toBe(true);
  });

  it("restores the previous value when saving fails", async () => {
    users.getOwnProfile.mockResolvedValue({ store_listening: true });
    users.updateProfile.mockRejectedValue(new Error("down"));
    render(<ListenHistorySetting />);
    const toggle = await screen.findByRole("switch");
    fireEvent.click(toggle);
    await screen.findByRole("alert");
    expect((toggle as HTMLInputElement).checked).toBe(true);
  });
});
