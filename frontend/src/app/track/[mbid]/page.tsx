import Link from "next/link";
import { notFound } from "next/navigation";
import CoverArt from "@/components/CoverArt";
import { getTrack } from "@/lib/catalog";

function formatDuration(ms: number | null): string {
  if (ms === null) return "";
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export default async function TrackPage(props: {
  params: Promise<{ mbid: string }>;
}) {
  const { mbid } = await props.params;

  let track;
  try {
    track = await getTrack(mbid);
  } catch (err: unknown) {
    const status =
      err instanceof Error && err.message.includes("404") ? 404 : 503;
    if (status === 404) notFound();
    throw err;
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <div className="mb-8 flex items-start gap-5">
        <CoverArt
          src={track.cover_art_url}
          alt={track.album_title ?? track.title}
          size={80}
        />
        <div className="min-w-0">
          <h1 className="text-2xl font-light tracking-tight">{track.title}</h1>

          {track.artist_name && track.artist_mbid && (
            <Link
              href={`/artist/${track.artist_mbid}`}
              className="mt-0.5 block text-sm text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100"
            >
              {track.artist_name}
            </Link>
          )}

          {track.album_mbid ? (
            <Link
              href={`/album/${track.album_mbid}`}
              className="mt-0.5 block text-sm text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-300"
            >
              {track.album_title ?? "—"}
            </Link>
          ) : (
            <p className="mt-0.5 text-sm text-neutral-400">—</p>
          )}

          {track.duration_ms !== null && (
            <p className="mt-1 text-xs tabular-nums text-neutral-400">
              {formatDuration(track.duration_ms)}
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
