/**
 * Helpdesk Support – vanilla JS frontend
 * API base URL can be overridden by window.API_BASE_URL (useful for dev with Vite proxy).
 * All DOM writes use textContent / createElement to prevent XSS.
 */

const API_BASE = (window.API_BASE_URL || "http://127.0.0.1:8000") + "/api/v1";
const STATUS_TABS = ["未対応", "対応中", "完了", "すべて"];
const PRIORITY_CLASS = { "高": "prio-high", "中": "prio-mid", "低": "prio-low" };

// ── State ──────────────────────────────────────────────────────────────────
let tickets = [];          // 全チケット（クライアント側で絞り込む）
let statusTab = "未対応";
let currentTicket = null;
let currentSuggestion = null;
let drafts = {};           // { customer: string, forward: string|null }
let draftTab = "customer";

const $ = id => document.getElementById(id);
const statusTabs = $("statusTabs"), ticketList = $("ticketList");
const noSelection = $("noSelection"), ticketDetail = $("ticketDetail");
const draftSection = $("draftSection"), loadingBox = $("loadingBox");
const btnDraft = $("btnDraft"), errorBox = $("errorBox");
const draftText = $("draftText"), draftTabs = $("draftTabs");
const inquiryForm = $("inquiryForm"), formInquiry = $("formInquiry");

// ── Utilities ──────────────────────────────────────────────────────────────
function showError(msg) { errorBox.textContent = "エラー: " + msg; errorBox.classList.remove("hidden"); }
function clearError() { errorBox.classList.add("hidden"); }

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

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text != null) e.textContent = text;
  return e;
}

function setPriority(elem, priority) {
  const p = priority || "未判定";
  elem.textContent = p;
  elem.className = "prio " + (PRIORITY_CLASS[p] || "prio-none");
}

function timeAgo(iso) {
  const min = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  if (min < 60) return `${min}分前`;
  if (min < 60 * 24) return `${Math.floor(min / 60)}時間前`;
  return `${Math.floor(min / 1440)}日前`;
}

