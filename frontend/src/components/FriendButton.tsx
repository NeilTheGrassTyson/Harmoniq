"use client";

import { useAuth } from "@clerk/nextjs";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  acceptFriendRequest,
  declineFriendRequest,
  removeFriend,
  sendFriendRequest,
} from "@/lib/friends";
import { friendlyError } from "@/lib/apiBase";
import type { FriendshipState } from "@/types";

type Action = "send" | "accept" | "decline" | "remove";

const quiet =
  "rounded-control border-hairline text-secondary hover:text-primary border px-3 py-1.5 text-xs font-medium disabled:opacity-50";

/**
 * Friendship controls for someone else's profile. A sent request is never
 * shown back to its sender (specs/phase-2-friend-requests.md, Founder
 * decision 2026-09-27): the send is acknowledged once and the control
 * returns to "Add friend", so a decline can never be read from it.
 */
export default function FriendButton({
  username,
  initialState,
}: {
  username: string;
  initialState: FriendshipState;
}) {
  const { getToken } = useAuth();
  const router = useRouter();
  const [state, setState] = useState<FriendshipState>(
    initialState === "request_sent" ? "none" : initialState
  );
  const [justSent, setJustSent] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);

  const mutation = useMutation({
    mutationFn: async (action: Action) => {
      const token = await getToken().catch(() => null);
      if (!token) throw new Error("Sign in to add friends.");
      const call = {
        send: sendFriendRequest,
        accept: acceptFriendRequest,
        decline: declineFriendRequest,
        remove: removeFriend,
      }[action];
      return call(token, username);
    },
    onMutate: () => setJustSent(false),
    onSuccess: (next, action) => {
      setConfirmRemove(false);
      if (next === "request_sent") {
        setState("none");
        setJustSent(true);
        return;
      }
      setState(next);
      // Friends-only content on this page appears or disappears with the change.
      if (action === "accept" || action === "remove" || next === "friends") router.refresh();
    },
  });
  const busy = mutation.isPending;

  return (
    <div>
      {state === "none" && (
        <button className={quiet} disabled={busy} onClick={() => mutation.mutate("send")}>
          Add friend
        </button>
      )}

      {state === "request_received" && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-secondary text-xs">Wants to be friends</span>
          <button className={quiet} disabled={busy} onClick={() => mutation.mutate("accept")}>
            Accept
          </button>
          <button className={quiet} disabled={busy} onClick={() => mutation.mutate("decline")}>
            Not now
          </button>
        </div>
      )}

      {state === "friends" &&
        (confirmRemove ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-secondary text-xs">Remove from friends?</span>
            <button className={quiet} disabled={busy} onClick={() => mutation.mutate("remove")}>
              Remove
            </button>
            <button className={quiet} disabled={busy} onClick={() => setConfirmRemove(false)}>
              Keep
            </button>
          </div>
        ) : (
          <button
            className={quiet}
            aria-label="Friends — manage friendship"
            onClick={() => setConfirmRemove(true)}
          >
            Friends
          </button>
        ))}

      {justSent && (
        <p role="status" className="text-tertiary mt-1 text-xs">
          Request sent.
        </p>
      )}
      {mutation.isError && (
        <p role="alert" className="text-destructive mt-1 text-xs">
          {friendlyError(mutation.error, "Something went wrong. Try again.")}
        </p>
      )}
    </div>
  );
}
