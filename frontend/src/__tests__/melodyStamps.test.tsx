import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { formatStamp, inboxStamps, sentStamps } from "@/lib/melodyStamps";
import type { MelodyInboxItem, MelodySentItem } from "@/types";

vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ getToken: vi.fn() }) }));
vi.mock("@/components/CoverArt", () => ({ default: () => <div /> }));

import MelodySentList from "@/components/MelodySentList";

const person = { id: "u", username: "mara", display_name: "Mara", avatar_url: null };
const track = {
  id: "t",
  mbid: "mb",
  title: "Pyramid Song",
  artist_name: "Radiohead",
  cover_art_url: null,
};

const inbox = (o: Partial<MelodyInboxItem>): MelodyInboxItem => ({
  id: "m",
  sender: person,
  track,
  status: "received",
  created_at: "2026-08-30T10:00:00Z",
  received_at: "2026-08-30T20:22:00Z",
  responded_at: null,
  ...o,
});
const sent = (o: Partial<MelodySentItem>): MelodySentItem => ({
  id: "s",
  recipient: person,
  track,
  status: "sent",
  created_at: "2026-08-30T10:00:00Z",
  responded_at: null,
  ...o,
});

describe("formatStamp", () => {
  it("follows the mockup's order: weekday, day, month, time", () => {
    expect(formatStamp("2026-08-30T20:22:00Z", "en-GB", "UTC")).toBe("Sun 30 Aug, 20:22");
    expect(formatStamp("2026-08-30T20:22:00Z", "en-US", "UTC")).toBe("Sun 30 Aug, 8:22 PM");
  });

  it("uses the viewer's zone, not UTC", () => {
    expect(formatStamp("2026-08-30T02:05:00Z", "en-US", "America/New_York")).toBe(
      "Sat 29 Aug, 10:05 PM"
    );
  });
});

describe("stamp rows", () => {
  it("recipient: Received, then the outcome under its own name", () => {
    expect(inboxStamps(inbox({})).map((s) => s.label)).toEqual(["Received"]);
    for (const [status, label] of [
      ["accepted", "Accepted"],
      ["opened", "Opened"],
      ["rejected", "Passed"],
    ] as const) {
      const rows = inboxStamps(inbox({ status, responded_at: "2026-08-30T21:00:00Z" }));
      expect(rows.map((s) => s.label)).toEqual(["Received", label]);
    }
  });

  it("recipient: no outcome row without an outcome time", () => {
    expect(
      inboxStamps(inbox({ status: "accepted", responded_at: null })).map((s) => s.label)
    ).toEqual(["Received"]);
  });

  // HARMONIQ.md §6 — delivery time on the sender's side is a read receipt.
  it("sender: Sent and the outcome, never Received", () => {
    expect(sentStamps(sent({})).map((s) => s.label)).toEqual(["Sent"]);
    const rows = sentStamps(sent({ status: "rejected", responded_at: "2026-08-30T21:00:00Z" }));
    expect(rows.map((s) => s.label)).toEqual(["Sent", "Passed"]);
  });

  it("the sent list renders no Received stamp", () => {
    render(
      <MelodySentList
        initialItems={[sent({ status: "opened", responded_at: "2026-08-30T21:00:00Z" })]}
        initialCursor={null}
      />
    );
    const stamps = screen.getByTestId("melody-stamps").textContent ?? "";
    expect(stamps).toMatch(/Sent.*Opened/);
    expect(stamps).not.toMatch(/Received/);
  });
});
