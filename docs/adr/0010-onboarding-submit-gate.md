# ADR 0010 — The Onboarding Submit Gate Reads Values, Not `formState.isValid`

**Date:** 2026-08-18
**Status:** Accepted
**Deciders:** Founder

---

## Context

Two people invited to try Harmoniq were unable to create an account. Both
reported the same thing: on `/onboarding`, after typing a username, the
**Continue** button stayed greyed out, with nothing on screen explaining
why. Onboarding is the only path to an account, so this blocked signup
entirely for anyone who hit it.

The button was gated on `form.formState.isValid` from react-hook-form
(7.82.0), with `mode: "onChange"` and an async `zodResolver`. The page also
seeded the display-name field from the Clerk profile in a mount effect:

```ts
form.setValue("displayName", clerkName, { shouldValidate: true });
```

`shouldValidate: true` starts an async schema validation. Every keystroke in
the username field starts one too. When the Clerk session is already warm at
mount — the common case for someone who has just signed up, and the case the
seeding was written for — the seed's validation overlaps the user's first
burst of keystrokes. The two runs resolve out of order, and the loser leaves
`formState.isValid` pinned to `false`. Nothing recovers it except a further
edit made after everything has settled, which a user has no reason to
attempt: their username reads "Available.", their name is filled in, and the
button is simply dead.

Reproduced in `frontend/src/__tests__/OnboardingPage.test.tsx` ("survives a
burst of keystrokes racing the seeded display name"), which fails against
the previous implementation and passes against this one.

Two smaller faults in the same form compounded it. An empty display name —
what every email/password sign-up starts with, since Clerk supplies no first
or last name — disabled Continue with no message anywhere on the form. And a
failed availability check (offline, rate limited, backend cold) was caught
and swallowed into the `idle` state, which renders nothing: another silent
dead end.

## Decision

**The onboarding submit gate is computed synchronously from the form's
current values, not from react-hook-form's asynchronous validity state.**

```ts
const values = useWatch({ control: form.control });
const parsed = onboardingSchema.safeParse(values);
```

`handleSubmit` still runs the resolver before `onSubmit`, so this can only
ever _enable_ the button — an invalid value cannot reach the API through it.
The display name is seeded without `shouldValidate`, since nothing depends
on the validation it used to trigger.

Alongside it, three supporting rules for this form:

1. **The button is never inert without a reason on screen.** Whenever
   Continue is disabled, the form states what is missing.
2. **A failed availability check is not a "taken" username.**
   `checkUsernameAvailable` throws when the server does not answer, and the
   form treats that as passable — the write path re-checks uniqueness and
   returns 409 with a message we already surface.
3. **A stale availability response never overwrites a newer one.** The
   in-flight username is tracked and late answers for older values are
   dropped.

## Rationale

- **Simplicity Before Complexity** (HARMONIQ.md §4). A synchronous parse of
  the current values is one line and can be reasoned about completely. The
  previous gate depended on the internal ordering of concurrent async
  validations inside a third-party library — behaviour no one can explain in
  one sentence, and which no amount of care at the call site makes
  predictable.
- **Design Is a Feature** (HARMONIQ.md §8). A disabled control with no
  explanation is not a calm interface; it is a wall. The failure mode here
  was not just a bug but the absence of any way for the user to understand
  what the form wanted.
- **Quality Before Speed** (HARMONIQ.md §3). The fix is accompanied by a
  regression test that reproduces the original race, rather than a
  re-ordering of the effect that happens to make the symptom go away.

## Consequences

- `formState.isValid` is not used as a gate anywhere in the onboarding form.
  `formState.isSubmitting` still is — it is set synchronously around the
  submit handler and is not subject to this race.
- `checkUsernameAvailable` now throws on a non-OK response instead of
  returning `{ available: false }`. `ProfileEditPanel` — the other caller —
  was updated to render a distinct "couldn't check" state rather than
  reporting an unreachable server as an unavailable username.
- Any future form in this codebase that gates a control on an async
  `isValid` inherits the same failure mode. Prefer the value-derived gate.
