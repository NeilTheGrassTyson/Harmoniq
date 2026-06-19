import Link from "next/link";
import { notFound } from "next/navigation";
import CoverArt from "@/components/CoverArt";
import { getAlbum } from "@/lib/catalog";

function formatDuration(ms: number | null): string {
  if (ms === null) return "";
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export default async function AlbumPage(props: {
  params: Promise<{ mbid: string }>;
}) {
  const { mbid } = await props.params;

  let album;
  try {
    album = await getAlbum(mbid);
  } catch (err: unknown) {
    const status =
      err instanceof Error && err.message.includes("404") ? 404 : 503;
    if (status === 404) notFound();
    throw err;
  }

  const typeLabel = album.album_type
    ? album.album_type.charAt(0).toUpperCase() + album.album_type.slice(1)
    : null;

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <div className="mb-8 flex items-start gap-5">
        <CoverArt src={album.cover_art_url} alt={album.title} size={120} />
        <div className="min-w-0">
          <h1 className="text-2xl font-light tracking-tight">{album.title}</h1>
          {album.artist_name && album.artist_mbid && (
            <Link
              href={`/artist/${album.artist_mbid}`}
              className="mt-0.5 block text-sm text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100"
            >
              {album.artist_name}
            </Link>
          )}
          <p className="mt-1 text-xs text-neutral-400">
            {[album.release_year, typeLabel].filter(Boolean).join(" · ")}
          </p>
        </div>
      </div>

      {album.tracks.length > 0 ? (
        <section>
          <h2 className="mb-3 text-xs font-medium uppercase tracking-widest text-neutral-400">
            Tracks in catalog
          </h2>
          <ul className="space-y-px">
            {album.tracks.map((t) => (
              <li key={t.mbid}>
                <Link
                  href={`/track/${t.mbid}`}
                  className="flex items-center gap-3 rounded px-2 py-2 hover:bg-neutral-50 dark:hover:bg-neutral-800"
                >
                  <span className="min-w-0 flex-1 text-sm">{t.title}</span>
                  {t.duration_ms !== null && (
                    <span className="shrink-0 text-xs tabular-nums text-neutral-400">
                      {formatDuration(t.duration_ms)}
                    </span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <p className="text-sm text-neutral-400">No tracks in catalog yet.</p>
      )}
    </main>
  );
}
