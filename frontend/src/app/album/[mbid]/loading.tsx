import AppShell from "@/components/AppShell";
import { AlbumSkeleton } from "@/components/skeletons/EntitySkeletons";

export default function Loading() {
  return (
    <AppShell>
      <AlbumSkeleton />
    </AppShell>
  );
}
