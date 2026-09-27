import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  APPEARANCE_COOKIE,
  appearanceFromCookieString,
  parseAppearance,
  themeAttribute,
} from "@/lib/appearance";
import { clerkAppearanceFor } from "@/lib/clerkAppearance";

const cookieSet = vi.fn();
vi.mock("next/headers", () => ({
  cookies: async () => ({ set: cookieSet }),
}));

describe("appearance helpers", () => {
  it("defaults to Midnight for anything it doesn't recognise", () => {
    expect(parseAppearance(undefined)).toBe("midnight");
    expect(parseAppearance("")).toBe("midnight");
    expect(parseAppearance("LIGHT")).toBe("midnight");
    expect(parseAppearance('dark" onload="x')).toBe("midnight");
    expect(parseAppearance("light")).toBe("light");
    expect(parseAppearance("dark")).toBe("dark");
  });

  it("gives Midnight no data-theme attribute — it is the base token set", () => {
    expect(themeAttribute("midnight")).toBeUndefined();
    expect(themeAttribute("dark")).toBe("dark");
    expect(themeAttribute("light")).toBe("light");
  });

  it("reads the preference out of a document.cookie string", () => {
    expect(appearanceFromCookieString("")).toBe("midnight");
    expect(appearanceFromCookieString(`a=1; ${APPEARANCE_COOKIE}=light; b=2`)).toBe("light");
    expect(appearanceFromCookieString(`${APPEARANCE_COOKIE}=bogus`)).toBe("midnight");
    expect(appearanceFromCookieString(`x${APPEARANCE_COOKIE}=light`)).toBe("midnight");
  });
});

describe("setAppearance server action", () => {
  beforeEach(() => {
    cookieSet.mockReset();
  });

  it("stores a valid choice for a year, site-wide", async () => {
    const { setAppearance } = await import("@/app/settings/actions");
    expect(await setAppearance("light")).toEqual({ ok: true });
    expect(cookieSet).toHaveBeenCalledWith(
      APPEARANCE_COOKIE,
      "light",
      expect.objectContaining({ path: "/", maxAge: 31536000, sameSite: "lax" })
    );
  });

  // A Server Action is a public endpoint: the value is whatever the caller
  // sends, so it is validated here rather than trusted from the picker.
  it("refuses anything that isn't one of the three themes", async () => {
    const { setAppearance } = await import("@/app/settings/actions");
    for (const bad of ["", "LIGHT", "sepia", 1, null, { value: "light" }]) {
      expect(await setAppearance(bad)).toEqual({ ok: false });
    }
    expect(cookieSet).not.toHaveBeenCalled();
  });
});

describe("clerkAppearanceFor", () => {
  it("hands Clerk the active theme's canvas, text and accent", () => {
    const light = clerkAppearanceFor("light").variables!;
    expect(light.colorBackground).toBe("#f7f8fa");
    expect(light.colorForeground).toBe("#14161c");
    expect(light.colorPrimary).toBe("#1a64d6");

    expect(clerkAppearanceFor("dark").variables!.colorBackground).toBe("#0b0d12");
    expect(clerkAppearanceFor("midnight").variables!.colorBackground).toBe("#000000");
  });

  // DESIGN_SYSTEM.md §8: at 60% the ring measured 2.78:1 on Dark, under the
  // 3:1 WCAG 1.4.11 needs for UI state.
  it("draws the focus ring at 80% in every theme", () => {
    for (const a of ["light", "dark", "midnight"] as const) {
      expect(String(clerkAppearanceFor(a).variables!.colorRing)).toMatch(/, 0\.8\)$/);
    }
  });
});
