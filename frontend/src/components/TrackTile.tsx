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
  const isFriend = !!sharedBy;
  const tileBg = isFriend ? "#121a2a" : "#151821";
  const glyphFill = isFriend ? "#34507c" : "#343b4d";

  return (
    <Link href={href} className="tile-hover block min-w-0">
      {/* Artwork square */}
      <div
        className="rounded-control relative w-full overflow-hidden"
        style={{ aspectRatio: "1 / 1", backgroundColor: tileBg }}
      >
        {/* Equalizer glyph is always present as the lower layer.
            CoverArt (fill mode) covers it when artwork loads;
            if src is absent or the load fails, the glyph stays visible. */}
        <div className="absolute inset-0 flex items-center justify-center">
          <EqualizerGlyph fill={glyphFill} size={40} />
        </div>

        <CoverArt src={coverArtUrl} alt={title} fill />

        {isFriend && (
          <span
            className="absolute right-2 bottom-2 block rounded-full" /* unslop-ignore — 6px status dot, circular per DESIGN_SYSTEM §4 */
            style={{ width: 6, height: 6, backgroundColor: "#5a8fd6" }}
            aria-hidden="true"
          />
        )}
      </div>

      {/* Text below — no border, no card background, no shadow */}
      <div className="mt-2 min-w-0">
        <p
          className="font-display text-primary truncate"
          style={{ fontSize: 14, fontWeight: 500, lineHeight: "1.3" }}
        >
          {title}
        </p>
        {artistName && (
          <p
            className="text-secondary truncate"
            style={{ fontSize: 12, lineHeight: "1.4", marginTop: 2 }}
          >
            {artistName}
          </p>
        )}
        {sharedBy && (
          <p className="text-secondary truncate" style={{ fontSize: 11, marginTop: 2 }}>
            <span
              className="inline-block rounded-full" /* unslop-ignore — 5px inline dot, circular per DESIGN_SYSTEM §4 */
              style={{
                width: 5,
                height: 5,
                backgroundColor: "#5a8fd6",
                marginRight: 5,
                verticalAlign: "middle",
              }}
            />
            @{sharedBy.username}
          </p>
        )}
      </div>
    </Link>
  );
}