function formatReceived(iso) {
  const d = new Date(iso);
  const pad = n => String(n).padStart(2, "0");
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// ── Provider ───────────────────────────────────────────────────────────────
const PROVIDER_LABEL = { mock: "Mock", watsonx: "watsonx.ai", openai_compatible: "OpenAI互換", local: "ローカル" };

async function loadProvider() {
  const badge = $("providerBadge");
  try {
    const p = await apiFetch("/health/providers");
    const llm = PROVIDER_LABEL[p.llm.provider] || p.llm.provider;
    const emb = PROVIDER_LABEL[p.embedding.provider] || p.embedding.provider;
    badge.textContent = llm === emb ? `接続先: ${llm}` : `LLM: ${llm} / 埋め込み: ${emb}`;
    badge.title = `LLM: ${p.llm.model || "—"}\n埋め込み: ${p.embedding.model || "—"}`;
    // mock が含まれる場合は、実環境ではないことが分かるようにする
    badge.classList.toggle("is-mock", p.llm.provider === "mock" || p.embedding.provider === "mock");
  } catch (_) {
    badge.textContent = "接続先を取得できません";
  }
}

// ── Ticket list ────────────────────────────────────────────────────────────
async function loadTickets() {
  // shortcut: 全件を取得してクライアント側で絞り込む。数千件を超えるならサーバー側の絞り込みに戻す
  const all = [];
  let cursor = null;
  try {
    do {
      const params = new URLSearchParams({ limit: "100" });
      if (cursor) params.set("cursor", cursor);
      const data = await apiFetch("/tickets?" + params.toString());
      all.push(...data.items);
      cursor = data.next_cursor;
    } while (cursor);
    tickets = all;
    renderTabs();
    renderList();
  } catch (e) {
    showError("問い合わせ一覧の取得に失敗しました: " + e.message);
  }
}

function renderTabs() {
  statusTabs.textContent = "";
  STATUS_TABS.forEach(name => {
    const count = name === "すべて" ? tickets.length : tickets.filter(t => t.status === name).length;
    const b = el("button", null, name);
    b.type = "button";
    b.setAttribute("role", "tab");
    b.setAttribute("aria-selected", String(name === statusTab));
    b.appendChild(el("span", "count", String(count)));
    b.addEventListener("click", () => { statusTab = name; renderTabs(); renderList(); });
    statusTabs.appendChild(b);
  });
}

function renderList() {
  ticketList.textContent = "";
  const visible = tickets.filter(t => statusTab === "すべて" || t.status === statusTab);
  if (visible.length === 0) {
    ticketList.appendChild(el("li", "placeholder", "この状態の問い合わせはありません"));
    return;
  }
  visible.forEach(t => {
    const li = el("li");
    const b = el("button", "ticket-item" + (currentTicket?.ticket_id === t.ticket_id ? " active" : ""));
    b.type = "button";
    b.dataset.id = t.ticket_id;

    const row = el("div", "row");
    const prio = el("span");
    setPriority(prio, t.priority);
    row.append(prio, el("span", "t-id", t.ticket_id),
      el("span", "t-ago", t.status === "完了" ? "完了" : timeAgo(t.created_at)));

    const sub = el("div", "t-sub");
    sub.appendChild(el("span", null, t.status));
    if (t.has_attachment) sub.appendChild(el("span", null, "写真あり"));

    b.append(row, el("div", "t-title", t.title), sub);
    b.addEventListener("click", () => selectTicket(t));
    li.appendChild(b);
    ticketList.appendChild(li);
  });
}

// ── Ticket detail ──────────────────────────────────────────────────────────
function renderHeader(t) {
  $("detailId").textContent = t.ticket_id;
  renderStatusSwitch(t);
  setPriority($("detailPriority"), t.priority);
  $("detailPriority").textContent = "緊急度 " + (t.priority || "未判定");
  $("detailReceived").textContent = `受付 ${formatReceived(t.created_at)}（${timeAgo(t.created_at)}）`;
}

// ステータスの切り替え（アプリ内だけで変わる。スプシには書き戻さない）
function renderStatusSwitch(t) {
  const box = $("statusSwitch");
  box.textContent = "";
  STATUS_TABS.filter(s => s !== "すべて").forEach(name => {
    const b = el("button", null, name);
    b.type = "button";
    b.setAttribute("role", "radio");
    b.setAttribute("aria-checked", String(t.status === name));
    b.addEventListener("click", () => changeStatus(name));
    box.appendChild(b);
  });
}

async function changeStatus(name) {
  const t = currentTicket;
  if (!t || t.status === name) return;
  clearError();
  try {
    const updated = await apiFetch("/tickets/" + t.ticket_id, {
      method: "PATCH",
      body: JSON.stringify({ version: t.version, status: name }),
    });
    tickets = tickets.map(x => (x.ticket_id === updated.ticket_id ? updated : x));
    if (currentTicket?.ticket_id === updated.ticket_id) {
      currentTicket = updated;
      renderHeader(updated);
    }
    renderTabs();
    renderList();
  } catch (e) {
    // 409 は別の画面などで先に更新された場合。最新を読み直してもらう
    showError("ステータスを変更できませんでした: " + e.message);
  }
}

function selectTicket(ticket) {
  currentTicket = ticket;
  currentSuggestion = null;
  clearError();
  inquiryForm.classList.add("hidden");
  ticketList.querySelectorAll(".ticket-item").forEach(b => b.classList.toggle("active", b.dataset.id === ticket.ticket_id));

  renderHeader(ticket);
  $("detailTitle").textContent = ticket.title;
  // 氏名は表示のみ（textContent）。検索・回答案生成へは渡さない
  $("detailCustomer").textContent = ticket.customer_name || "—";
  $("detailProduct").textContent = ticket.product_name || "—";
  $("detailDesc").textContent = ticket.description;
  // 注文番号は担当者が注文管理システムで調べるために表示する（LLM・検索には渡さない）
  $("detailOrder").textContent = ticket.order_number || "なし";
  // 写真があるのにリンクが無い（Excel から取り込んだチケットなど）ときだけ知らせる
  $("photoNote").classList.toggle("hidden",
    !(ticket.has_attachment && !(ticket.attachment_file_ids || []).length));

  renderPhotos(ticket.attachment_file_ids || []);
  loadRelated(ticket);
  loadSimilar(ticket);

  draftSection.classList.add("hidden");
  loadingBox.classList.add("hidden");
  btnDraft.classList.remove("hidden");
  btnDraft.disabled = false;
  noSelection.classList.add("hidden");
  ticketDetail.classList.remove("hidden");
}

// ── Photos（Google ドライブの添付写真。ブラウザのGoogleログインの権限で表示する） ──
const DRIVE_ID_RE = /^[A-Za-z0-9_-]{10,100}$/;

function renderPhotos(ids) {
  const box = $("detailPhotos");
  box.textContent = "";
  const valid = ids.filter(id => DRIVE_ID_RE.test(id));
  box.classList.toggle("hidden", valid.length === 0);
  valid.forEach((id, i) => {
    const a = el("a", "photo");
    a.href = `https://drive.google.com/file/d/${id}/view`;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    const img = el("img");
    img.src = `https://drive.google.com/thumbnail?id=${id}&sz=w480`;
    img.alt = `添付写真 ${i + 1}`;
    img.loading = "lazy";
    img.referrerPolicy = "no-referrer";
    // 見る権限がない（別アカウントなど）ときは、ドライブで開くリンクだけにする
    img.addEventListener("error", () => a.replaceChildren(el("span", "photo-fallback", `写真 ${i + 1} をドライブで開く`)));
    a.appendChild(img);
    box.appendChild(a);
  });
}

// ── Related documents（FAQ・分類基準。開いた時点で表示する） ──────────────────
// 検索結果の本文は「タイトル 質問: … 回答: … 窓口対応: …」の形なので、担当者に要る部分だけにする
function summarizeDoc(c) {
  let s = (c.snippet || "").trim();
  if (c.title && s.startsWith(c.title)) s = s.slice(c.title.length).trim();
  const faq = s.match(/回答:\s*(.*?)(?:\s*窓口対応:\s*(.*))?$/);
  if (faq) return { body: faq[1], tag: faq[2] ? `窓口対応: ${faq[2]}` : "" };
  const route = s.match(/対応先:\s*(\S+)/);
  return { body: s, tag: route ? `対応先: ${route[1]}` : "" };
}

function renderSourceList(list, items) {
  list.textContent = "";
  items.forEach(c => {
    const { body, tag } = summarizeDoc(c);
    const li = el("li");
    const head = el("div", "s-head");
    const source = (c.source || "").split("#")[0].replace(/\.xlsx$/, "");
    const score = c.score != null ? `  類似度 ${c.score.toFixed(2)}` : "";
    head.append(el("span", "s-title", c.title || ""), el("span", "s-source", source + score));
    li.append(head, el("div", "s-snippet", body));
    if (tag) li.appendChild(el("span", "chip", tag));
    list.appendChild(li);
  });
}

async function loadRelated(ticket) {
  const list = $("relatedList"), status = $("relatedStatus");
  list.textContent = "";
  status.textContent = "探しています";
  status.classList.remove("hidden");
  // 個人情報は送らない。お客様が選ぶ種類はあてにならないので、商品名と本文だけで探す
  const query = [ticket.product_name, ticket.description].filter(Boolean).join(" ").slice(0, 4000);
  try {
    const data = await apiFetch("/search", { method: "POST", body: JSON.stringify({ query, top_k: 3 }) });
    if (currentTicket?.ticket_id !== ticket.ticket_id) return;  // 別のチケットへ移った
    renderSourceList(list, data.items);
    status.textContent = data.items.length ? "" : "関連する FAQ・分類基準は見つかりませんでした";
    status.classList.toggle("hidden", data.items.length > 0);
  } catch (e) {
    if (currentTicket?.ticket_id !== ticket.ticket_id) return;
    status.textContent = "関連文書を取得できませんでした: " + e.message;
  }
}

// ── Similar inquiries（回答案とは別の機能。開いた時点で表示する） ─────────────
async function loadSimilar(ticket) {
  // shortcut: 過去データ担当の類似検索APIができるまで空表示。できたらここで呼んで renderSimilar に渡す
  renderSimilar({ note: "", items: [] });
}

function renderSimilar(result) {
  const list = $("similarList"), note = $("similarNote");
  list.textContent = "";
  note.textContent = result.note || "";
  note.classList.toggle("hidden", !result.note);
  $("similarEmpty").classList.toggle("hidden", result.items.length > 0);
  result.items.forEach(m => {
    const li = el("li");
    const row = el("div", "row");
    const prio = el("span");
    setPriority(prio, m.priority);
    row.append(el("span", "meta-text", `${m.ticket_id}  ${m.date || ""}`), prio);
    li.append(row, el("div", null, m.description),
      el("div", "meta-text", [m.category, m.handling_type, m.assigned_team, m.faq_id].filter(Boolean).join(" ／ ")));
    if (m.notes) li.appendChild(el("div", "meta-text", "備考: " + m.notes));
    list.appendChild(li);
  });
}

// ── Draft answer ───────────────────────────────────────────────────────────
btnDraft.addEventListener("click", async () => {
  if (!currentTicket) return;
  const ticket = currentTicket;
  clearError();
  btnDraft.disabled = true;
  btnDraft.classList.add("hidden");
  draftSection.classList.add("hidden");
  loadingBox.classList.remove("hidden");

  try {
    const data = await apiFetch("/answers/draft", {
      method: "POST",
      body: JSON.stringify({ ticket_id: ticket.ticket_id, top_k: 5 }),
    });
    if (currentTicket !== ticket) return;  // 生成中に別のチケットへ移った
    renderDraft(ticket, data);
    loadingBox.classList.add("hidden");
    draftSection.classList.remove("hidden");
  } catch (e) {
    loadingBox.classList.add("hidden");
    btnDraft.classList.remove("hidden");
    showError("回答案の生成に失敗しました: " + e.message);
  } finally {
    btnDraft.disabled = false;
  }
});

function handlingText(s) {
  if (!s) return "判断できませんでした";
  if (s.handling_type === "専門部署へ引き継ぎ" && s.assigned_team) return `${s.assigned_team}へ回す`;
  if (s.handling_type === "FAQで回答") return "窓口で回答する";
  return s.assigned_team || s.handling_type || "判断できませんでした";
}

function renderDraft(ticket, data) {
  // AIの判断
  const s = data.classification_suggestion || null;
  currentSuggestion = s;
  $("aiHandling").textContent = handlingText(s);
  setPriority($("aiPriority"), s?.priority);
  $("aiReason").textContent = s?.priority_reason || "";
  $("aiCategory").textContent =
    [s?.category, s?.handling_type, s?.assigned_team, s?.faq_id].filter(Boolean).join(" ／ ") || "提案なし";
  const btnApply = $("btnApplySuggestion");
  btnApply.disabled = !s;
  btnApply.textContent = "この分類を適用";
  $("applyResult").textContent = "";

  // 送る前に確認すること
  const checks = (Array.isArray(data.missing_information) ? data.missing_information : [])
    .filter(x => typeof x === "string" && x.trim());
  const list = $("checkList");
  list.textContent = "";
  checks.forEach((text, i) => {
    const li = el("li");
    const label = el("label");
    const box = el("input");
    box.type = "checkbox";
    box.id = `check-${i}`;
    box.addEventListener("change", updateCheckCount);
    label.append(box, el("span", null, text));
    li.appendChild(label);
    list.appendChild(li);
  });
  $("checkBox").classList.toggle("hidden", checks.length === 0);
  updateCheckCount();

  // 下書き（お客様への回答 ／ 担当部署への転送文）
  const greeting = ticket.customer_name ? `${ticket.customer_name} 様\n\n` : "お客様\n\n";
  drafts = {
    customer: `件名：Re: ${ticket.title || "お問い合わせの件"}\n\n${greeting}${data.draft_answer || ""}\n\n---\n問い合わせ窓口担当\n`,
    forward: data.forward_draft || null,
  };
  draftTab = "customer";
  renderDraftTabs(s);

  // 参照した資料
  const cites = data.citations || [];
  $("refsSummary").textContent = `参照した資料（${cites.length}件）`;
  renderSourceList($("citationList"), cites);

  const meta = data.metadata || {};
  $("draftMeta").textContent = `Model: ${meta.model || "—"} ／ Request ID: ${meta.request_id || "—"}`;
}

function updateCheckCount() {
  const boxes = [...$("checkList").querySelectorAll("input")];
  $("checkCount").textContent = `${boxes.filter(b => b.checked).length} / ${boxes.length} 完了`;
}

function renderDraftTabs(s) {
  draftTabs.textContent = "";
  const tabs = [{ key: "customer", label: drafts.forward ? "お客様への一次回答" : "お客様への回答" }];
  if (drafts.forward) tabs.push({ key: "forward", label: `${s?.assigned_team || "担当部署"}への転送文` });
  tabs.forEach(tab => {
    const b = el("button", null, tab.label);
    b.type = "button";
    b.setAttribute("role", "tab");
    b.setAttribute("aria-selected", String(tab.key === draftTab));
    b.addEventListener("click", () => {
      drafts[draftTab] = draftText.value;  // 編集した内容を残す
      draftTab = tab.key;
      renderDraftTabs(s);
    });
    draftTabs.appendChild(b);
  });
  draftText.value = drafts[draftTab] || "";
  $("draftNote").textContent = draftTab === "forward"
    ? "社内向けの転送文です。担当部署へそのまま転送できます"
    : "お客様へ送る文面です。自動では送信されません。内容を確認してから使ってください";
  $("btnCopy").textContent = "コピー";
}

$("btnCopy").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(draftText.value);
    $("btnCopy").textContent = "コピーしました";
  } catch (_) {
    draftText.select();
    $("btnCopy").textContent = "選択しました（Cmd+C でコピー）";
  }
});

