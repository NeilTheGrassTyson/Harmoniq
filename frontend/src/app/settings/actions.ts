"use server";

import { cookies } from "next/headers";
import { APPEARANCE_COOKIE, isAppearance } from "@/lib/appearance";

const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

/**
 * Persists the viewer's Website Appearance. Run as a Server Action so the
 * response carries the re-rendered root layout — new `data-theme` on <html>
 * and the matching Clerk palette — in the same round trip, with no reload.
 *
 * Deliberately needs no session: it only writes a cosmetic cookie back to the
 * browser that asked. Not httpOnly because global-error.tsx, which renders
 * without the root layout, has to read it client-side.
 */
export async function setAppearance(value: unknown): Promise<{ ok: boolean }> {
  if (!isAppearance(value)) return { ok: false };
  const store = await cookies();
  store.set(APPEARANCE_COOKIE, value, {
    path: "/",
    maxAge: ONE_YEAR_SECONDS,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
  });
  return { ok: true };
}
