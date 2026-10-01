// Load board page: fetch loads from the API and render them as table rows.

const statusFilter = document.getElementById("status-filter");
const originSearch = document.getElementById("origin-search");
const rows = document.getElementById("load-rows");
const emptyMessage = document.getElementById("empty-message");
const resultCount = document.getElementById("result-count");

async function refreshBoard() {
  const { ok, data } = await api.getLoads({
    status: statusFilter.value,
    origin: originSearch.value,
  });

  rows.innerHTML = "";
  if (!ok) {
    resultCount.textContent = errorMessages(data).join(" ");
    return;
  }

  // Each row is a link to the detail page. data-testid attributes give the
  // UI tests stable hooks that won't break when the styling changes.
  for (const load of data) {
    const tr = document.createElement("tr");
    tr.dataset.testid = "load-row";
    tr.dataset.loadId = load.id;
    tr.innerHTML = `
      <td><a href="/load.html?id=${load.id}" data-testid="load-link">${load.id}</a></td>
      <td data-testid="load-origin">${escapeHtml(load.origin)}</td>
      <td>${escapeHtml(load.destination)}</td>
      <td>${load.pickupDate}</td>
      <td>${formatWeight(load.weight)}</td>
      <td>${formatMoney(load.rate)}</td>
      <td><span class="status status-${load.status}" data-testid="load-status">${load.status}</span></td>
      <td>${load.carrier ? escapeHtml(load.carrier.name) : "<span class='muted'>—</span>"}</td>`;
    rows.appendChild(tr);
  }

  emptyMessage.classList.toggle("hidden", data.length > 0);
  resultCount.textContent = `${data.length} load${data.length === 1 ? "" : "s"}`;
}

// Never put user/API text straight into innerHTML without escaping it.
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

statusFilter.addEventListener("change", refreshBoard);
originSearch.addEventListener("input", refreshBoard);
refreshBoard();
