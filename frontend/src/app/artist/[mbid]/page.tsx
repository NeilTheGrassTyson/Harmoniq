import Link from "next/link";
import { notFound } from "next/navigation";
import AppShell from "@/components/AppShell";
import CoverArt from "@/components/CoverArt";
import { getArtist } from "@/lib/catalog";
import type { AlbumResult } from "@/types";

// Discography sections, in display order. The backend only returns these
// three types (live/compilation/etc. are filtered out at the source).
const SECTIONS: { type: string; label: string }[] = [
  { type: "album", label: "Albums" },
  { type: "ep", label: "EPs" },
  { type: "single", label: "Singles" },
];

function DiscographySection({ label, albums }: { label: string; albums: AlbumResult[] }) {
  if (albums.length === 0) return null;
  return (
    <section className="mb-8">
      <h2 className="text-tertiary mb-3 text-xs font-medium tracking-widest uppercase">{label}</h2>
      <ul className="space-y-1">
        {albums.map((a) => (
          <li key={a.mbid}>
            <Link
              href={`/album/${a.mbid}`}
              className="rounded-nav hover:bg-nav-hover flex items-center gap-3 p-2"
            >
              <CoverArt src={a.cover_art_url} alt={a.title} size={40} />
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium">{a.title}</span>
                {a.release_year && <span className="text-tertiary text-xs">{a.release_year}</span>}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default async function ArtistPage(props: { params: Promise<{ mbid: string }> }) {
  const { mbid } = await props.params;

  let artist;
  try {
    artist = await getArtist(mbid);
  } catch (err: unknown) {
    const status = (err as { status?: number }).status;
    if (status === 404) notFound();
    throw err;
  }

  return (
    <AppShell>
      <main className="mx-auto max-w-2xl px-4 py-10">
        <div className="mb-8 flex items-start gap-5">
          <CoverArt
            src={artist.image_url}
            alt={artist.name}
            size={80}
            className="rounded-full" /* unslop-ignore — artist photo, circular per DESIGN_SYSTEM §4 */
          />
          <div className="min-w-0">
            <h1 className="text-2xl font-light tracking-tight">{artist.name}</h1>
            {artist.disambiguation && (
              <p className="text-tertiary mt-0.5 text-sm">{artist.disambiguation}</p>
            )}
          </div>
        </div>

        {artist.albums.length > 0 ? (
          SECTIONS.map(({ type, label }) => (
            <DiscographySection
              key={type}
              label={label}
              albums={artist.albums.filter((a) => a.album_type === type)}
            />
          ))
        ) : (
          <p className="text-tertiary text-sm">No releases in catalog yet.</p>
        )}
      </main>
    </AppShell>
  );
}
