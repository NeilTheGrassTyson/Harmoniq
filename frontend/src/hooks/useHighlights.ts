"use client";

import { useAuth } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";
import { getHighlights } from "@/lib/highlights";
import { errorStatus } from "@/lib/apiBase";

/**
 * One user's highlights as the current viewer may see them. null means "not
 * shown to you": private to this viewer (403) or switched off (404).
 * Keyed on the viewer too, so one person's view is never shown to another.
 */
export function useHighlights(username: string | null) {
  const { getToken, userId, isLoaded } = useAuth();
  return useQuery({
    queryKey: ["highlights", username, userId ?? null],
    queryFn: async () => {
      try {
        return await getHighlights(username!, (await getToken()) ?? undefined);
      } catch (error) {
        const status = errorStatus(error);
        if (status === 403 || status === 404) return null;
        throw error;
      }
    },
    enabled: isLoaded && !!username,
    retry: false,
  });
}
