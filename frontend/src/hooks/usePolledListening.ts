"use client";

import { useEffect, useRef, useState } from "react";
import { getListening } from "@/lib/spotify";
import type { ListeningResponse } from "@/types";

interface UsePolledListeningOptions {
  username: string;
  token?: string;
  initial: ListeningResponse;
  /** Default ~25s: the backend caches per-user for 60s, so most polls land on
   *  a warm cache — this cadence just controls how quickly the UI notices. */
  intervalMs?: number;
}

/**
 * Polls GET /spotify/listening/{username} while the tab is visible, pausing
 * when hidden and refetching immediately on becoming visible again. A failed
 * poll silently keeps the last known-good data (section-independence — same
 * philosophy as Home's _safe_section) rather than surfacing an error.
 */
export function usePolledListening({
  username,
  token,
  initial,
  intervalMs = 25_000,
}: UsePolledListeningOptions): ListeningResponse {
  const [listening, setListening] = useState(initial);

  // Held in refs so a Clerk token refresh (or any other prop churn) doesn't
  // tear down and recreate the interval — only the mount/unmount lifecycle
  // and an explicit intervalMs change should do that. Updated in their own
  // effect, not during render, per react-hooks/refs.
  const usernameRef = useRef(username);
  const tokenRef = useRef(token);
  useEffect(() => {
    usernameRef.current = username;
    tokenRef.current = token;
  }, [username, token]);

  useEffect(() => {
    let cancelled = false;
    let intervalId: ReturnType<typeof setInterval> | null = null;

    const poll = async () => {
      try {
        const result = await getListening(usernameRef.current, tokenRef.current);
        if (!cancelled) setListening(result);
      } catch {
        // Keep showing the last known-good data.
      }
    };

    const start = () => {
      if (intervalId !== null) return;
      intervalId = setInterval(poll, intervalMs);
    };
    const stop = () => {
      if (intervalId !== null) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };

    const handleVisibilityChange = () => {
      if (document.hidden) {
        stop();
      } else {
        void poll();
        start();
      }
    };

    if (!document.hidden) start();
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      cancelled = true;
      stop();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [intervalMs]);

  return listening;
}
