"use client";

import { SignInButton, UserButton } from "@clerk/nextjs";
import { useViewer } from "@/components/ViewerProvider";

/**
 * Signed-in state comes from the server-resolved viewer, not `useAuth()`.
 * Gating on Clerk's `isLoaded` left the whole right side of the header empty
 * until hydration, so every page load shifted as the avatar appeared.
 * `<UserButton />` renders its own placeholder while Clerk loads.
 */
export default function NavAuth() {
  const { signedIn } = useViewer();

  // Signing up from inside this modal is the third way to reach a new account,
  // and it lands on onboarding like the other two — see the sign-up page.
  if (!signedIn) {
    return (
      <SignInButton mode="modal" signUpForceRedirectUrl="/onboarding">
        <button className="text-secondary hover:text-primary text-sm font-medium">Sign in</button>
      </SignInButton>
    );
  }

  return <UserButton />;
}
