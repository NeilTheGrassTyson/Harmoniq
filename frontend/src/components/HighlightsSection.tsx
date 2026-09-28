"use client";

import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import CoverArt from "@/components/CoverArt";
import EqualizerGlyph from "@/components/EqualizerGlyph";
import PlaylistPicker from "@/components/PlaylistPicker";
import { useHighlights } from "@/hooks/useHighlights";
import { removeHighlight } from "@/lib/highlights";
import { friendlyError } from "@/lib/apiBase";
import type { HighlightItem } from "@/types";

const TILE_GRID = "grid grid-cols-[repeat(auto-fill,minmax(130px,1fr))] gap-5";

function safePlaylistUrl(raw: string | null): string | null {
  if (!raw) return null;
  try {
    const url = new URL(raw);
    const match = url.pathname.match(/^\/playlist\/([A-Za-z0-9]{22})$/);
    return url.protocol === "https:" && url.host === "open.spotify.com" && match
      ? `https://open.spotify.com/playlist/${match[1]}`
      : null;
  } catch {
    return null;
  }
}

function Artwork({ item }: { item: HighlightItem }) {
  // Artist art is circular (DESIGN_SYSTEM §4); album, track and playlist art
  // is square, so the grid carries both shapes deliberately.
  const shape = item.entity_type === "artist" ? "rounded-full" : "rounded-control";
  return (
    <div className={`bg-tile relative aspect-square w-full overflow-hidden ${shape}`}>
      <div className="absolute inset-0 flex items-center justify-center">
        <EqualizerGlyph size={36} className="text-icon-trend" />
      </div>
      <CoverArt src={item.image_url} alt={item.title} fill />
    </div>
  );
}

function Tile({
  item,
  onRemove,
  removing,
}: {
  item: HighlightItem;
  onRemove?: () => void;
  removing: boolean;
}) {
  const playlistUrl = item.entity_type === "playlist" ? safePlaylistUrl(item.external_url) : null;
  const inner = (
    <>
      <Artwork item={item} />
      <p className="font-display text-primary mt-2 truncate text-sm/[1.3] font-medium">
        {item.title}
      </p>
      {item.subtitle && (
        <p className="text-secondary mt-0.5 truncate text-xs/[1.4]">{item.subtitle}</p>
      )}
    </>
  );
  return (
    <li className="min-w-0">
      {item.mbid ? (
        <Link
          href={`/${item.entity_type}/${encodeURIComponent(item.mbid)}`}
          className="tile-hover block"
        >
          {inner}
        </Link>
      ) : playlistUrl ? (
        <a
          href={playlistUrl}
          target="_blank"
          rel="noopener noreferrer"
          referrerPolicy="no-referrer"
          className="tile-hover block"
        >
          {inner}
          <span className="sr-only"> — open in Spotify (new tab)</span>
        </a>
      ) : (
        <div>{inner}</div>
      )}
      {item.review && (
        <p className="text-secondary mt-1.5 line-clamp-3 text-xs/[1.5]">
          <span className="text-primary font-display font-medium">{item.review.score}/10</span>{" "}
          {item.review.review_text}
          {item.review.of_album && <span className="text-tertiary"> (album review)</span>}
        </p>
      )}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          disabled={removing}
          aria-label={`Remove ${item.title} from highlights`}
          className="text-tertiary hover:text-secondary mt-1 text-[11px] underline-offset-2 hover:underline disabled:opacity-50"
        >
          Remove
        </button>
      )}
    </li>
  );
}

/**
 * The curated half of a profile (specs/phase-2-highlights.md): tiles, to read
 * as distinct from the Listening rows without a legend. Everyone sees the same
 * calm empty state (Founder decision 2026-09-27); the owner also gets how to
 * add some, worded so a profile never reads as incomplete without them.
 */
export default function HighlightsSection({
  username,
  isOwnProfile,
}: {
  username: string;
  isOwnProfile: boolean;
}) {
  const { getToken } = useAuth();
  const queryClient = useQueryClient();
  const query = useHighlights(username);
  const [pickerOpen, setPickerOpen] = useState(false);

  const remove = useMutation({
    mutationFn: async (id: string) => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await removeHighlight(token, id);
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["highlights", username] }),
  });

  const data = query.data;
  if (query.isPending || data === null || data === undefined) return null;

  const owner = isOwnProfile;
  return (
    <section aria-labelledby="highlights-heading" className="mb-8">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2
          id="highlights-heading"
          className="font-display text-tertiary text-xs font-medium tracking-wide uppercase"
        >
          Highlights
        </h2>
        {owner && (
          <span className="text-tertiary text-[11px] tabular-nums">
            {data.items.length} of {data.limit}
          </span>
        )}
      </div>

      {data.items.length === 0 ? (
        <div className="text-tertiary text-sm">
          <p>No highlights yet.</p>
          {owner && (
            <p className="mt-1 text-xs">
              Highlight tracks, albums and artists from their pages
              {data.playlists_available ? ", or add one of your Spotify playlists" : ""} — up to{" "}
              {data.limit}.
            </p>
          )}
        </div>
      ) : (
        <ul className={TILE_GRID}>
          {data.items.map((item) => (
            <Tile
              key={item.id}
              item={item}
              removing={remove.isPending}
              onRemove={owner ? () => remove.mutate(item.id) : undefined}
            />
          ))}
        </ul>
      )}

      {remove.isError && (
        <p role="alert" className="text-destructive mt-2 text-xs">
          {friendlyError(remove.error, "Couldn't remove that. Try again.")}
        </p>
      )}

      {owner && data.playlists_available && (
        <div className="mt-4">
          {pickerOpen ? (
            <PlaylistPicker
              full={data.items.length >= data.limit}
              onClose={() => setPickerOpen(false)}
              onAdded={() =>
                void queryClient.invalidateQueries({ queryKey: ["highlights", username] })
              }
            />
          ) : (
            <button
              type="button"
              onClick={() => setPickerOpen(true)}
              className="rounded-control border-hairline text-secondary hover:text-primary border px-3 py-1.5 text-xs font-medium"
            >
              Add a playlist
            </button>
          )}
        </div>
      )}
    </section>
  );
}
