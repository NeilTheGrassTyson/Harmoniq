import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// ── Module mocks ──────────────────────────────────────────────────────────────

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: async () => "test-token" }),
  useUser: () => ({ isSignedIn: true }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

const mockSend = vi.fn();
vi.mock("@/lib/melodies", () => ({
  sendMelody: (...args: unknown[]) => mockSend(...args),
}));

vi.mock("@/components/CoverArt", () => ({
  default: () => <div data-testid="cover" />,
}));
vi.mock("@/components/EqualizerGlyph", () => ({
  default: () => <span data-testid="glyph" />,
}));

import SendMelodyPanel from "@/components/SendMelodyPanel";

const TRACK = {
  mbid: "mbid-1",
  title: "Only Shallow",
  artist_name: "My Bloody Valentine",
  cover_art_url: null,
};

beforeEach(() => {
  mockSend.mockReset();
});

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("SendMelodyPanel", () => {
  it("expands from the trigger button and shows the embed preview", () => {
    render(<SendMelodyPanel track={TRACK} />);

    fireEvent.click(screen.getByText("Send a Melody"));

    expect(screen.getByTestId("melody-card")).toBeDefined();
    expect(screen.getByText("Only Shallow")).toBeDefined();
    expect(screen.getByLabelText("Recipient username")).toBeDefined();
  });

  it("sends to the entered recipient and confirms calmly", async () => {
    mockSend.mockResolvedValue({
      id: "m1",
      recipient: { id: "u2", username: "bob", display_name: "Bob", avatar_url: null },
      track: { id: "t1", ...TRACK },
      status: "sent",
      created_at: new Date().toISOString(),
      responded_at: null,
    });
    render(<SendMelodyPanel track={TRACK} />);
    fireEvent.click(screen.getByText("Send a Melody"));

    fireEvent.change(screen.getByLabelText("Recipient username"), {
      target: { value: "@bob" },
    });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() => {
      // Leading @ is stripped before sending.
      expect(mockSend).toHaveBeenCalledWith("test-token", "bob", "mbid-1");
      expect(screen.getByText("Melody sent to @bob.")).toBeDefined();
    });
  });

  it("renders the backend's neutral accept-scope error verbatim", async () => {
    mockSend.mockRejectedValue(
      Object.assign(new Error("This member isn't receiving Melodies right now."), {
        status: 403,
      })
    );
    render(<SendMelodyPanel track={TRACK} />);
    fireEvent.click(screen.getByText("Send a Melody"));

    fireEvent.change(screen.getByLabelText("Recipient username"), {
      target: { value: "carol" },
    });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() => {
      expect(screen.getByText("This member isn't receiving Melodies right now.")).toBeDefined();
    });
  });

  it("disables Send with an empty recipient", () => {
    render(<SendMelodyPanel track={TRACK} />);
    fireEvent.click(screen.getByText("Send a Melody"));

    const send = screen.getByText("Send") as HTMLButtonElement;
    expect(send.disabled).toBe(true);
  });
});
