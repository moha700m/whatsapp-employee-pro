"use strict";
/* ---------- helpers ---------- */
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
async function api(method, params = {}) {
  const r = await fetch("/api/" + method, {method: "POST", headers: {"Content-Type": "application/json", "X-Token": window.API_TOKEN}, body: JSON.stringify(params)});
  const j = await r.json();
  if (!j.ok) throw new Error(j.error || "خطأ");
  return j.data;
}
async function safe(fn, okMsg) { try { const r = await fn(); if (okMsg) toast(okMsg, "ok"); return r; } catch (e) { toast(e.message, "err"); throw e; } }
function toast(msg, kind = "") { const t = document.createElement("div"); t.className = "toast " + kind; t.textContent = msg; $("#toasts").appendChild(t); setTimeout(() => t.remove(), 3500); }
function modal(title, html, onMount) { $("#modalTitle").textContent = title; $("#modalBody").innerHTML = html; $("#modal").classList.remove("hidden"); onMount && onMount($("#modalBody")); }
function closeModal() { $("#modal").classList.add("hidden"); $("#modal .modal-card").classList.remove("wide"); }
$("#modalClose").onclick = closeModal; $("#modal").onclick = e => { if (e.target.id === "modal") closeModal(); };
function confirmBox(msg) { return window.confirm(msg); }
const pill = (c) => c ? `<span class="pill ${esc(String(c).replace(/ /g, "-"))}">${esc(META.class_ar?.[c] || c)}</span>` : "";
function table(cols, rows, opts = {}) {
  if (!rows.length) return `<div class="empty">${opts.empty || "ما فيه شي للحين"}</div>`;
  return `<div class="table-wrap"><table><thead><tr>${cols.map(c => `<th>${c[1]}</th>`).join("")}</tr></thead><tbody>${
    rows.map(r => `<tr data-id="${esc(r.id)}">${cols.map(c => `<td>${c[2] ? c[2](r) : esc(r[c[0]])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
function selectable(root, cb) { root.querySelectorAll("tbody tr").forEach(tr => tr.onclick = () => { root.querySelectorAll("tr.sel").forEach(x => x.classList.remove("sel")); tr.classList.add("sel"); cb && cb(tr.dataset.id); }); }

/* ---------- icons (inline SVG, stroke) ---------- */
const P = {
  flow: '<path d="M4 6h6v4H4zM14 14h6v4h-6zM7 10v4a2 2 0 0 0 2 2h5M14 6h6v4h-6M17 10v4"/>',
  home: '<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  chat: '<path d="M21 12a8 8 0 0 1-11.8 7L3 20l1.1-5.2A8 8 0 1 1 21 12z"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14.5a6.5 6.5 0 0 1 3.5 5.5"/>',
  bot: '<rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 8V4M9 13h.01M15 13h.01M9 17h6"/>',
  funnel: '<path d="M3 4h18l-7 8v6l-4 2v-8z"/>',
  mega: '<path d="M3 11v2a1 1 0 0 0 1 1h3l5 4V6L7 10H4a1 1 0 0 0-1 1zM16 8a5 5 0 0 1 0 8"/>',
  bell: '<path d="M6 16V11a6 6 0 1 1 12 0v5l2 2H4zM10 21h4"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  play: '<path d="M7 4l13 8-13 8z"/>', stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
  power: '<path d="M12 3v9M6.3 6.3a8 8 0 1 0 11.4 0"/>', wa: '<path d="M21 12a8 8 0 0 1-11.8 7L3 20l1.1-5.2A8 8 0 1 1 21 12z"/><path d="M9 9.5c0 3 2.5 5.5 5.5 5.5l1-1.5-2-1-1 .8a4 4 0 0 1-1.8-1.8l.8-1-1-2z"/>',
  qr: '<path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h2v2h-2zM18 14h2v2h-2zM14 18h2v2h-2zM18 18h2v2h-2z"/>',
  check: '<path d="M5 12l5 5L20 7"/>', moon: '<path d="M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z"/>', sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>', edit: '<path d="M4 20h4L19 9l-4-4L4 16zM14 6l4 4"/>', trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  up: '<path d="M12 19V5M5 12l7-7 7 7"/>', down: '<path d="M12 5v14M5 12l7 7 7-7"/>', flask: '<path d="M9 3h6M10 3v6L4 19a1 1 0 0 0 .9 2h14.2a1 1 0 0 0 .9-2L14 9V3"/>',
  download: '<path d="M12 4v12M6 10l6 6 6-6M4 20h16"/>', upload: '<path d="M12 20V8M6 14l6-6 6 6M4 4h16"/>', reset: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5"/>',
  save: '<path d="M5 3h11l3 3v15H5zM8 3v6h8M8 21v-7h8v7"/>', copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-5-5"/>', alert: '<path d="M12 3l10 18H2zM12 10v5M12 18h.01"/>', zap: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
};
const ic = (n, c = "") => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="${c}">${P[n] || ""}</svg>`;

/* ---------- navigation ---------- */
const PAGES = [["overview", "الرئيسية", "home"], ["inbox", "المحادثات", "chat"], ["orders", "الطلبات", "list"], ["settings", "الإعدادات", "gear"],
  ["workflow", "سير عمل البوت", "flow"], ["brain", "عقل المحل والأسعار", "bot"], ["crm", "العملاء", "users"], ["ai", "الموظف الذكي", "bot"],
  ["pipeline", "مسار المبيعات", "funnel"], ["advisor", "المستشار التسويقي", "zap"], ["campaigns", "الحملات", "mega"], ["followups", "المتابعات", "bell"],
  ["analytics", "الأرقام", "chart"], ["reports", "تقارير الأداء", "chart"], ["pro", "النسخ والأمان", "save"], ["logs", "السجل", "list"]];
const MAIN = 4;
let META = {}, CURRENT = "overview", STATUS = {};
function renderNav() {
  const adv = localStorage.adv === "1" || PAGES.findIndex(p => p[0] === CURRENT) >= MAIN;
  const link = ([k, t, i], big) => `<a data-p="${k}" class="${big ? "main " : ""}${k === CURRENT ? "active" : ""}">${ic(i)}<span>${t}</span>${k === "inbox" && STATUS.pending ? `<span class="badge q" title="تنتظر موافقتك">${STATUS.pending}</span>` : ""}${k === "inbox" && STATUS.needs ? `<span class="badge" title="يحتاجونك">${STATUS.needs}</span>` : ""}</a>`;
  $("#nav").innerHTML = PAGES.slice(0, MAIN).map(p => link(p, true)).join("") +
    `<button class="adv-toggle" id="advT" aria-expanded="${adv}">${adv ? "▾" : "◂"} متقدم</button>` +
    (adv ? `<div class="adv">${PAGES.slice(MAIN).map(p => link(p, false)).join("")}</div>` : "");
  $("#nav").querySelectorAll("a").forEach(a => a.onclick = () => go(a.dataset.p));
  $("#advT").onclick = () => { localStorage.adv = adv ? "0" : "1"; renderNav(); };
}
async function go(p) {
  CURRENT = p; location.hash = p; renderNav();
  const el = $("#page"); el.innerHTML = '<div class="empty">لحظة…</div>';
  try { await PAGE[p](el); } catch (e) { el.innerHTML = `<div class="card"><h3>ما فتحت الصفحة، جرب مرة ثانية</h3><p class="muted">${esc(e.message)}</p></div>`; }
}
const head = (t, s) => `<h1>${t}</h1><p class="sub">${s || ""}</p>`;

/* ---------- status bar (polled) ---------- */
function setChip(id, cls, text) { const c = $(id); c.className = "chip " + cls; c.querySelector("b").textContent = text; }
async function pollStatus() {
  try {
    STATUS = await api("status");
    setChip("#chipWa", {connected: "ok", qr: "warn", loading: "warn", conflict: "warn", phone_offline: "warn", disconnected: "bad", missing_deps: "bad", error: "bad"}[STATUS.wa], STATUS.wa_ar + (STATUS.wa === "connected" && STATUS.profile ? " · " + STATUS.profile : ""));
    setChip("#chipGpt", {ready: "ok", unused: "", unknown: "", login: "warn", error: "bad"}[STATUS.gpt], STATUS.gpt_ar);
    setChip("#chipEmp", {watching: "ok", replying: "ok", waiting: "warn", stopped: ""}[STATUS.emp], STATUS.emp_ar);
    $("#lastCheck").textContent = STATUS.last_check || "—";
    const k = $("#killBtn"); k.classList.toggle("on", STATUS.kill);
    k.innerHTML = STATUS.kill ? ic("play") + " إعادة التشغيل" : ic("power") + " وقّف كل شي";
    $("#banner").innerHTML = (STATUS.kill ? '<div class="warnbar">⛔ زر الإيقاف الفوري مفعّل — الموظف متوقف تماماً ولن يقرأ أو يرسل أي شيء.</div>' : "") + depsBanner();
    const fb = $("#fixBtn"); if (fb) fb.onclick = fixDeps;
    CONN_HOOKS.forEach(f => f(STATUS));
    notifyDrafts(STATUS.pending || 0); QUEUE_HOOKS.forEach(f => f(STATUS));
    $("#startBtn").disabled = STATUS.emp === "watching" || STATUS.emp === "replying" || STATUS.kill;
    $("#stopBtn").disabled = STATUS.emp === "stopped";
    document.body.classList.toggle("wa-ok", STATUS.wa === "connected"); document.body.classList.toggle("emp-on", STATUS.emp === "watching" || STATUS.emp === "replying");
    renderNav();
    if (CURRENT === "ai" && LIVE) LIVE();
  } catch (e) { setChip("#chipEmp", "bad", "التطبيق غير متصل"); }
}
let LIVE = null;
const CONN_HOOKS = new Set(), QUEUE_HOOKS = new Set();

/* ---------- approval queue: every reply waits for the user's click ---------- */
let LAST_PENDING = null;
const EDITS = {};                      // id -> text the user is editing (survives refreshes)
function beep() { try { const a = new AudioContext(), o = a.createOscillator(), g = a.createGain(); o.frequency.value = 880; g.gain.value = .06; o.connect(g); g.connect(a.destination); o.start(); o.stop(a.currentTime + .15); } catch (e) {} }
function notifyDrafts(n) {
  document.title = (n ? `(${n}) ` : "") + "موظف واتساب الذكي";
  if (LAST_PENDING !== null && n > LAST_PENDING) {
    if (localStorage.wae_sound !== "0") beep();
    if (localStorage.wae_notify === "1" && "Notification" in window && Notification.permission === "granted") new Notification("رد جديد بانتظار موافقتك", {body: `عندك ${n} رد جاهز`});
    toast(`📝 رد جديد بانتظار موافقتك (${n})`);
  }
  LAST_PENDING = n;
}
function draftCard(d) {
  const txt = EDITS[d.id] ?? d.reply ?? "", msgs = (d.incoming || "").split("\n").filter(Boolean).slice(-4);
  const sc = d.score ? `<span class="score ${d.score.band}" title="نقاط العميل ${d.score.value}/100">${d.score.band_ar} · ${d.score.value}</span>` : "";
  return `<article class="qcard ${d.kind === "holding" ? "hold" : ""}" data-id="${d.id}">
    <header><div class="av">${esc((d.chat || "?").trim().slice(0, 1))}</div><div class="who"><b>${esc(d.chat)}</b><span class="note num">${esc(d.phone || "")} ${esc(d.updated_at || d.created_at || "")}</span></div>
      <span class="sp"></span>${d.classification ? pill(d.classification) : ""}${sc}${d.kind === "holding" ? '<span class="pill Complaint">يحتاجك</span>' : ""}</header>
    <div class="bubbles">${msgs.map(m => `<p class="in">${esc(m)}</p>`).join("") || '<p class="in muted">—</p>'}</div>
    <label class="f"><span>${d.kind === "followup" ? "رسالة متابعة من المستشار" : "الرد المقترح"} ${d.provider === "chatgpt_web" ? "(ChatGPT)" : ""} — عدّله براحتك قبل الإرسال</span><textarea rows="3" data-edit>${esc(txt)}</textarea></label>
    <div class="chips-q">${(QUICK || []).map((q, i) => `<button class="qchip" data-q="${i}" title="${esc(q)}">${esc(q.slice(0, 28))}</button>`).join("")}</div>
    ${d.error ? `<p class="qerr">${ic("alert")} ${esc(d.error)}</p>` : ""}
    <footer><button class="btn primary" data-a="send">✅ إرسال</button><button class="btn outline" data-a="edit">✏️ تعديل</button>
      <button class="btn outline" data-a="regen">🔄 رد ثاني</button><span class="sp"></span><button class="btn danger-outline" data-a="ignore">❌ تجاهل</button></footer></article>`;
}
let QUICK = null;
function mountQueue(el, opts = {}) {
  let sig = null;
  const load = async (force) => {
    if (!document.body.contains(el)) { QUEUE_HOOKS.delete(hook); return; }
    if (el.contains(document.activeElement) && !force) return;            // never redraw under the user's cursor
    if (!QUICK) QUICK = await api("quick_replies");
    const ds = await api("drafts"), ns = ds.map(d => d.id + ":" + d.updated_at).join(",");
    if (ns === sig && !force) return; sig = ns;
    el.innerHTML = `<div class="qhead"><h3>${ic("bell")} بانتظار موافقتك <span class="badge q num">${ds.length}</span></h3><span class="sp"></span>
      <span class="note">ما ينرسل أي رد إلا بضغطتك على ✅ إرسال</span></div>` +
      (ds.length ? `<div class="qlist">${ds.slice(0, opts.limit || 50).map(draftCard).join("")}</div>` :
       `<div class="empty qempty">${ic("check")}<div>ما فيه ردود تنتظرك 👌<br><span class="note">${STATUS.emp === "stopped" ? "شغّل الموظف عشان يقرأ الرسائل الجديدة ويجهّز لك الردود" : "أول ما توصل رسالة جديدة بيجهّز لك رد هنا"}</span></div></div>`);
    el.querySelectorAll(".qcard").forEach(card => {
      const id = +card.dataset.id, ta = card.querySelector("[data-edit]");
      ta.oninput = () => EDITS[id] = ta.value;
      card.querySelectorAll("[data-q]").forEach(b => b.onclick = () => { ta.value += (ta.value ? " " : "") + QUICK[+b.dataset.q]; EDITS[id] = ta.value; ta.focus(); });
      card.querySelectorAll("[data-a]").forEach(b => b.onclick = async () => {
        const a = b.dataset.a;
        if (a === "edit") { ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); return; }
        card.classList.add("busy"); b.disabled = true;
        try {
          if (a === "send") { await api("draft_send", {id, text: ta.value}); delete EDITS[id]; toast("✅ انرسل الرد", "ok"); card.classList.add("gone"); }
          if (a === "ignore") { await api("draft_ignore", {id}); delete EDITS[id]; toast("أبشر، تجاهلته"); card.classList.add("gone"); }
          if (a === "regen") { const r = await api("draft_regenerate", {id}); ta.value = r.reply; delete EDITS[id]; toast("🔄 جهّزت رد ثاني"); }
        } catch (e) { toast(e.message, "err"); }
        card.classList.remove("busy"); b.disabled = false;
        if (a !== "regen") setTimeout(() => { load(true); pollStatus(); }, 250);
      });
    });
  };
  const hook = () => load(false);
  QUEUE_HOOKS.add(hook); return load(true);
}

/* ---------- dependencies ---------- */
function depsBanner() {
  const m = STATUS.missing || [];
  if (!m.length && STATUS.fix !== "restart") return "";
  const st = STATUS.fix;
  const msg = st === "running" ? "لحظة، قاعد أصلح… يثبت المكتبات الناقصة (دقيقة أو دقيقتين)" : st === "restart" || (st === "done" && m.length) ? "✅ تم ✅ — اقفل البرنامج وافتحه من جديد" :
    st === "failed" ? "❌ فشل الإصلاح التلقائي — تأكد من الإنترنت وجرب مرة ثانية، أو شغّل START.bat" : `بعض مكونات البرنامج ناقصة (${m.join("، ")}) — بدونها ما يقدر يفتح واتساب.`;
  return `<div class="depbar">${ic("alert")}<span>${msg}</span>${st === "running" ? '<span class="spin"></span>' : (st === "restart" ? "" : `<button class="btn small primary" id="fixBtn">${ic("zap")} إصلاح تلقائي</button>`)}</div>`;
}
async function fixDeps() { await safe(() => api("deps_fix"), "بدأ الإصلاح التلقائي"); }

/* ---------- WhatsApp connection view (modal, wizard, AI page) ---------- */
const STEPS = ["افتح واتساب في جوالك", "الإعدادات", "الأجهزة المرتبطة", "ربط جهاز", "امسح الرمز"];
function connView(s, opts = {}) {
  const steps = `<ol class="qr-steps">${STEPS.map(x => `<li>${x}</li>`).join("")}</ol>`;
  const shell = (cls, icon, title, body, extra = "") => `<div class="conn ${cls}"><div class="conn-visual">${icon}</div><div class="conn-text"><h2>${title}</h2>${body}${extra}</div></div>`;
  switch (s.wa) {
    case "qr": return `<div class="conn qr"><div class="qr-frame">${s.qr ? `<img src="${s.qr}" alt="رمز QR لواتساب">` : '<div class="qr-wait"><span class="spin big"></span></div>'}<span class="scan-line"></span></div>
      <div class="conn-text"><h2>امسح الرمز من جوالك</h2>${steps}<p class="note">الرمز يتجدد تلقائياً كل كم ثانية${s.qr_time ? " · آخر تحديث " + s.qr_time : ""}. ما نحتاج كلمة مرور ولا نحفظ شي خارج جهازك.</p></div></div>`;
    case "connected": return shell("ok", `<div class="okmark">${ic("check")}</div>`, "تم الربط ✅", `<p>${s.profile ? "الحساب: <b>" + esc(s.profile) + "</b>" : "واتساب متصل وقائمة المحادثات ظاهرة."}</p><p class="note">نافذة Chrome ${s.show_browser ? "ظاهرة" : "تشتغل بالخلفية"}، وتقدر تقفل هالنافذة.</p>`);
    case "conflict": return shell("warn", `<div class="okmark warn">${ic("alert")}</div>`, "واتساب مفتوح في مكان ثاني", "<p>واتساب ويب ما يشتغل إلا في نافذة وحدة. اضغط الزر عشان يشتغل هنا.</p>", `<button class="btn primary" data-act="use_here">استخدام هنا</button>`);
    case "phone_offline": return shell("warn", `<div class="okmark warn">${ic("alert")}</div>`, "جوالك مو متصل", "<p>تأكد إن جوالك متصل بالإنترنت وواتساب شغال فيه. الرسائل بتوصل أول ما يرجع الاتصال.</p>");
    case "missing_deps": return shell("bad", `<div class="okmark bad">${ic("alert")}</div>`, "مكونات البرنامج ناقصة", `<p>مكتبة <b>Playwright</b> اللي يفتح فيها البرنامج واتساب مو مثبتة عندك.</p>`, `<button class="btn primary" data-act="fix">${ic("zap")} إصلاح تلقائي</button>`);
    case "error": return shell("bad", `<div class="okmark bad">${ic("alert")}</div>`, "ما قدرت أفتح Chrome", `<p class="note">${esc(s.error || "")}</p><p>تأكد إن Google Chrome مثبت، وجرب مرة ثانية.</p>`, `<button class="btn primary" data-act="open">حاول مرة ثانية</button>`);
    case "loading": return shell("wait", '<span class="spin big"></span>', "لحظة، قاعد أفتح واتساب…", "<p>لحظات ويظهر رمز QR هنا.</p>");
    default: return shell("idle", `<div class="okmark idle">${ic("wa")}</div>`, "اربط واتساب", "<p>بيفتح البرنامج واتساب ويب في نافذة Chrome خاصة فيه، ويعرض لك رمز QR هنا داخل البرنامج.</p>", `<button class="btn primary" data-act="open">${ic("wa")} ابدأ الربط</button>`);
  }
}
function bindConn(root) {
  root.querySelectorAll("[data-act]").forEach(b => b.onclick = () => ({open: () => safe(() => api("wa_open")), use_here: () => safe(() => api("wa_use_here")), fix: fixDeps})[b.dataset.act]());
}
function mountConn(el, opts = {}) {
  let last = "", closeTimer = null;
  const draw = s => { if (!document.body.contains(el)) { CONN_HOOKS.delete(draw); return; }
    const sig = s.wa + "|" + s.qr_time + "|" + s.profile + "|" + s.error;
    if (sig === last) return; last = sig; el.innerHTML = connView(s, opts); bindConn(el);
    if (s.wa === "connected" && opts.onConnected && !closeTimer) closeTimer = setTimeout(opts.onConnected, 2200); };
  CONN_HOOKS.add(draw); draw(STATUS);
}
async function openConnect() {
  modal("ربط واتساب", '<div id="connHost"></div>', b => { b.closest(".modal-card").classList.add("wide"); mountConn($("#connHost", b), {onConnected: () => { closeModal(); toast("واتساب متصل ✅", "ok"); }}); });
  if (STATUS.wa !== "connected" && STATUS.wa !== "qr") { try { await api("wa_open"); } catch (e) { toast(e.message, "err"); } }
  pollStatus();
}

/* ---------- pages ---------- */
const PAGE = {};
PAGE.advisor = async el => {
  const a = await api("mk_analysis");
  const bars = (list, empty) => list.length ? `<div class="bars">${list.map(([k, v]) => `<div class="bar"><span>${esc(k)}</span><i style="width:${Math.max(8, 100 * v / list[0][1])}%"></i><b class="num">${v}</b></div>`).join("")}</div>` : `<div class="empty">${empty}</div>`;
  const maxh = Math.max(1, ...a.hours);
  const cust = (r, extra) => `<div class="mrow"><b>${esc(r.name || r.chat)}</b>${r.score ? `<span class="score ${esc(r.score.band)}">${esc(r.score.band_ar)}</span>` : ""}<span class="sp"></span><span class="note">${extra}</span></div>`;
  el.innerHTML = head("المستشار التسويقي", "أفكار ونصايح من بيانات محلك — كل شي محلي على جهازك، وما ينرسل شي إلا بموافقتك") + `
  <div class="card advisor-hero"><h3>${ic("zap")} وش أسوي الحين؟</h3><ul class="tips">${a.tips.map(t => `<li>${esc(t)}</li>`).join("")}</ul>
    <span class="note">حللت ${a.messages} رسالة من عملائك</span></div>
  <div class="card mt ask"><h3>💬 اطلب من الموظف</h3><div class="row"><input id="askq" placeholder="مثال: اكتب لي كابشن ليوم الأم، أو وش أسوي عرض الأسبوع؟"><button class="btn primary" id="askb">اسأل</button></div>
    <div class="row mt">${["اكتب لي كابشن انستقرام", "اقترح عروض للمناسبة الجاية", "مين أتابع من العملاء؟"].map(q => `<button class="qchip" data-ask="${esc(q)}">${esc(q)}</button>`).join("")}</div><div id="askr" class="mt"></div></div>
  <div class="grid g3 mt">
    <div class="card"><h3>🌹 أكثر شي ينسأل عنه</h3>${bars(a.products, "ما فيه بيانات كفاية للحين")}</div>
    <div class="card"><h3>🎉 المناسبات اللي يذكرونها</h3>${bars(a.occasions, "ما أحد ذكر مناسبة للحين")}</div>
    <div class="card"><h3>🤔 وش يوقفهم عن الشراء</h3>${bars(a.objections, "ما فيه اعتراضات — ممتاز 👌")}</div></div>
  <div class="grid g2 mt">
    <div class="card"><h3>⏰ أوقات الذروة</h3><div class="hours">${a.hours.map((v, h) => `<div title="${h}:00 — ${v} رسالة"><i style="height:${100 * v / maxh}%"></i><span>${h % 3 ? "" : h}</span></div>`).join("")}</div></div>
    <div class="card"><h3>🔥 جاهزين يشترون</h3>${a.hot.map(r => cust(r, esc(r.need || ""))).join("") || '<div class="empty">ما فيه أحد للحين</div>'}</div></div>
  <div class="grid g2 mt">
    <div class="card"><h3>⏳ ينتظرون ردك</h3>${a.unanswered.map(u => cust(u, `${esc((u.last || "").slice(0, 40))} · من ${u.hours} ساعة`)).join("") || '<div class="empty">ما أحد ينتظر 👌</div>'}
      ${a.unanswered.length ? '<button class="btn small outline mt" data-go="inbox">روح لـ«بانتظار موافقتك»</button>' : ""}</div>
    <div class="card"><h3>💤 كانوا مهتمين وسكتوا</h3>${a.lost.map(r => cust(r, `من ${r.days} يوم`)).join("") || '<div class="empty">ما فيه أحد ضايع 👌</div>'}</div></div>
  <div class="card mt"><h3>📅 تقويم المناسبات السعودية</h3><p class="note">كابشن وعرض جاهز لكل مناسبة — انسخه وانشره بنفسك. (المناسبات الهجرية تقريبية حسب الرؤية)</p>
    <div class="occ">${a.occasions_cal.map((o, i) => `<div class="occ-card"><div class="occ-h"><b>${esc(o.name)}</b><span class="pill num">${esc(o.date)}${o.approx ? " تقريباً" : ""}</span></div>
      <div class="note">بعد ${o.days} يوم · ابدأ الحملة ${esc(o.start)}</div><p class="cap">${esc(o.caption)}</p><p class="offer">🎁 ${esc(o.offer)}</p>
      <button class="btn small outline" data-copy="${i}">${ic("copy")} انسخ</button></div>`).join("")}</div></div>
  <div class="card mt"><div class="row"><h3 style="margin:0">📝 اقتراحات المتابعة</h3><span class="sp"></span><span class="note">كل رسالة تروح لـ«بانتظار موافقتك» — ما ينرسل شي إلا بضغطتك</span></div><div id="fups" class="mt"></div></div>`;
  el.querySelectorAll("[data-go]").forEach(b => b.onclick = () => go(b.dataset.go));
  el.querySelectorAll("[data-copy]").forEach(b => b.onclick = () => { const o = a.occasions_cal[+b.dataset.copy]; navigator.clipboard?.writeText(o.caption + "\n" + o.offer); toast("تم، نسخته 📋", "ok"); });
  const ask = async q => { if (!q.trim()) return toast("اكتب سؤالك أول", "err"); $("#askr").innerHTML = '<span class="spin"></span> لحظة، قاعد أفكر…';
    try { const r = await api("mk_ask", {question: q}); $("#askr").innerHTML = `<div class="answer">${esc(r.answer).replace(/\n/g, "<br>")}</div><span class="note">${r.provider === "chatgpt_web" ? "من ChatGPT" : "من القوالب المحلية"}</span>`; }
    catch (e) { $("#askr").innerHTML = ""; toast(e.message, "err"); } };
  $("#askb").onclick = () => ask($("#askq").value); $("#askq").onkeydown = e => e.key === "Enter" && ask($("#askq").value);
  el.querySelectorAll("[data-ask]").forEach(b => b.onclick = () => { $("#askq").value = b.dataset.ask; ask(b.dataset.ask); });
  const fups = await api("mk_followups");
  $("#fups").innerHTML = fups.length ? `<div class="qlist">${fups.map((f, i) => `<article class="qcard"><header><div class="av">${esc((f.name || "?").slice(0, 1))}</div><div class="who"><b>${esc(f.name)}</b><span class="note">${esc(f.why)}</span></div><span class="sp"></span>${f.score ? `<span class="score ${esc(f.score.band)}">${esc(f.score.band_ar)}</span>` : ""}</header>
    <textarea rows="3" data-f="${i}">${esc(f.text)}</textarea><footer><button class="btn primary" data-fd="${i}">📝 حطها في بانتظار موافقتك</button></footer></article>`).join("")}</div>` : '<div class="empty">ما فيه أحد يحتاج متابعة الحين 👌</div>';
  $("#fups").querySelectorAll("[data-fd]").forEach(b => b.onclick = async () => { const i = +b.dataset.fd;
    try { await api("mk_followup_draft", {customer_id: fups[i].customer_id, text: $(`[data-f="${i}"]`).value}); toast("أبشر، حطيتها في «بانتظار موافقتك» 📝", "ok"); b.disabled = true; b.textContent = "✓ تنتظر موافقتك"; pollStatus(); }
    catch (e) { toast(e.message, "err"); } });
};
PAGE.overview = async el => {
  const d = await api("overview"), s = d.stats, wa = STATUS.wa, run = STATUS.emp === "watching" || STATUS.emp === "replying";
  const pend = STATUS.pending || 0, needs = STATUS.needs || 0;
  let tone, title, sub, btn, act;
  if (STATUS.kill) { tone = "bad"; title = "الموظف موقّف بالكامل"; sub = "ما يقرأ ولا يرسل شي"; btn = "رجّع التشغيل"; act = async () => { await api("kill_toggle"); await pollStatus(); go("overview"); }; }
  else if (wa !== "connected") { tone = "warn"; title = "واتساب مو مربوط"; sub = "اضغط الزر وامسح الرمز من جوال المحل"; btn = "اربط واتساب"; act = openConnect; }
  else if (!run) { tone = "warn"; title = "واتساب مربوط، والموظف واقف"; sub = "شغّله عشان يقرأ الرسائل ويجهز الردود"; btn = "شغّل الموظف"; act = () => safe(() => api("emp_start"), "اشتغل الموظف ✅").then(() => setTimeout(() => go("overview"), 600)); }
  else if (pend) { tone = "ok"; title = `${pend} رد ينتظر موافقتك`; sub = "راجعها وأرسلها بضغطة"; btn = "افتح المحادثات"; act = () => go("inbox"); }
  else { tone = "ok"; title = "كل شي تمام، الموظف شغال"; sub = "أول ما توصل رسالة بيجهز لك الرد هنا"; btn = "شوف المحادثات"; act = () => go("inbox"); }
  el.innerHTML = `<div class="hero ${tone}"><div class="dot"></div><div class="hero-t"><h1>${title}</h1><p>${sub}</p></div>
    <button class="btn primary xl" id="heroBtn">${btn}</button></div>
    <div class="tiles">
      <a class="tile" data-go="inbox"><b class="num">${pend}</b><span>ردود تنتظر موافقتك</span></a>
      <a class="tile ${needs ? "alert" : ""}" data-go="ai"><b class="num">${needs}</b><span>عملاء يحتاجونك</span></a>
      <a class="tile" data-go="orders"><b class="num">${s.sales ?? 0}</b><span>طلبات مسجلة</span></a>
      <a class="tile" data-go="crm"><b class="num">${s.total}</b><span>كل العملاء</span></a></div>
    <div class="card mt"><h3>آخر المحادثات</h3>${table([["name", "العميل"], ["classification", "الحالة", r => pill(r.classification)], ["summary", "وش يبي", r => esc((r.summary || "").slice(0, 80))]], d.recent, {empty: "ما فيه محادثات للحين"})}</div>`;
  $("#heroBtn").onclick = act;
  el.querySelectorAll("[data-go]").forEach(t => t.onclick = () => go(t.dataset.go));
};
function howItWorks() {
  return `<div class="card"><h3>${ic("zap")} كيف يشتغل الموظف؟</h3><ol class="steps">
  <li>يفتح نافذة Chrome خاصة فيه على WhatsApp Web (منفصلة عن متصفحك).</li>
  <li>تمسح رمز QR مرة وحدة من جوالك، وبعدها يتذكر الجلسة.</li>
  <li>يعرف إنك متصل لما تظهر قائمة المحادثات، ولو ظهر رمز QR يعرف إنه ينتظر المسح.</li>
  <li>كل كم ثانية يدوّر على المحادثات اللي عليها علامة «غير مقروءة».</li>
  <li>يفتح المحادثة ويقرأ الرسائل الظاهرة على الشاشة، مثل ما تقرأها أنت.</li>
  <li>يقرر الرد من قواعد «سير عمل البوت» أو من الذكاء الاصطناعي، وما يخترع أسعاراً.</li>
  <li>يجهّز الرد ويحطه في «بانتظار موافقتك» — ما يرسل شي أبداً بدون ضغطتك.</li>
  <li>تعدّل الرد أو تطلب رد ثاني، وتضغط ✅ إرسال، فيكتبه في واتساب ويرسله ويسجّل كل شي.</li></ol></div>`;
}
PAGE.inbox = async el => {
  const d = await api("inbox");
  const tone = o => ({drafted: "Follow-up", holding_drafted: "Complaint", replied: "Existing-Customer", rule_replied: "Existing-Customer", holding_sent: "Complaint", flagged_only: "Complaint", error: "Complaint", waiting: "Follow-up"}[o] || "");
  el.innerHTML = head("صندوق واتساب", "الردود الجاهزة تنتظر موافقتك، والمحادثات اللي يشوفها الموظف الحين") + `<section class="card queue" id="queue"></section><div class="card mt"><div class="row"><h3 style="margin:0">${ic("wa")} المحادثات اللي ما انقرت (مباشر)</h3><span class="sp"></span>
    <span class="note">${STATUS.wa === "connected" ? "يتحدث تلقائياً" : "اربط واتساب عشان تظهر المحادثات"}</span><button class="btn small outline" id="rf">تحديث</button></div><div class="mt">${
    table([["name", "المحادثة", r => `<b>${esc(r.name)}</b>${r.group ? ' <span class="pill">مجموعة</span>' : ""}`], ["last", "آخر رسالة", r => esc((r.last || "").slice(0, 80))], ["unread", "غير مقروءة", r => `<span class="pill num">${r.unread}</span>`],
      ["outcome_ar", "وش سوّى الموظف", r => `<span class="pill ${tone(r.outcome)}">${esc(r.outcome_ar)}</span>`], ["t", "الوقت", r => `<span class="num">${esc(r.t)}</span>`]], d.live, {empty: STATUS.wa === "connected" ? "ما فيه محادثات غير مقروءة حالياً 👌" : "واتساب مو متصل — اضغط «فتح واتساب»"})}</div></div>
    <div class="card mt"><h3>المحادثات المحللة</h3>${table([["name", "العميل"], ["classification", "التصنيف", r => pill(r.classification)],
    ["handoff", "تدخل بشري", r => r.handoff ? '<span class="pill Complaint">نعم</span>' : "—"], ["summary", "الملخص"], ["created_at", "التاريخ"]], d.analyzed)}</div>`;
  await mountQueue($("#queue"));
  $("#rf").onclick = () => go("inbox");
  clearTimeout(window.__inboxT); window.__inboxT = setTimeout(() => CURRENT === "inbox" && !$("#modal:not(.hidden)") && !$("#queue").contains(document.activeElement) && !Object.keys(EDITS).length && go("inbox"), 8000);
};
PAGE.crm = async el => {
  el.innerHTML = head("العملاء CRM", "بيانات عملائك محفوظة على جهازك فقط") + `<div class="card"><div class="row"><div style="flex:1;max-width:340px;position:relative"><input id="q" placeholder="دوّر بالاسم أو الجوال…"></div><span class="sp"></span>
    <button class="btn blue" id="ed">${ic("edit")} تعديل</button><button class="btn outline" id="op">${ic("stop")} إيقاف المتابعة</button>
    <button class="btn outline" id="ord">🧾 الطلبات</button><button class="btn outline" id="csv">⬇️ CSV</button><button class="btn outline" id="vcf">⬇️ جهات اتصال VCF</button><button class="btn outline" id="prt">🖨️ تقرير</button>
    <button class="btn danger-outline" id="dl">${ic("trash")} حذف العميل</button><button class="btn danger" id="da">حذف كل البيانات</button></div><div id="tb" class="mt"></div></div>`;
  let sel = null, rows = [];
  const load = async () => { rows = await api("customers", {q: $("#q").value}); $("#tb").innerHTML = table([["name", "الاسم"], ["phone", "الجوال"], ["classification", "التصنيف", r => pill(r.classification)],
    ["need", "الاحتياج"], ["last_contact", "آخر تواصل"], ["follow_up_date", "المتابعة"], ["notes", "ملاحظات"]], rows); selectable($("#tb"), id => sel = id); };
  $("#q").oninput = load; await load();
  const dl = async (fmt, name, type) => { const t = await api("export_contacts", {fmt}); const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([t], {type})); a.download = name; a.click(); toast("تم، نزّلته ✅", "ok"); };
  $("#csv").onclick = () => dl("csv", "customers.csv", "text/csv"); $("#vcf").onclick = () => dl("vcf", "contacts.vcf", "text/vcard"); $("#prt").onclick = () => window.print();
  $("#ord").onclick = async () => { const c = rows.find(r => String(r.id) === String(sel)); if (!c) return toast("اختار عميل أول");
    const draw = async b => { const os = await api("orders", {customer_id: c.id}), tot = os.filter(o => o.status !== "ملغي").reduce((x, o) => x + (o.amount || 0), 0);
      $("#ol", b).innerHTML = (os.map(o => `<div class="mrow"><b>${esc(o.item)}</b><span class="num">${o.amount || 0} ريال</span><span class="sp"></span><select data-o="${o.id}">${["جديد", "قيد التجهيز", "تم التوصيل", "ملغي"].map(x => `<option ${o.status === x ? "selected" : ""}>${x}</option>`).join("")}</select></div>`).join("") || '<div class="empty">ما فيه طلبات للحين</div>') + `<p class="note">المجموع: <b class="num">${tot}</b> ريال</p>`;
      $("#ol", b).querySelectorAll("[data-o]").forEach(x => x.onchange = () => safe(() => api("order_status", {id: +x.dataset.o, status: x.value}), "تم ✅")); };
    modal("طلبات " + c.name, `<div id="ol"></div><div class="row mt"><input id="oi" placeholder="وش الطلب؟ (باقة جوري…)"><input id="oa" type="number" placeholder="المبلغ" style="max-width:110px"><button class="btn primary" id="oadd">إضافة</button></div>`, b => {
      draw(b); $("#oadd", b).onclick = async () => { await safe(() => api("order_add", {customer_id: c.id, item: $("#oi", b).value, amount: $("#oa", b).value}), "تم، انضاف ✅"); $("#oi", b).value = $("#oa", b).value = ""; draw(b); }; }); };
  $("#dl").onclick = async () => { if (sel && confirmBox("حذف العميل وكل بياناته نهائياً؟")) { await safe(() => api("customer_delete", {id: sel}), "تم، انحذف"); load(); } };
  $("#da").onclick = async () => { if (confirmBox("حذف جميع بيانات العملاء؟ (تؤخذ نسخة احتياطية أولاً)")) { await safe(() => api("customers_delete_all"), "تم"); load(); } };
  $("#op").onclick = async () => { if (sel) await safe(() => api("customer_optout", {id: sel}), "أوقفنا المتابعة والتسويق لهذا العميل"); };
  $("#ed").onclick = () => { const c = rows.find(r => String(r.id) === String(sel)); if (!c) return toast("اختار عميل أول");
    modal("تعديل عميل", ["name:الاسم", "phone:الجوال", "need:الاحتياج", "notes:ملاحظات", "follow_up_date:موعد المتابعة"].map(x => { const [k, t] = x.split(":"); return `<label class="f"><span>${t}</span><input data-k="${k}" value="${esc(c[k])}"></label>`; }).join("") +
      `<label class="f"><span>التصنيف</span><select data-k="classification">${META.classes.map(k => `<option value="${k}" ${k === c.classification ? "selected" : ""}>${META.class_ar[k]}</option>`).join("")}</select></label><div class="row end"><button class="btn primary" id="sv">${ic("save")} حفظ</button></div>`,
      b => $("#sv", b).onclick = async () => { const f = {}; b.querySelectorAll("[data-k]").forEach(i => f[i.dataset.k] = i.value); await safe(() => api("customer_update", {id: c.id, fields: f}), "تم، انحفظ ✅"); closeModal(); load(); }); };
};
PAGE.ai = async el => {
  el.innerHTML = head("الموظف الذكي", "تحكم بالموظف وشوف وش يسوي لحظة بلحظة") + `<div class="grid ai-top"><div class="card conn-card" id="connCard"></div><div class="card emp-card" id="empCard"></div></div>
  <section class="card queue mt" id="queue"></section>
  <div class="grid g4 mt" id="ctr"></div>
  <div class="grid g2 mt"><div class="card"><h3>${ic("zap")} النشاط المباشر</h3><div class="feed" id="feed"></div></div>
  <div class="card"><div class="row"><h3 style="margin:0">${ic("alert")} يحتاجونك</h3><span class="sp"></span><button class="btn small outline" id="nd">${ic("check")} خلصت منه</button></div><div id="needs" class="mt"></div></div></div>
  <div class="grid g2 mt"><div class="card"><h3>آخر الردود المرسلة (بموافقتك)</h3><div id="auto"></div></div>
  <div class="card"><h3>تحليل يدوي (بدون إرسال)</h3><label class="f"><span>اسم العميل (اختياري)</span><input id="cn"></label>
  <label class="f"><span>الصق المحادثة أو استورد ملف تصدير واتساب .txt</span><textarea id="tx" rows="5"></textarea></label>
  <div class="row"><button class="btn primary" id="an">${ic("search")} تحليل</button><label class="btn outline">${ic("upload")} استيراد .txt<input type="file" id="fl" accept=".txt" hidden></label></div><div id="res" class="mt"></div></div></div>`;
  let needSel = null, lastSig = "";
  LIVE = async () => {
    const s = STATUS;
    const running = s.emp === "watching" || s.emp === "replying";
    $("#empCard").innerHTML = `<div class="emp-state ${s.emp}"><span class="pulse"></span><div><div class="t">حالة الموظف</div><div class="v">${esc(s.emp_ar)}</div></div></div>
      <div class="kv mt"><b>طريقة الإرسال</b><span><span class="pill Existing-Customer">بموافقتك فقط</span></span><b>تجهيز الردود</b><span>${s.auto_enabled ? '<span class="pill Existing-Customer">مفعّل</span>' : '<span class="pill">طافي</span> <a class="link" data-go="workflow">فعّله</a>'}</span>
      <b>مزود الردود</b><span>${s.provider === "chatgpt_web" ? "ChatGPT (" + esc(s.gpt_ar) + ")" : "المحلل المحلي"}</span><b>آخر فحص</b><span class="num">${esc(s.last_check || "—")}</span></div>
      <div class="row mt"><button class="btn ${running ? "danger-outline" : "primary"}" id="empToggle" ${s.kill ? "disabled" : ""}>${running ? ic("stop") + " إيقاف الموظف" : ic("play") + " تشغيل الموظف"}</button>
      <button class="btn small outline" id="diagBtn" title="يحفظ تقرير المحددات في data/logs/selectors.txt">🩺 تشخيص واتساب</button>
      <label class="check small">${`<span class="switch"><input type="checkbox" id="showBr" ${s.show_browser ? "checked" : ""}><i></i></span>`} إظهار نافذة Chrome</label></div>`;
    $("#empToggle").onclick = () => running ? safe(() => api("emp_stop"), "أبشر، وقفته") : safe(() => api("emp_start"), "بدأ الموظف");
    $("#diagBtn").onclick = () => safe(() => api("wa_diagnose"), "لحظة، قاعد أفحص… التقرير في data/logs/selectors.txt");
    $("#showBr").onchange = e => safe(() => api("browser_visible", {visible: e.target.checked}));
    $("#empCard").querySelectorAll("[data-go]").forEach(a => a.onclick = () => go(a.dataset.go));
    const c = s.counters; $("#ctr").innerHTML = [["بانتظار موافقتك", s.pending || 0], ["أرسلتها اليوم", s.today], ["ردود جهّزها", c.drafts || 0], ["تخطي/أخطاء", `${c.skipped}/${c.errors}`]]
      .map(([t, v]) => `<div class="card stat"><div><div class="t">${t}</div><div class="v num">${v}</div></div></div>`).join("");
    $("#feed").innerHTML = (s.events || []).map(e => `<div class="${e.level}"><time>${e.t}</time><span>${esc(e.text)}</span></div>`).join("") || '<div class="empty">ما صار شي للحين</div>';
    const sig = s.today + ":" + s.needs;
    if (sig !== lastSig) { lastSig = sig;
      const [ar, nd] = await Promise.all([api("auto_replies"), api("needs")]);
      $("#auto").innerHTML = table([["chat", "العميل"], ["kind", "النوع", r => `<span class="pill">${{approved: "معتمد ✅", auto: "ذكي", rule: "قاعدة", holding: "مؤقت", away: "خارج الدوام", opt_out: "إيقاف"}[r.kind] || r.kind}</span>`], ["reply", "الرد"], ["created_at", "الوقت"]], ar, {empty: "ما أرسلت أي رد بعد"});
      $("#needs").innerHTML = table([["chat", "العميل"], ["reason", "السبب"], ["last_message", "آخر رسالة"]], nd, {empty: "ما فيه أحد يحتاجك 👌"}); selectable($("#needs"), id => needSel = id); }
  };
  mountConn($("#connCard")); mountQueue($("#queue"), {limit: 6});
  $("#nd").onclick = async () => { if (needSel) { await api("need_done", {id: needSel}); lastSig = ""; LIVE(); } };
  $("#fl").onchange = e => { const f = e.target.files[0]; if (f) f.text().then(t => $("#tx").value = t); };
  $("#an").onclick = async () => { const r = await safe(() => api("analyze", {text: $("#tx").value, customer: $("#cn").value}));
    $("#res").innerHTML = `<div class="result"><div class="kv"><b>العميل</b><span>${esc(r.customer)}</span><b>التصنيف</b><span>${pill(r.classification)}</span><b>الاحتياج</b><span>${esc(r.need)}</span>
      <b>الملخص</b><span>${esc(r.summary)}</span><b>تدخل بشري</b><span>${r.handoff ? "⚠️ " + esc(r.handoff_reason) : "لا"}</span><b>المتابعة</b><span>${esc(r.follow_up || "—")}</span></div>
      <div class="reply">${esc(r.reply)}</div><div class="row mt"><button class="btn primary" id="ap">${ic("copy")} اعتماد ونسخ</button><button class="btn outline" id="rj">رفض</button></div></div>`;
    $("#ap").onclick = async () => { try { await navigator.clipboard.writeText(r.reply); } catch (e) {} await safe(() => api("reply_status", {id: r.reply_id, status: "approved"}), "اعتمدنا الرد ونسخناه — الصقه في واتساب"); };
    $("#rj").onclick = () => safe(() => api("reply_status", {id: r.reply_id, status: "rejected"}), "تم، رفضته"); };
  LIVE();
};
PAGE.pipeline = async el => {
  const d = await api("pipeline");
  el.innerHTML = head("مسار المبيعات", "مراحل عملائك من أول تواصل لين الشراء") + `<div class="kanban">${META.stages.map(st => `<div class="col"><h4>${META.class_ar[st]} <span class="pill">${d[st].length}</span></h4>${
    d[st].map(c => `<div class="kcard"><b>${esc(c.name)}</b><small>${esc((c.need || "").slice(0, 60))}</small></div>`).join("") || '<div class="note">—</div>'}</div>`).join("")}</div>`;
};
PAGE.campaigns = async el => {
  const rows = await api("campaigns");
  el.innerHTML = head("الحملات التسويقية", "مسودات فقط — ما فيه إرسال جماعي آلي، وتنرسل فقط للعملاء الموافقين") + `<div class="grid g2"><div class="card"><h3>حملة جديدة</h3>
    <label class="f"><span>اسم الحملة</span><input id="n"></label><label class="f"><span>الشريحة</span><select id="s">${META.classes.map(c => `<option value="${c}">${META.class_ar[c]}</option>`).join("")}</select></label>
    <label class="f"><span>الرسالة</span><textarea id="m"></textarea></label><button class="btn primary" id="add">${ic("save")} حفظ كمسودة</button></div>
    <div class="card"><h3>الحملات</h3>${table([["name", "الحملة"], ["segment", "الشريحة", r => pill(r.segment)], ["status", "الحالة"], ["message", "الرسالة"]], rows)}</div></div>`;
  $("#add").onclick = async () => { await safe(() => api("campaign_add", {name: $("#n").value, segment: $("#s").value, message: $("#m").value}), "حُفظت المسودة"); go("campaigns"); };
};
PAGE.followups = async el => {
  const rows = await api("followups"); let sel = null;
  el.innerHTML = head("المتابعات", "العملاء اللي يحتاجون متابعة ومواعيدهم") + `<div class="card"><div class="row end"><button class="btn primary" id="dn">${ic("check")} تمت المتابعة</button></div><div id="t" class="mt">${
    table([["name", "العميل"], ["due_date", "الموعد"], ["status", "الحالة", r => `<span class="pill">${{open: "مفتوحة", done: "تمت", stopped: "موقوفة"}[r.status] || r.status}</span>`], ["message", "الرسالة"]], rows)}</div></div>`;
  selectable($("#t"), id => sel = id); $("#dn").onclick = async () => { if (sel) { await api("followup_done", {id: sel}); go("followups"); } };
};
PAGE.analytics = async el => {
  const d = await api("analytics"), tot = Math.max(1, ...Object.values(d.dist)), s = d.stats, maxd = Math.max(1, ...d.days.map(x => x.n));
  const rate = Math.round(100 * s.approved / Math.max(1, s.replies));
  el.innerHTML = head("الأرقام والتقارير", "") + `<div class="grid g2"><div class="card"><h3>توزيع العملاء حسب التصنيف</h3><div class="bars">${META.classes.map(c =>
    `<div class="bar"><span>${META.class_ar[c]}</span><div class="tr"><div class="fi" style="width:${100 * d.dist[c] / tot}%"></div></div><b class="num">${d.dist[c]}</b></div>`).join("")}</div></div>
    <div class="card"><h3>الردود المرسلة يومياً</h3>${d.days.length ? `<div class="spark">${d.days.map(x => `<div style="height:${100 * x.n / maxd}%" title="${x.n}"><span>${x.d.slice(5)}</span></div>`).join("")}</div>` : '<div class="empty">ما فيه شي للحين</div>'}
    <p class="mt">أداء الموظف: <b>${s.replies}</b> رد مقترح، <b>${s.approved}</b> معتمد (${rate}%)</p></div></div>`;
};
PAGE.logs = async el => {
  const rows = await api("logs");
  el.innerHTML = head("وش صار (السجل)", "كل شي يسويه البرنامج تلقاه هنا وفي data\\logs") + `<div class="card">${table([["created_at", "الوقت"], ["level", "المستوى", r => `<span class="pill">${esc(r.level)}</span>`], ["action", "وش صار"], ["details", "التفاصيل"]], rows)}</div>`;
};
PAGE.settings = async el => {
  el.innerHTML = head("الإعدادات", "إعدادات عامة — إعدادات الموظف كلها في «سير عمل البوت»") + `<div class="grid g2"><div class="card"><h3>المظهر</h3><div class="row"><button class="btn outline" id="th">${ic("moon")} تبديل الوضع الليلي/النهاري</button></div></div>
    <div class="card"><h3>البيانات</h3><p class="note">كل البيانات محفوظة في مجلد data على جهازك. تؤخذ نسخة احتياطية تلقائياً عند الإغلاق وقبل أي حذف.</p><button class="btn blue" id="bk">${ic("save")} نسخة احتياطية الآن</button></div>
    <div class="card"><h3>سير عمل البوت</h3><p class="note">المنتجات والأسعار والقواعد والقوالب والتوقيت والأمان.</p><button class="btn primary" id="wf">${ic("flow")} فتح سير عمل البوت</button></div>
    <div class="card"><h3>${ic("zap")} معالج البداية</h3><p class="note">يعيد خطوات الإعداد الأولى: ربط واتساب، المعلومات، التجربة، التشغيل.</p><button class="btn outline" id="wzr">تشغيل المعالج</button></div>${howItWorks()}</div>`;
  $("#wzr").onclick = () => wizard(0);
  $("#th").onclick = toggleTheme; $("#wf").onclick = () => go("workflow");
  $("#bk").onclick = async () => { const p = await safe(() => api("backup")); toast("حُفظت: " + p, "ok"); };
};

/* ---------- workflow editor ---------- */
let WF = null, WTAB = "general";
PAGE.workflow = async el => {
  WF = await api("workflow_get");
  const tabs = [["general", "عام"], ["business", "معلومات النشاط"], ["rules", "القواعد"], ["templates", "القوالب والأسلوب"], ["prompt", "تعليمات ChatGPT"], ["safety", "التوقيت والأمان"], ["test", "🧪 تجربة"], ["io", "استيراد/تصدير"]];
  el.innerHTML = head("سير عمل البوت", "من هنا تتحكم بكل شي، وأي تعديل ينطبق فوراً بدون إعادة تشغيل") + `<div class="tabs">${tabs.map(([k, t]) => `<button data-t="${k}" class="${k === WTAB ? "active" : ""}">${t}</button>`).join("")}</div><div id="wt"></div>`;
  el.querySelectorAll(".tabs button").forEach(b => b.onclick = () => { WTAB = b.dataset.t; el.querySelectorAll(".tabs button").forEach(x => x.classList.toggle("active", x === b)); WT[WTAB]($("#wt")); });
  WT[WTAB]($("#wt"));
};
async function saveWF(payload, msg = "تم، انحفظ ✅ ويشتغل على طول") { WF = await safe(() => api("workflow_save", payload), msg); return WF; }
const sw = (id, on, label) => `<label class="check"><span class="switch"><input type="checkbox" id="${id}" ${on ? "checked" : ""}><i></i></span>${label}</label>`;
const val = id => $("#" + id).value, chk = id => $("#" + id).checked;
const WT = {};
WT.general = el => { const s = WF.settings, w = WF.wf, h = w.working_hours;
  el.innerHTML = `<div class="grid g2"><div class="card"><h3>التشغيل</h3>${sw("en", s.auto_reply_enabled, "<b>تجهيز الردود للموافقة</b> (المفتاح الرئيسي — يقرأ الرسائل ويجهّز ردود، وما يرسل شي إلا بضغطتك)")}
    ${sw("wfen", w.enabled, "تفعيل سير العمل")}${sw("grp", s.skip_groups, "تجاهل المجموعات")}
    <label class="f mt"><span>مزود الذكاء الاصطناعي</span><select id="prov"><option value="offline">المحلل المحلي (بدون إنترنت)</option><option value="chatgpt_web">ChatGPT عبر المتصفح (اشتراكك)</option></select></label>
    <div class="row"><button class="btn outline small" id="gc">فحص اتصال ChatGPT</button><span class="note">سجّل دخولك في chatgpt.com داخل نافذة Chrome الخاصة بالبرنامج</span></div></div>
    <div class="card"><h3>أوقات العمل</h3>${sw("whe", h.enabled, "الرد فقط خلال أوقات العمل")}<div class="row"><label class="f" style="flex:1"><span>من</span><input type="time" id="st" value="${h.start}"></label><label class="f" style="flex:1"><span>إلى</span><input type="time" id="et" value="${h.end}"></label></div>
    ${sw("away", h.away_enabled, "إرسال رسالة «خارج الدوام» مرة باليوم لكل عميل")}</div></div><div class="row end mt"><button class="btn primary" id="sv">${ic("save")} حفظ</button></div>`;
  $("#prov").value = s.provider; $("#gc").onclick = () => safe(() => api("gpt_check"), "لحظة، قاعد أفحص… شوف شريط الحالة");
  $("#sv").onclick = () => { w.enabled = chk("wfen"); w.working_hours = {enabled: chk("whe"), start: val("st"), end: val("et"), away_enabled: chk("away")};
    saveWF({wf: w, settings: {auto_reply_enabled: chk("en"), skip_groups: chk("grp"), provider: val("prov")}}); };
};
WT.business = el => { const b = WF.wf.business;
  el.innerHTML = `<div class="grid g2"><div class="card"><h3>بيانات النشاط</h3><label class="f"><span>اسم النشاط</span><input id="bn" value="${esc(b.name)}"></label>
    <label class="f"><span>الوصف</span><textarea id="bd">${esc(b.description)}</textarea></label><label class="f"><span>الموقع</span><input id="bl" value="${esc(b.location)}"></label>
    <label class="f"><span>أوقات العمل (نص يظهر للعميل)</span><input id="bh" value="${esc(b.hours)}"></label></div>
    <div class="card"><h3>الأسئلة الشائعة</h3><div id="faq"></div><button class="btn outline small" id="fa">${ic("plus")} سؤال جديد</button></div></div>
    <div class="card mt"><div class="row"><h3 style="margin:0">المنتجات والخدمات والأسعار المعتمدة</h3><span class="sp"></span><button class="btn primary small" id="pa">${ic("plus")} إضافة</button></div>
    <p class="note">الموظف يذكر الأسعار من هنا فقط. اترك السعر فاضي إذا ما تبيه يذكره، وبيحوّل العميل لك.</p><div id="pt"></div></div>
    <div class="row end mt"><button class="btn primary" id="sv">${ic("save")} حفظ بيانات النشاط</button></div>`;
  let faq = b.faq.map(x => ({...x}));
  const drawFaq = () => { $("#faq").innerHTML = faq.map((f, i) => `<div class="row" style="margin-bottom:8px"><input data-i="${i}" data-k="q" placeholder="السؤال" value="${esc(f.q)}" style="flex:1"><input data-i="${i}" data-k="a" placeholder="الجواب" value="${esc(f.a)}" style="flex:2"><button class="icon-btn" data-del="${i}">${ic("trash")}</button></div>`).join("") || '<p class="note">ما فيه أسئلة بعد</p>';
    $("#faq").querySelectorAll("input").forEach(i => i.oninput = () => faq[i.dataset.i][i.dataset.k] = i.value);
    $("#faq").querySelectorAll("[data-del]").forEach(x => x.onclick = () => { faq.splice(+x.dataset.del, 1); drawFaq(); }); };
  drawFaq(); $("#fa").onclick = () => { faq.push({q: "", a: ""}); drawFaq(); };
  const drawP = () => { $("#pt").innerHTML = table([["kind", "النوع"], ["title", "الاسم"], ["price", "السعر", r => r.price ? `<b>${esc(r.price)}</b>` : '<span class="muted">ما تحدد</span>'], ["content", "التفاصيل"],
    ["id", "", r => `<button class="icon-btn" data-e="${r.id}">${ic("edit")}</button><button class="icon-btn" data-d="${r.id}">${ic("trash")}</button>`]], WF.products, {empty: "أضف منتجاتك وخدماتك"});
    $("#pt").querySelectorAll("[data-e]").forEach(x => x.onclick = () => productDialog(WF.products.find(p => p.id == x.dataset.e)));
    $("#pt").querySelectorAll("[data-d]").forEach(x => x.onclick = async () => { if (confirmBox("حذف المنتج؟")) { await api("product_delete", {id: x.dataset.d}); WF = await api("workflow_get"); drawP(); } }); };
  const productDialog = (p = {kind: "منتج", title: "", price: "", content: ""}) => modal(p.id ? "تعديل منتج" : "منتج/خدمة جديدة",
    `<label class="f"><span>النوع</span><input id="mk" value="${esc(p.kind)}"></label><label class="f"><span>الاسم</span><input id="mt" value="${esc(p.title)}"></label>
     <label class="f"><span>السعر (مثال: 500 ريال)</span><input id="mp" value="${esc(p.price)}"></label><label class="f"><span>التفاصيل</span><textarea id="mc">${esc(p.content)}</textarea></label>
     <div class="row end"><button class="btn primary" id="ms">${ic("save")} حفظ</button></div>`,
    () => $("#ms").onclick = async () => { await safe(() => api("product_save", {id: p.id, kind: val("mk"), title: val("mt"), price: val("mp"), content: val("mc")}), "تم، انحفظ ✅"); closeModal(); WF = await api("workflow_get"); drawP(); });
  drawP(); $("#pa").onclick = () => productDialog();
  $("#sv").onclick = () => { const w = WF.wf; w.business = {name: val("bn"), description: val("bd"), location: val("bl"), hours: val("bh"), faq: faq.filter(f => f.q.trim() && f.a.trim())}; saveWF({wf: w}); };
};
WT.rules = el => { const rules = WF.wf.rules; let sel = null;
  const draw = () => { el.innerHTML = `<div class="card"><p class="note">تُقرأ القواعد من فوق لتحت، وأول قاعدة تنطبق تحدد وش يسوي الموظف. قاعدة «تعيين التصنيف» تكمل للي بعدها. القواعد الافتراضية هي نفس سلوك البرنامج.</p>
    <div class="row"><button class="btn primary small" id="ad">${ic("plus")} قاعدة جديدة</button><button class="btn outline small" id="ed">${ic("edit")} تعديل</button><button class="btn outline small" id="up">${ic("up")}</button><button class="btn outline small" id="dn">${ic("down")}</button><button class="btn danger-outline small" id="dl">${ic("trash")} حذف</button></div>
    <div class="mt" id="rt">${table([["i", "#", r => r.i + 1], ["enabled", "مفعّلة", r => `<span class="switch"><input type="checkbox" data-tg="${r.i}" ${r.enabled ? "checked" : ""}><i></i></span>`], ["name", "القاعدة", r => `<b>${esc(r.name)}</b>`],
      ["trigger", "إذا", r => `${esc(META.triggers[r.trigger])}${r.value ? ` <span class="pill">${esc(META.class_ar[r.value] || r.value)}</span>` : ""}`], ["action", "فـ", r => esc(META.actions[r.action])], ["text", "نص الرد", r => esc((r.text || "").slice(0, 70))]],
      rules.map((r, i) => ({...r, i, id: i})))}</div></div>`;
    selectable($("#rt"), id => sel = +id);
    if (sel !== null) $("#rt").querySelector(`tr[data-id="${sel}"]`)?.classList.add("sel");
    $("#rt").querySelectorAll("[data-tg]").forEach(x => x.onclick = async e => { e.stopPropagation(); rules[+x.dataset.tg].enabled = x.checked; await saveWF({wf: WF.wf}); });
    $("#ad").onclick = () => dialog(null); $("#ed").onclick = () => sel !== null && dialog(sel);
    $("#rt").querySelectorAll("tbody tr").forEach(tr => tr.ondblclick = () => dialog(+tr.dataset.id));
    const mv = async d => { if (sel === null) return; const j = sel + d; if (j < 0 || j >= rules.length) return; [rules[sel], rules[j]] = [rules[j], rules[sel]]; sel = j; await saveWF({wf: WF.wf}, "تم، رتبتها"); WF.wf.rules === rules || Object.assign(rules, WF.wf.rules); draw(); };
    $("#up").onclick = () => mv(-1); $("#dn").onclick = () => mv(1);
    $("#dl").onclick = async () => { if (sel !== null && confirmBox("حذف القاعدة؟")) { rules.splice(sel, 1); sel = null; await saveWF({wf: WF.wf}); WT.rules(el); } }; };
  const dialog = i => { const r = i === null ? {name: "قاعدة جديدة", enabled: true, trigger: "keywords", value: "", action: "reply", text: "", set_class: ""} : {...rules[i]};
    const opts = (o, cur) => Object.entries(o).map(([k, v]) => `<option value="${k}" ${k === cur ? "selected" : ""}>${v}</option>`).join("");
    modal(i === null ? "قاعدة جديدة" : "تعديل قاعدة", `<label class="f"><span>اسم القاعدة</span><input id="rn" value="${esc(r.name)}"></label>
      <label class="f"><span>إذا (الشرط)</span><select id="rtg">${opts(META.triggers, r.trigger)}</select></label>
      <label class="f" id="vk"><span>الكلمات (مفصولة بفاصلة)</span><input id="rv" value="${esc(r.value)}"></label>
      <label class="f" id="vc"><span>التصنيف</span><select id="rvc">${META.classes.map(c => `<option value="${c}" ${c === r.value ? "selected" : ""}>${META.class_ar[c]}</option>`).join("")}</select></label>
      <label class="f"><span>فـ (الإجراء)</span><select id="ra">${opts(META.actions, r.action)}</select></label>
      <label class="f" id="tx"><span>نص الرد — يدعم {name} {greeting} {holding} {away} {fallback} {business_name}</span><textarea id="rx">${esc(r.text)}</textarea></label>
      <label class="f" id="sc"><span>عيّن التصنيف/المرحلة</span><select id="rs">${META.classes.map(c => `<option value="${c}" ${c === r.set_class ? "selected" : ""}>${META.class_ar[c]}</option>`).join("")}</select></label>
      ${sw("ren", r.enabled, "مفعّلة")}<div class="row end"><button class="btn primary" id="rsv">${ic("save")} حفظ القاعدة</button></div>`, () => {
      const upd = () => { const t = val("rtg"), a = val("ra"); $("#vk").style.display = t === "keywords" ? "" : "none"; $("#vc").style.display = t === "classification" ? "" : "none";
        $("#tx").style.display = ["reply", "holding", "stop"].includes(a) ? "" : "none"; $("#sc").style.display = a === "mark" ? "" : "none"; };
      $("#rtg").onchange = upd; $("#ra").onchange = upd; upd();
      $("#rsv").onclick = async () => { const t = val("rtg"), a = val("ra");
        const nr = {...r, name: val("rn") || "قاعدة", trigger: t, value: t === "keywords" ? val("rv") : t === "classification" ? val("rvc") : "", action: a, text: val("rx"), set_class: a === "mark" ? val("rs") : "", enabled: chk("ren")};
        if (t === "keywords" && !nr.value.trim()) return toast("اكتب كلمة واحدة على الأقل", "err");
        if (i === null) rules.splice(Math.max(0, rules.length - 1), 0, nr); else rules[i] = nr;
        await saveWF({wf: WF.wf}); closeModal(); WT.rules(el); }; }); };
  draw();
};
WT.templates = el => { const t = WF.wf.templates, tone = WF.wf.tone;
  const f = (k, l) => `<label class="f"><span>${l}</span><textarea id="t_${k}" rows="2">${esc(t[k])}</textarea></label>`;
  el.innerHTML = `<div class="grid g2"><div class="card"><h3>قوالب الردود</h3>${f("greeting", "الترحيب")}${f("holding", "الرد المؤقت (تحويل لموظف)")}${f("away", "خارج أوقات العمل")}${f("opt_out", "تأكيد إيقاف الرسائل (فاضي = لا يرسل شيء)")}${f("fallback", "الرد الاحتياطي")}<p class="note">المتغيرات: {name} اسم العميل، {business_name} اسم النشاط</p></div>
    <div class="card"><h3>الأسلوب</h3><label class="f"><span>اللهجة</span><select id="dia">${["السعودية", "الخليجية", "الفصحى المبسطة"].map(d => `<option ${d === tone.dialect ? "selected" : ""}>${d}</option>`).join("")}</select></label>
    <label class="f"><span>أقصى طول للرد (حرف)</span><input type="number" id="ml" value="${tone.max_len}" min="40"></label>${sw("emo", tone.emoji, "السماح بالإيموجي")}</div></div>
    <div class="row end mt"><button class="btn primary" id="sv">${ic("save")} حفظ</button></div>`;
  $("#sv").onclick = () => { const w = WF.wf; ["greeting", "holding", "away", "opt_out", "fallback"].forEach(k => w.templates[k] = val("t_" + k).trim());
    if (!w.templates.holding) w.templates.holding = "أبشر، بيتواصل معك الزميل المختص قريب";
    w.tone = {dialect: val("dia"), max_len: parseInt(val("ml")) || 300, emoji: chk("emo")}; saveWF({wf: w}); };
};
WT.prompt = el => {
  el.innerHTML = `<div class="card"><h3>التعليمات المرسلة لـ ChatGPT</h3><p class="note">المتغيرات: {business_name} {business} {chat} {customer} {dialect} {max_len} {emoji_rule}</p>
    <p class="warn-note">مهما كتبت هنا، أي رد فيه سعر مو موجود في معلومات النشاط ينرفض ويتبدل برد آمن.</p><textarea id="pr" rows="14">${esc(WF.wf.chatgpt_prompt)}</textarea>
    <div class="row end mt"><button class="btn outline" id="rs">${ic("reset")} استرجاع الافتراضي</button><button class="btn primary" id="sv">${ic("save")} حفظ</button></div></div>`;
  $("#sv").onclick = () => { WF.wf.chatgpt_prompt = val("pr").trim() || META.default_prompt; saveWF({wf: WF.wf}); };
  $("#rs").onclick = () => { $("#pr").value = META.default_prompt; WF.wf.chatgpt_prompt = META.default_prompt; saveWF({wf: WF.wf}, "رجعت التعليمات للافتراضي"); };
};
WT.safety = el => { const s = WF.settings;
  const n = (k, l, st = "1") => `<label class="f"><span>${l}</span><input type="number" step="${st}" min="0" id="s_${k}" value="${s[k]}"></label>`;
  el.innerHTML = `<div class="grid g2"><div class="card"><h3>التوقيت (يخلي الرد طبيعي)</h3><div class="row"><div style="flex:1">${n("min_delay", "أقل تأخير قبل الرد (ثانية)")}</div><div style="flex:1">${n("max_delay", "أكثر تأخير (ثانية)")}</div></div>
    ${n("typing_delay_ms", "سرعة الكتابة (مللي ثانية لكل حرف)")}${n("poll_interval", "فحص الرسائل الجديدة كل (ثانية)", "0.5")}</div>
    <div class="card"><h3>الأمان والحدود</h3>${n("chat_cooldown", "أقل فاصل بين ردين بنفس المحادثة (ثانية)")}<div class="row"><div style="flex:1">${n("max_per_chat_hour", "أقصى ردود لكل محادثة بالساعة")}</div><div style="flex:1">${n("global_hour_cap", "أقصى ردود كلية بالساعة")}</div></div>
    <label class="f"><span>كلمات إيقاف الرسائل (مفصولة بفاصلة)</span><textarea id="ow" rows="2">${esc(s.opt_out_words)}</textarea></label></div></div>
    <div class="row end mt"><button class="btn primary" id="sv">${ic("save")} حفظ</button></div>`;
  $("#sv").onclick = () => { const o = {opt_out_words: val("ow")}; ["min_delay", "max_delay", "typing_delay_ms", "poll_interval", "chat_cooldown", "max_per_chat_hour", "global_hour_cap"].forEach(k => o[k] = parseFloat(val("s_" + k)) || 0); saveWF({settings: o}); };
};
WT.test = el => {
  el.innerHTML = `<div class="grid g2"><div class="card"><h3>${ic("flask")} جرّب رسالة</h3><p class="note">شوف وش بيسوي الموظف بالضبط، بدون إرسال أي شي.</p><label class="f"><span>اسم العميل</span><input id="tn" value="أحمد"></label>
    <label class="f"><span>رسالة العميل</span><textarea id="tm">السلام عليكم، كم السعر؟</textarea></label><button class="btn primary" id="go">${ic("play")} جرّب</button></div><div class="card"><h3>النتيجة</h3><div id="tr" class="empty">اكتب رسالة واضغط جرّب</div></div></div>`;
  $("#go").onclick = async () => { const r = await safe(() => api("simulate", {text: val("tm"), name: val("tn")}));
    $("#tr").className = ""; $("#tr").innerHTML = `<div class="result"><div class="kv"><b>القاعدة</b><span><b>${esc(r.rule)}</b></span><b>الإجراء</b><span>${esc(r.action_ar)}</span><b>التصنيف</b><span>${pill(r.classification)}</span>
      <b>أوقات العمل</b><span>${r.in_hours ? "داخل الدوام" : "خارج الدوام — بيتطبق إعداد خارج الدوام"}</span><b>المصدر</b><span>${esc(r.provider)}</span></div><div class="reply">${esc(r.reply) || '<span class="muted">(بدون رد)</span>'}</div></div>`; };
};
WT.io = el => {
  el.innerHTML = `<div class="grid g3"><div class="card"><h3>${ic("download")} تصدير</h3><p class="note">ملف JSON فيه القواعد والقوالب والمعلومات والمنتجات والتوقيت.</p><button class="btn blue" id="ex">تصدير</button></div>
    <div class="card"><h3>${ic("upload")} استيراد</h3><p class="note">الاستيراد ما يشغّل الموظف أبداً، والإرسال دائماً بموافقتك. تؤخذ نسخة احتياطية قبلها.</p><label class="btn outline">اختيار ملف<input type="file" id="im" accept=".json" hidden></label></div>
    <div class="card"><h3>${ic("reset")} الإعدادات الافتراضية</h3><p class="note">يرجع القواعد والقوالب والتعليمات. المنتجات والتوقيت تبقى.</p><button class="btn danger-outline" id="rs">إرجاع الافتراضي</button></div></div>`;
  $("#ex").onclick = async () => { const t = await api("workflow_export"); const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([t], {type: "application/json"})); a.download = "workflow.json"; a.click(); toast("تم، صدّرته", "ok"); };
  $("#im").onchange = async e => { const f = e.target.files[0]; if (!f) return; const text = await f.text(); WF = await safe(() => api("workflow_import", {text}), "تم، استوردته"); };
  $("#rs").onclick = async () => { if (confirmBox("إرجاع سير العمل للوضع الافتراضي؟")) WF = await safe(() => api("workflow_reset"), "رجع للافتراضي"); };
};

