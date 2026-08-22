"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useAuth, useUser } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Form, FormControl, FormField, FormItem, FormLabel } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { friendlyError } from "@/lib/apiBase";
import { checkUsernameAvailable, createUser } from "@/lib/users";

const USERNAME_RE = /^[a-zA-Z0-9_-]{3,30}$/;

const onboardingSchema = z.object({
  username: z.string().regex(USERNAME_RE),
  displayName: z.string().trim().min(1).max(50),
});

type OnboardingValues = z.infer<typeof onboardingSchema>;

type AvailabilityState =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "available" }
  | { kind: "taken" }
  | { kind: "invalid" }
  // The check itself failed (offline, rate limited, backend down). Distinct
  // from "taken": the server never gave an answer, so this must not block.
  | { kind: "error" };

export default function OnboardingPage() {
  const { getToken } = useAuth();
  const { user, isLoaded } = useUser();
  const router = useRouter();

  const [availability, setAvailability] = useState<AvailabilityState>({
    kind: "idle",
  });
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Derive the default display name from the Clerk profile once it loads.
  // Falls back to the Clerk username, since email/password sign-ups arrive
  // with no first or last name at all.
  const clerkName =
    isLoaded && user
      ? (([user.firstName, user.lastName].filter(Boolean).join(" ") || user.username) ?? "")
      : "";

  const form = useForm<OnboardingValues>({
    resolver: zodResolver(onboardingSchema),
    mode: "onChange",
    defaultValues: { username: "", displayName: "" },
  });

  // Seed the display name from Clerk unless the user already edited it.
  // Deliberately without shouldValidate: a validation kicked off here races
  // the ones the user's own keystrokes start, and the loser of that race
  // used to pin formState.isValid to false for the rest of the session —
  // leaving Continue greyed out with nothing on screen explaining why. The
  // submit gate below reads the values directly instead, so nothing depends
  // on RHF's async validity bookkeeping.
  const nameEditedRef = useRef(false);
  useEffect(() => {
    if (!nameEditedRef.current && clerkName && !form.getValues("displayName")) {
      form.setValue("displayName", clerkName);
    }
  }, [clerkName, form]);

  // Users who already have a Harmoniq account never reach this page — the
  // proxy.ts gate checks the backend record and redirects them away, even
  // when the JWT's onboarded claim is stale or missing.

  // Debounced availability check — server-side truth, outside the zod schema.
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // The username the newest check was started for. A slower earlier request
  // must not overwrite the result for what's in the field now.
  const inFlightRef = useRef<string | null>(null);

  const handleUsernameChange = useCallback((value: string) => {
    setSubmitError(null);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    inFlightRef.current = value;

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
        if (inFlightRef.current !== value) return;
        setAvailability(result.available ? { kind: "available" } : { kind: "taken" });
      } catch {
        if (inFlightRef.current !== value) return;
        setAvailability({ kind: "error" });
      }
    }, 300);
  }, []);

  // Clear the debounce on unmount so a late callback can't set state on a
  // component that's already gone.
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const onSubmit = async (values: OnboardingValues) => {
    setSubmitError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");
      const profile = await createUser(token, values.username, values.displayName.trim());

      // Force a session reload so the Clerk JWT picks up onboarded=true.
      await user?.reload();
      router.replace(`/u/${profile.username}`);
    } catch (err: unknown) {
      // Never the raw message: a fetch that never reached the backend throws
      // "Load failed" in Safari and "Failed to fetch" in Chrome, and putting
      // either in front of someone trying to sign up tells them nothing.
      // Server-sent detail messages ("That username is taken.") pass through.
      setSubmitError(friendlyError(err));
    }
  };

  // The submit gate is computed from the current values, not from
  // formState.isValid — see the seeding comment above. handleSubmit still
  // runs the resolver before onSubmit, so this only ever opens the button;
  // it can't let an invalid value through.
  const values = useWatch({ control: form.control });
  const parsed = onboardingSchema.safeParse(values);
  const isSubmitting = form.formState.isSubmitting;
  // "error" counts as passable: the server is the authority on uniqueness and
  // answers again on submit, so a check we couldn't complete is not a wall.
  const usernameSettled = availability.kind === "available" || availability.kind === "error";
  const canSubmit = parsed.success && usernameSettled && !isSubmitting;

  // Named so the button is never inert without a reason on screen.
  const blockedReason = (() => {
    if (canSubmit || isSubmitting) return null;
    if (!values?.username) return "Choose a username to continue.";
    if (availability.kind === "invalid" || availability.kind === "taken") return null;
    if (availability.kind === "checking") return "Checking that username…";
    if (!onboardingSchema.shape.displayName.safeParse(values?.displayName ?? "").success) {
      return "Add a display name — it's how you appear on Harmoniq.";
    }
    return null;
  })();

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-6 py-16">
      <h1 className="text-primary mb-1 text-2xl font-light tracking-tight">Choose a username</h1>
      <p className="text-secondary mb-8 text-sm">
        Your username appears in your profile URL and @mentions.
      </p>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
          <FormField
            control={form.control}
            name="username"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="text-tertiary text-xs font-medium tracking-widest uppercase">
                  Username
                </FormLabel>
                <FormControl>
                  <Input
                    {...field}
                    onChange={(e) => {
                      field.onChange(e);
                      handleUsernameChange(e.target.value);
                    }}
                    placeholder="yourname"
                    autoComplete="off"
                    autoCapitalize="none"
                    spellCheck={false}
                    maxLength={30}
                    className="h-auto px-3 py-2 text-sm"
                  />
                </FormControl>
                <div className="min-h-[1.25rem] text-xs">
                  {availability.kind === "invalid" && (
                    <span role="alert" className="text-destructive">
                      Usernames can only contain letters, numbers, underscores, and hyphens (3–30
                      characters).
                    </span>
                  )}
                  {availability.kind === "taken" && (
                    <span role="alert" className="text-destructive">
                      That username is taken.
                    </span>
                  )}
                  {availability.kind === "error" && (
                    <span className="text-tertiary">
                      Couldn&apos;t check that username. You can continue — we&apos;ll confirm it
                      when you finish.
                    </span>
                  )}
                  {availability.kind === "available" && (
                    <span className="text-accent">Available.</span>
                  )}
                  {availability.kind === "checking" && (
                    <span className="text-tertiary">Checking…</span>
                  )}
                  {availability.kind === "idle" && field.value.length === 0 && (
                    <span className="text-tertiary">
                      Letters, numbers, _ and - · 3–30 characters
                    </span>
                  )}
                </div>
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="displayName"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="text-tertiary text-xs font-medium tracking-widest uppercase">
                  Display name
                </FormLabel>
                <FormControl>
                  <Input
                    {...field}
                    onChange={(e) => {
                      nameEditedRef.current = true;
                      field.onChange(e);
                    }}
                    placeholder="Your name"
                    maxLength={50}
                    required
                    className="h-auto px-3 py-2 text-sm"
                  />
                </FormControl>
              </FormItem>
            )}
          />

          {submitError && (
            <p role="alert" className="text-destructive text-sm">
              {submitError}
            </p>
          )}

          <div className="space-y-2">
            <Button
              type="submit"
              disabled={!canSubmit}
              className="h-auto w-full px-4 py-2.5 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {isSubmitting ? "Creating account…" : "Continue"}
            </Button>
            <p aria-live="polite" className="text-tertiary text-center text-xs">
              {blockedReason}
            </p>
          </div>
        </form>
      </Form>
    </main>
  );
}
