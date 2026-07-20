"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useAuth, useUser } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Form, FormControl, FormField, FormItem, FormLabel } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
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
  | { kind: "invalid" };

export default function OnboardingPage() {
  const { getToken } = useAuth();
  const { user, isLoaded } = useUser();
  const router = useRouter();

  const [availability, setAvailability] = useState<AvailabilityState>({
    kind: "idle",
  });
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Derive the default display name from the Clerk profile once it loads.
  const clerkName =
    isLoaded && user ? [user.firstName, user.lastName].filter(Boolean).join(" ") : "";

  const form = useForm<OnboardingValues>({
    resolver: zodResolver(onboardingSchema),
    mode: "onChange",
    defaultValues: { username: "", displayName: "" },
  });

  // Seed the display name from Clerk unless the user already edited it.
  const nameEditedRef = useRef(false);
  useEffect(() => {
    if (!nameEditedRef.current && clerkName && !form.getValues("displayName")) {
      form.setValue("displayName", clerkName, { shouldValidate: true });
    }
  }, [clerkName, form]);

  // Users who already have a Harmoniq account never reach this page — the
  // proxy.ts gate checks the backend record and redirects them away, even
  // when the JWT's onboarded claim is stale or missing.

  // Debounced availability check — server-side truth, outside the zod schema.
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleUsernameChange = useCallback((value: string) => {
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
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setSubmitError(message);
    }
  };

  // RHF's isSubmitting doubles as the double-submit guard: handleSubmit
  // won't re-enter while the previous submission promise is pending.
  const canSubmit =
    form.formState.isValid && availability.kind === "available" && !form.formState.isSubmitting;

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

          <Button
            type="submit"
            disabled={!canSubmit}
            className="h-auto w-full px-4 py-2.5 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {form.formState.isSubmitting ? "Creating account…" : "Continue"}
          </Button>
        </form>
      </Form>
    </main>
  );
}
