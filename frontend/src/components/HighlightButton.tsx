"use client";

import { useAuth } from "@clerk/nextjs";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useViewer } from "@/components/ViewerProvider";
import { useHighlights } from "@/hooks/useHighlights";
import { addHighlight, removeHighlight } from "@/lib/highlights";
import { friendlyError } from "@/lib/apiBase";

type CatalogType = "track" | "album" | "artist";

const quiet =
  "rounded-control border-hairline text-secondary hover:text-primary border px-3 py-1.5 text-xs font-medium disabled:opacity-50";

/**
 * Highlight this track, album or artist on your profile — from the page you're
 * on when you think "this is me" (Founder decision 2026-09-27). Needs no
 * rating. Absent when signed out or when highlights are switched off.
 */
export default function HighlightButton({
  entityType,
  mbid,
}: {
  entityType: CatalogType;
  mbid: string;
}) {
  const { getToken } = useAuth();
  const { signedIn, username } = useViewer();
  const queryClient = useQueryClient();
  const own = useHighlights(signedIn ? username : null);

  const current = own.data?.items.find(
    (item) => item.entity_type === entityType && item.mbid === mbid
  );
  const full = own.data ? own.data.items.length >= own.data.limit : false;

  const mutation = useMutation({
    mutationFn: async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      if (current) await removeHighlight(token, current.id);
      else await addHighlight(token, { entity_type: entityType, mbid });
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["highlights", username] }),
  });

  if (!signedIn || !own.data) return null;

  return (
    <div className="mt-3">
      <button
        type="button"
        className={quiet}
        disabled={mutation.isPending || (!current && full)}
        aria-pressed={!!current}
        onClick={() => mutation.mutate()}
      >
        {current ? "Highlighted" : "Highlight"}
      </button>
      {!current && full && (
        <p className="text-tertiary mt-1 text-xs">
          You have {own.data.limit} highlights. Remove one from your profile to add this.
        </p>
      )}
      {mutation.isError && (
        <p role="alert" className="text-destructive mt-1 text-xs">
          {friendlyError(mutation.error, "Something went wrong. Try again.")}
        </p>
      )}
    </div>
  );
}
