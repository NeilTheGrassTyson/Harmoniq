import type { HomeResponse } from "@/types";
import { API_BASE } from "@/lib/apiBase";

export async function getHome(token: string): Promise<HomeResponse> {
  const response = await fetch(`${API_BASE}/api/v1/home`, {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    throw Object.assign(new Error(`Home request failed: ${response.status}`), {
      status: response.status,
    });
  }
  return response.json() as Promise<HomeResponse>;
}
