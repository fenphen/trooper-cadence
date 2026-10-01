import { APIRequestContext, expect } from "@playwright/test";

/**
 * Small helpers for talking to the API directly from tests.
 *
 * UI tests use these to *arrange* data quickly (create a fresh load through the
 * API, then exercise it through the browser). That keeps each test independent
 * of the seed data and of whatever other tests have done.
 */

export const API_KEY_HEADER = "X-Api-Key";
export const API_KEY = "test-key-123";

/** Headers for a write request (POST/PUT/DELETE). */
export const authHeaders = { [API_KEY_HEADER]: API_KEY };

/** Shape of a load as the API returns it. */
export interface Load {
  id: number;
  origin: string;
  destination: string;
  pickupDate: string;
  weight: number;
  rate: number;
  status: "Available" | "Booked" | "InTransit" | "Delivered";
  carrierId: number | null;
  carrier: { id: number; name: string; mcNumber: string; rating: number; isActive: boolean } | null;
}

/** "YYYY-MM-DD" for N days from today (UTC, matching the server's clock). */
export function dateFromToday(days: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** A valid load body; override any field with `overrides`. */
export function validLoad(overrides: Record<string, unknown> = {}) {
  return {
    origin: "Austin, TX",
    destination: "Tulsa, OK",
    pickupDate: dateFromToday(7),
    weight: 30000,
    rate: 1500,
    ...overrides,
  };
}

/** Creates an Available load through the API and returns it. */
export async function createLoad(request: APIRequestContext, overrides: Record<string, unknown> = {}): Promise<Load> {
  const response = await request.post("/api/loads", { headers: authHeaders, data: validLoad(overrides) });
  expect(response.status(), await response.text()).toBe(201);
  return response.json();
}

/** Assigns a carrier (default: carrier 1, "Lone Star Logistics", which is active). */
export async function assignCarrier(request: APIRequestContext, loadId: number, carrierId = 1): Promise<Load> {
  const response = await request.put(`/api/loads/${loadId}/assign/${carrierId}`, { headers: authHeaders });
  expect(response.status(), await response.text()).toBe(200);
  return response.json();
}

/** Changes a load's status through the API, asserting it succeeded. */
export async function setStatus(request: APIRequestContext, loadId: number, status: Load["status"]): Promise<Load> {
  const response = await request.put(`/api/loads/${loadId}/status`, { headers: authHeaders, data: { status } });
  expect(response.status(), await response.text()).toBe(200);
  return response.json();
}