// ── Apply suggestion ────────────────────────────────────────────────────────
$("btnApplySuggestion").addEventListener("click", async () => {
  const s = currentSuggestion, t = currentTicket;
  if (!s || !t) return;
  const result = $("applyResult");
  result.textContent = "適用中";
  const payload = { version: t.version };
  ["category", "priority", "handling_type", "assigned_team", "faq_id"].forEach(k => { if (s[k]) payload[k] = s[k]; });
  try {
    const updated = await apiFetch("/tickets/" + t.ticket_id, { method: "PATCH", body: JSON.stringify(payload) });
    tickets = tickets.map(x => (x.ticket_id === updated.ticket_id ? updated : x));
    currentTicket = updated;
    renderHeader(updated);
    renderList();
    $("btnApplySuggestion").disabled = true;
    $("btnApplySuggestion").textContent = "適用済み";
    result.textContent = "";
  } catch (e) {
    result.textContent = "適用できませんでした: " + e.message;
  }
});

// ── Inquiry form ───────────────────────────────────────────────────────────
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const ORDER_RE = /^[A-Z0-9-]{1,40}$/;

async function loadInquiryTypes() {
  const box = $("inquiryTypes");
  box.textContent = "";
  try {
    const data = await apiFetch("/masters/inquiry-types");
    data.items.forEach(item => {
      const label = el("label");
      const radio = el("input");
      radio.type = "radio";
      radio.name = "inquiryType";
      radio.value = item.inquiry_type_name;
      label.append(radio, document.createTextNode(item.inquiry_type_name));
      box.appendChild(label);
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
    const v = field.querySelector("input,textarea").value.trim();
    if (type === "order") ok = v === "" || ORDER_RE.test(v);
    else {
      ok = v.length > 0;
      if (ok && type === "email") ok = EMAIL_RE.test(v);
    }
  }
  field.classList.toggle("invalid", !ok);
  return ok;
}

$("btnNewInquiry").addEventListener("click", () => {
  clearError();
  currentTicket = null;
  ticketList.querySelectorAll(".ticket-item").forEach(b => b.classList.remove("active"));
  noSelection.classList.add("hidden");
  ticketDetail.classList.add("hidden");
  formInquiry.reset();
  formInquiry.classList.remove("hidden");
  $("inquiryDone").classList.add("hidden");
  formInquiry.querySelectorAll(".invalid").forEach(f => f.classList.remove("invalid"));
  inquiryForm.classList.remove("hidden");
});

formInquiry.addEventListener("submit", async e => {
  e.preventDefault();
  clearError();
  const fields = [...formInquiry.querySelectorAll(".field[data-req], .field[data-type=order]")];
  const results = fields.map(checkField);
  if (results.includes(false)) {
    fields[results.indexOf(false)].scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }
  // 受付番号・作成日時・ステータスはBackendが決定する。Browserからは送らない
  const payload = {
    customer_name: $("fName").value.trim(),
    customer_email: $("fEmail").value.trim(),
    order_number: $("fOrder").value.trim() || null,
    product_name: $("fProduct").value.trim() || null,
    inquiry_type: formInquiry.querySelector("input[name=inquiryType]:checked").value,
    description: $("fBody").value.trim(),
    has_attachment: $("fPhoto").files.length > 0,
  };
  const btn = $("btnSubmitInquiry");
  btn.disabled = true;
  try {
    const ticket = await apiFetch("/tickets", { method: "POST", body: JSON.stringify(payload) });
    $("doneTicketId").textContent = ticket.ticket_id;
    formInquiry.classList.add("hidden");
    $("inquiryDone").classList.remove("hidden");
    loadTickets();
  } catch (err) {
    showError("送信に失敗しました: " + err.message);
  } finally {
    btn.disabled = false;
  }
});

// ── Init ───────────────────────────────────────────────────────────────────
loadProvider();
loadTickets();
loadInquiryTypes();
