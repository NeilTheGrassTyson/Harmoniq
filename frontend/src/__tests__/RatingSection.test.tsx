import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import RatingSection from "@/components/RatingSection";
import type { RatingRead } from "@/types";

// ── Module mocks ──────────────────────────────────────────────────────────────

let mockUsername: string | null = "viewer";

vi.mock("@clerk/nextjs", () => ({
  useUser: () => ({
    isSignedIn: !!mockUsername,
    user: mockUsername ? { username: mockUsername } : null,
  }),
}));

// RatingComposer: captures onSubmitted so tests can trigger it via a button
let capturedOnSubmitted: ((r: RatingRead) => void) | undefined;

vi.mock("@/components/RatingComposer", () => ({
  default: ({
    onSubmitted,
    initialRating,
  }: {
    onSubmitted?: (r: RatingRead) => void;
    initialRating?: { score: number; review_text: string; visibility: string };
  }) => {
    capturedOnSubmitted = onSubmitted;
    return (
      <div>
        <span data-testid="composer-prefilled">{initialRating ? "prefilled" : "blank"}</span>
        <button data-testid="composer-submit">submit</button>
      </div>
    );
  },
}));

// ReviewList: renders review IDs so tests can count/inspect them, and a
// per-item delete trigger so tests can exercise onDeleted.
vi.mock("@/components/ReviewList", () => ({
  default: ({
    reviews,
    onDeleted,
  }: {
    reviews: RatingRead[];
    onDeleted: (id: string) => void;
    onVisibilityChanged: (id: string, v: string) => void;
  }) => (
    <ul>
      {reviews.map((r) => (
        <li key={r.id} data-testid="review-item" data-review-id={r.id}>
          {r.reviewer.username}: {r.score}
          <button data-testid={`delete-${r.id}`} onClick={() => onDeleted(r.id)}>
            delete
          </button>
        </li>
      ))}
    </ul>
  ),
}));

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeReview(overrides: Partial<RatingRead> & { id: string }): RatingRead {
  return {
    reviewer: { username: "someone", display_name: "Someone", avatar_url: null },
    score: 7,
    review_text: "Great album",
    visibility: "public",
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

const reviewA = makeReview({
  id: "r-a",
  reviewer: { username: "alice", display_name: "Alice", avatar_url: null },
  score: 8,
});
const reviewB = makeReview({
  id: "r-b",
  reviewer: { username: "bob", display_name: "Bob", avatar_url: null },
  score: 6,
});

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("RatingSection — optimistic update on submit", () => {
  beforeEach(() => {
    mockUsername = "viewer";
    capturedOnSubmitted = undefined;
  });

  it("adds a new review row when the user submits a fresh review", async () => {
    render(
      <RatingSection
        entityType="album"
        entityMbid="mbid-1"
        initialReviews={[reviewA, reviewB]}
        initialAggregate={7.0}
      />
    );

    const itemsBefore = screen.getAllByTestId("review-item");
    expect(itemsBefore).toHaveLength(2);

    const newReview = makeReview({
      id: "r-new",
      reviewer: { username: "viewer", display_name: "Viewer", avatar_url: null },
      score: 9,
    });

    await act(async () => {
      capturedOnSubmitted?.(newReview);
    });

    const itemsAfter = screen.getAllByTestId("review-item");
    expect(itemsAfter).toHaveLength(3);
  });

  it("replaces the existing review row instead of inserting a duplicate", async () => {
    // viewer already has a review in the list
    const viewerExistingReview = makeReview({
      id: "r-viewer",
      reviewer: { username: "viewer", display_name: "Viewer", avatar_url: null },
      score: 5,
    });

    render(
      <RatingSection
        entityType="album"
        entityMbid="mbid-1"
        initialReviews={[reviewA, viewerExistingReview]}
        initialAggregate={6.5}
      />
    );

    const itemsBefore = screen.getAllByTestId("review-item");
    expect(itemsBefore).toHaveLength(2);

    const updatedReview = makeReview({
      id: "r-viewer", // same ID — upsert returns the same record
      reviewer: { username: "viewer", display_name: "Viewer", avatar_url: null },
      score: 8,
    });

    await act(async () => {
      capturedOnSubmitted?.(updatedReview);
    });

    // List length must stay the same — no duplicate
    const itemsAfter = screen.getAllByTestId("review-item");
    expect(itemsAfter).toHaveLength(2);

    // The updated score is now shown
    expect(screen.getByText(/viewer: 8/)).toBeTruthy();
    expect(screen.queryByText(/viewer: 5/)).toBeNull();
  });

  it("pre-fills the composer when the user already has a review in initialReviews", () => {
    const viewerReview = makeReview({
      id: "r-viewer",
      reviewer: { username: "viewer", display_name: "Viewer", avatar_url: null },
      score: 7,
    });

    render(
      <RatingSection
        entityType="album"
        entityMbid="mbid-1"
        initialReviews={[viewerReview, reviewA]}
        initialAggregate={7.5}
      />
    );

    expect(screen.getByTestId("composer-prefilled").textContent).toBe("prefilled");
  });

  it("passes blank initialRating when the user has no existing review", () => {
    render(
      <RatingSection
        entityType="album"
        entityMbid="mbid-1"
        initialReviews={[reviewA, reviewB]}
        initialAggregate={7.0}
      />
    );

    expect(screen.getByTestId("composer-prefilled").textContent).toBe("blank");
  });

  it("removes the review row when a review is deleted", async () => {
    render(
      <RatingSection
        entityType="album"
        entityMbid="mbid-1"
        initialReviews={[reviewA, reviewB]}
        initialAggregate={7.0}
      />
    );

    expect(screen.getAllByTestId("review-item")).toHaveLength(2);

    await act(async () => {
      fireEvent.click(screen.getByTestId("delete-r-a"));
    });

    const itemsAfter = screen.getAllByTestId("review-item");
    expect(itemsAfter).toHaveLength(1);
    expect(screen.queryByText(/alice: 8/)).toBeNull();
  });
});
