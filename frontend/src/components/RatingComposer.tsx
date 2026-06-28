"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import VisibilitySelect from "@/components/VisibilitySelect";
import { submitRating } from "@/lib/ratings";
import type { RatingRead, VisibilityScope } from "@/types";

const REVIEW_MIN = 15;
const REVIEW_MAX = 2000;
const SCORES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const;

interface Props {
  entityType: "track" | "album";
  entityMbid: string;
  onSubmitted?: (rating: RatingRead) => void;
  /** When provided, pre-fills the form with the user's existing review and
   *  changes the submit label to "Update review". */
  initialRating?: { score: number; review_text: string; visibility: string };
}

export default function RatingComposer({
  entityType,
  entityMbid,
  onSubmitted,
  initialRating,
}: Props) {
  const { getToken } = useAuth();
  const [score, setScore] = useState<number | null>(initialRating?.score ?? null);
  const [text, setText] = useState(initialRating?.review_text ?? "");
  const [visibility, setVisibility] = useState<VisibilityScope>(
    (initialRating?.visibility as VisibilityScope) ?? "public"
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync form state when the parent updates initialRating (e.g. after a successful submit).
  useEffect(() => {
    setScore(initialRating?.score ?? null);
    setText(initialRating?.review_text ?? "");
    setVisibility((initialRating?.visibility as VisibilityScope) ?? "public");
  }, [initialRating]);

  const trimmed = text.trim();
  const tooShort = trimmed.length < REVIEW_MIN;
  const canSubmit = score !== null && !tooShort && !submitting;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const rating = await submitRating(token, {
        entity_type: entityType,
        entity_mbid: entityMbid,
        score: score!,
        review_text: trimmed,
        visibility,
      });
      // Don't reset manually — the parent updates initialRating after onSubmitted,
      // which triggers the useEffect above and syncs the form to the saved state.
      onSubmitted?.(rating);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong. Your review wasn't saved. Try again."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Score selector */}
      <div>
        <div className="flex flex-wrap gap-1">
          {SCORES.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setScore(s)}
              aria-pressed={score === s}
              className={[
                "rounded-control h-8 w-8 text-sm font-medium transition-colors",
                score === s
                  ? "bg-primary text-canvas"
                  : "border-hairline text-secondary hover:border-secondary border",
              ].join(" ")}
            >
              {s}
            </button>
          ))}
        </div>
        {score === null && <p className="text-tertiary mt-1 text-xs">Pick a rating from 1–10.</p>}
      </div>

      {/* Review text */}
      <div>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="What did you think?"
          maxLength={REVIEW_MAX}
          rows={4}
          className="rounded-control border-hairline bg-control text-primary placeholder:text-tertiary w-full border px-3 py-2 text-sm"
        />
        {tooShort && trimmed.length > 0 && (
          <p className="text-tertiary mt-1 text-xs">A few more words — tell us what stood out.</p>
        )}
        <p className="text-tertiary mt-1 text-right text-xs">
          {trimmed.length} / {REVIEW_MAX}
        </p>
      </div>

      {/* Visibility + submit */}
      <div className="flex items-center gap-3">
        <VisibilitySelect value={visibility} onChange={setVisibility} id="rating-visibility" />
        <button
          type="submit"
          disabled={!canSubmit}
          className="rounded-control border-hairline text-primary border px-4 py-1.5 text-sm font-medium transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitting ? "Saving…" : initialRating ? "Update review" : "Submit review"}
        </button>
      </div>

      {error && (
        <p role="alert" className="text-sm" style={{ color: "#f87171" }}>
          {error}
        </p>
      )}
    </form>
  );
}
