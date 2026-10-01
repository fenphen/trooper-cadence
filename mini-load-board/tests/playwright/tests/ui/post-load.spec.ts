import { test, expect } from "@playwright/test";
import { PostLoadPage } from "../../pages/PostLoadPage";
import { LoadDetailPage } from "../../pages/LoadDetailPage";
import { dateFromToday } from "../../helpers/api";

/**
 * "Post a Load" form tests: the happy path, client-side validation, and
 * server-side validation (the browser lets some values through on purpose so
 * the API's own rules get exercised).
 */
test.describe("Post a Load form", () => {
  let form: PostLoadPage;

  test.beforeEach(async ({ page }) => {
    form = new PostLoadPage(page);
    await form.goto();
  });

  test("posts a valid load and shows a success message", async ({ page }) => {
    await form.fillForm({
      origin: "Austin, TX",
      destination: "Tulsa, OK",
      pickupDate: dateFromToday(5),
      weight: 30000,
      rate: 1500,
    });
    await form.submit();

    await expect(form.successMessage).toBeVisible();
    await expect(form.successMessage).toContainText(/Load #\d+ posted/);

    // Follow the link and make sure the new load really exists.
    const newId = await form.createdLoadId();
    await page.getByTestId("view-new-load").click();
    const detail = new LoadDetailPage(page);
    await expect(detail.title).toHaveText(`Load #${newId}`);
    await expect(detail.status).toHaveText("Available");
  });

  test("shows a client-side error for every empty required field", async () => {
    await form.submit(); // Submit the empty form.

    await expect(form.fieldError("origin")).toHaveText("Origin is required.");
    await expect(form.fieldError("destination")).toHaveText("Destination is required.");
    await expect(form.fieldError("pickup-date")).toHaveText("Pickup date is required.");
    await expect(form.fieldError("weight")).toHaveText("Weight is required.");
    await expect(form.fieldError("rate")).toHaveText("Rate is required.");
    // Nothing was sent to the server.
    await expect(form.serverErrors).toBeHidden();
  });

  test("rejects an overweight load, a free load and a past pickup date", async () => {
    await form.fillForm({
      origin: "Austin, TX",
      destination: "Tulsa, OK",
      pickupDate: dateFromToday(-1),
      weight: 48001,
      rate: 0,
    });
    await form.submit();

    await expect(form.fieldError("weight")).toContainText("between 1 and 48,000");
    await expect(form.fieldError("rate")).toHaveText("Rate must be greater than 0.");
    await expect(form.fieldError("pickup-date")).toHaveText("Pickup date cannot be in the past.");
    await expect(form.successMessage).toBeHidden();
  });

  test("accepts the maximum legal weight of 48,000 lbs", async () => {
    // Boundary value: 48,000 is the top of the valid range and must be accepted
    // by both the browser and the server.
    await form.fillForm({
      origin: "Laredo, TX",
      destination: "Kansas City, MO",
      pickupDate: dateFromToday(3),
      weight: 48000,
      rate: 2800,
    });
    await form.submit();

    await expect(form.serverErrors).toBeHidden();
    await expect(form.successMessage).toBeVisible();
  });
});
