import type {
  MelodyInboxItem,
  MelodyInboxResponse,
  MelodyRespondAction,
  MelodyReaction,
  MelodySentItem,
  MelodySentResponse,
} from "@/types";
import { API_BASE, REQUEST_TIMEOUT_MS } from "@/lib/apiBase";

async function melodiesGet<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1/melodies${path}`, {
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

async function melodiesMutation<T>(path: string, token: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1/melodies${path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
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

export function sendMelody(
  token: string,
  recipientUsername: string,
  trackMbid: string
): Promise<MelodySentItem> {
  return melodiesMutation<MelodySentItem>("", token, {
    recipient_username: recipientUsername,
    track_mbid: trackMbid,
  });
}

export function getInbox(token: string, cursor?: string): Promise<MelodyInboxResponse> {
  const params = new URLSearchParams();
  if (cursor) params.set("cursor", cursor);
  const qs = params.size > 0 ? `?${params}` : "";
  return melodiesGet<MelodyInboxResponse>(`/inbox${qs}`, token);
}

export function getSentMelodies(token: string, cursor?: string): Promise<MelodySentResponse> {
  const params = new URLSearchParams();
  if (cursor) params.set("cursor", cursor);
  const qs = params.size > 0 ? `?${params}` : "";
  return melodiesGet<MelodySentResponse>(`/sent${qs}`, token);
}

export function respondToMelody(
  token: string,
  melodyId: string,
  action: MelodyRespondAction
): Promise<MelodyInboxItem> {
  return melodiesMutation<MelodyInboxItem>(`/${melodyId}/respond`, token, { action });
}

export function reactToMelody(
  token: string,
  melodyId: string,
  reaction: MelodyReaction
): Promise<MelodyInboxItem> {
  return melodiesMutation<MelodyInboxItem>(`/${melodyId}/react`, token, { reaction });
}

export const REACTION_LABELS: Record<MelodyReaction, string> = {
  not_for_me: "Not for me",
  liked: "Liked it",
  loved: "Loved it — send more like this",
};
