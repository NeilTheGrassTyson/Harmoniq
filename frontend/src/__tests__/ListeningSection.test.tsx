import { screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ListeningSection, { formatRelative } from "@/components/ListeningSection";
import { renderWithQuery } from "@/__tests__/test-utils";
import type { ListeningResponse, RecentlyPlayedItem } from "@/types";

// The component polls via usePolledListening (which calls getListening) —
// mock it so no real network/timer activity happens during render.
const mockGetListening = vi.fn();
vi.mock("@/lib/spotify", () => ({
  getListening: (...args: unknown[]) => mockGetListening(...args),
}));

function makeItem(overrides: Partial<RecentlyPlayedItem> = {}): RecentlyPlayedItem {
  return {
    track_name: "Song",
    artist_name: "Artist",
    album_name: "Album",
    album_art_url: null,
    spotify_url: null,
    played_at: new Date().toISOString(),
    ...overrides,
  };
}

function renderSection(listening: ListeningResponse) {
  return renderWithQuery(<ListeningSection username="testuser" token="tok" initial={listening} />);
}

describe("ListeningSection", () => {
  beforeEach(() => {
    mockGetListening.mockReset();
    mockGetListening.mockResolvedValue({
      connected: false,
      now_playing: null,
      recently_played: [],
    });
  });

  it("shows the quiet empty state when not connected", () => {
    renderSection({ connected: false, now_playing: null, recently_played: [] });
    expect(screen.getByText("No listening activity yet.")).toBeTruthy();
  });

  it("shows a calm nothing-recent state when connected but idle", () => {
    renderSection({ connected: true, now_playing: null, recently_played: [] });
    expect(screen.getByText("Nothing played recently.")).toBeTruthy();
  });

  it("renders a Now playing row above recently played", () => {
    renderSection({
      connected: true,
      now_playing: makeItem({ track_name: "Current Song" }),
      recently_played: [makeItem({ track_name: "Earlier Song" })],
    });

    expect(screen.getByText("Current Song")).toBeTruthy();
    expect(screen.getByText("Now playing")).toBeTruthy();
    expect(screen.getByText("Earlier Song")).toBeTruthy();

    const rows = screen.getAllByRole("listitem");
    expect(rows[0].textContent).toContain("Current Song");
  });

  it("renders track and artist names for recent items", () => {
    renderSection({
      connected: true,
      now_playing: null,
      recently_played: [makeItem({ track_name: "Recent One", artist_name: "The Band" })],
    });
    expect(screen.getByText("Recent One")).toBeTruthy();
    expect(screen.getByText("The Band")).toBeTruthy();
  });

  it("only the now-playing row carries the accent tint class", () => {
    renderSection({
      connected: true,
      now_playing: makeItem({ track_name: "Current Song" }),
      recently_played: [makeItem({ track_name: "Earlier Song" })],
    });

    const rows = screen.getAllByRole("listitem");
    expect(rows[0].className).toContain("listening-now-row");
    expect(rows[1].className).not.toContain("listening-now-row");
  });

  it("only the now-playing row renders the equalizer glyph", () => {
    renderSection({
      connected: true,
      now_playing: makeItem({ track_name: "Current Song" }),
      recently_played: [makeItem({ track_name: "Earlier Song" })],
    });

    const rows = screen.getAllByRole("listitem");
    expect(rows[0].querySelector("svg")).toBeTruthy();
    expect(rows[1].querySelector("svg")).toBeNull();
  });

  it("renders no equalizer glyph when nothing is playing", () => {
    renderSection({
      connected: true,
      now_playing: null,
      recently_played: [makeItem()],
    });
    expect(screen.queryByRole("listitem")?.querySelector("svg")).toBeNull();
  });
});

describe("formatRelative", () => {
  const now = new Date("2026-07-04T12:00:00Z");

  it("formats sub-minute as just now", () => {
    expect(formatRelative("2026-07-04T11:59:40Z", now)).toBe("just now");
  });

  it("formats minutes", () => {
    expect(formatRelative("2026-07-04T11:57:00Z", now)).toBe("3m ago");
  });

  it("formats hours", () => {
    expect(formatRelative("2026-07-04T10:00:00Z", now)).toBe("2h ago");
  });

  it("formats days", () => {
    expect(formatRelative("2026-07-02T12:00:00Z", now)).toBe("2d ago");
  });

  it("falls back to a short date after a week", () => {
    const result = formatRelative("2026-06-20T12:00:00Z", now);
    expect(result).toMatch(/Jun/);
  });
});
