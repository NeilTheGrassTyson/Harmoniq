import AppShell from "@/components/AppShell";
import { FollowListSkeleton } from "@/components/skeletons/EntitySkeletons";

export default function Loading() {
  return (
    <AppShell>
      <FollowListSkeleton />
    </AppShell>
  );
}
