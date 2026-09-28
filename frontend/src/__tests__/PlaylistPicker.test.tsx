import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery } from "@/__tests__/test-utils";
import PlaylistPicker from "@/components/PlaylistPicker";

const auth = vi.hoisted(() => ({ getToken: async () => "token" }));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth }));
vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));
vi.mock("@/components/CoverArt", () => ({ default: () => null }));
const api = vi.hoisted(() => ({ options: vi.fn(), add: vi.fn(), connect: vi.fn() }));
vi.mock("@/lib/highlights", () => ({
  getPlaylistOptions: api.options,
  addHighlight: api.add,
}));
vi.mock("@/lib/spotify", () => ({ getSpotifyConnectUrl: api.connect }));

const assign = vi.fn();
beforeEach(() => {
  Object.values(api).forEach((fn) => fn.mockReset());
  assign.mockReset();
  vi.stubGlobal("location", { ...window.location, assign });
});
afterEach(() => vi.unstubAllGlobals());

const noop = () => {};

describe("PlaylistPicker", () => {
  it("asks Spotify for the playlist permission, saying declining is harmless", async () => {
    api.options.mockResolvedValue({ status: "needs_permission", playlists: [] });
    api.connect.mockResolvedValue({ url: "https://accounts.spotify.com/authorize?x" });
    renderWithQuery(<PlaylistPicker full={false} onClose={noop} onAdded={noop} />);
    expect(await screen.findByText(/everything else keeps working/)).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Allow access to my playlists" }));
    await waitFor(() =>
      expect(assign).toHaveBeenCalledWith("https://accounts.spotify.com/authorize?x")
    );
  });

  it("adds one playlist at a time, with no add-all", async () => {
    const onAdded = vi.fn();
    api.options.mockResolvedValue({
      status: "ok",
      playlists: [
        { id: "a".repeat(22), name: "Night Drive", image_url: null, highlighted: false },
        { id: "b".repeat(22), name: "Mornings", image_url: null, highlighted: true },
      ],
    });
    api.add.mockResolvedValue({});
    renderWithQuery(<PlaylistPicker full={false} onClose={noop} onAdded={onAdded} />);
    fireEvent.click(await screen.findByRole("button", { name: "Highlight Night Drive" }));
    await waitFor(() =>
      expect(api.add).toHaveBeenCalledWith("token", {
        entity_type: "playlist",
        playlist_id: "a".repeat(22),
      })
    );
    await waitFor(() => expect(onAdded).toHaveBeenCalled());
    expect(screen.getByText("Highlighted")).toBeDefined();
    expect(screen.queryByRole("button", { name: /all/i })).toBeNull();
  });

  it("disables adding at the cap", async () => {
    api.options.mockResolvedValue({
      status: "ok",
      playlists: [{ id: "a".repeat(22), name: "Night Drive", image_url: null, highlighted: false }],
    });
    renderWithQuery(<PlaylistPicker full onClose={noop} onAdded={noop} />);
    const button = await screen.findByRole("button", { name: "Highlight Night Drive" });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/Remove one to add a playlist/)).toBeDefined();
  });

  it("points an unconnected user to settings", async () => {
    api.options.mockResolvedValue({ status: "not_connected", playlists: [] });
    renderWithQuery(<PlaylistPicker full={false} onClose={noop} onAdded={noop} />);
    expect((await screen.findByRole("link", { name: "settings" })).getAttribute("href")).toBe(
      "/settings"
    );
  });
});
