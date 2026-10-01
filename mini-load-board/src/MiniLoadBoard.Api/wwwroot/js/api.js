// ---------------------------------------------------------------------------
// Tiny wrapper around fetch() for talking to our API.
// Every page includes this file. Keeping the HTTP details in one place means
// the page scripts only deal with "load" and "carrier" objects.
// ---------------------------------------------------------------------------

// The "secret" the server expects on POST/PUT/DELETE. In a real app this would
// never be in client-side code - it is hard-coded here to keep the demo simple.
const API_KEY = "test-key-123";

/**
 * Calls the API and returns { ok, status, data }.
 * We don't throw on 4xx so the pages can show the server's validation messages.
 */
async function apiRequest(method, url, body) {
  const headers = { "Accept": "application/json" };
  if (method !== "GET") {
    headers["X-Api-Key"] = API_KEY;
  }
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  // 204 No Content has no body to parse.
  let data = null;
  if (response.status !== 204) {
    try { data = await response.json(); } catch { data = null; }
  }
  return { ok: response.ok, status: response.status, data };
}

const api = {
  getLoads: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.status) params.set("status", filters.status);
    if (filters.origin) params.set("origin", filters.origin);
    const qs = params.toString();
    return apiRequest("GET", "/api/loads" + (qs ? "?" + qs : ""));
  },
  getLoad: (id) => apiRequest("GET", `/api/loads/${id}`),
  createLoad: (load) => apiRequest("POST", "/api/loads", load),
  assignCarrier: (loadId, carrierId) => apiRequest("PUT", `/api/loads/${loadId}/assign/${carrierId}`),
  updateStatus: (loadId, status) => apiRequest("PUT", `/api/loads/${loadId}/status`, { status }),
  deleteLoad: (id) => apiRequest("DELETE", `/api/loads/${id}`),
  getCarriers: () => apiRequest("GET", "/api/carriers"),
};

/**
 * Turns an API error response into a flat list of messages.
 * Handles both shapes our API returns:
 *   { "error": "..." }                         - simple business-rule errors
 *   { "errors": { "Weight": ["..."], ... } }   - validation problem details
 */
function errorMessages(data) {
  if (!data) return ["Something went wrong."];
  if (data.error) return [data.error];
  if (data.errors) return Object.values(data.errors).flat();
  return [data.title || "Something went wrong."];
}

// Formatting helpers shared by the pages.
const formatMoney = (n) => "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 0 });
const formatWeight = (n) => Number(n).toLocaleString("en-US") + " lbs";
