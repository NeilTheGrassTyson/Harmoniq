import { readFileSync } from "node:fs";
import { test, expect, type BrowserContext, type Page } from "@playwright/test";

const fixtures = JSON.parse(readFileSync(process.env.E2E_FIXTURES!, "utf8")) as {
  accounts: Record<string, { id: string; username: string; token: string }>;
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

test("ask, decline silently, ask back, accept, follow back and remove", async ({
  browser,
}, testInfo) => {
  const asker = "e2e_" + testInfo.project.name + "_asker";
  const owner = "e2e_" + testInfo.project.name + "_owner";
  const askerContext = await browser.newContext(testInfo.project.use);
  const ownerContext = await browser.newContext(testInfo.project.use);
  await signIn(askerContext, asker);
  await signIn(ownerContext, owner);
  const a = await askerContext.newPage();
  const o = await ownerContext.newPage();
  const pageErrors: string[] = [];
  for (const page of [a, o]) page.on("pageerror", (error) => pageErrors.push(error.message));
  try {
    // The send is acknowledged once; the sender never sees it again.
    await a.goto(origin + "/u/" + owner);
    await a.getByRole("button", { name: "Add friend", exact: true }).click();
    await expect(a.getByText("Request sent.")).toBeVisible();
    await expect(a.getByRole("button", { name: "Add friend", exact: true })).toBeVisible();
    await a.reload();
    await expect(a.getByRole("button", { name: "Add friend", exact: true })).toBeVisible();
    await expect(a.getByText(/Request sent|pending/i)).toHaveCount(0);

    // The owner is told, and declining is quiet.
    await o.goto(origin + "/friends");
    const requests = o.getByRole("region", { name: "Requests" });
    await expect(requests.getByText("@" + asker)).toBeVisible();
    await noOverflow(o);
    await o.screenshot({ path: testInfo.outputPath("friend-request.png"), fullPage: true });
    await requests.getByRole("button", { name: "Not now", exact: true }).click();
    await expect(o.getByRole("region", { name: "Requests" })).toHaveCount(0);

    // Nothing about the decline reaches the sender.
    await a.reload();
    await expect(a.getByRole("button", { name: "Add friend", exact: true })).toBeVisible();
    await a.goto(origin + "/friends");
    await expect(a.getByRole("region", { name: "Requests" })).toHaveCount(0);
    await expect(a.getByText(/declin|reject/i)).toHaveCount(0);

    // A decline is recoverable: the owner asks instead.
    await o.goto(origin + "/u/" + asker);
    await o.getByRole("button", { name: "Add friend", exact: true }).click();
    await expect(o.getByText("Request sent.")).toBeVisible();

    // Accepting offers a one-tap follow-back, since friendship creates no follow.
    await a.goto(origin + "/friends");
    await a
      .getByRole("region", { name: "Requests" })
      .getByRole("button", { name: "Accept", exact: true })
      .click();
    const friends = a.getByRole("region", { name: "Friends" });
    await expect(friends.getByText("@" + owner)).toBeVisible();
    await friends.getByRole("button", { name: "Follow", exact: true }).click();
    await expect(friends.getByRole("button", { name: "Following", exact: true })).toBeEnabled();

    // The owner sees the friendship on the profile and can end it quietly.
    await o.goto(origin + "/u/" + asker);
    await o.getByRole("button", { name: /Friends/ }).click();
    await o.getByRole("button", { name: "Remove", exact: true }).click();
    await expect(o.getByRole("button", { name: "Add friend", exact: true })).toBeVisible();
    await a.goto(origin + "/friends");
    await expect(a.getByText(/No friends yet/)).toBeVisible();

    // The consent setting is on the settings page.
    await o.goto(origin + "/settings");
    await expect(o.getByText("Who can send you friend requests")).toBeVisible();
    await noOverflow(o);
    expect(pageErrors).toEqual([]);
  } finally {
    await askerContext.close();
    await ownerContext.close();
  }
});
