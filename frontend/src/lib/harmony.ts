import { API_BASE, REQUEST_TIMEOUT_MS } from "@/lib/apiBase";
import type { HarmonyResponse, VisibilityScope } from "@/types";

export async function getHarmony(username: string, token?: string): Promise<HarmonyResponse> {
  const res = await fetch(`${API_BASE}/api/v1/harmony/${encodeURIComponent(username)}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    cache: "no-store",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!res.ok)
    throw Object.assign(new Error("Couldn't load Harmony. Try again."), { status: res.status });
  return res.json() as Promise<HarmonyResponse>;
}

export async function setHarmonyVisibility(token: string, visibility: VisibilityScope) {
  const res = await fetch(`${API_BASE}/api/v1/harmony/me`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ visibility }),
    cache: "no-store",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!res.ok)
    throw Object.assign(new Error("Couldn't confirm your Harmony visibility. Try again."), {
      status: res.status,
    });
  return res.json() as Promise<{ visibility: VisibilityScope }>;
}
