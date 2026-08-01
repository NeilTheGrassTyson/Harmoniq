import type { ClerkAppearanceTheme } from "@clerk/shared/types";

/**
 * Clerk appearance mapped onto Harmoniq's design tokens (DESIGN_SYSTEM.md §15).
 *
 * Clerk's prebuilt components render their own DOM, so they can't inherit the
 * `@theme` block the way our own components do — every token has to be handed
 * over explicitly. The values below are copied from DESIGN_SYSTEM.md §2–§4 and
 * must be updated there first if they ever change (§14).
 *
 * No `@clerk/themes` dependency: the `dark` prebuilt theme carries its own
 * palette (and its own shadows), which would then need overriding back to
 * Harmoniq's values anyway. Driving `variables` directly is fewer moving parts.
 */

// DESIGN_SYSTEM.md §3 — body face is the system stack; display face is
// Space Grotesk, injected as a CSS var by next/font in layout.tsx.
const BODY_FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
const DISPLAY_FONT = "var(--font-space-grotesk), system-ui, sans-serif";

export const clerkAppearance: ClerkAppearanceTheme = {
  options: {
    // Our own wordmark + equalizer glyph sit above the card (see the sign-in
    // and sign-up pages), so Clerk's dashboard-hosted logo is suppressed —
    // one brand mark per screen, and it's the one we control.
    logoPlacement: "none",
    socialButtonsPlacement: "top",
    socialButtonsVariant: "blockButton",
    // Decorative motion is banned (§8); the avatar shimmer is exactly that.
    shimmer: false,
  },

  variables: {
    // Palette — DESIGN_SYSTEM.md §2
    colorPrimary: "#2f8cff",
    colorPrimaryForeground: "#0b0d12",
    colorBackground: "#0b0d12",
    colorForeground: "#f2f3f5",
    colorMuted: "#151821",
    colorMutedForeground: "#8b93a3",
    colorInput: "rgba(255, 255, 255, 0.05)",
    colorInputForeground: "#f2f3f5",
    colorBorder: "rgba(255, 255, 255, 0.07)",
    colorNeutral: "#8b93a3",
    colorDanger: "#f87171",
    // The focus ring is the only permitted shadow (§8).
    colorRing: "rgba(47, 140, 255, 0.6)",
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
    headerSubtitle: { color: "#8b93a3" },

    // Micro-label treatment matching the onboarding form's field labels.
    formFieldLabel: {
      color: "#757c8c",
      fontSize: "0.6875rem",
      fontWeight: 500,
      textTransform: "uppercase",
      letterSpacing: "0.06em",
    },

    formButtonPrimary: {
      backgroundColor: "#2f8cff",
      color: "#0b0d12",
      fontWeight: 500,
      textTransform: "none",
      boxShadow: "none",
    },

    socialButtonsBlockButton: {
      backgroundColor: "rgba(255, 255, 255, 0.05)",
      borderColor: "rgba(255, 255, 255, 0.07)",
      color: "#f2f3f5",
      boxShadow: "none",
    },

    dividerLine: { backgroundColor: "rgba(255, 255, 255, 0.07)" },
    dividerText: { color: "#757c8c" },
    footerActionText: { color: "#8b93a3" },
    footerActionLink: { color: "#2f8cff", fontWeight: 500 },
  },
};
