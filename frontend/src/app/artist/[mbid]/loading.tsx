import AppShell from "@/components/AppShell";
import { ArtistSkeleton } from "@/components/skeletons/EntitySkeletons";

export default function Loading() {
  return (
    <AppShell>
      <ArtistSkeleton />
    </AppShell>
  );
}
