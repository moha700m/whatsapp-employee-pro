'use strict';
// موظف واتساب — واجهة البرنامج (بسيط وكبير)
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
let CSRF = '', SET = {}, ST = {}, CRM = {}, CL = [], CH = null, PAGE = 'home', lastSig = '', FILTER = 'all', OCCS = [];
const PAGES = [['home', 'الرئيسية'], ['chats', 'المحادثات'], ['sales', 'الطلبات والعملاء'], ['mkt', 'التسويق'], ['chan', 'القناة'], ['emp', 'الموظف'], ['set', 'الإعدادات']];
const STAGES = ['جديد', 'قيد التجهيز', 'تم التوصيل', 'ملغي'];
const toast = t => { const e = $('#toast'); e.textContent = t; e.classList.add('on'); clearTimeout(e._t); e._t = setTimeout(() => e.classList.remove('on'), 2800) };
const ago = t => { if (!t) return ''; const d = (Date.now() - t) / 6e4; if (d < 1) return 'الحين'; if (d < 60) return Math.floor(d) + ' د'; if (d < 1440) return Math.floor(d / 60) + ' س'; return Math.floor(d / 1440) + ' يوم' };
const fmtT = t => new Date(t).toLocaleTimeString('ar-SA-u-ca-gregory', { hour: 'numeric', minute: '2-digit' });
const fmtD = t => new Date(t).toLocaleDateString('ar-SA-u-ca-gregory', { weekday: 'long', day: 'numeric', month: 'long' });
const fdate = iso => iso ? new Date(iso + 'T12:00:00').toLocaleDateString('ar-SA-u-ca-gregory', { day: 'numeric', month: 'long' }) : '';
const nice = t => esc(t).replace(/\d{4}-\d{2}-\d{2}/g, m => fdate(m));
const hm12 = s => { const [h, m] = String(s || '').split(':').map(Number); if (isNaN(h)) return s; const p = h < 12 ? 'الصبح' : h < 15 ? 'الظهر' : h < 18 ? 'العصر' : h < 19 ? 'المغرب' : 'الليل'; return num(h % 12 || 12) + (m ? ':' + String(m).padStart(2, '0').replace(/\d/g, d => '٠١٢٣٤٥٦٧٨٩'[d]) : '') + ' ' + p };
const ini = n => esc((n || '؟').replace(/^\+/, '').trim().charAt(0) || '؟');
const num = n => (+n || 0).toLocaleString('ar-SA');
const money = n => num(n) + ' ر.س';
const who = c => c.label || c.name || c.disp || 'عميل';
// phone shown left-to-right inside Arabic text (no flipped + or digits); hidden numbers say so instead of a raw id
const PN = c => c.disp ? `<bdi dir="ltr" class="pn">${esc(c.disp)}</bdi>` : (c.hid ? `<span class="muted">الرقم ما وصل بعد · #${esc(c.hid)}</span>` : '<span class="muted">—</span>');
const B = t => `<bdi>${esc(t)}</bdi>`;
const waitTxt = ms => { const m = Math.round(ms / 6e4); return m < 60 ? num(Math.max(1, m)) + ' د' : m < 1440 ? num(Math.round(m / 60)) + ' س' : num(Math.round(m / 1440)) + ' يوم' };
const STB = c => (c.state === 'wait' ? `<span class="chip w">ينتظر ردك · ${waitTxt(c.waitMs)}</span>` : c.state === 'new' ? '<span class="chip b">جديد</span>' : c.state === 'replied' ? '<span class="chip g">رديت</span>' : '') + (c.openOrders ? '<span class="chip r">عنده طلب</span>' : '');
// theme: light / dark / auto (follows Windows)
const SW = (id, v, l, h) => `<div class="setrow"><div class="grow"><b>${l}</b>${h ? `<div class="help-t">${h}</div>` : ''}</div><label class="switch"><input type="checkbox" id="${id}" ${v ? 'checked' : ''} aria-label="${esc(l)}"><span></span></label></div>`;
const MQ = matchMedia('(prefers-color-scheme: dark)');
function applyTheme(t) { t = t || SET.theme || 'auto'; document.documentElement.dataset.theme = t === 'auto' ? (MQ.matches ? 'dark' : 'light') : t; brandText() }
// brand colour used as TEXT: same colour in light mode, a lighter tint in dark mode (keeps contrast ≥ 4.5)
function brandText() { const r = document.documentElement, c = (r.style.getPropertyValue('--brand') || '#0A7A3E').trim(); if (!/^#[0-9a-f]{6}$/i.test(c)) return;
  if (r.dataset.theme !== 'dark') return r.style.setProperty('--brand-t', c); const n = parseInt(c.slice(1), 16), mix = v => Math.round(v + (255 - v) * .62);
  r.style.setProperty('--brand-t', '#' + [n >> 16, (n >> 8) & 255, n & 255].map(mix).map(v => v.toString(16).padStart(2, '0')).join('')) }
MQ.addEventListener?.('change', () => applyTheme());
// ---- customer media: thumbnails, lightbox, video, voice notes with speed, stickers, documents ----
const MURL = id => 'api/media?id=' + encodeURIComponent(id);
const dur = s => { s = Math.max(0, Math.round(s || 0)); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0') };
const kb = n => n > 1048576 ? (n / 1048576).toFixed(1) + ' م.ب' : Math.max(1, Math.round(n / 1024)) + ' ك.ب';
function MEDIA(m) {
  const x = m.media, u = MURL(m.id), th = x.thumb ? `data:image/jpeg;base64,${x.thumb}` : '';
  if (x.type === 'image') return `<button class="mimg" data-full="${u}" aria-label="افتح الصورة بالحجم الكامل"><img src="${u}" alt="صورة من العميل" loading="lazy"></button>`;
  if (x.type === 'sticker') return `<img class="mstk" src="${u}" alt="ملصق" loading="lazy">`;
  if (x.type === 'video') return `<video class="mvid" controls preload="none" playsinline ${th ? `poster="${th}"` : ''} src="${u}" aria-label="فيديو من العميل"></video>${x.secs ? `<small class="muted">فيديو · ${dur(x.secs)}</small>` : ''}`;
  if (x.type === 'audio') return `<div class="mau" data-src="${u}"><button class="mplay" aria-label="شغّل الرسالة الصوتية"><svg aria-hidden="true"><use href="#i-play"/></svg></button>
    <div class="mbar" role="slider" aria-label="موضع التشغيل" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" tabindex="0"><i></i></div>
    <span class="mtime">${dur(x.secs)}</span><button class="mspd" aria-label="سرعة التشغيل">1×</button><span class="mlbl">${x.ptt ? 'رسالة صوتية' : 'مقطع صوتي'}</span></div>`;
  if (x.type === 'document') return `<div class="mdoc"><svg aria-hidden="true"><use href="#i-file"/></svg><div class="grow"><b class="ell">${esc((x.name || 'ملف').replace(/\.[a-z0-9]{1,6}$/i, ''))}</b><small class="muted">${x.mime === 'application/pdf' ? 'مستند' : 'ملف'}${x.size ? ' · ' + kb(x.size) : ''}</small></div>
    <a class="btn" href="${u}" target="_blank" rel="noopener">افتح</a><a class="btn ghost" href="${u}&dl=1" download>نزّل</a></div>`;
  return '';
}
document.addEventListener('error', e => { const t = e.target; if (t?.matches?.('.mimg img, .mstk, .mvid') && !t._err) { t._err = 1; mediaErr(t) } }, true);
const mediaErr = el => { const d = document.createElement('div'); d.className = 'merr'; d.innerHTML = 'ما قدرنا نفتح الملف. تأكد إن الجوال متصل <button class="btn ghost">جرّب مرة ثانية</button>';
  d.querySelector('button').onclick = () => { const n = el.cloneNode(); n.src = el.src.split('&r=')[0] + '&r=' + Date.now(); d.replaceWith(n) }; (el.closest('.mimg') || el).replaceWith(d) };
let AU = null;
document.addEventListener('click', e => {
  const im = e.target.closest('.mimg'); if (im) { const dl = document.getElementById('lightbox'); dl.querySelector('img').src = im.dataset.full; dl.querySelector('a').href = im.dataset.full + '&dl=1'; dl.showModal(); return }
  if (e.target.closest('#lightbox') && !e.target.closest('a')) { document.getElementById('lightbox').close(); return }
  const box = e.target.closest('.mau'); if (!box) return; const a = box._a ??= (() => { const a = new Audio(box.dataset.src); a.preload = 'none';
    const bar = box.querySelector('.mbar i'), t = box.querySelector('.mtime'), b = box.querySelector('.mplay');
    a.ontimeupdate = () => { const p = a.duration ? a.currentTime / a.duration * 100 : 0; bar.style.width = p + '%'; box.querySelector('.mbar').setAttribute('aria-valuenow', Math.round(p)); t.textContent = dur(a.currentTime) + ' / ' + dur(a.duration) };
    a.onplay = () => { b.innerHTML = '<svg aria-hidden="true"><use href="#i-pause"/></svg>'; b.setAttribute('aria-label', 'وقّف'); box.classList.add('on') };
    a.onpause = a.onended = () => { b.innerHTML = '<svg aria-hidden="true"><use href="#i-play"/></svg>'; b.setAttribute('aria-label', 'شغّل الرسالة الصوتية'); box.classList.remove('on') };
    a.onerror = () => { t.textContent = 'ما اشتغل، جرّب مرة ثانية'; box._a = null }; return a })();
  if (e.target.closest('.mspd')) { const r = { 1: 1.5, 1.5: 2, 2: 1 }[a.playbackRate] || 1; a.playbackRate = r; e.target.closest('.mspd').textContent = r + '×'; return }
  if (e.target.closest('.mbar')) { const r = e.target.closest('.mbar').getBoundingClientRect(); if (a.duration) a.currentTime = a.duration * (r.right - e.clientX) / r.width; return }
  if (e.target.closest('.mplay')) { if (a.paused) { if (AU && AU !== a) AU.pause(); AU = a; a.play() } else a.pause() }
});

async function api(p, b) {
  const o = b === undefined ? {} : { method: 'POST', headers: { 'content-type': 'application/json', 'x-csrf': CSRF }, body: JSON.stringify(b) };
  const r = await fetch(p, o); if (r.status === 401) { showAuth(); throw new Error('login') }
  const j = await r.json().catch(() => ({})); if (!r.ok) throw Object.assign(new Error(j.error || 'تعذّر الاتصال'), { code: j.error }); return j;
}
// ---------- dialog (replaces window.confirm, keyboard friendly)
function ask(title, html, ok = 'تأكيد', danger = false) {
  return new Promise(res => {
    const m = $('#modal'), prev = document.activeElement; $('#mTitle').textContent = title; $('#mBody').innerHTML = html; $('#mOk').textContent = ok;
    $('#mOk').className = 'btn ' + (danger ? 'danger' : 'primary'); m.hidden = false; $('#mOk').focus();
    const done = v => { m.hidden = true; document.removeEventListener('keydown', key); prev?.focus?.(); res(v) };
    const key = e => { if (e.key === 'Escape') done(false); if (e.key === 'Tab') { const f = [$('#mOk'), $('#mNo')]; const i = f.indexOf(document.activeElement); e.preventDefault(); f[(i + (e.shiftKey ? 1 : 1)) % 2].focus() } };
    document.addEventListener('keydown', key); $('#mOk').onclick = () => done(true); $('#mNo').onclick = () => done(false); m.onclick = e => { if (e.target === m) done(false) };
  });
}
function brand(s) {
  const c = s.brand || '#0A7A3E'; document.documentElement.style.setProperty('--brand', c); brandText();
  const L = s.logo ? `<img src="${esc(s.logo)}" alt="">` : ini(s.name || s.shopName);
  $('#logo').innerHTML = L; $('#authLogo').innerHTML = L; $('#shopName').textContent = s.name || s.shopName; document.title = (s.name || s.shopName) + ' — موظف واتساب';
}
// ---------- auth (only when the owner set a lock password)
async function boot() { try { const a = await (await fetch('api/auth')).json(); brand(a.shop); LOCKED = a.locked; if (a.loggedIn) { CSRF = a.csrf; start() } else showAuth() } catch { setTimeout(boot, 1500) } }
function showAuth() {
  $('#app').hidden = true; $('#auth').hidden = false; $('#pw').focus();
  $('#authForm').onsubmit = async e => {
    e.preventDefault(); $('#authErr').textContent = '';
    try { const r = await fetch('api/auth/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ password: $('#pw').value }) }); const j = await r.json(); if (!r.ok) throw new Error(j.error); CSRF = j.csrf; $('#pw').value = ''; start() }
    catch (x) { $('#authErr').textContent = x.message }
  };
}
let started = false;
async function start() {
  $('#auth').hidden = true; $('#app').hidden = false; if (started) return go(PAGE); started = true;
  $('#nav').innerHTML = PAGES.map(([k, l]) => `<button class="tab" data-p="${k}" data-tour="tab-${k}">${l}${k === 'chats' ? '<span class="cnt" id="wc" hidden></span>' : ''}</button>`).join('');
  $$('[data-p]').forEach(b => b.onclick = () => go(b.dataset.p));
  $('#bell').onclick = toggleAlerts; $('#help').onclick = toggleHelp; $('#empPill').onclick = () => go('emp');
  await loadSettings(); await tick();
  go(location.hash.slice(1) || 'home'); setInterval(tick, 2500);
  if (!SET.tourDone) setTimeout(() => tour(0), 600);
}
// ---------- polling
async function tick() {
  try { ST = await api('api/state'); tick.fail = 0 } catch { tick.fail = (tick.fail || 0) + 1; const sb = $('#syncBar'); if (tick.fail >= 2) { $('#conn').className = 'pill conn bad'; $('#connTxt').textContent = 'منقطع'; sb.hidden = false; sb.className = 'syncbar bad'; sb.innerHTML = '<span class="spin"></span>انقطع الاتصال بمحرك البرنامج… نحاول نرجع. إذا طوّل اقفل البرنامج وافتحه.' } return }
  $('#syncBar').className = 'syncbar';
  const c = { connected: ['on', 'متصل'], qr: ['warn', 'بانتظار الربط'], reconnecting: ['warn', 'يعيد الاتصال'], loggedOut: ['bad', 'غير مربوط'], starting: ['', 'يبدأ…'] }[ST.status] || ['', ST.status];
  $('#conn').className = 'pill conn ' + c[0]; $('#connTxt').textContent = c[1]; $('#conn').title = 'الواتساب: ' + c[1];
  const e = ST.employee || {}; $('#empPill').className = 'pill ' + (e.active ? 'on' : e.enabled ? 'warn' : '');
  $('#empTxt').textContent = e.active ? 'الموظف شغّال' : e.enabled ? 'الموظف ينتظر وقته' : 'الموظف مطفي';
  $('#bellDot').hidden = !ST.unreadAlerts; if (ST.unreadAlerts > (tick.n ?? ST.unreadAlerts)) notify(); tick.n = ST.unreadAlerts;
  const sb = $('#syncBar'); sb.hidden = !(ST.status === 'connected' && ST.syncing);
  if (!sb.hidden) sb.innerHTML = `<span class="spin"></span>نحمّل محادثاتك القديمة من الجوال… وصلنا ${num(ST.chats)} محادثة و${num(ST.messages)} رسالة`;
  const dg = !ST.qr && ((ST.waitingSec || 0) >= 30 || (ST.error && ST.attempts >= 3)) ? (ST.error?.text || '1') + ST.attempts : '';
  if (PAGE === 'home' && (ST.status !== tick.s || ST.qr !== tick.q || dg !== tick.d || (ST.syncing && ST.chats !== tick.c))) renderHome(); tick.s = ST.status; tick.c = ST.chats; tick.q = ST.qr; tick.d = dg;
  if (PAGE === 'chats') { await loadChats(); if (CH) drawThread() }
}
async function notify() { try { const a = await api('api/alerts'); const n = a.find(x => !x.read); if (n) { toast(n.text); if (window.Notification?.permission === 'granted' && document.hidden) new Notification(SET.shopName || 'تنبيه', { body: n.text }) } } catch { } }
const KIND = { hot: ['r', 'فرصة'], new: ['b', 'جديد'], human: ['w', 'يحتاج ردك'], channel: ['g', 'القناة'] };
async function toggleAlerts() {
  const p = $('#alertsPop'); $('#helpPop').hidden = true; if (!p.hidden) return p.hidden = true; const A = await api('api/alerts');
  p.innerHTML = `<div style="display:flex;align-items:center;padding:6px 8px"><b class="grow">التنبيهات</b>${A.some(a => !a.read) ? '<button class="btn sm" id="ra">تعليم الكل كمقروء</button>' : ''}</div>` +
    (A.length ? A.map(a => `<div class="row" data-j="${esc(a.jid)}" tabindex="0"><span class="chip ${(KIND[a.kind] || KIND.new)[0]}">${(KIND[a.kind] || KIND.new)[1]}</span><div class="grow"><div style="${a.read ? '' : 'font-weight:700'}">${esc(a.text)}</div><small class="muted">${ago(a.t)}</small></div></div>`).join('') : '<div class="empty"><b>ما فيه تنبيهات</b>أول ما يكتب عميل مهتم أو جديد ينبهك هنا.</div>');
  p.hidden = false; if ($('#ra')) $('#ra').onclick = async () => { await api('api/alerts/read', {}); p.hidden = true; tick() };
  p.querySelectorAll('.row').forEach(r => r.onclick = r.onkeydown = e => { if (e.type === 'keydown' && e.key !== 'Enter') return; p.hidden = true; r.dataset.j && r.dataset.j !== 'null' && r.dataset.j !== 'undefined' ? openChat(r.dataset.j) : go('chan') });
}
function toggleHelp() {
  const p = $('#helpPop'); $('#alertsPop').hidden = true; if (!p.hidden) return p.hidden = true;
  p.innerHTML = `<div style="padding:8px 10px"><b>المساعدة</b><p class="muted" style="font-size:14px">نسخة ${esc(ST.version || '')}</p></div>
  <button class="btn ghost" id="h1">ابدأ الجولة التعريفية من جديد</button><button class="btn ghost" id="h2">اشرح لي هذي الصفحة</button><button class="btn ghost" id="h3">وش يقدر يسوي الموظف؟</button>`;
  p.hidden = false; $('#h1').onclick = () => { p.hidden = true; go('home'); setTimeout(() => tour(0), 200) };
  if (ST.status === 'connected') { p.insertAdjacentHTML('beforeend', '<button class="btn ghost" id="h4" style="color:var(--bad)">فصل الواتساب بعد ما أخلص…</button>'); $('#h4').onclick = () => { p.hidden = true; disconnectWA() } }
  $('#h2').onclick = () => { p.hidden = true; showHint(PAGE, true) }; $('#h3').onclick = () => { p.hidden = true; go('emp'); setTimeout(() => showHint('emp', true), 100) };
}
document.addEventListener('click', e => { for (const [p, b] of [['#alertsPop', '#bell'], ['#helpPop', '#help']]) { const el = $(p); if (!el.hidden && !el.contains(e.target) && !$(b).contains(e.target)) el.hidden = true } });
document.addEventListener('keydown', e => { if (e.key === 'Escape') { $('#alertsPop').hidden = true; $('#helpPop').hidden = true } });
async function loadSettings() { const j = await api('api/crm'); CRM = j.crm; SET = j.settings; OCCS = j.occasions || []; brand(SET); applyTheme() }
function go(p) {
  if (!PAGES.find(x => x[0] === p)) p = 'home'; PAGE = p; history.replaceState(null, '', '#' + p);
  $$('[data-p]').forEach(b => { b.classList.toggle('on', b.dataset.p === p); b.setAttribute('aria-current', b.dataset.p === p ? 'page' : 'false') });
  $$('.page').forEach(s => s.hidden = s.id !== 'p-' + p); showHint(p);
  const R = { home: renderHome, chats: renderChats, sales: renderSales, mkt: renderMkt, chan: renderChan, emp: renderEmp, set: renderSet }[p];
  loadSettings().then(R, () => { $('#p-' + p).innerHTML = errBox('البرنامج ما يرد الحين', () => go(p)) });
}
// ---------- per-screen hints (skippable, re-openable from «؟»)
const HINTS = {
  home: ['الرئيسية', 'هنا ملخص يومك: كم عميل ينتظر ردك، مين جاهز يشتري، الطلبات المفتوحة والمتابعات. اضغط على أي اسم يفتح محادثته.'],
  chats: ['المحادثات', 'كل محادثاتك القديمة والجديدة. اختر عميل، وتحت خانة الرد تلقى ردود مقترحة من المساعد وردودك الجاهزة. ما ينرسل شي إلا لما تضغط «إرسال» وتأكد.'],
  sales: ['الطلبات والعملاء', 'كل الطلبات المسجّلة وحالتها، ومسار العملاء من «جديد» إلى «تم التوصيل». غيّر حالة الطلب من هنا، وتصنيف العميل من ملفه داخل المحادثة.'],
  mkt: ['التسويق', 'كل يوم نرتب لك أهم ٥ خطوات تسويق، ومعها رسالة جاهزة. تفتح محادثة العميل وترسل بنفسك، وحدة وحدة.'],
  chan: ['القناة', 'انشر عروضك وتنسيقاتك لكل متابعين قناتك مرة وحدة. خذ فكرة جاهزة، خل الذكاء يكتبها، وأنت تراجع وتضغط «انشر». ما ينتشر شي لحاله.'],
  emp: ['الموظف', 'الموظف يرد على عملائك تلقائياً لما تشغّله: يرحّب ويجاوب الأسئلة البسيطة، وإذا العميل يبي يطلب أو يسأل عن سعر أو عنده شكوى يقوله «لحظات» وينبهك ترد بنفسك. مطفي لين تشغّله أنت.'],
  set: ['الإعدادات', 'بيانات المحل، قائمة الأسعار اللي يعتمد عليها المساعد، الردود الجاهزة، التنبيهات، قفل البرنامج، والسجل.'],
};
function showHint(p, force) {
  const h = $('#hint'), off = SET.hintsOff || []; if (!HINTS[p] || (!force && off.includes(p))) { h.hidden = true; return }
  h.innerHTML = `<svg aria-hidden="true"><use href="#i-help"/></svg><div class="grow"><b>${HINTS[p][0]}</b>${HINTS[p][1]}</div><button class="btn sm" id="hintX">فهمت</button>`; h.hidden = false;
  $('#hintX').onclick = async () => { h.hidden = true; fitChat(); if (!off.includes(p)) { SET = await api('api/settings', { hintsOff: [...off, p] }) } };
}
// ---------- first-run guided tour
const TOUR = [
  { t: 'هلا والله 👋', b: 'هذا «موظف واتساب»: يرتب محادثات محلك، يساعدك ترد أسرع، ويرد عن بالك لما تبي. خذ جولة سريعة (دقيقة وحدة).', el: null },
  { t: 'اربط الواتساب', b: 'من الرئيسية تمسح رمز QR من جوال المحل مرة وحدة بس. بعدها تنزل محادثاتك القديمة كلها وتبقى محفوظة حتى لو قفلت البرنامج.', el: '[data-tour=tab-home]' },
  { t: 'المحادثات', b: 'هنا كل العملاء. افتح أي محادثة، اختر رد مقترح أو اكتب ردك، واضغط «إرسال».', el: '[data-tour=tab-chats]' },
  { t: 'الطلبات والعملاء', b: 'الطلبات اللي تسجلها (أو يطلعها المساعد من المحادثة) وحالتها، ومبيعاتك.', el: '[data-tour=tab-sales]' },
  { t: 'التسويق', b: 'حملات المناسبات، الرسائل الجماعية كمسودة، وترجيع العملاء القدامى.', el: '[data-tour=tab-mkt]' },
  { t: 'القناة', b: 'قناة واتساب حقتك: أفكار منشورات جاهزة، كتابة بالذكاء، وتنشر بنفسك بعد ما تأكد.', el: '[data-tour=tab-chan]' },
  { t: 'الموظف (الرد الآلي)', b: 'شغّله ويرد على العملاء بنفسه، ويحوّل لك الطلبات والأسعار والشكاوى. هذا الزر يوريك حالته دايم.', el: '[data-tour=emp]' },
  { t: 'التنبيهات', b: 'لما يكتب عميل جاهز يشتري أو يحتاج ردك، يطلع لك تنبيه هنا.', el: '[data-tour=bell]' },
  { t: 'المساعدة', b: 'تبي الشرح مرة ثانية؟ اضغط علامة الاستفهام في أي وقت.', el: '[data-tour=help]' },
];
function tour(i) {
  const T = $('#tour'), step = TOUR[i]; if (!step) return endTour(); T.hidden = false;
  $('#tourN').textContent = `${num(i + 1)} من ${num(TOUR.length)}`; $('#tourT').textContent = step.t; $('#tourB').textContent = step.b;
  $('#tourPrev').hidden = i === 0; $('#tourNext').textContent = i === TOUR.length - 1 ? 'يلا نبدأ' : 'التالي';
  const hole = $('#tourHole'), card = T.querySelector('.tour-card'), el = step.el && $(step.el);
  if (el) { const r = el.getBoundingClientRect(); Object.assign(hole.style, { top: r.top - 6 + 'px', left: r.left - 6 + 'px', width: r.width + 12 + 'px', height: r.height + 12 + 'px' });
    const cw = Math.min(380, innerWidth - 32); let left = Math.min(Math.max(16, r.left + r.width / 2 - cw / 2), innerWidth - cw - 16);
    Object.assign(card.style, { top: r.bottom + 18 + 'px', left: left + 'px' }) }
  else { Object.assign(hole.style, { top: '50%', left: '50%', width: '0px', height: '0px' }); Object.assign(card.style, { top: 'calc(50% - 120px)', left: `calc(50% - ${Math.min(380, innerWidth - 32) / 2}px)` }) }
  $('#tourNext').onclick = () => tour(i + 1); $('#tourPrev').onclick = () => tour(i - 1); $('#tourSkip').onclick = endTour; $('#tourNext').focus();
  T.onkeydown = e => { if (e.key === 'Escape') endTour(); if (e.key === 'ArrowLeft') tour(i + 1); if (e.key === 'ArrowRight' && i) tour(i - 1) };
}
async function endTour() { $('#tour').hidden = true; if (!SET.tourDone) { SET = await api('api/settings', { tourDone: true }) } }
// ---------- HOME
async function renderHome() {
  const el = $('#p-home');
  if (ST.status && ST.status !== 'connected') {
    el.innerHTML = `<div class="link card"><div class="qrbox">${ST.qr ? `<img src="${ST.qr}" alt="رمز QR لربط الواتساب">` : '<div style="text-align:center"><span class="spin" style="width:36px;height:36px;color:var(--brand);display:inline-block"></span><p class="muted" style="margin-top:12px">نجهّز الرمز…</p></div>'}</div>
    <div><h1 style="font-size:30px;font-weight:800">اربط واتساب المحل</h1><p class="muted" style="font-size:17px;margin-top:6px">${ST.status === 'loggedOut' ? 'الواتساب مفصول عن هذا الجهاز. امسح الرمز إذا تبي تربطه من جديد.' : ST.status === 'reconnecting' ? 'نعيد الاتصال… لحظات.' : 'مرة وحدة بس، وبعدها يبقى مربوط حتى لو قفلت البرنامج.'}</p>
    <ol class="steps"><li>افتح واتساب في جوال المحل</li><li>اضغط ⋮ أو الإعدادات ← الأجهزة المرتبطة</li><li>اضغط «ربط جهاز» وامسح الرمز</li></ol>
    <div class="notice g">بعد الربط تنزل محادثاتك القديمة تلقائياً. البرنامج ما يرسل أي رسالة إلا لما تضغط «إرسال» بنفسك، أو تشغّل الموظف.</div>
    ${!ST.qr && !ST.sim && ((ST.waitingSec || 0) >= 30 || (ST.error && ST.attempts >= 3)) ? `<div class="notice" id="waDiag" role="alert" style="margin-top:14px;border-color:var(--bad,#c0392b)"><b>ما وصلنا رمز الربط من واتساب.</b><br>السبب: ${esc(ST.error?.text || 'الاتصال بواتساب بطيء أو محجوب — تأكد من الإنترنت ومن إن برنامج الحماية ما يمنع البرنامج')}.<br><span class="muted">نحاول تلقائياً${ST.attempts ? ` (محاولة ${ST.attempts.toLocaleString('ar-SA')})` : ''}. السجل محفوظ في مجلد logs داخل بيانات البرنامج.</span>
      <div style="display:flex;gap:10px;margin-top:12px;flex-wrap:wrap"><button class="btn primary" id="waRetry">إعادة المحاولة</button><button class="btn" id="waReset">إعادة ضبط الربط</button></div></div>` : ''}
    ${ST.sim ? '<button class="btn primary big" id="simLink" style="margin-top:16px">ربط تجريبي</button>' : ''}</div></div>`;
    if ($('#waRetry')) $('#waRetry').onclick = async e => { e.currentTarget.disabled = true; try { await api('api/wa/retry', {}); toast('نحاول من جديد…') } catch (x) { toast('تعذّر: ' + x.message) } tick() };
    if ($('#waReset')) $('#waReset').onclick = async () => { if (!await ask('إعادة ضبط الربط', 'نمسح جلسة الربط القديمة ونطلب رمز جديد. محادثاتك وعملاؤك وإعداداتك ما تنمسح.', 'إعادة الضبط')) return; try { await api('api/wa/reset', {}); toast('جاري طلب رمز جديد…') } catch (x) { toast('تعذّر: ' + x.message) } tick() };
    if ($('#simLink')) $('#simLink').onclick = () => api('api/sim/link', { me: '966500000000', history: window.SIM_HISTORY }).then(tick);
    return;
  }
  if (!el.querySelector('.kpis')) el.innerHTML = '<div class="card"><div class="skel" style="width:40%;height:28px"></div><div class="skel"></div><div class="skel" style="width:70%"></div></div>';
  let d; try { d = await api('api/dashboard') } catch (x) { el.innerHTML = errBox('ما قدرنا نجيب الملخص', renderHome); return }
  const a = d.analytics, days = [...Array(14)].map((_, i) => new Date(Date.now() - (13 - i) * 864e5).toISOString().slice(0, 10)), mx = Math.max(1, ...days.map(x => a.msgsByDay[x] || 0));
  const rt = a.medianResponseMin == null ? '' : a.medianResponseMin < 1 ? 'أقل من دقيقة' : a.medianResponseMin < 60 ? num(a.medianResponseMin) + ' د' : num(Math.round(a.medianResponseMin / 60)) + ' س';
  let P = null; try { P = await api('api/plan') } catch { }
  const hi = P?.greeting || 'أهلاً';
  const T = { reply: ['w', 'رد'], follow: ['b', 'متابعة'], order: ['r', 'طلب'], reengage: ['g', 'رجّعه'], occasion: ['', 'فرصة'] };
  const pct = P && P.progress.total ? Math.round(P.progress.done / P.progress.total * 100) : 0;
  const planH = !P ? errBox('ما قدرنا نجهز الخطة', renderHome) : !P.items.length
    ? `<div class="empty"><b>${P.progress.total ? 'خلصت كل شي اليوم 👏' : 'ما فيه شي مستعجل 👌'}</b>أول ما يكتب لك عميل تطلع له مهمة هنا.</div>`
    : `<ol class="plan">${P.items.map(i => `<li class="pi" data-id="${esc(i.id)}"><span class="chip ${T[i.type]?.[0] || ''}">${T[i.type]?.[1] || ''}</span><div class="grow"><b class="ell" style="display:block">${B(i.title)}</b><small class="muted">${B(i.why)}</small></div>
        ${i.value ? `<span class="val" title="قيمة تقديرية من أسعارك">~${money(i.value)}</span>` : ''}
        <div class="pi-act">${i.jid ? `<button class="btn sm" data-open="${esc(i.jid)}">افتح</button>` : ''}${i.suggest && i.jid ? `<button class="btn sm soft" data-sug="${esc(i.jid)}"><svg aria-hidden="true"><use href="#i-spark"/></svg>رد مقترح</button>` : ''}${i.type === 'occasion' ? '<button class="btn sm soft" data-mkt="1">جهّز عرض</button>' : ''}<button class="btn sm ghost" data-done="${esc(i.id)}" aria-label="تم: ${esc(i.title)}">تم ✓</button></div></li>`).join('')}</ol>${P.more ? `<p class="muted" style="font-size:14px;margin-top:6px">و${num(P.more)} مهمة ثانية أقل أهمية.</p>` : ''}`;
  const sub = P ? [P.counts.waiting && `${num(P.counts.waiting)} ينتظرون ردك`, P.counts.overdue && `${num(P.counts.overdue)} متابعة متأخرة`, P.value && `فرص بقيمة ~${money(P.value)}`].filter(Boolean).join(' · ') : '';
  el.innerHTML = `<div class="page-h"><div><h1>${esc(hi)}، ${B(SET.shopName)}</h1><p>${fmtD(Date.now())} · ${ST.open ? 'المحل مفتوح الحين' : 'خارج ساعات العمل'}</p></div>
   <div class="act"><button class="btn primary" id="toChats">افتح المحادثات${a.waiting ? ` <span class="cnt inv">${num(a.waiting)}</span>` : ''}</button></div></div>
  <div class="grid kpis" style="margin-bottom:var(--s4)">
   <div class="kpi main"><div class="v">${num(a.waiting)}</div><div class="l">${a.waiting ? 'محادثة تنتظر ردك' : 'ما أحد ينتظر ردك 👌'}</div></div>
   ${a.revenue ? `<div class="kpi"><div class="v">${money(a.revenue)}</div><div class="l">مبيعات مسجّلة · ${num(a.orders)} طلب</div></div>` : `<div class="kpi kpi-empty"><div class="v sm">سجّل أول طلب</div><div class="l">من «ملف العميل» داخل المحادثة — ونحسب لك المبيعات هنا.</div></div>`}
   <div class="kpi"><div class="v">${num(a.customers)}</div><div class="l">عميل${a.active7 ? ` · ${num(a.active7)} نشط هالأسبوع` : ''}</div></div>
   ${rt ? `<div class="kpi"><div class="v">${rt}</div><div class="l">متوسط وقت ردك</div></div>` : `<div class="kpi kpi-empty"><div class="v sm">—</div><div class="l">متوسط وقت ردك يطلع بعد أول ردود</div></div>`}</div>
  <div class="hero"><div class="card plan-card"><h3><svg aria-hidden="true"><use href="#i-spark"/></svg>خطة اليوم<button class="btn sm ghost act" id="brf" aria-label="حدّث الخطة">حدّث</button></h3>
   ${P && P.progress.total ? `<div class="prog" role="progressbar" aria-valuemin="0" aria-valuemax="${P.progress.total}" aria-valuenow="${P.progress.done}" aria-label="تقدّم خطة اليوم"><span style="width:${pct}%"></span></div><p class="muted prog-t">خلصت ${num(P.progress.done)} من ${num(P.progress.total)}${sub ? ' · ' + sub : ''}</p>` : sub ? `<p class="muted prog-t">${sub}</p>` : ''}
   ${planH}
   ${P?.summary?.length ? `<div class="eod"><b>ملخص اليوم</b><span>${P.summary.map(esc).join(' · ')}</span></div>` : ''}</div>
   <div class="card"><h3><svg aria-hidden="true" style="color:var(--hot)"><use href="#i-flame"/></svg>جاهزين للشراء<button class="btn sm soft act" id="score">قيّم العملاء</button></h3>
   ${d.hot.length ? d.hot.slice(0, 5).map(x => `<div class="row" data-j="${esc(x.jid)}" tabindex="0"><div class="av">${ini(who(x))}</div><div class="grow"><b class="ell" style="display:block">${B(who(x))}</b><small class="muted ell" style="display:block">${esc(x.reason || x.last.text || '')}</small></div><span class="chip r">${num(x.score)}</span></div>`).join('') : '<div class="empty"><b>ما فيه أحد حالياً</b>أول ما يسأل عميل عن سعر أو توصيل يطلع هنا.</div>'}</div></div>
  <div class="grid g3"><div class="card"><h3><svg aria-hidden="true" style="color:var(--warn)"><use href="#i-clock"/></svg>متابعات${d.reminders.length ? ` <span class="chip w">${num(d.reminders.length)}</span>` : ''}</h3>
   ${d.reminders.length ? d.reminders.slice(0, 6).map(r => `<div class="row" data-j="${esc(r.jid)}" tabindex="0"><div class="av">${ini(r.name)}</div><div class="grow"><b class="ell" style="display:block">${B(r.name)}</b><small class="muted">${esc(r.why)}</small></div></div>`).join('') : '<div class="empty"><b>كل العملاء متابَعين</b>ما فيه متابعات مستحقة.</div>'}</div>
   <div class="card"><h3><svg aria-hidden="true"><use href="#i-box"/></svg>طلبات مفتوحة${d.orders.length ? ` <span class="chip g">${num(d.orders.length)}</span>` : ''}</h3>
   ${d.orders.length ? d.orders.slice(0, 6).map(o => `<div class="row" data-j="${esc(o.jid)}" tabindex="0"><div class="grow"><b class="ell" style="display:block">${esc(o.item)}</b><small class="muted">${B(o.name)}${o.deliveryDate ? ' · ' + fdate(o.deliveryDate) : ''}</small></div><span class="chip">${esc(o.status || 'جديد')}</span></div>`).join('') : '<div class="empty"><b>ما فيه طلبات مفتوحة</b>سجّل الطلب من ملف العميل داخل المحادثة.</div>'}</div>
   <div class="card"><h3>رسائل العملاء آخر ١٤ يوم</h3><div class="bars" role="img" aria-label="عدد رسائل العملاء يومياً">${days.map((x, i) => `<div class="${i === 13 ? 'hi' : ''}" style="height:${(a.msgsByDay[x] || 0) / mx * 100}%" title="${x}: ${a.msgsByDay[x] || 0}"></div>`).join('')}</div>
   <div class="bars-l">${days.map((x, i) => `<span>${i % 3 ? '' : num(+x.slice(8))}</span>`).join('')}</div>
   ${a.autoToday ? `<p class="muted" style="margin-top:10px;font-size:14px">الموظف رد ${num(a.autoToday)} مرة اليوم</p>` : ''}</div></div>`;
  el.querySelectorAll('[data-open]').forEach(b => b.onclick = () => openChat(b.dataset.open));
  el.querySelectorAll('[data-sug]').forEach(b => b.onclick = () => { PREFILL = b.dataset.sug; openChat(b.dataset.sug) });
  el.querySelectorAll('[data-mkt]').forEach(b => b.onclick = () => go('mkt'));
  el.querySelectorAll('[data-done]').forEach(b => b.onclick = async () => { b.disabled = true; try { await api('api/plan/done', { id: b.dataset.done }); b.closest('li').classList.add('gone'); setTimeout(renderHome, 260) } catch { b.disabled = false; toast('تعذّر') } });
  el.querySelectorAll('.row[data-j]').forEach(r => r.onclick = r.onkeydown = e => { if (e.type === 'keydown' && e.key !== 'Enter') return; openChat(r.dataset.j) });
  $('#toChats').onclick = () => go('chats');
  $('#brf').onclick = () => renderHome();
  $('#score').onclick = async e => { const b = e.currentTarget; b.disabled = true; b.textContent = 'نقيّم…'; try { const r = await api('api/ai/score-all', {}); toast('تم تقييم ' + num(r.scored) + ' عميل'); renderHome() } catch (x) { toast(x.code === 'brain_off' ? 'المساعد مقفل من الإعدادات' : 'تعذّر التقييم'); b.disabled = false; b.textContent = 'قيّم العملاء' } };
}
function errBox(t, retry) { // shown when the local engine does not answer
 setTimeout(() => { const b = $('#retry'); if (b) b.onclick = retry }, 0); return `<div class="card empty"><b>${t}</b>تأكد إن البرنامج شغّال وجرب مرة ثانية.<div style="margin-top:12px"><button class="btn" id="retry">إعادة المحاولة</button></div></div>` }
// ---------- CHATS
function renderChats() {
  const el = $('#p-chats');
  if (ST.status !== 'connected') { el.innerHTML = `<div class="card empty"><b>الواتساب غير مربوط</b>اربطه من الرئيسية وتطلع محادثاتك هنا.<div style="margin-top:12px"><button class="btn primary" id="gl">اربط الحين</button></div></div>`; $('#gl').onclick = () => go('home'); return }
  el.innerHTML = `<div class="chatwrap" id="cw"><div class="clist"><div class="search"><svg aria-hidden="true"><use href="#i-search"/></svg><input id="cq" placeholder="ابحث بالاسم أو الرقم" aria-label="ابحث بالاسم أو الرقم"></div>
   <div class="filters" style="margin:12px 0 6px" id="cf" role="group" aria-label="تصفية"></div><small class="muted" id="clCount" aria-live="polite"></small><div id="cl"></div></div>
   <div class="thread" id="th"><div class="th-empty"><svg aria-hidden="true"><use href="#i-chat"/></svg><b>اختر محادثة</b><span>محادثاتك مرتبة مثل واتساب: الأحدث فوق.</span></div></div><aside class="side-panel" id="sp" aria-label="معلومات العميل"></aside><div class="sp-scrim" id="spx"></div></div>`;
  $('#spx').onclick = () => $('#cw').classList.remove('panel'); $('#cq').oninput = drawList; drawFilters(); fitChat(); lastSig = ''; loadChats().then(() => { if (CH) openChat(CH) });
}
// WhatsApp-style list time: clock today, «أمس», weekday this week, else date
const hue = j => [...String(j)].reduce((a, ch) => (a * 31 + ch.charCodeAt(0)) % 360, 7);
function clock(ts) { if (!ts) return ''; const d = new Date(ts), n = new Date(), day = 864e5, t0 = new Date(n.toDateString()).getTime();
  if (ts >= t0) return d.toLocaleTimeString('ar-SA', { hour: 'numeric', minute: '2-digit' }); if (ts >= t0 - day) return 'أمس';
  if (ts >= t0 - 6 * day) return d.toLocaleDateString('ar-SA', { weekday: 'long' }); return d.toLocaleDateString('ar-SA', { day: 'numeric', month: 'numeric', year: '2-digit' }) }
function drawFilters() {
  const f = [['all', 'الكل'], ['wait', 'ينتظر ردك'], ['new', 'جديد'], ['orders', 'عنده طلب'], ['hot', 'ساخن']], isTag = FILTER.startsWith('t:') || FILTER === 'resolved';
  $('#cf').innerHTML = f.map(([k, l]) => `<button data-f="${esc(k)}" class="${FILTER === k ? 'on' : ''}" aria-pressed="${FILTER === k}">${esc(l)}</button>`).join('') +
   `<select id="cfs" aria-label="تصفية حسب التصنيف" style="width:auto;min-height:36px;padding:4px 10px;font-size:14px;font-weight:700;${isTag ? 'border-color:var(--ink)' : ''}"><option value="">التصنيف…</option>${(SET.tags || []).map(t => `<option value="t:${esc(t)}" ${FILTER === 't:' + t ? 'selected' : ''}>${esc(t)}</option>`).join('')}<option value="resolved" ${FILTER === 'resolved' ? 'selected' : ''}>منتهية</option></select>`;
  $('#cf').querySelectorAll('button').forEach(b => b.onclick = () => { FILTER = b.dataset.f; drawFilters(); drawList() });
  $('#cfs').onchange = e => { FILTER = e.target.value || 'all'; drawFilters(); drawList() };
}
function fitChat() { const w = $('#cw'); if (!w) return; const top = w.getBoundingClientRect().top + scrollY; w.style.height = Math.max(480, innerHeight - top - 20) + 'px' }
addEventListener('resize', fitChat);
async function loadChats() {
  try { CL = await api('api/chats') } catch { return }
  const w = CL.filter(c => c.state === 'wait').length, e = $('#wc'); if (e) { e.hidden = !w; e.textContent = num(w) }
  if ($('#cl')) drawList();
}
let LIMIT = 120;   // render in pages; scrolling near the end shows more (all chats, no cap)
function drawList(more) {
  const q = ($('#cq')?.value || '').trim(), qd = q.replace(/\D/g, ''), qf = qd ? [qd, qd.replace(/^0/, '966'), qd.replace(/^966/, '0')] : [];
  let l = CL.filter(c => !q || (c.label || '').includes(q) || (c.name || '').includes(q) || (qd.length >= 3 && qf.some(f => (c.phone || '').includes(f) || (c.disp || '').includes(f))));
  if (FILTER === 'wait') l = l.filter(c => c.state === 'wait'); else if (FILTER === 'new') l = l.filter(c => c.isNew); else if (FILTER === 'hot') l = l.filter(c => c.score >= SET.hotScore);
  else if (FILTER === 'orders') l = l.filter(c => c.openOrders || c.orders); else if (FILTER === 'resolved') l = l.filter(c => c.status === 'resolved');
  else if (FILTER.startsWith('t:')) l = l.filter(c => c.tag === FILTER.slice(2)); else l = l.filter(c => c.status !== 'resolved');
  if (!more) LIMIT = Math.max(120, LIMIT);
  const shown = l.slice(0, LIMIT);
  const h = shown.map(c => `<button class="ci ${c.jid === CH ? 'on' : ''} ${c.state === 'wait' ? 'is-wait' : ''}" data-j="${esc(c.jid)}"><div class="av" style="--h:${hue(c.jid)}">${ini(who(c))}</div><div class="grow"><div class="t1"><b class="ell grow">${B(who(c))}</b><small class="${c.state === 'wait' ? 'hot-t' : ''}">${clock(c.lastAt)}</small></div>
   <div class="t2"><span class="ell grow">${c.fromMe ? `<svg class="tick" aria-hidden="true"><use href="#i-check"/></svg>${c.auto ? 'الموظف: ' : ''}` : ''}${c.last ? esc(c.last) : (c.name && c.disp ? PN(c) : 'محادثة قديمة')}</span>${c.pinned ? '<svg class="pin" aria-label="مثبّتة"><use href="#i-pin"/></svg>' : ''}${c.state === 'wait' ? '<i class="wdot" aria-label="ينتظر ردك"></i>' : ''}</div><div class="t3">${STB(c)}${c.score >= SET.hotScore ? '<span class="chip r">ساخن</span>' : ''}</div></div></button>`).join('')
    + (l.length > LIMIT ? `<button class="btn block ghost" id="clMore">اعرض ${num(Math.min(120, l.length - LIMIT))} محادثة زيادة (باقي ${num(l.length - LIMIT)})</button>` : '');
  const cl = $('#cl'); if (cl._h !== h) { const st = cl.scrollTop; cl.innerHTML = h || `<div class="empty"><b>${CL.length ? 'ما فيه نتائج' : ST.syncing ? 'نحمّل المحادثات…' : 'ما فيه محادثات للحين'}</b>${CL.length ? 'جرّب تصفية ثانية.' : ''}</div>`; cl._h = h; cl.scrollTop = st;
    cl.querySelectorAll('.ci').forEach(r => r.onclick = () => openChat(r.dataset.j)); const m = $('#clMore'); if (m) m.onclick = () => { LIMIT += 120; drawList(true) } }
  const cnt = $('#clCount'); if (cnt) cnt.textContent = `${num(l.length)} من ${num(CL.length)} محادثة`;
  if (!cl._sc) { cl._sc = true; cl.addEventListener('scroll', () => { if (cl.scrollTop + cl.clientHeight > cl.scrollHeight - 300 && $('#clMore')) { LIMIT += 120; drawList(true) } }, { passive: true }) }
}
async function openChat(j) { CH = j; lastSig = ''; if (PAGE !== 'chats') { go('chats'); return } drawList(); await drawThread(true) }
async function drawThread(full) {
  let c; try { c = await api('api/chat?jid=' + encodeURIComponent(CH)) } catch { return } const th = $('#th'); if (!c || !th) return;
  if (full || !th.querySelector('.msgs')) {
    th.innerHTML = `<div class="th-head"><button class="icon-btn th-back" id="tbk" aria-label="رجوع للمحادثات"><svg aria-hidden="true"><use href="#i-x"/></svg></button><div class="av" style="--h:${hue(c.jid)}">${ini(who(c))}</div><div class="grow"><b class="ell" style="display:block">${esc(who(c))}</b><small class="muted">${c.name ? PN(c) : (c.disp ? '' : 'رقمه مخفي من واتساب')}</small></div>
     <label class="sr" for="cst" hidden>حالة المحادثة</label><select id="cst" aria-label="حالة المحادثة"><option value="open">مفتوحة</option><option value="pending">معلّقة</option><option value="resolved">منتهية</option></select>
     <button class="icon-btn info" id="pt" aria-label="معلومات العميل والطلبات" title="معلومات العميل والطلبات"><svg aria-hidden="true"><use href="#i-info"/></svg></button></div>
     <div class="autobar" id="ab" hidden><span class="spin"></span>الموظف بيرد عليه خلال ثواني — إذا رديت أنت يلغي رده.</div><div class="autowhy" id="aw" hidden></div>
     <div class="msgs" id="ms" aria-live="polite"></div>
     <div class="composer" style="position:relative"><div class="sugs" id="sg"></div><div class="slash" id="sl" hidden></div>
      <div class="bar"><textarea id="tx" rows="1" placeholder="اكتب ردك هنا… (اكتب / للردود الجاهزة)" aria-label="نص الرد"></textarea><button class="btn primary" id="sd"><svg aria-hidden="true"><use href="#i-send"/></svg>إرسال</button></div></div>`;
    $('#cst').value = c.crm.status || 'open'; $('#cst').onchange = () => saveCRM({ status: $('#cst').value }).then(() => { toast('تم تحديث الحالة'); loadChats() });
    $('#pt').onclick = () => $('#cw').classList.toggle('panel'); $('#tbk').onclick = () => $('#cw').classList.remove('open-th', 'panel');
    $('#cw').classList.add('open-th');
    if (PRETEXT?.jid === CH) { $('#tx').value = PRETEXT.text; PRETEXT = null; $('#tx').focus(); toast('الرسالة جاهزة — راجعها واضغط «إرسال»') }
    $('#tx').oninput = () => { slash(); const t = $('#tx'); t.style.height = 'auto'; t.style.height = Math.min(160, t.scrollHeight + 2) + 'px' };
    $('#tx').onkeydown = e => { const sl = $('#sl'); if (!sl.hidden && e.key === 'Enter') { e.preventDefault(); sl.querySelector('[data-i]')?.click() } else if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) send() };
    $('#sd').onclick = send; drawSugs(); drawPanel(c); suggest();
  }
  $('#ab').hidden = !c.pendingAuto; { const w = c.autoWhy, el = $('#aw'); el.hidden = !w || c.pendingAuto || !SET.autoReply?.enabled || Date.now() - w.t > 864e5; if (w) { el.className = 'autowhy ' + (/^(sent|queued)$/.test(w.code) ? 'ok' : 'no'); el.textContent = (/^(sent|queued)$/.test(w.code) ? 'الموظف: ' : 'الموظف ما رد لأن ') + w.why + ' · ' + clock(w.t) } }
  const sig = c.messages.length + ':' + (c.messages.at(-1)?.id || ''); if (sig === lastSig) return; lastSig = sig; let pd = ''; const ms = $('#ms');
  ms.innerHTML = c.messages.length ? c.messages.map(m => { const d = new Date(m.ts).toDateString(); const sep = d !== pd ? `<div class="daysep">${fmtD(m.ts)}</div>` : ''; pd = d;
    return sep + `<div class="m ${m.fromMe ? 'me' : 'them'} ${m.auto ? 'auto' : ''}">${m.auto ? '<span class="who"><svg aria-hidden="true"><use href="#i-bot"/></svg>رد الموظف</span>\n' : ''}${m.media ? MEDIA(m) : ''}${m.media && /^\[(صورة|فيديو|رسالة صوتية|ملصق|ملف)\]$/.test(m.text) ? '' : esc(m.text)}<time>${fmtT(m.ts)}</time></div>` }).join('') : '<div class="empty">ما فيه رسائل</div>';
  ms.scrollTop = ms.scrollHeight; if (!full) suggest();
}
let SUG = [], PREFILL = null, PRETEXT = null;
function drawSugs() {
  const t = (SET.templates || []).map((x, i) => `<button class="sug tpl" data-t="${i}" title="${esc(x.t)}">${esc(x.k)}</button>`).join('');
  const s = SUG.map((r, i) => `<button class="sug" data-s="${i}" title="${esc(r)}">${nice(r)}</button>`).join('');
  $('#sg').innerHTML = (s ? `<div class="sugrow"><span class="sug-l">مقترح</span>${s}</div>` : '') + (t ? `<div class="sugrow"><span class="sug-l">جاهز</span>${t}</div>` : '');
  $('#sg').querySelectorAll('[data-t]').forEach(b => b.onclick = () => ins(SET.templates[b.dataset.t].t)); $('#sg').querySelectorAll('[data-s]').forEach(b => b.onclick = () => ins(SUG[b.dataset.s], true));
}
function ins(t, replace) { const tx = $('#tx'); tx.value = replace || !tx.value ? t : tx.value + ' ' + t; tx.focus(); tx.dispatchEvent(new Event('input')); $('#sl').hidden = true }
function slash() {
  const v = $('#tx').value, sl = $('#sl'); if (!v.startsWith('/')) { sl.hidden = true; return } const q = v.slice(1); const l = (SET.templates || []).filter(x => (x.k + x.t).includes(q));
  sl.innerHTML = l.map(x => `<div data-i="${SET.templates.indexOf(x)}"><b>/${esc(x.k)}</b> <small class="muted">${esc(x.t.slice(0, 60))}</small></div>`).join('') || '<div class="muted">ما فيه رد بهذا الاسم</div>'; sl.hidden = false;
  sl.querySelectorAll('[data-i]').forEach(d => d.onclick = () => ins(SET.templates[d.dataset.i].t, true));
}
async function suggest() { const j0 = CH; try { const j = await api('api/ai/suggest', { jid: CH }); if (j0 !== CH) return; SUG = j.replies || [] } catch { SUG = [] } if ($('#sg')) drawSugs(); if (PREFILL === CH && SUG[0] && $('#tx') && !$('#tx').value) { ins(SUG[0], true); toast('جهزنا لك رد مقترح — راجعه واضغط «إرسال»') } if (PREFILL === CH) PREFILL = null }
async function send() {
  const text = $('#tx').value.trim(); if (!text) { $('#tx').focus(); return toast('اكتب الرد أول') }
  const c = CL.find(x => x.jid === CH); if (!await ask('ترسل هذي الرسالة؟', `<p class="muted" style="margin-bottom:8px">إلى: <b>${esc(c ? who(c) : '')}</b></p><div class="quote">${esc(text)}</div>`, 'إرسال')) return;
  const b = $('#sd'); b.disabled = true;
  try { await api('api/send', { jid: CH, text, confirm: true }); $('#tx').value = ''; $('#tx').style.height = ''; lastSig = ''; await drawThread(); loadChats(); toast('انرسلت ✓') }
  catch (e) { toast('ما انرسلت: ' + e.message) } b.disabled = false;
}
async function saveCRM(data) { CRM[CH] = await api('api/crm', { jid: CH, data }); return CRM[CH] }
function drawPanel(c) {
  const cr = c.crm || {}, sp = $('#sp'); let tag = cr.tag || 'جديد', ORD = [...(cr.orders || [])];
  sp.innerHTML = `<h3 style="display:flex;align-items:center">معلومات العميل<button class="icon-btn" id="cpx" aria-label="إغلاق" style="margin-inline-start:auto"><svg><use href="#i-x"/></svg></button></h3>
  <div id="pf" class="profile"><div class="skel"></div><div class="skel" style="width:70%"></div></div>
  <label class="lbl">التصنيف</label><div class="filters" id="tg">${(SET.tags || []).map(t => `<button class="${tag === t ? 'on' : ''}" data-t="${esc(t)}" aria-pressed="${tag === t}">${esc(t)}</button>`).join('')}</div>
  <label class="lbl" for="fu">موعد متابعة</label><input type="date" id="fu" value="${esc(cr.followUp || '')}">
  <label class="lbl" for="nt">ملاحظات (ما يشوفها العميل)</label><textarea id="nt" placeholder="مثلاً: يحب الجوري الأبيض">${esc(cr.note || '')}</textarea>
  <h3 style="margin-top:18px;display:flex;align-items:center">الطلبات<button class="btn sm soft" id="ex" style="margin-inline-start:auto"><svg aria-hidden="true"><use href="#i-spark"/></svg>طلّع الطلب</button></h3>
  <div id="exo"></div><div id="od"></div>
  <label class="lbl" for="oi">إضافة طلب</label><input id="oi" placeholder="الطلب، مثلاً: بوكيه جوري">
  <div class="grid g2" style="gap:8px;margin-top:8px"><input id="oa" type="number" min="0" inputmode="numeric" placeholder="المبلغ" aria-label="المبلغ"><input type="date" id="odd" aria-label="موعد التوصيل"></div>
  <button class="btn sm" id="oad" style="margin-top:8px">+ أضف الطلب</button>
  <button class="btn primary block" id="sv" style="margin-top:18px">حفظ الملف</button>`;
  loadProfile(c.jid);
  const drawO = () => { $('#od').innerHTML = ORD.length ? ORD.map((o, i) => `<div class="order"><div class="grow"><b class="ell" style="display:block">${esc(o.item)}</b><small class="muted">${money(o.amount)}${o.deliveryDate ? ' · ' + fdate(o.deliveryDate) : ''}</small></div>
    <select data-i="${i}" aria-label="حالة الطلب" style="width:auto;min-height:36px">${STAGES.map(x => `<option ${(o.status || 'جديد') === x ? 'selected' : ''}>${x}</option>`).join('')}</select></div>`).join('') : '<p class="muted" style="font-size:14px">ما فيه طلبات مسجّلة</p>';
    $('#od').querySelectorAll('select').forEach(s => s.onchange = () => ORD[s.dataset.i].status = s.value) }; drawO();
  $('#cpx').onclick = () => $('#cw').classList.remove('panel');
  $('#tg').querySelectorAll('button').forEach(b => b.onclick = () => { tag = b.dataset.t; $('#tg').querySelectorAll('button').forEach(x => { x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', x === b) }) });
  $('#oad').onclick = () => { const it = $('#oi').value.trim(); if (!it) { $('#oi').focus(); return toast('اكتب الطلب أول') } ORD.push({ item: it, amount: +$('#oa').value || 0, deliveryDate: $('#odd').value, status: 'جديد', date: Date.now() }); $('#oi').value = $('#oa').value = $('#odd').value = ''; drawO() };
  $('#sv').onclick = async () => { try { await saveCRM({ tag, followUp: $('#fu').value, note: $('#nt').value, orders: ORD }); toast('انحفظ ✓'); loadChats() } catch (x) { toast('تعذّر الحفظ') } };
  $('#ex').onclick = async e => { const b = e.currentTarget; b.disabled = true; $('#exo').innerHTML = '<div class="skel"></div>';
    try { const j = await api('api/ai/extract', { jid: CH });
      $('#exo').innerHTML = `<div class="notice b" style="margin-top:8px"><b>${esc(j.stage)} · احتمال الشراء ${num(j.score)}٪</b><div style="font-size:14px">${esc(j.reason)}</div>${j.missing?.length ? `<div style="font-size:14px">ناقص: ${esc(j.missing.join('، '))}</div>` : ''}
       ${(j.orders || []).map((o, i) => `<div class="order" style="background:var(--card)"><div class="grow">${esc(o.item)} — ${money(o.amount)}${o.deliveryDate ? ' · ' + fdate(o.deliveryDate) : ''}${o.address ? `<div><small>${esc(o.address)}</small></div>` : ''}</div><button class="btn sm primary" data-i="${i}">أضف</button></div>`).join('') || '<div style="font-size:14px">ما لقيت طلب واضح في المحادثة</div>'}</div>`;
      $('#exo').querySelectorAll('[data-i]').forEach(x => x.onclick = () => { const o = j.orders[x.dataset.i]; ORD.push({ item: o.item, amount: +o.amount || 0, deliveryDate: o.deliveryDate || '', status: 'جديد', date: Date.now(), address: o.address || '' }); drawO(); x.remove(); toast('أضفناه — اضغط «حفظ الملف»') });
      if (j.stage && (SET.tags || []).includes(j.stage)) { tag = j.stage; $('#tg').querySelectorAll('button').forEach(x => x.classList.toggle('on', x.dataset.t === tag)) } }
    catch (x) { $('#exo').innerHTML = `<p class="err">${x.code === 'brain_off' ? 'المساعد مقفل من الإعدادات' : 'تعذّر الاستخراج'}</p>` } b.disabled = false };
}
// smart customer profile: filled by the local brain from the chat; every field editable with one click, nothing to type
const PFIELDS = [['name', 'الاسم'], ['district', 'الحي'], ['city', 'المدينة'], ['occasions', 'المناسبة'], ['items', 'سأل عن'], ['budget', 'الميزانية'], ['value', 'قيمة العميل'], ['sentiment', 'المزاج'], ['nextAction', 'الخطوة الجاية'], ['followUp', 'موعد المتابعة']];
async function loadProfile(jid) {
  let c; try { c = await api('api/chat?profile=1&jid=' + encodeURIComponent(jid)) } catch { return } if (CH !== jid || !$('#pf')) return;
  const p = c.profile || {}, box = $('#pf');
  if (!p || p.empty || !Object.keys(p).length) { box.innerHTML = '<p class="muted" style="font-size:14px">الملف يتعبّى تلقائياً أول ما يكتب العميل.</p>'; return }
  const show = (k, v) => v == null || v === '' || (Array.isArray(v) && !v.length) ? '' : k === 'budget' ? money(v) : k === 'followUp' ? fdate(v) : Array.isArray(v) ? v.join('، ') : v;
  const vChip = { VIP: 'r', 'عالي': 'g', 'متوسط': 'b', 'جديد': '' }, sChip = { 'إيجابي': 'g', 'سلبي': 'x', 'محايد': '' };
  box.innerHTML = `<div class="pf-top"><span class="chip ${vChip[p.value] ?? ''}">${esc(p.value || 'جديد')}</span>${p.sentiment ? `<span class="chip ${sChip[p.sentiment] ?? ''}">${esc(p.sentiment)}</span>` : ''}${p.temperature ? `<span class="chip">${esc(p.temperature)}</span>` : ''}
   ${p.spent ? `<span class="chip g">صرف ${money(p.spent)} · ${num(p.orders)} طلب</span>` : p.orders ? `<span class="chip">${num(p.orders)} طلب</span>` : ''}</div>
   ${p.nextAction ? `<div class="next"><small>الخطوة الجاية</small><b>${esc(p.nextAction)}</b></div>` : ''}
   <dl class="pf">${PFIELDS.filter(([k]) => k !== 'nextAction').map(([k, l]) => { const v = show(k, p[k]); return `<div class="pf-r"><dt>${l}${(p.edited || []).includes(k) ? ' <small class="muted">(معدّل)</small>' : ''}</dt><dd>${v ? (k === 'name' || k === 'district' ? B(v) : esc(v)) : '<span class="muted">—</span>'}</dd><button class="icon-btn sm" data-e="${k}" aria-label="تعديل ${l}"><svg><use href="#i-edit"/></svg></button></div>` }).join('')}</dl>
   <small class="muted">يتحدث تلقائياً من المحادثة. اضغط ✎ لتعديل أي معلومة.</small>`;
  box.querySelectorAll('[data-e]').forEach(b => b.onclick = () => { const k = b.dataset.e, r = b.closest('.pf-r'), cur = Array.isArray(p[k]) ? p[k].join('، ') : (p[k] ?? '');
    r.querySelector('dd').innerHTML = `<input ${k === 'followUp' ? 'type="date"' : k === 'budget' ? 'type="number" min="0"' : ''} value="${esc(cur)}" aria-label="${esc(b.getAttribute('aria-label'))}">`; const i = r.querySelector('input'); i.focus();
    const save = async () => { let v = i.value.trim(); if (['occasions', 'items'].includes(k)) v = v.split(/[،,]/).map(x => x.trim()).filter(Boolean); if (k === 'budget') v = +v || ''; try { await saveCRM({ profileEdit: { [k]: v } }); toast('انحفظ ✓') } catch { toast('تعذّر الحفظ') } loadProfile(jid) };
    i.onkeydown = e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') loadProfile(jid) }; i.onblur = save });
}
// ---------- SALES (orders + pipeline + reports)
async function renderSales() {
  const el = $('#p-sales'); let d, O; try { await loadChats(); [d, O] = await Promise.all([api('api/dashboard'), api('api/orders')]) } catch { el.innerHTML = errBox('ما قدرنا نجيب الطلبات', renderSales); return }
  const a = d.analytics, A = ST.analysis;
  const cols = (SET.tags || []).map(t => { const cs = CL.filter(c => c.tag === t);
    return `<div class="col"><h4><span>${esc(t)}</span><span class="chip">${num(cs.length)}</span></h4>${cs.slice(0, 30).map(c => `<button class="deal" data-j="${esc(c.jid)}"><b class="ell" style="display:block">${esc(who(c))}</b><small class="muted">${ago(c.lastAt)}${c.score >= SET.hotScore ? ' · ساخن' : ''}</small></button>`).join('') || '<p class="muted" style="font-size:14px">ما فيه أحد</p>'}</div>` }).join('');
  el.innerHTML = `<div class="page-h"><div><h1>الطلبات والعملاء</h1><p>كل طلب مسجّل، ومكان كل عميل في مسار البيع.</p></div></div>
  <div class="grid kpis" style="margin-bottom:var(--s4)"><div class="kpi main"><div class="v">${money(a.revenue)}</div><div class="l">إجمالي المبيعات</div></div><div class="kpi"><div class="v">${num(a.orders)}</div><div class="l">طلب</div></div><div class="kpi"><div class="v">${num(a.avgOrder)}</div><div class="l">متوسط الطلب (ر.س)</div></div><div class="kpi"><div class="v">${num(a.buyers)}</div><div class="l">عميل اشترى</div></div></div>
  <div class="card" style="margin-bottom:var(--s4)"><h3><svg aria-hidden="true"><use href="#i-box"/></svg>الطلبات</h3>${O.length ? `<div style="overflow-x:auto"><table class="tbl"><thead><tr><th>الطلب</th><th>العميل</th><th>المبلغ</th><th>التوصيل</th><th>الحالة</th></tr></thead><tbody>${O.map(o => `<tr><td><b>${esc(o.item)}</b>${o.address ? `<div><small class="muted">${esc(o.address)}</small></div>` : ''}</td><td><button class="btn sm ghost" data-j="${esc(o.jid)}">${esc(o.name)}</button></td><td style="white-space:nowrap">${money(o.amount)}</td><td style="white-space:nowrap">${o.deliveryDate ? fdate(o.deliveryDate) : '—'}</td>
   <td><select data-oj="${esc(o.jid)}" data-oi="${o.i}" aria-label="حالة الطلب">${STAGES.map(x => `<option ${(o.status || 'جديد') === x ? 'selected' : ''}>${x}</option>`).join('')}</select></td></tr>`).join('')}</tbody></table></div>` : '<div class="empty"><b>ما فيه طلبات للحين</b>افتح محادثة عميل واضغط «طلّع الطلب» أو أضفه يدوي من ملف العميل.</div>'}</div>
  <div class="card" style="margin-bottom:var(--s4)"><h3>مسار العملاء</h3><div class="pipe">${cols}</div></div>
  <div class="card"><h3>ترتيب كل المحادثات وتصديرها<button class="btn sm primary act" id="org">رتّب الحين</button></h3>
  ${A ? `<p>${esc(A.summary)}</p><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px"><a class="btn" href="report.html" target="_blank" rel="noopener">تقرير للطباعة</a><a class="btn" href="contacts.vcf" download>جهات اتصال VCF</a><a class="btn" href="contacts.csv" download>ملف Excel ‏CSV</a></div>` : '<p class="muted">اضغط «رتّب الحين» ونرتب لك كل المحادثات: مين طلب، وش المعلّق، ومين ما انرد عليه — وتقدر تصدّرها.</p>'}</div>`;
  el.querySelectorAll('[data-j]').forEach(x => x.onclick = () => openChat(x.dataset.j));
  el.querySelectorAll('select[data-oj]').forEach(s => s.onchange = async () => { try { await api('api/orders/status', { jid: s.dataset.oj, i: +s.dataset.oi, status: s.value }); toast('تم تحديث الطلب') } catch { toast('تعذّر التحديث') } });
  $('#org').onclick = async e => { const b = e.currentTarget; b.disabled = true; b.textContent = 'نرتّب…'; try { ST.analysis = await api('api/analyze', {}); renderSales() } catch { toast('تعذّر الترتيب'); b.disabled = false; b.textContent = 'رتّب الحين' } };
}
// ---------- MARKETING
// ---------- MARKETING (v2.3): a few ranked, ready actions. Every message is a draft the owner opens and sends himself.
let MKT = null, MKTD = {};
async function renderMkt() {
  const el = $('#p-mkt');
  el.innerHTML = `<div class="page-h"><div><h1>التسويق</h1><p>أهم الخطوات اليوم، مرتبة من الأقوى. الرسالة جاهزة، وأنت تفتح المحادثة وترسل بنفسك.</p></div></div><div id="mk"><div class="skel" style="height:160px"></div><div class="skel" style="height:160px"></div></div>`;
  try { MKT = await api('api/mkt/actions') } catch { $('#mk').innerHTML = errBox('ما قدرنا نجهز التسويق', renderMkt); return }
  const left = Math.max(0, MKT.cap - MKT.opened);
  $('#mk').innerHTML = `<div class="mk-cap"><svg aria-hidden="true"><use href="#i-check"/></svg><span>عشان رقمك يبقى بأمان: أرسل لـ ${num(MKT.cap)} عميل بالكثير باليوم، وحدة وحدة. باقي لك اليوم <b>${num(left)}</b>.</span></div>
   <ol class="mk-list">${MKT.actions.map((a, i) => `<li class="mk ${i === 0 ? 'top' : ''}" data-id="${a.id}"><div class="mk-h"><span class="mk-n">${num(i + 1)}</span><div class="grow"><h3>${esc(a.title)}</h3><p>${esc(a.why)}</p></div></div>
     <div class="mk-draft"><textarea data-t="${a.id}" rows="3" aria-label="نص الرسالة">${esc(MKTD[a.id] || a.template)}</textarea>
      <div class="mk-act"><button class="btn sm soft" data-ai="${a.id}"><svg aria-hidden="true"><use href="#i-spark"/></svg>اكتبها بالذكاء</button><button class="btn sm ghost" data-cp="${a.id}">نسخ</button>${a.status ? '<span class="muted">انسخها وحطها في حالتك مع صورة ورد اليوم</span>' : `<span class="muted">${num(a.people.length)} عميل</span>`}</div></div>
     ${a.people.length ? `<div class="mk-people">${a.people.slice(0, i === 0 ? 8 : 4).map(p => `<button class="mk-p" data-open="${esc(p.jid)}" data-a="${a.id}"><span class="av" style="--h:${hue(p.jid)}">${ini(p.label)}</span><span class="grow ell">${esc(p.label)}${p.item ? `<small>${esc(p.item)}</small>` : ''}</span><span class="go">افتح وأرسل</span></button>`).join('')}${a.people.length > (i === 0 ? 8 : 4) ? `<button class="btn sm ghost mk-more" data-more="${a.id}">اعرض الباقين (${num(a.people.length - (i === 0 ? 8 : 4))})</button>` : ''}</div>` : ''}</li>`).join('')}</ol>`;
  const txt = id => $(`[data-t="${id}"]`).value;
  $$('[data-t]').forEach(t => t.oninput = () => MKTD[t.dataset.t] = t.value);
  $$('[data-cp]').forEach(b => b.onclick = () => navigator.clipboard.writeText(txt(b.dataset.cp).replace(/\{الاسم\}\s*/g, '')).then(() => toast('انسخت ✓'), () => toast('ما قدرنا ننسخ')));
  $$('[data-ai]').forEach(b => b.onclick = async () => { const a = MKT.actions.find(x => x.id === b.dataset.ai); b.disabled = true; const o = b.innerHTML; b.textContent = 'يكتب…';
    try { const r = await api('api/mkt/draft', { goal: a.goal, template: txt(a.id) }); MKTD[a.id] = r.text; $(`[data-t="${a.id}"]`).value = r.text; toast(r.engine === 'ai' ? 'كتبها الذكاء المحلي — عدّلها براحتك' : 'الذكاء مو متاح الحين، خليناها مثل ما هي') } catch { toast('ما ضبط') } b.disabled = false; b.innerHTML = o });
  $$('[data-more]').forEach(b => b.onclick = () => { const a = MKT.actions.find(x => x.id === b.dataset.more); const box = b.parentElement; b.remove();
    box.insertAdjacentHTML('beforeend', a.people.slice(box.querySelectorAll('.mk-p').length).map(p => `<button class="mk-p" data-open="${esc(p.jid)}" data-a="${a.id}"><span class="av" style="--h:${hue(p.jid)}">${ini(p.label)}</span><span class="grow ell">${esc(p.label)}</span><span class="go">افتح وأرسل</span></button>`).join('')); bindOpen() });
  const bindOpen = () => $$('.mk-p').forEach(b => b.onclick = async () => { if (MKT.opened >= MKT.cap) return toast('وصلت حد اليوم — كمل بكرة عشان رقمك يبقى بأمان');
    const p = MKT.actions.find(x => x.id === b.dataset.a).people.find(x => x.jid === b.dataset.open); PRETEXT = { jid: p.jid, text: txt(b.dataset.a).replace(/\{الاسم\}/g, p.first || '').replace(/هلا\s+،/, 'هلا،') };
    try { const r = await api('api/mkt/opened', { jid: p.jid }); MKT.opened = r.opened } catch { } openChat(p.jid) });
  bindOpen();
}
// ---------- EMPLOYEE (auto-reply)
const AUDIT_AR = { manual_send: 'إرسال منك', auto_reply: 'رد الموظف', auto_handoff: 'الموظف حوّله لك', auto_skip: 'الموظف ما رد', auto_reply_failed: 'فشل رد الموظف', auto_reply_enabled: 'تشغيل الموظف', auto_reply_disabled: 'إيقاف الموظف',
  login: 'دخول', login_failed: 'محاولة دخول فاشلة', password_changed: 'تعيين كلمة المرور', password_removed: 'إزالة كلمة المرور', settings_changed: 'تعديل الإعدادات', whatsapp_linked: 'ربط الواتساب', whatsapp_unlinked: 'فصل الواتساب', order_status: 'تحديث طلب', send_failed: 'فشل إرسال' };
const auditRow = a => `<div class="row"><span class="chip ${a.type === 'auto_reply' ? 'g' : a.type === 'auto_handoff' ? 'w' : /failed/.test(a.type) ? 'x' : ''}">${esc(AUDIT_AR[a.type] || a.type)}</span><div class="grow">${a.to ? `<b>${esc(a.to)}</b>` : ''}${a.why ? ` <span class="muted">— ${esc(a.why)}</span>` : ''}${a.q ? `<div style="font-size:14px">العميل: «${esc(a.q)}»</div>` : ''}${a.preview ? `<div class="muted" style="font-size:14px">${esc(a.preview)}</div>` : ''}${a.err ? `<div class="err">${esc(a.err)}</div>` : ''}</div><small class="muted" style="white-space:nowrap">${ago(a.t)}</small></div>`;
async function renderEmp() {
  const el = $('#p-emp'), ar = SET.autoReply, e = ST.employee || {};
  const statusTxt = !ar.enabled ? 'مطفي — ما يرد على أحد' : e.active ? 'شغّال الحين ويرد على العملاء' : 'مشغّل، بس الحين مو وقته (حسب الوقت اللي اخترته)';
  el.innerHTML = `<div class="emp-hero ${ar.enabled ? 'on' : ''}"><div class="ic"><svg aria-hidden="true"><use href="#i-bot"/></svg></div><div class="grow"><h2>الموظف ${ar.enabled ? 'شغّال' : 'مطفي'}</h2><p>${statusTxt}</p></div>
   <label class="bigswitch" title="تشغيل/إيقاف الموظف"><input type="checkbox" id="e0" ${ar.enabled ? 'checked' : ''} aria-label="تشغيل الموظف"><span></span></label></div>
  ${ST.status !== 'connected' ? '<div class="notice" style="margin-bottom:16px">الواتساب غير مربوط، فالموظف ما يقدر يرد لين تربطه.</div>' : ''}
  <div class="grid g2"><div class="card"><h3>متى يرد؟</h3><div class="choice" id="sch">
    ${[['always', 'دايم', 'يرد على أي رسالة في أي وقت'], ['offhours', 'خارج الدوام فقط', `برا ساعات المحل (${hm12(SET.hoursFrom)} – ${hm12(SET.hoursTo)})`], ['custom', 'وقت أحدده', 'من ساعة إلى ساعة']].map(([v, l, h]) => `<label><input type="radio" name="sch" value="${v}" ${ar.schedule === v ? 'checked' : ''}><span><b>${l}</b><small>${h}</small></span></label>`).join('')}</div>
    <div class="grid g2" id="cust" ${ar.schedule === 'custom' ? '' : 'hidden'} style="gap:8px"><div><label class="lbl" for="e1">من الساعة</label><input type="time" id="e1" value="${esc(ar.from)}"></div><div><label class="lbl" for="e2">إلى الساعة</label><input type="time" id="e2" value="${esc(ar.to)}"></div></div>
    <h3 style="margin-top:22px">وش يرد؟</h3><div class="choice">
    <label><input type="radio" name="mode" value="smart" ${ar.mode === 'smart' ? 'checked' : ''}><span><b>رد ذكي</b><small>يفهم العميل ويرد: ترحيب، أوقات الدوام، التوصيل، معاني الورد، العناية… من معلومات محلك.</small></span></label>
    <label><input type="radio" name="mode" value="fixed" ${ar.mode === 'fixed' ? 'checked' : ''}><span><b>رسالة ثابتة</b><small>نفس الرسالة لكل عميل.</small></span></label></div>
    <label class="lbl" for="e3">الرسالة الثابتة</label><textarea id="e3" style="min-height:72px">${esc(ar.message)}</textarea></div>
   <div class="card"><h3>الأمان والحدود</h3>
    <div class="setrow"><div class="grow"><b>حوّل لي الطلبات والأسعار والشكاوى</b><div class="help-t">يرد على العميل «لحظات» وينبهك ترد بنفسك. ننصح تخليه شغّال.</div></div><label class="switch"><input type="checkbox" id="e4" ${ar.handoff ? 'checked' : ''} aria-label="تحويل الطلبات لي"><span></span></label></div>
    <label class="lbl" for="e5">رسالة التحويل</label><textarea id="e5" style="min-height:72px">${esc(ar.handoffMessage)}</textarea>
    <div class="grid g2" style="gap:8px"><div><label class="lbl" for="e6">ينتظر قبل الرد (ثانية)</label><input type="number" id="e6" min="0" max="600" value="${ar.delaySec}"></div>
    <div><label class="lbl" for="e7">أقل وقت بين ردّين لنفس العميل (دقيقة)</label><input type="number" id="e7" min="0" max="1440" value="${ar.cooldownMin}"></div>
    <div><label class="lbl" for="e8">أقصى ردود للعميل باليوم</label><input type="number" id="e8" min="1" max="50" value="${ar.maxPerDay}"></div>
    <div><label class="lbl" for="e9">يسكت إذا رديت أنت خلال (دقيقة)</label><input type="number" id="e9" min="0" max="240" value="${ar.ownerActiveMin}"></div></div>
    <p class="help-t" style="margin-top:10px">ما يرد أبداً على القروبات أو الحالات، ولا على أي عميل كتب «وقف».</p>
    <h3 style="margin-top:22px">حماية الرقم من الحظر</h3>
    <div class="notice g" style="font-size:14px">الموظف <b>ما يبدأ محادثة أبداً</b> — يرد بس على اللي كتب لك. يقرأ الرسالة، يطلع «يكتب…» بوقت يناسب طول الرد، ويترك فاصل عشوائي بين الردود.${e.guard ? `<br>اليوم: ${num(e.guard.day)} من ${num(e.guard.perDay)} رد · هالساعة: ${num(e.guard.hour)} من ${num(e.guard.perHour)}${e.guard.warm ? '<br><b>رقم مربوط جديد:</b> نبدأ بحد أقل ونزيده تدريجياً خلال أسبوع (تسخين).' : ''}` : ''}</div>
    ${SW('e10', ar.humanTyping !== false, 'يكتب مثل الإنسان', 'قراءة ← «يكتب…» ← إرسال، بأوقات طبيعية')}
    <div class="grid g2" style="gap:8px"><div><label class="lbl" for="e11">أقصى ردود بالساعة (كل العملاء)</label><input type="number" id="e11" min="1" max="60" value="${ar.maxPerHour ?? 20}"></div>
    <div><label class="lbl" for="e12">أقصى ردود باليوم (كل العملاء)</label><input type="number" id="e12" min="1" max="200" value="${ar.maxTotalPerDay ?? 80}"></div></div>
    <button class="btn primary" id="esv" style="margin-top:16px">حفظ الإعدادات</button></div></div>
  <div class="card" style="margin-top:var(--s4)"><div style="display:flex;align-items:center;gap:12px"><div class="grow"><h3 style="margin:0">فحص الموظف</h3><p class="muted" style="font-size:14px;margin:4px 0 0">ما رد على أحد؟ اضغط ونقولك السبب بالضبط.</p></div><button class="btn primary" id="echk">افحص الحين</button></div><div id="echo"></div></div>
  <div class="grid g2" style="margin-top:var(--s4)"><div class="card"><h3>جرّب الموظف</h3><p class="muted" style="font-size:14px;margin-top:-6px">اكتب رسالة كأنك عميل وشوف وش بيرد. (ما ينرسل شي)</p>
    <div class="bar" style="margin-top:10px"><input id="et" placeholder="مثلاً: متى تفتحون؟" aria-label="رسالة تجربة"><button class="btn" id="etb">جرّب</button></div><div id="eto" style="margin-top:12px"></div></div>
   <div class="card"><h3>آخر شغل الموظف</h3><div id="elog" class="audit"><div class="skel"></div></div></div></div>`;
  $$('input[name=sch]').forEach(r => r.onchange = () => $('#cust').hidden = r.value !== 'custom' || !r.checked);
  const body = () => ({ schedule: $('input[name=sch]:checked').value, mode: $('input[name=mode]:checked').value, from: $('#e1').value, to: $('#e2').value, message: $('#e3').value, handoff: $('#e4').checked, handoffMessage: $('#e5').value, delaySec: +$('#e6').value, cooldownMin: +$('#e7').value, maxPerDay: +$('#e8').value, ownerActiveMin: +$('#e9').value, humanTyping: $('#e10').checked, maxPerHour: +$('#e11').value, maxTotalPerDay: +$('#e12').value });
  $('#e0').onchange = async ev => { const on = ev.target.checked;
    if (on && !await ask('تشغّل الموظف؟', `<p>بيرد على عملائك تلقائياً <b>${{ always: 'في أي وقت', offhours: 'خارج الدوام', custom: `من ${hm12($('#e1').value)} إلى ${hm12($('#e2').value)}` }[$('input[name=sch]:checked').value]}</b>${$('#e4').checked ? '، ويحوّل لك الطلبات والأسعار والشكاوى' : ''}. كل رد ينسجل وتقدر تطفيه بأي وقت.</p>`, 'شغّله')) { ev.target.checked = false; return }
    try { SET = await api('api/settings', { autoReply: { ...body(), enabled: on } }); await tick(); toast(on ? 'الموظف شغّال ✓' : 'انطفى الموظف'); renderEmp() } catch { ev.target.checked = !on; toast('تعذّر الحفظ') } };
  $('#esv').onclick = async () => { try { SET = await api('api/settings', { autoReply: body() }); await tick(); toast('انحفظ ✓'); renderEmp() } catch { toast('تعذّر الحفظ') } };
  const tryIt = async () => { const t = $('#et').value.trim(); if (!t) return $('#et').focus(); try { const j = await api('api/employee/test', { text: t });
    $('#eto').innerHTML = j.action === 'skip' ? `<div class="notice">ما بيرد: ${esc(j.reason === 'customer_said_stop' ? 'العميل طلب ما نراسله' : j.reason)}</div>` : `<div class="notice ${j.action === 'handoff' ? '' : 'g'}"><b>${j.action === 'handoff' ? 'بيحوّله لك ويرد:' : 'بيرد:'}</b><div style="white-space:pre-wrap;margin-top:4px">${esc(j.text)}</div></div>` } catch (x) { toast('تعذّر: ' + x.message) } };
  $('#echk').onclick = async () => { const o = $('#echo'); o.innerHTML = '<div class="skel" style="height:120px;margin-top:12px"></div>';
    try { const j = await api('api/employee/check'); const AR = { auto_reply: 'رد', auto_handoff: 'رد وحوّله لك', auto_skip: 'ما رد', auto_reply_failed: 'فشل', auto_reply_disabled: 'توقف' };
      o.innerHTML = `<div class="notice ${j.ok ? 'g' : ''}" style="margin-top:12px">${j.ok ? 'كل شي سليم، الموظف بيرد على أول رسالة توصل ✓' : 'فيه شي يمنع الموظف يرد، شوف اللي بالأحمر تحت'}</div>
      <ul class="chk">${j.checks.map(c => `<li class="${c.ok ? 'ok' : 'no'}"><span aria-hidden="true">${c.ok ? '✓' : '✕'}</span>${esc(c.text)}</li>`).join('')}</ul>
      ${j.recent.length ? `<h4 style="margin:14px 0 6px">آخر قرارات الموظف</h4>${j.recent.map(a => `<div class="row"><span class="chip ${a.type === 'auto_skip' ? 'w' : /fail|disabled/.test(a.type) ? 'x' : 'g'}">${AR[a.type] || a.type}</span><div class="grow">${esc(a.to || '')} <small class="muted">${esc(a.why)}</small></div><small class="muted">${ago(a.t)}</small></div>`).join('')}` : '<p class="muted">ما وصلت رسائل للموظف للحين.</p>'}` }
    catch (e) { o.innerHTML = `<p class="err">${esc(e.message)}</p>` } };
  $('#etb').onclick = tryIt; $('#et').onkeydown = e => { if (e.key === 'Enter') tryIt() };
  try { const l = (await api('api/audit')).filter(a => /^auto_/.test(a.type)).slice(0, 12); $('#elog').innerHTML = l.length ? l.map(auditRow).join('') : '<div class="empty"><b>ما رد على أحد للحين</b>أول ما يرد يطلع هنا.</div>' } catch { $('#elog').innerHTML = '<p class="err">تعذّر تحميل السجل</p>' }
}
// ---------- SETTINGS
let SETTAB = 'shop';
const SETTABS = [['teach', 'تعليم الموظف'], ['shop', 'المحل'], ['prices', 'الأسعار والمنتجات'], ['tpl', 'الردود الجاهزة'], ['brain', 'المساعد'], ['rules', 'المتابعة والتنبيهات'], ['brand', 'الشكل والهوية'], ['sec', 'القفل والأمان'], ['log', 'السجل'], ['wa', 'الواتساب'], ['about', 'عن البرنامج']];
async function renderSet() {
  const el = $('#p-set'), s = SET; let logo = s.logo, brandC = s.brand, T = (s.templates || []).map(x => ({ ...x })), P = (s.products || []).map(x => ({ ...x }));
  const sw = (id, v, l, h) => `<div class="setrow"><div class="grow"><b>${l}</b>${h ? `<div class="help-t">${h}</div>` : ''}</div><label class="switch"><input type="checkbox" id="${id}" ${v ? 'checked' : ''} aria-label="${esc(l)}"><span></span></label></div>`;
  const body = {
    teach: '<div id="teachbox"></div>',
    shop: `<h3>بيانات المحل</h3><label class="lbl" for="s1">اسم المحل</label><input id="s1" value="${esc(s.shopName)}"><div class="grid g2" style="gap:12px"><div><label class="lbl" for="s2">النشاط</label><input id="s2" value="${esc(s.shopType)}"></div><div><label class="lbl" for="s3">المدينة</label><input id="s3" value="${esc(s.city)}"></div></div>
     <div class="grid g2" style="gap:12px"><div><label class="lbl" for="s6">يفتح الساعة</label><input type="time" id="s6" value="${esc(s.hoursFrom)}"></div><div><label class="lbl" for="s7">يقفل الساعة</label><input type="time" id="s7" value="${esc(s.hoursTo)}"></div></div>
     <label class="lbl" for="s4">نبذة عن المحل</label><textarea id="s4" placeholder="وش تبيعون، وش يميزكم…">${esc(s.about)}</textarea><label class="lbl" for="s5">التوصيل والدفع</label><textarea id="s5" style="min-height:72px" placeholder="مثلاً: نوصل داخل المدينة بـ ٣٠ ريال، والدفع تحويل أو مدى">${esc(s.delivery)}</textarea>`,
    prices: `<h3>الأسعار والمنتجات</h3><p class="muted" style="font-size:14px">المساعد ما يذكر للعميل أي سعر غير الموجود هنا. اتركها فاضية ويستخدم القائمة الافتراضية.</p>
     <div class="prod" style="margin-top:14px;font-weight:700;font-size:13px;color:var(--muted)"><span>المنتج</span><span>السعر (ر.س)</span><span>أسماء ثانية يقولها العميل</span><span></span></div><div id="pl"></div>
     <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px"><button class="btn sm" id="pa">+ منتج</button><button class="btn sm ghost" id="pd">عبّها بالقائمة الافتراضية</button></div>`,
    tpl: `<h3>الردود الجاهزة</h3><p class="muted" style="font-size:14px">تطلع كأزرار تحت خانة الرد، أو اكتب / واختر. الضغط يحط النص فقط — الإرسال بيدك.</p><div id="tl" style="margin-top:12px"></div><button class="btn sm" id="ta">+ رد جديد</button>
     <label class="lbl" for="tg2">تصنيفات العملاء (افصل بفاصلة)</label><input id="tg2" value="${esc((s.tags || []).join('، '))}">`,
    brain: `<h3>المساعد</h3><div class="notice g">مساعد سعودي يشتغل على جهازك بدون نت وبدون اشتراك: يفهم وش يبي العميل، يقترح ردود، يطلّع الطلبات من المحادثة، ويقيّم العملاء.</div>
     ${sw('a1', s.aiEnabled, 'تشغيل المساعد', 'الاقتراحات، استخراج الطلبات، تقييم العملاء، والرد الذكي للموظف')}
     <label class="lbl" for="a2">أسلوب الكلام</label><select id="a2">${['ودودة ومحترفة', 'رسمية', 'شبابية خفيفة', 'فخمة وراقية'].map(t => `<option ${s.aiTone === t ? 'selected' : ''}>${t}</option>`).join('')}</select>`,
    rules: `<h3>المتابعة والتنبيهات</h3><div class="grid g2" style="gap:12px"><div><label class="lbl" for="u1">ذكّرني إذا ما رديت على عميل بعد (يوم)</label><input type="number" id="u1" value="${s.followUpDays}" min="0" max="60"></div><div><label class="lbl" for="u2">العميل يعتبر قديم بعد (يوم)</label><input type="number" id="u2" value="${s.dormantDays}" min="3" max="365"></div></div>
     <label class="lbl" for="u3">من كم يعتبر العميل «ساخن»؟ (٠–١٠٠)</label><input type="number" id="u3" value="${s.hotScore}" min="10" max="100">${sw('u4', s.notifyHot, 'نبهني لما يكتب عميل جاهز يشتري')}${sw('u5', s.notifyNew, 'نبهني لما يكتب عميل جديد')}
     <button class="btn sm" id="np" style="margin-top:12px">تفعيل إشعارات ويندوز</button>`,
    brand: `<h3>الشكل والهوية</h3><label class="lbl">الشعار</label><div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap"><div class="logo-lg" id="lp">${s.logo ? `<img src="${esc(s.logo)}" alt="">` : ini(s.shopName)}</div><label class="btn sm" for="lf">اختر صورة</label><input type="file" id="lf" accept="image/png,image/jpeg,image/webp" hidden><button class="btn sm ghost" id="lr">إزالة</button></div>
     <label class="lbl" for="bc">اللون الأساسي</label><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><input type="color" id="bc" value="${esc(s.brand)}" style="width:56px;height:44px;border:0;background:none;padding:0">${['#0A7A3E', '#B0305A', '#7A3E8E', '#B4470C', '#0F6E6E', '#1D4ED8'].map(c => `<button class="icon-btn" data-c="${c}" style="background:${c}" aria-label="لون ${c}"></button>`).join('')}</div>
     <p class="help-t">اختر لون غامق عشان النص الأبيض يبان واضح.</p>
     <label class="lbl">المظهر</label><div class="choice" id="thm" style="grid-template-columns:repeat(3,minmax(0,1fr))">${[['auto', 'تلقائي', 'مثل ويندوز'], ['light', 'فاتح', ''], ['dark', 'داكن', 'مريح بالليل']].map(([k, l, h]) => `<label><input type="radio" name="thm" value="${k}" ${(s.theme || 'auto') === k ? 'checked' : ''}><span><b>${l}</b>${h ? `<small>${h}</small>` : ''}</span></label>`).join('')}</div>`,
    sec: `<h3>القفل والأمان</h3><p class="muted" style="font-size:15px">${store_locked() ? 'البرنامج مقفل بكلمة مرور.' : 'البرنامج يفتح مباشرة بدون كلمة مرور. تقدر تقفله إذا الجهاز يستخدمه أكثر من شخص.'}</p>
     ${store_locked() ? '<label class="lbl" for="x2">كلمة المرور الحالية</label><input type="password" id="x2" autocomplete="current-password">' : ''}
     <label class="lbl" for="x3">${store_locked() ? 'كلمة مرور جديدة (اتركها فاضية لإزالة القفل)' : 'كلمة مرور جديدة (٦ أحرف أو أكثر)'}</label><input type="password" id="x3" autocomplete="new-password">
     <button class="btn sm" id="x4" style="margin-top:10px">${store_locked() ? 'تحديث' : 'اقفل البرنامج'}</button>
     <label class="lbl" for="x1">اقفل تلقائياً بعد عدم استخدام (دقيقة)</label><input type="number" id="x1" value="${s.sessionMinutes}" min="5" max="720">
     <div class="notice b" style="margin-top:16px">بياناتك محفوظة على جهازك فقط، مع نسخة احتياطية يومية. البرنامج ما يرسل شي لأي جهة.</div>`,
    log: `<h3>السجل</h3><div id="lg" class="audit"><div class="skel"></div></div>`,
    wa: `<h3>الواتساب</h3><p>الرقم المربوط: <b>${ST.meDisp ? `<bdi dir="ltr">${esc(ST.meDisp)}</bdi>` : '—'}</b></p><p class="muted" style="margin-top:6px">${num(ST.chats)} محادثة · ${num(ST.messages)} رسالة محفوظة</p>
     <h3 style="margin-top:22px">فصل الواتساب</h3><p class="muted" style="font-size:15px">خلصت شغلك؟ افصل الواتساب عن هذا الجهاز. تقدر تربطه مرة ثانية بأي وقت بمسح الرمز.</p>
     <button class="btn danger" id="w1" style="margin-top:12px">فصل الواتساب…</button>`,
    about: `<div class="about"><div style="display:flex;gap:14px;align-items:center"><div class="logo-lg">و</div><div><h3 style="margin:0">موظف واتساب</h3><p class="muted">الإصدار ${esc(ST.version || '')}</p></div></div>
     <p style="margin-top:16px">برنامج يرتب محادثات واتساب محلك، يجهز الردود، ويتابع العملاء — كله على جهازك وبدون اشتراك.</p>
     <p><b>التطوير والتصميم:</b> Mohammed alzhrani</p><p class="muted">© ${num(new Date().getFullYear()).replace(/٬/g, '')} Mohammed alzhrani. جميع الحقوق محفوظة.</p>
     <div class="notice b" style="margin-top:12px">واتساب ما يسمح رسمياً بالبرامج غير الرسمية. البرنامج يقلل الخطر (ما يرسل إلا بموافقتك أو للي كتب لك، وبوقت طبيعي)، لكن الخطر ما يصير صفر.</div></div>`,
  }[SETTAB];
  el.innerHTML = `<div class="page-h"><div><h1>الإعدادات</h1></div></div><div class="setwrap"><nav class="setnav" aria-label="أقسام الإعدادات">${SETTABS.map(([k, l]) => `<button data-t="${k}" class="${SETTAB === k ? 'on' : ''}" aria-current="${SETTAB === k}">${l}</button>`).join('')}</nav>
   <div class="card setcard ${SETTAB === 'teach' ? 'wide' : ''}">${body}${['log', 'wa', 'sec', 'about', 'teach'].includes(SETTAB) ? '' : '<button class="btn primary" id="sv" style="margin-top:20px">حفظ</button>'}</div></div>`;
  el.querySelectorAll('.setnav [data-t]').forEach(b => b.onclick = () => { SETTAB = b.dataset.t; renderSet() });
  const v = id => $('#' + id)?.value, c = id => $('#' + id)?.checked;
  if (SETTAB === 'teach') renderTeach($('#teachbox'));
  if (SETTAB === 'brand') { $('#lf').onchange = e => { const f = e.target.files[0]; if (!f) return; if (f.size > 200000) return toast('الصورة كبيرة (الحد ٢٠٠ كيلوبايت)'); const r = new FileReader(); r.onload = () => { logo = r.result; $('#lp').innerHTML = `<img src="${esc(logo)}" alt="">` }; r.readAsDataURL(f) };
    $$('input[name=thm]').forEach(r => r.onchange = () => applyTheme(r.value));
    $('#lr').onclick = () => { logo = ''; $('#lp').textContent = ini(s.shopName) }; $('#bc').oninput = e => { brandC = e.target.value; document.documentElement.style.setProperty('--brand', brandC); brandText() };
    el.querySelectorAll('[data-c]').forEach(b => b.onclick = () => { brandC = b.dataset.c; $('#bc').value = brandC; document.documentElement.style.setProperty('--brand', brandC); brandText() }) }
  if (SETTAB === 'tpl') { const drawT = () => { $('#tl').innerHTML = T.map((x, i) => `<div class="grid" style="grid-template-columns:150px minmax(0,1fr) 44px;gap:8px;margin-bottom:8px"><input data-k="${i}" value="${esc(x.k)}" aria-label="اسم الرد"><input data-v="${i}" value="${esc(x.t)}" aria-label="نص الرد"><button class="icon-btn" data-d="${i}" aria-label="حذف الرد"><svg><use href="#i-x"/></svg></button></div>`).join('');
    $('#tl').querySelectorAll('[data-k]').forEach(e => e.oninput = () => T[e.dataset.k].k = e.value); $('#tl').querySelectorAll('[data-v]').forEach(e => e.oninput = () => T[e.dataset.v].t = e.value); $('#tl').querySelectorAll('[data-d]').forEach(e => e.onclick = () => { T.splice(e.dataset.d, 1); drawT() }) }; drawT(); $('#ta').onclick = () => { T.push({ k: 'رد جديد', t: '' }); drawT(); $('#tl').querySelector('[data-v]:last-of-type')?.focus() } }
  if (SETTAB === 'prices') { const drawP = () => { $('#pl').innerHTML = P.length ? P.map((p, i) => `<div class="prod"><input data-n="${i}" value="${esc(p.name)}" aria-label="اسم المنتج"><input data-p="${i}" type="number" min="0" value="${p.price || ''}" aria-label="السعر"><input data-a="${i}" value="${esc((p.aliases || []).join('، '))}" aria-label="أسماء ثانية"><button class="icon-btn" data-d="${i}" aria-label="حذف المنتج"><svg><use href="#i-x"/></svg></button></div>`).join('') : '<p class="muted" style="font-size:14px;padding:8px 0">يستخدم القائمة الافتراضية حالياً.</p>';
    $('#pl').querySelectorAll('[data-n]').forEach(e => e.oninput = () => P[e.dataset.n].name = e.value); $('#pl').querySelectorAll('[data-p]').forEach(e => e.oninput = () => P[e.dataset.p].price = +e.value);
    $('#pl').querySelectorAll('[data-a]').forEach(e => e.oninput = () => P[e.dataset.a].aliases = e.value.split(/[،,]/).map(x => x.trim()).filter(Boolean)); $('#pl').querySelectorAll('[data-d]').forEach(e => e.onclick = () => { P.splice(e.dataset.d, 1); drawP() }) }; drawP();
    $('#pa').onclick = () => { P.push({ name: '', price: 0, aliases: [] }); drawP() };
    if (!P.length) api('api/brain/products').then(j => { if (P.length || SETTAB !== 'prices') return; P = j.defaults.map(x => ({ ...x })); drawP(); $('#pl').insertAdjacentHTML('beforebegin', '<div class="notice b" style="margin-bottom:10px">هذي الأسعار الافتراضية. عدّلها على أسعار محلك واضغط «حفظ».</div>') }).catch(() => {}); $('#pd').onclick = async () => { const j = await api('api/brain/products'); P = j.defaults.map(x => ({ ...x })); drawP(); toast('انضافت — عدّل الأسعار واضغط حفظ') } }
  if (SETTAB === 'rules') $('#np').onclick = () => window.Notification ? Notification.requestPermission().then(p => toast(p === 'granted' ? 'تم التفعيل' : 'ما تفعّلت')) : toast('غير مدعوم');
  if (SETTAB === 'sec') { $('#x4').onclick = async () => { try { const r = await api('api/auth/password', { old: v('x2'), password: v('x3') }); toast(r.locked ? 'انقفل البرنامج بكلمة مرور ✓' : 'انشال القفل'); LOCKED = r.locked; renderSet() } catch (e) { toast(e.message) } };
    $('#x1').onchange = async () => { SET = await api('api/settings', { sessionMinutes: +v('x1') }); toast('انحفظ ✓') } }
  if (SETTAB === 'log') api('api/audit').then(l => { $('#lg').innerHTML = l.filter(a => a.type !== 'auto_skip').length ? l.filter(a => a.type !== 'auto_skip').slice(0, 200).map(auditRow).join('') : '<div class="empty"><b>السجل فاضي</b>كل إرسال وتعديل ينسجل هنا.</div>' }).catch(() => $('#lg').innerHTML = '<p class="err">تعذّر تحميل السجل</p>');
  if (SETTAB === 'wa') $('#w1').onclick = disconnectWA;
  const sv = $('#sv'); if (sv) sv.onclick = async () => { const b = {};
    if (SETTAB === 'shop') { if (!v('s1').trim()) { $('#s1').focus(); return toast('اكتب اسم المحل') } Object.assign(b, { shopName: v('s1'), shopType: v('s2'), city: v('s3'), about: v('s4'), delivery: v('s5'), hoursFrom: v('s6'), hoursTo: v('s7') }) }
    if (SETTAB === 'brand') Object.assign(b, { logo, brand: brandC, theme: $('input[name=thm]:checked')?.value || 'auto' }); if (SETTAB === 'brain') Object.assign(b, { aiEnabled: c('a1'), aiTone: v('a2') });
    if (SETTAB === 'tpl') Object.assign(b, { templates: T.filter(x => x.t.trim()), tags: v('tg2').split(/[،,]/).map(x => x.trim()).filter(Boolean) });
    if (SETTAB === 'prices') b.products = P.filter(p => p.name.trim());
    if (SETTAB === 'rules') Object.assign(b, { followUpDays: +v('u1'), dormantDays: +v('u2'), hotScore: +v('u3'), notifyHot: c('u4'), notifyNew: c('u5') });
    sv.disabled = true; try { SET = await api('api/settings', b); brand(SET); toast('انحفظ ✓'); renderSet() } catch { toast('تعذّر الحفظ'); sv.disabled = false } };
}
// unlink WhatsApp from this PC: keep data (default) or wipe it; settings always stay. Re-link anytime from Home.
async function disconnectWA() {
  const ok = await ask('فصل الواتساب', `<p>الواتساب ينفصل عن هذا الجهاز (مثل «تسجيل خروج» من الأجهزة المرتبطة). جوالك ما يتأثر.</p>
   <div class="choice disc"><label><input type="radio" name="wipe" value="0" checked><span><b>احتفظ بالبيانات</b><small>المحادثات والعملاء والطلبات تبقى على جهازك.</small></span></label>
   <label><input type="radio" name="wipe" value="1"><span><b>امسح البيانات</b><small>نمسح المحادثات والعملاء والطلبات من هذا الجهاز. الإعدادات تبقى.</small></span></label></div>`, 'افصل الواتساب', true);
  if (!ok) return; const wipe = $('input[name=wipe]:checked')?.value === '1';
  if (wipe && !await ask('متأكد تمسح؟', '<p>ما نقدر نرجع المحادثات والعملاء بعد المسح.</p>', 'امسح وافصل', true)) return;
  try { await api('api/logout', { wipe }); CL = []; CH = null; toast(wipe ? 'انفصل وانمسحت البيانات' : 'انفصل الواتساب — بياناتك محفوظة'); await tick(); go('home') } catch (x) { toast('تعذّر: ' + x.message) }
}
let LOCKED = null; const store_locked = () => LOCKED;
boot();
