"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { searchCatalog } from "@/lib/catalog";
import type { SearchResponse } from "@/types";
import CoverArt from "./CoverArt";

function formatDuration(ms: number | null): string {
  if (ms === null) return "";
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

type PanelState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "empty"; query: string }
  | { kind: "results"; data: SearchResponse };

export default function SearchBar() {
  const [query, setQuery] = useState("");
  const [panel, setPanel] = useState<PanelState>({ kind: "idle" });
  const containerRef = useRef<HTMLDivElement>(null);

  // Close panel on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setPanel({ kind: "idle" });
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Debounced search
  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setPanel({ kind: "idle" });
      return;
    }
    const timeout = setTimeout(async () => {
      setPanel({ kind: "loading" });
      try {
        const data = await searchCatalog(trimmed);
        const hasResults =
          data.artists.length > 0 ||
          data.albums.length > 0 ||
          data.tracks.length > 0;
        setPanel(hasResults ? { kind: "results", data } : { kind: "empty", query: trimmed });
      } catch {
        setPanel({ kind: "error" });
      }
    }, 300);
    return () => clearTimeout(timeout);
  }, [query]);

  const dismiss = () => {
    setQuery("");
    setPanel({ kind: "idle" });
  };

  const showPanel = panel.kind !== "idle";

  return (
    <div ref={containerRef} className="relative w-full max-w-sm">
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search artists, albums, tracks…"
        className="w-full rounded border border-neutral-200 bg-white px-3 py-1.5 text-sm text-neutral-900 placeholder:text-neutral-400 focus:border-neutral-400 focus:outline-none dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100 dark:placeholder:text-neutral-500"
        autoComplete="off"
        spellCheck={false}
      />

      {showPanel && (
        <div className="absolute left-0 top-full z-50 mt-1 w-full min-w-[20rem] rounded border border-neutral-200 bg-white shadow-sm dark:border-neutral-700 dark:bg-neutral-900">
          {panel.kind === "loading" && (
            <div className="px-4 py-3 text-sm text-neutral-400">Searching…</div>
          )}

          {panel.kind === "error" && (
            <div className="px-4 py-3 text-sm text-neutral-500">
              Couldn&rsquo;t reach the music catalog right now. Try again in a moment.
            </div>
          )}

          {panel.kind === "empty" && (
            <div className="px-4 py-3 text-sm text-neutral-500">
              No results for &ldquo;{panel.query}&rdquo;.
            </div>
          )}

          {panel.kind === "results" && (
            <div className="divide-y divide-neutral-100 dark:divide-neutral-800">
              {panel.data.artists.length > 0 && (
                <section>
                  <p className="px-4 pt-3 pb-1 text-xs font-medium uppercase tracking-widest text-neutral-400">
                    Artists
                  </p>
                  <ul>
                    {panel.data.artists.map((a) => (
                      <li key={a.mbid}>
                        <Link
                          href={`/artist/${a.mbid}`}
                          onClick={dismiss}
                          className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-neutral-50 dark:hover:bg-neutral-800"
                        >
                          <CoverArt src={a.image_url} alt={a.name} size={36} className="rounded-full" />
                          <span className="min-w-0">
                            <span className="block truncate font-medium">{a.name}</span>
                            {a.disambiguation && (
                              <span className="block truncate text-xs text-neutral-400">
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

              {panel.data.albums.length > 0 && (
                <section>
                  <p className="px-4 pt-3 pb-1 text-xs font-medium uppercase tracking-widest text-neutral-400">
                    Albums
                  </p>
                  <ul>
                    {panel.data.albums.map((a) => (
                      <li key={a.mbid}>
                        <Link
                          href={`/album/${a.mbid}`}
                          onClick={dismiss}
                          className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-neutral-50 dark:hover:bg-neutral-800"
                        >
                          <CoverArt src={a.cover_art_url} alt={a.title} size={36} />
                          <span className="min-w-0">
                            <span className="block truncate font-medium">{a.title}</span>
                            <span className="block truncate text-xs text-neutral-400">
                              {[a.artist_name, a.release_year].filter(Boolean).join(" · ")}
                            </span>
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {panel.data.tracks.length > 0 && (
                <section>
                  <p className="px-4 pt-3 pb-1 text-xs font-medium uppercase tracking-widest text-neutral-400">
                    Tracks
                  </p>
                  <ul>
                    {panel.data.tracks.map((t) => (
                      <li key={t.mbid}>
                        <Link
                          href={`/track/${t.mbid}`}
                          onClick={dismiss}
                          className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-neutral-50 dark:hover:bg-neutral-800"
                        >
                          <div className="flex w-9 shrink-0 items-center justify-center text-xs text-neutral-300 dark:text-neutral-600">
                            ♪
                          </div>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate font-medium">{t.title}</span>
                            <span className="block truncate text-xs text-neutral-400">
                              {[t.artist_name, t.album_title].filter(Boolean).join(" · ")}
                            </span>
                          </span>
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
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
