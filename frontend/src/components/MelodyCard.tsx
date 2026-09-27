"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";
import CoverArt from "@/components/CoverArt";
import EqualizerGlyph from "@/components/EqualizerGlyph";
import { formatStamp, type MelodyStamp } from "@/lib/melodyStamps";
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
  /** Received / Sent, then Accepted / Opened / Passed — label, then local time. */
  stamps?: MelodyStamp[];
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
  stamps,
  actions,
}: MelodyCardProps) {
  const size = compact ? 40 : 56;

  return (
    <div
      className="bg-tile border-hairline flex flex-wrap items-center border"
      style={{
        borderRadius: 14,
        padding: compact ? "10px 12px" : "14px 16px",
        columnGap: compact ? 12 : 16,
        rowGap: 12,
      }}
      data-testid="melody-card"
    >
      <CoverArt src={track.cover_art_url} alt={track.title} size={size} />

      <div className="min-w-0 flex-1">
        <div className="flex items-center" style={{ gap: 8 }}>
          {!compact && <EqualizerGlyph size={11} className="text-accent" />}
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
          <Link href={`/u/${person.username}`} className="hover:text-secondary">
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
        {stamps && stamps.length > 0 && (
          <dl
            className="font-label text-tertiary mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-[3px]"
            data-testid="melody-stamps"
          >
            {stamps.map((stamp) => (
              <div key={stamp.label} className="contents">
                <dt className="text-[9.5px] leading-[16px] font-bold tracking-[1px] uppercase">
                  {stamp.label}
                </dt>
                <dd className="text-[11px] leading-[16px] whitespace-nowrap">
                  <LocalTime iso={stamp.at} />
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>

      {/* Below sm the actions take their own row, under the text: beside it
          they squeezed a 390px card until the time stamps wrapped a word per
          line. From sm up there is room, and they sit on the right. */}
      {actions && (
        <div
          className="flex shrink-0 basis-full items-center pl-[72px] sm:basis-auto sm:pl-0"
          style={{ gap: 8 }}
        >
          {actions}
        </div>
      )}
    </div>
  );
}

const noSubscription = () => () => {};

/**
 * Formatted in the viewer's own time zone, so only after mount: a server-
 * rendered time would be the server's zone and mismatch on hydration. Until
 * then the row holds its height with a non-breaking space.
 */
function LocalTime({ iso }: { iso: string }) {
  const mounted = useSyncExternalStore(
    noSubscription,
    () => true,
    () => false
  );
  return <time dateTime={iso}>{mounted ? formatStamp(iso) : "\u00a0"}</time>;
}
