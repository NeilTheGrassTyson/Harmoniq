import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { ReportQueueItem } from "@/types";

// ── Module mocks ──────────────────────────────────────────────────────────────

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: async () => "test-token" }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

const mockHide = vi.fn();
const mockDismiss = vi.fn();
const mockSuspend = vi.fn();
vi.mock("@/lib/moderation", () => ({
  hideRating: (...args: unknown[]) => mockHide(...args),
  dismissReport: (...args: unknown[]) => mockDismiss(...args),
  suspendUser: (...args: unknown[]) => mockSuspend(...args),
  getReports: vi.fn(),
}));

import ModerationQueue from "@/components/ModerationQueue";

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeReport(overrides: Partial<ReportQueueItem> & { id: string }): ReportQueueItem {
  return {
    status: "open",
    created_at: new Date().toISOString(),
    reporter: { id: "u1", username: "alice", display_name: "Alice", avatar_url: null },
    rating: {
      id: "r1",
      entity_type: "track",
      score: 2,
      review_text: "Something reportable.",
      hidden: false,
      author: { id: "u2", username: "bob", display_name: "Bob", avatar_url: null },
      author_suspended: false,
    },
    open_report_count: 1,
    ...overrides,
  };
}

beforeEach(() => {
  mockHide.mockReset();
  mockDismiss.mockReset();
  mockSuspend.mockReset();
});

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("ModerationQueue", () => {
  it("renders report context and actions", () => {
    render(<ModerationQueue initialItems={[makeReport({ id: "rep1" })]} initialCursor={null} />);

    expect(screen.getByText("Something reportable.")).toBeDefined();
    expect(screen.getByText("Hide review")).toBeDefined();
    expect(screen.getByText("Dismiss report")).toBeDefined();
    expect(screen.getByText("Suspend author…")).toBeDefined();
  });

  it("hide review calls the API and removes the row", async () => {
    mockHide.mockResolvedValue(undefined);
    render(<ModerationQueue initialItems={[makeReport({ id: "rep1" })]} initialCursor={null} />);

    fireEvent.click(screen.getByText("Hide review"));

    await waitFor(() => {
      expect(mockHide).toHaveBeenCalledWith("test-token", "r1");
      expect(screen.queryByTestId("report-row")).toBeNull();
    });
  });

  it("dismiss calls the API and removes the row", async () => {
    mockDismiss.mockResolvedValue(undefined);
    render(<ModerationQueue initialItems={[makeReport({ id: "rep1" })]} initialCursor={null} />);

    fireEvent.click(screen.getByText("Dismiss report"));

    await waitFor(() => {
      expect(mockDismiss).toHaveBeenCalledWith("test-token", "rep1");
      expect(screen.queryByTestId("report-row")).toBeNull();
    });
  });

  it("suspend requires a two-step confirm", async () => {
    mockSuspend.mockResolvedValue(undefined);
    render(<ModerationQueue initialItems={[makeReport({ id: "rep1" })]} initialCursor={null} />);

    fireEvent.click(screen.getByText("Suspend author…"));
    // Nothing sent yet — confirm step shown instead.
    expect(mockSuspend).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText("Confirm — suspend @bob"));

    await waitFor(() => {
      expect(mockSuspend).toHaveBeenCalledWith("test-token", "bob");
    });
  });

  it("cancel backs out of the suspend confirm", () => {
    render(<ModerationQueue initialItems={[makeReport({ id: "rep1" })]} initialCursor={null} />);

    fireEvent.click(screen.getByText("Suspend author…"));
    fireEvent.click(screen.getByText("Cancel"));

    expect(screen.getByText("Suspend author…")).toBeDefined();
    expect(mockSuspend).not.toHaveBeenCalled();
  });

  it("shows the empty state with no open reports", () => {
    render(<ModerationQueue initialItems={[]} initialCursor={null} />);
    expect(screen.getByText("No open reports.")).toBeDefined();
  });
});
