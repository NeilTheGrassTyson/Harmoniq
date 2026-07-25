import Skeleton from "@/components/skeletons/Skeleton";

/**
 * Loading placeholders for the catalog detail pages.
 *
 * Catalog reads can be slow on a cache miss — MusicBrainz ingestion happens
 * on demand, and album/track detail is deliberately uncached because it embeds
 * visibility-scoped reviews (see lib/catalog.ts). Without a placeholder the
 * whole navigation stalls on a blank frame, which is what made browsing feel
 * unresponsive. Each skeleton mirrors its page's real geometry — same
 * max-width, padding, cover size and line rhythm — so nothing jumps when the
 * data lands.
 */

function Line({
  w,
  h = 16,
  className = "",
}: {
  w: string | number;
  h?: number;
  className?: string;
}) {
  return <Skeleton className={`rounded-nav ${className}`} style={{ width: w, height: h }} />;
}

/** Wraps a page-level skeleton and announces the load to assistive tech. */
function LoadingMain({ children }: { children: React.ReactNode }) {
  return (
    <main role="status" aria-busy="true" className="mx-auto max-w-2xl px-4 py-10">
      <span className="sr-only">Loading</span>
      {children}
    </main>
  );
}

function RowList({ rows, thumb }: { rows: number; thumb?: number }) {
  return (
    <ul className={thumb ? "space-y-1" : "space-y-px"}>
      {Array.from({ length: rows }, (_, i) => (
        <li key={i} className={`flex items-center gap-3 ${thumb ? "p-2" : "px-2 py-2"}`}>
          {thumb && (
            <Skeleton
              className="rounded-control shrink-0"
              style={{ width: thumb, height: thumb }}
            />
          )}
          <Line w={`${68 - i * 6}%`} h={14} />
        </li>
      ))}
    </ul>
  );
}

function SectionLabelSkeleton() {
  return <Line w={110} h={11} className="mb-3" />;
}

export function AlbumSkeleton() {
  return (
    <LoadingMain>
      <div className="mb-8 flex items-start gap-5">
        <Skeleton className="rounded-control shrink-0" style={{ width: 120, height: 120 }} />
        <div className="min-w-0 flex-1 space-y-2">
          <Line w="62%" h={26} />
          <Line w="38%" h={14} />
          <Line w="24%" h={12} />
        </div>
      </div>
      <SectionLabelSkeleton />
      <RowList rows={6} />
    </LoadingMain>
  );
}

export function ArtistSkeleton() {
  return (
    <LoadingMain>
      <div className="mb-8 flex items-start gap-5">
        {/* Artist portraits are circular per DESIGN_SYSTEM §4. */}
        <Skeleton className="shrink-0 rounded-full" style={{ width: 80, height: 80 }} />
        <div className="min-w-0 flex-1 space-y-2">
          <Line w="52%" h={26} />
          <Line w="34%" h={14} />
        </div>
      </div>
      <SectionLabelSkeleton />
      <RowList rows={4} thumb={40} />
    </LoadingMain>
  );
}

export function TrackSkeleton() {
  return (
    <LoadingMain>
      <div className="mb-8 flex items-start gap-5">
        <Skeleton className="rounded-control shrink-0" style={{ width: 80, height: 80 }} />
        <div className="min-w-0 flex-1 space-y-2">
          <Line w="56%" h={26} />
          <Line w="36%" h={14} />
          <Line w="30%" h={14} />
          <Line w="12%" h={12} />
        </div>
      </div>
      <SectionLabelSkeleton />
      <RowList rows={3} />
    </LoadingMain>
  );
}
