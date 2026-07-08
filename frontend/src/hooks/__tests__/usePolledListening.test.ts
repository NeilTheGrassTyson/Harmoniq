import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { usePolledListening } from "@/hooks/usePolledListening";
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
    // Ensure the tab reads as visible by default in jsdom.
    Object.defineProperty(document, "hidden", { value: false, configurable: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns the initial value before any timer fires", () => {
    mockGetListening.mockResolvedValue(UPDATED);
    const { result } = renderHook(() =>
      usePolledListening({ username: "alice", initial: INITIAL })
    );
    expect(result.current).toEqual(INITIAL);
    expect(mockGetListening).not.toHaveBeenCalled();
  });

  it("updates from a successful poll after the interval elapses", async () => {
    mockGetListening.mockResolvedValue(UPDATED);
    const { result } = renderHook(() =>
      usePolledListening({ username: "alice", token: "tok", initial: INITIAL, intervalMs: 1000 })
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(mockGetListening).toHaveBeenCalledWith("alice", "tok");
    expect(result.current).toEqual(UPDATED);
  });

  it("keeps the last known-good value when a poll fails", async () => {
    mockGetListening
      .mockResolvedValueOnce(UPDATED)
      .mockRejectedValueOnce(new Error("network error"));
    const { result } = renderHook(() =>
      usePolledListening({ username: "alice", initial: INITIAL, intervalMs: 1000 })
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(result.current).toEqual(UPDATED);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    // Still UPDATED — the rejected poll must not clear or crash the state.
    expect(result.current).toEqual(UPDATED);
  });

  it("stops polling while the tab is hidden and resumes with an immediate poll when visible", async () => {
    mockGetListening.mockResolvedValue(UPDATED);
    renderHook(() => usePolledListening({ username: "alice", initial: INITIAL, intervalMs: 1000 }));

    Object.defineProperty(document, "hidden", { value: true, configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(mockGetListening).not.toHaveBeenCalled();

    Object.defineProperty(document, "hidden", { value: false, configurable: true });
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(mockGetListening).toHaveBeenCalledTimes(1);
  });

  it("stops polling entirely after unmount", async () => {
    mockGetListening.mockResolvedValue(UPDATED);
    const { unmount } = renderHook(() =>
      usePolledListening({ username: "alice", initial: INITIAL, intervalMs: 1000 })
    );

    unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(mockGetListening).not.toHaveBeenCalled();
  });
});
