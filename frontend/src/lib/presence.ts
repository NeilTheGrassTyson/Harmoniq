import type { FriendsPresenceResponse } from "@/types";
import { API_BASE, REQUEST_TIMEOUT_MS } from "@/lib/apiBase";

async function presenceRequest<T>(method: "GET" | "POST", path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1/presence${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!res.ok) {
    throw Object.assign(new Error(res.statusText), { status: res.status });
  }
  return res.json() as Promise<T>;
}

/** Returns whether the beat was kept — false means Online status is Private. */
export async function sendHeartbeat(token: string): Promise<boolean> {
  return (await presenceRequest<{ recorded: boolean }>("POST", "/heartbeat", token)).recorded;
}

export function getFriendsPresence(token: string): Promise<FriendsPresenceResponse> {
  return presenceRequest<FriendsPresenceResponse>("GET", "/friends", token);
}
