"use client";

import Link from "next/link";
import CoverArt from "@/components/CoverArt";
import EqualizerGlyph from "@/components/EqualizerGlyph";
import type { TrackSummary, UserSummary } from "@/types";

// The card renders identity, not internal PKs — API payloads (which carry
// ids) satisfy these structurally, and previews can omit them.
type MelodyTrack = Omit<TrackSummary, "id">;
type MelodyPerson = Omit<UserSummary, "id">;

interface MelodyCardProps {
  track: MelodyTrack;
  /** The other person: sender in an inbox, recipient in a sent list. */
  person: MelodyPerson;
  /** "from" renders "From <name>", "to" renders "To <name>". */
  direction: "from" | "to";
  /** Compact mode drops the glyph and tightens spacing (notification rows). */
  compact?: boolean;
  /** Muted status/outcome line under the person, e.g. "You passed on this". */
  statusLabel?: string;
  /** Quick actions rendered on the right edge (inbox rows). */
  actions?: React.ReactNode;
}

/**
 * The Melody embed: a self-contained music object — cover art, track title,
 * artist, and who it's from. A Melody carries no message; this card IS the
 * gesture. Reused by the inbox, the sent list, the send preview, and
 * (compact) notification rows. Phase 2 seam: preview playback mounts here.
 */
export default function MelodyCard({
  track,
  person,
  direction,
  compact = false,
  statusLabel,
  actions,
}: MelodyCardProps) {
  const size = compact ? 40 : 56;

  return (
    <div
      className="bg-tile border-hairline flex items-center border"
      style={{
        borderRadius: 14,
        padding: compact ? "10px 12px" : "14px 16px",
        gap: compact ? 12 : 16,
      }}
      data-testid="melody-card"
    >
      <CoverArt src={track.cover_art_url} alt={track.title} size={size} />

      <div className="min-w-0 flex-1">
        <div className="flex items-center" style={{ gap: 8 }}>
          {!compact && <EqualizerGlyph fill="#2f8cff" size={11} />}
          <Link
            href={`/track/${track.mbid}`}
            className="text-primary hover:text-secondary block truncate"
            style={{ fontSize: compact ? 13 : 14, fontWeight: 500 }}
          >
            {track.title}
          </Link>
        </div>
        {track.artist_name && (
          <p className="text-secondary truncate" style={{ fontSize: 12, marginTop: 2 }}>
            {track.artist_name}
          </p>
        )}
        <p className="text-tertiary truncate" style={{ fontSize: 12, marginTop: 4 }}>
          {direction === "from" ? "From " : "To "}
          <Link
            href={`/u/${person.username}`}
            className="hover:text-secondary"
          >
            {person.display_name}
          </Link>
          {/* Skip the handle when it adds nothing (e.g. send-preview placeholder). */}
          {person.username !== person.display_name && <span> @{person.username}</span>}
        </p>
        {statusLabel && (
          <p className="text-tertiary" style={{ fontSize: 12, marginTop: 4 }}>
            {statusLabel}
          </p>
        )}
      </div>

      {actions && (
        <div className="flex shrink-0 items-center" style={{ gap: 8 }}>
          {actions}
        </div>
      )}
    </div>
  );
}
