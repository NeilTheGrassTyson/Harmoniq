import type { FollowListResponse, FollowState } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function followsMutation(method: string, path: string, token: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/follows${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw Object.assign(new Error((detail as { detail?: string }).detail ?? res.statusText), {
      status: res.status,
    });
  }
}

async function followsGet<T>(path: string, token?: string): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/api/v1/follows${path}`, {
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

export function followUser(token: string, username: string): Promise<void> {
  return followsMutation("POST", `/${encodeURIComponent(username)}`, token);
}

export function unfollowUser(token: string, username: string): Promise<void> {
  return followsMutation("DELETE", `/${encodeURIComponent(username)}`, token);
}

export function getFollowState(username: string, token?: string): Promise<FollowState> {
  return followsGet<FollowState>(`/${encodeURIComponent(username)}/state`, token);
}

export function getFollowers(
  username: string,
  cursor?: string,
  limit = 20
): Promise<FollowListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) params.set("cursor", cursor);
  return followsGet<FollowListResponse>(`/${encodeURIComponent(username)}/followers?${params}`);
}

export function getFollowing(
  username: string,
  cursor?: string,
  limit = 20
): Promise<FollowListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) params.set("cursor", cursor);
  return followsGet<FollowListResponse>(`/${encodeURIComponent(username)}/following?${params}`);
}
