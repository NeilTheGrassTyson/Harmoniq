import type { HomeResponse } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function getHome(token: string): Promise<HomeResponse> {
  const response = await fetch(`${API_BASE}/api/v1/home`, {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Home request failed: ${response.status}`);
  }
  return response.json() as Promise<HomeResponse>;
}