/* ---------- first-run wizard ---------- */
const WZ = [["wa", "اربط واتساب"], ["biz", "معلومات النشاط"], ["try", "جرّب الرد"], ["go", "شغّل الموظف"]];
async function wizard(step = 0) {
  modal("", `<div class="wz"><div class="wz-head"><div class="wz-title"><h2>أهلاً بك 👋</h2><p class="note">أربع خطوات وموظفك جاهز يرد على عملائك.</p></div>
    <ol class="wz-steps">${WZ.map(([k, t], i) => `<li class="${i < step ? "done" : i === step ? "cur" : ""}"><span>${i < step ? "✓" : i + 1}</span>${t}</li>`).join("")}</ol></div><div id="wzBody" class="wz-body"></div>
    <div class="row wz-foot"><button class="btn ghost-dark" id="wzSkip">تخطّي المعالج</button><span class="sp"></span>${step ? '<button class="btn outline" id="wzBack">السابق</button>' : ""}<button class="btn primary" id="wzNext">${step === 3 ? "إنهاء" : "التالي"}</button></div></div>`,
    async b => { b.closest(".modal-card").classList.add("wide", "wz-card"); $("#modalTitle").textContent = "";
      const body = $("#wzBody"), next = $("#wzNext");
      $("#wzSkip").onclick = async () => { await api("onboarding_done", {done: true}); closeModal(); };
      if ($("#wzBack")) $("#wzBack").onclick = () => wizard(step - 1);
      if (step === 0) { mountConn(body); next.onclick = () => wizard(1); }
      if (step === 1) { const d = await api("workflow_get"), bz = d.wf.business, p0 = d.products[0] || {};
        body.innerHTML = `<div class="grid g2"><div><label class="f"><span>اسم النشاط</span><input id="wn" value="${esc(bz.name)}" placeholder="مثال: متجر ليان للورد"></label>
          <label class="f"><span>نبذة قصيرة</span><textarea id="wd" rows="3" placeholder="وش تبيع؟ ولمين؟">${esc(bz.description)}</textarea></label><label class="f"><span>الموقع</span><input id="wl" value="${esc(bz.location)}"></label></div>
          <div><h3>أول منتج أو خدمة</h3><label class="f"><span>الاسم</span><input id="pt" value="${esc(p0.title || "")}" placeholder="مثال: باقة ورد جوري"></label>
          <label class="f"><span>السعر</span><input id="pp" value="${esc(p0.price || "")}" placeholder="مثال: 250 ريال"></label><label class="f"><span>التفاصيل</span><input id="pc" value="${esc(p0.content || "")}"></label>
          <p class="note">الموظف يذكر الأسعار من هنا فقط. تقدر تضيف الباقي من «سير عمل البوت».</p></div></div>`;
        next.onclick = async () => { bz.name = val("wn"); bz.description = val("wd"); bz.location = val("wl"); await api("workflow_save", {wf: d.wf});
          if (val("pt").trim()) await api("product_save", {id: p0.id, title: val("pt"), price: val("pp"), content: val("pc"), kind: p0.kind || "منتج"});
          wizard(2); }; }
      if (step === 2) { body.innerHTML = `<div class="grid g2"><div><label class="f"><span>اكتب رسالة كأنك عميل</span><textarea id="wm" rows="4">السلام عليكم، كم السعر؟</textarea></label>
          <button class="btn outline" id="wt">${ic("flask")} جرّب</button></div><div id="wr" class="result"><p class="note">بيطلع هنا الرد اللي بيرسله الموظف بالضبط (بدون إرسال).</p></div></div>`;
        $("#wt").onclick = async () => { const r = await safe(() => api("simulate", {text: val("wm"), name: "عميل"}));
          $("#wr").innerHTML = `<div class="kv"><b>القاعدة</b><span>${esc(r.rule)}</span><b>التصنيف</b><span>${pill(r.classification)}</span></div><div class="reply">${esc(r.reply) || "(بدون رد)"}</div>`; };
        $("#wt").click(); next.onclick = () => wizard(3); }
      if (step === 3) { const d = await api("workflow_get");
        body.innerHTML = `<div class="final"><div class="okmark">${ic("bot")}</div><h3>كل شي جاهز</h3>${sw("wa_en", d.settings.auto_reply_enabled, "<b>فعّل تجهيز الردود</b> — الموظف يقرأ رسائل عملائك ويجهّز لك رد لكل محادثة، وأنت تعتمده بضغطة. ما ينرسل شي بدون موافقتك.")}
          <p class="note">تقدر توقفه بأي وقت بزر «وقّف كل شي».</p></div>`;
        next.onclick = async () => { if (chk("wa_en")) { await api("workflow_save", {settings: {auto_reply_enabled: true}}); }
          await api("onboarding_done", {done: true}); closeModal();
          if (chk("wa_en") && STATUS.wa === "connected") safe(() => api("emp_start"), "بدأ الموظف 🎉"); else toast("تم! شغّل الموظف من فوق لما يتصل واتساب", "ok"); go("ai"); }; }
    });
}

