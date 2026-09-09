// Replaces only the external Clerk boundary in a copied E2E build.
import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";
function session(token?: string) {
  const payload = token
    ? JSON.parse(Buffer.from(token.split(".")[1], "base64url").toString())
    : {};
  return {
    userId: payload.sub ?? null,
    token: token ?? null,
    username: payload.username ?? null,
  };
}
export async function fixtureSession() {
  return session((await cookies()).get("e2e_token")?.value);
}
function authValue(value: ReturnType<typeof session>) {
  return {
    userId: value.userId,
    getToken: async () => value.token,
    sessionClaims: { metadata: { onboarded: true } },
  };
}
export async function auth() {
  return authValue(await fixtureSession());
}
type Accessor = typeof auth & { protect: () => Promise<void> };
export function clerkMiddleware(
  handler: (
    accessor: Accessor,
    request: NextRequest,
  ) => Promise<Response | undefined>,
) {
  return async (request: NextRequest) => {
    const value = session(request.cookies.get("e2e_token")?.value);
    const accessor = Object.assign(async () => authValue(value), {
      protect: async () => {
        if (!value.userId) throw new Error("fixture-sign-in");
      },
    });
    try {
      return (await handler(accessor, request)) ?? NextResponse.next();
    } catch (error) {
      if (error instanceof Error && error.message === "fixture-sign-in")
        return NextResponse.redirect(new URL("/sign-in", request.url));
      throw error;
    }
  };
}
export function createRouteMatcher(patterns: string[]) {
  return (request: NextRequest) =>
    patterns.some((pattern) =>
      new RegExp("^" + pattern + "$").test(request.nextUrl.pathname),
    );
}
