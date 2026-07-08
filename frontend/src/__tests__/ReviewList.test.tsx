import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ReviewList from "@/components/ReviewList";
import type { RatingRead } from "@/types";

// ── Module mocks ──────────────────────────────────────────────────────────────

let mockUsername: string | null = "viewer";

vi.mock("@clerk/nextjs", () => ({
  useUser: () => ({
    user: mockUsername ? { username: mockUsername } : null,
  }),
  useAuth: () => ({
    getToken: async () => "test-token",
  }),
}));

const deleteRatingMock = vi.fn();
const updateVisibilityMock = vi.fn();

vi.mock("@/lib/ratings", () => ({
  deleteRating: (...args: unknown[]) => deleteRatingMock(...args),
  reportRating: vi.fn(),
  updateRatingVisibility: (...args: unknown[]) => updateVisibilityMock(...args),
}));

vi.mock("@/components/AvatarImage", () => ({
  default: () => <span data-testid="avatar" />,
}));

vi.mock("@/components/VisibilitySelect", () => ({
  default: ({ onChange }: { onChange: (v: string) => void }) => (
    <button data-testid="vis-select" onClick={() => onChange("private")}>
      visibility
    </button>
  ),
}));

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeReview(overrides: Partial<RatingRead> & { id: string }): RatingRead {
  return {
    reviewer: { username: "viewer", display_name: "Viewer", avatar_url: null },
    score: 7,
    review_text: "Great album",
    visibility: "public",
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("ReviewList — delete", () => {
  beforeEach(() => {
    mockUsername = "viewer";
    deleteRatingMock.mockReset();
    updateVisibilityMock.mockReset();
  });

  it("owner's delete button calls the API and onDeleted", async () => {
    deleteRatingMock.mockResolvedValue(undefined);
    const onDeleted = vi.fn();

    render(
      <ReviewList
        reviews={[makeReview({ id: "r-1" })]}
        onDeleted={onDeleted}
        onVisibilityChanged={vi.fn()}
      />
    );

    fireEvent.click(screen.getByText("Delete"));

    await waitFor(() => {
      expect(deleteRatingMock).toHaveBeenCalledWith("test-token", "r-1");
      expect(onDeleted).toHaveBeenCalledWith("r-1");
    });
  });

  it("failed delete surfaces an error and keeps the review", async () => {
    deleteRatingMock.mockRejectedValue(new Error("Couldn't delete. Try again."));
    const onDeleted = vi.fn();

    render(
      <ReviewList
        reviews={[makeReview({ id: "r-1" })]}
        onDeleted={onDeleted}
        onVisibilityChanged={vi.fn()}
      />
    );

    fireEvent.click(screen.getByText("Delete"));

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toMatch(/couldn't delete/i);
    });
    expect(onDeleted).not.toHaveBeenCalled();
    expect(screen.getByText("Great album")).toBeTruthy();
  });

  it("non-owner sees Report, not Delete", () => {
    render(
      <ReviewList
        reviews={[
          makeReview({
            id: "r-2",
            reviewer: { username: "alice", display_name: "Alice", avatar_url: null },
          }),
        ]}
        onDeleted={vi.fn()}
        onVisibilityChanged={vi.fn()}
      />
    );

    expect(screen.queryByText("Delete")).toBeNull();
    expect(screen.getByText("Report")).toBeTruthy();
  });
});

describe("ReviewList — visibility change", () => {
  beforeEach(() => {
    mockUsername = "viewer";
    deleteRatingMock.mockReset();
    updateVisibilityMock.mockReset();
  });

  it("successful change calls the API and onVisibilityChanged", async () => {
    updateVisibilityMock.mockResolvedValue(undefined);
    const onVisibilityChanged = vi.fn();

    render(
      <ReviewList
        reviews={[makeReview({ id: "r-1" })]}
        onDeleted={vi.fn()}
        onVisibilityChanged={onVisibilityChanged}
      />
    );

    fireEvent.click(screen.getByTestId("vis-select"));

    await waitFor(() => {
      expect(updateVisibilityMock).toHaveBeenCalledWith("test-token", "r-1", "private");
      expect(onVisibilityChanged).toHaveBeenCalledWith("r-1", "private");
    });
  });

  it("failed change surfaces an error instead of silently pretending it worked", async () => {
    updateVisibilityMock.mockRejectedValue(new Error("network"));
    const onVisibilityChanged = vi.fn();

    render(
      <ReviewList
        reviews={[makeReview({ id: "r-1" })]}
        onDeleted={vi.fn()}
        onVisibilityChanged={onVisibilityChanged}
      />
    );

    fireEvent.click(screen.getByTestId("vis-select"));

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toMatch(/couldn't update visibility/i);
    });
    expect(onVisibilityChanged).not.toHaveBeenCalled();
  });
});