/* ---------- shell ---------- */
function toggleTheme() { const t = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = t; localStorage.theme = t; drawThemeBtn(); }
function drawThemeBtn() { $("#themeBtn").innerHTML = document.documentElement.dataset.theme === "dark" ? ic("sun") + " الوضع النهاري" : ic("moon") + " الوضع الليلي"; }
async function boot() {
  document.documentElement.dataset.theme = localStorage.theme || "light"; drawThemeBtn();
  $("#logo").innerHTML = ic("bot");
  $("#openWa").innerHTML = ic("wa") + " ربط واتساب"; $("#startBtn").innerHTML = ic("play") + " شغّل"; $("#stopBtn").innerHTML = ic("stop") + " وقّف";
  $("#ver").textContent = "نسخة " + ((await api("meta")).version || "");
  $("#themeBtn").onclick = toggleTheme;
  $("#openWa").onclick = openConnect;
  $("#startBtn").onclick = () => safe(() => api("emp_start"), "بدأ الموظف");
  $("#stopBtn").onclick = () => safe(() => api("emp_stop"), "أبشر، وقفته");
  $("#killBtn").onclick = async () => { await safe(() => api("kill_toggle")); pollStatus(); };
  META = await api("meta");
  await pollStatus(); setInterval(pollStatus, 1500);
  setTimeout(pollReminders, 4000); setInterval(pollReminders, 60000);
  const h = location.hash.slice(1); go(PAGE[h] ? h : "overview");
  if (!STATUS.onboarding_done && !location.search.includes("nowizard")) wizard(0);
  window.__ready = true; const sp = $("#splash"); if (sp) { sp.classList.add("gone"); setTimeout(() => sp.remove(), 400); }
}
window.addEventListener("hashchange", () => { const h = location.hash.slice(1); if (PAGE[h] && h !== CURRENT) go(h); });
const _go = go; go = async p => { if (p !== "ai") LIVE = null; return _go(p); };
boot().catch(e => { document.body.innerHTML = `<div style="padding:40px;font-family:sans-serif">تعذر تشغيل الواجهة: ${esc(e.message)}</div>`; });


