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
const detailMeta      = document.getElementById("detailMeta");
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
const inquiryForm   = document.getElementById("inquiryForm");
const formInquiry   = document.getElementById("formInquiry");
const inquiryTypes  = document.getElementById("inquiryTypes");
const inquiryDone   = document.getElementById("inquiryDone");
const doneTicketId  = document.getElementById("doneTicketId");
const btnNewInquiry = document.getElementById("btnNewInquiry");
const btnSubmitInq  = document.getElementById("btnSubmitInquiry");

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
// GET /health/providers が返す、実際に動作中の接続先を表示する。
// LLM と Embedding が同じ provider ならまとめて 1 つ、異なる場合は両方を表示する。
function setProviderBadge(text, cssClass, title) {
  providerBadge.textContent = text;
  providerBadge.className = "badge " + cssClass;
  providerBadge.title = title || "";
}

function providerBadgeClass(name) {
  if (name === "mock") return "badge-mock";
  if (name === "watsonx") return "badge-watsonx";
  return "badge-other";
}

function providerDisplayName(name) {
  const labels = {
    mock: "Mock",
    watsonx: "watsonx.ai",
    openai_compatible: "OpenAI互換",
    local: "ローカル",
    chroma: "Chroma",
    milvus: "Milvus",
    numpy: "NumPy",
    unavailable: "利用不可",
  };
  return labels[name] || name;
}

async function loadProvider() {
  try {
    const res = await fetch(API_BASE + "/health/providers");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const p = await res.json();
    const llm = p.llm.provider;
    const emb = p.embedding.provider;
    const llmLabel = providerDisplayName(llm);
    const embLabel = providerDisplayName(emb);
    const text = llm === emb
      ? `接続先: ${llmLabel}`
      : `LLM: ${llmLabel} / 埋め込み: ${embLabel}`;
    const title = [
      `LLM: ${llmLabel} (${p.llm.model || "—"})`,
      `埋め込み: ${embLabel} (${p.embedding.model || "—"})`,
      `ベクトルストア: ${providerDisplayName(p.vector_store.provider)}`,
    ].join("\n");
    // mock が 1 つでも含まれる場合は、実環境ではないことが分かるよう mock の色にする
    const cssClass = (llm === "mock" || emb === "mock")
      ? "badge-mock"
      : providerBadgeClass(llm);
    setProviderBadge(text, cssClass, title);
  } catch (_) {
    setProviderBadge("接続先を取得できません", "badge-other", "");
  }
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
  inquiryForm.classList.add("hidden");

  // Highlight selected
  ticketList.querySelectorAll("li").forEach(li => {
    li.classList.toggle("active", li.dataset.id === ticket.ticket_id);
  });

  // Populate detail
  detailId.textContent = ticket.ticket_id;
  detailStatus.textContent = ticket.status;
  detailTitle.textContent = ticket.title;
  // 氏名・メール・注文番号は検索・回答案生成へ渡さない。表示のみ（textContent）
  detailMeta.textContent = [
    "お客様: " + (ticket.customer_name || "—"),
    "商品: " + (ticket.product_name || "—"),
    "カテゴリ: " + (ticket.category || "未判定"),
    "緊急度: " + (ticket.priority || "未判定"),
  ].join(" | ");
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
    // 検索Queryは お問い合わせ種類・商品名・問い合わせ内容 に限定する（個人情報は送らない）
    const query = [ticket.inquiry_type, ticket.product_name, ticket.description]
      .filter(Boolean)
      .join(" ");
    const data = await apiFetch("/search", {
      method: "POST",
      body: JSON.stringify({ query: query.slice(0, 4000), top_k: 5 }),
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

    renderSuggestion(data.classification_suggestion);

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

function renderSuggestion(suggestion) {
  let box = document.getElementById("suggestionBox");
  if (!box) {
    box = document.createElement("div");
    box.id = "suggestionBox";
    box.className = "suggestion-box";
    draftText.parentNode.insertBefore(box, draftText);
  }
  if (!suggestion) {
    box.classList.add("hidden");
    return;
  }
  const label = { category: "カテゴリ", priority: "緊急度", handling_type: "対応区分",
                  assigned_team: "担当", faq_id: "FAQ番号" };
  const parts = Object.keys(label)
    .filter(k => suggestion[k])
    .map(k => `${label[k]}: ${suggestion[k]}`);
  box.textContent = "分類案（確定値ではありません。担当者が確認してください） " + parts.join(" / ");
  box.classList.remove("hidden");
}

// ── Inquiry form ───────────────────────────────────────────────────────────

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const ORDER_RE = /^[A-Z0-9-]{1,40}$/;

async function loadInquiryTypes() {
  inquiryTypes.textContent = "";
  try {
    const data = await apiFetch("/masters/inquiry-types");
    data.items.forEach(item => {
      const label = document.createElement("label");
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = "inquiryType";
      radio.value = item.inquiry_type_name;
      label.appendChild(radio);
      label.appendChild(document.createTextNode(item.inquiry_type_name));
      inquiryTypes.appendChild(label);
    });
  } catch (e) {
    showError("問い合わせ種類の取得に失敗しました: " + e.message);
  }
}

function checkField(field) {
  let ok = true;
  const type = field.dataset.type;
  if (type === "radio") {
    ok = !!field.querySelector("input:checked");
  } else {
    const el = field.querySelector("input,textarea");
    const v = el.value.trim();
    if (type === "order") ok = v === "" || ORDER_RE.test(v);
    else {
      ok = v.length > 0;
      if (ok && type === "email") ok = EMAIL_RE.test(v);
    }
  }
  field.classList.toggle("invalid", !ok);
  return ok;
}

function openInquiryForm() {
  clearError();
  currentTicketId = null;
  ticketList.querySelectorAll("li").forEach(li => li.classList.remove("active"));
  noSelection.classList.add("hidden");
  ticketDetail.classList.add("hidden");
  formInquiry.reset();
  formInquiry.classList.remove("hidden");
  inquiryDone.classList.add("hidden");
  formInquiry.querySelectorAll(".invalid").forEach(f => f.classList.remove("invalid"));
  inquiryForm.classList.remove("hidden");
}

btnNewInquiry.addEventListener("click", openInquiryForm);

formInquiry.addEventListener("submit", async e => {
  e.preventDefault();
  clearError();
  const fields = [...formInquiry.querySelectorAll(".field[data-req], .field[data-type=order]")];
  const results = fields.map(checkField);
  if (results.includes(false)) {
    fields[results.indexOf(false)].scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }

  const photo = document.getElementById("fPhoto");
  // 受付番号・作成日時・ステータスはBackendが決定する。Browserからは送らない
  const payload = {
    customer_name: document.getElementById("fName").value.trim(),
    customer_email: document.getElementById("fEmail").value.trim(),
    order_number: document.getElementById("fOrder").value.trim() || null,
    product_name: document.getElementById("fProduct").value.trim() || null,
    inquiry_type: formInquiry.querySelector("input[name=inquiryType]:checked").value,
    description: document.getElementById("fBody").value.trim(),
    has_attachment: photo.files.length > 0,
  };

  btnSubmitInq.disabled = true;
  try {
    const ticket = await apiFetch("/tickets", { method: "POST", body: JSON.stringify(payload) });
    doneTicketId.textContent = ticket.ticket_id;  // textContent: XSS防止
    formInquiry.classList.add("hidden");
    inquiryDone.classList.remove("hidden");
    loadTickets(true);
  } catch (err) {
    showError("送信に失敗しました: " + err.message);
  } finally {
    btnSubmitInq.disabled = false;
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
loadInquiryTypes();
