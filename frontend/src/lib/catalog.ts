import type {
  AlbumDetail,
  ArtistDetail,
  SearchResponse,
  TrackDetail,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function catalogGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}/api/v1/catalog${path}`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error((body as { detail?: string }).detail ?? "Request failed");
  }
  return response.json() as Promise<T>;
}

export function searchCatalog(query: string): Promise<SearchResponse> {
  return catalogGet<SearchResponse>(`/search?q=${encodeURIComponent(query)}`);
}

export function getArtist(mbid: string): Promise<ArtistDetail> {
  return catalogGet<ArtistDetail>(`/artists/${encodeURIComponent(mbid)}`);
}

export function getAlbum(mbid: string): Promise<AlbumDetail> {
  return catalogGet<AlbumDetail>(`/albums/${encodeURIComponent(mbid)}`);
}

export function getTrack(mbid: string): Promise<TrackDetail> {
  return catalogGet<TrackDetail>(`/tracks/${encodeURIComponent(mbid)}`);
}
