"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";
import { disconnectSpotify, getSpotifyConnection, getSpotifyConnectUrl } from "@/lib/spotify";
import type { SpotifyConnectionStatus } from "@/types";
import { friendlyError } from "@/lib/apiBase";

interface ConnectedAccountsProps {
  /** True immediately after the Spotify OAuth callback redirects back here. */
  justConnected?: boolean;
}

/**
 * Third-party account links, on the global Settings page.
 *
 * A connection is account-level, not part of how a profile presents itself,
 * so it belongs with app settings rather than inside the profile edit form.
 * What the connection *reveals* is still governed by the Listening activity
 * visibility scope on the profile — linking an account never publishes
 * anything on its own (HARMONIQ.md §6, Consent Before Visibility).
 */
export default function ConnectedAccounts({ justConnected = false }: ConnectedAccountsProps) {
  const { getToken } = useAuth();

  const [spotify, setSpotify] = useState<SpotifyConnectionStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Tracked separately from `spotify` because null previously meant both "not
  // connected" and "we never found out" — so a failed check rendered a Connect
  // button at someone whose account was already linked.
  const [checkFailed, setCheckFailed] = useState(false);

  useEffect(() => {
    getToken()
      .then(async (token) => {
        if (!token) return;
        setSpotify(await getSpotifyConnection(token));
        setCheckFailed(false);
      })
      .catch(() => setCheckFailed(true));
  }, [getToken]);

  const handleConnect = async () => {
    setBusy(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");
      const { url } = await getSpotifyConnectUrl(token);
      window.location.assign(url);
    } catch (err: unknown) {
      setError(friendlyError(err, "Spotify integration isn't available right now."));
      setBusy(false);
    }
  };

  const handleDisconnect = async () => {
    setBusy(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");
      await disconnectSpotify(token);
      setSpotify({ connected: false, spotify_user_id: null, connected_at: null });
      setCheckFailed(false);
    } catch {
      setError("Couldn't disconnect. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const buttonClass =
    "rounded-control border-hairline text-secondary hover:text-primary border px-3 py-1.5 text-xs font-medium disabled:opacity-50";

  return (
    <section>
      <h2 className="text-tertiary mb-3 text-xs font-medium tracking-widest uppercase">
        Connected accounts
      </h2>

      {checkFailed ? (
        <p role="alert" className="text-secondary text-sm">
          Couldn&rsquo;t check your Spotify connection right now.
        </p>
      ) : spotify?.connected ? (
        <div className="flex items-center justify-between gap-4">
          <p className="text-secondary text-sm">
            Spotify — connected as <span className="text-primary">{spotify.spotify_user_id}</span>
            {spotify.connected_at && (
              <span className="text-tertiary">
                {" "}
                · since{" "}
                {new Date(spotify.connected_at).toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}
              </span>
            )}
          </p>
          <button type="button" onClick={handleDisconnect} disabled={busy} className={buttonClass}>
            {busy ? "Working…" : "Disconnect"}
          </button>
        </div>
      ) : (
        <div className="flex items-center justify-between gap-4">
          <p className="text-secondary text-sm">Spotify</p>
          <button type="button" onClick={handleConnect} disabled={busy} className={buttonClass}>
            {busy ? "Working…" : "Connect Spotify"}
          </button>
        </div>
      )}

      <p className="text-tertiary mt-2 text-xs">
        Listening activity is shown on your profile according to your Listening activity visibility
        setting, which you can change when editing your profile.
      </p>

      {justConnected && spotify?.connected && (
        <p role="status" className="text-accent mt-1 text-xs">
          Spotify connected.
        </p>
      )}
      {error && (
        <p role="alert" className="text-destructive mt-1 text-xs">
          {error}
        </p>
      )}
    </section>
  );
}
