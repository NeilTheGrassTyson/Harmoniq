import Link from "next/link";
import CoverArt from "@/components/CoverArt";
import EqualizerGlyph from "@/components/EqualizerGlyph";

interface TrackTileProps {
  title: string;
  artistName: string | null;
  coverArtUrl: string | null;
  href: string;
  sharedBy?: {
    username: string;
  };
}

export default function TrackTile({
  title,
  artistName,
  coverArtUrl,
  href,
  sharedBy,
}: TrackTileProps) {
  // Friend-sourced tiles are distinguished by artwork tint and a small dot,
  // not by a colored border (DESIGN_SYSTEM §7).
  const isFriend = !!sharedBy;
  const tileBg = isFriend ? "bg-tile-friend" : "bg-tile";
  const glyphColor = isFriend ? "text-icon-friend" : "text-icon-trend";

  return (
    <Link href={href} className="tile-hover block min-w-0">
      {/* Artwork square */}
      <div className={`rounded-control relative aspect-square w-full overflow-hidden ${tileBg}`}>
        {/* Equalizer glyph is always present as the lower layer.
            CoverArt (fill mode) covers it when artwork loads;
            if src is absent or the load fails, the glyph stays visible. */}
        <div className="absolute inset-0 flex items-center justify-center">
          <EqualizerGlyph size={40} className={glyphColor} />
        </div>

        <CoverArt src={coverArtUrl} alt={title} fill />

        {isFriend && (
          <span
            className="bg-friend-dot absolute right-2 bottom-2 block size-1.5 rounded-full" /* unslop-ignore — 6px status dot, circular per DESIGN_SYSTEM §4 */
            aria-hidden="true"
          />
        )}
      </div>

      {/* Text below — no border, no card background, no shadow */}
      <div className="mt-2 min-w-0">
        <p className="font-display text-primary truncate text-sm/[1.3] font-medium">{title}</p>
        {artistName && <p className="text-secondary mt-0.5 truncate text-xs/[1.4]">{artistName}</p>}
        {sharedBy && (
          <p className="text-secondary mt-0.5 truncate text-[11px]">
            <span
              className="bg-friend-dot mr-[5px] inline-block size-[5px] rounded-full align-middle" /* unslop-ignore — 5px inline dot, circular per DESIGN_SYSTEM §4 */
            />
            @{sharedBy.username}
          </p>
        )}
      </div>
    </Link>
  );
}
