"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import AvatarImage from "@/components/AvatarImage";
import { searchCatalog } from "@/lib/catalog";
import { searchUsers } from "@/lib/users";
import type { SearchResponse, UserSearchResult } from "@/types";

function formatDuration(ms: number | null): string {
  if (ms === null) return "";
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

/* Minimal music-note glyph for tracks — inline SVG avoids emoji */
function MusicNoteIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M9 18V5l12-2v13"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="6" cy="18" r="3" stroke="currentColor" strokeWidth="2" />
      <circle cx="18" cy="16" r="3" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

type PanelState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "empty"; query: string }
  | { kind: "results"; people: UserSearchResult[]; music: SearchResponse | null };

// Shared row/section classes. Hover lives in CSS rather than onMouseEnter /
// onMouseLeave handlers so it also covers touch and keyboard focus.
const ROW =
  "text-primary hover:bg-nav-hover flex cursor-pointer items-center gap-[10px] px-[14px] py-2 text-[13px] no-underline";
const ROW_TITLE = "block truncate font-medium";
const ROW_SUB = "text-tertiary block truncate text-[11px]";
const PANEL_MSG = "text-tertiary px-[14px] py-[10px] text-[13px]";
const SECTION_DIVIDER = "border-hairline border-t";

function ResultLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-display text-tertiary px-[14px] pt-[10px] pb-1 text-[11px] font-medium tracking-[0.6px] uppercase">
      {children}
    </p>
  );
}

