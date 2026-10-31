// موظف واتساب — local engine. Runs on 127.0.0.1 inside the desktop app.
// WhatsApp link via Baileys (full history sync), local JSON store, local Saudi brain (Python, offline).
// Nothing is sent unless the owner presses «إرسال», or the owner switched the auto-reply employee ON.
import express from 'express'; import QRCode from 'qrcode'; import fs from 'fs'; import path from 'path'; import crypto from 'crypto';
import { fileURLToPath } from 'url';
import { analyze } from './analyze.js'; import { csv, vcf, reportHTML } from './report.js';
import { decide, AUTO_DEFAULTS, SKIP_AR, scheduleOpen, inWindow, hm, BAD_JID } from './employee.js';
import { campaign, OCCASIONS } from './campaigns.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DIR = process.env.DATA_DIR || path.join(HERE, 'data'); fs.mkdirSync(DIR, { recursive: true });
const PORT = +process.env.PORT || 8796, HOST = '127.0.0.1';
const TOKEN = (process.env.TOKEN || crypto.randomBytes(12).toString('hex')).trim();
const BRAIN_URL = process.env.BRAIN_URL || '', BRAIN_KEY = process.env.BRAIN_KEY || '';
const FAKE = process.env.FAKE_WA === '1';
const VERSION = process.env.APP_VERSION || '2.1.0';
const DATA = path.join(DIR, 'store.json');

// ---------------- store ----------------
const BACKUPS = path.join(DIR, 'backups'); fs.mkdirSync(BACKUPS, { recursive: true });
function load() {   // store.json, or the newest good backup if it is missing/corrupt
  try { return JSON.parse(fs.readFileSync(DATA, 'utf8')) } catch (e) {
    const bk = fs.readdirSync(BACKUPS).filter(f => f.startsWith('store-')).sort().reverse();
    for (const f of bk) { try { const j = JSON.parse(fs.readFileSync(path.join(BACKUPS, f), 'utf8')); console.log('restored from backup', f); return j } catch { } }
    if (fs.existsSync(DATA)) fs.copyFileSync(DATA, DATA + '.corrupt-' + Date.now());
    return {};
  }
}
function backup() {   // one snapshot per day, keep the last 14
  try {
    if (!fs.existsSync(DATA)) return; const f = path.join(BACKUPS, 'store-' + new Date().toISOString().slice(0, 10) + '.json');
    fs.copyFileSync(DATA, f); const all = fs.readdirSync(BACKUPS).filter(x => x.startsWith('store-')).sort();
    for (const x of all.slice(0, Math.max(0, all.length - 14))) fs.rmSync(path.join(BACKUPS, x), { force: true });
  } catch { }
}
const store = load();
for (const [k, v] of Object.entries({ chats: {}, contacts: {}, crm: {}, audit: [], alerts: [], auth: {}, ai: {}, autoHist: {} })) store[k] ??= v;
const DEF = {
  shopName: 'محل الورد', shopType: 'محل ورد', city: '', phone: '', about: '', delivery: '', logo: '', brand: '#0A7A3E',
  hoursFrom: '09:00', hoursTo: '23:00', tz: 'Asia/Riyadh', products: [],
  templates: [{ k: 'ترحيب', t: 'هلا والله، نورتنا 🌷 كيف أقدر أخدمك؟' }, { k: 'أسعار', t: 'أسعار الباقات تبدأ من ١٥٠ ريال، تحب أرسل لك صور الخيارات؟' },
    { k: 'تأكيد', t: 'تم تأكيد طلبك ✅ وموعد التوصيل …' }, { k: 'شكر', t: 'شكراً لثقتك فينا، نتشرف بخدمتك دايم 🌹' }],
  tags: ['جديد', 'مهتم', 'طلب', 'تم التوصيل', 'مميز'], followUpDays: 1, dormantDays: 30, hotScore: 60, notifyHot: true, notifyNew: true,
  aiEnabled: true, aiTone: 'ودودة ومحترفة', sessionMinutes: 120, tourDone: false, hintsOff: [],
  autoReply: { ...AUTO_DEFAULTS },
};
store.settings = { ...DEF, ...(store.settings || {}), autoReply: { ...AUTO_DEFAULTS, ...(store.settings?.autoReply || {}) } };
if (['fixed', 'ai'].includes(store.settings.autoReply.mode) && store.settings.autoReply.mode === 'ai') store.settings.autoReply.mode = 'smart';
const S = () => store.settings;
let saveT; const save = () => { clearTimeout(saveT); const tmp = DATA + '.tmp'; const fd = fs.openSync(tmp, 'w'); fs.writeSync(fd, JSON.stringify(store)); fs.fsyncSync(fd); fs.closeSync(fd); fs.renameSync(tmp, DATA) };
const saveSoon = () => { clearTimeout(saveT); saveT = setTimeout(save, 500) };
const audit = (type, info = {}) => { store.audit.unshift({ t: Date.now(), type, ...info }); store.audit = store.audit.slice(0, 1000); saveSoon() };
const alert = (kind, jid, text) => { store.alerts.unshift({ id: crypto.randomUUID(), t: Date.now(), kind, jid, text, read: false }); store.alerts = store.alerts.slice(0, 300); saveSoon() };
const phoneOf = j => (j || '').split('@')[0].split(':')[0];
const chat = jid => store.chats[jid] ??= { jid, phone: phoneOf(jid), isGroup: jid.endsWith('@g.us'), name: '', messages: [] };
function txt(m) {
  const x = m.message || {}; const e = x.ephemeralMessage?.message || x.viewOnceMessage?.message || null; if (e) return txt({ message: e });
  return x.conversation || x.extendedTextMessage?.text || x.imageMessage?.caption || x.videoMessage?.caption ||
    (x.imageMessage ? '[صورة]' : x.audioMessage ? '[رسالة صوتية]' : x.locationMessage ? '[موقع]' : x.documentMessage ? '[ملف]' : x.stickerMessage ? '[ملصق]' : x.videoMessage ? '[فيديو]' : x.contactMessage ? '[جهة اتصال]' : '');
}
function addMsg(m) {
  const j = m.key?.remoteJid; if (BAD_JID(j) && !j?.endsWith('@g.us')) return null; if (!j) return null;
  const t = txt(m); if (!t) return null; const c = chat(j);
  if (c.messages.some(x => x.id === m.key.id)) return null;
  const msg = { id: m.key.id, fromMe: !!m.key.fromMe, ts: Number(m.messageTimestamp || Date.now() / 1000) * 1000, text: t };
  c.messages.push(msg); if (c.messages.length > 2000) c.messages.splice(0, c.messages.length - 2000);
  if (!m.key.fromMe && m.pushName && !c.name) c.name = m.pushName; return { c, msg };
}
function addContact(c) { if (!c.id) return; store.contacts[c.id] = { ...store.contacts[c.id], ...c }; const ch = store.chats[c.id]; if (ch && (c.name || c.notify)) ch.name = c.name || c.notify || ch.name }

