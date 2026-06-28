"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth, useUser } from "@clerk/nextjs";
import AvatarImage from "@/components/AvatarImage";
import VisibilitySelect from "@/components/VisibilitySelect";
import { deleteRating, reportRating, updateRatingVisibility } from "@/lib/ratings";
import type { RatingRead, VisibilityScope } from "@/types";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

interface ReviewItemProps {
  review: RatingRead;
  viewerUsername: string | null | undefined;
  onDeleted: (id: string) => void;
  onVisibilityChanged: (id: string, v: VisibilityScope) => void;
}

function ReviewItem({ review, viewerUsername, onDeleted, onVisibilityChanged }: ReviewItemProps) {
  const { getToken } = useAuth();
  const isOwn = viewerUsername != null && viewerUsername === review.reviewer.username;
  const [visibility, setVisibility] = useState<VisibilityScope>(review.visibility);
  const [reporting, setReporting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [reported, setReported] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete() {
    setDeleting(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) return;
      await deleteRating(token, review.id);
      onDeleted(review.id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Couldn't delete. Try again.");
      setDeleting(false);
    }
  }

  async function handleReport() {
    setReporting(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) return;
      await reportRating(token, review.id);
      setReported(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Couldn't submit your report. Try again.");
    } finally {
      setReporting(false);
    }
  }

  async function handleVisibilityChange(v: VisibilityScope) {
    try {
      const token = await getToken();
      if (!token) return;
      await updateRatingVisibility(token, review.id, v);
      setVisibility(v);
      onVisibilityChanged(review.id, v);
    } catch {
      // silently ignore
    }
  }

  return (
    <div className="border-hairline border-b py-4 last:border-0">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <AvatarImage
            src={review.reviewer.avatar_url}
            username={review.reviewer.username}
            size={28}
          />
          <Link
            href={`/u/${review.reviewer.username}`}
            className="text-primary text-sm font-medium hover:underline"
          >
            {review.reviewer.display_name}
          </Link>
          <span className="text-tertiary text-xs">@{review.reviewer.username}</span>
        </div>
        <span className="text-primary shrink-0 text-sm font-medium">{review.score}/10</span>
      </div>

      <p className="text-secondary text-sm leading-relaxed">{review.review_text}</p>

      <div className="mt-2 flex flex-wrap items-center gap-3">
        <span className="text-tertiary text-xs">{formatDate(review.created_at)}</span>

        {isOwn && (
          <>
            <VisibilitySelect value={visibility} onChange={handleVisibilityChange} />
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="text-tertiary text-xs hover:text-red-400 disabled:opacity-40"
            >
              {deleting ? "Deleting…" : "Delete"}
            </button>
          </>
        )}

        {!isOwn && viewerUsername != null && !reported && (
          <button
            onClick={handleReport}
            disabled={reporting}
            className="text-tertiary hover:text-secondary text-xs disabled:opacity-40"
          >
            {reporting ? "Reporting…" : "Report"}
          </button>
        )}

        {reported && <span className="text-tertiary text-xs">Reported</span>}
      </div>

      {error && (
        <p role="alert" className="mt-1 text-xs" style={{ color: "#f87171" }}>
          {error}
        </p>
      )}
    </div>
  );
}

interface Props {
  reviews: RatingRead[];
  onDeleted: (id: string) => void;
  onVisibilityChanged: (id: string, v: VisibilityScope) => void;
}

export default function ReviewList({ reviews, onDeleted, onVisibilityChanged }: Props) {
  const { user } = useUser();
  const viewerUsername = user?.username ?? null;

  if (reviews.length === 0) {
    return <p className="text-tertiary text-sm">No reviews yet.</p>;
  }

  return (
    <div>
      {reviews.map((r) => (
        <ReviewItem
          key={r.id}
          review={r}
          viewerUsername={viewerUsername}
          onDeleted={onDeleted}
          onVisibilityChanged={onVisibilityChanged}
        />
      ))}
    </div>
  );
}
