import type {
  HighlightItem,
  HighlightType,
  HighlightsResponse,
  PlaylistPickerResponse,
} from "@/types";
import { API_BASE, REQUEST_TIMEOUT_MS } from "@/lib/apiBase";

async function highlightsFetch<T>(
  path: string,
  { token, method = "GET", body }: { token?: string; method?: string; body?: unknown } = {}
): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`${API_BASE}/api/v1/highlights${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw Object.assign(new Error((detail as { detail?: string }).detail ?? res.statusText), {
      status: res.status,
    });
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export function getHighlights(username: string, token?: string) {
  return highlightsFetch<HighlightsResponse>(`/user/${encodeURIComponent(username)}`, { token });
}

export function addHighlight(
  token: string,
  target:
    | { entity_type: Exclude<HighlightType, "playlist">; mbid: string }
    | {
        entity_type: "playlist";
        playlist_id: string;
      }
) {
  return highlightsFetch<HighlightItem>("", { token, method: "POST", body: target });
}

export function removeHighlight(token: string, id: string) {
  return highlightsFetch<void>(`/${encodeURIComponent(id)}`, { token, method: "DELETE" });
}

export function getPlaylistOptions(token: string) {
  return highlightsFetch<PlaylistPickerResponse>("/playlists", { token });
}
