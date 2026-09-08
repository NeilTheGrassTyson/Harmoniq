import { readFileSync } from "node:fs";
import { test, expect, type BrowserContext, type Page } from "@playwright/test";

const fixtures = JSON.parse(readFileSync(process.env.E2E_FIXTURES!, "utf8")) as {
  accounts: Record<string, { id: string; username: string; token: string }>;
  track: string;
};
const api = process.env.E2E_API_URL!;
const origin = process.env.E2E_BASE_URL!;
async function signIn(context: BrowserContext, username: string) {
  await context.addCookies([
    { name: "e2e_token", value: fixtures.accounts[username].token, url: origin },
  ]);
}
async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
}
async function reaction(page: Page, label: string) {
  await page.getByRole("button", { name: label, exact: true }).click();
  await expect(page.getByText("Your reaction: " + label, { exact: true })).toBeVisible();
}

test("recommend, react, share/revoke Harmony, listen, and retain existing social flows", async ({
  browser,
}, testInfo) => {
  const sender = "e2e_" + testInfo.project.name + "_sender";
  const recipient = "e2e_" + testInfo.project.name + "_recipient";
  const senderContext = await browser.newContext(testInfo.project.use);
  const recipientContext = await browser.newContext(testInfo.project.use);
  const anonymousContext = await browser.newContext(testInfo.project.use);
  await signIn(senderContext, sender);
  await signIn(recipientContext, recipient);
  const s = await senderContext.newPage();
  const r = await recipientContext.newPage();
  const a = await anonymousContext.newPage();
  const pageErrors: string[] = [];
  for (const page of [s, r, a]) page.on("pageerror", (error) => pageErrors.push(error.message));
  try {
    await s.goto(origin + "/track/" + fixtures.track);
    await expect(s.getByRole("heading", { name: "E2E 青い空 / & Song" })).toBeVisible();
    await expect(s.getByRole("link", { name: /Open in Spotify/ })).toBeVisible();
    await expect(s.getByRole("region", { name: "Listen on" }).getByRole("link")).toHaveCount(6);
    await noOverflow(s);
    // The browser opens a separate tab without an opener or private referrer.
    await senderContext.route("https://open.spotify.com/**", (route) =>
      route.fulfill({ body: "Provider boundary" })
    );
    const opened = senderContext.waitForEvent("page");
    await s.getByRole("link", { name: /Open in Spotify/ }).click();
    const provider = await opened;
    await provider.waitForLoadState();
    expect(await provider.evaluate(() => window.opener)).toBeNull();
    expect(await provider.evaluate(() => document.referrer)).toBe("");
    await provider.close();

    await s.getByRole("button", { name: "Send a Melody" }).click();
    await s.getByRole("textbox", { name: "Recipient username" }).fill(recipient);
    await s.getByRole("button", { name: "Send", exact: true }).click();
    await expect(s.getByText("Melody sent to @" + recipient + ".")).toBeVisible();
    // Duplicate pending sends remain guarded.
    await s.getByRole("textbox", { name: "Recipient username" }).fill(recipient);
    await s.getByRole("button", { name: "Send", exact: true }).click();
    await expect(s.getByTestId("send-melody-panel").getByRole("alert")).toContainText(
      "already sent"
    );

    await r.goto(origin + "/melodies");
    await expect(
      r.getByRole("group", { name: "Your reaction to E2E 青い空 / & Song" })
    ).toBeVisible();
    await expect(r.getByTestId("notification-bell")).toBeVisible();
    await r.getByRole("button", { name: "Liked it", exact: true }).focus();
    await r.keyboard.press("Enter");
    await expect(r.getByText("Your reaction: Liked it", { exact: true })).toBeVisible();
    await reaction(r, "Loved it — send more like this");
    await noOverflow(r);
    await r.screenshot({ path: testInfo.outputPath("reactions.png"), fullPage: true });

    await s.goto(origin + "/melodies");
    await s.getByRole("button", { name: "Sent", exact: true }).click();
    await expect(s.getByText("Their reaction: Loved it — send more like this")).toBeVisible();
    await s.goto(origin + "/u/" + sender);
    await expect(s.getByText("100% positive reception")).toBeVisible();
    const visibility = s.getByRole("combobox", { name: "Share a positive summary with" });
    await expect(visibility).toHaveValue("private");
    await a.goto(origin + "/u/" + sender);
    await expect(a.getByRole("heading", { name: "Harmony" })).toHaveCount(0);
    await visibility.selectOption("public");
    await expect(s.getByText("Visibility saved.")).toBeVisible();
    await a.reload();
    await expect(a.getByText("Your music has found listeners")).toBeVisible();
    await expect(a.getByText(/positive reception/)).toHaveCount(0);

    await reaction(r, "Not for me");
    await s.reload();
    await expect(s.getByText("0% positive reception")).toBeVisible();
    await a.reload();
    await expect(a.getByRole("heading", { name: "Harmony" })).toHaveCount(0);
    await r.getByRole("button", { name: "Listen", exact: true }).click();
    await expect(r).toHaveURL(origin + "/track/" + fixtures.track);
    await expect(r.getByRole("link", { name: /Search Apple Music/ })).toBeVisible();
    await r.goto(origin + "/melodies");
    await expect(r.getByText("Your reaction: Not for me", { exact: true })).toBeVisible();
    await reaction(r, "Loved it — send more like this");
    await s.reload();
    await expect(s.getByText("100% positive reception")).toBeVisible();
    await s
      .getByRole("combobox", { name: "Share a positive summary with" })
      .selectOption("friends");
    await expect(s.getByText("Visibility saved.")).toBeVisible();
    await r.goto(origin + "/u/" + sender);
    await expect(r.getByRole("heading", { name: "Harmony" })).toHaveCount(0);
    await r.getByRole("button", { name: "Follow", exact: true }).click();
    await expect(r.getByRole("button", { name: "Following", exact: true })).toBeEnabled();
    await s.goto(origin + "/u/" + recipient);
    await s.getByRole("button", { name: "Follow", exact: true }).click();
    await expect(s.getByRole("button", { name: "Following", exact: true })).toBeEnabled();
    await r.reload();
    await expect(r.getByText("Your music has found listeners")).toBeVisible();
    await s.goto(origin + "/u/" + sender);
    await s
      .getByRole("combobox", { name: "Share a positive summary with" })
      .selectOption("private");
    await expect(s.getByText("Visibility saved.")).toBeVisible();
    await r.reload();
    await expect(r.getByRole("heading", { name: "Harmony" })).toHaveCount(0);
    await noOverflow(s);
    await s.screenshot({ path: testInfo.outputPath("harmony.png"), fullPage: true });

    // Existing rating creation and visibility still work through the browser.
    await s.goto(origin + "/track/" + fixtures.track);
    await s.getByRole("button", { name: "8", exact: true }).click();
    const review = "A thoughtful recommendation with a beautiful melody and a memorable rhythm.";
    await s.getByPlaceholder("What did you think?").fill(review);
    await s.locator("#rating-visibility").selectOption("private");
    await s.getByRole("button", { name: "Submit review", exact: true }).click();
    await expect(s.getByText(review, { exact: true })).toBeVisible();
    await a.goto(origin + "/track/" + fixtures.track);
    await expect(a.getByText(review, { exact: true })).toHaveCount(0);
    await s.getByRole("button", { name: "Delete", exact: true }).click();
    await expect(s.getByText(review, { exact: true })).toHaveCount(0);
    expect(pageErrors).toEqual([]);
  } finally {
    await senderContext.close();
    await recipientContext.close();
    await anonymousContext.close();
  }
});

test("failed sections and old API keep the track and profile usable", async ({
  page,
  context,
}, testInfo) => {
  const sender = "e2e_" + testInfo.project.name + "_sender";
  await signIn(context, sender);
  await page.route(api + "/api/v1/streaming/**", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "unavailable" },
      headers: { "Access-Control-Allow-Origin": origin },
    })
  );
  await page.goto("/track/" + fixtures.track);
  await expect(page.getByText(/Couldn't load music services/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "E2E 青い空 / & Song" })).toBeVisible();
  await expect(page.getByTestId("send-melody-panel")).toBeVisible();
  await page.route(api + "/api/v1/harmony/**", (route) =>
    route.fulfill({
      status: 404,
      json: { detail: "older API" },
      headers: { "Access-Control-Allow-Origin": origin },
    })
  );
  await page.goto("/u/" + sender);
  await expect(page.getByRole("heading", { name: sender, exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Harmony" })).toHaveCount(0);
});
