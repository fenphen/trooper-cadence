import { test, expect } from "@playwright/test";
import { LoadBoardPage } from "../../pages/LoadBoardPage";

/**
 * Load board tests: viewing, filtering and searching.
 * These only READ data, so they can rely on the seed data in SeedData.cs.
 */
test.describe("Load board", () => {
  let board: LoadBoardPage;

  test.beforeEach(async ({ page }) => {
    board = new LoadBoardPage(page);
    await board.goto();
  });

  test("shows the seeded loads with the expected columns", async ({ page }) => {
    // Role-based locators: this is how a screen reader "sees" the table.
    const table = page.getByRole("table");
    await expect(table.getByRole("columnheader", { name: "Origin" })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Status" })).toBeVisible();

    // 11 loads are seeded; other tests may add more, so assert a minimum.
    // `toHaveCount` auto-retries until the rows render - no sleeps needed.
    expect(await board.rows.count()).toBeGreaterThanOrEqual(11);
    await expect(board.resultCount).toContainText(/\d+ loads/);
  });

  test("filters the board by status", async () => {
    await board.filterByStatus("Booked");

    // Wait for the table to re-render, then check every visible row.
    await expect(board.rows.first()).toBeVisible();
    const statuses = await board.visibleStatuses();
    expect(statuses.length).toBeGreaterThan(0);
    expect(statuses.every((s) => s === "Booked")).toBe(true);

    // Clearing the filter brings everything back.
    await board.filterByStatus("");
    await expect(board.rows.first()).toBeVisible();
    expect(new Set(await board.visibleStatuses()).size).toBeGreaterThan(1);
  });

  test("searches by origin", async () => {
    await board.searchByOrigin("Dallas");

    await expect(board.rows.first()).toBeVisible();
    const origins = await board.visibleOrigins();
    expect(origins.length).toBeGreaterThan(0);
    expect(origins.every((o) => o.includes("Dallas"))).toBe(true);
  });

  test("origin search ignores letter case", async () => {
    // A dispatcher typing "dallas" in a hurry expects the same results as "Dallas".
    await board.searchByOrigin("dallas");

    await expect(board.rows.first()).toBeVisible();
    const origins = await board.visibleOrigins();
    // Guard against a vacuous pass: [].every(...) is always true!
    expect(origins.length).toBeGreaterThan(0);
    expect(origins.every((o) => o.toLowerCase().includes("dallas"))).toBe(true);
  });

  test("shows an empty-state message when nothing matches", async () => {
    await board.searchByOrigin("Nowhere, ZZ");

    await expect(board.emptyMessage).toBeVisible();
    await expect(board.rows).toHaveCount(0);
    await expect(board.resultCount).toHaveText("0 loads");
  });

  test("navigates to the load detail page from a row", async ({ page }) => {
    await board.openLoad(1);

    await expect(page).toHaveURL(/load\.html\?id=1$/);
    await expect(page.getByTestId("load-title")).toHaveText("Load #1");
  });
});
