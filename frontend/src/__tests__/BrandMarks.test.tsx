import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import React from "react";
import OctaveMark from "@/components/brand/OctaveMark";
import Wordmark from "@/components/brand/Wordmark";

describe("OctaveMark", () => {
  it("draws both waves at full size and drops the overtone when compact", () => {
    // The small mark is a redraw, not a scale: below ~20px the overtone falls
    // under a pixel and reads as noise (DESIGN_SYSTEM.md §6.1). A regression
    // here is invisible in review — it just looks slightly fuzzy at 18px.
    const { container: full } = render(<OctaveMark size={24} />);
    expect(full.querySelectorAll("path")).toHaveLength(2);

    const { container: compact } = render(<OctaveMark size={18} compact />);
    expect(compact.querySelectorAll("path")).toHaveLength(1);
  });

  it("is hidden from assistive tech, so its container must carry the name", () => {
    const { container } = render(<OctaveMark />);
    expect(container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });

  it("animates only when asked", () => {
    // .octave-draw is reserved for Melody arrival (DESIGN_SYSTEM.md §8). The
    // logo must never carry it, so the default has to stay off.
    const { container: still } = render(<OctaveMark />);
    expect(still.querySelector(".octave-draw")).toBeNull();

    const { container: drawn } = render(<OctaveMark animated />);
    expect(drawn.querySelector(".octave-draw")).not.toBeNull();
  });
});

describe("Wordmark", () => {
  it("renders the name as live text, not as an image", () => {
    // The word is real text in the display face — that is why the wordmark is
    // a component rather than an .svg (DESIGN_SYSTEM.md §6.1). It is also what
    // gives the auth screen and the signed-out landing an accessible name.
    const { getByText } = render(<Wordmark />);
    expect(getByText("harmoniq").tagName).toBe("SPAN");
  });

  it("drops to the single-wave lockup below the four-hump floor", () => {
    // Four humps collapse into a fuzzy line under ~24px.
    const { container: small } = render(<Wordmark size={14} />);
    expect(small.querySelectorAll("path")).toHaveLength(1);

    const { container: large } = render(<Wordmark size={28} />);
    expect(large.querySelectorAll("path")).toHaveLength(2);
  });

  it("keeps the wave out of the accessibility tree", () => {
    const { container } = render(<Wordmark />);
    expect(container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });
});
