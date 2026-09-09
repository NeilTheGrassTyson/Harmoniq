import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery } from "@/__tests__/test-utils";
import StreamingAccess from "@/components/StreamingAccess";
import { safeSpotifyUrl } from "@/lib/streaming";

const get = vi.hoisted(() => vi.fn());
vi.mock("@/lib/streaming", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/streaming")>()),
  getStreamingLinks: get,
}));
beforeEach(() => {
  // Returning the mock makes Vitest register it as a teardown callback.
  // A rejected mock would then throw after an otherwise successful test.
  get.mockReset();
});

describe("StreamingAccess", () => {
  it("distinguishes exact songs from search and isolates new tabs", async () => {
    get.mockResolvedValue({
      mapping_status: "available",
      links: [
        {
          provider: "spotify",
          name: "Spotify",
          kind: "exact",
          url: "https://open.spotify.com/track/0123456789abcdefghijkl",
        },
        {
          provider: "apple",
          name: "Apple Music",
          kind: "search",
          url: "https://music.apple.com/us/search?term=Song",
        },
      ],
    });
    renderWithQuery(<StreamingAccess mbid="track" />);
    await screen.findByRole("link", { name: /Open in Spotify/ });
    const search = screen.getByRole("link", { name: /Search Apple Music/ });
    expect(search.getAttribute("rel")).toBe("noopener noreferrer");
    expect(search.getAttribute("referrerpolicy")).toBe("no-referrer");
    expect(search.getAttribute("target")).toBe("_blank");
  });

  it("keeps the containing page usable during loading and after failure", async () => {
    get
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValue({ mapping_status: "unavailable", links: [] });
    renderWithQuery(
      <>
        <h1>A track</h1>
        <StreamingAccess mbid="track" />
      </>
    );
    expect(screen.getByRole("status").textContent).toContain("Finding");
    fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
    await screen.findByText(/Exact links are temporarily unavailable/);
    expect(screen.getByRole("heading", { name: "A track" })).toBeDefined();
  });

  it("supports an older API with links unavailable", async () => {
    get.mockRejectedValue(Object.assign(new Error("unavailable"), { status: 404 }));
    renderWithQuery(<StreamingAccess mbid="track" />);
    await waitFor(() => expect(screen.queryByRole("region", { name: "Listen on" })).toBeNull());
  });

  it("omits a successful older response that does not include links", async () => {
    get.mockResolvedValue({});
    renderWithQuery(
      <>
        <h1>A track</h1>
        <StreamingAccess mbid="track" />
      </>
    );
    await waitFor(() => expect(screen.queryByRole("region", { name: "Listen on" })).toBeNull());
    expect(screen.getByRole("heading", { name: "A track" })).toBeDefined();
  });
});

it("validates listening-row links and removes tracking parameters", () => {
  const safe = "https://open.spotify.com/track/0123456789abcdefghijkl";
  expect(safeSpotifyUrl(safe + "?si=tracking")).toBe(safe);
  for (const url of [
    "javascript:alert(1)",
    safe.replace(".com", ".com.evil.test"),
    safe.replace("https://", "https://attacker@"),
    safe + "\n",
    safe.replace("/track/", "/album/"),
  ]) {
    expect(safeSpotifyUrl(url)).toBeNull();
  }
});
