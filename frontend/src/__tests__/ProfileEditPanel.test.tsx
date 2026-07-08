import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import ProfileEditPanel from "@/components/ProfileEditPanel";
import type { OwnProfileResponse } from "@/types";

// ── Module mocks ──────────────────────────────────────────────────────────────

const mockGetToken = vi.fn().mockResolvedValue("mock-token");

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: mockGetToken }),
}));

vi.mock("@/components/AvatarImage", () => ({
  default: () => <span data-testid="avatar" />,
}));

vi.mock("@/components/VisibilitySelect", () => ({
  default: ({
    id,
    value,
    onChange,
  }: {
    id?: string;
    value: string;
    onChange: (v: string) => void;
  }) => (
    <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="public">Everyone</option>
      <option value="friends">Friends</option>
      <option value="private">Only you</option>
    </select>
  ),
}));

const mockGetOwnProfile = vi.fn();
const mockUpdateProfile = vi.fn();
const mockUploadAvatar = vi.fn();
const mockCheckUsernameAvailable = vi.fn();

vi.mock("@/lib/users", () => ({
  getOwnProfile: (...args: unknown[]) => mockGetOwnProfile(...args),
  updateProfile: (...args: unknown[]) => mockUpdateProfile(...args),
  uploadAvatar: (...args: unknown[]) => mockUploadAvatar(...args),
  checkUsernameAvailable: (...args: unknown[]) => mockCheckUsernameAvailable(...args),
}));

const mockGetSpotifyConnection = vi.fn();
const mockGetSpotifyConnectUrl = vi.fn();
const mockDisconnectSpotify = vi.fn();

vi.mock("@/lib/spotify", () => ({
  getSpotifyConnection: (...args: unknown[]) => mockGetSpotifyConnection(...args),
  getSpotifyConnectUrl: (...args: unknown[]) => mockGetSpotifyConnectUrl(...args),
  disconnectSpotify: (...args: unknown[]) => mockDisconnectSpotify(...args),
}));

// ── Fixtures ──────────────────────────────────────────────────────────────────

function makeOwnProfile(overrides: Partial<OwnProfileResponse> = {}): OwnProfileResponse {
  return {
    username: "alice",
    display_name: "Alice",
    avatar_url: null,
    bio: "Existing bio",
    visibility_bio: "private",
    visibility_activity: "private",
    visibility_ratings: "public",
    visibility_follows: "public",
    melody_accept_scope: "everyone",
    is_moderator: false,
    ...overrides,
  };
}

async function renderPanel(onSaved = vi.fn(), onCancel = vi.fn()) {
  render(
    <ProfileEditPanel
      initial={{ username: "alice", displayName: "Alice", avatarUrl: null }}
      onCancel={onCancel}
      onSaved={onSaved}
    />
  );
  // Wait for the lazy getOwnProfile fetch to resolve and hydrate the form.
  await screen.findByLabelText("Display name");
  return { onSaved, onCancel };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("ProfileEditPanel — load and hydrate", () => {
  beforeEach(() => {
    mockGetOwnProfile.mockResolvedValue(makeOwnProfile());
    mockGetSpotifyConnection.mockResolvedValue({
      connected: false,
      spotify_user_id: null,
      connected_at: null,
    });
    mockUpdateProfile.mockReset();
    mockUploadAvatar.mockReset();
    mockCheckUsernameAvailable.mockReset();
  });

  it("loads getOwnProfile on mount and populates the bio field", async () => {
    await renderPanel();
    expect(mockGetOwnProfile).toHaveBeenCalledWith("mock-token");
    // "Bio" also labels the bio-visibility <select> row — disambiguate to the textarea.
    const bioField = screen.getByLabelText("Bio", { selector: "textarea" }) as HTMLTextAreaElement;
    expect(bioField.value).toBe("Existing bio");
  });

  it("loads Spotify connection status separately", async () => {
    mockGetSpotifyConnection.mockResolvedValue({
      connected: true,
      spotify_user_id: "spotify_alice",
      connected_at: "2026-01-01T00:00:00Z",
    });
    await renderPanel();
    expect(await screen.findByText(/connected as/i)).toBeTruthy();
  });
});

describe("ProfileEditPanel — save", () => {
  beforeEach(() => {
    mockGetOwnProfile.mockResolvedValue(makeOwnProfile());
    mockGetSpotifyConnection.mockResolvedValue({
      connected: false,
      spotify_user_id: null,
      connected_at: null,
    });
    mockUpdateProfile.mockReset();
  });

  it("Save calls updateProfile with the full field set and calls onSaved", async () => {
    const updated = makeOwnProfile({ display_name: "Alice Updated" });
    mockUpdateProfile.mockResolvedValue(updated);
    const { onSaved } = await renderPanel();

    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: "Alice Updated" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(mockUpdateProfile).toHaveBeenCalled());
    expect(mockUpdateProfile).toHaveBeenCalledWith(
      "mock-token",
      expect.objectContaining({
        display_name: "Alice Updated",
        username: undefined, // unchanged
        bio: "Existing bio",
        visibility_bio: "private",
        visibility_activity: "private",
        visibility_ratings: "public",
        visibility_follows: "public",
      })
    );
    expect(onSaved).toHaveBeenCalledWith(updated);
  });

  it("Cancel calls onCancel without calling updateProfile", async () => {
    const { onCancel } = await renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(mockUpdateProfile).not.toHaveBeenCalled();
  });
});

