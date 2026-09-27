/**
 * Every route into a new account must land on /onboarding.
 *
 * Onboarding is the only thing that creates a Harmoniq user record, and the
 * proxy.ts gate structurally cannot be what enforces it: that gate redirects an
 * un-onboarded user only away from *protected* routes, while Clerk's own
 * default sends a completed sign-up to "/", which is public. A new account that
 * stayed on a browse surface was therefore never asked to choose a username —
 * it existed in Clerk, had no row in the database, and lost its Profile link
 * permanently, because lib/viewer.ts resolves the handle from that missing row.
 *
 * The props below are the only thing standing between a sign-up and that dead
 * end, so each entry point is pinned here.
 */

import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import React from "react";

const signUpProps = vi.fn();
const signInProps = vi.fn();
const signInButtonProps = vi.fn();

vi.mock("@clerk/nextjs", () => ({
  SignUp: (props: Record<string, unknown>) => {
    signUpProps(props);
    return <div data-testid="sign-up" />;
  },
  SignIn: (props: Record<string, unknown>) => {
    signInProps(props);
    return <div data-testid="sign-in" />;
  },
  SignInButton: ({ children, ...props }: { children: React.ReactNode }) => {
    signInButtonProps(props);
    return <>{children}</>;
  },
  UserButton: () => <span data-testid="user-button" />,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

vi.mock("@/components/ViewerProvider", () => ({
  useViewer: () => ({ signedIn: false, username: null }),
}));

const SignUpPage = (await import("@/app/sign-up/[[...sign-up]]/page")).default;
const SignInPage = (await import("@/app/sign-in/[[...sign-in]]/page")).default;
const NavAuth = (await import("@/components/NavAuth")).default;

describe("sign-up lands on onboarding", () => {
  it("forces the hosted sign-up page to onboarding", () => {
    render(<SignUpPage />);

    // `force`, not `fallback`: a ?redirect_url= deep link must not be able to
    // carry a brand-new account past the only form that gives it a username.
    expect(signUpProps).toHaveBeenCalledWith(
      expect.objectContaining({ forceRedirectUrl: "/onboarding" })
    );
  });

  it("forces a sign-up started from the sign-in page to onboarding", () => {
    render(<SignInPage />);

    expect(signInProps).toHaveBeenCalledWith(
      expect.objectContaining({ signUpForceRedirectUrl: "/onboarding" })
    );
  });

  it("forces a sign-up started from the nav modal to onboarding", () => {
    render(<NavAuth />);

    expect(signInButtonProps).toHaveBeenCalledWith(
      expect.objectContaining({ signUpForceRedirectUrl: "/onboarding" })
    );
  });
});
