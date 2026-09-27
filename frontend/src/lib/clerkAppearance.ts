import type { ClerkAppearanceTheme } from "@clerk/shared/types";
import type { Appearance } from "@/lib/appearance";

/**
 * Clerk appearance mapped onto Harmoniq's design tokens (DESIGN_SYSTEM.md §15),
 * one palette per Website Appearance (§2.2).
 *
 * Clerk derives shades from its colour variables in JS, so it can't take the
 * `var()` references the rest of the app reads — every value is handed over
 * as a literal. They mirror the palette blocks in globals.css and must be
 * updated there first if they ever change (§14).
 *
 * No `@clerk/themes` dependency: its prebuilt themes carry their own palettes
 * (and their own shadows), which would then need overriding back to
 * Harmoniq's values anyway. Driving `variables` directly is fewer moving parts.
 */

interface ClerkPalette {
  canvas: string;
  text: string;
  secondary: string;
  tertiary: string;
  tile: string;
  control: string;
  hairline: string;
  accent: string;
  ring: string;
  danger: string;
}

const DARK_TEXT = { text: "#f2f3f5", secondary: "#8b93a3", tertiary: "#757c8c" };
const DARK_UI = {
  control: "rgba(255, 255, 255, 0.05)",
  accent: "#2f8cff",
  ring: "rgba(47, 140, 255, 0.8)",
  danger: "#f87171",
};

const PALETTES: Record<Appearance, ClerkPalette> = {
  midnight: {
    ...DARK_TEXT,
    ...DARK_UI,
    canvas: "#000000",
    tile: "#0d1016",
    hairline: "rgba(255, 255, 255, 0.09)",
  },
  dark: {
    ...DARK_TEXT,
    ...DARK_UI,
    canvas: "#0b0d12",
    tile: "#151821",
    hairline: "rgba(255, 255, 255, 0.07)",
  },
  light: {
    canvas: "#f7f8fa",
    text: "#14161c",
    secondary: "#565d6b",
    tertiary: "#666c7a",
    tile: "#eef0f4",
    control: "rgba(0, 0, 0, 0.05)",
    hairline: "rgba(0, 0, 0, 0.1)",
    accent: "#1a64d6",
    ring: "rgba(26, 100, 214, 0.8)",
    danger: "#c62828",
  },
};

// DESIGN_SYSTEM.md §3 — body face is the system stack; display face is
// Space Grotesk, injected as a CSS var by next/font in layout.tsx.
const BODY_FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
const DISPLAY_FONT = "var(--font-space-grotesk), system-ui, sans-serif";

export function clerkAppearanceFor(appearance: Appearance): ClerkAppearanceTheme {
  const p = PALETTES[appearance];
  return {
    options: {
      // Our own wordmark sits above the card (see the sign-in and sign-up
      // pages), so Clerk's dashboard-hosted logo is suppressed — one brand
      // mark per screen, and it's the one we control.
      logoPlacement: "none",
      socialButtonsPlacement: "top",
      socialButtonsVariant: "blockButton",
      // Decorative motion is banned (§8); the avatar shimmer is exactly that.
      shimmer: false,
    },

    variables: {
      // Palette — DESIGN_SYSTEM.md §2 / §2.2
      colorPrimary: p.accent,
      colorPrimaryForeground: p.canvas,
      colorBackground: p.canvas,
      colorForeground: p.text,
      colorMuted: p.tile,
      colorMutedForeground: p.secondary,
      colorInput: p.control,
      colorInputForeground: p.text,
      colorBorder: p.hairline,
      colorNeutral: p.secondary,
      colorDanger: p.danger,
      // The focus ring is the only permitted shadow (§8).
      colorRing: p.ring,
      colorShadow: "transparent",

      // Typography — §3
      fontFamily: BODY_FONT,
      fontFamilyButtons: BODY_FONT,
      fontSize: "0.8125rem", // 13px — matches nav/body scale
      // "No weight above 500 anywhere" (§3). Clerk's semibold/bold slots are
      // collapsed to 500 so its internal headings can't reintroduce heavy text.
      fontWeight: { normal: 400, medium: 500, semibold: 500, bold: 500 },

      // Radius — §4 (--radius-control)
      borderRadius: "8px",
    },

    elements: {
      // The card reads as page content, not a floating panel: separation comes
      // from whitespace, not boxes or shadows (§1, §8).
      cardBox: { boxShadow: "none", border: "none" },
      card: {
        backgroundColor: "transparent",
        boxShadow: "none",
        border: "none",
      },
      // Clerk's footer sits outside the card and carries its own surface fill.
      footer: { background: "transparent", boxShadow: "none", borderTop: "none" },

      headerTitle: {
        fontFamily: DISPLAY_FONT,
        fontWeight: 500,
        fontSize: "1.25rem",
        letterSpacing: "-0.01em",
      },
      headerSubtitle: { color: p.secondary },

      // Micro-label treatment matching the onboarding form's field labels.
      formFieldLabel: {
        color: p.tertiary,
        fontSize: "0.6875rem",
        fontWeight: 500,
        textTransform: "uppercase",
        letterSpacing: "0.06em",
      },

      formButtonPrimary: {
        backgroundColor: p.accent,
        color: p.canvas,
        fontWeight: 500,
        textTransform: "none",
        boxShadow: "none",
      },

      socialButtonsBlockButton: {
        backgroundColor: p.control,
        borderColor: p.hairline,
        color: p.text,
        boxShadow: "none",
      },

      dividerLine: { backgroundColor: p.hairline },
      dividerText: { color: p.tertiary },
      footerActionText: { color: p.secondary },
      footerActionLink: { color: p.accent, fontWeight: 500 },
    },
  };
}
