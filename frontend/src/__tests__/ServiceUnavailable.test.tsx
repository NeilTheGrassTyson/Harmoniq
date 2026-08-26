import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import React from "react";
import ServiceUnavailable from "@/components/ServiceUnavailable";

// Render next/link as a plain <a> so the component can render outside a router.
vi.mock("next/link", () => ({
  default: function MockLink({
    href,
    children,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
  }) {
    return (
      <a href={href} {...rest}>
        {children}
      </a>
    );
  },
}));

describe("ServiceUnavailable", () => {
  it("tells crawlers not to index the outage state", () => {
    // Every route rendering this has a loading.tsx, so the response has
    // already committed to 200 by the time the backend failure is known and
    // the status can no longer say "unavailable". Without this tag a crawler
    // reaching a public profile or catalog page mid-outage could index
    // "Couldn't load this page" as the page's real content.
    render(<ServiceUnavailable />);

    // Queried on document.head, not the render container: React hoists
    // metadata tags out of the tree into <head>, which is the only place a
    // crawler reads them. Asserting on the container would pass while the
    // tag sat somewhere Google never looks.
    const robots = document.head.querySelector('meta[name="robots"]');
    expect(robots).not.toBeNull();
    expect(robots?.getAttribute("content")).toBe("noindex");
  });

  it("still renders the human-facing message", () => {
    // The noindex is for crawlers only; it must not displace the reader's
    // explanation or the way back.
    const { getByRole, getByText } = render(<ServiceUnavailable what="this album" />);

    expect(getByRole("alert")).toBeTruthy();
    expect(getByText(/Couldn.t load this album/)).toBeTruthy();
    expect(getByText("Back to Home").getAttribute("href")).toBe("/");
  });
});
