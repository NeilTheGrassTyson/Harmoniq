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
});

describe("ProfileEditPanel — save", () => {
  beforeEach(() => {
    mockGetOwnProfile.mockResolvedValue(makeOwnProfile());
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
    mockCheckUsernameAvailable.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("debounces the availability check and shows Available", async () => {
    mockCheckUsernameAvailable.mockResolvedValue({ available: true });
    // Load with real timers first (getOwnProfile resolves
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

  // Regression: this panel had its own copy of the debounce logic and was
  // missing the stale-response guard the onboarding form got in ADR 0010.
  // A slow answer for an earlier value could land after a newer one and
  // overwrite it — telling the user a name is taken when it isn't.
  it("ignores a stale availability response that resolves after a newer one", async () => {
    let resolveFirst: (v: { available: boolean }) => void = () => {};
    mockCheckUsernameAvailable
      .mockImplementationOnce(
        () => new Promise<{ available: boolean }>((resolve) => (resolveFirst = resolve))
      )
      .mockResolvedValueOnce({ available: true });

    await renderPanel();
    vi.useFakeTimers();

    const field = screen.getByLabelText("Username");

    fireEvent.change(field, { target: { value: "first_name" } });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });

    // The user keeps typing; the newer check answers "available".
    fireEvent.change(field, { target: { value: "second_name" } });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });

    // Only now does the request for the abandoned value come back "taken".
    await act(async () => {
      resolveFirst({ available: false });
    });

    expect(screen.getByText("Available.")).toBeTruthy();
    expect(screen.queryByText("That username is taken.")).toBeNull();
  });
});
