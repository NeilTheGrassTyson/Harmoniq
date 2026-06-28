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

function ResultLabel({ children }: { children: React.ReactNode }) {
  return (
    <p
      style={{
        padding: "10px 14px 4px",
        fontSize: 11,
        fontWeight: 500,
        textTransform: "uppercase",
        letterSpacing: "0.6px",
        color: "#757c8c",
        fontFamily: "var(--font-space-grotesk), system-ui, sans-serif",
      }}
    >
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

  const dismiss = () => {
    setQuery("");
    setPanel({ kind: "idle" });
  };

  const derivedPanel: PanelState = query.trim().length < 2 ? { kind: "idle" } : panel;
  const showPanel = derivedPanel.kind !== "idle";

  const inputStyle: React.CSSProperties = {
    width: "100%",
    backgroundColor: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.07)",
    borderRadius: 8,
    padding: "6px 12px",
    fontSize: 13,
    color: "#f2f3f5",
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  };

  const panelStyle: React.CSSProperties = {
    position: "absolute",
    top: "calc(100% + 4px)",
    left: 0,
    zIndex: 50,
    width: "100%",
    minWidth: 280,
    backgroundColor: "#0e1015",
    border: "1px solid rgba(255,255,255,0.07)",
    borderRadius: 8,
    overflow: "hidden",
  };

  const rowStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "8px 14px",
    fontSize: 13,
    color: "#f2f3f5",
    textDecoration: "none",
    cursor: "pointer",
  };

  const hoverHandlers = {
    onMouseEnter: (e: React.MouseEvent<HTMLAnchorElement>) => {
      (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.04)";
    },
    onMouseLeave: (e: React.MouseEvent<HTMLAnchorElement>) => {
      (e.currentTarget as HTMLElement).style.background = "transparent";
    },
  };

  return (
    <div ref={containerRef} style={{ position: "relative", width: "100%" }}>
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="search"
        aria-label="Search artists, albums, tracks, and people"
        aria-expanded={showPanel}
        aria-haspopup="listbox"
        className="search-focus"
        style={{ ...inputStyle, outline: "none" }}
        autoComplete="off"
        spellCheck={false}
      />

      {showPanel && (
        <div style={panelStyle}>
          {derivedPanel.kind === "loading" && (
            <p style={{ padding: "10px 14px", fontSize: 13, color: "#757c8c" }}>Searching…</p>
          )}

          {derivedPanel.kind === "error" && (
            <p style={{ padding: "10px 14px", fontSize: 13, color: "#757c8c" }}>
              Couldn&rsquo;t reach the search service right now. Try again in a moment.
            </p>
          )}

          {derivedPanel.kind === "empty" && (
            <p style={{ padding: "10px 14px", fontSize: 13, color: "#757c8c" }}>
              No results for &ldquo;{derivedPanel.query}&rdquo;.
            </p>
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
                        <Link
                          href={`/u/${u.username}`}
                          onClick={dismiss}
                          style={rowStyle}
                          {...hoverHandlers}
                        >
                          <AvatarImage src={u.avatar_url} username={u.username} size={28} />
                          <span style={{ minWidth: 0 }}>
                            <span
                              style={{
                                display: "block",
                                fontWeight: 500,
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {u.display_name}
                            </span>
                            <span
                              style={{
                                display: "block",
                                fontSize: 11,
                                color: "#757c8c",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }}
                            >
                              @{u.username}
                            </span>
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
                    <section
                      style={
                        derivedPanel.people.length > 0
                          ? { borderTop: "1px solid rgba(255,255,255,0.07)" }
                          : undefined
                      }
                    >
                      <ResultLabel>Artists</ResultLabel>
                      <ul>
                        {derivedPanel.music.artists.map((a) => (
                          <li key={a.mbid}>
                            <Link
                              href={`/artist/${a.mbid}`}
                              onClick={dismiss}
                              style={rowStyle}
                              {...hoverHandlers}
                            >
                              <ArtworkThumb src={a.image_url} alt={a.name} round />
                              <span style={{ minWidth: 0 }}>
                                <span
                                  style={{
                                    display: "block",
                                    fontWeight: 500,
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                    whiteSpace: "nowrap",
                                  }}
                                >
                                  {a.name}
                                </span>
                                {a.disambiguation && (
                                  <span
                                    style={{
                                      display: "block",
                                      fontSize: 11,
                                      color: "#757c8c",
                                      overflow: "hidden",
                                      textOverflow: "ellipsis",
                                      whiteSpace: "nowrap",
                                    }}
                                  >
                                    {a.disambiguation}
                                  </span>
                                )}
                              </span>
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}

                  {derivedPanel.music.albums.length > 0 && (
                    <section style={{ borderTop: "1px solid rgba(255,255,255,0.07)" }}>
                      <ResultLabel>Albums</ResultLabel>
                      <ul>
                        {derivedPanel.music.albums.map((a) => (
                          <li key={a.mbid}>
                            <Link
                              href={`/album/${a.mbid}`}
                              onClick={dismiss}
                              style={rowStyle}
                              {...hoverHandlers}
                            >
                              <ArtworkThumb src={a.cover_art_url} alt={a.title} />
                              <span style={{ minWidth: 0 }}>
                                <span
                                  style={{
                                    display: "block",
                                    fontWeight: 500,
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                    whiteSpace: "nowrap",
                                  }}
                                >
                                  {a.title}
                                </span>
                                <span
                                  style={{
                                    display: "block",
                                    fontSize: 11,
                                    color: "#757c8c",
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                    whiteSpace: "nowrap",
                                  }}
                                >
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
                    <section style={{ borderTop: "1px solid rgba(255,255,255,0.07)" }}>
                      <ResultLabel>Tracks</ResultLabel>
                      <ul>
                        {derivedPanel.music.tracks.map((t) => (
                          <li key={t.mbid}>
                            <Link
                              href={`/track/${t.mbid}`}
                              onClick={dismiss}
                              style={rowStyle}
                              {...hoverHandlers}
                            >
                              <span
                                style={{
                                  width: 32,
                                  height: 32,
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  flexShrink: 0,
                                  color: "#343b4d",
                                  backgroundColor: "#151821",
                                  borderRadius: 6,
                                }}
                              >
                                <MusicNoteIcon />
                              </span>
                              <span style={{ minWidth: 0, flex: 1 }}>
                                <span
                                  style={{
                                    display: "block",
                                    fontWeight: 500,
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                    whiteSpace: "nowrap",
                                  }}
                                >
                                  {t.title}
                                </span>
                                <span
                                  style={{
                                    display: "block",
                                    fontSize: 11,
                                    color: "#757c8c",
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                    whiteSpace: "nowrap",
                                  }}
                                >
                                  {[t.artist_name, t.album_title].filter(Boolean).join(" · ")}
                                </span>
                              </span>
                              {t.duration_ms !== null && (
                                <span
                                  style={{
                                    flexShrink: 0,
                                    fontSize: 11,
                                    color: "#757c8c",
                                    fontVariantNumeric: "tabular-nums",
                                  }}
                                >
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
  const radius = round ? "50%" : 6;

  if (!src || failed) {
    return (
      <span
        style={{
          display: "block",
          width: 32,
          height: 32,
          flexShrink: 0,
          backgroundColor: "#151821",
          borderRadius: radius,
        }}
        aria-hidden="true"
      />
    );
  }

  return (
    <span
      style={{
        display: "block",
        position: "relative",
        width: 32,
        height: 32,
        flexShrink: 0,
        overflow: "hidden",
        borderRadius: radius,
      }}
    >
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
