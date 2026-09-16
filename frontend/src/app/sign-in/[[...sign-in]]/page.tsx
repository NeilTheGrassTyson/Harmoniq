import { SignIn } from "@clerk/nextjs";
import AuthScreen from "@/components/AuthScreen";

export default function SignInPage() {
  return (
    <AuthScreen caption="Sign in to see what your friends are listening to.">
      {/* The "Sign up" link on this screen leads to a sign-up that must land
          on onboarding too — see the sign-up page for why the route gate
          can't cover it. */}
      <SignIn signUpForceRedirectUrl="/onboarding" />
    </AuthScreen>
  );
}
