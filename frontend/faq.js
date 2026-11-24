/**
 * FAQ キーワード検索ページ (faq.html)
 *
 * Flow:
 *   入力 (300ms debounce) → GET /api/v1/faq/suggest?q=... → 候補リスト表示
 *   候補クリック → 右ペインに回答文を表示
 *   answer != null → テキストエリア + コピーボタンを表示
 *   answer == null → 警告メッセージを表示、コピーボタンは非表示
 *
 * XSS対策: DOM 書き込みは textContent / textarea.value のみ使用。
 */

const API_BASE = (window.API_BASE_URL || "http://127.0.0.1:8000") + "/api/v1";

// ── DOM refs ───────────────────────────────────────────────────────────────
const faqKeyword      = document.getElementById("faqKeyword");
const faqList         = document.getElementById("faqList");
const faqNoSelection  = document.getElementById("faqNoSelection");
const faqAnswerPane   = document.getElementById("faqAnswerPane");
const faqAnswerTitle  = document.getElementById("faqAnswerTitle");
const faqAnswerCat    = document.getElementById("faqAnswerCategory");
const faqCopyRow      = document.getElementById("faqCopyRow");
const faqAnswerText   = document.getElementById("faqAnswerText");
const faqCopyBtn      = document.getElementById("faqCopyBtn");
const faqUnavailable  = document.getElementById("faqUnavailable");
const faqErrorBox     = document.getElementById("faqErrorBox");
const faqLoading      = document.getElementById("faqLoading");

// ── Utilities ──────────────────────────────────────────────────────────────
function showError(msg) {
  faqErrorBox.textContent = "エラー: " + msg;
  faqErrorBox.classList.remove("hidden");
}
function clearError() { faqErrorBox.classList.add("hidden"); }
function showLoading() { faqLoading.classList.remove("hidden"); }
function hideLoading() { faqLoading.classList.add("hidden"); }

// ── Debounce ───────────────────────────────────────────────────────────────
let debounceTimer = null;
function debounce(fn, delay) {
  return (...args) => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => fn(...args), delay);
  };
}

// ── Fetch FAQ suggestions ──────────────────────────────────────────────────
async function fetchSuggestions(query) {
  clearError();
  const q = query.trim();

  if (!q) {
    renderEmpty("キーワードを入力すると候補が表示されます");
    return;
  }

  showLoading();
  try {
    const params = new URLSearchParams({ q, limit: "20" });
    const res = await fetch(API_BASE + "/faq/suggest?" + params.toString());
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    renderList(data.items);
  } catch (e) {
    showError("検索に失敗しました: " + e.message);
    renderEmpty("候補を取得できませんでした");
  } finally {
    hideLoading();
  }
}

// ── Render list ────────────────────────────────────────────────────────────
function renderEmpty(message) {
  faqList.innerHTML = "";
  const li = document.createElement("li");
  li.className = "faq-empty";
  li.textContent = message;
  faqList.appendChild(li);
}

function renderList(items) {
  faqList.innerHTML = "";

  if (items.length === 0) {
    renderEmpty("該当する FAQ が見つかりませんでした");
    return;
  }

  items.forEach(item => {
    const li = document.createElement("li");
    li.dataset.faqId = item.faq_id;

    const titleEl = document.createElement("div");
    titleEl.className = "t-title";
    titleEl.textContent = item.title;

    const categoryEl = document.createElement("div");
    categoryEl.className = "faq-item-category t-status";
    categoryEl.textContent = item.category || "";

    li.appendChild(titleEl);
    li.appendChild(categoryEl);
    li.addEventListener("click", () => selectFaq(item, li));
    faqList.appendChild(li);
  });
}

// ── Select FAQ ─────────────────────────────────────────────────────────────
function selectFaq(item, liEl) {
  // Highlight selected item
  faqList.querySelectorAll("li").forEach(li => li.classList.remove("active"));
  liEl.classList.add("active");

  // Show answer pane
  faqNoSelection.classList.add("hidden");
  faqAnswerPane.classList.remove("hidden");

  faqAnswerTitle.textContent = item.title;
  faqAnswerCat.textContent = item.category ? "カテゴリ: " + item.category : "";

  if (item.answer_unavailable || item.answer == null) {
    // Answer could not be extracted: show warning, hide copy area
    faqCopyRow.classList.add("hidden");
    faqUnavailable.classList.remove("hidden");
  } else {
    // Answer available: show textarea and copy button
    faqUnavailable.classList.add("hidden");
    faqAnswerText.value = item.answer;
    faqCopyRow.classList.remove("hidden");
    // Reset copy button label
    faqCopyBtn.textContent = "コピー";
    faqCopyBtn.classList.remove("copied");
  }
}

// ── Copy answer ────────────────────────────────────────────────────────────
faqCopyBtn.addEventListener("click", async () => {
  const text = faqAnswerText.value;
  if (!text) return;

  try {
    await navigator.clipboard.writeText(text);
    faqCopyBtn.textContent = "コピーしました ✓";
    faqCopyBtn.classList.add("copied");
    setTimeout(() => {
      faqCopyBtn.textContent = "コピー";
      faqCopyBtn.classList.remove("copied");
    }, 2000);
  } catch (_) {
    // Fallback: select all text in textarea
    faqAnswerText.select();
    showError("クリップボードへのアクセスが拒否されました。テキストを手動でコピーしてください。");
  }
});

// ── Input event with debounce ──────────────────────────────────────────────
faqKeyword.addEventListener("input", debounce(e => {
  fetchSuggestions(e.target.value);
}, 300));

faqKeyword.addEventListener("keydown", e => {
  if (e.key === "Enter") {
    clearTimeout(debounceTimer);
    fetchSuggestions(e.target.value);
  }
});

// ── Init ───────────────────────────────────────────────────────────────────
faqKeyword.focus();
