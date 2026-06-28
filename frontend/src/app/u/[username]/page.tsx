import Link from "next/link";
import { notFound } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import AppShell from "@/components/AppShell";
import AvatarImage from "@/components/AvatarImage";
import FollowButton from "@/components/FollowButton";
import { getProfile } from "@/lib/users";
import { getUserRatings } from "@/lib/ratings";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default async function ProfilePage(props: { params: Promise<{ username: string }> }) {
  const { username } = await props.params;
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

  const ratingsData = await getUserRatings(username, token ?? undefined).catch(() => ({
    reviews: [],
  }));

  return (
    <AppShell>
      <div style={{ padding: "26px 22px 30px", maxWidth: 720 }}>
        {/* ── Profile header ─────────────────────────────────────────────── */}
        <div style={{ display: "flex", alignItems: "flex-start", gap: 20, marginBottom: 24 }}>
          <AvatarImage src={profile.avatar_url} username={profile.username} size={72} />
          <div style={{ minWidth: 0, flex: 1 }}>
            <h1
              className="font-display text-primary"
              style={{ fontSize: 20, fontWeight: 500, lineHeight: 1.2 }}
            >
              {profile.display_name}
            </h1>
            <p className="text-secondary" style={{ fontSize: 13, marginTop: 2 }}>
              @{profile.username}
            </p>

            {"bio" in profile && profile.bio && (
              <p className="text-secondary" style={{ fontSize: 13, marginTop: 8, lineHeight: 1.5 }}>
                {profile.bio}
              </p>
            )}
            {"bio" in profile && profile.bio === null && profile.is_own_profile && (
              <Link
                href="/settings"
                className="text-tertiary hover:text-secondary"
                style={{ fontSize: 13, marginTop: 8, display: "block" }}
              >
                Add a bio
              </Link>
            )}

            {/* Follower / following counts */}
            <div style={{ display: "flex", gap: 16, marginTop: 12, fontSize: 13 }}>
              <Link
                href={`/u/${profile.username}/followers`}
                className="text-secondary hover:text-accent"
              >
                <span className="text-primary" style={{ fontWeight: 500 }}>
                  {profile.follower_count}
                </span>{" "}
                {profile.follower_count === 1 ? "follower" : "followers"}
              </Link>
              <Link
                href={`/u/${profile.username}/following`}
                className="text-secondary hover:text-accent"
              >
                <span className="text-primary" style={{ fontWeight: 500 }}>
                  {profile.following_count}
                </span>{" "}
                following
              </Link>
            </div>
          </div>
        </div>

        {/* ── Actions ────────────────────────────────────────────────────── */}
        <div style={{ marginBottom: 32 }}>
          {profile.is_own_profile ? (
            <Link
              href="/settings"
              style={{
                display: "inline-block",
                padding: "5px 14px",
                fontSize: 12,
                fontWeight: 500,
                color: "#8b93a3",
                border: "1px solid rgba(255,255,255,0.07)",
                borderRadius: 8,
                textDecoration: "none",
              }}
            >
              Edit profile
            </Link>
          ) : (
            profile.follow !== undefined && (
              <FollowButton
                username={profile.username}
                initialIsFollowing={profile.follow.is_following}
              />
            )
          )}
        </div>

        {/* ── Listening activity placeholder ─────────────────────────────── */}
        {"activity_placeholder" in profile && profile.activity_placeholder && (
          <section style={{ marginBottom: 32 }}>
            <SectionLabel>Listening activity</SectionLabel>
            <p className="text-tertiary" style={{ fontSize: 13 }}>
              Listening history coming soon.
            </p>
          </section>
        )}

        {/* ── Ratings ────────────────────────────────────────────────────── */}
        {"ratings_count" in profile && (
          <section>
            <SectionLabel>Ratings</SectionLabel>
            {ratingsData.reviews.length === 0 ? (
              <p className="text-tertiary" style={{ fontSize: 13 }}>
                No reviews yet.
              </p>
            ) : (
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {ratingsData.reviews.map((r, idx) => (
                  <li
                    key={r.id}
                    style={{
                      paddingBottom: 20,
                      marginBottom: 20,
                      borderBottom:
                        idx < ratingsData.reviews.length - 1
                          ? "1px solid rgba(255,255,255,0.07)"
                          : "none",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "baseline",
                        justifyContent: "space-between",
                        gap: 12,
                        marginBottom: 4,
                      }}
                    >
                      <div style={{ minWidth: 0 }}>
                        {r.entity_mbid ? (
                          <Link
                            href={`/${r.entity_type}/${r.entity_mbid}`}
                            className="text-primary hover:text-accent"
                            style={{ fontSize: 14, fontWeight: 500 }}
                          >
                            {r.entity_title ?? r.entity_mbid}
                          </Link>
                        ) : (
                          <span className="text-primary" style={{ fontSize: 14, fontWeight: 500 }}>
                            {r.entity_title ?? "Unknown"}
                          </span>
                        )}
                        <span className="text-tertiary" style={{ fontSize: 11, marginLeft: 8 }}>
                          {r.entity_type}
                        </span>
                      </div>
                      <span
                        className="text-primary font-display"
                        style={{ fontSize: 13, fontWeight: 500, flexShrink: 0 }}
                      >
                        {r.score}/10
                      </span>
                    </div>
                    <p className="text-secondary" style={{ fontSize: 13, lineHeight: 1.6 }}>
                      {r.review_text}
                    </p>
                    <p className="text-tertiary" style={{ fontSize: 11, marginTop: 4 }}>
                      {formatDate(r.created_at)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </div>
    </AppShell>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h2
      className="font-display text-tertiary"
      style={{
        fontSize: 11,
        fontWeight: 500,
        textTransform: "uppercase",
        letterSpacing: "0.6px",
        marginBottom: 14,
      }}
    >
      {children}
    </h2>
  );
}
