"use client";

import { useAuth } from "@clerk/nextjs";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { getHarmony, setHarmonyVisibility } from "@/lib/harmony";
import { errorStatus, friendlyError } from "@/lib/apiBase";
import type { VisibilityScope } from "@/types";

export default function HarmonySection({ username }: { username: string }) {
  const { getToken, userId, isLoaded } = useAuth();
  const selectId = useId();
  const query = useQuery({
    queryKey: ["harmony", username, userId ?? null],
    queryFn: async () => {
      try {
        return await getHarmony(username, (await getToken()) ?? undefined);
      } catch (error) {
        if (errorStatus(error) === 404) return null;
        throw error;
      }
    },
    enabled: isLoaded,
    gcTime: 0,
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: "always",
    retry: false,
  });
  const visibility = useMutation({
    mutationFn: async (scope: VisibilityScope) => {
      const token = await getToken();
      if (!token) throw new Error("Sign in to change your Harmony visibility.");
      return setHarmonyVisibility(token, scope);
    },
    onSuccess: () => {
      void query.refetch();
    },
    retry: false,
  });
  const harmony = query.data;
  // A refetch must not leave a previously visible summary on screen after
  // consent is revoked, including if the new request fails.
  if (!isLoaded || query.isFetching) return null;
  if (query.isError)
    return (
      <section aria-label="Harmony" className="text-tertiary mb-8 text-sm">
        <p>Couldn&apos;t load Harmony.</p>
        <button onClick={() => void query.refetch()} className="underline underline-offset-2">
          Try again
        </button>
      </section>
    );
  if (!harmony || harmony.kind === "hidden" || (harmony.kind === "shared" && !harmony.summary))
    return null;

  return (
    <section aria-labelledby={`${selectId}-heading`} className="mb-8 text-sm">
      <h2
        id={`${selectId}-heading`}
        className="font-display text-tertiary mb-3 text-xs font-medium tracking-wide uppercase"
      >
        Harmony
      </h2>
      {harmony.kind === "shared" ? (
        <p className="text-secondary">
          {harmony.summary === "sustained"
            ? "Finding resonance over time"
            : "Your music has found listeners"}
        </p>
      ) : (
        <>
          <p className="text-secondary">
            {harmony.acceptance_percent === null
              ? "No responses yet."
              : `${harmony.acceptance_percent}% positive reception`}
          </p>
          {harmony.resolved_count > 0 && (
            <p className="text-tertiary mt-1">
              {harmony.positive_count} positive of {harmony.resolved_count} responses. Positive
              responses to music you sent in {harmony.active_sending_months} of the last 6 calendar
              months.
            </p>
          )}
          <p className="text-tertiary mt-2 text-xs">
            Your numbers are only visible to you. Liked and loved reactions count as positive.
            Without a reaction, taken and opened Melodies count as positive; passed Melodies count
            as a response. Opening a song does not prove playback.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <label htmlFor={selectId} className="text-secondary">
              Share a positive summary with
            </label>
            <select
              id={selectId}
              value={harmony.visibility}
              disabled={visibility.isPending}
              onChange={(event) => visibility.mutate(event.target.value as VisibilityScope)}
              className="rounded-control border-hairline bg-control text-primary border px-2 py-1 disabled:opacity-50"
            >
              <option value="private">Only you</option>
              <option value="friends">Friends — people you both follow</option>
              <option value="public">Everyone</option>
            </select>
          </div>
          {visibility.isError && (
            <p role="alert" className="text-destructive mt-2">
              {friendlyError(
                visibility.error,
                "Couldn't confirm your Harmony visibility. Try again."
              )}
            </p>
          )}
          {visibility.isSuccess && (
            <p role="status" className="text-tertiary mt-2 text-xs">
              Visibility saved.
            </p>
          )}
        </>
      )}
    </section>
  );
}
