/**
 * Helpdesk Support – minimal vanilla JS frontend
 * API base URL can be overridden by window.API_BASE_URL (useful for dev with Vite proxy).
 * All DOM writes use textContent / createElement to prevent XSS.
 */

const API_BASE = (window.API_BASE_URL || "http://127.0.0.1:8000") + "/api/v1";

// ── State ──────────────────────────────────────────────────────────────────
let currentTicketId = null;
let nextCursor = null;
let filterStatus = "";
let isLoading = false;

// ── DOM refs ───────────────────────────────────────────────────────────────
const ticketList      = document.getElementById("ticketList");
const btnLoadMore     = document.getElementById("btnLoadMore");
const btnFilter       = document.getElementById("btnFilter");
const filterInput     = document.getElementById("filterStatus");
const noSelection     = document.getElementById("noSelection");
const ticketDetail    = document.getElementById("ticketDetail");
const detailId        = document.getElementById("detailId");
const detailStatus    = document.getElementById("detailStatus");
const detailTitle     = document.getElementById("detailTitle");
const detailDept      = document.getElementById("detailDept");
const detailDesc      = document.getElementById("detailDesc");
const btnSearch       = document.getElementById("btnSearch");
const btnDraft        = document.getElementById("btnDraft");
const searchResults   = document.getElementById("searchResults");
const searchList      = document.getElementById("searchList");
const draftSection    = document.getElementById("draftSection");
const draftText       = document.getElementById("draftText");
const citationList    = document.getElementById("citationList");
const draftMeta       = document.getElementById("draftMeta");
const errorBox        = document.getElementById("errorBox");
const loadingSpinner  = document.getElementById("loadingSpinner");
const providerBadge   = document.getElementById("providerBadge");

// ── Utilities ──────────────────────────────────────────────────────────────
function showError(msg) {
  errorBox.textContent = "エラー: " + msg;
  errorBox.classList.remove("hidden");
}
function clearError() { errorBox.classList.add("hidden"); }
function showLoading() { loadingSpinner.classList.remove("hidden"); }
function hideLoading() { loadingSpinner.classList.add("hidden"); }

