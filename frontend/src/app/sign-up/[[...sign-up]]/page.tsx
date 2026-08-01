import { SignUp } from "@clerk/nextjs";
import AuthScreen from "@/components/AuthScreen";

export default function SignUpPage() {
  return (
    <AuthScreen caption="Music, shared between people who trust each other's taste.">
      <SignUp />
    </AuthScreen>
  );
}
