import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration.
 *
 * Key ideas to be able to explain in an interview:
 *  - `webServer` starts the .NET app before the tests and waits for it to
 *    answer on `url`. Locally it reuses an already-running app (so you can
 *    keep `dotnet run` open while writing tests); in CI it always starts fresh.
 *  - `baseURL` lets tests call `page.goto("/")` instead of hard-coding hosts.
 *  - `trace: "on-first-retry"` records a full trace (DOM snapshots, network,
 *    console) only when a test fails and is retried - cheap, but invaluable.
 *  - Projects let you run the same tests on several browsers; we keep just
 *    Chromium so the suite stays fast and simple.
 */
const BASE_URL = process.env.BASE_URL ?? "http://localhost:5000";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false, // Tests share one database, so run them in order.
  workers: 1,
  forbidOnly: !!process.env.CI, // Fail CI if someone leaves `test.only` in.
  retries: process.env.CI ? 1 : 0,
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
  ],
  timeout: 30_000,
  expect: { timeout: 5_000 },

  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    // Default headers for the `request` fixture used by the API tests.
    extraHTTPHeaders: { Accept: "application/json" },
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    // Run the API from source. `--urls` pins the port so BASE_URL always matches.
    command: "dotnet run --project ../../src/MiniLoadBoard.Api --urls http://localhost:5000",
    url: BASE_URL + "/api/carriers",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000, // First `dotnet run` includes a build, which can be slow.
    stdout: "ignore",
    stderr: "pipe",
  },
});
