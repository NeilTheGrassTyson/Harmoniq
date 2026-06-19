"use client";

import type { VisibilityScope } from "@/types";

interface VisibilitySelectProps {
  value: VisibilityScope;
  onChange: (value: VisibilityScope) => void;
  id?: string;
}

const OPTIONS: { value: VisibilityScope; label: string; description: string }[] =
  [
    { value: "private", label: "Only you", description: "" },
    {
      value: "friends",
      label: "Friends",
      description: "People you both follow",
    },
    { value: "public", label: "Everyone", description: "" },
  ];

export default function VisibilitySelect({
  value,
  onChange,
  id,
}: VisibilitySelectProps) {
  return (
    <select
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value as VisibilityScope)}
      className="rounded border border-neutral-200 bg-white px-2 py-1 text-sm text-neutral-700 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300"
    >
      {OPTIONS.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
          {opt.description ? ` — ${opt.description}` : ""}
        </option>
      ))}
    </select>
  );
}
