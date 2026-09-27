import "server-only";
import { cookies } from "next/headers";
import { APPEARANCE_COOKIE, parseAppearance, type Appearance } from "@/lib/appearance";

export async function getAppearance(): Promise<Appearance> {
  const store = await cookies();
  return parseAppearance(store.get(APPEARANCE_COOKIE)?.value);
}
