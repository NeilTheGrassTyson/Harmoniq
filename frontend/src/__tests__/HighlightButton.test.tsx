import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery } from "@/__tests__/test-utils";
import HighlightButton from "@/components/HighlightButton";
import type { HighlightItem } from "@/types";

const auth = vi.hoisted(() => ({
  getToken: async () => "token",
  userId: "me",
  isLoaded: true,
}));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth }));
const viewer = vi.hoisted(() => ({ signedIn: true, username: "me" as string | null }));
vi.mock("@/components/ViewerProvider", () => ({ useViewer: () => viewer }));
const api = vi.hoisted(() => ({ get: vi.fn(), add: vi.fn(), remove: vi.fn() }));
vi.mock("@/lib/highlights", () => ({
  getHighlights: api.get,
  addHighlight: api.add,
  removeHighlight: api.remove,
}));

const mine = (n: number, extra: Partial<HighlightItem>[] = []) => ({
  limit: 15,
  items: [
    ...extra.map((e, i) => ({ id: `x${i}`, entity_type: "album", mbid: "al-x", ...e })),
    ...Array.from({ length: n }, (_, i) => ({ id: `h${i}`, entity_type: "album", mbid: `a${i}` })),
  ],
});

beforeEach(() => {
  viewer.signedIn = true;
  viewer.username = "me";
  Object.values(api).forEach((fn) => fn.mockReset());
  api.add.mockResolvedValue({});
  api.remove.mockResolvedValue(undefined);
});

describe("HighlightButton", () => {
  it("is absent when signed out", () => {
    viewer.signedIn = false;
    viewer.username = null;
    const { container } = renderWithQuery(<HighlightButton entityType="track" mbid="tr-1" />);
    expect(container.innerHTML).toBe("");
    expect(api.get).not.toHaveBeenCalled();
  });

  it("highlights something new with no rating needed", async () => {
    api.get.mockResolvedValue(mine(2));
    renderWithQuery(<HighlightButton entityType="track" mbid="tr-1" />);
    const button = await screen.findByRole("button", { name: "Highlight" });
    expect(button.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(button);
    await waitFor(() =>
      expect(api.add).toHaveBeenCalledWith("token", { entity_type: "track", mbid: "tr-1" })
    );
  });

  it("removes something already highlighted", async () => {
    api.get.mockResolvedValue(mine(1, [{ id: "mine-1", entity_type: "track", mbid: "tr-1" }]));
    renderWithQuery(<HighlightButton entityType="track" mbid="tr-1" />);
    const button = await screen.findByRole("button", { name: "Highlighted" });
    expect(button.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(button);
    await waitFor(() => expect(api.remove).toHaveBeenCalledWith("token", "mine-1"));
  });

  it("explains the cap instead of failing at fifteen", async () => {
    api.get.mockResolvedValue(mine(15));
    renderWithQuery(<HighlightButton entityType="album" mbid="al-new" />);
    const button = await screen.findByRole("button", { name: "Highlight" });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/You have 15 highlights/)).toBeDefined();
  });

  it("is absent while highlights are switched off", async () => {
    api.get.mockRejectedValue(Object.assign(new Error("off"), { status: 404 }));
    const { container } = renderWithQuery(<HighlightButton entityType="album" mbid="al-1" />);
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(container.innerHTML).toBe("");
  });
});
