"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useState } from "react";
import { dismissReport, getReports, hideRating, suspendUser } from "@/lib/moderation";
import type { ReportQueueItem } from "@/types";

interface ModerationQueueProps {
  initialItems: ReportQueueItem[];
  initialCursor: string | null;
}

function QueueAction({
  label,
  onClick,
  disabled,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="border-hairline text-secondary hover:text-primary rounded-control border disabled:opacity-50"
      style={{ padding: "5px 10px", fontSize: 12 }}
    >
      {label}
    </button>
  );
}

export default function ModerationQueue({
  initialItems,
  initialCursor,
}: ModerationQueueProps) {
  const { getToken } = useAuth();
  const [items, setItems] = useState(initialItems);
  const [cursor, setCursor] = useState(initialCursor);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [confirmSuspendId, setConfirmSuspendId] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (reportId: string, fn: (token: string) => Promise<void>) => {
    if (busyId) return;
    setBusyId(reportId);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await fn(token);
      setItems((prev) => prev.filter((r) => r.id !== reportId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusyId(null);
      setConfirmSuspendId(null);
    }
  };

  const loadMore = async () => {
    if (!cursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const page = await getReports(token, "open", cursor);
      setItems((prev) => [...prev, ...page.items]);
      setCursor(page.next_cursor);
    } catch {
      setError("Couldn't load more. Try again.");
    } finally {
      setLoadingMore(false);
    }
  };

  if (items.length === 0) {
    return (
      <p className="text-tertiary" style={{ fontSize: 13, padding: "24px 0" }}>
        No open reports.
      </p>
    );
  }

  return (
    <div className="flex flex-col" style={{ gap: 12, paddingTop: 16 }}>
      {error && (
        <p style={{ color: "#f87171", fontSize: 13 }} role="alert">
          {error}
        </p>
      )}
      {items.map((report) => {
        const busy = busyId === report.id;
        const confirming = confirmSuspendId === report.id;
        return (
          <article
            key={report.id}
            className="bg-tile border-hairline border"
            style={{ borderRadius: 14, padding: 16 }}
            data-testid="report-row"
          >
            <header className="flex items-center justify-between" style={{ fontSize: 12 }}>
              <span className="text-tertiary">
                Reported by{" "}
                <Link
                  href={`/u/${report.reporter.username}`}
                  className="hover:text-secondary"
                >
                  @{report.reporter.username}
                </Link>
                {report.open_report_count > 1 &&
                  ` · ${report.open_report_count} open reports on this review`}
              </span>
              <span className="text-tertiary">
                {new Date(report.created_at).toLocaleDateString()}
              </span>
            </header>

            <div className="mt-3">
              <p className="text-secondary" style={{ fontSize: 12 }}>
                <Link
                  href={`/u/${report.rating.author.username}`}
                  className="text-primary hover:text-secondary"
                >
                  {report.rating.author.display_name}
                </Link>{" "}
                @{report.rating.author.username} · scored {report.rating.score}/10
                {report.rating.hidden && " · already hidden"}
                {report.rating.author_suspended && " · author suspended"}
              </p>
              <p className="text-primary mt-2" style={{ fontSize: 13, lineHeight: 1.5 }}>
                {report.rating.review_text}
              </p>
            </div>

            <footer className="mt-4 flex items-center" style={{ gap: 8 }}>
              {!report.rating.hidden && (
                <QueueAction
                  label="Hide review"
                  disabled={busy}
                  onClick={() =>
                    void run(report.id, (token) => hideRating(token, report.rating.id))
                  }
                />
              )}
              <QueueAction
                label="Dismiss report"
                disabled={busy}
                onClick={() =>
                  void run(report.id, (token) => dismissReport(token, report.id))
                }
              />
              {!report.rating.author_suspended &&
                (confirming ? (
                  <>
                    <QueueAction
                      label={`Confirm — suspend @${report.rating.author.username}`}
                      disabled={busy}
                      onClick={() =>
                        void run(report.id, (token) =>
                          suspendUser(token, report.rating.author.username)
                        )
                      }
                    />
                    <QueueAction
                      label="Cancel"
                      disabled={busy}
                      onClick={() => setConfirmSuspendId(null)}
                    />
                  </>
                ) : (
                  <QueueAction
                    label="Suspend author…"
                    disabled={busy}
                    onClick={() => setConfirmSuspendId(report.id)}
                  />
                ))}
            </footer>
          </article>
        );
      })}
      {cursor && (
        <button
          onClick={() => void loadMore()}
          disabled={loadingMore}
          className="text-tertiary hover:text-secondary self-start disabled:opacity-50"
          style={{ fontSize: 13, padding: "6px 0" }}
        >
          {loadingMore ? "Loading…" : "Show more"}
        </button>
      )}
    </div>
  );
}
