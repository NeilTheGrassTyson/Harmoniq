"use client";

import { useState } from "react";
import { useUser } from "@clerk/nextjs";
import RatingComposer from "@/components/RatingComposer";
import ReviewList from "@/components/ReviewList";
import type { RatingRead, VisibilityScope } from "@/types";

interface Props {
  entityType: "track" | "album";
  entityMbid: string;
  initialReviews: RatingRead[];
  initialAggregate: number | null;
}

export default function RatingSection({
  entityType,
  entityMbid,
  initialReviews,
  initialAggregate,
}: Props) {
  const { isSignedIn, user } = useUser();
  const ownUsername = user?.username ?? null;

  // Find the signed-in user's existing review so we can pre-fill the composer.
  const initialOwnReview = ownUsername
    ? (initialReviews.find((r) => r.reviewer.username === ownUsername) ?? null)
    : null;

  const [reviews, setReviews] = useState<RatingRead[]>(initialReviews);
  const [aggregate, setAggregate] = useState<number | null>(initialAggregate);
  const [ownReview, setOwnReview] = useState<RatingRead | null>(initialOwnReview);

  function handleSubmitted(rating: RatingRead) {
    setOwnReview(rating);
    // Replace any existing row from this user (matched by ID or username) rather
    // than inserting a duplicate. The backend does an upsert so the returned ID
    // is always the same record — filtering both guards against that and against
    // any edge-case where a stale list held a row with a different ID.
    setReviews((prev) => [
      rating,
      ...prev.filter(
        (r) => r.id !== rating.id && r.reviewer.username !== rating.reviewer.username
      ),
    ]);
    setAggregate(null);
  }

  function handleDeleted(id: string) {
    setReviews((prev) => prev.filter((r) => r.id !== id));
    if (ownReview?.id === id) setOwnReview(null);
  }

  function handleVisibilityChanged(id: string, v: VisibilityScope) {
    setReviews((prev) => prev.map((r) => (r.id === id ? { ...r, visibility: v } : r)));
    if (ownReview?.id === id) setOwnReview((prev) => (prev ? { ...prev, visibility: v } : prev));
  }

  return (
    <section className="mt-10">
      {aggregate !== null && (
        <div className="mb-6">
          <p className="text-tertiary text-xs font-medium tracking-widest uppercase">
            Average rating
          </p>
          <p className="text-primary mt-1 text-3xl font-light">
            {aggregate.toFixed(1)}
            <span className="text-tertiary ml-1 text-base">/10</span>
          </p>
        </div>
      )}

      {isSignedIn && (
        <div className="mb-8">
          <h2 className="text-tertiary mb-3 text-xs font-medium tracking-widest uppercase">
            Your review
          </h2>
          <RatingComposer
            entityType={entityType}
            entityMbid={entityMbid}
            onSubmitted={handleSubmitted}
            initialRating={ownReview ?? undefined}
          />
        </div>
      )}

      <div>
        <h2 className="text-tertiary mb-4 text-xs font-medium tracking-widest uppercase">
          Reviews
        </h2>
        <ReviewList
          reviews={reviews}
          onDeleted={handleDeleted}
          onVisibilityChanged={handleVisibilityChanged}
        />
      </div>
    </section>
  );
}
