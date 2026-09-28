"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getOwnProfile, updateProfile } from "@/lib/users";
import type { FriendRequestScope } from "@/types";

const OPTIONS: { value: FriendRequestScope; label: string }[] = [
  { value: "everyone", label: "Everyone" },
  { value: "follows", label: "People you follow" },
  { value: "mutuals", label: "Mutuals" },
];

/**
 * "Who can send you friend requests" — the consent gate for an inbound
 * gesture, shaped like MelodySettings. As there, no control is shown until
 * the real value has loaded, so an unknown setting is never presented as a
 * permissive one (HARMONIQ.md §6).
 */
export default function FriendRequestSettings() {
  const { getToken, isSignedIn } = useAuth();
  const [scope, setScope] = useState<FriendRequestScope | null>(null);
  const [supported, setSupported] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isSignedIn) return;
    getToken()
      .then(async (token) => {
        if (!token) return;
        const profile = await getOwnProfile(token);
        // An older backend has no friend requests to configure.
        if (profile.friend_request_scope === undefined) setSupported(false);
        else setScope(profile.friend_request_scope);
      })
      .catch(() => setError("Couldn't load your settings."));
  }, [getToken, isSignedIn]);

  if (!isSignedIn || !supported) return null;

  const handleChange = async (next: FriendRequestScope) => {
    const previous = scope;
    setScope(next);
    setSaving(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await updateProfile(token, { friend_request_scope: next });
    } catch {
      setScope(previous);
      setError("Something went wrong. Try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="mt-8" data-testid="friend-request-settings">
      <h2 className="text-primary" style={{ fontSize: 14, fontWeight: 500 }}>
        Friends
      </h2>
      <div className="mt-3 flex items-center justify-between">
        <label htmlFor="friend-request-scope" className="text-secondary" style={{ fontSize: 13 }}>
          Who can send you friend requests
        </label>
        {scope === null ? (
          <span className="text-tertiary text-[13px]" data-testid="friend-scope-unknown">
            {error ? "unavailable" : "…"}
          </span>
        ) : (
          <Select
            value={scope}
            onValueChange={(value) => void handleChange(value as FriendRequestScope)}
            disabled={saving}
          >
            <SelectTrigger id="friend-request-scope">
              <SelectValue>{OPTIONS.find((opt) => opt.value === scope)?.label}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              {OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>
      <p className="text-tertiary mt-2 text-xs">
        Declining a request never tells the other person.
      </p>
      {error && (
        <p className="text-destructive mt-2 text-[13px]" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
