/**
 * The username check, which is where this project's most user-visible bug
 * lived: a friend could not sign up, and the screen said "Couldn't check that
 * username".
 *
 * Two rules matter more than the rest, and both are about not lying to
 * someone who is trying to create an account:
 *
 * 1. A *failed* check is not a *taken* username. The endpoint is advisory and
 *    the write path re-checks, so a failure must report `error` and leave the
 *    form usable. Collapsing it into `taken` turns a backend hiccup into a
 *    permanent, inexplicable refusal.
 * 2. A slow answer must not overwrite a newer one. `ProfileEditPanel` had its
 *    own copy of this logic and was missing the guard (ADR 0010, rule 3),
 *    so an abandoned prefix could come back late and mark a perfectly free
 *    username as taken.
 *
 * Tested here rather than only through the two forms, because the reason this
 * hook exists is that the same logic in two places drifted apart.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useUsernameAvailability, USERNAME_RE } from "@/lib/useUsernameAvailability";

const checkUsernameAvailable = vi.fn();

vi.mock("@/lib/users", () => ({
  checkUsernameAvailable: (username: string) => checkUsernameAvailable(username),
}));

const DEBOUNCE_MS = 300;

/** A promise the test resolves by hand, to control response ordering. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  vi.useFakeTimers();
  checkUsernameAvailable.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

async function settle() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(DEBOUNCE_MS);
  });
}

describe("useUsernameAvailability", () => {
  it("does not ask the server about input the server would reject", () => {
    const { result } = renderHook(() => useUsernameAvailability());

    act(() => result.current.check("no spaces"));

    expect(result.current.availability).toEqual({ kind: "invalid" });
    expect(checkUsernameAvailable).not.toHaveBeenCalled();
  });

  it("reports the account's existing username as unchanged, not taken", () => {
    const { result } = renderHook(() => useUsernameAvailability("ana"));

    act(() => result.current.check("ana"));

    // Their own username is theirs. Reporting it taken would make the profile
    // editor refuse to save a form nobody edited.
    expect(result.current.availability).toEqual({ kind: "unchanged" });
    expect(checkUsernameAvailable).not.toHaveBeenCalled();
  });

  it("debounces a burst of keystrokes into one request", async () => {
    checkUsernameAvailable.mockResolvedValue({ available: true });
    const { result } = renderHook(() => useUsernameAvailability());

    act(() => {
      result.current.check("a");
      result.current.check("an");
      result.current.check("ana");
    });
    await settle();

    expect(checkUsernameAvailable).toHaveBeenCalledTimes(1);
    expect(checkUsernameAvailable).toHaveBeenCalledWith("ana");
    expect(result.current.availability).toEqual({ kind: "available" });
  });

  it("reports a failed check as an error, never as taken", async () => {
    // The original incident: the check failed and the user read it as a
    // rejection. `taken` here would block a signup the backend would allow.
    checkUsernameAvailable.mockRejectedValue(new TypeError("Load failed"));
    const { result } = renderHook(() => useUsernameAvailability());

    act(() => result.current.check("ana"));
    await settle();

    expect(result.current.availability).toEqual({ kind: "error" });
  });

  it("ignores a slow answer for a username the user has moved on from", async () => {
    const first = deferred<{ available: boolean }>();
    const second = deferred<{ available: boolean }>();
    checkUsernameAvailable.mockImplementation((username: string) =>
      username === "alpha" ? first.promise : second.promise
    );

    const { result } = renderHook(() => useUsernameAvailability());

    act(() => result.current.check("alpha"));
    await settle();
    act(() => result.current.check("beta"));
    await settle();

    // "beta" is free; "alpha" was taken, and answers second.
    await act(async () => {
      second.resolve({ available: true });
      await Promise.resolve();
    });
    await act(async () => {
      first.resolve({ available: false });
      await Promise.resolve();
    });

    // Without the guard this reads `taken` — for a username the field no
    // longer contains.
    expect(result.current.availability).toEqual({ kind: "available" });
  });

  it("ignores a slow failure for an abandoned username too", async () => {
    const first = deferred<{ available: boolean }>();
    const second = deferred<{ available: boolean }>();
    checkUsernameAvailable.mockImplementation((username: string) =>
      username === "alpha" ? first.promise : second.promise
    );

    const { result } = renderHook(() => useUsernameAvailability());

    act(() => result.current.check("alpha"));
    await settle();
    act(() => result.current.check("beta"));
    await settle();

    await act(async () => {
      second.resolve({ available: true });
      await Promise.resolve();
    });
    // The error path needs the same guard as the success path — it is a
    // second `setAvailability` call and it was added separately.
    await act(async () => {
      first.reject(new TypeError("Load failed"));
      await Promise.resolve();
    });

    expect(result.current.availability).toEqual({ kind: "available" });
  });

  it("does not fire a pending check after unmount", async () => {
    checkUsernameAvailable.mockResolvedValue({ available: true });
    const { result, unmount } = renderHook(() => useUsernameAvailability());

    act(() => result.current.check("ana"));
    unmount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS);
    });

    // A late callback on a gone component is the React warning ADR 0010 rule
    // 3 exists to prevent.
    expect(checkUsernameAvailable).not.toHaveBeenCalled();
  });
});

describe("USERNAME_RE", () => {
  // Mirrors backend/app/schemas/user.py::_USERNAME_RE. Drift means the form
  // accepts input the API rejects, and the user gets a 422 with no field
  // pointing at it.
  it.each(["ana", "a_b-c", "A1b", "a".repeat(30)])("accepts %s", (value) => {
    expect(USERNAME_RE.test(value)).toBe(true);
  });

  it.each(["ab", "a".repeat(31), "has space", "dots.not", "emoji🎵", ""])("rejects %s", (value) => {
    expect(USERNAME_RE.test(value)).toBe(false);
  });

  it("is character-for-character the backend's rule", async () => {
    // Asserted against the source rather than a copy of it. A comment saying
    // "mirrors the backend" is exactly the kind of claim that stops being
    // true without anything failing.
    const { readFileSync } = await import("node:fs");
    const { resolve } = await import("node:path");
    // Vitest runs with the frontend package as cwd.
    const schema = readFileSync(resolve(process.cwd(), "../backend/app/schemas/user.py"), "utf-8");
    const match = schema.match(/_USERNAME_RE = re\.compile\(r"(.+)"\)/);

    expect(match, "backend/app/schemas/user.py no longer declares _USERNAME_RE").toBeTruthy();
    expect(USERNAME_RE.source).toBe(match![1]);
  });
});
