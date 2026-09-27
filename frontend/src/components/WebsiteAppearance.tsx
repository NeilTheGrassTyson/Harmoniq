"use client";

import { useRef, useState, useTransition } from "react";
import SectionLabel from "@/components/SectionLabel";
import { setAppearance } from "@/app/settings/actions";
import { APPEARANCES, APPEARANCE_LABELS, themeAttribute, type Appearance } from "@/lib/appearance";

function applyToDocument(appearance: Appearance) {
  const attr = themeAttribute(appearance);
  if (attr) document.documentElement.setAttribute("data-theme", attr);
  else document.documentElement.removeAttribute("data-theme");
}

/**
 * "Website Appearance" — the viewer's own theme (ADR 0015). The name is
 * load-bearing: this is a preference about how the site looks to *you*, never
 * a profile theme other people see, so it shares no control, token layer or
 * stored field with Harmony v2's themes.
 */
export default function WebsiteAppearance({ initial }: { initial: Appearance }) {
  const [selected, setSelected] = useState<Appearance>(initial);
  const [error, setError] = useState<string | null>(null);
  const [, startTransition] = useTransition();
  // Arrow keys move through native radios one change at a time, so several
  // saves can be in flight. Only the newest may roll the page back on failure.
  const latest = useRef<Appearance>(initial);

  const choose = (next: Appearance) => {
    const previous = selected;
    latest.current = next;
    setSelected(next);
    setError(null);
    applyToDocument(next); // repaint now; the action's response re-renders Clerk too

    startTransition(async () => {
      let ok = false;
      try {
        ok = (await setAppearance(next)).ok;
      } catch {
        ok = false;
      }
      if (!ok && latest.current === next) {
        latest.current = previous;
        setSelected(previous);
        applyToDocument(previous);
        setError("Couldn't save your appearance. Try again.");
      }
    });
  };

  return (
    <section className="mt-8" data-testid="website-appearance">
      <SectionLabel>Website Appearance</SectionLabel>
      <p className="text-secondary mb-4 text-[13px]">
        How Harmoniq looks in this browser. Only you see it.
      </p>
      <div role="radiogroup" aria-label="Website Appearance" className="grid grid-cols-3 gap-3">
        {APPEARANCES.map((appearance) => {
          const checked = appearance === selected;
          return (
            <label
              key={appearance}
              className={`rounded-frame block cursor-pointer border p-1.5 has-focus-visible:shadow-[0_0_0_1.5px_var(--accent-ui-ring)] ${
                checked ? "border-accent" : "border-hairline hover:border-secondary"
              }`}
            >
              <input
                type="radio"
                name="website-appearance"
                value={appearance}
                checked={checked}
                onChange={() => choose(appearance)}
                className="sr-only"
              />
              {/* A miniature of the app in that theme's own tokens. */}
              <span
                data-appearance-preview={appearance}
                aria-hidden="true"
                className="bg-canvas border-hairline rounded-control flex h-16 overflow-hidden border"
              >
                <span className="bg-sidebar border-hairline w-1/4 border-r" />
                <span className="flex flex-1 flex-col justify-center gap-1.5 px-2">
                  <span className="bg-primary h-1.5 w-3/4 rounded-full" />
                  <span className="bg-tertiary h-1.5 w-1/2 rounded-full" />
                  <span className="bg-accent h-1.5 w-1/4 rounded-full" />
                </span>
              </span>
              <span className="mt-2 flex items-center gap-2 px-1 pb-0.5">
                <span
                  aria-hidden="true"
                  className={`flex size-3.5 shrink-0 items-center justify-center rounded-full border ${
                    checked ? "border-accent" : "border-tertiary"
                  }`}
                >
                  {checked && <span className="bg-accent size-1.5 rounded-full" />}
                </span>
                <span className="text-primary text-[13px]">{APPEARANCE_LABELS[appearance]}</span>
              </span>
            </label>
          );
        })}
      </div>
      {error && (
        <p className="text-destructive mt-2 text-[13px]" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
