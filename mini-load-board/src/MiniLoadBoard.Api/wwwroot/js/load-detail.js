// Load detail page: show one load, let the user assign a carrier, update the
// status, or delete it. The page re-fetches the load after every action so
// what you see is always what the server has.

const loadId = Number(new URLSearchParams(location.search).get("id"));

const $ = (testId) => document.querySelector(`[data-testid="${testId}"]`);
const carrierSelect = $("carrier-select");
const actionMessage = $("action-message");

function showMessage(text, isError) {
  actionMessage.textContent = text;
  actionMessage.className = "alert " + (isError ? "alert-error" : "alert-success");
}

function render(load) {
  $("load-title").textContent = `Load #${load.id}`;
  document.title = `Load #${load.id} - Mini Load Board`;
  $("detail-route").textContent = `${load.origin} → ${load.destination}`;
  $("detail-pickup").textContent = load.pickupDate;
  $("detail-weight").textContent = formatWeight(load.weight);
  $("detail-rate").textContent = formatMoney(load.rate);
  $("detail-carrier").textContent = load.carrier ? `${load.carrier.name} (${load.carrier.mcNumber})` : "Unassigned";

  const status = $("detail-status");
  status.textContent = load.status;
  status.className = `status status-${load.status}`;

  // Show/enable only the actions that make sense for the current status.
  // The server enforces these rules too; the UI just avoids pointless clicks.
  $("assign-section").classList.toggle("hidden", load.status !== "Available");
  $("mark-in-transit").disabled = load.status !== "Booked";
  $("mark-delivered").disabled = load.status !== "InTransit";
}

async function loadCarriers() {
  const { data } = await api.getCarriers();
  carrierSelect.innerHTML = "";
  for (const carrier of data) {
    const option = document.createElement("option");
    option.value = carrier.id;
    // Inactive carriers are listed (so the server-side rule can be exercised)
    // but clearly labelled.
    option.textContent = `${carrier.name} (${carrier.mcNumber})` + (carrier.isActive ? "" : " - INACTIVE");
    option.dataset.testid = `carrier-option-${carrier.id}`;
    carrierSelect.appendChild(option);
  }
}

async function refresh() {
  const { ok, data } = await api.getLoad(loadId);
  if (!ok) {
    $("not-found").classList.remove("hidden");
    document.getElementById("load-detail").classList.add("hidden");
    document.getElementById("actions-card").classList.add("hidden");
    return;
  }
  render(data);
}

/** Runs an API action, shows the result message and refreshes the page. */
async function runAction(promise, successText) {
  const { ok, data } = await promise;
  if (ok) showMessage(successText, false);
  else showMessage(errorMessages(data).join(" "), true);
  await refresh();
}

$("assign-button").addEventListener("click", () =>
  runAction(api.assignCarrier(loadId, carrierSelect.value), "Carrier assigned - load is now Booked."));

$("mark-in-transit").addEventListener("click", () =>
  runAction(api.updateStatus(loadId, "InTransit"), "Load is now In Transit."));

$("mark-delivered").addEventListener("click", () =>
  runAction(api.updateStatus(loadId, "Delivered"), "Load delivered."));

$("delete-button").addEventListener("click", async () => {
  const { ok, data } = await api.deleteLoad(loadId);
  if (ok) location.href = "/";
  else showMessage(errorMessages(data).join(" "), true);
});

loadCarriers().then(refresh);
