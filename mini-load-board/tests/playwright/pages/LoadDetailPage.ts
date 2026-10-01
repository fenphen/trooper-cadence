import { Locator, Page } from "@playwright/test";

/** Page Object for load.html?id=N - assign a carrier and move a load through its statuses. */
export class LoadDetailPage {
  readonly title: Locator;
  readonly status: Locator;
  readonly carrier: Locator;
  readonly carrierSelect: Locator;
  readonly assignButton: Locator;
  readonly markInTransitButton: Locator;
  readonly markDeliveredButton: Locator;
  readonly deleteButton: Locator;
  readonly actionMessage: Locator;
  readonly notFound: Locator;

  constructor(private readonly page: Page) {
    this.title = page.getByTestId("load-title");
    this.status = page.getByTestId("detail-status");
    this.carrier = page.getByTestId("detail-carrier");
    this.carrierSelect = page.getByTestId("carrier-select");
    this.assignButton = page.getByRole("button", { name: "Assign Carrier" });
    this.markInTransitButton = page.getByRole("button", { name: "Mark In Transit" });
    this.markDeliveredButton = page.getByRole("button", { name: "Mark Delivered" });
    this.deleteButton = page.getByRole("button", { name: "Delete Load" });
    this.actionMessage = page.getByTestId("action-message");
    this.notFound = page.getByTestId("not-found");
  }

  async goto(loadId: number) {
    await this.page.goto(`/load.html?id=${loadId}`);
  }

  /** Picks a carrier by (part of) its visible name and clicks Assign. */
  async assignCarrier(carrierName: string) {
    // <option> labels include the MC number, so look the value up by partial text.
    const option = this.carrierSelect.locator("option", { hasText: carrierName });
    const value = await option.getAttribute("value");
    if (!value) throw new Error(`No carrier option containing "${carrierName}"`);
    await this.carrierSelect.selectOption(value);
    await this.assignButton.click();
  }

  /** Picks a carrier by its database id and clicks Assign. */
  async assignCarrierById(carrierId: number) {
    await this.carrierSelect.selectOption(String(carrierId));
    await this.assignButton.click();
  }

  async markInTransit() {
    await this.markInTransitButton.click();
  }

  async markDelivered() {
    await this.markDeliveredButton.click();
  }
}
