import { Locator, Page } from "@playwright/test";

/** The values the "Post a Load" form accepts. All optional so tests can leave fields blank. */
export interface LoadFormValues {
  origin?: string;
  destination?: string;
  pickupDate?: string; // "YYYY-MM-DD"
  weight?: string | number;
  rate?: string | number;
}

/** Page Object for post-load.html. */
export class PostLoadPage {
  readonly origin: Locator;
  readonly destination: Locator;
  readonly pickupDate: Locator;
  readonly weight: Locator;
  readonly rate: Locator;
  readonly submitButton: Locator;
  readonly serverErrors: Locator;
  readonly successMessage: Locator;

  constructor(private readonly page: Page) {
    this.origin = page.getByTestId("origin-input");
    this.destination = page.getByTestId("destination-input");
    this.pickupDate = page.getByTestId("pickup-date-input");
    this.weight = page.getByTestId("weight-input");
    this.rate = page.getByTestId("rate-input");
    this.submitButton = page.getByRole("button", { name: "Post Load" });
    // role="alert" / role="status" elements are also reachable with getByRole.
    this.serverErrors = page.getByTestId("server-errors");
    this.successMessage = page.getByTestId("success-message");
  }

  async goto() {
    await this.page.goto("/post-load.html");
  }

  /** Fills whichever fields are provided and leaves the rest empty. */
  async fillForm(values: LoadFormValues) {
    if (values.origin !== undefined) await this.origin.fill(values.origin);
    if (values.destination !== undefined) await this.destination.fill(values.destination);
    if (values.pickupDate !== undefined) await this.pickupDate.fill(values.pickupDate);
    if (values.weight !== undefined) await this.weight.fill(String(values.weight));
    if (values.rate !== undefined) await this.rate.fill(String(values.rate));
  }

  async submit() {
    await this.submitButton.click();
  }

  /** Client-side error text under a field, e.g. fieldError("weight"). */
  fieldError(field: "origin" | "destination" | "pickup-date" | "weight" | "rate"): Locator {
    return this.page.getByTestId(`${field}-error`);
  }

  /** Reads "#42" out of the success message and returns 42. */
  async createdLoadId(): Promise<number> {
    const text = await this.successMessage.textContent();
    const match = text?.match(/#(\d+)/);
    if (!match) throw new Error(`No load id found in success message: "${text}"`);
    return Number(match[1]);
  }
}
