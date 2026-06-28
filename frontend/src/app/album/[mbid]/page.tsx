import Link from "next/link";
import { notFound } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import AppShell from "@/components/AppShell";
import CoverArt from "@/components/CoverArt";
import RatingSection from "@/components/RatingSection";
import { getAlbum } from "@/lib/catalog";

function formatDuration(ms: number | null): string {
  if (ms === null) return "";
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export default async function AlbumPage(props: { params: Promise<{ mbid: string }> }) {
  const { mbid } = await props.params;
  const { getToken } = await auth();
  const token = await getToken().catch(() => null);

  let album;
  try {
    album = await getAlbum(mbid, token ?? undefined);
  } catch (err: unknown) {
    const status = err instanceof Error && err.message.includes("404") ? 404 : 503;
    if (status === 404) notFound();
    throw err;
  }

  const typeLabel = album.album_type
    ? album.album_type.charAt(0).toUpperCase() + album.album_type.slice(1)
    : null;

  return (
    <AppShell>
    <main className="mx-auto max-w-2xl px-4 py-10">
      <div className="mb-8 flex items-start gap-5">
        <CoverArt src={album.cover_art_url} alt={album.title} size={120} />
        <div className="min-w-0">
          <h1 className="text-2xl font-light tracking-tight">{album.title}</h1>
          {album.artist_name && album.artist_mbid && (
            <Link
              href={`/artist/${album.artist_mbid}`}
              className="mt-0.5 block text-sm text-secondary hover:text-primary"
            >
              {album.artist_name}
            </Link>
          )}
          <p className="mt-1 text-xs text-tertiary">
            {[album.release_year, typeLabel].filter(Boolean).join(" · ")}
          </p>
        </div>
      </div>

      {album.tracks.length > 0 ? (
        <section>
          <h2 className="mb-3 text-xs font-medium tracking-widest text-tertiary uppercase">
            Tracks in catalog
          </h2>
          <ul className="space-y-px">
            {album.tracks.map((t) => (
              <li key={t.mbid}>
                <Link
                  href={`/track/${t.mbid}`}
                  className="flex items-center gap-3 rounded-nav px-2 py-2 hover:bg-nav-hover"
                >
                  <span className="min-w-0 flex-1 text-sm">{t.title}</span>
                  {t.duration_ms !== null && (
                    <span className="shrink-0 text-xs text-tertiary tabular-nums">
                      {formatDuration(t.duration_ms)}
                    </span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <p className="text-sm text-tertiary">No tracks in catalog yet.</p>
      )}

      <RatingSection
        entityType="album"
        entityMbid={mbid}
        initialReviews={album.reviews}
        initialAggregate={album.aggregate_score}
      />
    </main>
    </AppShell>
  );
}
