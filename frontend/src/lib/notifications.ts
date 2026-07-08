import type { NotificationListResponse, UnreadCountResponse } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function notificationsGet<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1/notifications${path}`, {
    headers: { Authorization: `Bearer ${token}` },
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

async function notificationsPost(path: string, token: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/notifications${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw Object.assign(new Error((detail as { detail?: string }).detail ?? res.statusText), {
      status: res.status,
    });
  }
}

export function getNotifications(
  token: string,
  cursor?: string
): Promise<NotificationListResponse> {
  const params = new URLSearchParams();
  if (cursor) params.set("cursor", cursor);
  const qs = params.size > 0 ? `?${params}` : "";
  return notificationsGet<NotificationListResponse>(qs, token);
}

export function getUnreadCount(token: string): Promise<UnreadCountResponse> {
  return notificationsGet<UnreadCountResponse>("/unread-count", token);
}

export function markNotificationRead(token: string, notificationId: string): Promise<void> {
  return notificationsPost(`/${notificationId}/read`, token);
}

export function markAllNotificationsRead(token: string): Promise<void> {
  return notificationsPost("/read-all", token);
}
