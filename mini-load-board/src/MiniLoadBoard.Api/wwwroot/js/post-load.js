// "Post a Load" page: client-side validation, then POST to the API and show
// whatever the server says. The server re-validates everything - client-side
// checks are a convenience for the user, not a security boundary.

const form = document.getElementById("post-load-form");
const serverErrors = document.getElementById("server-errors");
const successMessage = document.getElementById("success-message");

const MAX_WEIGHT = 48000;

/** Returns an object of field -> message for anything invalid (empty when valid). */
function validateClientSide(values) {
  const errors = {};
  const today = new Date().toISOString().slice(0, 10); // "YYYY-MM-DD"

  if (!values.origin.trim()) errors.origin = "Origin is required.";
  if (!values.destination.trim()) errors.destination = "Destination is required.";

  if (!values.pickupDate) errors.pickupDate = "Pickup date is required.";
  else if (values.pickupDate < today) errors.pickupDate = "Pickup date cannot be in the past.";

  const weight = Number(values.weight);
  if (values.weight === "") errors.weight = "Weight is required.";
  else if (!Number.isInteger(weight) || weight < 1 || weight > MAX_WEIGHT)
    errors.weight = `Weight must be between 1 and ${MAX_WEIGHT.toLocaleString()} lbs.`;

  const rate = Number(values.rate);
  if (values.rate === "") errors.rate = "Rate is required.";
  else if (!(rate > 0)) errors.rate = "Rate must be greater than 0.";

  return errors;
}

function showFieldErrors(errors) {
  // Map camelCase field names to the data-testid used by the error <span>s.
  const ids = {
    origin: "origin-error",
    destination: "destination-error",
    pickupDate: "pickup-date-error",
    weight: "weight-error",
    rate: "rate-error",
  };
  for (const [field, testId] of Object.entries(ids)) {
    const span = form.querySelector(`[data-testid="${testId}"]`);
    span.textContent = errors[field] || "";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  serverErrors.classList.add("hidden");
  successMessage.classList.add("hidden");

  const values = Object.fromEntries(new FormData(form).entries());

  const clientErrors = validateClientSide(values);
  showFieldErrors(clientErrors);
  if (Object.keys(clientErrors).length > 0) return;

  const { ok, data } = await api.createLoad({
    origin: values.origin.trim(),
    destination: values.destination.trim(),
    pickupDate: values.pickupDate,
    weight: Number(values.weight),
    rate: Number(values.rate),
  });

  if (!ok) {
    serverErrors.innerHTML = "<strong>The server rejected this load:</strong><ul>" +
      errorMessages(data).map((m) => `<li>${m}</li>`).join("") + "</ul>";
    serverErrors.classList.remove("hidden");
    return;
  }

  successMessage.innerHTML = `Load <strong>#${data.id}</strong> posted. <a href="/load.html?id=${data.id}" data-testid="view-new-load">View it</a> or <a href="/">back to the board</a>.`;
  successMessage.classList.remove("hidden");
  form.reset();
});
