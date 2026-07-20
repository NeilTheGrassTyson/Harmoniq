import { renderHook, act, waitFor } from "@testing-library/react";
import { focusManager } from "@tanstack/react-query";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { usePolledListening } from "@/hooks/usePolledListening";
import { queryWrapper } from "@/__tests__/test-utils";
import type { ListeningResponse } from "@/types";

const mockGetListening = vi.fn();

vi.mock("@/lib/spotify", () => ({
  getListening: (...args: unknown[]) => mockGetListening(...args),
}));

const INITIAL: ListeningResponse = { connected: false, now_playing: null, recently_played: [] };
const UPDATED: ListeningResponse = {
  connected: true,
  now_playing: {
    track_name: "New Song",
    artist_name: "Artist",
    album_name: null,
    album_art_url: null,
    spotify_url: null,
  },
  recently_played: [],
};

describe("usePolledListening", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockGetListening.mockReset();
    focusManager.setFocused(true);
  });

  afterEach(() => {
    focusManager.setFocused(undefined);
    vi.useRealTimers();
  });

  it("returns the initial value before any timer fires", () => {
    mockGetListening.mockResolvedValue(UPDATED);
    const { result } = renderHook(
      () => usePolledListening({ username: "alice", initial: INITIAL }),
      { wrapper: queryWrapper() }
    );
    expect(result.current).toEqual(INITIAL);
    expect(mockGetListening).not.toHaveBeenCalled();
  });

  // Real timers for the data-flow tests: Query's observer notification does
  // not flush deterministically under fake timers, so we poll fast and wait.
  it("updates from a successful poll after the interval elapses", async () => {
    vi.useRealTimers();
    mockGetListening.mockResolvedValue(UPDATED);
    const { result } = renderHook(
      () =>
        usePolledListening({ username: "alice", token: "tok", initial: INITIAL, intervalMs: 50 }),
      { wrapper: queryWrapper() }
    );

    await waitFor(() => expect(result.current).toEqual(UPDATED));
    expect(mockGetListening).toHaveBeenCalledWith("alice", "tok");
  });

  it("keeps the last known-good value when a poll fails", async () => {
    vi.useRealTimers();
    mockGetListening
      .mockResolvedValueOnce(UPDATED)
      .mockRejectedValue(new Error("network error"));
    const { result } = renderHook(
      () => usePolledListening({ username: "alice", initial: INITIAL, intervalMs: 50 }),
      { wrapper: queryWrapper() }
    );

    await waitFor(() => expect(result.current).toEqual(UPDATED));

    // Wait until at least one rejected poll has happened after the success.
    await waitFor(() => expect(mockGetListening.mock.calls.length).toBeGreaterThanOrEqual(2));
    // Still UPDATED — the rejected poll must not clear or crash the state.
    expect(result.current).toEqual(UPDATED);
  });

  it("stops polling while the tab is hidden and resumes with a poll when visible", async () => {
    mockGetListening.mockResolvedValue(UPDATED);
    renderHook(
      () => usePolledListening({ username: "alice", initial: INITIAL, intervalMs: 1000 }),
      { wrapper: queryWrapper() }
    );

    act(() => focusManager.setFocused(false));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(mockGetListening).not.toHaveBeenCalled();

    await act(async () => {
      focusManager.setFocused(true);
      await vi.advanceTimersByTimeAsync(0);
    });
    // The stored data is 5s old (older than staleTime = intervalMs), so the
    // focus refetch fires immediately on becoming visible.
    expect(mockGetListening).toHaveBeenCalledTimes(1);
  });

  it("stops polling entirely after unmount", async () => {
    mockGetListening.mockResolvedValue(UPDATED);
    const { unmount } = renderHook(
      () => usePolledListening({ username: "alice", initial: INITIAL, intervalMs: 1000 }),
      { wrapper: queryWrapper() }
    );

    unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(mockGetListening).not.toHaveBeenCalled();
  });
});
