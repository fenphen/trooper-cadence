import { test, expect } from "@playwright/test";
import { LoadDetailPage } from "../../pages/LoadDetailPage";
import { createLoad, assignCarrier } from "../../helpers/api";

/**
 * Load lifecycle tests: assign a carrier, then move the load
 * Booked -> InTransit -> Delivered through the UI.
 *
 * Pattern: ARRANGE through the API (fast, reliable), ACT and ASSERT through
 * the browser. Each test creates its own load so it never depends on seed data
 * or on test order.
 */
test.describe("Load lifecycle", () => {
  test("assigns an active carrier and the load becomes Booked", async ({ page, request }) => {
    const load = await createLoad(request);

    const detail = new LoadDetailPage(page);
    await detail.goto(load.id);
    await expect(detail.status).toHaveText("Available");
    await expect(detail.carrier).toHaveText("Unassigned");

    await detail.assignCarrier("Great Lakes Freight");

    await expect(detail.actionMessage).toContainText("Carrier assigned");
    await expect(detail.status).toHaveText("Booked");
    await expect(detail.carrier).toContainText("Great Lakes Freight");
    // Once booked, the assign controls disappear.
    await expect(detail.assignButton).toBeHidden();
  });

  test("refuses to assign an inactive carrier", async ({ page, request }) => {
    const load = await createLoad(request);
    const detail = new LoadDetailPage(page);
    await detail.goto(load.id);

    await detail.assignCarrier("Budget Trucking Co"); // seeded as IsActive = false

    await expect(detail.actionMessage).toContainText("inactive");
    await expect(detail.status).toHaveText("Available"); // unchanged
  });

  test("moves a booked load through InTransit to Delivered", async ({ page, request }) => {
    const load = await createLoad(request);
    await assignCarrier(request, load.id);

    const detail = new LoadDetailPage(page);
    await detail.goto(load.id);
    await expect(detail.status).toHaveText("Booked");

    // Only the next step in the lifecycle should be clickable.
    await expect(detail.markInTransitButton).toBeEnabled();
    await expect(detail.markDeliveredButton).toBeDisabled();

    await detail.markInTransit();
    await expect(detail.status).toHaveText("InTransit");
    await expect(detail.markInTransitButton).toBeDisabled();
    await expect(detail.markDeliveredButton).toBeEnabled();

    await detail.markDelivered();
    await expect(detail.status).toHaveText("Delivered");
    await expect(detail.actionMessage).toContainText("delivered");
    await expect(detail.markDeliveredButton).toBeDisabled();
  });

  test("deletes an available load and returns to the board", async ({ page, request }) => {
    const load = await createLoad(request, { origin: "Delete Me, TX" });
    const detail = new LoadDetailPage(page);
    await detail.goto(load.id);

    await detail.deleteButton.click();

    await expect(page).toHaveURL(/\/$/);
    const check = await request.get(`/api/loads/${load.id}`);
    expect(check.status()).toBe(404);
  });
});
