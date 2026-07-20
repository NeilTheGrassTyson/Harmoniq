import { screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderWithQuery } from "@/__tests__/test-utils";
import type { MelodyInboxItem } from "@/types";

// â”€â”€ Module mocks â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: async () => "test-token" }),
}));

const mockRespond = vi.fn();
vi.mock("@/lib/melodies", () => ({
  respondToMelody: (...args: unknown[]) => mockRespond(...args),
  getInbox: vi.fn(),
}));

vi.mock("@/components/CoverArt", () => ({
  default: () => <div data-testid="cover" />,
}));
vi.mock("@/components/EqualizerGlyph", () => ({
  default: () => <span data-testid="glyph" />,
}));

import MelodyInbox from "@/components/MelodyInbox";

// â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function makeItem(overrides: Partial<MelodyInboxItem> & { id: string }): MelodyInboxItem {
  return {
    sender: { id: "u1", username: "alice", display_name: "Alice", avatar_url: null },
    track: {
      id: "t1",
      mbid: "mbid-1",
      title: "Only Shallow",
      artist_name: "My Bloody Valentine",
      cover_art_url: null,
    },
    status: "received",
    created_at: new Date().toISOString(),
    responded_at: null,
    ...overrides,
  };
}

beforeEach(() => {
  mockRespond.mockReset();
  mockPush.mockReset();
});

// â”€â”€ Tests â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

describe("MelodyInbox â€” quick actions", () => {
  it("renders sender, track, and the three actions for an unresponded Melody", () => {
    renderWithQuery(<MelodyInbox initialItems={[makeItem({ id: "m1" })]} initialCursor={null} />);

    expect(screen.getByText("Only Shallow")).toBeDefined();
    expect(screen.getByText("My Bloody Valentine")).toBeDefined();
    expect(screen.getByText("Listen")).toBeDefined();
    expect(screen.getByText("Take it")).toBeDefined();
    expect(screen.getByText("Not for me")).toBeDefined();
  });

  it("accept calls respond with 'accept' and shows the outcome label", async () => {
    mockRespond.mockResolvedValue(makeItem({ id: "m1", status: "accepted" }));
    renderWithQuery(<MelodyInbox initialItems={[makeItem({ id: "m1" })]} initialCursor={null} />);

    fireEvent.click(screen.getByText("Take it"));

    await waitFor(() => {
      expect(mockRespond).toHaveBeenCalledWith("test-token", "m1", "accept");
      expect(screen.getByText("You took this one.")).toBeDefined();
    });
  });

  it("open navigates to the track page", async () => {
    mockRespond.mockResolvedValue(makeItem({ id: "m1", status: "opened" }));
    renderWithQuery(<MelodyInbox initialItems={[makeItem({ id: "m1" })]} initialCursor={null} />);

    fireEvent.click(screen.getByText("Listen"));

    await waitFor(() => {
      expect(mockRespond).toHaveBeenCalledWith("test-token", "m1", "open");
      expect(mockPush).toHaveBeenCalledWith("/track/mbid-1");
    });
  });

  it("reject keeps the row actionable (recoverable) with neutral copy", async () => {
    mockRespond.mockResolvedValue(makeItem({ id: "m1", status: "rejected" }));
    renderWithQuery(<MelodyInbox initialItems={[makeItem({ id: "m1" })]} initialCursor={null} />);

    fireEvent.click(screen.getByText("Not for me"));

    await waitFor(() => {
      expect(screen.getByText("You passed on this.")).toBeDefined();
    });
    // Still recoverable: Listen and Take it remain; re-reject is gone.
    expect(screen.getByText("Listen")).toBeDefined();
    expect(screen.getByText("Take it")).toBeDefined();
    expect(screen.queryByText("Not for me")).toBeNull();
  });

  it("terminal statuses render no actions", () => {
    renderWithQuery(
      <MelodyInbox initialItems={[makeItem({ id: "m1", status: "opened" })]} initialCursor={null} />
    );
    expect(screen.queryByText("Listen")).toBeNull();
    expect(screen.queryByText("Take it")).toBeNull();
    expect(screen.getByText("You listened.")).toBeDefined();
  });

  it("shows the empty state when there are no Melodies", () => {
    renderWithQuery(<MelodyInbox initialItems={[]} initialCursor={null} />);
    expect(screen.getByText(/No Melodies yet/)).toBeDefined();
  });
});
