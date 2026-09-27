/**
 * Website Appearance — the viewer's own theme preference (ADR 0015).
 *
 * Not a profile theme: nothing here is ever sent to the backend or shown to
 * anyone else. It lives in a cookie so the root layout can paint the right
 * theme on the first byte, with no flash of the default.
 */

export const APPEARANCES = ["light", "dark", "midnight"] as const;
export type Appearance = (typeof APPEARANCES)[number];

export const DEFAULT_APPEARANCE: Appearance = "midnight";
export const APPEARANCE_COOKIE = "harmoniq-appearance";

export const APPEARANCE_LABELS: Record<Appearance, string> = {
  light: "Light",
  dark: "Dark",
  midnight: "Midnight",
};

export function isAppearance(value: unknown): value is Appearance {
  return typeof value === "string" && (APPEARANCES as readonly string[]).includes(value);
}

/** Anything unrecognised — absent, stale, hand-edited — reads as the default. */
export function parseAppearance(value: string | null | undefined): Appearance {
  return isAppearance(value) ? value : DEFAULT_APPEARANCE;
}

/**
 * The `data-theme` value for <html>. Midnight is the base token set in
 * globals.css, so it carries no attribute at all.
 */
export function themeAttribute(appearance: Appearance): "light" | "dark" | undefined {
  return appearance === "midnight" ? undefined : appearance;
}

/** Reads the preference out of a `document.cookie`-style string. */
export function appearanceFromCookieString(cookieString: string): Appearance {
  for (const part of cookieString.split(";")) {
    const [name, ...rest] = part.trim().split("=");
    if (name === APPEARANCE_COOKIE) return parseAppearance(decodeURIComponent(rest.join("=")));
  }
  return DEFAULT_APPEARANCE;
}
