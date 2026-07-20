"use client";

import { useQuery } from "@tanstack/react-query";
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
 * Polls GET /spotify/listening/{username} while the tab is visible —
 * refetchIntervalInBackground stays false so hidden tabs stop polling, and
 * refetchOnWindowFocus refreshes immediately on return. A failed poll keeps
 * the last known-good data (section-independence — same philosophy as Home's
 * _safe_section) rather than surfacing an error.
 */
export function usePolledListening({
  username,
  token,
  initial,
  intervalMs = 25_000,
}: UsePolledListeningOptions): ListeningResponse {
  const { data } = useQuery({
    // Token deliberately excluded from the key: a Clerk token refresh is the
    // same viewer, and keying on it would reset the cache entry every ~60s.
    queryKey: ["listening", username],
    queryFn: () => getListening(username, token),
    initialData: initial,
    // The RSC parent just fetched `initial`; the first refetch belongs to the
    // interval, not the mount. Fresh for one cycle so a focus-refetch only
    // fires when the data is actually older than a poll.
    refetchOnMount: false,
    staleTime: intervalMs,
    refetchInterval: intervalMs,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    retry: false,
  });

  return data;
}