// ---------------- local brain (Python service) ----------------
let brainOk = false;
async function brain(route, body) {
  if (!BRAIN_URL || !S().aiEnabled) return null;
  const ctl = new AbortController(), to = setTimeout(() => ctl.abort(), 5000);
  try {
    const r = await fetch(BRAIN_URL + route, { method: 'POST', signal: ctl.signal, headers: { 'content-type': 'application/json', 'x-brain-key': BRAIN_KEY },
      body: JSON.stringify({ ...body, shop: { name: S().shopName, location: S().city, city: S().city, hours: `${S().hoursFrom} - ${S().hoursTo}` }, products: S().products }) });
    if (!r.ok) throw new Error('brain ' + r.status); brainOk = true; return await r.json();
  } catch { brainOk = false; return null } finally { clearTimeout(to) }
}
const HOT = /(ابي|أبي|ابغى|ابغا|اطلب|طلب|بكم|كم السعر|سعر|توصيل|اليوم|بكرة|بكره|عنوان|موقع|حول|تحويل|دفع|حجز|باقة|بوكيه)/g;
function keywordScore(c) {
  const inc = c.messages.filter(m => !m.fromMe); if (!inc.length) return 0;
  const rec = Math.max(0, 1 - (Date.now() - Math.max(...c.messages.map(m => m.ts))) / (14 * 864e5));
  const hits = (inc.slice(-10).map(m => m.text).join(' ').match(HOT) || []).length; return Math.min(100, Math.round(hits * 12 + rec * 40));
}
const msgsFor = (c, n = 40) => [...c.messages].sort((a, b) => a.ts - b.ts).slice(-n).map(m => ({ fromMe: m.fromMe, text: m.text, ts: m.ts }));

