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

export function getArtist(mbid: string): Promise<ArtistDetail> {
  // Viewer-independent catalog metadata — cache in the Next data cache.
  // Short TTL because the albums list grows as on-demand ingestion runs.
  return catalogGet<ArtistDetail>(`/artists/${encodeURIComponent(mbid)}`, undefined, {
    next: { revalidate: 300, tags: ["catalog"] },
  });
}

// Album and track detail responses embed visibility-scoped reviews
// (rating_svc.list_for_entity filters per viewer) — caching them would
// serve one viewer's reviews to another (ENGINEERING_BIBLE.md §8.1).
// `no-store` is explicit so a future edit can't accidentally opt them in.
export function getAlbum(mbid: string, token?: string): Promise<AlbumDetail> {
  return catalogGet<AlbumDetail>(`/albums/${encodeURIComponent(mbid)}`, token, {
    cache: "no-store",
  });
}

export function getTrack(mbid: string, token?: string): Promise<TrackDetail> {
  return catalogGet<TrackDetail>(`/tracks/${encodeURIComponent(mbid)}`, token, {
    cache: "no-store",
  });
}
