import { SignUp } from "@clerk/nextjs";
import AuthScreen from "@/components/AuthScreen";

export default function SignUpPage() {
  return (
    <AuthScreen caption="Music, shared between people who trust each other's taste.">
      {/* A completed sign-up goes straight to onboarding, and `force` rather
          than `fallback` so a ?redirect_url= deep link cannot skip it either.
          The proxy.ts gate cannot be what catches this: it only redirects an
          un-onboarded user away from *protected* routes, and Clerk's own
          default lands a new account on "/", which is public. Anyone who
          signed up and stayed on a browse surface therefore never reached
          this form, never got a Harmoniq record, and lost the Profile link
          for good. An already-onboarded account that arrives here is bounced
          back out by that same gate. */}
      <SignUp forceRedirectUrl="/onboarding" />
    </AuthScreen>
  );
}
