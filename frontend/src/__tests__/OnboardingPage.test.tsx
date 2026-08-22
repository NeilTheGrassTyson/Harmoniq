import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// ── Module mocks ──────────────────────────────────────────────────────────────

const mockGetToken = vi.fn().mockResolvedValue("mock-token");
const mockReplace = vi.fn();
const mockReload = vi.fn().mockResolvedValue(undefined);

type ClerkUser = { firstName: string | null; lastName: string | null; username?: string | null };

// Mutable so each test can decide what Clerk knows, and when it finishes loading.
let clerkState: { user: ClerkUser | null; isLoaded: boolean } = { user: null, isLoaded: false };

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: mockGetToken }),
  useUser: () => ({
    isLoaded: clerkState.isLoaded,
    user: clerkState.user ? { ...clerkState.user, reload: mockReload } : null,
  }),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: mockReplace }) }));

const mockCheckUsernameAvailable = vi.fn();
const mockCreateUser = vi.fn();

vi.mock("@/lib/users", () => ({
  checkUsernameAvailable: (...args: unknown[]) => mockCheckUsernameAvailable(...args),
  createUser: (...args: unknown[]) => mockCreateUser(...args),
}));

import OnboardingPage from "@/app/onboarding/page";

// ── Helpers ───────────────────────────────────────────────────────────────────

const continueButton = () =>
  screen.getByRole("button", { name: /continue|creating account/i }) as HTMLButtonElement;

const usernameInput = () => screen.getByLabelText(/username/i);
const displayNameInput = () => screen.getByLabelText(/display name/i);

let rerenderPage: (() => void) | null = null;

function renderPage() {
  const { rerender } = render(<OnboardingPage />);
  rerenderPage = () => rerender(<OnboardingPage />);
}

/** Types a value and lets the 300ms availability debounce run. */
async function typeUsername(value: string) {
  fireEvent.change(usernameInput(), { target: { value } });
  await act(async () => {
    vi.advanceTimersByTime(400);
  });
}

/** Flips the Clerk mock to "loaded", the way a real session resolves mid-typing. */
async function resolveClerk(user: ClerkUser | null) {
  clerkState = { user, isLoaded: true };
  await act(async () => {
    rerenderPage?.();
  });
}