export default function SearchBar() {
  const [query, setQuery] = useState("");
  const [panel, setPanel] = useState<PanelState>({ kind: "idle" });
  const containerRef = useRef<HTMLDivElement>(null);
  const pathname = usePathname();
  const router = useRouter();
  // URL sync and dropdown fetches run only after the user has actually typed.
  // Without this gate, mounting on /search?q=… would push a bare /search
  // (stripping the query), and dismissing the panel after a result click
  // would fire a competing navigation that cancels the click's.
  const hasEdited = useRef(false);

  // Restore the query text when landing directly on /search?q=… so the
  // header input matches the page body. hasEdited stays false: no refetch,
  // no URL push, no uninvited dropdown. Deferred a tick so no state update
  // fires synchronously inside the effect body.
  useEffect(() => {
    if (pathname !== "/search") return;
    const q = new URLSearchParams(window.location.search).get("q");
    if (!q) return;
    const t = setTimeout(() => setQuery(q), 0);
    return () => clearTimeout(t);
    // Mount-only by design; later query changes are user-driven.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setPanel({ kind: "idle" });
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    if (!hasEdited.current) return;
    const trimmed = query.trim();

    if (trimmed.length < 2) {
      // Clear URL param when query is cleared on /search
      if (pathname === "/search") {
        router.push("/search");
      }
      return;
    }

    const timeout = setTimeout(async () => {
      // Sync URL on the /search page so the page body stays in sync
      if (pathname === "/search") {
        router.push(`/search?q=${encodeURIComponent(trimmed)}`);
      }

      setPanel({ kind: "loading" });

      const [musicSettled, usersSettled] = await Promise.allSettled([
        searchCatalog(trimmed),
        searchUsers(trimmed),
      ]);

      const music = musicSettled.status === "fulfilled" ? musicSettled.value : null;
      const people = usersSettled.status === "fulfilled" ? usersSettled.value : [];
      const bothFailed = musicSettled.status === "rejected" && usersSettled.status === "rejected";

      if (bothFailed) {
        setPanel({ kind: "error" });
        return;
      }

      const hasMusic =
        music !== null &&
        (music.artists.length > 0 || music.albums.length > 0 || music.tracks.length > 0);

      if (people.length === 0 && !hasMusic) {
        setPanel({ kind: "empty", query: trimmed });
        return;
      }

      setPanel({ kind: "results", people, music });
    }, 300);

    return () => clearTimeout(timeout);
  }, [query, pathname, router]);

  // Close the panel WITHOUT clearing the query: clearing would re-trigger
  // the URL-sync effect mid-navigation and cancel the clicked link.
  const dismiss = () => {
    setPanel({ kind: "idle" });
  };

  const derivedPanel: PanelState = query.trim().length < 2 ? { kind: "idle" } : panel;
  // On /search the page body renders the same results — a dropdown on top
  // of them is duplicate content that occludes the page.
  const showPanel = derivedPanel.kind !== "idle" && pathname !== "/search";

  return (
    <div ref={containerRef} className="relative w-full">
      <input
        type="search"
        value={query}
        onChange={(e) => {
          hasEdited.current = true;
          setQuery(e.target.value);
        }}
        onKeyDown={(e) => {
          // Escape closes the dropdown only — the browser's native
          // clear-the-input behavior would wipe the query and results.
          if (e.key === "Escape") {
            e.preventDefault();
            setPanel({ kind: "idle" });
          }
        }}
        placeholder="search"
        aria-label="Search artists, albums, tracks, and people"
        aria-expanded={showPanel}
        aria-haspopup="listbox"
        className="search-focus bg-control border-hairline rounded-control text-primary w-full border px-3 py-1.5 text-[13px] outline-none"
        autoComplete="off"
        spellCheck={false}
      />

      {showPanel && (
        <div className="bg-sidebar border-hairline rounded-control absolute top-[calc(100%+4px)] left-0 z-50 w-full min-w-[280px] overflow-hidden border">
          {derivedPanel.kind === "loading" && <p className={PANEL_MSG}>Searching…</p>}

          {derivedPanel.kind === "error" && (
            <p className={PANEL_MSG}>
              Couldn&rsquo;t reach the search service right now. Try again in a moment.
            </p>
          )}

          {derivedPanel.kind === "empty" && (
            <p className={PANEL_MSG}>No results for &ldquo;{derivedPanel.query}&rdquo;.</p>
          )}

          {derivedPanel.kind === "results" && (
            <div>
              {/* People section — shown first, only when results exist */}
              {derivedPanel.people.length > 0 && (
                <section>
                  <ResultLabel>People</ResultLabel>
                  <ul>
                    {derivedPanel.people.map((u) => (
                      <li key={u.username}>
                        <Link href={`/u/${u.username}`} onClick={dismiss} className={ROW}>
                          <AvatarImage src={u.avatar_url} username={u.username} size={28} />
                          <span className="min-w-0">
                            <span className={ROW_TITLE}>{u.display_name}</span>
                            <span className={ROW_SUB}>@{u.username}</span>
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Music sections — only shown when music search succeeded */}
              {derivedPanel.music !== null && (
                <>
                  {derivedPanel.music.artists.length > 0 && (
                    <section className={derivedPanel.people.length > 0 ? SECTION_DIVIDER : ""}>
                      <ResultLabel>Artists</ResultLabel>
                      <ul>
                        {derivedPanel.music.artists.map((a) => (
                          <li key={a.mbid}>
                            <Link href={`/artist/${a.mbid}`} onClick={dismiss} className={ROW}>
                              <ArtworkThumb src={a.image_url} alt={a.name} round />
                              <span className="min-w-0">
                                <span className={ROW_TITLE}>{a.name}</span>
                                {a.disambiguation && (
                                  <span className={ROW_SUB}>{a.disambiguation}</span>
                                )}
                              </span>
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}

                  {derivedPanel.music.albums.length > 0 && (
                    <section className={SECTION_DIVIDER}>
                      <ResultLabel>Albums</ResultLabel>
                      <ul>
                        {derivedPanel.music.albums.map((a) => (
                          <li key={a.mbid}>
                            <Link href={`/album/${a.mbid}`} onClick={dismiss} className={ROW}>
                              <ArtworkThumb src={a.cover_art_url} alt={a.title} />
                              <span className="min-w-0">
                                <span className={ROW_TITLE}>{a.title}</span>
                                <span className={ROW_SUB}>
                                  {[a.artist_name, a.release_year].filter(Boolean).join(" · ")}
                                </span>
                              </span>
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}

                  {derivedPanel.music.tracks.length > 0 && (
                    <section className={SECTION_DIVIDER}>
                      <ResultLabel>Tracks</ResultLabel>
                      <ul>
                        {derivedPanel.music.tracks.map((t) => (
                          <li key={t.mbid}>
                            <Link href={`/track/${t.mbid}`} onClick={dismiss} className={ROW}>
                              <span className="rounded-nav bg-tile text-icon-trend flex size-8 shrink-0 items-center justify-center">
                                <MusicNoteIcon />
                              </span>
                              <span className="min-w-0 flex-1">
                                <span className={ROW_TITLE}>{t.title}</span>
                                <span className={ROW_SUB}>
                                  {[t.artist_name, t.album_title].filter(Boolean).join(" · ")}
                                </span>
                              </span>
                              {t.duration_ms !== null && (
                                <span className="text-tertiary shrink-0 text-[11px] tabular-nums">
                                  {formatDuration(t.duration_ms)}
                                </span>
                              )}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ArtworkThumb({
  src,
  alt,
  round = false,
}: {
  src: string | null | undefined;
  alt: string;
  round?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  // Artists render circular, releases at the nav radius (DESIGN_SYSTEM §4).
  const radius = round ? "rounded-full" : "rounded-nav";

  if (!src || failed) {
    return <span className={`bg-tile block size-8 shrink-0 ${radius}`} aria-hidden="true" />;
  }

  return (
    <span className={`relative block size-8 shrink-0 overflow-hidden ${radius}`}>
      <Image
        src={src}
        alt={alt}
        fill
        sizes="32px"
        className="object-cover"
        onError={() => setFailed(true)}
        unoptimized
      />
    </span>
  );
}
