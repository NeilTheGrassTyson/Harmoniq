import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { OwnProfileResponse, ProfileResponse } from "@/types";

// ── Module mocks ──────────────────────────────────────────────────────────────

const mockPush = vi.fn();
const mockReplace = vi.fn();
const mockRefresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace, refresh: mockRefresh }),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    className,
  }: {
    href: string;
    children: React.ReactNode;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

vi.mock("@/components/AvatarImage", () => ({
  default: () => <span data-testid="avatar" />,
}));

vi.mock("@/components/FollowButton", () => ({
  default: ({ username }: { username: string }) => (
    <button data-testid="follow-button">Follow {username}</button>
  ),
}));

let capturedEditPanelProps:
  | {
      onCancel: () => void;
      onSaved: (updated: OwnProfileResponse) => void;
      spotifyJustConnected?: boolean;
    }
  | undefined;

vi.mock("@/components/ProfileEditPanel", () => ({
  default: (props: {
    onCancel: () => void;
    onSaved: (updated: OwnProfileResponse) => void;
    spotifyJustConnected?: boolean;
  }) => {
    capturedEditPanelProps = props;
    return <div data-testid="edit-panel" />;
  },
}));

// ── Import after mocks ────────────────────────────────────────────────────────

import ProfileHeader from "@/components/ProfileHeader";

// ── Fixtures ──────────────────────────────────────────────────────────────────

function makeOwnProfile(overrides: Partial<ProfileResponse> = {}): ProfileResponse {
  return {
    username: "alice",
    display_name: "Alice",
    avatar_url: null,
    is_own_profile: true,
    follower_count: 5,
    following_count: 3,
    bio: null,
    ...overrides,
  };
}

function makeOtherProfile(overrides: Partial<ProfileResponse> = {}): ProfileResponse {
  return {
    username: "bob",
    display_name: "Bob",
    avatar_url: null,
    is_own_profile: false,
    follower_count: 5,
    following_count: 3,
    follow: { is_following: false, follows_you: false, is_friend: false },
    ...overrides,
  };
}

function makeOwnProfileUpdate(
  overrides: Partial<OwnProfileResponse> = {}
): OwnProfileResponse {
  return {
    username: "alice",
    display_name: "Alice",
    avatar_url: null,
    bio: null,
    visibility_bio: "private",
    visibility_activity: "private",
    visibility_ratings: "public",
    visibility_follows: "public",
    melody_accept_scope: "everyone",
    is_moderator: false,
    ...overrides,
  };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("ProfileHeader — own profile", () => {
  beforeEach(() => {
    capturedEditPanelProps = undefined;
    mockPush.mockReset();
    mockReplace.mockReset();
    mockRefresh.mockReset();
  });

  it("shows an Edit profile button, not a link", () => {
    render(<ProfileHeader profile={makeOwnProfile()} />);
    const button = screen.getByRole("button", { name: "Edit profile" });
    expect(button).toBeTruthy();
    expect(screen.queryByTestId("follow-button")).toBeNull();
  });

  it("clicking Edit profile reveals the panel", () => {
    render(<ProfileHeader profile={makeOwnProfile()} />);
    expect(screen.queryByTestId("edit-panel")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Edit profile" }));
    expect(screen.getByTestId("edit-panel")).toBeTruthy();
  });

  it("starts open when autoOpenEdit is true", () => {
    render(<ProfileHeader profile={makeOwnProfile()} autoOpenEdit />);
    expect(screen.getByTestId("edit-panel")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Edit profile" })).toBeNull();
  });

  it("passes spotifyJustConnected through to the edit panel when auto-opened", () => {
    render(<ProfileHeader profile={makeOwnProfile()} autoOpenEdit />);
    expect(capturedEditPanelProps?.spotifyJustConnected).toBe(true);
  });

  it('shows "Add a bio" when bio is null, which opens the panel', () => {
    render(<ProfileHeader profile={makeOwnProfile({ bio: null })} />);
    const addBio = screen.getByRole("button", { name: "Add a bio" });
    fireEvent.click(addBio);
    expect(screen.getByTestId("edit-panel")).toBeTruthy();
  });

  it("does not show Add a bio when a bio is already present", () => {
    render(<ProfileHeader profile={makeOwnProfile({ bio: "I like music." })} />);
    expect(screen.queryByRole("button", { name: "Add a bio" })).toBeNull();
    expect(screen.getByText("I like music.")).toBeTruthy();
  });

  it("onSaved updates displayed name/bio optimistically and closes the panel", () => {
    render(<ProfileHeader profile={makeOwnProfile()} autoOpenEdit />);
    act(() => {
      capturedEditPanelProps?.onSaved(
        makeOwnProfileUpdate({ display_name: "New Name", bio: "New bio" })
      );
    });
    expect(screen.getByText("New Name")).toBeTruthy();
    expect(screen.getByText("New bio")).toBeTruthy();
    expect(screen.queryByTestId("edit-panel")).toBeNull();
  });

  it("onSaved with an unchanged username calls router.refresh", () => {
    render(<ProfileHeader profile={makeOwnProfile()} autoOpenEdit />);
    act(() => {
      capturedEditPanelProps?.onSaved(makeOwnProfileUpdate({ username: "alice" }));
    });
    expect(mockRefresh).toHaveBeenCalledTimes(1);
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("onSaved with a changed username navigates to the new profile URL", () => {
    render(<ProfileHeader profile={makeOwnProfile()} autoOpenEdit />);
    act(() => {
      capturedEditPanelProps?.onSaved(makeOwnProfileUpdate({ username: "alice2" }));
    });
    expect(mockReplace).toHaveBeenCalledWith("/u/alice2");
    expect(mockRefresh).not.toHaveBeenCalled();
  });

  it("onCancel closes the panel", () => {
    render(<ProfileHeader profile={makeOwnProfile()} autoOpenEdit />);
    expect(screen.getByTestId("edit-panel")).toBeTruthy();
    act(() => {
      capturedEditPanelProps?.onCancel();
    });
    expect(screen.queryByTestId("edit-panel")).toBeNull();
  });
});

describe("ProfileHeader — other user's profile", () => {
  it("never shows Edit profile and renders FollowButton instead", () => {
    render(<ProfileHeader profile={makeOtherProfile()} />);
    expect(screen.queryByRole("button", { name: "Edit profile" })).toBeNull();
    expect(screen.getByTestId("follow-button")).toBeTruthy();
  });

  it("never shows Add a bio even if bio is null", () => {
    render(<ProfileHeader profile={makeOtherProfile({ bio: null })} />);
    expect(screen.queryByRole("button", { name: "Add a bio" })).toBeNull();
  });
});
