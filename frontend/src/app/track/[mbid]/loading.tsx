import AppShell from "@/components/AppShell";
import { TrackSkeleton } from "@/components/skeletons/EntitySkeletons";

export default function Loading() {
  return (
    <AppShell>
      <TrackSkeleton />
    </AppShell>
  );
}
