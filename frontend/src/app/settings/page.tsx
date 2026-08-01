import AppShell from "@/components/AppShell";
import ConnectedAccounts from "@/components/ConnectedAccounts";
import MelodySettings from "@/components/MelodySettings";

// Profile editing (name, username, bio, visibility, avatar) lives inline on
// the profile page. This route holds global app settings — things that belong
// to the account rather than to how a profile presents itself.
export default async function SettingsPage(props: { searchParams: Promise<{ spotify?: string }> }) {
  const { spotify } = await props.searchParams;

  return (
    <AppShell>
      <main className="mx-auto max-w-2xl space-y-10 px-4 py-10">
        <h1 className="text-primary text-2xl font-light tracking-tight">Settings</h1>
        <ConnectedAccounts justConnected={spotify === "connected"} />
        <MelodySettings />
      </main>
    </AppShell>
  );
}
