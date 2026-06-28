"use client";

import { useAuth, useUser } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { checkUsernameAvailable, createUser } from "@/lib/users";

const USERNAME_RE = /^[a-zA-Z0-9_-]{3,30}$/;

type AvailabilityState =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "available" }
  | { kind: "taken" }
  | { kind: "invalid" };

export default function OnboardingPage() {
  const { getToken } = useAuth();
  const { user, isLoaded } = useUser();
  const router = useRouter();

  const [username, setUsername] = useState("");
  // Tracks user edits. When null, the display name field derives from Clerk.
  const [editedName, setEditedName] = useState<string | null>(null);
  const [availability, setAvailability] = useState<AvailabilityState>({
    kind: "idle",
  });
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Derive display name: prefer user's edit, fall back to Clerk profile name.
  const clerkName =
    isLoaded && user ? [user.firstName, user.lastName].filter(Boolean).join(" ") : "";
  const displayName = editedName ?? clerkName;

  // Check if user already has a Harmoniq account (e.g. arriving from a new
  // device before the JWT has refreshed to include onboarded=true).
  useEffect(() => {
    if (!isLoaded || !user) return;
    getToken()
      .then(async (token) => {
        if (!token) return;
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/users/me`,
          { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" }
        );
        if (res.ok) {
          const profile = await res.json();
          router.replace(`/u/${profile.username}`);
        }
      })
      .catch(() => {
        // No existing account — stay on onboarding page.
      });
  }, [isLoaded, user, getToken, router]);

  // Debounced availability check
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleUsernameChange = useCallback((value: string) => {
    setUsername(value);
    setSubmitError(null);

    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!value) {
      setAvailability({ kind: "idle" });
      return;
    }
    if (!USERNAME_RE.test(value)) {
      setAvailability({ kind: "invalid" });
      return;
    }

    setAvailability({ kind: "checking" });
    debounceRef.current = setTimeout(async () => {
      try {
        const result = await checkUsernameAvailable(value);
        setAvailability(result.available ? { kind: "available" } : { kind: "taken" });
      } catch {
        setAvailability({ kind: "idle" });
      }
    }, 300);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    if (!USERNAME_RE.test(username)) return;
    if (!displayName.trim()) return;

    setSubmitting(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");
      const profile = await createUser(token, username, displayName.trim());

      // Force a session reload so the Clerk JWT picks up onboarded=true.
      await user?.reload();
      router.replace(`/u/${profile.username}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setSubmitError(message);
    } finally {
      setSubmitting(false);
    }
  };

  const usernameValid = USERNAME_RE.test(username);
  const canSubmit =
    usernameValid &&
    displayName.trim().length > 0 &&
    availability.kind === "available" &&
    !submitting;

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-6 py-16">
      <h1 className="mb-1 text-2xl font-light tracking-tight text-primary">Choose a username</h1>
      <p className="mb-8 text-sm text-secondary">
        Your username appears in your profile URL and @mentions.
      </p>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label
            htmlFor="username"
            className="mb-1.5 block text-xs font-medium tracking-widest text-tertiary uppercase"
          >
            Username
          </label>
          <input
            id="username"
            type="text"
            value={username}
            onChange={(e) => handleUsernameChange(e.target.value)}
            placeholder="yourname"
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            maxLength={30}
            className="w-full rounded-control border border-hairline bg-control px-3 py-2 text-sm text-primary placeholder:text-tertiary"
          />
          <div className="mt-1.5 min-h-[1.25rem] text-xs">
            {availability.kind === "invalid" && (
              <span role="alert" style={{ color: "#f87171" }}>
                Usernames can only contain letters, numbers, underscores, and hyphens (3–30
                characters).
              </span>
            )}
            {availability.kind === "taken" && (
              <span role="alert" style={{ color: "#f87171" }}>That username is taken.</span>
            )}
            {availability.kind === "available" && (
              <span className="text-accent">Available.</span>
            )}
            {availability.kind === "checking" && (
              <span className="text-tertiary">Checking…</span>
            )}
            {availability.kind === "idle" && username.length === 0 && (
              <span className="text-tertiary">Letters, numbers, _ and - · 3–30 characters</span>
            )}
          </div>
        </div>

        <div>
          <label
            htmlFor="display-name"
            className="mb-1.5 block text-xs font-medium tracking-widest text-tertiary uppercase"
          >
            Display name
          </label>
          <input
            id="display-name"
            type="text"
            value={displayName}
            onChange={(e) => setEditedName(e.target.value)}
            placeholder="Your name"
            maxLength={50}
            className="w-full rounded-control border border-hairline bg-control px-3 py-2 text-sm text-primary placeholder:text-tertiary"
          />
        </div>

        {submitError && <p role="alert" className="text-sm text-red-500">{submitError}</p>}

        <button
          type="submit"
          disabled={!canSubmit}
          className="w-full rounded-control bg-primary px-4 py-2.5 text-sm font-medium text-canvas transition-opacity hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitting ? "Creating account…" : "Continue"}
        </button>
      </form>
    </main>
  );
}
