"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import EqualizerGlyph from "@/components/EqualizerGlyph";
import { usePolledListening } from "@/hooks/usePolledListening";
import type { ListeningResponse, ListeningTrack, VisibilityScope } from "@/types";

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
    return <span className="bg-tile rounded-nav block size-9 shrink-0" aria-hidden="true" />;
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
      {isNowPlaying && <EqualizerGlyph animated size={14} className="text-accent" />}
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
  /** True when the viewer is looking at their own profile. */
  isOwnProfile?: boolean;
  /** Owner-only: who else can see this section. Absent for other viewers. */
  scope?: VisibilityScope;
}

/**
 * A quiet line telling the owner who else can see their listening.
 *
 * Activity defaults to private, so without this the owner sees their own
 * tracks, assumes everyone does, and finds every other profile empty — which
 * reads as a broken feature rather than a setting. Shown only to the owner:
 * who can see someone's activity is not another viewer's business
 * (HARMONIQ.md §6).
 */
function ScopeNote({ scope }: { scope: VisibilityScope }) {
  if (scope === "public") return null;
  return (
    <p className="text-tertiary mb-2" style={{ fontSize: 12 }}>
      {scope === "private" ? "Only you can see this." : "Visible to friends."}{" "}
      <Link href="/settings" className="underline underline-offset-2">
        Change
      </Link>
    </p>
  );
}

export default function ListeningSection({
  username,
  token,
  initial,
  isOwnProfile = false,
  scope,
}: ListeningSectionProps) {
  const listening = usePolledListening({ username, token, initial });

  const note = isOwnProfile && scope ? <ScopeNote scope={scope} /> : null;

  if (!listening.connected) {
    // "No activity yet" conflated an unlinked account with a quiet one. Only
    // the owner can act on this, and only they are told which it is.
    return (
      <>
        {note}
        <p className="text-tertiary" style={{ fontSize: 13 }}>
          {isOwnProfile ? (
            <>
              Spotify isn&rsquo;t connected.{" "}
              <Link href="/settings" className="underline underline-offset-2">
                Connect it in settings
              </Link>
              .
            </>
          ) : (
            "No listening activity yet."
          )}
        </p>
      </>
    );
  }

  const hasAnything = listening.now_playing || listening.recently_played.length > 0;
  if (!hasAnything) {
    return (
      <>
        {note}
        <p className="text-tertiary" style={{ fontSize: 13 }}>
          Nothing played recently.
        </p>
      </>
    );
  }

  return (
    <>
      {note}
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
    </>
  );
}
