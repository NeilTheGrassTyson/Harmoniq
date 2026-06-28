"use client";

import { useAuth, SignInButton, UserButton } from "@clerk/nextjs";

export default function NavAuth() {
  const { isSignedIn, isLoaded } = useAuth();

  if (!isLoaded) return null;

  if (!isSignedIn) {
    return (
      <SignInButton mode="modal">
        <button className="text-secondary hover:text-primary text-sm font-medium">Sign in</button>
      </SignInButton>
    );
  }

  return <UserButton />;
}
