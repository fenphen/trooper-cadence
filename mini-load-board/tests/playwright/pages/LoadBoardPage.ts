import { Locator, Page, expect } from "@playwright/test";

/**
 * Page Object for the load board (index.html).
 *
 * The Page Object Model (POM) pattern keeps "how to find and click things" in
 * one class per page, so tests read like user stories and only one place needs
 * updating when the UI changes.
 *
 * Locator strategy, in order of preference:
 *   1. getByRole  - matches how users and screen readers see the page.
 *   2. getByTestId - stable `data-testid` hooks we added for the test suite.
 *   3. CSS/XPath  - last resort, brittle; avoided here.
 */
export class LoadBoardPage {
  readonly statusFilter: Locator;
  readonly originSearch: Locator;
  readonly rows: Locator;
  readonly resultCount: Locator;
  readonly emptyMessage: Locator;

  constructor(private readonly page: Page) {
    this.statusFilter = page.getByTestId("status-filter");
    this.originSearch = page.getByTestId("origin-search");
    this.rows = page.getByTestId("load-row");
    this.resultCount = page.getByTestId("result-count");
    this.emptyMessage = page.getByTestId("empty-message");
  }

  async goto() {
    await this.page.goto("/");
    // The table is filled by JavaScript after the page loads, so wait for the
    // result count to appear instead of a fixed sleep.
    await expect(this.resultCount).toContainText(/load/);
  }

  /**
   * Changing a filter triggers a fetch and the table is re-rendered when the
   * response arrives. Waiting for that response (instead of a fixed sleep)
   * guarantees the rows we read next are the filtered ones, not the old ones.
   */
  async filterByStatus(status: "" | "Available" | "Booked" | "InTransit" | "Delivered") {
    const reloaded = this.page.waitForResponse((r) => r.url().includes("/api/loads"));
    await this.statusFilter.selectOption(status);
    await reloaded;
  }

  async searchByOrigin(text: string) {
    const reloaded = this.page.waitForResponse((r) => r.url().includes("/api/loads"));
    await this.originSearch.fill(text); // fill() fires a single "input" event
    await reloaded;
  }

  /** Status cell text for every visible row, e.g. ["Available", "Booked"]. */
  async visibleStatuses(): Promise<string[]> {
    return this.rows.getByTestId("load-status").allTextContents();
  }

  /** Origin cell text for every visible row. */
  async visibleOrigins(): Promise<string[]> {
    return this.rows.getByTestId("load-origin").allTextContents();
  }

  /** The row for one specific load id. */
  row(loadId: number): Locator {
    return this.page.locator(`[data-testid="load-row"][data-load-id="${loadId}"]`);
  }

  async openLoad(loadId: number) {
    await this.row(loadId).getByTestId("load-link").click();
  }
}
