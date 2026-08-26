import AppShell from "@/components/AppShell";
import { ProfileSkeleton } from "@/components/skeletons/EntitySkeletons";

export default function Loading() {
  return (
    <AppShell>
      <ProfileSkeleton />
    </AppShell>
  );
}
