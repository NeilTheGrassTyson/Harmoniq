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
import type { MelodyAcceptScope } from "@/types";

const OPTIONS: { value: MelodyAcceptScope; label: string }[] = [
  { value: "everyone", label: "Everyone" },
  { value: "follows", label: "People you follow" },
  { value: "mutuals", label: "Mutuals" },
];

/** "Who can send you Melodies" — the consent guard for inbound Melodies. */
export default function MelodySettings() {
  const { getToken, isSignedIn } = useAuth();
  const [scope, setScope] = useState<MelodyAcceptScope | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isSignedIn) return;
    getToken()
      .then(async (token) => {
        if (!token) return;
        const profile = await getOwnProfile(token);
        setScope(profile.melody_accept_scope);
      })
      .catch(() => setError("Couldn't load your settings."));
  }, [getToken, isSignedIn]);

  if (!isSignedIn) return null;

  const handleChange = async (next: MelodyAcceptScope) => {
    const previous = scope;
    setScope(next); // optimistic
    setSaving(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await updateProfile(token, { melody_accept_scope: next });
    } catch {
      setScope(previous);
      setError("Something went wrong. Try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="mt-8" data-testid="melody-settings">
      <h2 className="text-primary" style={{ fontSize: 14, fontWeight: 500 }}>
        Melodies
      </h2>
      <div className="mt-3 flex items-center justify-between">
        <label htmlFor="melody-accept-scope" className="text-secondary" style={{ fontSize: 13 }}>
          Who can send you Melodies
        </label>
        <Select
          value={scope ?? "everyone"}
          onValueChange={(value) => void handleChange(value as MelodyAcceptScope)}
          disabled={scope === null || saving}
        >
          <SelectTrigger id="melody-accept-scope">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {error && (
        <p className="mt-2" style={{ color: "#f87171", fontSize: 13 }} role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
