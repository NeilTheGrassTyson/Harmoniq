import { API_BASE, REQUEST_TIMEOUT_MS } from "@/lib/apiBase";
import type { StreamingResponse } from "@/types";

export async function getStreamingLinks(mbid: string): Promise<StreamingResponse> {
  const res = await fetch(`${API_BASE}/api/v1/streaming/${encodeURIComponent(mbid)}`, {
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!res.ok)
    throw Object.assign(new Error("Couldn't load music services."), { status: res.status });
  return res.json() as Promise<StreamingResponse>;
}

/** Defense in depth for provider URLs already validated by the backend. */
export function safeSpotifyUrl(raw: string | null): string | null {
  if (!raw || /[\s\\]/.test(raw)) return null;
  try {
    const url = new URL(raw);
    if (
      url.protocol !== "https:" ||
      url.host !== "open.spotify.com" ||
      url.username ||
      url.password
    )
      return null;
    const match = url.pathname.match(/^\/(?:intl-[a-z]{2}\/)?track\/([A-Za-z0-9]{22})$/);
    return match ? `https://open.spotify.com/track/${match[1]}` : null;
  } catch {
    return null;
  }
}
