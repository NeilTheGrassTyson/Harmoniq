import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import RatingComposer from "@/components/RatingComposer";
import type { RatingRead } from "@/types";

// ── Module mocks ──────────────────────────────────────────────────────────────

const mockGetToken = vi.fn().mockResolvedValue("mock-token");

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: mockGetToken }),
}));

vi.mock("@/components/VisibilitySelect", () => ({
  default: ({
    value,
    onChange,
    id,
  }: {
    value: string;
    onChange: (v: string) => void;
    id?: string;
  }) => (
    <select
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      data-testid="visibility-select"
    >
      <option value="public">Everyone</option>
      <option value="friends">Friends</option>
      <option value="private">Only you</option>
    </select>
  ),
}));

const mockSubmitRating = vi.fn();

vi.mock("@/lib/ratings", () => ({
  submitRating: (...args: unknown[]) => mockSubmitRating(...args),
}));

const LONG_ENOUGH_TEXT = "This is a long enough review text for testing purposes.";

function makeReturnedRating(overrides: Partial<RatingRead> = {}): RatingRead {
  return {
    id: "rating-1",
    reviewer: { username: "testuser", display_name: "Test User", avatar_url: null },
    score: 8,
    review_text: LONG_ENOUGH_TEXT,
    visibility: "public",
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("RatingComposer — blank state (no initialRating)", () => {
  it('shows "Submit review" label and blank form when no initialRating is provided', () => {
    render(<RatingComposer entityType="album" entityMbid="mbid-1" />);

    // No score selected
    const scoreButtons = screen
      .getAllByRole("button")
      .filter((b) => b.getAttribute("aria-pressed") === "true");
    expect(scoreButtons).toHaveLength(0);

    // Textarea is empty
    const textarea = screen.getByRole("textbox");
    expect((textarea as HTMLTextAreaElement).value).toBe("");

    // Submit button says "Submit review"
    expect(screen.getByRole("button", { name: "Submit review" })).toBeTruthy();
  });
});

describe("RatingComposer — pre-fill from initialRating", () => {
  const initialRating = { score: 7, review_text: LONG_ENOUGH_TEXT, visibility: "friends" };

  it("pre-selects the correct score button", () => {
    render(<RatingComposer entityType="album" entityMbid="mbid-1" initialRating={initialRating} />);

    const btn7 = screen.getAllByRole("button").find((b) => b.textContent === "7");
    expect(btn7?.getAttribute("aria-pressed")).toBe("true");
  });

  it("pre-fills the textarea with the existing review text", () => {
    render(<RatingComposer entityType="album" entityMbid="mbid-1" initialRating={initialRating} />);

    const textarea = screen.getByRole("textbox");
    expect((textarea as HTMLTextAreaElement).value).toBe(LONG_ENOUGH_TEXT);
  });

  it('changes submit button label to "Update review" when initialRating is provided', () => {
    render(<RatingComposer entityType="album" entityMbid="mbid-1" initialRating={initialRating} />);

    expect(screen.getByRole("button", { name: "Update review" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Submit review" })).toBeNull();
  });

  it("calls submitRating (POST upsert) with the current form values on submit", async () => {
    const returnedRating = makeReturnedRating({ score: 7 });
    mockSubmitRating.mockResolvedValueOnce(returnedRating);

    render(<RatingComposer entityType="album" entityMbid="mbid-1" initialRating={initialRating} />);

    const submitBtn = screen.getByRole("button", { name: "Update review" });
    await act(async () => {
      fireEvent.click(submitBtn);
    });

    expect(mockSubmitRating).toHaveBeenCalledWith(
      "mock-token",
      expect.objectContaining({
        entity_type: "album",
        entity_mbid: "mbid-1",
        score: 7,
      })
    );
  });
});

describe("RatingComposer — new review submit", () => {
  beforeEach(() => {
    mockSubmitRating.mockClear();
  });

  it("calls submitRating and invokes onSubmitted callback", async () => {
    const returnedRating = makeReturnedRating({ score: 9 });
    mockSubmitRating.mockResolvedValueOnce(returnedRating);
    const onSubmitted = vi.fn();

    render(<RatingComposer entityType="track" entityMbid="mbid-2" onSubmitted={onSubmitted} />);

    // Select score 9
    const btn9 = screen.getAllByRole("button").find((b) => b.textContent === "9")!;
    fireEvent.click(btn9);

    // Fill text
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: LONG_ENOUGH_TEXT },
    });

    const submitBtn = screen.getByRole("button", { name: "Submit review" });
    await act(async () => {
      fireEvent.click(submitBtn);
    });

    expect(mockSubmitRating).toHaveBeenCalledOnce();
    expect(onSubmitted).toHaveBeenCalledWith(returnedRating);
  });
});
