# Melody Reactions and Future Recommendation XP

> **Status: Reactions APPROVED — Founder, 2026-09-08. XP rules DRAFT.**
> This amends Melody's interaction surface with explicit, editable feedback.
> It does not authorize text conversations, rankings, or a scoring formula.

## Approved behavior

- A recipient can choose **Not for me**, **Liked it**, or **Loved it — send
  more like this** on any received Melody, including historical Melodies.
- The reaction is visible only in that recipient's inbox and sender's sent
  list. It creates no notification. No public per-song feedback is introduced.
- A recipient can change their mind. Repeating the same choice is idempotent;
  each Melody stores its current reaction and its change timestamp.
- Listening/opening and reacting are separate actions. A reaction does not
  claim playback occurred or send another recommendation automatically.
- Explicit reactions override status-derived sentiment in Harmony. Without a
  reaction, accepted/opened remain positive, rejected negative, pending unset.
  Historical and new responses use the same rule without invented backfills.
- Existing status transitions and endpoints remain compatible. Reactions
  resolve pending delivery to accepted or rejected as appropriate; opened
  stays opened as a record of the user's deliberate navigation. A subsequent
  old-client status action never clears or changes an explicit reaction.
- Recipient identity is enforced in the database query. Sender, unrelated,
  anonymous, and suspended users cannot mutate a recipient's reaction.
- Use row locking for competing recipient actions; the most recently committed
  reaction wins. No score counter is incremented by repeated requests.

## XP proposal — awaiting a separate answer

Proposed points: not-for-me 0, liked 1, loved 3, with no deductions. A private
sender total would count one contribution per sender/recipient/track, using
the latest explicit reaction across repeat sends. Changing a reaction replaces
its contribution. Earlier status-only responses remain included in Harmony's
reception statistics but must not be relabeled as explicit love/like.

The Founder has been asked to approve these exact rules or ship reactions
first. Do not implement points or invent a historical XP conversion before
that answer. XP must not use provider listening data, audio, or metadata as
scoring input. It is feedback on recommendations, not proof of musical taste
or a measure of a person's worth.

## Future ideas — not approved for implementation

The Founder suggested Harmony DNA and a global or regional recommender
leaderboard after onboarding users. Record this interest without building it.
ENGINEERING_BIBLE.md currently excludes Harmony leaderboards and comparison
surfaces. A future spec must explicitly resolve that governance change,
consent, regional data collection, sample size, and abuse resistance first.

## Verification and rollback

Cover reaction changes after every delivery state, repeat requests, historical
rows, malformed values, recipient isolation, suspension, no notifications,
and concurrent reaction/open requests against real PostgreSQL. Browser tests
must cover sender feedback, keyboard/mobile interaction, errors, and unchanged
track navigation. Disable reactions independently; preserve additive columns
on application rollback. Old API absence must leave song cards usable.
