import { auth } from "@clerk/nextjs/server";
import FriendsRail from "@/components/FriendsRail";
import { getFriendsPresence } from "@/lib/presence";

/**
 * The rail's first read, on the server. Rendered inside a Suspense boundary:
 * resolving a friend's Listening now can mean a Spotify round trip, and that
 * must never hold up the inbox beside it. A failed read hands the client an
 * empty start, and it polls from there.
 */
export default async function FriendsRailSection() {
  const { getToken } = await auth();
  const token = await getToken().catch(() => null);
  const initial = token ? await getFriendsPresence(token).catch(() => null) : null;
  return <FriendsRail initial={initial} />;
}
