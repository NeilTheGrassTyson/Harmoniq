import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import MelodySettings from "@/components/MelodySettings";

// ── Module mocks ──────────────────────────────────────────────────────────────

const mockGetToken = vi.fn().mockResolvedValue("mock-token");
vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: mockGetToken, isSignedIn: true }),
}));

const mockGetOwnProfile = vi.fn();
const mockUpdateProfile = vi.fn();
vi.mock("@/lib/users", () => ({
  getOwnProfile: (...args: unknown[]) => mockGetOwnProfile(...args),
  updateProfile: (...args: unknown[]) => mockUpdateProfile(...args),
}));

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("MelodySettings", () => {
  beforeEach(() => {
    mockGetOwnProfile.mockReset();
    mockUpdateProfile.mockReset();
  });

  it("shows the scope the server actually reported", async () => {
    mockGetOwnProfile.mockResolvedValue({ melody_accept_scope: "mutuals" });
    render(<MelodySettings />);

    await waitFor(() =>
      expect(screen.getByTestId("melody-settings").textContent).toContain("Mutuals")
    );
  });

  // HARMONIQ.md §6, Consent Before Visibility. The control used to read
  // `scope ?? "everyone"`, so a settings request that failed told the reader
  // their inbox was open to everybody — a statement about their consent made
  // without having loaded it.
  it("never falls back to the most permissive scope when the load fails", async () => {
    mockGetOwnProfile.mockRejectedValue(new Error("network"));
    render(<MelodySettings />);

    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toMatch(/Couldn.t load your settings/)
    );
    const panel = screen.getByTestId("melody-settings").textContent ?? "";
    expect(panel.toLowerCase()).not.toContain("everyone");
    expect(screen.getByTestId("melody-scope-unknown")).toBeDefined();
  });
});
