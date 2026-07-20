"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useAuth } from "@clerk/nextjs";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Form, FormControl, FormField, FormItem } from "@/components/ui/form";
import { Textarea } from "@/components/ui/textarea";
import VisibilitySelect from "@/components/VisibilitySelect";
import { submitRating } from "@/lib/ratings";
import type { RatingRead, VisibilityScope } from "@/types";

const REVIEW_MIN = 15;
const REVIEW_MAX = 2000;
const SCORES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const;

// The validation rules live here, not scattered across canSubmit booleans —
// the submit gate and the input constraints read from the same schema.
const ratingSchema = z.object({
  score: z.number().int().min(1).max(10),
  reviewText: z
    .string()
    .trim()
    .min(REVIEW_MIN)
    .max(REVIEW_MAX),
  visibility: z.enum(["private", "friends", "public"]),
});

type RatingValues = z.infer<typeof ratingSchema>;

interface Props {
  entityType: "track" | "album";
  entityMbid: string;
  onSubmitted?: (rating: RatingRead) => void;
  /** When provided, pre-fills the form with the user's existing review and
   *  changes the submit label to "Update review". */
  initialRating?: { score: number; review_text: string; visibility: string };
}

function valuesFrom(initialRating?: Props["initialRating"]): Partial<RatingValues> {
  return {
    score: initialRating?.score,
    reviewText: initialRating?.review_text ?? "",
    visibility: (initialRating?.visibility as VisibilityScope) ?? "public",
  };
}

export default function RatingComposer({
  entityType,
  entityMbid,
  onSubmitted,
  initialRating,
}: Props) {
  const { getToken } = useAuth();

  const form = useForm<RatingValues>({
    resolver: zodResolver(ratingSchema),
    mode: "onChange",
    defaultValues: valuesFrom(initialRating) as RatingValues,
  });

  // Sync form state when the parent updates initialRating (e.g. after a
  // successful submit) so the composer always reflects the saved review.
  useEffect(() => {
    form.reset(valuesFrom(initialRating) as RatingValues);
  }, [initialRating, form]);

  const score = form.watch("score");
  const text = form.watch("reviewText") ?? "";
  const trimmed = text.trim();
  const tooShort = trimmed.length < REVIEW_MIN;
  // Synchronous mirror of the schema for the disabled state — formState.isValid
  // updates a tick after interactions, which reads as a laggy button. The zod
  // resolver inside handleSubmit stays the authoritative gate.
  const canSubmit = score !== undefined && !tooShort && !form.formState.isSubmitting;

  const onSubmit = async (values: RatingValues) => {
    form.clearErrors("root");
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const rating = await submitRating(token, {
        entity_type: entityType,
        entity_mbid: entityMbid,
        score: values.score,
        review_text: values.reviewText.trim(),
        visibility: values.visibility,
      });
      // Don't reset manually — the parent updates initialRating after
      // onSubmitted, and the reset effect syncs the form to the saved state.
      onSubmitted?.(rating);
    } catch (err: unknown) {
      form.setError("root", {
        message:
          err instanceof Error
            ? err.message
            : "Something went wrong. Your review wasn't saved. Try again.",
      });
    }
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        {/* Score selector */}
        <div>
          <div className="flex flex-wrap gap-1">
            {SCORES.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => form.setValue("score", s, { shouldValidate: true })}
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
          {score === undefined && (
            <p className="text-tertiary mt-1 text-xs">Pick a rating from 1–10.</p>
          )}
        </div>

        {/* Review text */}
        <FormField
          control={form.control}
          name="reviewText"
          render={({ field }) => (
            <FormItem className="gap-0">
              <FormControl>
                <Textarea
                  {...field}
                  placeholder="What did you think?"
                  maxLength={REVIEW_MAX}
                  rows={4}
                  className="min-h-0 px-3 py-2 text-sm"
                />
              </FormControl>
              {tooShort && trimmed.length > 0 && (
                <p className="text-tertiary mt-1 text-xs">
                  A few more words — tell us what stood out.
                </p>
              )}
              <p className="text-tertiary mt-1 text-right text-xs">
                {trimmed.length} / {REVIEW_MAX}
              </p>
            </FormItem>
          )}
        />

        {/* Visibility + submit — wraps so the button never clips on narrow screens */}
        <div className="flex flex-wrap items-center gap-3">
          <FormField
            control={form.control}
            name="visibility"
            render={({ field }) => (
              <VisibilitySelect
                value={field.value}
                onChange={field.onChange}
                id="rating-visibility"
              />
            )}
          />
          <Button
            type="submit"
            variant="outline"
            disabled={!canSubmit}
            className="h-auto px-4 py-1.5 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {form.formState.isSubmitting
              ? "Saving…"
              : initialRating
                ? "Update review"
                : "Submit review"}
          </Button>
        </div>

        {form.formState.errors.root && (
          <p role="alert" className="text-destructive text-sm">
            {form.formState.errors.root.message}
          </p>
        )}
      </form>
    </Form>
  );
}
