import { SignIn } from "@clerk/nextjs";
import AuthScreen from "@/components/AuthScreen";

export default function SignInPage() {
  return (
    <AuthScreen caption="Sign in to see what your friends are listening to.">
      <SignIn />
    </AuthScreen>
  );
}
