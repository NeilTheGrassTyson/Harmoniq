import type {
  AvatarUploadResponse,
  OwnProfileResponse,
  ProfileResponse,
  ProfileUpdateRequest,
  UsernameCheckResponse,
  UserSearchResult,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function authedGet<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw Object.assign(new Error(detail.detail ?? res.statusText), {
      status: res.status,
    });
  }
  return res.json() as Promise<T>;
}

async function authedMutation<T>(
  method: string,
  path: string,
  token: string,
  body?: unknown
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw Object.assign(new Error(detail.detail ?? res.statusText), {
      status: res.status,
    });
  }
  return res.json() as Promise<T>;
}

/** Create the Harmoniq user record during onboarding. */
export async function createUser(
  token: string,
  username: string,
  displayName: string
): Promise<OwnProfileResponse> {
  return authedMutation<OwnProfileResponse>("POST", "/api/v1/users/", token, {
    username,
    display_name: displayName,
  });
}

/** Check whether a username is available. No auth required — rate-limited by IP. */
export async function checkUsernameAvailable(username: string): Promise<UsernameCheckResponse> {
  const res = await fetch(
    `${API_BASE}/api/v1/users/check-username?q=${encodeURIComponent(username)}`,
    { cache: "no-store" }
  );
  if (!res.ok) return { available: false };
  return res.json() as Promise<UsernameCheckResponse>;
}

/** Fetch the authenticated user's own profile with visibility settings. */
export async function getOwnProfile(token: string): Promise<OwnProfileResponse> {
  return authedGet<OwnProfileResponse>("/api/v1/users/me", token);
}

/** Fetch a public profile by username. Token is optional for personalisation. */
export async function getProfile(username: string, token?: string): Promise<ProfileResponse> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/api/v1/users/${encodeURIComponent(username)}`, {
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw Object.assign(new Error(detail.detail ?? res.statusText), {
      status: res.status,
    });
  }
  return res.json() as Promise<ProfileResponse>;
}

/** Update the authenticated user's profile. */
export async function updateProfile(
  token: string,
  updates: ProfileUpdateRequest
): Promise<OwnProfileResponse> {
  return authedMutation<OwnProfileResponse>("PATCH", "/api/v1/users/me", token, updates);
}

/** Search users by username or display name. No auth required. */
export async function searchUsers(query: string): Promise<UserSearchResult[]> {
  const res = await fetch(`${API_BASE}/api/v1/users/search?q=${encodeURIComponent(query)}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("User search failed");
  return res.json() as Promise<UserSearchResult[]>;
}

/** Upload a new avatar. Returns the public URL. */
export async function uploadAvatar(token: string, file: File): Promise<AvatarUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/v1/users/me/avatar`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw Object.assign(new Error(detail.detail ?? res.statusText), {
      status: res.status,
    });
  }
  return res.json() as Promise<AvatarUploadResponse>;
}
