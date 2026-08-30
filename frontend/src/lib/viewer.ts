import { cache } from "react";
import { auth } from "@clerk/nextjs/server";
import { getOwnProfile } from "@/lib/users";

/**
 * Who is looking at the page, resolved on the server.
 *
 * `username` is the *Harmoniq* username — the one profile routes are keyed by.
 * It is deliberately not Clerk's `user.username`: Clerk's is set at sign-up
 * and never synced (the backend writes only `publicMetadata.onboarded`), so
 * the two diverge for anyone who chose a different handle at onboarding or
 * renamed themselves later. Building `/u/{username}` from Clerk's copy sent
 * those people to a dead route, or to whoever had since claimed their old
 * handle. See ADR 0012.
 */
export interface Viewer {
  signedIn: boolean;
  /** Null when signed out, mid-onboarding, or the backend didn't answer. */
  username: string | null;
}

const SIGNED_OUT: Viewer = { signedIn: false, username: null };

/**
 * Shorter than the app-wide REQUEST_TIMEOUT_MS on purpose. This call sits in
 * the root layout, so a hung backend would otherwise hold every page on the
 * site blank for the full ten seconds. The nav is chrome: past a couple of
 * seconds it is better to render the page without the Profile link.
 */
const VIEWER_TIMEOUT_MS = 2_500;

/**
 * One backend round trip per render, deduped by `cache()` across every server
 * component in the tree.
 *
 * Reading the username from the session token instead would cost nothing, but
 * it would mean a second copy of it living in Clerk that a failed rename could
 * leave stale — which is the bug this exists to fix. One source of truth is
 * worth the request.
 *
 * Failure resolves to a null username rather than throwing: the nav then hides
 * the Profile link, which is honest. Linking somewhere wrong is not.
 */
export const getViewer = cache(async (): Promise<Viewer> => {
  const { userId, getToken } = await auth();
  if (!userId) return SIGNED_OUT;

  const token = await getToken().catch(() => null);
  if (!token) return { signedIn: true, username: null };

  try {
    const profile = await getOwnProfile(token, AbortSignal.timeout(VIEWER_TIMEOUT_MS));
    return { signedIn: true, username: profile.username };
  } catch {
    return { signedIn: true, username: null };
  }
});
