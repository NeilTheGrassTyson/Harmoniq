import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery } from "@/__tests__/test-utils";
import HighlightsSection from "@/components/HighlightsSection";
import type { HighlightItem, HighlightsResponse } from "@/types";

const auth = vi.hoisted(() => ({
  getToken: async () => "token",
  userId: "viewer",
  isLoaded: true,
}));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));
vi.mock("@/components/CoverArt", () => ({ default: () => null }));
vi.mock("@/components/PlaylistPicker", () => ({
  default: () => <div data-testid="picker" />,
}));
const api = vi.hoisted(() => ({ get: vi.fn(), remove: vi.fn() }));
vi.mock("@/lib/highlights", () => ({ getHighlights: api.get, removeHighlight: api.remove }));

const item = (overrides: Partial<HighlightItem>): HighlightItem => ({
  id: "h1",
  entity_type: "album",
  title: "Loveless",
  subtitle: "my bloody valentine",
  image_url: null,
  mbid: "al-1",
  external_url: null,
  provider: null,
  review: null,
  ...overrides,
});

const response = (overrides: Partial<HighlightsResponse> = {}): HighlightsResponse => ({
  items: [],
  limit: 15,
  ...overrides,
});

beforeEach(() => {
  api.get.mockReset();
  api.remove.mockReset().mockResolvedValue(undefined);
});

describe("HighlightsSection", () => {
  it("shows a visitor tiles, the owner's visible review, and no controls", async () => {
    api.get.mockResolvedValue(
      response({
        items: [
          item({
            review: { score: 9, review_text: "Still the one.", of_album: false },
          }),
          item({
            id: "h2",
            entity_type: "track",
            title: "Sometimes",
            mbid: "tr-1",
            review: { score: 8, review_text: "Album take", of_album: true },
          }),
          item({ id: "h3", entity_type: "artist", title: "Slowdive", mbid: "ar-1" }),
        ],
      })
    );
    renderWithQuery(<HighlightsSection username="amy" isOwnProfile={false} />);
    await screen.findByRole("heading", { name: "Highlights" });
    expect(screen.getByRole("link", { name: /Loveless/ }).getAttribute("href")).toBe("/album/al-1");
    expect(screen.getByText("Still the one.")).toBeDefined();
    expect(screen.getByText("(album review)")).toBeDefined();
    expect(screen.queryByRole("button", { name: /Remove/ })).toBeNull();
    expect(screen.queryByText(/of 15/)).toBeNull();
  });

  it("opens playlists in Spotify only through a validated link", async () => {
    api.get.mockResolvedValue(
      response({
        items: [
          item({
            id: "p1",
            entity_type: "playlist",
            title: "Night Drive",
            mbid: null,
            provider: "spotify",
            subtitle: "Spotify playlist",
            external_url: "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
          }),
          item({
            id: "p2",
            entity_type: "playlist",
            title: "Sketchy",
            mbid: null,
            external_url: "javascript:alert(1)",
          }),
        ],
      })
    );
    renderWithQuery(<HighlightsSection username="amy" isOwnProfile={false} />);
    const link = await screen.findByRole("link", { name: /Night Drive/ });
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toContain("noopener");
    expect(screen.queryByRole("link", { name: /Sketchy/ })).toBeNull();
  });

  it("shows everyone the same calm empty state, and the owner how to add", async () => {
    api.get.mockResolvedValue(response());
    const visitor = renderWithQuery(<HighlightsSection username="amy" isOwnProfile={false} />);
    await screen.findByText("No highlights yet.");
    expect(screen.queryByText(/from their pages/)).toBeNull();
    visitor.unmount();

    api.get.mockResolvedValue(response({ visibility: "public", playlists_available: true }));
    renderWithQuery(<HighlightsSection username="amy" isOwnProfile />);
    await screen.findByText("No highlights yet.");
    expect(
      screen.getByText(/from their pages, or add one of your Spotify playlists/)
    ).toBeDefined();
    expect(screen.getByText("0 of 15")).toBeDefined();
  });

  it("renders nothing when the viewer may not see them", async () => {
    api.get.mockRejectedValue(Object.assign(new Error("private"), { status: 403 }));
    const { container } = renderWithQuery(
      <HighlightsSection username="amy" isOwnProfile={false} />
    );
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(container.innerHTML).toBe("");
  });

  it("lets the owner remove one and offers the playlist picker when on", async () => {
    api.get.mockResolvedValue(
      response({ items: [item({})], visibility: "public", playlists_available: true })
    );
    renderWithQuery(<HighlightsSection username="amy" isOwnProfile />);
    fireEvent.click(await screen.findByRole("button", { name: "Remove Loveless from highlights" }));
    await waitFor(() => expect(api.remove).toHaveBeenCalledWith("token", "h1"));
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole("button", { name: "Add a playlist" }));
    expect(screen.getByTestId("picker")).toBeDefined();
  });

  it("offers no playlist picker while playlists are switched off", async () => {
    api.get.mockResolvedValue(response({ visibility: "public", playlists_available: false }));
    renderWithQuery(<HighlightsSection username="amy" isOwnProfile />);
    await screen.findByText("No highlights yet.");
    expect(screen.queryByRole("button", { name: "Add a playlist" })).toBeNull();
  });
});
