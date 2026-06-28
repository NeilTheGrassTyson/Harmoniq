"use client";

// Fully dynamic page — prerendering is not useful here since content depends
// entirely on ?q= param. useSearchParams is safe without an outer Suspense
// boundary when the component is never statically prerendered.

import Link from "next/link";
import Image from "next/image";
import { useEffect, useState } from "react";
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

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p
      style={{
        fontSize: 11,
        fontWeight: 600,
        textTransform: "uppercase",
        letterSpacing: "0.7px",
        color: "#757c8c",
        marginBottom: 4,
        fontFamily: "var(--font-space-grotesk), system-ui, sans-serif",
      }}
    >
      {children}
    </p>
  );
}

function ResultRow({ children, href }: { children: React.ReactNode; href: string }) {
  const [hovered, setHovered] = useState(false);
  return (
    <Link
      href={href}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "9px 12px",
        borderRadius: 8,
        textDecoration: "none",
        background: hovered ? "rgba(255,255,255,0.04)" : "transparent",
        transition: "background 80ms ease",
      }}
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
  if (!src || failed) {
    return (
      <span
        style={{
          display: "block",
          width: 40,
          height: 40,
          flexShrink: 0,
          backgroundColor: "#151821",
          borderRadius: round ? "50%" : 8,
        }}
      />
    );
  }
  return (
    <span
      style={{
        display: "block",
        position: "relative",
        width: 40,
        height: 40,
        flexShrink: 0,
        overflow: "hidden",
        borderRadius: round ? "50%" : 8,
      }}
    >
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
  return (
    <span
      style={{
        display: "block",
        fontSize: 14,
        fontWeight: 500,
        color: "#f2f3f5",
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}

function SubText({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        display: "block",
        fontSize: 12,
        color: "#757c8c",
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}

function Section({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <section style={{ marginBottom: 28 }}>
      <SectionLabel>{label}</SectionLabel>
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>{children}</ul>
    </section>
  );
}

export default function SearchPage() {
  const searchParams = useSearchParams();
  const q = searchParams.get("q") ?? "";
  const [state, setState] = useState<SearchState>({ kind: "idle" });

  useEffect(() => {
    if (q.length < 2) {
      setState({ kind: "idle" });
      return;
    }

    setState({ kind: "loading" });

    let cancelled = false;

    Promise.allSettled([searchCatalog(q), searchUsers(q)]).then(
      ([musicSettled, usersSettled]) => {
        if (cancelled) return;

        const music =
          musicSettled.status === "fulfilled" ? musicSettled.value : null;
        const people =
          usersSettled.status === "fulfilled" ? usersSettled.value : [];

        const hasMusic =
          music !== null &&
          (music.artists.length > 0 ||
            music.albums.length > 0 ||
            music.tracks.length > 0);

        if (people.length === 0 && !hasMusic) {
          setState({ kind: "empty" });
        } else {
          setState({ kind: "results", people, music });
        }
      }
    );

    return () => {
      cancelled = true;
    };
  }, [q]);

  return (
    <AppShell>
      <main style={{ padding: "26px 22px 30px", maxWidth: 680 }}>
        {q.length < 2 && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              paddingTop: 80,
              gap: 12,
              color: "#8b93a3",
            }}
          >
            <EqualizerGlyph size={36} fill="#8b93a3" />
            <p
              style={{
                margin: 0,
                fontSize: 14,
                fontFamily: "var(--font-space-grotesk), system-ui, sans-serif",
              }}
            >
              Search for music or people
            </p>
          </div>
        )}

        {state.kind === "loading" && q.length >= 2 && (
          <p style={{ fontSize: 13, color: "#757c8c" }}>Searching…</p>
        )}

        {state.kind === "empty" && (
          <p style={{ fontSize: 13, color: "#757c8c" }}>
            No results for &ldquo;{q}&rdquo;.
          </p>
        )}

        {state.kind === "results" && (
          <>
            {state.people.length > 0 && (
              <Section label="People">
                {state.people.slice(0, MAX_PER_SECTION).map((u) => (
                  <li key={u.username}>
                    <ResultRow href={`/u/${u.username}`}>
                      <AvatarImage
                        src={u.avatar_url}
                        username={u.username}
                        size={40}
                      />
                      <span style={{ minWidth: 0 }}>
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
                      <span style={{ minWidth: 0 }}>
                        <PrimaryText>{a.name}</PrimaryText>
                        {a.disambiguation && (
                          <SubText>{a.disambiguation}</SubText>
                        )}
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
                      <span style={{ minWidth: 0 }}>
                        <PrimaryText>{a.title}</PrimaryText>
                        <SubText>
                          {[a.artist_name, a.release_year]
                            .filter(Boolean)
                            .join(" · ")}
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
                      <span style={{ minWidth: 0, flex: 1 }}>
                        <PrimaryText>{t.title}</PrimaryText>
                        <SubText>
                          {[t.artist_name, t.album_title]
                            .filter(Boolean)
                            .join(" · ")}
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
    </AppShell>
  );
}
