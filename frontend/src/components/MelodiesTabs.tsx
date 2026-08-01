"use client";

import { useState } from "react";
import MelodyInbox from "@/components/MelodyInbox";
import MelodySentList from "@/components/MelodySentList";
import type { MelodyInboxItem, MelodySentItem } from "@/types";

interface MelodiesTabsProps {
  inboxItems: MelodyInboxItem[];
  inboxCursor: string | null;
  sentItems: MelodySentItem[];
  sentCursor: string | null;
}

export default function MelodiesTabs({
  inboxItems,
  inboxCursor,
  sentItems,
  sentCursor,
}: MelodiesTabsProps) {
  const [tab, setTab] = useState<"inbox" | "sent">("inbox");

  const tabButton = (key: "inbox" | "sent", label: string) => {
    const active = tab === key;
    return (
      <button
        onClick={() => setTab(key)}
        aria-pressed={active}
        className={`border-b-[1.5px] py-1.5 text-[13px] ${
          active
            ? "text-primary border-accent font-medium"
            : "text-tertiary hover:text-secondary border-transparent"
        }`}
      >
        {label}
      </button>
    );
  };

  return (
    <div>
      <div className="border-hairline flex border-b" style={{ gap: 20 }}>
        {tabButton("inbox", "Inbox")}
        {tabButton("sent", "Sent")}
      </div>
      {tab === "inbox" ? (
        <MelodyInbox initialItems={inboxItems} initialCursor={inboxCursor} />
      ) : (
        <MelodySentList initialItems={sentItems} initialCursor={sentCursor} />
      )}
    </div>
  );
}
