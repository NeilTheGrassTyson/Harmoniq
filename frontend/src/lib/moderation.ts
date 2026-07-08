import type { ReportQueueResponse, ReportStatus } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function moderationGet<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1/moderation${path}`, {
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

async function moderationPost(path: string, token: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/moderation${path}`, {
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

export function getReports(
  token: string,
  status: ReportStatus = "open",
  cursor?: string
): Promise<ReportQueueResponse> {
  const params = new URLSearchParams({ status });
  if (cursor) params.set("cursor", cursor);
  return moderationGet<ReportQueueResponse>(`/reports?${params}`, token);
}

export function dismissReport(token: string, reportId: string): Promise<void> {
  return moderationPost(`/reports/${reportId}/dismiss`, token);
}

export function hideRating(token: string, ratingId: string): Promise<void> {
  return moderationPost(`/ratings/${ratingId}/hide`, token);
}

export function suspendUser(token: string, username: string): Promise<void> {
  return moderationPost(`/users/${encodeURIComponent(username)}/suspend`, token);
}