// ---------------- incoming: alerts + the auto-reply employee ----------------
const pending = new Map();   // jid -> timer (one scheduled auto reply per customer)
let state = { status: 'starting', qr: null, me: null, syncing: false, lastSync: null }, realSend = null, SOCK = null;
async function onIncoming(c, msg) {
  if (c.isGroup || msg.fromMe || BAD_JID(c.jid)) return;
  if (Date.now() - msg.ts > 5 * 60e3) return;
  const b = await brain('/think', { text: msg.text, customer: c.name, after_hours: !inWindow(S().hoursFrom, S().hoursTo, hm(new Date(), S().tz)) });
  const sc = Math.max(keywordScore(c), b?.lead_score || 0);
  store.crm[c.jid] = { ...store.crm[c.jid], score: Math.max(sc, store.crm[c.jid]?.score || 0) };
  if (S().notifyHot && sc >= S().hotScore) alert('hot', c.jid, `عميل مهتم: ${c.name || c.phone} — «${msg.text.slice(0, 60)}»`);
  else if (S().notifyNew && c.messages.filter(m => !m.fromMe).length <= 1) alert('new', c.jid, `عميل جديد: ${c.name || c.phone}`);
  const d = decide(c, msg, { settings: S(), connected: state.status === 'connected' && !!realSend, history: store.autoHist, brain: b });
  if (d.action === 'skip') { if (d.reason !== 'off') audit('auto_skip', { jid: c.jid, to: c.name || c.phone, why: SKIP_AR[d.reason] || d.reason }); return }
  const ar = { ...AUTO_DEFAULTS, ...S().autoReply };
  clearTimeout(pending.get(c.jid));
  pending.set(c.jid, setTimeout(() => { pending.delete(c.jid); sendAuto(c.jid, msg, d).catch(() => {}) }, Math.max(0, ar.delaySec) * 1000));
}
async function sendAuto(jid, trigger, d) {
  const c = store.chats[jid]; if (!c) return;
  const ar = S().autoReply;
  if (!ar.enabled) return audit('auto_skip', { jid, why: 'انطفى الموظف قبل الإرسال' });
  if (c.messages.some(m => m.fromMe && m.ts > trigger.ts)) return audit('auto_skip', { jid, to: c.name || c.phone, why: 'رديت عليه قبل الموظف' });
  if (!realSend || state.status !== 'connected') return audit('auto_reply_failed', { jid, err: 'الواتساب غير متصل' });
  try {
    const m = await realSend(jid, { text: d.text }); const r = addMsg(m); if (r) r.msg.auto = true; else { const x = c.messages.find(y => y.id === m?.key?.id); if (x) x.auto = true }
    const h = store.autoHist[jid] ??= { times: [] }; h.times = [...h.times.filter(t => Date.now() - t < 864e5), Date.now()];
    if (d.action === 'handoff') { h.handoffAt = Date.now(); alert('human', jid, `يحتاج ردك: ${c.name || c.phone} — «${trigger.text.slice(0, 60)}»`) }
    audit(d.action === 'handoff' ? 'auto_handoff' : 'auto_reply', { jid, to: c.name || c.phone, kind: d.kind, len: d.text.length, preview: d.text.slice(0, 90), q: trigger.text.slice(0, 60) });
    saveSoon();
  } catch (e) { audit('auto_reply_failed', { jid, err: String(e.message).slice(0, 80) }) }
}

// ---------------- WhatsApp connection ----------------
let fake = null, connecting = false;
async function connect() {
  if (connecting) return; connecting = true;
  try {
    let sock;
    if (FAKE) { const { makeFakeSocket } = await import('./fakewa.js'); sock = fake = makeFakeSocket() }
    else {
      const pino = (await import('pino')).default; const M = await import('@whiskeysockets/baileys'); const B = M.useMultiFileAuthState ? M : M.default;
      const makeWASocket = typeof B.default === 'function' ? B.default : B.makeWASocket;
      const { state: auth, saveCreds } = await B.useMultiFileAuthState(path.join(DIR, 'auth')); const { version } = await B.fetchLatestBaileysVersion().catch(() => ({}));
      sock = makeWASocket({ auth, version, logger: pino({ level: 'silent' }), browser: B.Browsers.windows('Desktop'), syncFullHistory: true,
        shouldSyncHistoryMessage: () => true, markOnlineOnConnect: false, printQRInTerminal: false, getMessage: async () => undefined });
      sock.ev.on('creds.update', saveCreds); sock._B = B;
    }
    realSend = sock.sendMessage.bind(sock); SOCK = sock;
    // Only realSend (owner presses Send, or the owner-enabled employee) may send. Every other mutating call is disabled.
    for (const f of ['sendMessage', 'readMessages', 'sendReceipt', 'sendReceipts', 'sendPresenceUpdate', 'chatModify', 'relayMessage', 'updateBlockStatus', 'groupLeave', 'star', 'addOrEditContact', 'removeContact', 'updateProfileStatus', 'updateProfileName'])
      if (typeof sock[f] === 'function') sock[f] = async () => {};
    sock.ev.on('connection.update', async u => {
      if (u.qr) { state.qr = await QRCode.toDataURL(u.qr, { width: 360, margin: 1 }); state.status = 'qr' }
      if (u.connection === 'open') { state.status = 'connected'; state.qr = null; state.me = phoneOf(sock.user?.id); state.syncing = true; audit('whatsapp_linked', {}); clearTimeout(state._st); state._st = setTimeout(() => state.syncing = false, 25e3) }
      if (u.connection === 'close') {
        const code = u.lastDisconnect?.error?.output?.statusCode; connecting = false;
        if (code === 401 || code === sock._B?.DisconnectReason?.loggedOut) { state.status = 'loggedOut'; fs.rmSync(path.join(DIR, 'auth'), { recursive: true, force: true }) } else state.status = 'reconnecting';
        setTimeout(connect, 3000);
      }
    });
    sock.ev.on('messaging-history.set', ({ chats, contacts, messages }) => {
      chats?.forEach(c => { const x = chat(c.id); if (c.name) x.name = c.name }); contacts?.forEach(addContact); messages?.forEach(addMsg);
      state.syncing = true; state.lastSync = Date.now(); clearTimeout(state._st); state._st = setTimeout(() => state.syncing = false, 15e3); saveSoon();
    });
    sock.ev.on('messages.upsert', ({ messages, type }) => { for (const m of messages) { const r = addMsg(m); if (r && type === 'notify') onIncoming(resolve(r.c), r.msg) } saveSoon() });
    sock.ev.on('contacts.upsert', cs => { cs.forEach(addContact); saveSoon() }); sock.ev.on('contacts.update', cs => { cs.forEach(addContact); saveSoon() });
  } finally { connecting = false }
}
if (process.env.NO_WA === '1') state.status = 'connected'; else connect();

