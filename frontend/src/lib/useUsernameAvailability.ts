"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { checkUsernameAvailable } from "@/lib/users";

/**
 * Username rules, mirroring the backend's `_USERNAME_RE`
 * (`backend/app/schemas/user.py`). The server is still the authority — this
 * only saves a round trip on input the API would reject anyway.
 */
export const USERNAME_RE = /^[a-zA-Z0-9_-]{3,30}$/;

const DEBOUNCE_MS = 300;

export type AvailabilityState =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "available" }
  | { kind: "taken" }
  | { kind: "invalid" }
  // The field holds the username the account already has — nothing to check.
  | { kind: "unchanged" }
  // The check itself failed (offline, rate limited, backend down). Distinct
  // from "taken": the server never gave an answer, so this must not block.
  | { kind: "error" };

/**
 * Debounced username availability, shared by onboarding and profile editing.
 *
 * Extracted because both forms had their own copy and they had drifted: the
 * profile editor was missing the stale-response guard and the unmount
 * cleanup, so a slow answer could overwrite a newer one and a late callback
 * could set state on an unmounted component (ADR 0010, rule 3).
 *
 * Pass `currentUsername` where the field starts populated — the value the
 * account already holds reports as `unchanged` rather than `taken`.
 */
export function useUsernameAvailability(currentUsername?: string) {
  const [availability, setAvailability] = useState<AvailabilityState>({ kind: "idle" });

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // The username the newest check was started for. A slower earlier request
  // must not overwrite the result for what's in the field now.
  const inFlightRef = useRef<string | null>(null);

  const check = useCallback(
    (value: string) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      inFlightRef.current = value;

      if (currentUsername !== undefined && value === currentUsername) {
        setAvailability({ kind: "unchanged" });
        return;
      }
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
      }, DEBOUNCE_MS);
    },
    [currentUsername]
  );

  // Clear the debounce on unmount so a late callback can't set state on a
  // component that's already gone.
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  return { availability, check };
}
