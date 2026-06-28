import Link from "next/link";
import { notFound } from "next/navigation";
import AppShell from "@/components/AppShell";
import CoverArt from "@/components/CoverArt";
import { getArtist } from "@/lib/catalog";

export default async function ArtistPage(props: { params: Promise<{ mbid: string }> }) {
  const { mbid } = await props.params;

  let artist;
  try {
    artist = await getArtist(mbid);
  } catch (err: unknown) {
    const status = err instanceof Error && err.message.includes("404") ? 404 : 503;
    if (status === 404) notFound();
    throw err;
  }

  return (
    <AppShell>
    <main className="mx-auto max-w-2xl px-4 py-10">
      <div className="mb-8 flex items-start gap-5">
        <CoverArt src={artist.image_url} alt={artist.name} size={80} className="rounded-full" /* unslop-ignore — artist photo, circular per DESIGN_SYSTEM §4 */ />
        <div className="min-w-0">
          <h1 className="text-2xl font-light tracking-tight">{artist.name}</h1>
          {artist.disambiguation && (
            <p className="mt-0.5 text-sm text-tertiary">{artist.disambiguation}</p>
          )}
        </div>
      </div>

      {artist.albums.length > 0 ? (
        <section>
          <h2 className="mb-3 text-xs font-medium tracking-widest text-tertiary uppercase">
            Albums in catalog
          </h2>
          <ul className="space-y-1">
            {artist.albums.map((a) => (
              <li key={a.mbid}>
                <Link
                  href={`/album/${a.mbid}`}
                  className="flex items-center gap-3 rounded-nav p-2 hover:bg-nav-hover"
                >
                  <CoverArt src={a.cover_art_url} alt={a.title} size={40} />
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{a.title}</span>
                    {a.release_year && (
                      <span className="text-xs text-tertiary">{a.release_year}</span>
                    )}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <p className="text-sm text-tertiary">No albums in catalog yet.</p>
      )}
    </main>
    </AppShell>
  );
}