// ---------------- data views ----------------
let byLidCache = { t: 0, m: {} };
const byLid = () => { if (Date.now() - byLidCache.t > 5000) { const m = {}; for (const c of Object.values(store.contacts)) if (c.lid) m[c.lid] = c; byLidCache = { t: Date.now(), m } } return byLidCache.m };
function resolve(c) { const k = byLid()[c.jid] || store.contacts[c.jid]; if (!k) return c; const ph = k.jid || (k.id?.endsWith('@s.whatsapp.net') ? k.id : null); return { ...c, phone: ph ? phoneOf(ph) : c.phone, name: k.name || k.notify || c.name } }
const chatsList = () => Object.values(store.chats).filter(c => c.messages.length && !c.isGroup && !BAD_JID(c.jid)).map(resolve);
const lastOf = c => c.messages.reduce((a, m) => m.ts > a.ts ? m : a, { ts: 0 });
const scoreOf = c => store.crm[c.jid]?.aiScore ?? Math.max(keywordScore(c), store.crm[c.jid]?.score || 0);
function analytics() {
  const cs = chatsList(), day = 864e5, now = Date.now(); let rev = 0, orders = 0, buyers = 0; const rts = [], revByDay = {};
  for (const c of cs) {
    const os = (store.crm[c.jid]?.orders || []).filter(o => o.status !== 'ملغي'); if (os.length) buyers++; orders += os.length;
    for (const o of os) { rev += +o.amount || 0; const d = new Date(o.date || now).toISOString().slice(0, 10); revByDay[d] = (revByDay[d] || 0) + (+o.amount || 0) }
    const ms = [...c.messages].sort((a, b) => a.ts - b.ts);
    for (let i = 0; i < ms.length; i++) if (!ms[i].fromMe && (i === 0 || ms[i - 1].fromMe)) { const r = ms.slice(i + 1).find(x => x.fromMe); if (r && r.ts - ms[i].ts < 3 * day) rts.push(r.ts - ms[i].ts) }
  }
  rts.sort((a, b) => a - b); const msgsByDay = {};
  for (const c of cs) for (const m of c.messages) if (now - m.ts < 14 * day && !m.fromMe) { const d = new Date(m.ts).toISOString().slice(0, 10); msgsByDay[d] = (msgsByDay[d] || 0) + 1 }
  const tags = {}; for (const c of cs) { const t = store.crm[c.jid]?.tag || 'جديد'; tags[t] = (tags[t] || 0) + 1 }
  const autoToday = store.audit.filter(a => ['auto_reply', 'auto_handoff'].includes(a.type) && now - a.t < day).length;
  return { customers: cs.length, buyers, orders, revenue: rev, avgOrder: orders ? Math.round(rev / orders) : 0, conversion: cs.length ? Math.round(buyers / cs.length * 100) : 0,
    medianResponseMin: rts.length ? Math.round(rts[Math.floor(rts.length / 2)] / 60000) : null, waiting: cs.filter(c => !lastOf(c).fromMe && store.crm[c.jid]?.status !== 'resolved').length,
    active7: cs.filter(c => now - lastOf(c).ts < 7 * day).length, revByDay, msgsByDay, tags, autoToday };
}
const hotLeads = () => chatsList().map(c => ({ jid: c.jid, name: c.name, phone: c.phone, score: scoreOf(c), reason: store.crm[c.jid]?.aiReason || '', last: lastOf(c) }))
  .filter(x => x.score >= S().hotScore).sort((a, b) => b.score - a.score).slice(0, 15);
function reminders() {
  const today = new Date().toISOString().slice(0, 10), now = Date.now();
  return chatsList().map(c => {
    const cr = store.crm[c.jid] || {}, l = lastOf(c); if (cr.status === 'resolved') return null;
    if (cr.followUp && cr.followUp <= today) return { jid: c.jid, name: c.name || c.phone, why: 'موعد متابعة ' + cr.followUp };
    if (!l.fromMe && now - l.ts > S().followUpDays * 864e5) return { jid: c.jid, name: c.name || c.phone, why: 'بدون رد من ' + Math.floor((now - l.ts) / 864e5) + ' يوم' };
    if (['مهتم', 'جديد'].includes(cr.tag || 'جديد') && l.fromMe && now - l.ts > 2 * 864e5 && now - l.ts < 20 * 864e5) return { jid: c.jid, name: c.name || c.phone, why: 'عميل مهتم سكت — تابعه' };
    return null;
  }).filter(Boolean);
}
function allOrders() {
  const out = []; for (const c of chatsList()) (store.crm[c.jid]?.orders || []).forEach((o, i) => out.push({ ...o, i, jid: c.jid, name: c.name || '+' + c.phone }));
  return out.sort((a, b) => (a.deliveryDate || '9').localeCompare(b.deliveryDate || '9'));
}

