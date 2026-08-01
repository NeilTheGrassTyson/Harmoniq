import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import ConnectedAccounts from "@/components/ConnectedAccounts";

// ── Module mocks ──────────────────────────────────────────────────────────────

const mockGetToken = vi.fn().mockResolvedValue("mock-token");

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: mockGetToken }),
}));

const mockGetSpotifyConnection = vi.fn();
const mockGetSpotifyConnectUrl = vi.fn();
const mockDisconnectSpotify = vi.fn();

vi.mock("@/lib/spotify", () => ({
  getSpotifyConnection: (...args: unknown[]) => mockGetSpotifyConnection(...args),
  getSpotifyConnectUrl: (...args: unknown[]) => mockGetSpotifyConnectUrl(...args),
  disconnectSpotify: (...args: unknown[]) => mockDisconnectSpotify(...args),
}));

const DISCONNECTED = { connected: false, spotify_user_id: null, connected_at: null };
const CONNECTED = {
  connected: true,
  spotify_user_id: "spotify_alice",
  connected_at: "2026-07-01T00:00:00Z",
};

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("ConnectedAccounts", () => {
  beforeEach(() => {
    mockGetSpotifyConnection.mockReset();
    mockGetSpotifyConnectUrl.mockReset();
    mockDisconnectSpotify.mockReset();
  });

  it("shows the connect affordance when no account is linked", async () => {
    mockGetSpotifyConnection.mockResolvedValue(DISCONNECTED);
    render(<ConnectedAccounts />);
    expect(await screen.findByRole("button", { name: "Connect Spotify" })).toBeTruthy();
  });

  it("shows the linked account identity when connected", async () => {
    mockGetSpotifyConnection.mockResolvedValue(CONNECTED);
    render(<ConnectedAccounts />);
    expect(await screen.findByText("spotify_alice")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Disconnect" })).toBeTruthy();
  });

  it("Connect Spotify redirects to the OAuth URL", async () => {
    mockGetSpotifyConnection.mockResolvedValue(DISCONNECTED);
    mockGetSpotifyConnectUrl.mockResolvedValue({ url: "https://accounts.spotify.com/authorize" });

    const assignSpy = vi.fn();
    Object.defineProperty(window, "location", {
      value: { assign: assignSpy },
      writable: true,
    });

    render(<ConnectedAccounts />);
    fireEvent.click(await screen.findByRole("button", { name: "Connect Spotify" }));

    await waitFor(() =>
      expect(assignSpy).toHaveBeenCalledWith("https://accounts.spotify.com/authorize")
    );
  });

  it("Disconnect calls the API and returns the section to its unlinked state", async () => {
    mockGetSpotifyConnection.mockResolvedValue(CONNECTED);
    mockDisconnectSpotify.mockResolvedValue(undefined);

    render(<ConnectedAccounts />);
    fireEvent.click(await screen.findByRole("button", { name: "Disconnect" }));

    await waitFor(() => expect(mockDisconnectSpotify).toHaveBeenCalledWith("mock-token"));
    expect(await screen.findByRole("button", { name: "Connect Spotify" })).toBeTruthy();
  });

  it("confirms the connection after the OAuth callback returns", async () => {
    mockGetSpotifyConnection.mockResolvedValue(CONNECTED);
    render(<ConnectedAccounts justConnected />);
    expect(await screen.findByRole("status")).toBeTruthy();
  });

  it("stays quiet on a normal visit", async () => {
    mockGetSpotifyConnection.mockResolvedValue(CONNECTED);
    render(<ConnectedAccounts />);
    await screen.findByText("spotify_alice");
    expect(screen.queryByRole("status")).toBeNull();
  });

  // A Spotify outage must not take the settings page down with it.
  it("renders the connect affordance when the status lookup fails", async () => {
    mockGetSpotifyConnection.mockRejectedValue(new Error("network"));
    render(<ConnectedAccounts />);
    expect(await screen.findByRole("button", { name: "Connect Spotify" })).toBeTruthy();
  });

  it("surfaces a disconnect failure without dropping the connection", async () => {
    mockGetSpotifyConnection.mockResolvedValue(CONNECTED);
    mockDisconnectSpotify.mockRejectedValue(new Error("boom"));

    render(<ConnectedAccounts />);
    fireEvent.click(await screen.findByRole("button", { name: "Disconnect" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Disconnect" })).toBeTruthy();
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});
