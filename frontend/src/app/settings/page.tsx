import AppShell from "@/components/AppShell";
import MelodySettings from "@/components/MelodySettings";

// Profile editing (name, username, bio, visibility, avatar, Spotify) lives
// inline on the profile page now. This route holds global app settings.
export default function SettingsPage() {
  return (
    <AppShell>
      <main className="mx-auto max-w-2xl px-4 py-10">
        <h1 className="text-primary mb-2 text-2xl font-light tracking-tight">Settings</h1>
        <MelodySettings />
      </main>
    </AppShell>
  );
}
