import { screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderWithQuery } from "@/__tests__/test-utils";
import type { MelodyInboxItem } from "@/types";

// â”€â”€ Module mocks â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const mockPush = vi.fn();
const mockRefresh = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, refresh: mockRefresh }),
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
const mockReact = vi.fn();
vi.mock("@/lib/melodies", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/melodies")>()),
  respondToMelody: (...args: unknown[]) => mockRespond(...args),
  reactToMelody: (...args: unknown[]) => mockReact(...args),
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
  mockReact.mockReset();
  mockRefresh.mockReset();
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
    expect(screen.getByText("You opened this track.")).toBeDefined();
  });

  it("shows the empty state when there are no Melodies", () => {
    renderWithQuery(<MelodyInbox initialItems={[]} initialCursor={null} />);
    expect(screen.getByText(/No Melodies yet/)).toBeDefined();
  });
});

describe("recipient reactions", () => {
  it("allows feedback after opening without claiming or repeating playback", async () => {
    const item = makeItem({ id: "m1", status: "opened" });
    mockReact.mockResolvedValue({ ...item, reaction: "loved" });
    renderWithQuery(<MelodyInbox initialItems={[item]} initialCursor={null} reactionsEnabled />);
    fireEvent.click(screen.getByRole("button", { name: "Loved it — send more like this" }));
    await waitFor(() => expect(mockReact).toHaveBeenCalledWith("test-token", "m1", "loved"));
    await screen.findByText("Your reaction: Loved it — send more like this");
    expect(
      screen
        .getByRole("button", { name: "Loved it — send more like this" })
        .getAttribute("aria-pressed")
    ).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "Listen" }));
    expect(mockPush).toHaveBeenCalledWith("/track/mbid-1");
    expect(mockRespond).not.toHaveBeenCalled();
  });

  it("lets someone change their mind and preserves the selected reaction on failure", async () => {
    const item = makeItem({ id: "m1", status: "opened", reaction: "loved" });
    mockReact.mockRejectedValue(new Error("unavailable"));
    renderWithQuery(<MelodyInbox initialItems={[item]} initialCursor={null} reactionsEnabled />);
    fireEvent.click(screen.getByRole("button", { name: "Not for me" }));
    await screen.findByRole("alert");
    expect(screen.getByText("Your reaction: Loved it — send more like this")).toBeDefined();
    mockReact.mockResolvedValue({ ...item, reaction: "not_for_me" });
    fireEvent.click(screen.getByRole("button", { name: "Not for me" }));
    await screen.findByText("Your reaction: Not for me");
  });

  it("disables repeated actions while saving", async () => {
    mockReact.mockReturnValue(new Promise(() => {}));
    renderWithQuery(
      <MelodyInbox initialItems={[makeItem({ id: "m1" })]} initialCursor={null} reactionsEnabled />
    );
    fireEvent.click(screen.getByRole("button", { name: "Liked it" }));
    fireEvent.click(screen.getByRole("button", { name: "Liked it" }));
    await waitFor(() => expect(mockReact).toHaveBeenCalledTimes(1));
    expect((screen.getByRole("button", { name: "Listen" }) as HTMLButtonElement).disabled).toBe(
      true
    );
  });
});
