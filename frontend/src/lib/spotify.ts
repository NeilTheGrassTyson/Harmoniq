import type { ListeningResponse, SpotifyConnectionStatus } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function spotifyGet<T>(path: string, token?: string): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/api/v1/spotify${path}`, {
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw Object.assign(new Error((detail as { detail?: string }).detail ?? res.statusText), {
      status: res.status,
    });
  }
  return res.json() as Promise<T>;
}

async function spotifyMutation<T>(
  method: string,
  path: string,
  token: string,
  body?: unknown
): Promise<T | undefined> {
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`${API_BASE}/api/v1/spotify${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw Object.assign(new Error((detail as { detail?: string }).detail ?? res.statusText), {
      status: res.status,
    });
  }
  if (res.status === 204) return undefined;
  return res.json() as Promise<T>;
}

export function getSpotifyConnectUrl(token: string): Promise<{ url: string }> {
  return spotifyGet<{ url: string }>("/connect-url", token);
}

export async function completeSpotifyCallback(
  token: string,
  code: string,
  state: string
): Promise<SpotifyConnectionStatus> {
  const result = await spotifyMutation<SpotifyConnectionStatus>("POST", "/callback", token, {
    code,
    state,
  });
  return result as SpotifyConnectionStatus;
}

export function getSpotifyConnection(token: string): Promise<SpotifyConnectionStatus> {
  return spotifyGet<SpotifyConnectionStatus>("/connection", token);
}

export async function disconnectSpotify(token: string): Promise<void> {
  await spotifyMutation<undefined>("DELETE", "/connection", token);
}

export function getListening(username: string, token?: string): Promise<ListeningResponse> {
  return spotifyGet<ListeningResponse>(`/listening/${encodeURIComponent(username)}`, token);
}
