"use client";

import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import { useMutation, useQuery } from "@tanstack/react-query";
import CoverArt from "@/components/CoverArt";
import { addHighlight, getPlaylistOptions } from "@/lib/highlights";
import { getSpotifyConnectUrl } from "@/lib/spotify";
import { friendlyError } from "@/lib/apiBase";

const quiet =
  "rounded-control border-hairline text-secondary hover:text-primary border px-3 py-1.5 text-xs font-medium disabled:opacity-50";

/**
 * Pick one of your own Spotify playlists to highlight — one at a time, by
 * explicit choice, which is what keeps the public-by-default exception
 * intact (specs/phase-2-highlights.md). There is deliberately no "add all".
 */
export default function PlaylistPicker({
  full,
  onClose,
  onAdded,
}: {
  full: boolean;
  onClose: () => void;
  onAdded: () => void;
}) {
  const { getToken } = useAuth();
  const options = useQuery({
    queryKey: ["playlist-options"],
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      return getPlaylistOptions(token);
    },
    retry: false,
  });

  const add = useMutation({
    mutationFn: async (playlistId: string) => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      return addHighlight(token, { entity_type: "playlist", playlist_id: playlistId });
    },
    onSuccess: () => {
      void options.refetch();
      onAdded();
    },
  });

  const allow = useMutation({
    // The widened scope is asked for through Spotify's own consent screen.
    // Declining there changes nothing: listening keeps working as before.
    mutationFn: async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const { url } = await getSpotifyConnectUrl(token);
      window.location.assign(url);
    },
  });

  const data = options.data;
  return (
    <div className="border-hairline rounded-control border p-3" data-testid="playlist-picker">
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="text-secondary text-sm">Your Spotify playlists</p>
        <button type="button" onClick={onClose} className="text-tertiary text-xs">
          Done
        </button>
      </div>

      {options.isPending && <p className="text-tertiary text-xs">Loading…</p>}
      {options.isError && (
        <p className="text-tertiary text-xs">Couldn&apos;t load your playlists. Try again later.</p>
      )}
      {data?.status === "unavailable" && (
        <p className="text-tertiary text-xs">Playlists can&apos;t be loaded right now.</p>
      )}
      {data?.status === "not_connected" && (
        <p className="text-tertiary text-xs">
          Connect Spotify in{" "}
          <Link href="/settings" className="underline underline-offset-2">
            settings
          </Link>{" "}
          to highlight a playlist.
        </p>
      )}
      {data?.status === "needs_permission" && (
        <div className="text-tertiary text-xs">
          <p>
            Harmoniq needs permission to see your playlists. Spotify will ask you to confirm; if you
            say no, everything else keeps working as it does now.
          </p>
          <button
            type="button"
            className={`${quiet} mt-2`}
            disabled={allow.isPending}
            onClick={() => allow.mutate()}
          >
            Allow access to my playlists
          </button>
        </div>
      )}
      {data?.status === "ok" &&
        (data.playlists.length === 0 ? (
          <p className="text-tertiary text-xs">You don&apos;t have any playlists of your own.</p>
        ) : (
          <ul className="max-h-72 overflow-y-auto">
            {data.playlists.map((playlist) => (
              <li key={playlist.id} className="flex items-center gap-3 py-1.5">
                <CoverArt src={playlist.image_url} alt={playlist.name} size={36} />
                <span className="text-primary min-w-0 flex-1 truncate text-sm">
                  {playlist.name}
                </span>
                {playlist.highlighted ? (
                  <span className="text-tertiary text-xs">Highlighted</span>
                ) : (
                  <button
                    type="button"
                    className={quiet}
                    disabled={add.isPending || full}
                    aria-label={`Highlight ${playlist.name}`}
                    onClick={() => add.mutate(playlist.id)}
                  >
                    Highlight
                  </button>
                )}
              </li>
            ))}
          </ul>
        ))}
      {full && data?.status === "ok" && (
        <p className="text-tertiary mt-2 text-xs">
          You have the most highlights you can. Remove one to add a playlist.
        </p>
      )}
      {(add.isError || allow.isError) && (
        <p role="alert" className="text-destructive mt-2 text-xs">
          {friendlyError(add.error ?? allow.error, "Something went wrong. Try again.")}
        </p>
      )}
    </div>
  );
}
