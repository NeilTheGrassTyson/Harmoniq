"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useId, useState } from "react";
import { getOwnProfile, updateProfile } from "@/lib/users";

/**
 * The separate opt-in for keeping recent listening (specs/phase-2-listen-
 * history.md). Hidden while the backend has the feature off, and — like the
 * other consent controls — never shown until the real value has loaded.
 */
export default function ListenHistorySetting() {
  const { getToken } = useAuth();
  const id = useId();
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [supported, setSupported] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getToken()
      .then(async (token) => {
        if (!token) return;
        const profile = await getOwnProfile(token);
        if (profile.store_listening == null) setSupported(false);
        else setEnabled(profile.store_listening);
      })
      .catch(() => setError("Couldn't load this setting."));
  }, [getToken]);

  if (!supported) return null;

  const toggle = async (next: boolean) => {
    const previous = enabled;
    setEnabled(next);
    setSaving(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await updateProfile(token, { store_listening: next });
    } catch {
      setEnabled(previous);
      setError("Something went wrong. Try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mt-4" data-testid="listen-history-setting">
      <div className="flex items-center justify-between gap-4">
        <label htmlFor={id} className="text-secondary text-sm">
          Keep your recent listening on your profile
        </label>
        {enabled === null ? (
          <span className="text-tertiary text-[13px]">{error ? "unavailable" : "…"}</span>
        ) : (
          <input
            id={id}
            type="checkbox"
            role="switch"
            checked={enabled}
            disabled={saving}
            onChange={(event) => void toggle(event.target.checked)}
            className="accent-accent size-4"
          />
        )}
      </div>
      <p className="text-tertiary mt-1 text-xs">
        Harmoniq keeps up to 20 recent plays so your profile doesn&apos;t go blank between visits.
        Who sees them follows your Listening activity visibility. Turning this off deletes them.
      </p>
      {error && enabled !== null && (
        <p role="alert" className="text-destructive mt-1 text-xs">
          {error}
        </p>
      )}
    </div>
  );
}
