import Link from "next/link";
import AppShell from "@/components/AppShell";
import EqualizerGlyph from "@/components/EqualizerGlyph";

export default function NotFound() {
  return (
    <AppShell>
      <main className="mx-auto flex max-w-2xl flex-col items-center px-4 py-24">
        <EqualizerGlyph size={36} fill="#8b93a3" />
        <h1 className="text-primary mt-4 text-lg font-light tracking-tight">Nothing here.</h1>
        <p className="text-tertiary mt-1 text-sm">
          This page doesn&rsquo;t exist, or it may have moved.
        </p>
        <Link
          href="/"
          className="border-hairline text-secondary hover:text-primary rounded-control mt-6 border px-4 py-2 text-sm"
        >
          Back to Home
        </Link>
      </main>
    </AppShell>
  );
}
