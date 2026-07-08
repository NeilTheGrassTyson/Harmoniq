import Link from "next/link";
import { notFound } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import AppShell from "@/components/AppShell";
import AvatarImage from "@/components/AvatarImage";
import { getFollowing } from "@/lib/follows";
import { getProfile } from "@/lib/users";

export default async function FollowingPage(props: {
  params: Promise<{ username: string }>;
  searchParams: Promise<{ cursor?: string }>;
}) {
  const { username } = await props.params;
  const { cursor } = await props.searchParams;
  const { getToken } = await auth();
  const token = await getToken().catch(() => null);

  let profile;
  try {
    profile = await getProfile(username, token ?? undefined);
  } catch (err: unknown) {
    const status =
      err instanceof Error && (err as Error & { status?: number }).status === 404 ? 404 : 503;
    if (status === 404) notFound();
    throw err;
  }

  const { data, listPrivate } = await getFollowing(username, cursor, 20, token ?? undefined).then(
    (result) => ({ data: result, listPrivate: false }),
    (err: unknown) => ({
      data: { items: [], next_cursor: null },
      listPrivate: err instanceof Error && (err as Error & { status?: number }).status === 403,
    })
  );

  return (
    <AppShell>
      <main className="mx-auto max-w-2xl px-4 py-10">
        <div className="mb-6">
          <Link href={`/u/${username}`} className="text-secondary hover:text-primary text-sm">
            ← @{username}
          </Link>
          <h1 className="text-primary mt-2 text-xl font-light tracking-tight">
            {profile.following_count === 1 ? "1 following" : `${profile.following_count} following`}
          </h1>
        </div>

        {listPrivate ? (
          <p className="text-tertiary text-sm">This list is private.</p>
        ) : data.items.length === 0 ? (
          <p className="text-tertiary text-sm">Not following anyone yet.</p>
        ) : (
          <ul className="divide-hairline divide-y">
            {data.items.map((user) => (
              <li key={user.user_id} className="flex items-center gap-3 py-3">
                <AvatarImage src={user.avatar_url} username={user.username} size={36} />
                <div className="min-w-0">
                  <Link
                    href={`/u/${user.username}`}
                    className="text-primary block text-sm font-medium hover:underline"
                  >
                    {user.display_name}
                  </Link>
                  <p className="text-tertiary text-xs">@{user.username}</p>
                </div>
              </li>
            ))}
          </ul>
        )}

        {data.next_cursor && (
          <div className="mt-6">
            <Link
              href={`/u/${username}/following?cursor=${encodeURIComponent(data.next_cursor)}`}
              className="text-secondary hover:text-primary text-sm"
            >
              Load more
            </Link>
          </div>
        )}
      </main>
    </AppShell>
  );
}
