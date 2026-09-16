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
  if (!token) {
    reportNamelessViewer("Clerk minted no session token for a signed-in user.");
    return { signedIn: true, username: null };
  }

  try {
    const profile = await getOwnProfile(token, AbortSignal.timeout(VIEWER_TIMEOUT_MS));
    return { signedIn: true, username: profile.username };
  } catch (err) {
    reportNamelessViewer(describeViewerFailure(err));
    return { signedIn: true, username: null };
  }
});

/**
 * A signed-in viewer with no username renders as a nav that is signed-in in
 * every respect except the Profile link, which is simply absent. That is the
 * intended fallback — chrome must never hold up a page — but on screen it is
 * indistinguishable from the link having been forgotten, and it is the failure
 * three separate signup investigations have started from.
 *
 * So it is logged, per ADR 0011: a failure that can break a surface for every
 * user must name itself somewhere. This runs in the root layout on the server,
 * so the line lands in the hosting platform's runtime logs. The Clerk user id
 * is deliberately not included — the backend redacts it in the same situation.
 */
function reportNamelessViewer(reason: string): void {
  console.error(`[viewer] No Profile link will render: ${reason}`);
}

function describeViewerFailure(err: unknown): string {
  // `status` present means the server answered; absent means it was never
  // reached. That contract is ADR 0011's, and the API helpers maintain it.
  const status = (err as { status?: number } | null)?.status;

  if (status === 404) {
    return (
      "GET /users/me returned 404 — this Clerk account has no Harmoniq user " +
      "record, so onboarding never completed for it. The account can still " +
      "browse every public route, with no Profile link and nothing prompting " +
      "it to finish."
    );
  }
  if (status === 401) {
    return (
      "GET /users/me returned 401 — the backend rejected the Clerk token. " +
      "Check CLERK_JWKS_URL points at the same Clerk instance issuing tokens."
    );
  }
  if (status !== undefined) {
    return `GET /users/me returned ${status}.`;
  }
  return (
    `GET /users/me never reached the backend — it timed out after ` +
    `${VIEWER_TIMEOUT_MS}ms or the host is unreachable. A cold backend can ` +
    `exceed that on the first request after an idle period.`
  );
}
