import { readFileSync } from "node:fs";
import { test, expect, type BrowserContext, type Page } from "@playwright/test";

const fixtures = JSON.parse(readFileSync(process.env.E2E_FIXTURES!, "utf8")) as {
  accounts: Record<string, { id: string; username: string; token: string }>;
  track: string;
};
const origin = process.env.E2E_BASE_URL!;

async function signIn(context: BrowserContext, username: string) {
  await context.addCookies([
    { name: "e2e_token", value: fixtures.accounts[username].token, url: origin },
  ]);
}
async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
}

test("stored listening and highlights on a profile", async ({ browser }, testInfo) => {
  const curator = "e2e_" + testInfo.project.name + "_curator";
  const visitor = "e2e_" + testInfo.project.name + "_visitor";
  const curatorContext = await browser.newContext(testInfo.project.use);
  const visitorContext = await browser.newContext(testInfo.project.use);
  await signIn(curatorContext, curator);
  await signIn(visitorContext, visitor);
  const c = await curatorContext.newPage();
  const v = await visitorContext.newPage();
  const pageErrors: string[] = [];
  for (const page of [c, v]) page.on("pageerror", (error) => pageErrors.push(error.message));
  try {
    // Stored plays render without Spotify, honestly labelled; a linked play
    // opens its Harmoniq track page.
    await v.goto(origin + "/u/" + curator);
    await expect(v.getByText(/not a complete history/)).toBeVisible();
    await expect(v.getByRole("link", { name: "E2E Linked Play" })).toHaveAttribute(
      "href",
      "/track/" + fixtures.track
    );
    await expect(v.getByText("E2E Snapshot Play")).toBeVisible();
    await expect(v.getByText(/reconnect/i)).toHaveCount(0);
    await expect(v.getByText("No highlights yet.")).toBeVisible();

    await c.goto(origin + "/u/" + curator);
    await expect(c.getByText(/needs reconnecting to add new plays/)).toBeVisible();
    await expect(
      c.getByText(/Highlight tracks, albums and artists from their pages/)
    ).toBeVisible();

    // The opt-in lives in settings, under the connected account.
    await c.goto(origin + "/settings");
    const keep = c.getByRole("switch", { name: "Keep your recent listening on your profile" });
    await expect(keep).toBeChecked();

    // Highlight from the track page, no rating needed.
    await c.goto(origin + "/track/" + fixtures.track);
    await c.getByRole("button", { name: "Highlight", exact: true }).click();
    await expect(c.getByRole("button", { name: "Highlighted", exact: true })).toBeVisible();

    await c.goto(origin + "/u/" + curator);
    const section = c.getByRole("region", { name: "Highlights" });
    await expect(section.getByText("E2E 青い空 / & Song")).toBeVisible();
    await expect(section.getByText("1 of 15")).toBeVisible();
    await noOverflow(c);
    await c.screenshot({ path: testInfo.outputPath("curated-profile.png"), fullPage: true });

    await v.reload();
    const seen = v.getByRole("region", { name: "Highlights" });
    await expect(seen.getByText("E2E 青い空 / & Song")).toBeVisible();
    await expect(seen.getByRole("button", { name: /Remove/ })).toHaveCount(0);
    await expect(seen.getByText(/of 15/)).toHaveCount(0);

    // Narrowing visibility takes effect for the visitor at once.
    await c.getByRole("button", { name: "Edit profile" }).click();
    await c.locator("#vis-highlights").selectOption("private");
    await c.getByRole("button", { name: "Save changes" }).click();
    await expect(c.getByRole("button", { name: "Edit profile" })).toBeVisible();
    await v.reload();
    await expect(v.getByRole("region", { name: "Highlights" })).toHaveCount(0);

    // Removing, and withdrawing the listening opt-in, take effect at once too.
    await c
      .getByRole("region", { name: "Highlights" })
      .getByRole("button", { name: /Remove .* from highlights/ })
      .click();
    await expect(c.getByText("No highlights yet.")).toBeVisible();
    await c.goto(origin + "/settings");
    await c.getByRole("switch", { name: "Keep your recent listening on your profile" }).click();
    await expect(
      c.getByRole("switch", { name: "Keep your recent listening on your profile" })
    ).not.toBeChecked();
    await v.reload();
    await expect(v.getByText("E2E Snapshot Play")).toHaveCount(0);
    expect(pageErrors).toEqual([]);
  } finally {
    await curatorContext.close();
    await visitorContext.close();
  }
});
