"use client";

// Content depends entirely on the ?q= param. useSearchParams requires a
// Suspense boundary above it so the static prerender of the shell can
// bail out to client rendering for the query-dependent part.

import Link from "next/link";
import Image from "next/image";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import AvatarImage from "@/components/AvatarImage";
import EqualizerGlyph from "@/components/EqualizerGlyph";
import { searchCatalog } from "@/lib/catalog";
import { searchUsers } from "@/lib/users";
import type { SearchResponse, UserSearchResult } from "@/types";

const MAX_PER_SECTION = 10;

type SearchState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "results"; people: UserSearchResult[]; music: SearchResponse | null }
  | { kind: "empty" };

// Weight and tracking follow DESIGN_SYSTEM §3 (500 / 0.6px), matching the
// SearchBar dropdown and Home. This label previously rendered at 600/0.7px,
// which both drifted from the other section labels and broke §3's ceiling of
// 500 on every weight in the system.
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-display text-tertiary mb-1 text-[11px] font-medium tracking-[0.6px] uppercase">
      {children}
    </p>
  );
}

// Hover was previously React state, so pointing at a row re-rendered it. It's
// a CSS concern — and as a class it covers keyboard focus too.
function ResultRow({ children, href }: { children: React.ReactNode; href: string }) {
  return (
    <Link
      href={href}
      className="rounded-control hover:bg-nav-hover flex items-center gap-3 px-3 py-[9px] no-underline transition-colors duration-75"
    >
      {children}
    </Link>
  );
}

function ArtworkBlock({
  src,
  alt,
  round = false,
}: {
  src: string | null | undefined;
  alt: string;
  round?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  // Artists circular, releases at the control radius (DESIGN_SYSTEM §4).
  const radius = round ? "rounded-full" : "rounded-control";

  if (!src || failed) {
    return <span className={`bg-tile block size-10 shrink-0 ${radius}`} aria-hidden="true" />;
  }
  return (
    <span className={`relative block size-10 shrink-0 overflow-hidden ${radius}`}>
      <Image
        src={src}
        alt={alt}
        fill
        sizes="40px"
        className="object-cover"
        onError={() => setFailed(true)}
        unoptimized
      />
    </span>
  );
}

function PrimaryText({ children }: { children: React.ReactNode }) {
  return <span className="text-primary block truncate text-sm font-medium">{children}</span>;
}

function SubText({ children }: { children: React.ReactNode }) {
  return <span className="text-tertiary block truncate text-xs">{children}</span>;
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section className="mb-7">
      <SectionLabel>{label}</SectionLabel>
      <ul className="m-0 list-none p-0">{children}</ul>
    </section>
  );
}

function SearchContent() {
  const searchParams = useSearchParams();
  const q = searchParams.get("q") ?? "";
  // Only the async fetch outcome is state; the view state (idle / loading /
  // empty / results) is derived at render so no setState fires synchronously
  // inside the effect.
  const [fetched, setFetched] = useState<{
    q: string;
    people: UserSearchResult[];
    music: SearchResponse | null;
  } | null>(null);

  useEffect(() => {
    if (q.length < 2) return;

    let cancelled = false;

    Promise.allSettled([searchCatalog(q), searchUsers(q)]).then(([musicSettled, usersSettled]) => {
      if (cancelled) return;

      setFetched({
        q,
        people: usersSettled.status === "fulfilled" ? usersSettled.value : [],
        music: musicSettled.status === "fulfilled" ? musicSettled.value : null,
      });
    });

    return () => {
      cancelled = true;
    };
  }, [q]);

  let state: SearchState;
  if (q.length < 2) {
    state = { kind: "idle" };
  } else if (fetched === null || fetched.q !== q) {
    state = { kind: "loading" };
  } else {
    const hasMusic =
      fetched.music !== null &&
      (fetched.music.artists.length > 0 ||
        fetched.music.albums.length > 0 ||
        fetched.music.tracks.length > 0);
    state =
      fetched.people.length === 0 && !hasMusic
        ? { kind: "empty" }
        : { kind: "results", people: fetched.people, music: fetched.music };
  }

  return (
    <main className="max-w-[680px] px-[22px] pt-[26px] pb-[30px]">
      {q.length < 2 && (
        <div className="text-secondary flex flex-col items-center justify-center gap-3 pt-20">
          <EqualizerGlyph size={36} />
          <p className="font-display m-0 text-sm">Search for music or people</p>
        </div>
      )}

      {state.kind === "loading" && q.length >= 2 && (
        <p className="text-tertiary text-[13px]">Searching…</p>
      )}

      {state.kind === "empty" && (
        <p className="text-tertiary text-[13px]">No results for &ldquo;{q}&rdquo;.</p>
      )}

      {state.kind === "results" && (
        <>
          {state.people.length > 0 && (
            <Section label="People">
              {state.people.slice(0, MAX_PER_SECTION).map((u) => (
                <li key={u.username}>
                  <ResultRow href={`/u/${u.username}`}>
                    <AvatarImage src={u.avatar_url} username={u.username} size={40} />
                    <span className="min-w-0">
                      <PrimaryText>{u.display_name}</PrimaryText>
                      <SubText>@{u.username}</SubText>
                    </span>
                  </ResultRow>
                </li>
              ))}
            </Section>
          )}

          {state.music !== null && state.music.artists.length > 0 && (
            <Section label="Artists">
              {state.music.artists.slice(0, MAX_PER_SECTION).map((a) => (
                <li key={a.mbid}>
                  <ResultRow href={`/artist/${a.mbid}`}>
                    <ArtworkBlock src={a.image_url} alt={a.name} round />
                    <span className="min-w-0">
                      <PrimaryText>{a.name}</PrimaryText>
                      {a.disambiguation && <SubText>{a.disambiguation}</SubText>}
                    </span>
                  </ResultRow>
                </li>
              ))}
            </Section>
          )}

          {state.music !== null && state.music.albums.length > 0 && (
            <Section label="Albums">
              {state.music.albums.slice(0, MAX_PER_SECTION).map((a) => (
                <li key={a.mbid}>
                  <ResultRow href={`/album/${a.mbid}`}>
                    <ArtworkBlock src={a.cover_art_url} alt={a.title} />
                    <span className="min-w-0">
                      <PrimaryText>{a.title}</PrimaryText>
                      <SubText>
                        {[a.artist_name, a.release_year].filter(Boolean).join(" · ")}
                      </SubText>
                    </span>
                  </ResultRow>
                </li>
              ))}
            </Section>
          )}

          {state.music !== null && state.music.tracks.length > 0 && (
            <Section label="Tracks">
              {state.music.tracks.slice(0, MAX_PER_SECTION).map((t) => (
                <li key={t.mbid}>
                  <ResultRow href={`/track/${t.mbid}`}>
                    <span className="min-w-0 flex-1">
                      <PrimaryText>{t.title}</PrimaryText>
                      <SubText>
                        {[t.artist_name, t.album_title].filter(Boolean).join(" · ")}
                      </SubText>
                    </span>
                  </ResultRow>
                </li>
              ))}
            </Section>
          )}
        </>
      )}
    </main>
  );
}

export default function SearchPage() {
  return (
    <AppShell>
      <Suspense fallback={null}>
        <SearchContent />
      </Suspense>
    </AppShell>
  );
}
