import { test, expect } from "@playwright/test";
import { authHeaders, createLoad, assignCarrier, validLoad, dateFromToday } from "../../helpers/api";

/**
 * API tests using Playwright's built-in `request` fixture.
 *
 * No browser is launched for these - they talk HTTP directly, which makes them
 * fast and a good first line of defence. Compare with tests/RestSharpTests,
 * which cover the same API from C#.
 */
test.describe("Loads API", () => {
  test("GET /api/loads returns the seeded loads", async ({ request }) => {
    const response = await request.get("/api/loads");

    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toContain("application/json");
    const loads = await response.json();
    expect(loads.length).toBeGreaterThanOrEqual(11);
    // Spot-check the shape of one record.
    expect(loads[0]).toMatchObject({ id: 1, origin: "Dallas, TX", status: expect.any(String) });
  });

  test("GET /api/loads?status=Delivered only returns delivered loads", async ({ request }) => {
    const loads = await (await request.get("/api/loads?status=Delivered")).json();

    expect(loads.length).toBeGreaterThan(0);
    for (const load of loads) expect(load.status).toBe("Delivered");
  });

  test("GET /api/loads?status=Bogus returns 400", async ({ request }) => {
    const response = await request.get("/api/loads?status=Bogus");
    expect(response.status()).toBe(400);
  });

  test("GET /api/loads/{id} returns 404 for an unknown load", async ({ request }) => {
    const response = await request.get("/api/loads/999999");
    expect(response.status()).toBe(404);
    expect(await response.json()).toEqual({ error: "Load 999999 not found." });
  });

  test("POST /api/loads without an API key is rejected with 401", async ({ request }) => {
    const response = await request.post("/api/loads", { data: validLoad() });
    expect(response.status()).toBe(401);
  });

  test("POST /api/loads with a past pickup date returns 400 with a clear message", async ({ request }) => {
    const response = await request.post("/api/loads", {
      headers: authHeaders,
      data: validLoad({ pickupDate: dateFromToday(-1) }),
    });

    expect(response.status()).toBe(400);
    const problem = await response.json();
    expect(problem.errors.PickupDate).toEqual(["Pickup date cannot be in the past."]);
  });

  test("POST /api/loads accepts the 48,000 lb boundary", async ({ request }) => {
    const response = await request.post("/api/loads", {
      headers: authHeaders,
      data: validLoad({ weight: 48000 }),
    });

    expect(response.status(), await response.text()).toBe(201);
    expect(response.headers()["location"]).toMatch(/\/api\/loads\/\d+$/);
  });

  test("PUT /api/loads/{id}/status rejects skipping from Booked straight to Delivered", async ({ request }) => {
    const load = await createLoad(request);
    await assignCarrier(request, load.id);

    const response = await request.put(`/api/loads/${load.id}/status`, {
      headers: authHeaders,
      data: { status: "Delivered" },
    });

    expect(response.status(), await response.text()).toBe(400);
    const after = await (await request.get(`/api/loads/${load.id}`)).json();
    expect(after.status).toBe("Booked");
  });

  test("DELETE /api/loads/{id} removes an Available load", async ({ request }) => {
    const load = await createLoad(request);

    const del = await request.delete(`/api/loads/${load.id}`, { headers: authHeaders });
    expect(del.status()).toBe(204);

    const after = await request.get(`/api/loads/${load.id}`);
    expect(after.status()).toBe(404);
  });
});
