import { defineConfig } from "@playwright/test";
if (!process.env.E2E_BASE_URL || !process.env.E2E_FIXTURES) {
  throw new Error("Run via: cd backend && poetry run python ../e2e/run.py");
}
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  retries: 0,
  reporter: [
    ["list"],
    ["html", { outputFolder: process.env.E2E_ARTIFACTS + "/report", open: "never" }],
  ],
  outputDir: process.env.E2E_ARTIFACTS + "/results",
  use: {
    baseURL: process.env.E2E_BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { browserName: "chromium", viewport: { width: 1440, height: 1000 } } },
    {
      name: "mobile",
      use: {
        browserName: "chromium",
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});
