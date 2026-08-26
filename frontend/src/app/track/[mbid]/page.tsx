import Link from "next/link";
import { notFound } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import AppShell from "@/components/AppShell";
import ServiceUnavailable from "@/components/ServiceUnavailable";
import CoverArt from "@/components/CoverArt";
import RatingSection from "@/components/RatingSection";
import SendMelodyPanel from "@/components/SendMelodyPanel";
import { getTrack } from "@/lib/catalog";
import { errorStatus, isUpstreamFailure } from "@/lib/apiBase";
import { getEntityRatings } from "@/lib/ratings";

function formatDuration(ms: number | null): string {
  if (ms === null) return "";
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export default async function TrackPage(props: { params: Promise<{ mbid: string }> }) {
  const { mbid } = await props.params;
  const { getToken } = await auth();
  const token = await getToken().catch(() => null);

  // Catalog metadata (cached) and reviews (viewer-scoped, never cached) are
  // separate requests, issued in parallel. A ratings failure degrades to an
  // empty review list rather than breaking the page.
  const ratingsPromise = getEntityRatings("track", mbid, token ?? undefined).catch(() => ({
    aggregate_score: null,
    reviews: [],
  }));

  let track;
  try {
    track = await getTrack(mbid);
  } catch (err: unknown) {
    if (errorStatus(err) === 404) notFound();
    // An unreachable or failing backend renders in place, keeping the
    // shell and navigation. Anything else is unexpected and belongs in
    // the error boundary, where its digest is recorded.
    if (isUpstreamFailure(err)) {
      return (
        <AppShell>
          <ServiceUnavailable what="this track" />
        </AppShell>
      );
    }
    throw err;
  }

  const ratings = await ratingsPromise;

  return (
    <AppShell>
      <main className="mx-auto max-w-2xl px-4 py-10">
        <div className="mb-8 flex items-start gap-5">
          <CoverArt src={track.cover_art_url} alt={track.album_title ?? track.title} size={80} />
          <div className="min-w-0">
            <h1 className="text-2xl font-light tracking-tight">{track.title}</h1>

            {track.artist_name && track.artist_mbid && (
              <Link
                href={`/artist/${track.artist_mbid}`}
                className="text-secondary hover:text-primary mt-0.5 block text-sm"
              >
                {track.artist_name}
              </Link>
            )}

            {track.album_mbid ? (
              <Link
                href={`/album/${track.album_mbid}`}
                className="text-tertiary hover:text-secondary mt-0.5 block text-sm"
              >
                {track.album_title ?? "—"}
              </Link>
            ) : (
              <p className="text-tertiary mt-0.5 text-sm">—</p>
            )}

            {track.duration_ms !== null && (
              <p className="text-tertiary mt-1 text-xs tabular-nums">
                {formatDuration(track.duration_ms)}
              </p>
            )}
          </div>
        </div>

        <SendMelodyPanel
          track={{
            mbid,
            title: track.title,
            artist_name: track.artist_name,
            cover_art_url: track.cover_art_url,
          }}
        />

        <RatingSection
          entityType="track"
          entityMbid={mbid}
          initialReviews={ratings.reviews}
          initialAggregate={ratings.aggregate_score}
        />
      </main>
    </AppShell>
  );
}
