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

  if (!signedIn) {
    return (
      <SignInButton mode="modal">
        <button className="text-secondary hover:text-primary text-sm font-medium">Sign in</button>
      </SignInButton>
    );
  }

  return <UserButton />;
}
