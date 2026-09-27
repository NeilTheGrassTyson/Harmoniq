import type { MelodyInboxItem, MelodySentItem } from "@/types";

export interface MelodyStamp {
  label: string;
  /** ISO 8601 from the API; formatted in the viewer's zone after mount. */
  at: string;
}

const OUTCOME_LABELS: Partial<Record<MelodyInboxItem["status"], string>> = {
  accepted: "Accepted",
  opened: "Opened",
  rejected: "Passed",
};

/** Recipient: when it arrived, then when the current outcome was reached. */
export function inboxStamps(item: MelodyInboxItem): MelodyStamp[] {
  const stamps: MelodyStamp[] = [];
  if (item.received_at) stamps.push({ label: "Received", at: item.received_at });
  const outcome = OUTCOME_LABELS[item.status];
  if (outcome && item.responded_at) stamps.push({ label: outcome, at: item.responded_at });
  return stamps;
}

/**
 * Sender: when they sent it, then the outcome. Never a "Received" row — the
 * sent view carries no delivery time at all, because on this side it would be
 * a read receipt (HARMONIQ.md §6).
 */
export function sentStamps(item: MelodySentItem): MelodyStamp[] {
  const stamps: MelodyStamp[] = [{ label: "Sent", at: item.created_at }];
  const outcome = OUTCOME_LABELS[item.status];
  if (outcome && item.responded_at) stamps.push({ label: outcome, at: item.responded_at });
  return stamps;
}

/**
 * "Sun 30 Aug, 8:22 PM" — the mockup's order, with the viewer's locale
 * choosing month names and 12- or 24-hour time.
 */
export function formatStamp(iso: string, locale?: string, timeZone?: string): string {
  const date = new Date(iso);
  const dayParts = new Intl.DateTimeFormat(locale, {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone,
  }).formatToParts(date);
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    dayParts.find((p) => p.type === type)?.value ?? "";
  const time = new Intl.DateTimeFormat(locale, {
    hour: "numeric",
    minute: "2-digit",
    timeZone,
  }).format(date);
  return `${part("weekday")} ${part("day")} ${part("month")}, ${time}`;
}
