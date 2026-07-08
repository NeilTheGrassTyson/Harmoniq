import type {
  EntityRatingListResponse,
  RatingRead,
  RatingSubmitRequest,
  UserRatingListResponse,
  VisibilityScope,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function ratingsGet<T>(path: string, token?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/api/v1/ratings${path}`, {
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw Object.assign(new Error((body as { detail?: string }).detail ?? "Request failed"), {
      status: res.status,
    });
  }
  return res.json() as Promise<T>;
}

async function ratingsMutation<T>(
  method: string,
  path: string,
  token: string,
  body?: unknown
): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1/ratings${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw Object.assign(new Error((detail as { detail?: string }).detail ?? res.statusText), {
      status: res.status,
    });
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function getEntityRatings(
  entityType: string,
  entityId: string,
  token?: string
): Promise<EntityRatingListResponse> {
  return ratingsGet<EntityRatingListResponse>(`/entity/${entityType}/${entityId}`, token);
}

export function getUserRatings(username: string, token?: string): Promise<UserRatingListResponse> {
  return ratingsGet<UserRatingListResponse>(`/user/${username}`, token);
}

export function submitRating(token: string, req: RatingSubmitRequest): Promise<RatingRead> {
  return ratingsMutation<RatingRead>("POST", "/", token, req);
}

export function updateRatingVisibility(
  token: string,
  ratingId: string,
  visibility: VisibilityScope
): Promise<RatingRead> {
  return ratingsMutation<RatingRead>("PATCH", `/${ratingId}/visibility`, token, {
    visibility,
  });
}

export function deleteRating(token: string, ratingId: string): Promise<void> {
  return ratingsMutation<void>("DELETE", `/${ratingId}`, token);
}

export function reportRating(token: string, ratingId: string): Promise<void> {
  return ratingsMutation<void>("POST", `/${ratingId}/report`, token);
}