// ---------------- app + security ----------------
const app = express(); app.disable('x-powered-by');
app.use((q, s, n) => { s.set({ 'X-Frame-Options': 'DENY', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'Cross-Origin-Opener-Policy': 'same-origin',
  'Content-Security-Policy': "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'" }); n() });
const r = express.Router(); r.use(express.json({ limit: '400kb' }));
const hash = (pw, salt) => crypto.scryptSync(pw, salt, 64).toString('hex');
const sessions = new Map(); let fails = { n: 0, t: Date.now() };
const cookie = q => Object.fromEntries((q.headers.cookie || '').split(';').map(x => x.trim().split('=')).filter(x => x[0]));
function startSession(s) { const id = crypto.randomBytes(32).toString('hex'), csrf = crypto.randomBytes(16).toString('hex'); sessions.set(id, { last: Date.now(), csrf }); s.set('Set-Cookie', `sid=${id}; Path=/${TOKEN}; HttpOnly; SameSite=Strict; Max-Age=86400`); return csrf }
function getSess(q) { const x = sessions.get(cookie(q).sid); if (!x) return null; if (store.auth.hash && Date.now() - x.last > S().sessionMinutes * 60e3) { sessions.delete(cookie(q).sid); return null } x.last = Date.now(); return x }
r.get('/healthz', (q, s) => s.json({ ok: true, version: VERSION, status: state.status }));
r.get('/api/auth', (q, s) => {
  let x = getSess(q), csrf = x?.csrf;
  if (!x && !store.auth.hash) csrf = startSession(s);           // no lock password: the desktop app opens directly
  s.json({ locked: !!store.auth.hash, loggedIn: !!csrf, csrf, shop: { name: S().shopName, brand: S().brand, logo: S().logo } });
});
r.post('/api/auth/login', (q, s) => {
  if (Date.now() - fails.t > 15 * 60e3) fails = { n: 0, t: Date.now() };
  if (fails.n >= 5) return s.status(429).json({ error: 'محاولات كثيرة، جرّب بعد ١٥ دقيقة' });
  if (!store.auth.hash) return s.json({ ok: true, csrf: startSession(s) });
  const ok = crypto.timingSafeEqual(Buffer.from(hash(String(q.body?.password || ''), store.auth.salt), 'hex'), Buffer.from(store.auth.hash, 'hex'));
  if (!ok) { fails.n++; audit('login_failed', {}); return s.status(401).json({ error: 'كلمة المرور غلط' }) }
  fails = { n: 0, t: Date.now() }; audit('login', {}); s.json({ ok: true, csrf: startSession(s) });
});
r.post('/api/auth/logout', (q, s) => { sessions.delete(cookie(q).sid); s.set('Set-Cookie', `sid=; Path=/${TOKEN}; Max-Age=0`); s.json({ ok: true }) });
r.use(['/api', '/report.html', '/contacts.csv', '/contacts.vcf'], (q, s, n) => { const x = getSess(q); if (!x) return s.status(401).json({ error: 'login' }); if (q.method !== 'GET' && q.get('x-csrf') !== x.csrf) return s.status(403).json({ error: 'csrf' }); n() });
r.post('/api/auth/password', (q, s) => {
  const { old, password } = q.body || {};
  if (store.auth.hash && hash(String(old || ''), store.auth.salt) !== store.auth.hash) return s.status(401).json({ error: 'كلمة المرور الحالية غلط' });
  if (password === '' && store.auth.hash) { store.auth = {}; save(); audit('password_removed', {}); return s.json({ ok: true, locked: false }) }
  if (String(password || '').length < 6) return s.status(400).json({ error: 'كلمة المرور ٦ أحرف على الأقل' });
  store.auth.salt = crypto.randomBytes(16).toString('hex'); store.auth.hash = hash(password, store.auth.salt); save(); audit('password_changed', {}); s.json({ ok: true, locked: true });
});
// ---- core
let analysis = (() => { try { return JSON.parse(fs.readFileSync(path.join(DIR, 'analysis.json'), 'utf8')) } catch { return null } })();
r.get('/api/state', (q, s) => {
  const cs = chatsList(), ar = S().autoReply;
  s.json({ status: state.status, qr: state.qr, me: state.me, syncing: state.syncing, lastSync: state.lastSync, version: VERSION, sim: FAKE,
    brain: brainOk || !!BRAIN_URL && S().aiEnabled, chats: cs.length, messages: cs.reduce((a, c) => a + c.messages.length, 0), analysis,
    unreadAlerts: store.alerts.filter(a => !a.read).length, now: hm(new Date(), S().tz), open: inWindow(S().hoursFrom, S().hoursTo, hm(new Date(), S().tz)),
    employee: { enabled: !!ar.enabled, active: !!ar.enabled && scheduleOpen(ar, S(), Date.now()), schedule: ar.schedule, mode: ar.mode, pending: pending.size } });
});
r.post('/api/analyze', async (q, s) => { analysis = await analyze(chatsList()); fs.writeFileSync(path.join(DIR, 'analysis.json'), JSON.stringify(analysis)); s.json(analysis) });
r.get('/report.html', (q, s) => analysis ? s.send(reportHTML(analysis, S())) : s.status(400).send('رتّب المحادثات أول'));
r.get('/contacts.csv', (q, s) => analysis ? s.type('text/csv').set('content-disposition', 'attachment; filename=contacts.csv').send('\ufeff' + csv(analysis)) : s.status(400).send('رتّب أول'));
r.get('/contacts.vcf', (q, s) => analysis ? s.type('text/vcard').set('content-disposition', 'attachment; filename=contacts.vcf').send(vcf(analysis)) : s.status(400).send('رتّب أول'));
r.get('/api/chats', (q, s) => s.json(chatsList().map(c => {
  const l = lastOf(c), cr = store.crm[c.jid] || {};
  return { jid: c.jid, name: c.name, phone: c.phone, last: l.text, lastAt: l.ts, fromMe: l.fromMe, auto: !!l.auto, n: c.messages.length, tag: cr.tag || 'جديد', status: cr.status || 'open', score: scoreOf(c), orders: (cr.orders || []).length };
}).sort((a, b) => b.lastAt - a.lastAt)));
r.get('/api/chat', (q, s) => { const c = chatsList().find(x => x.jid === q.query.jid); s.json(c ? { ...c, messages: [...c.messages].sort((a, b) => a.ts - b.ts).slice(-400), crm: store.crm[c.jid] || {}, pendingAuto: pending.has(c.jid) } : null) });
r.post('/api/send', async (q, s) => {
  const { jid, text, confirm } = q.body || {};
  if (confirm !== true || !jid || !store.chats[jid] || typeof text !== 'string' || !text.trim() || text.length > 4000) return s.status(400).json({ error: 'طلب غير صالح' });
  if (!realSend || state.status !== 'connected') return s.status(503).json({ error: 'الواتساب غير متصل' });
  try {
    clearTimeout(pending.get(jid)); pending.delete(jid);            // owner replied → cancel the employee's pending reply
    const m = await realSend(jid, { text: text.trim() }); addMsg(m); const c = resolve(store.chats[jid]);
    audit('manual_send', { jid, to: c.name || c.phone, len: text.length, preview: text.trim().slice(0, 80) }); saveSoon(); s.json({ ok: true });
  } catch (e) { audit('send_failed', { jid, err: String(e.message).slice(0, 80) }); s.status(500).json({ error: 'تعذّر الإرسال: ' + e.message }) }
});
r.get('/api/crm', (q, s) => s.json({ crm: store.crm, settings: S(), occasions: OCCASIONS }));
r.post('/api/crm', (q, s) => {
  const { jid, data } = q.body || {}; if (!jid || !data || typeof data !== 'object') return s.status(400).end();
  const allow = ['tag', 'note', 'followUp', 'orders', 'status'];
  const d = Object.fromEntries(Object.entries(data).filter(([k]) => allow.includes(k)));
  if (d.orders && !Array.isArray(d.orders)) return s.status(400).end();
  store.crm[jid] = { ...store.crm[jid], ...d, updatedAt: Date.now() }; saveSoon(); s.json(store.crm[jid]);
});
r.get('/api/orders', (q, s) => s.json(allOrders()));
r.post('/api/orders/status', (q, s) => {
  const { jid, i, status } = q.body || {}; const o = store.crm[jid]?.orders?.[i];
  if (!o || !['جديد', 'قيد التجهيز', 'تم التوصيل', 'ملغي'].includes(status)) return s.status(400).json({ error: 'طلب غير صالح' });
  o.status = status; saveSoon(); audit('order_status', { jid, preview: o.item + ' ← ' + status }); s.json({ ok: true });
});
r.post('/api/settings', (q, s) => {
  const b = q.body || {}, cur = S(); const str = (k, n = 200) => { if (typeof b[k] === 'string') cur[k] = b[k].slice(0, n) };
  ['shopName', 'shopType', 'city', 'phone', 'aiTone', 'tz'].forEach(k => str(k, 80)); ['about', 'delivery'].forEach(k => str(k, 800));
  if (/^#[0-9a-fA-F]{6}$/.test(b.brand || '')) cur.brand = b.brand;
  if (typeof b.logo === 'string' && (b.logo === '' || /^data:image\/(png|jpeg|webp);base64,/.test(b.logo)) && b.logo.length < 300000) cur.logo = b.logo;
  for (const k of ['hoursFrom', 'hoursTo']) if (/^\d\d:\d\d$/.test(b[k] || '')) cur[k] = b[k];
  for (const [k, lo, hi] of [['followUpDays', 0, 60], ['dormantDays', 3, 365], ['hotScore', 10, 100], ['sessionMinutes', 5, 720]]) if (b[k] !== '' && b[k] != null && Number.isFinite(+b[k])) cur[k] = Math.min(hi, Math.max(lo, +b[k]));
  for (const k of ['notifyHot', 'notifyNew', 'aiEnabled', 'tourDone']) if (typeof b[k] === 'boolean') cur[k] = b[k];
  if (Array.isArray(b.hintsOff)) cur.hintsOff = b.hintsOff.filter(x => typeof x === 'string').slice(0, 30);
  if (Array.isArray(b.templates)) cur.templates = b.templates.filter(x => x && typeof x.t === 'string' && x.t.trim()).slice(0, 40).map(x => ({ k: String(x.k || 'رد').slice(0, 30), t: x.t.slice(0, 1000) }));
  if (Array.isArray(b.tags)) cur.tags = [...new Set(b.tags.filter(x => typeof x === 'string' && x.trim()).map(x => x.trim().slice(0, 20)))].slice(0, 15);
  if (Array.isArray(b.products)) cur.products = b.products.filter(p => p && typeof p.name === 'string' && p.name.trim()).slice(0, 200)
    .map(p => ({ name: p.name.trim().slice(0, 60), price: Math.max(0, +p.price || 0), unit: String(p.unit || 'بوكيه').slice(0, 20), category: String(p.category || 'بوكيه').slice(0, 20), aliases: (Array.isArray(p.aliases) ? p.aliases : String(p.aliases || '').split(/[،,]/)).map(a => String(a).trim()).filter(Boolean).slice(0, 10) }));
  if (b.autoReply && typeof b.autoReply === 'object') {
    const a = b.autoReply, ar = cur.autoReply, was = ar.enabled;
    if (typeof a.enabled === 'boolean') ar.enabled = a.enabled;
    if (['always', 'offhours', 'custom'].includes(a.schedule)) ar.schedule = a.schedule;
    for (const k of ['from', 'to']) if (/^\d\d:\d\d$/.test(a[k] || '')) ar[k] = a[k];
    if (['smart', 'fixed'].includes(a.mode)) ar.mode = a.mode;
    if (typeof a.handoff === 'boolean') ar.handoff = a.handoff;
    for (const k of ['message', 'handoffMessage']) if (typeof a[k] === 'string' && a[k].trim()) ar[k] = a[k].trim().slice(0, 600);
    for (const [k, lo, hi] of [['delaySec', 0, 600], ['cooldownMin', 0, 1440], ['maxPerDay', 1, 50], ['ownerActiveMin', 0, 240]]) if (a[k] !== '' && a[k] != null && Number.isFinite(+a[k])) ar[k] = Math.min(hi, Math.max(lo, +a[k]));
    if (was !== ar.enabled) { audit(ar.enabled ? 'auto_reply_enabled' : 'auto_reply_disabled', { preview: { always: 'يرد دايم', offhours: 'يرد خارج الدوام', custom: `يرد من ${ar.from} إلى ${ar.to}` }[ar.schedule] }); if (!ar.enabled) { for (const t of pending.values()) clearTimeout(t); pending.clear() } }
  }
  saveSoon(); if (!b.tourDone && !b.hintsOff) audit('settings_changed', {}); s.json(cur);
});
r.post('/api/employee/test', async (q, s) => {   // dry run: what would the employee answer? (sends nothing)
  const text = String(q.body?.text || '').slice(0, 500); if (!text.trim()) return s.status(400).json({ error: 'اكتب رسالة' });
  const b = await brain('/think', { text, after_hours: !inWindow(S().hoursFrom, S().hoursTo, hm(new Date(), S().tz)) });
  const fakeChat = { jid: 'test@s.whatsapp.net', messages: [] }; const msg = { fromMe: false, text, ts: Date.now() };
  const d = decide(fakeChat, msg, { settings: { ...S(), autoReply: { ...S().autoReply, enabled: true, schedule: 'always' } }, connected: true, history: {}, brain: b });
  s.json({ ...d, brain: !!b, intents: b?.intents || [] });
});
r.get('/api/audit', (q, s) => s.json(store.audit.slice(0, 400)));
r.get('/api/alerts', (q, s) => s.json(store.alerts.slice(0, 60)));
r.post('/api/alerts/read', (q, s) => { store.alerts.forEach(a => a.read = true); saveSoon(); s.json({ ok: true }) });
r.get('/api/dashboard', (q, s) => s.json({ analytics: analytics(), hot: hotLeads(), reminders: reminders(), briefing: store.ai.briefing || null, orders: allOrders().filter(o => !['تم التوصيل', 'ملغي'].includes(o.status)).slice(0, 8) }));
r.post('/api/logout', async (q, s) => {
  try { await SOCK?.logout?.() } catch { } fs.rmSync(path.join(DIR, 'auth'), { recursive: true, force: true });
  store.chats = {}; store.contacts = {}; store.alerts = []; analysis = null; audit('whatsapp_unlinked', {}); save(); s.json({ ok: true });
  state = { status: 'starting', qr: null, me: null }; setTimeout(connect, 800);
});
// ---- brain endpoints (suggestions only — they never send)
const getChat = jid => chatsList().find(x => x.jid === jid);
r.get('/api/brain/products', async (q, s) => { const d = BRAIN_URL ? await fetch(BRAIN_URL + '/kb', { method: 'POST', headers: { 'x-brain-key': BRAIN_KEY } }).then(x => x.json()).catch(() => null) : null; s.json({ current: S().products, defaults: d?.products || [] }) });
r.post('/api/ai/suggest', async (q, s) => { const c = getChat(q.body?.jid); if (!c) return s.status(404).json({ error: 'المحادثة غير موجودة' }); const j = await brain('/suggest', { messages: msgsFor(c), customer: c.name }); if (!j) return s.status(503).json({ error: 'brain_off' }); s.json(j) });
r.post('/api/ai/extract', async (q, s) => {
  const c = getChat(q.body?.jid); if (!c) return s.status(404).json({ error: 'المحادثة غير موجودة' });
  const j = await brain('/extract', { messages: msgsFor(c, 80), customer: c.name }); if (!j) return s.status(503).json({ error: 'brain_off' });
  store.crm[c.jid] = { ...store.crm[c.jid], aiScore: j.score, aiReason: j.reason, aiSummary: j.summary }; saveSoon(); s.json(j);
});
r.post('/api/ai/score-all', async (q, s) => {
  const cs = chatsList().sort((a, b) => lastOf(b).ts - lastOf(a).ts).slice(0, 150); let done = 0;
  for (const c of cs) { const j = await brain('/extract', { messages: msgsFor(c, 30), customer: c.name }); if (!j) break; store.crm[c.jid] = { ...store.crm[c.jid], aiScore: j.score, aiReason: j.reason, aiStage: j.stage, aiSummary: j.summary }; done++ }
  saveSoon(); if (!done && cs.length) return s.status(503).json({ error: 'brain_off' }); s.json({ scored: done });
});
r.post('/api/ai/briefing', async (q, s) => {
  const N = x => (+x || 0).toLocaleString('ar-SA'), D = x => x ? new Date(x + 'T12:00:00').toLocaleDateString('ar-SA-u-ca-gregory', { weekday: 'long', day: 'numeric', month: 'long' }) : '';
  const a = analytics(), h = hotLeads().slice(0, 5), rm = reminders(), od = allOrders().filter(o => !['تم التوصيل', 'ملغي'].includes(o.status));
  const lines = [];
  if (a.waiting) lines.push(`• ${N(a.waiting)} محادثة تنتظر ردك — ابدأ فيها.`); else lines.push('• ما فيه أحد ينتظر رد 👌');
  if (h.length) lines.push(`• جاهزين للشراء: ${h.map(x => x.name || '+' + x.phone).join('، ')}.`);
  if (od.length) lines.push(`• ${N(od.length)} طلب مفتوح، أقربها: ${od[0].item}${od[0].deliveryDate ? ' يوم ' + D(od[0].deliveryDate) : ''}.`);
  if (rm.length) lines.push(`• ${N(rm.length)} متابعة مستحقة اليوم.`);
  lines.push(`• المبيعات المسجّلة: ${N(a.revenue)} ر.س من ${N(a.orders)} طلب.`);
  if (a.autoToday) lines.push(`• الموظف رد على ${N(a.autoToday)} رسالة آخر ٢٤ ساعة.`);
  store.ai.briefing = { t: Date.now(), text: lines.join('\n') }; saveSoon(); s.json(store.ai.briefing);
});
r.post('/api/ai/campaign', (q, s) => s.json(campaign(q.body || {}, S())));
r.post('/api/ai/reengage', (q, s) => {
  const now = Date.now(), D = S().dormantDays * 864e5;
  const list = chatsList().filter(c => now - lastOf(c).ts > D).map(c => ({ jid: c.jid, name: c.name || '+' + c.phone, phone: c.phone, days: Math.floor((now - lastOf(c).ts) / 864e5), bought: (store.crm[c.jid]?.orders || []).length > 0 }))
    .sort((a, b) => b.bought - a.bought || a.days - b.days).slice(0, 40);
  s.json({ list, message: `هلا {الاسم}، اشتقنا لك في ${S().shopName} 🌷 نزلت عندنا تشكيلة جديدة، تحب أرسل لك صورها؟` });
});
// ---- simulator (FAKE_WA=1 only): lets tests and design QA drive a full flow without a phone
if (FAKE) {
  r.post('/api/sim/link', (q, s) => { fake?.link(q.body?.me || '966500000000', q.body?.history); s.json({ ok: true }) });
  r.post('/api/sim/incoming', (q, s) => { const { jid, text, name, ts } = q.body || {}; s.json({ id: fake?.incoming(jid, text, name, ts) }) });
  r.get('/api/sim/outbox', (q, s) => s.json(fake?.outbox || []));
}
r.use(express.static(path.join(HERE, 'public'), { index: 'index.html' }));
app.get('/', (q, s) => s.status(404).send('Not found'));
app.use('/' + TOKEN, r); app.use((q, s) => s.status(404).send('Not found'));
const server = app.listen(PORT, HOST, () => console.log(`ENGINE READY http://${HOST}:${PORT}/${TOKEN}/`));
const bye = () => { try { save() } catch { } process.exit(0) };
process.on('SIGINT', bye); process.on('SIGTERM', bye);
if (process.env.EXIT_WITH_STDIN === '1') { process.stdin.on('end', bye); process.stdin.resume() }   // parent app closed → stop
backup(); setInterval(() => { try { save() } catch { } }, 60e3).unref(); setInterval(backup, 6 * 3600e3).unref();
export { server };
