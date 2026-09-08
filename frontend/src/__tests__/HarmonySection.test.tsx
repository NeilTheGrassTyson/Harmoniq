import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { focusManager } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { queryWrapper, renderWithQuery } from "@/__tests__/test-utils";
import HarmonySection from "@/components/HarmonySection";

const { get, save, authState } = vi.hoisted(() => ({
  get: vi.fn(),
  save: vi.fn(),
  authState: { userId: "owner", isLoaded: true },
}));
vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ ...authState, getToken: async () => "token" }),
}));
vi.mock("@/lib/harmony", () => ({ getHarmony: get, setHarmonyVisibility: save }));

const own = {
  kind: "owner",
  visibility: "private",
  positive_count: 2,
  resolved_count: 3,
  acceptance_percent: 67,
  active_sending_months: 1,
};

beforeEach(() => {
  get.mockReset();
  save.mockReset();
  authState.userId = "owner";
});

describe("Harmony profile", () => {
  it("shows owner numbers and changes visibility only after server confirmation", async () => {
    get.mockResolvedValue(own);
    save.mockImplementation(async () => {
      get.mockResolvedValue({ ...own, visibility: "friends" });
      return { visibility: "friends" };
    });
    renderWithQuery(<HarmonySection username="alice" />);
    await screen.findByText("67% positive reception");
    const select = screen.getByRole("combobox", { name: "Share a positive summary with" });
    expect((select as HTMLSelectElement).value).toBe("private");
    fireEvent.change(select, { target: { value: "friends" } });
    await waitFor(() => expect(save).toHaveBeenCalledWith("token", "friends"));
    await screen.findByText("Visibility saved.");
    expect((screen.getByRole("combobox") as HTMLSelectElement).value).toBe("friends");
  });

  it("distinguishes no responses from a failed request and leaves failed visibility unchanged", async () => {
    get.mockResolvedValue({
      ...own,
      positive_count: 0,
      resolved_count: 0,
      acceptance_percent: null,
    });
    save.mockRejectedValue(new Error("Your Harmony visibility wasn't saved. Try again."));
    renderWithQuery(<HarmonySection username="alice" />);
    await screen.findByText("No responses yet.");
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "public" } });
    await screen.findByRole("alert");
    expect((screen.getByRole("combobox") as HTMLSelectElement).value).toBe("private");
    expect(screen.queryByText("0% positive reception")).toBeNull();
  });

  it("never displays owner numbers or controls for shared responses", async () => {
    get.mockResolvedValue({ kind: "shared", summary: "listeners" });
    renderWithQuery(<HarmonySection username="alice" />);
    await screen.findByText("Your music has found listeners");
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.queryByText(/positive reception/)).toBeNull();
  });

  it("removes a previously shared summary when consent is revoked", async () => {
    get
      .mockResolvedValueOnce({ kind: "shared", summary: "listeners" })
      .mockResolvedValue({ kind: "hidden" });
    renderWithQuery(<HarmonySection username="alice" />);
    await screen.findByText("Your music has found listeners");
    await act(async () => {
      focusManager.setFocused(false);
      focusManager.setFocused(true);
    });
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByText("Your music has found listeners")).toBeNull());
  });

  it("hides previous owner data immediately after identity changes", async () => {
    get.mockResolvedValueOnce(own).mockResolvedValue({ kind: "hidden" });
    const view = render(<HarmonySection username="alice" />, { wrapper: queryWrapper() });
    await screen.findByText("67% positive reception");
    authState.userId = "other";
    view.rerender(<HarmonySection username="alice" />);
    expect(screen.queryByText("67% positive reception")).toBeNull();
  });

  it("quietly supports an older API without Harmony", async () => {
    get.mockRejectedValue(Object.assign(new Error("unavailable"), { status: 404 }));
    renderWithQuery(<HarmonySection username="alice" />);
    await waitFor(() => expect(get).toHaveBeenCalled());
    expect(screen.queryByRole("heading", { name: "Harmony" })).toBeNull();
  });
});