describe("ProfileEditPanel — avatar validation", () => {
  beforeEach(() => {
    mockGetOwnProfile.mockResolvedValue(makeOwnProfile());
    mockGetSpotifyConnection.mockResolvedValue({
      connected: false,
      spotify_user_id: null,
      connected_at: null,
    });
    mockUploadAvatar.mockReset();
  });

  it("rejects a non-image-allowed file type", async () => {
    await renderPanel();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["x"], "doc.pdf", { type: "application/pdf" });
    fireEvent.change(input, { target: { files: [file] } });
    expect(await screen.findByText(/JPEG, PNG, or WebP/)).toBeTruthy();
    expect(mockUploadAvatar).not.toHaveBeenCalled();
  });

  it("rejects a file over 5MB", async () => {
    await renderPanel();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const big = new File([new Uint8Array(6 * 1024 * 1024)], "big.png", {
      type: "image/png",
    });
    fireEvent.change(input, { target: { files: [big] } });
    expect(await screen.findByText(/under 5 MB/)).toBeTruthy();
    expect(mockUploadAvatar).not.toHaveBeenCalled();
  });
});

describe("ProfileEditPanel — username availability", () => {
  beforeEach(() => {
    mockGetOwnProfile.mockResolvedValue(makeOwnProfile());
    mockGetSpotifyConnection.mockResolvedValue({
      connected: false,
      spotify_user_id: null,
      connected_at: null,
    });
    mockCheckUsernameAvailable.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("debounces the availability check and shows Available", async () => {
    mockCheckUsernameAvailable.mockResolvedValue({ available: true });
    // Load with real timers first (getOwnProfile/getSpotifyConnection resolve
    // via microtasks, not fake timers) — only switch to fake timers to
    // control the 300ms debounce below.
    await renderPanel();
    vi.useFakeTimers();

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "alice2" },
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });

    expect(mockCheckUsernameAvailable).toHaveBeenCalledWith("alice2");
    expect(screen.getByText("Available.")).toBeTruthy();
  });

  it("shows taken when unavailable", async () => {
    mockCheckUsernameAvailable.mockResolvedValue({ available: false });
    await renderPanel();
    vi.useFakeTimers();

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "taken_name" },
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });

    expect(screen.getByText("That username is taken.")).toBeTruthy();
  });
});

describe("ProfileEditPanel — Spotify connect/disconnect", () => {
  beforeEach(() => {
    mockGetOwnProfile.mockResolvedValue(makeOwnProfile());
    mockGetSpotifyConnectUrl.mockReset();
    mockDisconnectSpotify.mockReset();
  });

  it("Connect Spotify redirects to the OAuth URL", async () => {
    mockGetSpotifyConnection.mockResolvedValue({
      connected: false,
      spotify_user_id: null,
      connected_at: null,
    });
    mockGetSpotifyConnectUrl.mockResolvedValue({ url: "https://accounts.spotify.com/authorize" });
    const assignSpy = vi.fn();
    // @ts-expect-error -- jsdom doesn't implement navigation; stub it for this assertion
    delete window.location;
    // @ts-expect-error -- minimal stub
    window.location = { assign: assignSpy };

    await renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Connect Spotify" }));

    await waitFor(() =>
      expect(assignSpy).toHaveBeenCalledWith("https://accounts.spotify.com/authorize")
    );
  });

  it("Disconnect calls disconnectSpotify and updates the section", async () => {
    mockGetSpotifyConnection.mockResolvedValue({
      connected: true,
      spotify_user_id: "spotify_alice",
      connected_at: "2026-01-01T00:00:00Z",
    });
    mockDisconnectSpotify.mockResolvedValue(undefined);

    await renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Disconnect" }));

    await waitFor(() => expect(mockDisconnectSpotify).toHaveBeenCalledWith("mock-token"));
    expect(await screen.findByRole("button", { name: "Connect Spotify" })).toBeTruthy();
  });
});
