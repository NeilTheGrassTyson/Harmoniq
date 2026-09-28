import type { FriendsOverview, FriendshipState } from "@/types";
import { API_BASE, REQUEST_TIMEOUT_MS } from "@/lib/apiBase";

async function friendsFetch<T>(path: string, token: string, method = "GET"): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1/friends${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw Object.assign(new Error((detail as { detail?: string }).detail ?? res.statusText), {
      status: res.status,
    });
  }
  return res.json() as Promise<T>;
}

type StateReply = { state: FriendshipState };

const who = (username: string) => `/${encodeURIComponent(username)}`;

export function getFriends(token: string): Promise<FriendsOverview> {
  return friendsFetch<FriendsOverview>("/me", token);
}

export async function sendFriendRequest(token: string, username: string) {
  return (await friendsFetch<StateReply>(`${who(username)}/request`, token, "POST")).state;
}

export async function acceptFriendRequest(token: string, username: string) {
  return (await friendsFetch<StateReply>(`${who(username)}/accept`, token, "POST")).state;
}

export async function declineFriendRequest(token: string, username: string) {
  return (await friendsFetch<StateReply>(`${who(username)}/decline`, token, "POST")).state;
}

export async function removeFriend(token: string, username: string) {
  return (await friendsFetch<StateReply>(who(username), token, "DELETE")).state;
}