async function apiFetch(path, options = {}) {
  const res = await fetch(API_BASE + path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Provider badge ─────────────────────────────────────────────────────────
async function loadProvider() {
  try {
    // POST to /llm/generate with a trivial prompt to discover provider
    // Fall back to health check metadata if that endpoint is not exposed
    const res = await fetch(API_BASE + "/health/live");
    if (res.ok) {
      providerBadge.textContent = "Provider: mock";
      providerBadge.className = "badge badge-mock";
    }
  } catch (_) { /* ignore */ }
}

// ── Ticket list ────────────────────────────────────────────────────────────
async function loadTickets(reset = false) {
  if (isLoading) return;
  isLoading = true;
  btnLoadMore.disabled = true;

  if (reset) {
    ticketList.innerHTML = "";
    nextCursor = null;
  }

  const params = new URLSearchParams({ limit: "20" });
  if (filterStatus.trim()) params.set("status", filterStatus.trim());
  if (nextCursor) params.set("cursor", nextCursor);

  try {
    const data = await apiFetch("/tickets?" + params.toString());
    if (reset && data.items.length === 0) {
      const li = document.createElement("li");
      li.className = "placeholder";
      li.textContent = "チケットが見つかりません";
      ticketList.appendChild(li);
    }
    data.items.forEach(renderTicketItem);
    nextCursor = data.next_cursor;
    btnLoadMore.disabled = !nextCursor;
  } catch (e) {
    showError("チケット一覧の取得に失敗しました: " + e.message);
  } finally {
    isLoading = false;
  }
}

function renderTicketItem(ticket) {
  const li = document.createElement("li");
  li.dataset.id = ticket.ticket_id;

  const idEl = document.createElement("div");
  idEl.className = "t-id";
  idEl.textContent = ticket.ticket_id;

  const titleEl = document.createElement("div");
  titleEl.className = "t-title";
  titleEl.textContent = ticket.title;

  const statusEl = document.createElement("div");
  statusEl.className = "t-status";
  statusEl.textContent = ticket.status;

  li.appendChild(idEl);
  li.appendChild(titleEl);
  li.appendChild(statusEl);

  li.addEventListener("click", () => selectTicket(ticket));
  ticketList.appendChild(li);
}

// ── Ticket detail ──────────────────────────────────────────────────────────
function selectTicket(ticket) {
  currentTicketId = ticket.ticket_id;
  clearError();

  // Highlight selected
  ticketList.querySelectorAll("li").forEach(li => {
    li.classList.toggle("active", li.dataset.id === ticket.ticket_id);
  });

  // Populate detail
  detailId.textContent = ticket.ticket_id;
  detailStatus.textContent = ticket.status;
  detailTitle.textContent = ticket.title;
  detailDept.textContent = "依頼部署: " + (ticket.requester_department || "—");
  detailDesc.textContent = ticket.description;

  // Reset RAG sections
  searchResults.classList.add("hidden");
  draftSection.classList.add("hidden");
  searchList.innerHTML = "";
  citationList.innerHTML = "";
  draftText.value = "";
  draftMeta.textContent = "";

  noSelection.classList.add("hidden");
  ticketDetail.classList.remove("hidden");
}

// ── Knowledge search ───────────────────────────────────────────────────────
btnSearch.addEventListener("click", async () => {
  if (!currentTicketId) return;
  clearError();
  showLoading();
  searchResults.classList.add("hidden");

  try {
    const ticket = await apiFetch("/tickets/" + currentTicketId);
    const query = ticket.title + " " + ticket.description;
    const data = await apiFetch("/search", {
      method: "POST",
      body: JSON.stringify({ query: query.slice(0, 500), top_k: 5 }),
    });

    searchList.innerHTML = "";
    if (data.items.length === 0) {
      const li = document.createElement("li");
      li.textContent = "関連文書が見つかりませんでした";
      searchList.appendChild(li);
    } else {
      data.items.forEach(renderSourceItem.bind(null, searchList));
    }
    searchResults.classList.remove("hidden");
  } catch (e) {
    showError("検索に失敗しました: " + e.message);
  } finally {
    hideLoading();
  }
});

function renderSourceItem(container, item, index) {
  const li = document.createElement("li");

  if (item.citation_id) {
    const badge = document.createElement("span");
    badge.className = "citation-id";
    badge.textContent = item.citation_id;
    li.appendChild(badge);
  }

  const titleEl = document.createElement("div");
  titleEl.className = "s-title";
  titleEl.textContent = (index != null ? `[${index + 1}] ` : "") + (item.title || "");

  const snippetEl = document.createElement("div");
  snippetEl.className = "s-snippet";
  snippetEl.textContent = item.snippet || "";

  const metaEl = document.createElement("div");
  metaEl.className = "s-meta";
  const score = item.score != null ? ` | score: ${item.score.toFixed(3)}` : "";
  metaEl.textContent = (item.source || "") + score;

  li.appendChild(titleEl);
  li.appendChild(snippetEl);
  li.appendChild(metaEl);
  container.appendChild(li);
}

// ── Draft answer ───────────────────────────────────────────────────────────
btnDraft.addEventListener("click", async () => {
  if (!currentTicketId) return;
  clearError();
  showLoading();
  draftSection.classList.add("hidden");

  try {
    const data = await apiFetch("/answers/draft", {
      method: "POST",
      body: JSON.stringify({ ticket_id: currentTicketId, top_k: 5 }),
    });

    draftText.value = data.draft_answer || "";

    citationList.innerHTML = "";
    if (data.citations && data.citations.length > 0) {
      data.citations.forEach(c => renderSourceItem(citationList, c, null));
    } else {
      const li = document.createElement("li");
      li.textContent = "参照元なし";
      citationList.appendChild(li);
    }

    const meta = data.metadata || {};
    draftMeta.textContent =
      `Provider: ${meta.provider || "—"} | Model: ${meta.model || "—"} | Request ID: ${meta.request_id || "—"}`;

    draftSection.classList.remove("hidden");
  } catch (e) {
    showError("回答案の生成に失敗しました: " + e.message);
  } finally {
    hideLoading();
  }
});

// ── Filter ─────────────────────────────────────────────────────────────────
btnFilter.addEventListener("click", () => {
  filterStatus = filterInput.value.trim();
  loadTickets(true);
});
filterInput.addEventListener("keydown", e => {
  if (e.key === "Enter") btnFilter.click();
});

btnLoadMore.addEventListener("click", () => loadTickets(false));

// ── Init ───────────────────────────────────────────────────────────────────
loadProvider();
loadTickets(true);