describe("OnboardingPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    clerkState = { user: null, isLoaded: false };
    rerenderPage = null;
    mockCheckUsernameAvailable.mockResolvedValue({ available: true });
    mockCreateUser.mockResolvedValue({ username: "dadrocks" });
  });

  it("enables Continue when Clerk resolves a name after the user has typed a username", async () => {
    renderPage();

    // The user starts typing before Clerk finishes loading — the common case
    // on a slow connection, and the one that used to wedge the form.
    await typeUsername("dadrocks");
    await resolveClerk({ firstName: "Dad", lastName: "Jordan" });

    await waitFor(() => expect(screen.getByText("Available.")).toBeTruthy());
    expect((displayNameInput() as HTMLInputElement).value).toBe("Dad Jordan");
    await waitFor(() => expect(continueButton().disabled).toBe(false));
  });

  // The original report: Continue stayed greyed out after typing a username.
  // It reproduces when the Clerk session is already warm at mount, so seeding
  // the display name overlaps the first burst of keystrokes.
  it("survives a burst of keystrokes racing the seeded display name", async () => {
    vi.useRealTimers();
    clerkState = { user: { firstName: "Dad", lastName: "Jordan" }, isLoaded: true };
    renderPage();

    const input = usernameInput();
    for (const value of ["d", "da", "dad", "dadr", "dadro", "dadroc", "dadrock", "dadrocks"]) {
      fireEvent.change(input, { target: { value } });
    }

    await waitFor(() => expect(screen.getByText("Available.")).toBeTruthy());
    await waitFor(() => expect(continueButton().disabled).toBe(false));
  });

  it("enables Continue when Clerk resolves a name before the user types", async () => {
    renderPage();
    await resolveClerk({ firstName: "Dad", lastName: "Jordan" });
    await typeUsername("dadrocks");

    await waitFor(() => expect(continueButton().disabled).toBe(false));
  });

  it("explains that a display name is required when Clerk has no name to seed", async () => {
    renderPage();
    await resolveClerk({ firstName: null, lastName: null });
    await typeUsername("dadrocks");

    expect(continueButton().disabled).toBe(true);
    expect(screen.getByText(/add a display name/i)).toBeTruthy();

    fireEvent.change(displayNameInput(), { target: { value: "Dad" } });
    await waitFor(() => expect(continueButton().disabled).toBe(false));
  });

  it("falls back to the Clerk username when no first or last name is set", async () => {
    renderPage();
    await resolveClerk({ firstName: null, lastName: null, username: "dadj" });
    await typeUsername("dadrocks");

    expect((displayNameInput() as HTMLInputElement).value).toBe("dadj");
    await waitFor(() => expect(continueButton().disabled).toBe(false));
  });

  it("keeps Continue disabled and says so when the username is taken", async () => {
    mockCheckUsernameAvailable.mockResolvedValue({ available: false });
    renderPage();
    await resolveClerk({ firstName: "Dad", lastName: "Jordan" });
    await typeUsername("dadrocks");

    expect(screen.getByText("That username is taken.")).toBeTruthy();
    expect(continueButton().disabled).toBe(true);
  });

  it("lets the user continue when the availability check itself fails", async () => {
    mockCheckUsernameAvailable.mockRejectedValue(new Error("network down"));
    renderPage();
    await resolveClerk({ firstName: "Dad", lastName: "Jordan" });
    await typeUsername("dadrocks");

    expect(screen.getByText(/couldn't check that username/i)).toBeTruthy();
    await waitFor(() => expect(continueButton().disabled).toBe(false));
  });

  it("ignores a stale availability response that resolves after a newer one", async () => {
    let resolveFirst: (v: { available: boolean }) => void = () => {};
    mockCheckUsernameAvailable
      .mockImplementationOnce(() => new Promise((r) => (resolveFirst = r)))
      .mockResolvedValue({ available: true });

    renderPage();
    await resolveClerk({ firstName: "Dad", lastName: "Jordan" });

    await typeUsername("taken_one");
    await typeUsername("free_one");
    await waitFor(() => expect(screen.getByText("Available.")).toBeTruthy());

    // The first, slower request now answers "taken" — for a username the
    // field no longer holds. It must not clobber the current result.
    await act(async () => {
      resolveFirst({ available: false });
    });
    expect(screen.getByText("Available.")).toBeTruthy();
    expect(continueButton().disabled).toBe(false);
  });

  it("creates the account and redirects to the new profile", async () => {
    renderPage();
    await resolveClerk({ firstName: "Dad", lastName: "Jordan" });
    await typeUsername("dadrocks");
    await waitFor(() => expect(continueButton().disabled).toBe(false));

    await act(async () => {
      fireEvent.click(continueButton());
    });

    await waitFor(() =>
      expect(mockCreateUser).toHaveBeenCalledWith("mock-token", "dadrocks", "Dad Jordan")
    );
    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/u/dadrocks"));
  });

  it("surfaces a backend rejection instead of failing silently", async () => {
    // Shaped like a real rejection from lib/users: an HTTP error carries the
    // status alongside the server's own user-facing detail message.
    mockCreateUser.mockRejectedValue(
      Object.assign(new Error("That username is taken."), { status: 409 })
    );
    renderPage();
    await resolveClerk({ firstName: "Dad", lastName: "Jordan" });
    await typeUsername("dadrocks");
    await waitFor(() => expect(continueButton().disabled).toBe(false));

    await act(async () => {
      fireEvent.click(continueButton());
    });

    await waitFor(() =>
      expect(screen.getAllByText("That username is taken.").length).toBeGreaterThan(0)
    );
    expect(mockReplace).not.toHaveBeenCalled();
  });

  // Regression: harmoniq.live was rejecting every browser call, and the raw
  // fetch rejection went straight to the screen. A friend trying to sign up
  // saw "Load failed" under the form and had no idea what it meant.
  it("shows a readable message when the backend can't be reached", async () => {
    // What Safari throws when a fetch never completes — note there is no
    // `status`, because no response ever arrived.
    mockCreateUser.mockRejectedValue(new TypeError("Load failed"));
    renderPage();
    await resolveClerk({ firstName: "Cooper", lastName: "Gallinson" });
    await typeUsername("cgallins");
    await waitFor(() => expect(continueButton().disabled).toBe(false));

    await act(async () => {
      fireEvent.click(continueButton());
    });

    await waitFor(() =>
      expect(
        screen.getByText("Couldn't reach Harmoniq. Check your connection and try again.")
      ).toBeTruthy()
    );
    expect(screen.queryByText("Load failed")).toBeNull();
    expect(mockReplace).not.toHaveBeenCalled();
  });
});
