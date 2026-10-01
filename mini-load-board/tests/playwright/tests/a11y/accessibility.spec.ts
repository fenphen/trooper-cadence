import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { LoadBoardPage } from "../../pages/LoadBoardPage";

/**
 * Automated accessibility scan with axe-core.
 *
 * axe checks the rendered DOM against WCAG rules (labels, colour contrast,
 * landmarks, ARIA usage...). It finds roughly 30-50% of accessibility issues
 * automatically - a cheap safety net, not a replacement for manual testing
 * with a screen reader or keyboard.
 */
test.describe("Accessibility", () => {
  test("load board has no serious or critical axe violations", async ({ page }) => {
    const board = new LoadBoardPage(page);
    await board.goto(); // Waits until the table has rendered.

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"]) // The rule sets most companies require.
      .analyze();

    // Keep "minor"/"moderate" as warnings; fail only on the bad ones.
    const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");

    // Print anything found so the report is useful even when the test passes.
    for (const v of results.violations) {
      console.log(`[axe:${v.impact}] ${v.id} - ${v.help} (${v.nodes.length} element(s))`);
    }

    expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
  });
});
