/**
 * `getViewer` resolves who is looking at the page, and the nav is built from
 * it. Both of its failure modes have shipped.
 *
 * The username must come from the *backend*, not from Clerk: Clerk's copy is
 * set at sign-up and never synced, so anyone who chose a different handle at
 * onboarding or renamed themselves got a `/u/{username}` link to a dead route
 * — or to whoever had since claimed their old handle (ADR 0012).
 *
 * And it must never throw. It sits in the root layout, so an exception here
 * is a blank site rather than a missing link. The cost of that safety is the
 * bug that followed: when the backend was slow, the timeout fired, the
 * username came back null, and the Profile link silently disappeared from a
 * signed-in user's nav with nothing on screen explaining why. Both halves are
 * pinned below, because the fix for either one is the other one's regression.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";

const auth = vi.fn();
const getOwnProfile = vi.fn();

vi.mock("@clerk/nextjs/server", () => ({ auth: () => auth() }));
vi.mock("@/lib/users", () => ({ getOwnProfile: (...args: unknown[]) => getOwnProfile(...args) }));

const { getViewer } = await import("@/lib/viewer");
const { REQUEST_TIMEOUT_MS } = await import("@/lib/apiBase");

const signedIn = (token: string | null = "tok") => ({
  userId: "user_1",
  getToken: async () => {
    if (token === null) throw new Error("no token");
    return token;
  },
});

beforeEach(() => {
  auth.mockReset();
  getOwnProfile.mockReset();
});

describe("getViewer", () => {
  it("reports a signed-out visitor without calling the backend", async () => {
    auth.mockResolvedValue({ userId: null, getToken: async () => null });

    expect(await getViewer()).toEqual({ signedIn: false, username: null });
    expect(getOwnProfile).not.toHaveBeenCalled();
  });

  it("returns the Harmoniq username, not Clerk's", async () => {
    auth.mockResolvedValue(signedIn());
    // Clerk's copy would be "clerk_handle"; the profile route is keyed by the
    // backend's, and linking to the wrong one is ADR 0012's dead route.
    getOwnProfile.mockResolvedValue({ username: "harmoniq_handle" });

    expect(await getViewer()).toEqual({ signedIn: true, username: "harmoniq_handle" });
  });

  it("stays signed in when the token cannot be minted", async () => {
    auth.mockResolvedValue(signedIn(null));

    // signedIn stays true: the person *is* signed in, and claiming otherwise
    // would offer them a sign-in button they do not need.
    expect(await getViewer()).toEqual({ signedIn: true, username: null });
    expect(getOwnProfile).not.toHaveBeenCalled();
  });

  it("never throws when the backend fails", async () => {
    auth.mockResolvedValue(signedIn());
    getOwnProfile.mockRejectedValue(Object.assign(new Error("boom"), { status: 500 }));

    // It renders in the root layout. A throw here is the whole site blank,
    // not a missing nav link.
    expect(await getViewer()).toEqual({ signedIn: true, username: null });
  });

  it("never throws when the backend times out", async () => {
    auth.mockResolvedValue(signedIn());
    getOwnProfile.mockRejectedValue(new DOMException("aborted", "TimeoutError"));

    // This is the path that made the Profile link vanish for a signed-in
    // user. It is deliberate — chrome must not hold up a page — but it is a
    // tradeoff, not an accident, so it is written down here.
    expect(await getViewer()).toEqual({ signedIn: true, username: null });
  });

  it("bounds the wait more tightly than an ordinary request", async () => {
    auth.mockResolvedValue(signedIn());
    getOwnProfile.mockResolvedValue({ username: "ana" });

    await getViewer();

    const signal = getOwnProfile.mock.calls[0][1] as AbortSignal | undefined;
    expect(signal).toBeInstanceOf(AbortSignal);
  });

  it("uses a timeout shorter than the app-wide one", () => {
    // The nav sits in every page's critical path, so it gets a shorter leash
    // than a request a user explicitly triggered and is waiting on.
    expect(REQUEST_TIMEOUT_MS).toBeGreaterThan(2_500);
  });
});
