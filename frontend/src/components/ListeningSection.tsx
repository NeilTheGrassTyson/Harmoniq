"use client";

import Image from "next/image";
import { useState } from "react";
import EqualizerGlyph from "@/components/EqualizerGlyph";
import { usePolledListening } from "@/hooks/usePolledListening";
import type { ListeningResponse, ListeningTrack } from "@/types";

/** "3m ago" / "2h ago" / "Jun 30" — quiet relative time for recent listens. */
export function formatRelative(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  const diffMs = now.getTime() - then.getTime();
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return then.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function Artwork({ src, alt }: { src: string | null; alt: string }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <span
        style={{
          display: "block",
          width: 36,
          height: 36,
          flexShrink: 0,
          backgroundColor: "#151821",
          borderRadius: 6,
        }}
      />
    );
  }
  return (
    <span
      style={{
        display: "block",
        position: "relative",
        width: 36,
        height: 36,
        flexShrink: 0,
        overflow: "hidden",
        borderRadius: 6,
      }}
    >
      <Image
        src={src}
        alt={alt}
        fill
        sizes="36px"
        className="object-cover"
        onError={() => setFailed(true)}
        unoptimized
      />
    </span>
  );
}

function TrackRow({
  track,
  meta,
  isNowPlaying = false,
}: {
  track: ListeningTrack;
  meta: string;
  isNowPlaying?: boolean;
}) {
  return (
    <li
      className={isNowPlaying ? "listening-now-row" : undefined}
      style={{ display: "flex", alignItems: "center", gap: 12, padding: "6px 0" }}
    >
      <Artwork src={track.album_art_url} alt={track.album_name ?? track.track_name} />
      <span style={{ minWidth: 0, flex: 1 }}>
        <span
          className="text-primary"
          style={{
            display: "block",
            fontSize: 13,
            fontWeight: 500,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {track.track_name}
        </span>
        <span
          className="text-tertiary"
          style={{
            display: "block",
            fontSize: 12,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {track.artist_name}
        </span>
      </span>
      {isNowPlaying && <EqualizerGlyph animated size={14} fill="#2f8cff" />}
      <span className="text-tertiary" style={{ fontSize: 11, flexShrink: 0 }}>
        {meta}
      </span>
    </li>
  );
}

interface ListeningSectionProps {
  username: string;
  token?: string;
  initial: ListeningResponse;
}

export default function ListeningSection({ username, token, initial }: ListeningSectionProps) {
  const listening = usePolledListening({ username, token, initial });

  if (!listening.connected) {
    return (
      <p className="text-tertiary" style={{ fontSize: 13 }}>
        No listening activity yet.
      </p>
    );
  }

  const hasAnything = listening.now_playing || listening.recently_played.length > 0;
  if (!hasAnything) {
    return (
      <p className="text-tertiary" style={{ fontSize: 13 }}>
        Nothing played recently.
      </p>
    );
  }

  return (
    <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
      {listening.now_playing && (
        <TrackRow track={listening.now_playing} meta="Now playing" isNowPlaying />
      )}
      {listening.recently_played.map((item, idx) => (
        <TrackRow
          key={`${item.played_at}-${idx}`}
          track={item}
          meta={formatRelative(item.played_at)}
        />
      ))}
    </ul>
  );
}
