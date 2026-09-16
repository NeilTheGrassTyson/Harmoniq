"use client";
// Copied only into the disposable E2E build. Never imported by production code.
import { createContext, useContext, useCallback } from "react";
type Session = {
  userId: string | null;
  token: string | null;
  username: string | null;
};
const Context = createContext<Session>({
  userId: null,
  token: null,
  username: null,
});
export function ClerkProvider({
  children,
  fixture,
}: {
  children: React.ReactNode;
  fixture: Session;
  appearance?: unknown;
}) {
  return <Context.Provider value={fixture}>{children}</Context.Provider>;
}
export function useAuth() {
  const session = useContext(Context);
  const getToken = useCallback(async () => session.token, [session.token]);
  return {
    userId: session.userId,
    isSignedIn: !!session.userId,
    isLoaded: true,
    getToken,
  };
}
export function useUser() {
  const session = useContext(Context);
  return {
    isLoaded: true,
    isSignedIn: !!session.userId,
    user: session.userId
      ? {
          id: session.userId,
          username: session.username,
          firstName: null,
          lastName: null,
          publicMetadata: { onboarded: true },
          reload: async () => {},
          update: async () => {},
        }
      : null,
  };
}
export function SignInButton({
  children,
}: {
  children: React.ReactNode;
  mode?: string;
}) {
  return children;
}
export function UserButton() {
  return <button>Test account</button>;
}
export function SignIn() {
  return <p>Sign-in provider fixture</p>;
}
export function SignUp() {
  return <p>Sign-up provider fixture</p>;
}
export function AuthenticateWithRedirectCallback() {
  return <p>Authentication provider fixture</p>;
}
