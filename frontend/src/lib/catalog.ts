import type { AlbumDetail, ArtistDetail, SearchResponse, TrackDetail } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function catalogGet<T>(
  path: string,
  token?: string,
  init?: Pick<RequestInit, "cache" | "next">
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const response = await fetch(`${API_BASE}/api/v1/catalog${path}`, { headers, ...init });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    // .status lets pages distinguish a real 404 from a transient failure —
    // never string-match error messages for this.
    throw Object.assign(new Error((body as { detail?: string }).detail ?? "Request failed"), {
      status: response.status,
    });
  }
  return response.json() as Promise<T>;
}

export function searchCatalog(query: string): Promise<SearchResponse> {
  return catalogGet<SearchResponse>(`/search?q=${encodeURIComponent(query)}`);
}

// Catalog detail is viewer-independent metadata — no auth token, no per-viewer
// content, so it caches in the Next data cache. Reviews are fetched separately
// via lib/ratings (never cached), which is what makes this safe.
// Short TTL because these grow as on-demand ingestion runs.
function catalogCache(): Pick<RequestInit, "cache" | "next"> {
  return { next: { revalidate: 300, tags: ["catalog"] } };
}

export function getArtist(mbid: string): Promise<ArtistDetail> {
  return catalogGet<ArtistDetail>(`/artists/${encodeURIComponent(mbid)}`, undefined, catalogCache());
}

export function getAlbum(mbid: string): Promise<AlbumDetail> {
  return catalogGet<AlbumDetail>(`/albums/${encodeURIComponent(mbid)}`, undefined, catalogCache());
}

export function getTrack(mbid: string): Promise<TrackDetail> {
  return catalogGet<TrackDetail>(`/tracks/${encodeURIComponent(mbid)}`, undefined, catalogCache());
}
