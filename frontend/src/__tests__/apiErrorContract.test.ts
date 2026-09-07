/**
 * Every API helper must attach `status` to an HTTP failure.
 *
 * `isNetworkError` distinguishes "the server said no" from "the server was
 * never reached" by the *absence* of `status` — so a helper that throws a bare
 * Error makes a 500 indistinguishable from being offline, and the user is told
 * to check their connection while the backend is the thing that is broken.
 *
 * `home.ts` and `users.ts::searchUsers` were both in that state. Neither was
 * visible in review: the missing property is one line that was never written,
 * and every call site still compiled and still showed *a* message.
 *
 * The related trap is in the tests rather than the code. Several component
 * tests mocked a helper rejecting with a bare Error, so they asserted the
 * network-failure copy against a rejection the real helper never produces —
 * a test passing on a shape that cannot occur. The sweep below runs the real
 * helpers over a mocked `fetch`, so the shape it pins is the one that ships.
 *
 * The coverage test at the bottom is the part that keeps this honest: a new
 * helper added without a row here fails, rather than quietly going unchecked.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import * as catalog from "@/lib/catalog";
import * as follows from "@/lib/follows";
import * as home from "@/lib/home";
import * as melodies from "@/lib/melodies";
import * as moderation from "@/lib/moderation";
import * as notifications from "@/lib/notifications";
import * as ratings from "@/lib/ratings";
import * as spotify from "@/lib/spotify";
import * as users from "@/lib/users";
import { errorStatus, isNetworkError, friendlyError } from "@/lib/apiBase";

type Call = () => Promise<unknown>;

/**
 * Each helper with arguments good enough to reach `fetch`. Values are
 * arbitrary — `fetch` is mocked, so only the call shape matters.
 */
const HELPERS: Record<string, Record<string, Call>> = {
  catalog: {
    searchCatalog: () => catalog.searchCatalog("radiohead"),
    getArtist: () => catalog.getArtist("mbid"),
    getAlbum: () => catalog.getAlbum("mbid"),
    getTrack: () => catalog.getTrack("mbid"),
  },
  follows: {
    followUser: () => follows.followUser("tok", "ana"),
    unfollowUser: () => follows.unfollowUser("tok", "ana"),
    getFollowState: () => follows.getFollowState("ana", "tok"),
    getFollowers: () => follows.getFollowers("ana"),
    getFollowing: () => follows.getFollowing("ana"),
  },
  home: {
    getHome: () => home.getHome("tok"),
  },
  melodies: {
    sendMelody: () => melodies.sendMelody("tok", "ana", "mbid"),
    getInbox: () => melodies.getInbox("tok"),
    getSentMelodies: () => melodies.getSentMelodies("tok"),
    respondToMelody: () => melodies.respondToMelody("tok", "id", "accept"),
  },
  moderation: {
    getReports: () => moderation.getReports("tok"),
    dismissReport: () => moderation.dismissReport("tok", "id"),
    hideRating: () => moderation.hideRating("tok", "id"),
    suspendUser: () => moderation.suspendUser("tok", "ana"),
  },
  notifications: {
    getNotifications: () => notifications.getNotifications("tok"),
    getUnreadCount: () => notifications.getUnreadCount("tok"),
    markNotificationRead: () => notifications.markNotificationRead("tok", "id"),
    markAllNotificationsRead: () => notifications.markAllNotificationsRead("tok"),
  },
  ratings: {
    getEntityRatings: () => ratings.getEntityRatings("album", "mbid"),
    getUserRatings: () => ratings.getUserRatings("ana"),
    submitRating: () =>
      ratings.submitRating("tok", {
        entity_type: "album",
        entity_mbid: "mbid",
        score: 8,
        review_text: "Good.",
        visibility: "public",
      }),
    updateRatingVisibility: () => ratings.updateRatingVisibility("tok", "id", "public"),
    deleteRating: () => ratings.deleteRating("tok", "id"),
    reportRating: () => ratings.reportRating("tok", "id"),
  },
  spotify: {
    getSpotifyConnectUrl: () => spotify.getSpotifyConnectUrl("tok"),
    completeSpotifyCallback: () => spotify.completeSpotifyCallback("tok", "code", "state"),
    getSpotifyConnection: () => spotify.getSpotifyConnection("tok"),
    disconnectSpotify: () => spotify.disconnectSpotify("tok"),
    getListening: () => spotify.getListening("ana", "tok"),
  },
  users: {
    createUser: () => users.createUser("tok", "ana", "Ana"),
    checkUsernameAvailable: () => users.checkUsernameAvailable("ana"),
    getOwnProfile: () => users.getOwnProfile("tok"),
    getProfile: () => users.getProfile("ana"),
    updateProfile: () => users.updateProfile("tok", { bio: "hi" }),
    searchUsers: () => users.searchUsers("ana"),
    uploadAvatar: () => users.uploadAvatar("tok", new File(["x"], "a.png")),
  },
};

const MODULES: Record<string, Record<string, unknown>> = {
  catalog,
  follows,
  home,
  melodies,
  moderation,
  notifications,
  ratings,
  spotify,
  users,
};

const entries = Object.entries(HELPERS).flatMap(([module, helpers]) =>
  Object.entries(helpers).map(([name, call]) => [`${module}.${name}`, call] as const)
);

function mockStatus(status: number, body: unknown = { detail: "Nope." }) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: false,
      status,
      statusText: "Error",
      json: async () => body,
    }))
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe.each(entries)("%s", (_name, call) => {
  it("attaches the HTTP status to a 500", async () => {
    mockStatus(500);
    const err = await call().catch((e: unknown) => e);

    expect(errorStatus(err)).toBe(500);
    // The consequence, stated directly: without `status` this reads as an
    // outage on the user's end and the copy blames their connection.
    expect(isNetworkError(err)).toBe(false);
    expect(friendlyError(err)).not.toContain("Check your connection");
  });

  it("attaches the HTTP status to a 404", async () => {
    // Pages tell a genuine 404 apart from a transient failure by this value
    // alone — never by matching on the message text.
    mockStatus(404);
    expect(errorStatus(await call().catch((e: unknown) => e))).toBe(404);
  });

  it("leaves a genuine network failure without a status", async () => {
    // The other half of the contract. If a helper ever invented a status for
    // an unreachable backend, "Couldn't reach Harmoniq" would stop appearing
    // when it is the true message.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Load failed");
      })
    );
    const err = await call().catch((e: unknown) => e);

    expect(errorStatus(err)).toBeUndefined();
    expect(isNetworkError(err)).toBe(true);
    expect(friendlyError(err)).toContain("Check your connection");
  });
});

describe("coverage", () => {
  it.each(Object.keys(MODULES))("every exported helper in lib/%s is swept", (module) => {
    const exported = Object.entries(MODULES[module])
      .filter(([, value]) => typeof value === "function")
      .map(([name]) => name);
    const covered = Object.keys(HELPERS[module]);

    // Sorted comparison rather than a subset check: an export removed without
    // its row is dead weight, and a row added for a helper that no longer
    // exists would otherwise pass forever.
    expect(exported.sort()).toEqual(covered.sort());
  });
});