/* ================= PRO pages (built-in brain, orders, reports, backup) ================= */
const SAR = v => (v == null || v === "" ? "حسب الطلب" : Number(v).toLocaleString("en-US") + " ر.س");
PAGE.brain = async el => {
  const [kb, ai] = await Promise.all([api("brain_kb"), api("ai_status")]);
  const rows = kb.products.map((p, i) => `<tr data-i="${i}"><td><input data-k="name" value="${esc(p.name)}"></td><td><input data-k="aliases" value="${esc((p.aliases||[]).join("، "))}"></td>
    <td><input data-k="price" type="number" min="0" value="${p.price ?? ""}" placeholder="حسب الطلب" style="width:90px"></td><td><input data-k="category" value="${esc(p.category)}" style="width:90px"></td>
    <td><button class="btn ghost" data-del="${i}">${ic("trash")}</button></td></tr>`).join("");
  el.innerHTML = head("عقل المحل 🌷", "موظفك يفهم الطلبات والمناسبات والأحياء وأسعارك — يشتغل على جهازك بدون إنترنت وبدون أي اشتراك") + `
  <div class="card"><h3>حالة الذكاء</h3><p>✅ العقل المدمج شغال (مجاني ومحلي). ${ai.ollama.running ? "🟢 لقيت Ollama شغال على جهازك (" + esc(ai.ollama.model) + ") — يقدر يساعد لو اخترته من النسخ والأمان." : "Ollama مو شغال — ما يحتاجه البرنامج، اختياري بس."} ChatGPT عبر المتصفح: ${ai.chatgpt_experimental ? "تجريبي مفعّل" : "مقفل (تجريبي)"}.</p></div>
  <div class="card"><h3>🧪 جرّب العقل</h3><textarea id="bt" rows="2" placeholder="مثال: ابي اطلب ٢ بوكيه توليب بكره العصر حي الفيصلية الدمام"></textarea>
    <button class="btn" id="btGo">${ic("flask")} وش بيفهم ويرد؟</button><div id="btR" class="mt"></div><p class="note">التجربة ما ترسل شي لأحد.</p></div>
  <div class="card"><h3>جدول الأسعار (ر.س) — العقل ما يذكر أي سعر مو موجود هنا</h3>
    <div class="table-wrap"><table id="pt"><thead><tr><th>المنتج</th><th>أسماء ثانية يكتبها العميل</th><th>السعر</th><th>التصنيف</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>
    <button class="btn ghost" id="padd">${ic("plus")} منتج جديد</button></div>
  <div class="card"><h3>معلومات المحل</h3><div class="grid2">
    <label class="f"><span>اسم المحل</span><input id="sn" value="${esc(kb.shop.name)}"></label><label class="f"><span>المدينة</span><input id="sc" value="${esc(kb.shop.city)}"></label>
    <label class="f"><span>الموقع</span><input id="sl" value="${esc(kb.shop.location)}"></label><label class="f"><span>الدوام</span><input id="sh" value="${esc(kb.shop.hours)}"></label></div>
    <p class="note">الويكند: الجمعة والسبت · العملة: ر.س · الأرقام تنحفظ بصيغة ‎+966</p></div>
  <div class="card"><h3>المناسبات اللي يعرفها</h3><p class="muted">${Object.entries(kb.occasions).map(([k, o]) => esc(k) + (o.date ? " (" + o.date + ")" : "")).join(" · ")}</p>
    <h3>المدن</h3><p class="muted">${Object.keys(kb.cities).map(esc).join(" · ")}</p></div>
  <div class="row"><button class="btn" id="ksave">${ic("save")} حفظ</button><button class="btn ghost" id="kreset">${ic("reset")} رجّع الافتراضي</button></div>`;
  const collect = () => { const P = [...el.querySelectorAll("#pt tbody tr")].map(tr => { const o = {}; tr.querySelectorAll("input").forEach(i => o[i.dataset.k] = i.value.trim()); o.aliases = o.aliases ? o.aliases.split(/[،,]/).map(x => x.trim()).filter(Boolean) : []; o.price = o.price === "" ? null : Number(o.price); o.unit = "بوكيه"; return o; }).filter(p => p.name);
    return {products: P, shop: {...kb.shop, name: $("#sn").value, city: $("#sc").value, location: $("#sl").value, hours: $("#sh").value}}; };
  $("#btGo").onclick = async () => { const r = await safe(() => api("brain_test", {text: $("#bt").value}));
    $("#btR").innerHTML = `<div class="kv"><b>النية</b><span>${esc(r.intents.join("، "))}</span><b>اللي فهمه</b><span>${esc(JSON.stringify(r.entities, null, 0))}</span>
      <b>حرارة العميل</b><span>${r.lead_score}/100 · ${esc(r.temperature)}</span>${r.total ? `<b>المجموع</b><span>${SAR(r.total)}</span>` : ""}${r.upsell.length ? `<b>اقترح عليه</b><span>${esc(r.upsell.join("، "))}</span>` : ""}${r.missing.length ? `<b>ناقص</b><span>${esc(r.missing.join("، "))}</span>` : ""}</div><div class="reply">${esc(r.reply)}</div>`; };
  el.querySelectorAll("[data-del]").forEach(b => b.onclick = () => b.closest("tr").remove());
  $("#padd").onclick = () => { $("#pt tbody").insertAdjacentHTML("beforeend", `<tr><td><input data-k="name"></td><td><input data-k="aliases"></td><td><input data-k="price" type="number" style="width:90px"></td><td><input data-k="category" value="بوكيه" style="width:90px"></td><td></td></tr>`); };
  $("#ksave").onclick = () => safe(() => api("brain_kb_save", {kb: collect()}), "انحفظ ✅");
  $("#kreset").onclick = async () => { if (confirmBox("ترجع كل شي للافتراضي؟")) { await safe(() => api("brain_kb_reset"), "رجع الافتراضي"); go("brain"); } };
};
const OST = ["جديد", "مؤكد", "قيد التجهيز", "طلع للتوصيل", "تم التوصيل", "ملغي"];
PAGE.orders = async el => {
  const rows = await api("orders_board");
  el.innerHTML = head("الطلبات", "كرت لكل طلب: المنتج والمبلغ وموعد التوصيل والحي والحالة — العقل يعبّيه من المحادثة وأنت تعدّله") +
    (rows.length ? `<div class="cards">${rows.map(o => `<div class="card order" data-id="${o.id}"><h3>${esc(o.customer || o.chat || "عميل")} <span class="pill">${esc(o.status)}</span></h3>
      <div class="kv"><b>الطلب</b><span>${esc((o.quantity > 1 ? o.quantity + " × " : "") + o.item)}</span><b>المبلغ</b><span>${esc(o.amount_text)}</span>
      <b>التوصيل</b><span>${esc(o.delivery_date || "—")} ${esc(o.delivery_time || "")}</span><b>العنوان</b><span>${esc([o.district && "حي " + o.district, o.city].filter(Boolean).join(" - ") || o.address || "—")}</span>
      ${o.occasion ? `<b>المناسبة</b><span>${esc(o.occasion)}</span>` : ""}${o.card_text ? `<b>البطاقة</b><span>${esc(o.card_text)}</span>` : ""}</div>
      <select data-st>${OST.map(x => `<option ${x === o.status ? "selected" : ""}>${x}</option>`).join("")}</select></div>`).join("")}</div>` : `<div class="empty">ما فيه طلبات للحين — أول ما عميل يطلب بيطلع كرته هنا</div>`);
  el.querySelectorAll("[data-st]").forEach(sel => sel.onchange = () => safe(() => api("order_update", {id: sel.closest(".order").dataset.id, fields: {status: sel.value}}), "تحدثت الحالة"));
};
PAGE.reports = async el => {
  const [r, camp] = await Promise.all([api("reports"), api("campaign_suggestions")]);
  el.innerHTML = head("تقارير الأداء", "سرعة الرد والتحويل من محادثة لطلب، آخر ٣٠ يوم") + `<div class="stats">
    <div class="stat"><b>${esc(r.median_response)}</b><span>متوسط سرعة الرد</span></div><div class="stat"><b>${r.unanswered_chats}</b><span>محادثات ما انرد عليها</span></div>
    <div class="stat"><b>${esc(r.conversion)}</b><span>نسبة التحويل لطلب</span></div><div class="stat"><b>${esc(r.revenue)}</b><span>مبيعات موصّلة</span></div></div>
    <div class="card"><h3>مراحل الطلبات</h3><div class="kv">${Object.entries(r.pipeline).map(([k, v]) => `<b>${esc(k)}</b><span>${v}</span>`).join("")}</div></div>
    <div class="card"><h3>حسب المناسبة</h3>${table([["occasion", "المناسبة"], ["n", "عدد"], ["s", "المبلغ", x => SAR(x.s)]], r.by_occasion)}</div>
    <div class="card"><h3>حملات المناسبات الجاية (مسودات بس)</h3>${camp.length ? camp.map((c, i) => `<div class="card"><b>${esc(c.occasion)}</b> — بعد ${c.days} يوم (${esc(c.date)})<div class="reply">${esc(c.message)}</div>
      <button class="btn ghost" data-camp="${i}">${ic("save")} احفظها مسودة حملة</button></div>`).join("") : '<div class="empty">ما فيه مناسبة ثابتة قريبة</div>'}</div>`;
  el.querySelectorAll("[data-camp]").forEach(b => b.onclick = () => { const c = camp[b.dataset.camp]; safe(() => api("campaign_add", {name: c.occasion, segment: c.segment, message: c.message}), "انحفظت مسودة — ما انرسل شي"); });
};
PAGE.pro = async el => {
  const [s, bl, ai] = await Promise.all([api("pro_settings"), api("backups_list"), api("ai_status")]);
  el.innerHTML = head("النسخ والأمان", "كل الردود تنتظر موافقتك. خارج الدوام تقدر تسمح بالردود الآمنة بس (ترحيب، شكر، أسئلة التوصيل)") + `<div class="card">
    <label class="chk"><input type="checkbox" id="aha" ${s.after_hours_auto ? "checked" : ""}> خارج الدوام: أرسل الردود الآمنة تلقائياً (الطلبات والأسعار والشكاوى تنتظرك دايماً)</label>
    <label class="chk"><input type="checkbox" id="bd" ${s.backup_daily ? "checked" : ""}> نسخة احتياطية يومية تلقائية</label>
    <label class="f"><span>احذف المحادثات الأقدم من (يوم) — ٠ = احتفظ بكل شي</span><input id="rd" type="number" min="0" value="${s.retention_days}"></label>
    <label class="f"><span>مصدر الذكاء</span><select id="pv"><option value="offline">العقل المدمج (مجاني، بدون إنترنت) — موصى به</option>
      <option value="auto">تلقائي: Ollama إذا كان شغال${ai.ollama.running ? " ✅" : " (مو شغال)"}، وإلا العقل المدمج</option><option value="chatgpt_web">ChatGPT عبر المتصفح (تجريبي، مو مضمون)</option></select></label>
    <label class="chk"><input type="checkbox" id="ce" ${s.chatgpt_experimental ? "checked" : ""}> أفهم إن ChatGPT عبر المتصفح تجريبي وممكن يتعطل أو يخالف شروطهم</label>
    <button class="btn" id="ps">${ic("save")} حفظ</button></div>
    <div class="card"><h3>النسخ الاحتياطي</h3><div class="row"><button class="btn" id="bn">${ic("save")} نسخة الحين</button><button class="btn ghost" id="be">${ic("download")} تصدير ملف</button></div>
    <label class="f mt"><span>استرجاع من ملف تصدير (.zip) — اكتب المسار</span><input id="rp" placeholder="C:\\Users\\...\\whatsapp-employee-export.zip"></label><button class="btn ghost" id="rs">${ic("upload")} استرجاع</button>
    <p class="note">آخر النسخ: ${bl.slice(0, 5).map(esc).join("<br>") || "—"}</p></div>`;
  $("#pv").value = s.provider;
  $("#ps").onclick = () => safe(() => api("pro_settings_save", {after_hours_auto: $("#aha").checked, backup_daily: $("#bd").checked, retention_days: +$("#rd").value, provider: $("#pv").value, chatgpt_experimental: $("#ce").checked}), "انحفظ ✅");
  $("#bn").onclick = () => safe(() => api("backup_now"), "سويت نسخة ✅");
  $("#be").onclick = async () => { const p = await safe(() => api("backup_export")); toast("انحفظ في: " + p, "ok"); };
  $("#rs").onclick = async () => { if ($("#rp").value && confirmBox("بسوي نسخة من الحالي وبعدين أسترجع. أكمل؟")) await safe(() => api("backup_restore", {path: $("#rp").value}), "استرجعت ✅"); };
};
const SHOWN_REM = new Set();
async function pollReminders() {
  try {
    const due = await api("reminders_due");
    const fresh = due.filter(r => !SHOWN_REM.has(r.kind + r.id));
    if (!fresh.length) return;
    fresh.forEach(r => SHOWN_REM.add(r.kind + r.id));
    modal("🔔 تذكير", fresh.map(r => `<div class="card"><b>${esc(r.chat || "")}</b> — ${esc(r.text)} <span class="muted">(${esc(r.due_at)})</span>
      ${r.kind === "reminder" ? `<button class="btn ghost" data-rd="${r.id}">${ic("check")} تم</button>` : ""}</div>`).join(""), root =>
      root.querySelectorAll("[data-rd]").forEach(b => b.onclick = () => safe(() => api("reminder_done", {id: b.dataset.rd}), "تم ✅").then(() => b.closest(".card").remove())));
    try { if (window.Notification && Notification.permission === "granted") new Notification("موظف واتساب", {body: fresh[0].text}); } catch (e) {}
  } catch (e) {}
}
