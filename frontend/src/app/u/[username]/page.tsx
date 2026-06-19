import Link from "next/link";
import { notFound } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import AvatarImage from "@/components/AvatarImage";
import { getProfile } from "@/lib/users";

export default async function ProfilePage(props: {
  params: Promise<{ username: string }>;
}) {
  const { username } = await props.params;
  const { getToken } = await auth();
  const token = await getToken().catch(() => null);

  let profile;
  try {
    profile = await getProfile(username, token ?? undefined);
  } catch (err: unknown) {
    const status =
      err instanceof Error &&
      (err as Error & { status?: number }).status === 404
        ? 404
        : 503;
    if (status === 404) notFound();
    throw err;
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      {/* Header */}
      <div className="mb-8 flex items-start gap-5">
        <AvatarImage
          src={profile.avatar_url}
          username={profile.username}
          size={80}
        />
        <div className="min-w-0">
          <h1 className="text-2xl font-light tracking-tight">
            {profile.display_name}
          </h1>
          <p className="mt-0.5 text-sm text-neutral-500">
            @{profile.username}
          </p>
          {"bio" in profile && profile.bio && (
            <p className="mt-2 text-sm text-neutral-600 dark:text-neutral-400">
              {profile.bio}
            </p>
          )}
          {"bio" in profile && profile.bio === null && profile.is_own_profile && (
            <Link
              href="/settings"
              className="mt-2 block text-sm text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300"
            >
              Add a bio
            </Link>
          )}
        </div>
      </div>

      {/* Edit button — own profile only */}
      {profile.is_own_profile && (
        <div className="mb-8">
          <Link
            href="/settings"
            className="rounded border border-neutral-200 px-3 py-1.5 text-xs font-medium text-neutral-600 hover:bg-neutral-50 dark:border-neutral-700 dark:text-neutral-400 dark:hover:bg-neutral-800"
          >
            Edit profile
          </Link>
        </div>
      )}

      {/* Listening activity */}
      {"activity_placeholder" in profile && profile.activity_placeholder && (
        <section className="mb-8">
          <h2 className="mb-2 text-xs font-medium uppercase tracking-widest text-neutral-400">
            Listening activity
          </h2>
          <p className="text-sm text-neutral-400">
            Listening history coming soon.
          </p>
        </section>
      )}

      {/* Ratings count */}
      {"ratings_count" in profile && (
        <section>
          <h2 className="mb-2 text-xs font-medium uppercase tracking-widest text-neutral-400">
            Ratings
          </h2>
          <p className="text-sm text-neutral-600 dark:text-neutral-400">
            {profile.ratings_count}{" "}
            {profile.ratings_count === 1 ? "rating" : "ratings"}
          </p>
        </section>
      )}
    </main>
  );
}
