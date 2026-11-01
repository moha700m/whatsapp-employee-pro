// موظف واتساب — local engine. Runs on 127.0.0.1 inside the desktop app.
// WhatsApp link via Baileys (full history sync), local JSON store, local Saudi brain (Python, offline).
// Nothing is sent unless the owner presses «إرسال», or the owner switched the auto-reply employee ON.
// SECURITY: libsignal prints whole sessions («Closing session: SessionEntry {… privKey, rootKey …}») with console.*; never let key material reach engine.log.
{ const SECRET = /SessionEntry|privKey|rootKey|chainKey|baseKey|ephemeralKeyPair|remoteIdentityKey|pendingPreKey|Closing session|Opening session|Removing old closed session|Closing open session|Session error|Bad MAC|Failed to decrypt/i;
  const bad = a => a.some(x => (typeof x === 'string' && SECRET.test(x)) || (x && typeof x === 'object' && (Buffer.isBuffer(x) || x instanceof Uint8Array || /SessionEntry|SessionRecord/.test(x.constructor?.name || '') || ('_chains' in x) || ('indexInfo' in x))));
  for (const k of ['log', 'info', 'warn', 'error', 'debug', 'trace']) { const o = console[k].bind(console); console[k] = (...a) => { if (bad(a)) return; o(...a) } } }
import express from 'express'; import QRCode from 'qrcode'; import fs from 'fs'; import path from 'path'; import crypto from 'crypto';
import { fileURLToPath } from 'url';
import { analyze } from './analyze.js'; import { csv, vcf, reportHTML } from './report.js';
import { decide, AUTO_DEFAULTS, SKIP_AR, scheduleOpen, inWindow, hm, BAD_JID, migrateAuto } from './employee.js';
import { campaign, OCCASIONS } from './campaigns.js';
import { humanSend, limits, canSend } from './antiban.js';
import * as CH from './channels.js';
import { isLid, isPn, bare, normJid, fmtPhone, searchForms } from './people.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DIR = process.env.DATA_DIR || path.join(HERE, 'data'); fs.mkdirSync(DIR, { recursive: true });
const PORT = +process.env.PORT || 8796, HOST = '127.0.0.1';
const TOKEN = (process.env.TOKEN || crypto.randomBytes(12).toString('hex')).trim();
const BRAIN_URL = process.env.BRAIN_URL || '', BRAIN_KEY = process.env.BRAIN_KEY || '';
const FAKE = process.env.FAKE_WA === '1', FAKE_FAST = FAKE && process.env.HUMAN_TYPING !== '1';
const VERSION = process.env.APP_VERSION || '2.4.2';
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
for (const [k, v] of Object.entries({ chats: {}, contacts: {}, crm: {}, audit: [], alerts: [], auth: {}, ai: {}, autoHist: {}, lidMap: {}, plan: {}, wa: {}, sends: [], chan: { known: {}, drafts: [], reminders: [], posts: {} } })) store[k] ??= v;
const DEF = {
  shopName: 'محل الورد', shopType: 'محل ورد', city: '', phone: '', about: '', delivery: '', logo: '', brand: '#0A7A3E',
  hoursFrom: '09:00', hoursTo: '23:00', tz: 'Asia/Riyadh', products: [],
  templates: [{ k: 'ترحيب', t: 'هلا والله، نورتنا. كيف أقدر أخدمك؟' }, { k: 'أسعار', t: 'أسعار الباقات تبدأ من ١٥٠ ريال، تحب أرسل لك صور الخيارات؟' },
    { k: 'تأكيد', t: 'تم تأكيد طلبك ✅ وموعد التوصيل …' }, { k: 'شكر', t: 'شكراً لثقتك فينا، نتشرف بخدمتك دايم 🌹' }],
  tags: ['جديد', 'مهتم', 'طلب', 'تم التوصيل', 'مميز'], followUpDays: 1, dormantDays: 30, hotScore: 60, notifyHot: true, notifyNew: true,
  aiEnabled: true, aiModel: 'auto', teach: null, aiTone: 'ودودة ومحترفة', sessionMinutes: 120, tourDone: false, hintsOff: [], theme: 'auto',
  autoReply: { ...AUTO_DEFAULTS }, notify: { on: true, msg: true, order: true, alert: true, sound: true, volume: 70, quiet: false, quietFrom: '23:00', quietTo: '08:00' },
};
store.settings = { ...DEF, ...(store.settings || {}), autoReply: { ...AUTO_DEFAULTS, ...(store.settings?.autoReply || {}) } };
migrateAuto(store.settings.autoReply);
for (const t of store.settings.templates || []) if (t.k === 'ترحيب' && t.t === 'هلا والله، نورتنا 🌷 كيف أقدر أخدمك؟') t.t = 'هلا والله، نورتنا. كيف أقدر أخدمك؟';
if (['fixed', 'ai'].includes(store.settings.autoReply.mode) && store.settings.autoReply.mode === 'ai') store.settings.autoReply.mode = 'smart';
const S = () => store.settings;
let saveT; const save = () => { clearTimeout(saveT); const tmp = DATA + '.tmp'; const fd = fs.openSync(tmp, 'w'); fs.writeSync(fd, JSON.stringify(store)); fs.fsyncSync(fd); fs.closeSync(fd); fs.renameSync(tmp, DATA) };
const saveSoon = () => { clearTimeout(saveT); saveT = setTimeout(save, 500) };
const audit = (type, info = {}) => { store.audit.unshift({ t: Date.now(), type, ...info }); store.audit = store.audit.slice(0, 1000); saveSoon() };
// ---- live events: UI (SSE) + desktop notifier (Python, internal key) ----
const UIS = new Set(), NOTS = new Set();
const sse = (set, type, data) => { const line = `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`; for (const s of set) try { s.write(line) } catch { set.delete(s) } };
const emit = (type, data = {}) => sse(UIS, type, data);
const NOTIFY_DEFAULTS = { on: true, msg: true, order: true, alert: true, sound: true, volume: 70, quiet: false, quietFrom: '23:00', quietTo: '08:00' };
function notify(kind, title, body, jid) {   // kind: msg | order | alert → native Windows toast + soft chime (the Python side shows it)
  const n = { ...NOTIFY_DEFAULTS, ...(S().notify || {}) }; if (!n.on || !n[kind]) return;
  const quiet = n.quiet && inWindow(n.quietFrom, n.quietTo, hm(new Date(), S().tz));
  const ev = { kind, title: String(title).slice(0, 80), body: String(body || '').slice(0, 160), jid: jid || '', sound: n.sound && !quiet, volume: Math.max(0, Math.min(100, +n.volume || 0)), quiet };
  console.log(new Date().toISOString(), 'NOTIFY', kind, quiet ? 'quiet' : '', ev.sound ? 'sound' : 'silent');
  sse(NOTS, 'notify', ev); emit('notify', ev);
}
const alert = (kind, jid, text) => { setImmediate(() => { emit('alert', { kind, jid }); if (kind === 'human' || kind === 'hot') notify('alert', kind === 'hot' ? 'عميل مهتم' : 'يحتاج ردك', text, jid) }); store.alerts.unshift({ id: crypto.randomUUID(), t: Date.now(), kind, jid, text, read: false }); store.alerts = store.alerts.slice(0, 300); saveSoon() };
let byLidCache = { t: 0, m: {} };
const phoneOf = j => (j || '').split('@')[0].split(':')[0];
const canon = j => { j = normJid(j); return (isLid(j) && store.lidMap[j]) || j };
const chat = jid => { jid = canon(jid); return store.chats[jid] ??= { jid, phone: isLid(jid) ? '' : phoneOf(jid), isGroup: jid.endsWith('@g.us'), name: '', messages: [] } };
// learn lid -> phone, and merge a chat that was stored under the LID into the phone-number chat
function learnLid(lid, pn) {
  lid = normJid(lid); pn = normJid(pn); if (!isLid(lid) || !isPn(pn) || store.lidMap[lid] === pn) return false;
  store.lidMap[lid] = pn; byLidCache.t = 0;
  const a = store.chats[lid];
  if (a) {
    const b = store.chats[pn] ??= { jid: pn, phone: phoneOf(pn), isGroup: false, name: '', messages: [] };
    const ids = new Set(b.messages.map(m => m.id)); for (const m of a.messages) if (!ids.has(m.id)) b.messages.push(m);
    b.name ||= a.name; b.t = Math.max(b.t || 0, a.t || 0); delete store.chats[lid];
  }
  if (store.crm[lid]) { store.crm[pn] = { ...store.crm[lid], ...store.crm[pn] }; delete store.crm[lid] }
  if (store.autoHist[lid]) { store.autoHist[pn] ??= store.autoHist[lid]; delete store.autoHist[lid] }
  for (const x of store.alerts) if (x.jid === lid) x.jid = pn;
  saveSoon(); return true;
}
function learnFromKey(k) {
  if (!k) return;
  if (isLid(k.remoteJid)) { if (k.senderPn) learnLid(k.remoteJid, k.senderPn); else if (k.participantPn) learnLid(k.remoteJid, k.participantPn) }
  if (isLid(k.senderLid) && isPn(k.remoteJid)) learnLid(k.senderLid, k.remoteJid);
  if (isLid(k.participant) && k.participantPn) learnLid(k.participant, k.participantPn);
  // Baileys v7: the "other" addressing form of the same chat/sender
  if (isLid(k.remoteJid) && isPn(normJid(k.remoteJidAlt))) learnLid(k.remoteJid, k.remoteJidAlt);
  if (isPn(k.remoteJid) && isLid(normJid(k.remoteJidAlt))) learnLid(k.remoteJidAlt, k.remoteJid);
  if (isLid(k.participant) && isPn(normJid(k.participantAlt))) learnLid(k.participant, k.participantAlt);
  if (isPn(k.participant) && isLid(normJid(k.participantAlt))) learnLid(k.participantAlt, k.participant);
}
function txt(m) {
  const x = unwrap(m.message);
  if (x.reactionMessage || x.protocolMessage || x.senderKeyDistributionMessage && Object.keys(x).length <= 2 || x.pollUpdateMessage || x.keepInChatMessage) return '';   // not a customer message
  return x.conversation || x.extendedTextMessage?.text || x.imageMessage?.caption || x.videoMessage?.caption || x.documentMessage?.caption ||
    x.buttonsResponseMessage?.selectedDisplayText || x.templateButtonReplyMessage?.selectedDisplayText || x.listResponseMessage?.title || x.interactiveResponseMessage?.body?.text ||
    (x.pollCreationMessage || x.pollCreationMessageV3)?.name || (x.ptvMessage ? '[فيديو]' : x.liveLocationMessage ? '[موقع]' : x.contactsArrayMessage ? '[جهة اتصال]' : '') ||
    (x.imageMessage ? '[صورة]' : x.audioMessage ? '[رسالة صوتية]' : x.locationMessage ? '[موقع]' : x.documentMessage ? '[ملف]' : x.stickerMessage ? '[ملصق]' : x.videoMessage ? '[فيديو]' : x.contactMessage ? '[جهة اتصال]' : '');
}
// WhatsApp timestamps arrive as number, numeric string, or protobuf Long {low, high}; seconds → ms
function tsMs(v) {
  if (v == null) return 0; if (typeof v === 'object') { if (typeof v.toNumber === 'function') v = v.toNumber(); else if ('low' in v) v = (v.high >>> 0) * 4294967296 + (v.low >>> 0); else v = +v }
  v = Number(v); if (!Number.isFinite(v) || v <= 0) return 0; return v < 1e12 ? v * 1000 : v;
}
// ---------------- media (images, video, voice notes, stickers, documents) ----------------
// The message's media keys are kept in DATA_DIR/media/idx/<id>.json; the file itself is fetched only when the owner opens it,
// then cached in DATA_DIR/media/<id>.<ext> (kept across restarts and upgrades).
const MDIR = path.join(DIR, 'media'), MIDX = path.join(MDIR, 'idx'); fs.mkdirSync(MIDX, { recursive: true });
const MKINDS = { imageMessage: 'image', videoMessage: 'video', audioMessage: 'audio', stickerMessage: 'sticker', documentMessage: 'document', documentWithCaptionMessage: 'document' };
const safeId = id => String(id || '').replace(/[^A-Za-z0-9_-]/g, '').slice(0, 80);
const EXT = { 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp', 'image/gif': 'gif', 'video/mp4': 'mp4', 'audio/ogg': 'ogg', 'audio/mpeg': 'mp3', 'audio/mp4': 'm4a', 'application/pdf': 'pdf' };
function unwrap(x) { x = x || {}; for (let i = 0; i < 4; i++) { const y = x.ephemeralMessage?.message || x.viewOnceMessage?.message || x.viewOnceMessageV2?.message || x.viewOnceMessageV2Extension?.message || x.documentWithCaptionMessage?.message || x.editedMessage?.message || x.deviceSentMessage?.message; if (!y) break; x = y } return x }
function mediaOf(m) {
  const x = unwrap(m.message); const k = Object.keys(MKINDS).find(k => x[k]); if (!k) return null; const v = x[k];
  const mime = String(v.mimetype || '').split(';')[0] || (k === 'stickerMessage' ? 'image/webp' : '');
  const meta = { type: MKINDS[k], mime, ...(v.seconds ? { secs: Number(v.seconds) } : {}), ...(v.ptt ? { ptt: true } : {}), ...(v.fileName ? { name: String(v.fileName).slice(0, 120) } : {}),
    ...(v.fileLength ? { size: Number(v.fileLength) } : {}), ...(v.width ? { w: v.width, h: v.height } : {}), ...(v.jpegThumbnail ? { thumb: Buffer.from(v.jpegThumbnail).toString('base64').slice(0, 8000) } : {}) };
  try { const id = safeId(m.key.id), f = path.join(MIDX, id + '.json'); if (id && !fs.existsSync(f)) fs.writeFileSync(f, JSON.stringify({ key: m.key, message: m.message, messageTimestamp: m.messageTimestamp }, (kk, vv) => vv?.type === 'Buffer' || vv instanceof Uint8Array ? { $b: Buffer.from(vv.data || vv).toString('base64') } : vv)) } catch { }
  return meta;
}
const revive = (k, v) => v && typeof v === 'object' && typeof v.$b === 'string' ? Buffer.from(v.$b, 'base64') : v;
const mediaBusy = new Map();
async function mediaFile(id) {
  id = safeId(id); if (!id) return null;
  const have = fs.readdirSync(MDIR).find(f => f.startsWith(id + '.')); if (have) return path.join(MDIR, have);
  if (mediaBusy.has(id)) return mediaBusy.get(id);
  const job = (async () => {
    const ix = path.join(MIDX, id + '.json'); if (!fs.existsSync(ix)) return null;
    const msg = JSON.parse(fs.readFileSync(ix, 'utf8'), revive); const x = unwrap(msg.message); const k = Object.keys(MKINDS).find(k => x[k]); const v = x[k] || {};
    let buf;
    if (FAKE) buf = v.fakeData ? Buffer.from(v.fakeData, 'base64') : null;
    else {
      const B = SOCK?._B; if (!B?.downloadMediaMessage) throw new Error('offline');
      // expired history media → ask the phone to re-upload (updateMediaMessage), then retry
      buf = await B.downloadMediaMessage(msg, 'buffer', {}, { logger: SOCK._log, reuploadRequest: SOCK.updateMediaMessage });
    }
    if (!buf?.length) return null;
    const mime = String(v.mimetype || '').split(';')[0] || (k === 'stickerMessage' ? 'image/webp' : 'application/octet-stream');
    const f = path.join(MDIR, `${id}.${EXT[mime] || (v.fileName && path.extname(v.fileName).slice(1).replace(/[^a-z0-9]/gi, '').slice(0, 6)) || 'bin'}`);
    fs.writeFileSync(f, buf); return f;
  })().finally(() => mediaBusy.delete(id));
  mediaBusy.set(id, job); return job;
}

function addMsg(m) {
  learnFromKey(m.key); if (isLid(normJid(m.key?.remoteJid)) && !store.lidMap[normJid(m.key.remoteJid)]) lidAsk(m.key.remoteJid); const j = canon(m.key?.remoteJid); if (BAD_JID(j) && !j?.endsWith('@g.us')) return null; if (!j) return null;
  const t = txt(m); if (!t) return null; const c = chat(j);
  if (c.messages.some(x => x.id === m.key.id)) return null;
  const media = mediaOf(m);
  const msg = { id: m.key.id, ...(m.key.remoteJid !== j ? { rjid: m.key.remoteJid } : {}), fromMe: !!m.key.fromMe, ts: tsMs(m.messageTimestamp) || Date.now(), text: t, ...(media ? { media } : {}) };
  c.messages.push(msg); if (c.messages.length > 2000) c.messages.splice(0, c.messages.length - 2000);
  if (!m.key.fromMe && m.pushName && !c.name) c.name = m.pushName; if (msg.ts > (c.t || 0)) c.t = msg.ts; return { c, msg };
}
function addContact(c) {
  if (!c?.id) return; const pnOf = c.phoneNumber || c.jid || (isPn(c.id) ? c.id : null);
  if (c.lid && isPn(normJid(pnOf))) learnLid(c.lid, pnOf); if (isLid(normJid(c.id)) && isPn(normJid(pnOf))) learnLid(c.id, pnOf);
  const id = canon(c.id); store.contacts[id] = { ...store.contacts[id], ...Object.fromEntries(Object.entries(c).filter(([, v]) => v != null && v !== '')) };
  const ch = store.chats[id]; if (ch && (c.name || c.notify || c.verifiedName)) ch.name = c.name || c.notify || c.verifiedName || ch.name;
}

// ---------------- local brain (Python service) ----------------
let brainOk = false;
// opt.ai → the brain may use the bundled local model (only if the owner left «الذكاء المحلي» on); those calls can take seconds
const aiOn = () => S().aiModel !== 'off';
async function brain(route, body, opt = {}) {
  if (!BRAIN_URL || !S().aiEnabled) return null;
  const ai = !!opt.ai && aiOn(); const ctl = new AbortController(), to = setTimeout(() => ctl.abort(), opt.timeout || (ai ? 90e3 : 5000));
  try {
    const r = await fetch(BRAIN_URL + route, { method: 'POST', signal: ctl.signal, headers: { 'content-type': 'application/json', 'x-brain-key': BRAIN_KEY },
      body: JSON.stringify({ teach: S().teach, ...body, ai, shop: { name: S().shopName, location: S().city, city: S().city, hours: `${S().hoursFrom} - ${S().hoursTo}`, delivery: S().delivery || '', about: S().about || '' }, products: S().products }) });
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
let state = { status: 'starting', qr: null, me: null, syncing: false, lastSync: null, since: Date.now(), error: null, attempts: 0 }, realSend = null, realPresence = null, realRead = null, SOCK = null;
const why = (c, reason, extra = {}) => { const t = SKIP_AR[reason] || reason; console.log(new Date().toISOString(), 'AUTO skip', reason, extra.detail || ''); const ch = store.chats[c.jid]; if (ch) ch.autoWhy = { t: Date.now(), why: t, code: reason };
  if (reason !== 'off') audit('auto_skip', { jid: c.jid, to: c.label || c.name || 'عميل', why: t, code: reason, ...extra }); saveSoon() };
// ---- batching: wait for a short silence, then ONE reply that covers every unanswered message (nothing is ever dropped on cooldown) ----
const BATCH = new Map();   // jid -> { first, timer }
const QUIET_MS = () => FAKE_FAST ? +(process.env.WAE_QUIET_MS || 400) : 10e3, CAP_MS = () => FAKE_FAST ? +(process.env.WAE_CAP_MS || 2000) : 45e3;
const MEDIA_ONLY = t => /^\[(صورة|رسالة صوتية|ملصق|فيديو|ملف|موقع|جهة اتصال)\]$/.test(String(t || '').trim());
const CLARIFY = ['حيّاك، وش كان قصدك بالضبط؟ تبي تشوف الأسعار، التوصيل، ولا تطلب؟', 'حيّاك الله، وضّح لي أكثر: تبي الأسعار، ولا التوصيل، ولا تبي تطلب؟'];
const ACK = 'وصلت، بشوفها وأرد عليك';
const tOf = m => m.at || m.ts;
function unanswered(c) {   // customer messages after our last outgoing message (auto or manual)
  const lastOut = Math.max(0, ...c.messages.filter(m => m.fromMe).map(tOf), ...(store.autoHist[c.jid]?.times || []));   // auto-send time in ms (WA timestamps are whole seconds)
  return c.messages.filter(m => !m.fromMe && tOf(m) > lastOut && Date.now() - tOf(m) < 12 * 3600e3).sort((x, y) => tOf(x) - tOf(y));
}
async function onIncoming(c, msg) {
  if (c.isGroup || msg.fromMe || BAD_JID(c.jid)) return;
  const sc = keywordScore(c); store.crm[c.jid] = { ...store.crm[c.jid], score: Math.max(sc, store.crm[c.jid]?.score || 0) };
  if (S().notifyHot && sc >= S().hotScore) alert('hot', c.jid, `عميل مهتم: ${c.label || c.name || 'عميل'} — «${msg.text.slice(0, 60)}»`);
  else if (S().notifyNew && c.messages.filter(m => !m.fromMe).length <= 1) alert('new', c.jid, `عميل جديد: ${c.label || c.name || 'عميل'}`);
  if (/(ابي|ابغى|أبغى|أبي|ودي|بغيت)\s*(اطلب|أطلب|بوكيه|ورد|باقة|تنسيق)|طلب جديد|اطلب/.test(msg.text)) notify('order', 'طلب جديد: ' + (c.label || c.name || 'عميل'), msg.text, c.jid);
  if (!S().autoReply?.enabled) return why(c, 'off');
  const now = Date.now(), B = BATCH.get(c.jid) || { first: now, n: 0 }; clearTimeout(B.timer); B.n++;
  const wait = Math.max(0, Math.min(QUIET_MS(), B.first + CAP_MS() - now));
  B.timer = setTimeout(() => { BATCH.delete(c.jid); flush(c.jid).catch(e => console.log(new Date().toISOString(), 'AUTO flush error', String(e?.message || e).slice(0, 120))) }, wait);
  BATCH.set(c.jid, B); pending.set(c.jid, B.timer);
  if (store.chats[c.jid]) store.chats[c.jid].autoWhy = { t: now, why: 'بيرد بعد ثواني (ينتظر لين يخلص العميل كلامه)', code: 'queued' };
  console.log(new Date().toISOString(), 'AUTO wait', `msgs=${B.n}`, `in=${wait}ms`);
}
async function flush(jid, tries = 0) {
  pending.delete(jid); const c0 = store.chats[jid]; if (!c0) return; const c = resolve(c0);
  const list = unanswered(c0); if (!list.length) return why(c, 'owner_replied');
  const last = list[list.length - 1], texts = list.map(m => m.text).filter(t => !MEDIA_ONLY(t)), mediaOnly = !texts.length;
  const combined = texts.join('\n').slice(0, 1500);
  const ar = { ...AUTO_DEFAULTS, ...S().autoReply };
  const trigger = { ...last, text: mediaOnly ? last.text : combined };
  let d;
  if (mediaOnly) {
    const pre = decide(c0, { ...trigger, text: 'x' }, { settings: S(), connected: state.status === 'connected' && !!realSend, history: store.autoHist, brain: null });
    d = pre.action === 'skip' ? pre : { action: 'reply', reason: 'media', kind: 'media_ack', text: ACK };
    if (d.action !== 'skip' || d.reason === 'cooldown') alert('human', jid, `${c.label || 'عميل'} أرسل ${last.text} — شوفه ورد عليه`);
  } else {
    const b = await brain('/think', { text: combined, customer: c.name, messages: msgsFor(c0, 8), after_hours: !inWindow(S().hoursFrom, S().hoursTo, hm(new Date(), S().tz)) && !(Date.now() - (store.autoHist[jid]?.afterHoursAt || 0) < 14 * 3600e3) }, { ai: false });   // rules + owner FAQ only
    if (b && b.engine === 'ai') { b.reply = ''; b.safe_auto = false }
    if (b?.lead_score) store.crm[jid] = { ...store.crm[jid], score: Math.max(b.lead_score, store.crm[jid]?.score || 0) };
    d = decide(c0, trigger, { settings: S(), connected: state.status === 'connected' && !!realSend, history: store.autoHist, brain: b }); d.engine = b?.engine || 'rules';
  }
  if (d.alertOwner) alert('human', jid, `يحتاج ردك: ${c.label || 'عميل'} — «${(combined || last.text).slice(0, 60)}»`);
  console.log(new Date().toISOString(), 'AUTO think', `msgs=${list.length}`, `chars=${combined.length}`, `kind=${d.kind || d.reason}`, `action=${d.action}`);
  if (d.action === 'skip' && d.reason === 'cooldown') {   // defer, never drop
    const h = store.autoHist[jid] || { times: [] }, lastT = Math.max(0, ...h.times), waitMs = Math.max(1000, ar.cooldownMin * 60e3 - (Date.now() - lastT));
    console.log(new Date().toISOString(), 'AUTO deferred', `batch=${list.length}`, 'cooldown', `in=${Math.round(waitMs / 1000)}s`);
    if (store.chats[jid]) store.chats[jid].autoWhy = { t: Date.now(), why: `بيرد بعد ${Math.max(1, Math.round(waitMs / 1000))} ثانية (يهدّي عشان رقمك يبقى بأمان)`, code: 'queued' };
    pending.set(jid, setTimeout(() => flush(jid, tries + 1).catch(() => {}), waitMs)); return;
  }
  if (d.action === 'skip') { if (/^(already_handed_off|daily_limit)$/.test(d.reason)) alert('human', jid, `يحتاج ردك: ${c.label || 'عميل'} — «${combined.slice(0, 60) || last.text}»`); console.log(new Date().toISOString(), 'AUTO batch', `msgs=${list.length}`, 'skip', d.reason); return why(c, d.reason) }
  // never the same text twice in a row: prefer something new, else stay quiet and tell the owner
  const prevAuto = [...c0.messages].filter(m => m.fromMe && m.auto).sort((x, y) => tOf(y) - tOf(x))[0];
  if (prevAuto && prevAuto.text === d.text && Date.now() - tOf(prevAuto) < 6 * 3600e3) {
    const alt = [...CLARIFY, ar.message, ar.handoffMessage].find(t => t && t !== prevAuto.text && t !== d.text);
    if (d.action === 'handoff' || !alt) { alert('human', jid, `يحتاج ردك: ${c.label || 'عميل'} — «${(combined || last.text).slice(0, 60)}»`); console.log(new Date().toISOString(), 'AUTO batch', `msgs=${list.length}`, 'skip same_text'); return why(c, 'same_text') }
    d = { ...d, text: alt, kind: d.kind + '_alt' };
  }
  console.log(new Date().toISOString(), 'AUTO batch', `msgs=${list.length}`, '→', d.action, d.kind || '');
  return sendAuto(jid, trigger, d);
}
const lastIncomingKey = c => { const m = [...c.messages].filter(x => !x.fromMe).sort((a, b) => b.ts - a.ts)[0]; return m ? { remoteJid: m.rjid || c.jid, id: m.id, fromMe: false } : null };
const sendLog = auto => { store.sends.push({ t: Date.now(), auto }); store.sends = store.sends.filter(x => Date.now() - x.t < 864e5) };
async function sendAuto(jid, trigger, d, tries = 0) {
  const c = store.chats[jid]; if (!c) return;
  const ar = { ...AUTO_DEFAULTS, ...S().autoReply };
  const C = resolve(c);
  if (!ar.enabled) return why(C, 'off_before_send');
  // «you already replied»: only a MANUAL message that arrived after the customer's message (by arrival time; our own auto replies don't count)
  const tAt = trigger.at || trigger.ts; if (c.messages.some(m => m.fromMe && !m.auto && m.at && m.at > tAt)) return why(C, 'owner_replied');
  if (!c.messages.some(m => !m.fromMe)) return why(C, 'not_first');
  if (!realSend || state.status !== 'connected') { audit('auto_reply_failed', { jid, err: 'الواتساب غير متصل' }); return why(C, 'offline') }
  const lim = limits(ar, store.wa.linkedAt); if (FAKE_FAST) lim.minGapMs = 0; const ok = canSend(store.sends, lim);
  if (!ok.ok && ok.wait && tries < 40) { console.log(new Date().toISOString(), 'AUTO deferred', 'gap', `in=${Math.round(ok.wait / 1000)}s`); pending.set(jid, setTimeout(() => { pending.delete(jid); sendAuto(jid, trigger, d, tries + 1).catch(() => {}) }, ok.wait)); return }
  if (!ok.ok) { alert('human', jid, `يحتاج ردك: ${C.label} — «${trigger.text.slice(0, 60)}»`); return why(C, 'rate_limit', { detail: ok.why || 'تهدئة' }) }
  const to = trigger.rjid && /@(lid|s\.whatsapp\.net)$/.test(trigger.rjid) ? trigger.rjid : jid;   // reply to the exact address the customer wrote from (LID or phone)
  try {
    const m = ar.humanTyping !== false && !FAKE_FAST
      ? await humanSend({ jid: to, text: d.text, send: realSend, presence: realPresence, read: realRead, readKey: lastIncomingKey(c), incoming: trigger.text })
      : await realSend(to, { text: d.text });
    keepSent(m); console.log(new Date().toISOString(), 'AUTO sent', d.action, `addr=${to.split('@')[1]}`); if (store.chats[jid]) store.chats[jid].autoWhy = { t: Date.now(), why: d.action === 'handoff' ? 'رد برسالة انتظار وحوّلها لك' : 'رد عليه', code: 'sent' };
    if (c.messages.some(x => x.fromMe && x.ts > trigger.ts && !x.auto)) { /* owner replied while we were typing — still sent; logged */ }
    sendLog(true); const r = addMsg(m); if (r) r.msg.auto = true; else { const x = c.messages.find(y => y.id === m?.key?.id); if (x) x.auto = true }
    const h = store.autoHist[jid] ??= { times: [] }; h.times = [...h.times.filter(t => Date.now() - t < 864e5), Date.now()]; if (/^after_hours/.test(d.kind || '')) h.afterHoursAt = Date.now();
    const lb = resolve(c).label;
    if (d.action === 'handoff') { h.handoffAt = Date.now(); alert('human', jid, `يحتاج ردك: ${lb} — «${trigger.text.slice(0, 60)}»`) }
    audit(d.action === 'handoff' ? 'auto_handoff' : 'auto_reply', { jid, to: lb, kind: d.kind, len: d.text.length, preview: d.text.slice(0, 90), q: trigger.text.slice(0, 60), engine: d.engine || 'rules' });
    saveSoon();
  } catch (e) {
    audit('auto_reply_failed', { jid, err: String(e.message).slice(0, 80) }); why(C, 'send_failed', { detail: String(e.message).slice(0, 80) });
    const fails = store.audit.filter(a => a.type === 'auto_reply_failed' && Date.now() - a.t < 36e5).length;
    if (fails >= 3 && S().autoReply.enabled) { S().autoReply.enabled = false; audit('auto_reply_disabled', { preview: 'إيقاف تلقائي لحماية الرقم: أخطاء إرسال متكررة' }); alert('human', jid, 'وقّفنا الموظف مؤقتاً لحماية رقمك (أخطاء إرسال متكررة). شغّله من صفحة الموظف إذا كل شي تمام.') }
  }
}
// ---------------- WhatsApp connection ----------------
const SENT = new Map();   // id -> sent WAMessage, so Baileys can answer retry receipts (else the customer sees «waiting for this message»)
const keepSent = m => { if (m?.key?.id && m.message) { SENT.set(m.key.id, m); if (SENT.size > 500) SENT.delete(SENT.keys().next().value) } };
let fake = null, connecting = false, profileIdx = 0, failsNoQr = 0, retryT = null;
// Ubuntu/Chrome is what WhatsApp accepts for QR linking (the "Desktop" profiles get 428 Connection Terminated before any QR).
const PROFILES = [B => B.Browsers.ubuntu('Chrome'), B => B.Browsers.appropriate ? B.Browsers.appropriate('Chrome') : B.Browsers.ubuntu('Chrome'), B => B.Browsers.macOS('Chrome')];
const WHY = { 428: 'واتساب قطع الاتصال قبل ما يعطينا الرمز', 405: 'واتساب رفض نوع الجهاز', 408: 'انتهت مهلة الاتصال بواتساب', 403: 'واتساب منع الاتصال', 500: 'خطأ من خوادم واتساب', 503: 'خوادم واتساب مشغولة', 515: 'واتساب طلب إعادة تشغيل الاتصال' };
function diagnose(code, msg) {
  if (/ENOTFOUND|EAI_AGAIN|ECONNREFUSED|ETIMEDOUT|ECONNRESET|getaddrinfo|socket hang up/i.test(msg)) return 'ما قدرنا نوصل لخوادم واتساب — تأكد من الإنترنت، أو إن الجدار الناري/برنامج الحماية ما يمنع البرنامج';
  return WHY[code] || ('انقطع الاتصال بواتساب' + (code ? ` (رمز ${code})` : ''));
}
function scheduleReconnect(ms) { clearTimeout(retryT); retryT = setTimeout(connect, ms) }
async function connect() {
  if (connecting) return; connecting = true;
  try {
    let sock;
    if (FAKE) { const { makeFakeSocket } = await import('./fakewa.js'); sock = fake = makeFakeSocket() }
    else {
      const pino = (await import('pino')).default; const M = await import('baileys'); const B = M.useMultiFileAuthState ? M : M.default;
      const makeWASocket = typeof B.default === 'function' ? B.default : B.makeWASocket;
      const { state: auth, saveCreds } = await B.useMultiFileAuthState(path.join(DIR, 'auth')); const { version } = await B.fetchLatestBaileysVersion().catch(() => ({}));
      sock = makeWASocket({ auth, version, logger: pino({ level: 'silent' }), browser: PROFILES[profileIdx % PROFILES.length](B), syncFullHistory: true,
        shouldSyncHistoryMessage: () => true, markOnlineOnConnect: false, printQRInTerminal: false, getMessage: async k => SENT.get(k?.id)?.message || undefined });
      sock.ev.on('creds.update', saveCreds); sock._B = B; sock._log = pino({ level: 'silent' });
    }
    const old = SOCK; realSend = sock.sendMessage.bind(sock); realPresence = sock.sendPresenceUpdate?.bind(sock) || null; realRead = sock.readMessages?.bind(sock) || null; SOCK = sock;
    if (old && old !== sock) try { old.end?.(undefined) } catch { }
    // Only realSend (owner presses Send, or the owner-enabled employee) may send. Every other mutating call is disabled.
    for (const f of ['sendMessage', 'readMessages', 'sendReceipt', 'sendReceipts', 'sendPresenceUpdate', 'chatModify', 'relayMessage', 'updateBlockStatus', 'groupLeave', 'star', 'addOrEditContact', 'removeContact', 'updateProfileStatus', 'updateProfileName'])
      if (typeof sock[f] === 'function') sock[f] = async () => {};
    sock.ev.on('connection.update', async u => { if (SOCK !== sock) return;  // ignore events from a replaced socket
      if (u.qr) { state.qr = await QRCode.toDataURL(u.qr, { width: 360, margin: 1 }); state.status = 'qr'; state.error = null; failsNoQr = 0; console.log('WA qr ready') }
      if (u.connection === 'open') { setTimeout(() => tryLidRepo().then(saveSoon), 3000); if (!store.wa.linkedAt || store.wa.me !== phoneOf(sock.user?.id)) { store.wa.linkedAt = Date.now(); store.wa.me = phoneOf(sock.user?.id) } state.status = 'connected'; state.qr = null; state.error = null; failsNoQr = 0; state.me = phoneOf(sock.user?.id); state.syncing = true; audit('whatsapp_linked', {}); clearTimeout(state._st); state._st = setTimeout(() => state.syncing = false, 25e3) }
      if (u.connection === 'close') {
        const err = u.lastDisconnect?.error, code = err?.output?.statusCode, msg = String(err?.message || ''); connecting = false; state.attempts++;
        console.log(new Date().toISOString(), 'WA close', code, msg.slice(0, 160));
        if (code === 401 || code === sock._B?.DisconnectReason?.loggedOut) { state.status = 'loggedOut'; state.qr = null; fs.rmSync(path.join(DIR, 'auth'), { recursive: true, force: true }); return scheduleReconnect(1500) }
        if (code === 515) { state.status = 'reconnecting'; return scheduleReconnect(500) }          // restart required right after scanning
        const linked = !!sock.authState?.creds?.registered || !!state.me;
        if (!linked && state.status !== 'qr') { failsNoQr++; if (failsNoQr % 2 === 0) profileIdx++ }  // no QR yet → try the next browser profile
        state.status = 'reconnecting'; state.qr = null; state.error = { code: code || null, text: diagnose(code, msg), at: Date.now() };
        scheduleReconnect(Math.min(30e3, 2000 * Math.max(1, failsNoQr)));
      }
    });
    sock.ev.on('messaging-history.set', ({ chats, contacts, messages }) => {
      chats?.forEach(chatPn); chats?.forEach(c => chanSeen(c.id, c.name));
      contacts?.forEach(addContact);
      chats?.forEach(c => { if (BAD_JID(c.id)) return; const x = chat(c.id); if (c.name) x.name = c.name; const t = tsMs(c.conversationTimestamp); if (t > (x.t || 0)) x.t = t; pinOf(x, c); x.hist = true });
      messages?.forEach(addMsg); tryLidRepo();
      state.syncing = true; state.lastSync = Date.now(); clearTimeout(state._st); state._st = setTimeout(() => state.syncing = false, 15e3); saveSoon();
    });
    sock.ev.on('messages.upsert', ({ messages, type }) => { for (const m of messages) { chanSeen(m.key?.remoteJid); if (type === 'notify' || type === 'append') { const jj = canon(m.key?.remoteJid); if (jj && !BAD_JID(jj)) setImmediate(() => emit('msg', { jid: jj, fromMe: !!m.key?.fromMe })) }
      const r = addMsg(m); if (!m.key?.fromMe && type === 'notify') console.log(new Date().toISOString(), 'IN', `type=${type}`, `addr=${String(m.key?.remoteJid || '').split('@')[1] || '?'}`, r ? 'new' : (txt(m) ? 'dup' : 'not-a-message:' + Object.keys(unwrap(m.message)).filter(k => k !== 'messageContextInfo').slice(0, 2).join('+')), `employee=${S().autoReply?.enabled ? 'on' : 'off'}`);
      if (r && type === 'notify' && r.msg.fromMe && state.me && phoneOf(r.c.jid) === state.me && !r.msg.auto) { console.log(new Date().toISOString(), 'IN own-number chat: employee does not answer yourself'); r.c.autoWhy = { t: Date.now(), why: SKIP_AR.own_number, code: 'own_number' }; emit('msg', { jid: r.c.jid, fromMe: true }) }
      if (r && type === 'notify') { r.msg.at = Date.now(); if (!r.msg.fromMe) { const rc = resolve(r.c); notify('msg', rc.label || rc.name || 'عميل', r.msg.text, rc.jid); onIncoming(rc, r.msg) } } } saveSoon() });
    sock.ev.on('lid-mapping.update', x => { for (const m of [].concat(x || [])) learnLid(m.lid, m.pn) });
    sock.ev.on('chats.upsert', cs => { (cs || []).forEach(c => { chanSeen(c.id, c.name); chatPn(c); chatMeta(c) }); saveSoon() }); sock.ev.on('chats.update', cs => { (cs || []).forEach(c => { chatPn(c); chatMeta(c) }); saveSoon() });
    sock.ev.on('contacts.upsert', cs => { cs.forEach(addContact); saveSoon() }); sock.ev.on('contacts.update', cs => { cs.forEach(addContact); saveSoon() });
  } catch (e) { console.log(new Date().toISOString(), 'WA start failed', e?.stack || e); state.status = 'reconnecting'; state.error = { code: null, text: diagnose(null, String(e?.message || e)), at: Date.now() }; scheduleReconnect(5000) }
  finally { connecting = false }
}
if (process.env.NO_WA === '1') state.status = 'connected'; else connect();

// newer Baileys builds keep their own LID store — use it when present (no network calls)
// pinned chats (WhatsApp sends `pinned` as a timestamp; 0/absent = not pinned) and newer conversation times
function pinOf(x, c) { if ('pinned' in (c || {})) { const p = tsMs(c.pinned); if (p) x.pinned = p; else delete x.pinned } }
function chatMeta(c) { const id = canon(c?.id); const x = id && store.chats[id]; if (!x) return; pinOf(x, c); const t = tsMs(c.conversationTimestamp); if (t > (x.t || 0)) x.t = t }
// history-sync chat records carry the phone in pnJid / phoneNumber, or the LID in lidJid
function chatPn(c) {
  const id = normJid(c?.id); if (!id) return; const pn = normJid(c.pnJid || c.phoneNumber), lid = normJid(c.lidJid || c.lid);
  if (isLid(id) && isPn(pn)) learnLid(id, pn); if (isPn(id) && isLid(lid)) learnLid(lid, id);
}
// Baileys v7 keeps a local LID↔phone store (signalRepository.lidMapping) — ask it in one batch, no network messages
let lidBusy = false;
async function tryLidRepo() {
  const lm = SOCK?.signalRepository?.lidMapping; if (!lm || lidBusy) return; lidBusy = true;
  try {
    const lids = [...new Set([...Object.keys(store.chats), ...Object.keys(store.contacts)].map(normJid).filter(j => isLid(j) && !store.lidMap[j]))];
    for (let i = 0; i < lids.length; i += 200) {
      const part = lids.slice(i, i + 200); let got = null;
      if (lm.getPNsForLIDs) try { got = await lm.getPNsForLIDs(part) } catch { }
      if (Array.isArray(got)) got.forEach(m => m && learnLid(m.lid, m.pn));
      else if (lm.getPNForLID) for (const j of part) { try { const pn = await lm.getPNForLID(j); if (pn) learnLid(j, pn) } catch { } }
    }
  } finally { lidBusy = false; lidLog('repo') }
}
const lidQ = new Set(); let lidT = null;
function lidAsk(j) { lidQ.add(normJid(j)); clearTimeout(lidT); lidT = setTimeout(() => { lidQ.clear(); tryLidRepo().then(saveSoon) }, 1500) }
function lidStats() {
  const all = Object.values(store.chats).filter(c => !c.isGroup); const lids = all.filter(c => isLid(c.jid));
  return { chats: all.length, withPhone: all.length - lids.length, unresolved: lids.length, known: Object.keys(store.lidMap).length };
}
let lidLast = '', lidLastT = 0;
function lidLog(why) { const x = lidStats(), k = `${x.withPhone}/${x.unresolved}/${x.known}`; if (why === 'repo' && k === lidLast && Date.now() - lidLastT < 600e3) return; lidLast = k; lidLastT = Date.now(); console.log(new Date().toISOString(), 'LID', why, `resolved=${x.withPhone} unresolved=${x.unresolved} map=${x.known}`) }
setInterval(() => { if (SOCK && state.status === 'connected' && lidStats().unresolved) tryLidRepo().then(saveSoon) }, 60e3).unref?.();
// ---------------- data views ----------------

const byLid = () => { if (Date.now() - byLidCache.t > 5000) { const m = {}; for (const c of Object.values(store.contacts)) if (c.lid) m[c.lid] = c; byLidCache = { t: Date.now(), m } } return byLidCache.m };
// short stable tag for a contact whose phone WhatsApp has not shared yet (last 4 digits of the LID)
const shortId = j => String(j || '').split('@')[0].replace(/\D/g, '').slice(-4) || '؟';
function resolve(c) {
  const bl = byLid()[c.jid]; const pn = isLid(c.jid) ? (store.lidMap[c.jid] || normJid(bl?.phoneNumber) || (isPn(normJid(bl?.jid)) ? normJid(bl.jid) : null) || null) : c.jid;
  const k = (pn && store.contacts[pn]) || store.contacts[c.jid] || byLid()[c.jid] || {};
  const phone = isPn(pn) ? phoneOf(pn) : '', disp = fmtPhone(phone);
  const cr = store.crm[c.jid]; const name = (cr?.profileEdit?.name || k.name || k.notify || k.verifiedName || c.name || cr?.profileAuto?.data?.name || '').trim();
  return { ...c, phone, disp, name, hidden: !phone, hid: phone ? '' : shortId(c.jid), label: name || disp || ('عميل #' + shortId(c.jid)) };
}
// startup: re-learn from saved contacts (older versions stored lid on the contact) and merge leftovers
setTimeout(() => { for (const c of Object.values(store.contacts)) { const pn = c.phoneNumber || c.jid || (isPn(c.id) ? c.id : null); if (c.lid && isPn(pn)) learnLid(c.lid, pn) }
  for (const [l, p] of Object.entries(store.lidMap)) if (store.chats[l]) { delete store.lidMap[l]; learnLid(l, p) }
  for (const c of Object.values(store.chats)) for (const m of c.messages || []) if (m.rjid && isPn(normJid(m.rjid)) && isLid(c.jid)) learnLid(c.jid, m.rjid);
  lidLog('startup'); saveSoon() }, 0);
const chatsList = () => Object.values(store.chats).filter(c => (c.messages.length || c.hist) && !c.isGroup && !BAD_JID(c.jid)).map(resolve);
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
    medianResponseMin: rts.length ? Math.round(rts[Math.floor(rts.length / 2)] / 60000) : null, waiting: cs.filter(c => chatState(c).state === 'wait').length,
    active7: cs.filter(c => now - lastOf(c).ts < 7 * day).length, revByDay, msgsByDay, tags, autoToday };
}
const hotLeads = () => chatsList().map(c => ({ jid: c.jid, name: c.name, phone: c.phone, score: scoreOf(c), reason: store.crm[c.jid]?.aiReason || '', last: lastOf(c) }))
  .filter(x => x.score >= S().hotScore).sort((a, b) => b.score - a.score).slice(0, 15);
const todayStr = () => new Intl.DateTimeFormat('en-CA', { timeZone: S().tz || 'Asia/Riyadh' }).format(new Date());
function reminders() {   // only real follow-ups: a date the owner/brain set, or a recent conversation that went quiet (not the whole history)
  const today = todayStr(), now = Date.now(), win = 14 * 864e5;
  return chatsList().map(c => {
    const cr = store.crm[c.jid] || {}, l = lastOf(c); if (cr.status === 'resolved' || !l.ts) return null; const age = now - l.ts;
    const fu = cr.profileEdit?.followUp || cr.followUp;
    if (fu && fu <= today && age < 60 * 864e5) return { jid: c.jid, name: c.label, why: fu < today ? `متابعة متأخرة ${Math.round((Date.parse(today) - Date.parse(fu)) / 864e5)} يوم` : 'موعد متابعة اليوم', kind: 'due', overdue: fu < today };
    if (!l.fromMe && age > Math.max(1, S().followUpDays) * 864e5 && age < win) return { jid: c.jid, name: c.label, why: `ينتظر ردك من ${Math.floor(age / 864e5)} يوم`, kind: 'unanswered' };
    if ((cr.tag === 'مهتم' || scoreOf(c) >= 35) && l.fromMe && age > 2 * 864e5 && age < win && !(cr.orders || []).length) return { jid: c.jid, name: c.label, why: `سكت بعد ردك من ${Math.floor(age / 864e5)} يوم`, kind: 'quiet' };
    return null;
  }).filter(Boolean);
}
function allOrders() {
  const out = []; for (const c of chatsList()) (store.crm[c.jid]?.orders || []).forEach((o, i) => out.push({ ...o, i, jid: c.jid, name: c.label }));
  return out.sort((a, b) => (a.deliveryDate || '9').localeCompare(b.deliveryDate || '9'));
}

// ---------------- app + security ----------------
const app = express(); app.disable('x-powered-by');
app.use((q, s, n) => { s.set({ 'X-Frame-Options': 'DENY', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'Cross-Origin-Opener-Policy': 'same-origin',
  'Content-Security-Policy': "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'" }); n() });
const r = express.Router(); const jsonS = express.json({ limit: '400kb' }), jsonL = express.json({ limit: '90mb' }); r.use((q, s, n) => (q.path === '/api/channels/publish' ? jsonL : jsonS)(q, s, n));
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
r.get('/internal/notify-events', (q, s) => {   // the desktop notifier (same PC, secret key from the launcher)
  const k = process.env.NOTIFY_KEY || ''; if (!k || q.get('x-notify-key') !== k) return s.status(403).end();
  s.set({ 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', Connection: 'keep-alive' }); s.flushHeaders?.(); s.write(': hi\n\n'); NOTS.add(s); q.on('close', () => NOTS.delete(s));
});
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
r.get('/api/events', (q, s) => {   // live UI updates (Server-Sent Events); the browser reconnects by itself
  s.set({ 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', Connection: 'keep-alive' }); s.flushHeaders?.(); s.write('retry: 1500\nevent: hello\ndata: {}\n\n'); UIS.add(s); q.on('close', () => UIS.delete(s));
});
setInterval(() => { for (const set of [UIS, NOTS]) for (const s of set) try { s.write(': ping\n\n') } catch { set.delete(s) } }, 20e3).unref?.();
r.post('/api/notify/test', (q, s) => { notify('msg', 'تجربة إشعار', 'كذا يوصلك الإشعار لما يكتب لك عميل', ''); s.json({ ok: true }) });
r.get('/api/state', (q, s) => {
  const cs = chatsList(), ar = S().autoReply;
  s.json({ status: state.status, qr: state.qr, me: state.me, error: state.error, attempts: state.attempts, waitingSec: Math.round((Date.now() - state.since) / 1000), syncing: state.syncing, lastSync: state.lastSync, version: VERSION, sim: FAKE,
    brain: brainOk || !!BRAIN_URL && S().aiEnabled, chats: cs.length, messages: cs.reduce((a, c) => a + c.messages.length, 0), analysis,
    unreadAlerts: store.alerts.filter(a => !a.read).length, now: hm(new Date(), S().tz), open: inWindow(S().hoursFrom, S().hoursTo, hm(new Date(), S().tz)),
    employee: { enabled: !!ar.enabled, active: !!ar.enabled && scheduleOpen(ar, S(), Date.now()), schedule: ar.schedule, mode: ar.mode, pending: pending.size, guard: (() => { const l = limits({ ...AUTO_DEFAULTS, ...ar }, store.wa.linkedAt), a = store.sends.filter(x => x.auto); return { ...l, hour: a.filter(x => Date.now() - x.t < 36e5).length, day: a.length } })() }, lid: lidStats(), ai: aiStat, version: VERSION, meDisp: fmtPhone(state.me || '') });
});
r.post('/api/analyze', async (q, s) => { analysis = await analyze(chatsList()); fs.writeFileSync(path.join(DIR, 'analysis.json'), JSON.stringify(analysis)); s.json(analysis) });
r.get('/report.html', (q, s) => analysis ? s.send(reportHTML(analysis, S())) : s.status(400).send('رتّب المحادثات أول'));
r.get('/contacts.csv', (q, s) => analysis ? s.type('text/csv').set('content-disposition', 'attachment; filename=contacts.csv').send('\ufeff' + csv(analysis)) : s.status(400).send('رتّب أول'));
r.get('/contacts.vcf', (q, s) => analysis ? s.type('text/vcard').set('content-disposition', 'attachment; filename=contacts.vcf').send(vcf(analysis)) : s.status(400).send('رتّب أول'));
// status badge for the list: ينتظر ردك / رديت / جديد / عنده طلب
function chatState(c) {
  const cr = store.crm[c.jid] || {}, l = lastOf(c), inc = c.messages.filter(m => !m.fromMe), now = Date.now();
  const openOrders = (cr.orders || []).filter(o => !['تم التوصيل', 'ملغي'].includes(o.status)).length;
  const waiting = !!l.ts && !l.fromMe && cr.status !== 'resolved' && now - l.ts < 30 * 864e5;   // older unanswered chats are history, not today's work
  const first = inc.length ? Math.min(...inc.map(m => m.ts)) : 0, isNew = inc.length > 0 && now - first < 3 * 864e5;
  return { state: waiting ? 'wait' : isNew ? 'new' : l.fromMe ? 'replied' : 'idle', waitMs: waiting ? now - l.ts : 0, isNew, openOrders };
}
r.get('/api/chats', (q, s) => s.json(chatsList().map(c => {
  const l = lastOf(c), cr = store.crm[c.jid] || {}, st = chatState(c);
  return { jid: c.jid, name: c.name, phone: c.phone, disp: c.disp, label: c.label, hidden: c.hidden, last: l.text || '', lastAt: Math.max(l.ts || 0, c.t || 0), pinned: c.pinned || 0, media: l.media?.type || '', fromMe: !!l.fromMe, auto: !!l.auto, n: c.messages.length,
    tag: cr.tag || 'جديد', status: cr.status || 'open', score: scoreOf(c), orders: (cr.orders || []).length, ...st };
}).sort((a, b) => (S().pinnedTop !== false ? (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0) || (b.pinned || 0) - (a.pinned || 0) : 0) || b.lastAt - a.lastAt)));
r.get('/api/media', async (q, s) => {
  try { const f = await mediaFile(q.query.id); if (!f) return s.status(404).json({ error: 'الملف ما عاد موجود على واتساب' });
    s.set('Cache-Control', 'private, max-age=31536000'); if (q.query.dl) s.set('Content-Disposition', `attachment; filename="${path.basename(f)}"`);
    s.sendFile(f) }
  catch (e) { s.status(502).json({ error: 'ما قدرنا نجيب الملف الحين، تأكد إن الجوال متصل وجرب مرة ثانية' }) }
});
r.get('/api/chat', async (q, s) => { const c = chatsList().find(x => x.jid === q.query.jid); if (!c) return s.json(null); const profile = q.query.profile ? await profileOf(c, false) : undefined;
  if (q.query.profile && aiOn() && !store.crm[c.jid]?.profileAuto?.ai) profileOf(c, true).catch(() => {}); /* AI upgrade in the background: opening a chat never waits for it */ s.json({ ...c, messages: [...c.messages].sort((a, b) => a.ts - b.ts).slice(-400), crm: store.crm[c.jid] || {}, pendingAuto: pending.has(c.jid), profile, ...chatState(c) }) });
r.post('/api/send', async (q, s) => {
  const { jid, text, confirm } = q.body || {};
  if (confirm !== true || !jid || !store.chats[jid] || typeof text !== 'string' || !text.trim() || text.length > 4000) return s.status(400).json({ error: 'طلب غير صالح' });
  if (!realSend || state.status !== 'connected') return s.status(503).json({ error: 'الواتساب غير متصل' });
  try {
    clearTimeout(pending.get(jid)); pending.delete(jid); clearTimeout(BATCH.get(jid)?.timer); BATCH.delete(jid);            // owner replied → cancel the employee's pending reply
    const ch0 = store.chats[jid]; const m = FAKE_FAST ? await realSend(jid, { text: text.trim() }) : await humanSend({ jid, text: text.trim(), send: realSend, presence: realPresence, read: realRead, readKey: lastIncomingKey(ch0), manual: true });
    sendLog(false); addMsg(m); const c = resolve(store.chats[jid]);
    audit('manual_send', { jid, to: c.label || c.name || 'عميل', len: text.length, preview: text.trim().slice(0, 80) }); saveSoon(); s.json({ ok: true });
  } catch (e) { audit('send_failed', { jid, err: String(e.message).slice(0, 80) }); s.status(500).json({ error: 'تعذّر الإرسال: ' + e.message }) }
});
r.get('/api/crm', (q, s) => s.json({ crm: store.crm, settings: S(), occasions: OCCASIONS }));
r.post('/api/crm', (q, s) => {
  const { jid, data } = q.body || {}; if (!jid || !data || typeof data !== 'object') return s.status(400).end();
  const allow = ['tag', 'note', 'followUp', 'orders', 'status', 'profileEdit'];
  const d = Object.fromEntries(Object.entries(data).filter(([k]) => allow.includes(k)));
  if (d.profileEdit !== undefined) { if (!d.profileEdit || typeof d.profileEdit !== 'object') return s.status(400).end();
    const PF = ['name', 'district', 'city', 'occasions', 'items', 'budget', 'value', 'sentiment', 'nextAction', 'followUp'];
    d.profileEdit = Object.fromEntries(Object.entries({ ...(store.crm[jid]?.profileEdit || {}), ...d.profileEdit }).filter(([k, v]) => PF.includes(k) && v !== null && v !== '').map(([k, v]) => [k, Array.isArray(v) ? v.map(x => String(x).slice(0, 40)).slice(0, 10) : typeof v === 'number' ? v : String(v).slice(0, 120)])) }
  if (d.orders && !Array.isArray(d.orders)) return s.status(400).end();
  store.crm[jid] = { ...store.crm[jid], ...d, updatedAt: Date.now() }; saveSoon(); s.json(store.crm[jid]);
});
r.get('/api/orders', (q, s) => s.json(allOrders()));
r.post('/api/orders/status', (q, s) => {
  const { jid, i, status } = q.body || {}; const o = store.crm[jid]?.orders?.[i];
  if (!o || !['جديد', 'قيد التجهيز', 'تم التوصيل', 'ملغي'].includes(status)) return s.status(400).json({ error: 'طلب غير صالح' });
  o.status = status; saveSoon(); audit('order_status', { jid, preview: o.item + ' ← ' + status }); s.json({ ok: true });
});
// «تعليم الموظف»: what the owner teaches the AI (also used by the rule brain: FAQ answers, handoff and forbidden words)
const L = (a, n, len) => (Array.isArray(a) ? a : []).map(x => String(x ?? '').trim().slice(0, len)).filter(Boolean).slice(0, n);
const QA = (a, n) => (Array.isArray(a) ? a : []).filter(x => x && String(x.q || '').trim() && String(x.a || '').trim()).slice(0, n).map(x => ({ q: String(x.q).trim().slice(0, 300), a: String(x.a).trim().slice(0, 500) }));
function cleanTeach(t) {
  return { persona: String(t.persona ?? '').slice(0, 300), tone: String(t.tone ?? '').slice(0, 300), dos: L(t.dos, 30, 200), donts: L(t.donts, 30, 200),
    faq: QA(t.faq, 60), examples: QA(t.examples, 40), forbidden: L(t.forbidden, 60, 60), handoff: L(t.handoff, 40, 80) };
}
let aiStat = { state: 'unknown' };
async function refreshAi() { const j = BRAIN_URL ? await brain('/ai/status', {}) : null; if (j) aiStat = { ...j, mode: S().aiModel || 'auto' } }
setInterval(refreshAi, 15e3).unref?.(); setTimeout(refreshAi, 1500);
r.get('/api/ai/status', async (q, s) => { await refreshAi(); s.json(aiStat) });
r.get('/api/teach', async (q, s) => { const d = BRAIN_URL ? await fetch(BRAIN_URL + '/teach_defaults', { method: 'POST', headers: { 'x-brain-key': BRAIN_KEY } }).then(x => x.json()).catch(() => null) : null; s.json({ current: S().teach || null, defaults: d }) });
r.post('/api/teach/try', async (q, s) => {   // «جرّب»: reply to a sample message with the (possibly unsaved) teaching — sends nothing
  const text = String(q.body?.text || '').slice(0, 500); if (!text.trim()) return s.status(400).json({ error: 'اكتب رسالة' });
  const teach = q.body?.teach && typeof q.body.teach === 'object' ? cleanTeach(q.body.teach) : S().teach;
  const j = await brain('/ai/try', { text, teach }, { ai: true }); if (!j) return s.status(503).json({ error: 'المساعد مو شغال الحين' }); s.json(j);
});
r.post('/api/settings', (q, s) => {
  const b = q.body || {}, cur = S(); const str = (k, n = 200) => { if (typeof b[k] === 'string') cur[k] = b[k].slice(0, n) };
  ['shopName', 'shopType', 'city', 'phone', 'aiTone', 'tz'].forEach(k => str(k, 80)); ['about', 'delivery'].forEach(k => str(k, 800));
  if (/^#[0-9a-fA-F]{6}$/.test(b.brand || '')) cur.brand = b.brand; if (['auto', 'light', 'dark'].includes(b.theme)) cur.theme = b.theme;
  if (typeof b.logo === 'string' && (b.logo === '' || /^data:image\/(png|jpeg|webp);base64,/.test(b.logo)) && b.logo.length < 300000) cur.logo = b.logo;
  for (const k of ['hoursFrom', 'hoursTo']) if (/^\d\d:\d\d$/.test(b[k] || '')) cur[k] = b[k];
  for (const [k, lo, hi] of [['followUpDays', 0, 60], ['dormantDays', 3, 365], ['hotScore', 10, 100], ['sessionMinutes', 5, 720]]) if (b[k] !== '' && b[k] != null && Number.isFinite(+b[k])) cur[k] = Math.min(hi, Math.max(lo, +b[k]));
  for (const k of ['notifyHot', 'notifyNew', 'aiEnabled', 'tourDone', 'pinnedTop']) if (typeof b[k] === 'boolean') cur[k] = b[k];
  if (b.notify && typeof b.notify === 'object') { const n = { ...NOTIFY_DEFAULTS, ...(cur.notify || {}) };
    for (const k of ['on', 'msg', 'order', 'alert', 'sound', 'quiet']) if (typeof b.notify[k] === 'boolean') n[k] = b.notify[k];
    if (Number.isFinite(+b.notify.volume)) n.volume = Math.max(0, Math.min(100, Math.round(+b.notify.volume)));
    for (const k of ['quietFrom', 'quietTo']) if (/^\d\d:\d\d$/.test(b.notify[k] || '')) n[k] = b.notify[k];
    cur.notify = n }
  if (Array.isArray(b.hintsOff)) cur.hintsOff = b.hintsOff.filter(x => typeof x === 'string').slice(0, 30);
  if (Array.isArray(b.templates)) cur.templates = b.templates.filter(x => x && typeof x.t === 'string' && x.t.trim()).slice(0, 40).map(x => ({ k: String(x.k || 'رد').slice(0, 30), t: x.t.slice(0, 1000) }));
  if (Array.isArray(b.tags)) cur.tags = [...new Set(b.tags.filter(x => typeof x === 'string' && x.trim()).map(x => x.trim().slice(0, 20)))].slice(0, 15);
  if (Array.isArray(b.products)) cur.products = b.products.filter(p => p && typeof p.name === 'string' && p.name.trim()).slice(0, 200)
    .map(p => ({ name: p.name.trim().slice(0, 60), price: Math.max(0, +p.price || 0), unit: String(p.unit || 'بوكيه').slice(0, 20), category: String(p.category || 'بوكيه').slice(0, 20), aliases: (Array.isArray(p.aliases) ? p.aliases : String(p.aliases || '').split(/[،,]/)).map(a => String(a).trim()).filter(Boolean).slice(0, 10) }));
  if (['auto', 'off'].includes(b.aiModel)) cur.aiModel = b.aiModel;
  if (b.teach && typeof b.teach === 'object') cur.teach = cleanTeach(b.teach);
  if (b.autoReply && typeof b.autoReply === 'object') {
    const a = b.autoReply, ar = cur.autoReply, was = ar.enabled;
    if (typeof a.enabled === 'boolean') ar.enabled = a.enabled;
    if (['always', 'offhours', 'custom'].includes(a.schedule)) ar.schedule = a.schedule;
    for (const k of ['from', 'to']) if (/^\d\d:\d\d$/.test(a[k] || '')) ar[k] = a[k];
    if (['smart', 'fixed'].includes(a.mode)) ar.mode = a.mode;
    if (typeof a.handoff === 'boolean') ar.handoff = a.handoff; if (typeof a.humanTyping === 'boolean') ar.humanTyping = a.humanTyping;
    for (const k of ['message', 'handoffMessage']) if (typeof a[k] === 'string' && a[k].trim()) ar[k] = a[k].trim().slice(0, 600);
    for (const [k, lo, hi] of [['delaySec', 0, 600], ['cooldownMin', 0, 1440], ['maxPerDay', 1, 200], ['ownerActiveMin', 0, 240], ['maxPerHour', 1, 200], ['maxTotalPerDay', 1, 1000]]) if (a[k] !== '' && a[k] != null && Number.isFinite(+a[k])) ar[k] = Math.min(hi, Math.max(lo, +a[k]));
    if (was !== ar.enabled) { audit(ar.enabled ? 'auto_reply_enabled' : 'auto_reply_disabled', { preview: { always: 'يرد دايم', offhours: 'يرد خارج الدوام', custom: `يرد من ${ar.from} إلى ${ar.to}` }[ar.schedule] }); if (!ar.enabled) { for (const t of pending.values()) clearTimeout(t); pending.clear() } }
  }
  saveSoon(); if (!b.tourDone && !b.hintsOff) audit('settings_changed', {}); s.json(cur);
});
r.get('/api/employee/check', async (q, s) => {   // «فحص الموظف»: every gate, in plain Saudi Arabic, plus the last decisions
  const ar = { ...AUTO_DEFAULTS, ...S().autoReply }, now = Date.now(), lim = limits(ar, store.wa.linkedAt), auto = store.sends.filter(x => x.auto);
  const h = auto.filter(x => now - x.t < 36e5).length, dd = auto.filter(x => now - x.t < 864e5).length;
  const lastIn = Object.values(store.chats).flatMap(c => c.messages.filter(m => !m.fromMe && m.at)).sort((a, b) => b.at - a.at)[0];
  const skew = lastIn ? Math.round((lastIn.at - lastIn.ts) / 60e3) : null; const b0 = BRAIN_URL ? await brain('/think', { text: 'السلام عليكم' }, { ai: false }) : null;
  const checks = [
    ['on', ar.enabled, ar.enabled ? 'الموظف شغّال' : 'الموظف مطفي — شغّله من فوق'],
    ['wa', state.status === 'connected' && !!realSend, state.status === 'connected' ? 'الواتساب متصل' : 'الواتساب مو متصل'],
    ['time', scheduleOpen(ar, S(), now), scheduleOpen(ar, S(), now) ? 'الحين داخل وقت عمل الموظف' : `الحين خارج وقت عمل الموظف (${ar.schedule === 'offhours' ? 'يرد بس برا ساعات الدوام' : ar.from + '–' + ar.to}). خله «دايم» إذا تبيه يرد كل الوقت`],
    ['brain', !!b0, b0 ? 'الردود الذكية جاهزة' : 'الردود الذكية مو جاهزة، بيرد بالرسالة الثابتة'],
    ['hour', h < lim.perHour, `ردود هالساعة ${h} من ${lim.perHour}`],
    ['day', dd < lim.perDay, `ردود اليوم ${dd} من ${lim.perDay}${lim.warm ? ' (رقم جديد، الحد يزيد مع الأيام)' : ''}`],
    ['queue', true, `رسائل ينتظر يرد عليها الحين: ${BATCH.size + pending.size} (يستنى العميل يخلص كلامه، ويهدّي بين الردود بدل ما يتركها)`],
    ['clock', skew == null || Math.abs(skew) < 5, skew == null ? 'ما وصلت رسالة من عميل من فتحت البرنامج' : Math.abs(skew) < 5 ? 'ساعة الجهاز مضبوطة' : `ساعة الجهاز مختلفة ${Math.abs(skew)} دقيقة عن واتساب — الموظف يتحمّلها، بس اضبط الساعة`],
  ];
  const recent = store.audit.filter(a => /^auto_/.test(a.type)).slice(0, 12).map(a => ({ t: a.t, type: a.type, to: a.to, why: a.why || a.err || a.preview || '' }));
  s.json({ ok: checks.slice(0, 4).every(c => c[1]), checks: checks.map(([id, ok, text]) => ({ id, ok, text })), pending: pending.size, recent });
});
r.post('/api/employee/test', async (q, s) => {   // dry run: what would the employee answer? (sends nothing)
  const text = String(q.body?.text || '').slice(0, 500); if (!text.trim()) return s.status(400).json({ error: 'اكتب رسالة' });
  const b = await brain('/think', { text, after_hours: !inWindow(S().hoursFrom, S().hoursTo, hm(new Date(), S().tz)) && !(Date.now() - (store.autoHist[jid]?.afterHoursAt || 0) < 14 * 3600e3) }, { ai: false });
  const fakeChat = { jid: 'test@s.whatsapp.net', messages: [] }; const msg = { fromMe: false, text, ts: Date.now() };
  const d = decide(fakeChat, msg, { settings: { ...S(), autoReply: { ...S().autoReply, enabled: true, schedule: 'always' } }, connected: true, history: {}, brain: b });
  s.json({ ...d, brain: !!b, intents: b?.intents || [] });
});
r.get('/api/audit', (q, s) => s.json(store.audit.slice(0, 400)));
r.get('/api/alerts', (q, s) => s.json(store.alerts.slice(0, 60)));
r.post('/api/alerts/read', (q, s) => { store.alerts.forEach(a => a.read = true); saveSoon(); s.json({ ok: true }) });
r.get('/api/dashboard', (q, s) => s.json({ analytics: analytics(), hot: hotLeads(), reminders: reminders(), briefing: store.ai.briefing || null, orders: allOrders().filter(o => !['تم التوصيل', 'ملغي'].includes(o.status)).slice(0, 8) }));
r.post('/api/wa/retry', (q, s) => { state.since = Date.now(); state.attempts = 0; state.error = null; failsNoQr = 0; scheduleReconnect(100); audit('wa_retry', {}); s.json({ ok: true }) });
r.post('/api/wa/reset', (q, s) => {   // clear a stale/corrupt link session (keeps chats, customers and settings)
  const old = SOCK; SOCK = null; try { old?.end?.(undefined) } catch { } fs.rmSync(path.join(DIR, 'auth'), { recursive: true, force: true });
  state = { ...state, status: 'starting', qr: null, me: null, error: null, attempts: 0, since: Date.now() }; profileIdx = 0; failsNoQr = 0; scheduleReconnect(300); audit('wa_reset', {}); s.json({ ok: true });
});
// Disconnect WhatsApp (unlink this computer). keep=true keeps chats/customers/orders on this PC; wipe=true deletes them (settings stay).
r.post('/api/logout', async (q, s) => {
  const wipe = q.body?.wipe === true; for (const t of pending.values()) clearTimeout(t); pending.clear();
  const old = SOCK; SOCK = null; try { await old?.logout?.() } catch { } try { old?.end?.(undefined) } catch { }
  fs.rmSync(path.join(DIR, 'auth'), { recursive: true, force: true }); store.wa = {};
  if (wipe) { Object.assign(store, { chats: {}, contacts: {}, crm: {}, alerts: [], autoHist: {}, lidMap: {}, plan: {}, sends: [] }); analysis = null; try { fs.rmSync(path.join(DIR, 'analysis.json'), { force: true }) } catch { } }
  audit('whatsapp_unlinked', { preview: wipe ? 'مع مسح البيانات' : 'مع الاحتفاظ بالبيانات' }); save();
  state = { ...state, status: 'loggedOut', qr: null, me: null, error: null, attempts: 0, since: Date.now() }; s.json({ ok: true, wiped: wipe });
  scheduleReconnect(1500);   // ready with a fresh QR whenever the owner wants to link again
});
// ---- brain endpoints (suggestions only — they never send)
const getChat = jid => chatsList().find(x => x.jid === jid);
r.get('/api/brain/products', async (q, s) => { const d = BRAIN_URL ? await fetch(BRAIN_URL + '/kb', { method: 'POST', headers: { 'x-brain-key': BRAIN_KEY } }).then(x => x.json()).catch(() => null) : null; s.json({ current: S().products, defaults: d?.products || [] }) });
r.post('/api/ai/suggest', async (q, s) => { const c = getChat(q.body?.jid); if (!c) return s.status(404).json({ error: 'المحادثة غير موجودة' }); const j = await brain('/suggest', { messages: msgsFor(c), customer: c.name }, { ai: true }); if (!j) return s.status(503).json({ error: 'brain_off' }); s.json(j) });
r.post('/api/ai/extract', async (q, s) => {
  const c = getChat(q.body?.jid); if (!c) return s.status(404).json({ error: 'المحادثة غير موجودة' });
  const j = await brain('/extract', { messages: msgsFor(c, 80), customer: c.name }, { ai: true }); if (!j) return s.status(503).json({ error: 'brain_off' });
  store.crm[c.jid] = { ...store.crm[c.jid], aiScore: j.score, aiReason: j.reason, aiSummary: j.summary }; saveSoon(); s.json(j);
});
r.post('/api/ai/score-all', async (q, s) => {
  const cs = chatsList().sort((a, b) => lastOf(b).ts - lastOf(a).ts).slice(0, 150); let done = 0;
  for (const c of cs) { const j = await brain('/extract', { messages: msgsFor(c, 30), customer: c.name }); if (!j) break; store.crm[c.jid] = { ...store.crm[c.jid], aiScore: j.score, aiReason: j.reason, aiStage: j.stage, aiSummary: j.summary }; done++ }
  saveSoon(); if (!done && cs.length) return s.status(503).json({ error: 'brain_off' }); s.json({ scored: done });
});
// ---- smart daily plan (local brain, no typing): prioritized actions with why + value, progress, end-of-day summary
function greeting() { const h = +hm(new Date(), S().tz).slice(0, 2); return h < 4 ? 'مساء الخير' : h < 12 ? 'صباح الخير' : h < 18 ? 'مساء الخير' : 'مساء النور' }
const PWHY = { price: 'سأل عن السعر', order: 'يبي يطلب', complaint: 'عنده شكوى', human: 'يبي يكلمك', delivery: 'يسأل عن التوصيل', catalog: 'يبي يشوف الخيارات', care: 'يسأل عن العناية', greeting: 'سلّم وينتظر', thanks: 'شكرك' };
const ago = ms => { const m = Math.round(ms / 60000); return m < 60 ? `${m.toLocaleString('ar-SA')} د` : m < 1440 ? `${Math.round(m / 60).toLocaleString('ar-SA')} س` : `${Math.round(m / 1440).toLocaleString('ar-SA')} يوم` };
let introBusy = false;
async function buildPlan() {
  const now = Date.now(), today = todayStr(), P = store.plan[today] ??= { done: [], seen: [] }, items = [];
  for (const k of Object.keys(store.plan)) if (k < new Date(now - 7 * 864e5).toISOString().slice(0, 10)) delete store.plan[k];
  const cs = chatsList(), a = analytics(), avg = a.avgOrder || 0;
  // 1) customers waiting for a reply (last 7 days)
  const waiting = cs.map(c => ({ c, st: chatState(c) })).filter(x => x.st.state === 'wait' && x.st.waitMs < 7 * 864e5).sort((x, y) => scoreOf(y.c) - scoreOf(x.c) || y.st.waitMs - x.st.waitMs).slice(0, 25);
  for (const { c, st } of waiting) {
    const ins = await brain('/insight', { messages: msgsFor(c, 8) }) || {}; const its = ins.intents || [];
    const top = ['complaint', 'order', 'price', 'human', 'delivery', 'catalog', 'care'].find(i => its.includes(i)) || its[0];
    const hot = scoreOf(c) >= S().hotScore;
    const why = [hot ? 'عميل ساخن' : '', PWHY[top] || 'كتب لك', ins.items?.[0] ? `(${ins.items[0]})` : '', `وينتظر من ${ago(st.waitMs)}`].filter(Boolean).join(' ');
    const pr = 40 + Math.min(30, st.waitMs / 36e5 * 3) + scoreOf(c) / 2 + (top === 'complaint' ? 25 : top === 'order' ? 20 : top === 'price' ? 15 : 0);
    items.push({ id: 'r:' + c.jid, type: 'reply', jid: c.jid, label: c.label, disp: c.disp, title: `رد على ${c.label}`, why, value: ins.value || 0, priority: Math.round(pr), suggest: true });
  }
  // 2) follow-ups (overdue first) — capped, the real total is reported separately
  const rm = reminders().filter(r => r.kind !== 'unanswered' || !waiting.some(w => w.c.jid === r.jid));
  for (const r of rm.filter(r => r.kind !== 'unanswered')) { const c = cs.find(x => x.jid === r.jid);
    items.push({ id: 'f:' + r.jid, type: 'follow', jid: r.jid, label: r.name, disp: c?.disp, title: `تابع ${r.name}`, why: r.why, value: store.crm[r.jid]?.profileAuto?.data?.potential || 0, priority: r.overdue ? 55 : 45, suggest: true }) }
  // 3) orders to prepare today/tomorrow
  const tmr = new Date(Date.parse(today) + 864e5).toISOString().slice(0, 10);
  for (const o of allOrders().filter(o => !['تم التوصيل', 'ملغي'].includes(o.status) && o.deliveryDate && o.deliveryDate <= tmr))
    items.push({ id: `o:${o.jid}:${o.i}`, type: 'order', jid: o.jid, label: o.name, title: `جهّز طلب ${o.item}`, why: o.deliveryDate < today ? 'موعد التوصيل فات!' : o.deliveryDate === today ? 'التوصيل اليوم' : 'التوصيل بكرة', value: +o.amount || 0, priority: o.deliveryDate <= today ? 90 : 60 });
  // 4) re-engage past buyers who went quiet
  const D = S().dormantDays * 864e5;
  cs.filter(c => (store.crm[c.jid]?.orders || []).some(o => o.status !== 'ملغي') && now - (lastOf(c).ts || c.t || now) > D).slice(0, 3).forEach(c => items.push({ id: 're:' + c.jid, type: 'reengage', jid: c.jid, label: c.label, disp: c.disp, title: `ذكّر ${c.label} فينا`, why: `اشترى قبل وغايب من ${ago(now - (lastOf(c).ts || c.t))}`, value: avg, priority: 30, suggest: true }));
  // 5) occasions & weekend opportunities
  const occ = (await brain('/occasions', { days: 21 }))?.list || [];
  for (const o of occ.slice(0, 2)) items.push({ id: 'occ:' + o.occasion, type: 'occasion', title: `${o.occasion} بعد ${o.days ? o.days.toLocaleString('ar-SA') + ' يوم' : 'اليوم'}`, why: 'جهّز عرض وأرسله لعملائك اللي اشتروا قبل', value: 0, priority: 35 - o.days });
  const wd = new Intl.DateTimeFormat('en-US', { timeZone: S().tz, weekday: 'short' }).format(new Date());
  if (['Wed', 'Thu'].includes(wd)) items.push({ id: 'wk:' + today, type: 'occasion', title: 'الويكند جاي', why: 'الخميس والجمعة أعلى طلب على الورد — جهّز بوكيهات جاهزة وعرض بسيط', value: 0, priority: 25 });
  // progress: items seen today that are no longer pending count as done (e.g. you replied), plus ones you ticked
  const ids = new Set(items.map(x => x.id)); for (const x of items) if (!P.seen.includes(x.id)) P.seen.push(x.id);
  const done = new Set([...P.done, ...P.seen.filter(id => !ids.has(id))]);
  const open = items.filter(x => !done.has(x.id)).sort((x, y) => y.priority - x.priority);
  // end-of-day summary (zeros hidden)
  const t0 = Date.parse(today + 'T00:00:00+03:00'), au = store.audit.filter(x => x.t >= t0);
  const sent = au.filter(x => x.type === 'manual_send').length, auto = au.filter(x => x.type === 'auto_reply' || x.type === 'auto_handoff').length;
  const newC = cs.filter(c => { const inc = c.messages.filter(m => !m.fromMe); return inc.length && Math.min(...inc.map(m => m.ts)) >= t0 }).length;
  const ordT = allOrders().filter(o => o.date && Date.parse(o.date) >= t0), ordV = ordT.reduce((x, o) => x + (+o.amount || 0), 0);
  const N = x => x.toLocaleString('ar-SA'), summary = [sent && `رديت على ${N(sent)} رسالة`, auto && `الموظف رد ${N(auto)} مرة`, newC && `${N(newC)} عميل جديد`, ordT.length && `${N(ordT.length)} طلب${ordV ? ` بقيمة ${N(ordV)} ر.س` : ''}`].filter(Boolean);
  const sig = open.slice(0, 6).map(i => i.id).join('|');
  if (P.introSig !== sig && !introBusy) { introBusy = true; brain('/plan_text', { items: open.slice(0, 6).map(i => `${i.title} — ${i.why}`) }, { ai: true })
    .then(j => { if (j?.text) { P.intro = j.text; P.introAi = j.engine === 'ai'; P.introSig = sig; saveSoon() } }).finally(() => introBusy = false) }
  saveSoon();
  return { greeting: greeting(), intro: P.intro || '', introAi: !!P.introAi, items: open.slice(0, 12), more: Math.max(0, open.length - 12), progress: { done: done.size, total: done.size + open.length },
    counts: { waiting: waiting.length, followups: rm.length, overdue: rm.filter(r => r.overdue).length }, summary, value: open.reduce((x, i) => x + (i.value || 0), 0), t: now };
}
// background: fill auto profiles (gives unnamed customers a name from «معك سارة», plus district/occasion…) without the owner typing
let profBusy = false;
setInterval(async () => { if (profBusy || !BRAIN_URL) return; profBusy = true;
  try { for (const c of chatsList().filter(c => c.messages.some(m => !m.fromMe) && store.crm[c.jid]?.profileAuto?.n !== c.messages.length + ':' + (store.crm[c.jid]?.orders || []).length).slice(0, 12)) await profileOf(c) } catch { } profBusy = false }, 8000).unref?.();
r.get('/api/plan', async (q, s) => s.json(await buildPlan()));
r.post('/api/plan/done', (q, s) => { const id = String(q.body?.id || '').slice(0, 200); if (!id) return s.status(400).end(); const P = store.plan[todayStr()] ??= { done: [], seen: [] }; if (!P.done.includes(id)) P.done.push(id); saveSoon(); s.json({ ok: true }) });
r.post('/api/ai/briefing', async (q, s) => { const p = await buildPlan(); const text = p.items.slice(0, 6).map(i => `• ${i.title} — ${i.why}`).join('\n') || '• ما فيه شي مستعجل 👌'; store.ai.briefing = { t: Date.now(), text }; saveSoon(); s.json(store.ai.briefing) });
// ---- auto customer profile (brain) — cached per message count; the owner's edits win
async function profileOf(c, deep = false) {
  const cr = store.crm[c.jid] ??= {}; const n = c.messages.length + ':' + (cr.orders || []).length;
  const want = deep && aiOn() && !cr.profileAuto?.ai;   // opening a chat may upgrade the rule profile with the local AI (once per new message)
  if (cr.profileAuto?.n !== n || want) { const d = await brain('/profile', { messages: msgsFor(c, 300), orders: cr.orders || [], deep }, { ai: deep }); if (d) { cr.profileAuto = { n, data: d, t: Date.now(), ai: !!(deep && aiOn()) }; saveSoon() } }
  return { ...(cr.profileAuto?.data || {}), ...(cr.profileEdit || {}), edited: Object.keys(cr.profileEdit || {}) };
}
// ---- Marketing v2.3: a short ranked list of ready actions. Drafts only — the owner opens each chat and presses send himself (no bulk sending).
// Practices: follow up unanswered inquiries fast; win back buyers silent 30–90 days; pre-order notice before Saudi peak dates; yearly repeat of last year's
// occasion; thank-you + review/referral after delivery; one WhatsApp Status a day. Daily cap keeps it human (anti-ban).
const MKT_DAILY = 20;
async function mktActions() {
  const now = Date.now(), day = 864e5, cs = chatsList(), crmOf = j => store.crm[j] || {}, acts = [];
  const lastIn = c => c.messages.filter(m => !m.fromMe).reduce((a, m) => Math.max(a, m.ts), 0), lastOut = c => c.messages.filter(m => m.fromMe).reduce((a, m) => Math.max(a, m.ts), 0);
  const who = c => ({ jid: c.jid, label: c.label, disp: c.disp, name: c.name, first: (c.name || '').split(/\s+/)[0] || '' });
  const ok = c => /^\d{8,15}$/.test(c.phone || '') || isLid(c.jid);
  // 1) inquiries that went cold: asked about price/order 1–7 days ago, no order recorded, nothing from us in the last 24h
  const cold = cs.filter(c => { const li = lastIn(c), lo = lastOut(c); const hot1 = new RegExp(HOT.source), asked = c.messages.some(m => !m.fromMe && hot1.test(m.text || ''));
    return ok(c) && asked && !(crmOf(c.jid).orders || []).length && li > now - 7 * day && li < now - day && lo < now - day }).slice(0, MKT_DAILY);
  if (cold.length) acts.push({ id: 'cold', icon: 'i-chat', title: 'عملاء سألوا وما كملوا', why: `${cold.length.toLocaleString('ar-SA')} عميل سأل عن سعر أو طلب خلال الأسبوع وما رجع. أسرع رسالة ترجعهم.`, score: 95 + cold.length,
    goal: 'متابعة لطيفة لعميل سأل عن الورد وما كمل الطلب، نسأله إذا يحتاج مساعدة يختار', template: 'هلا {الاسم} 🌷 شفت إنك سألت عن الورد قبل كم يوم، لقيت اللي يناسبك؟ إذا تحب أرسل لك صور خيارات قريبة من ميزانيتك.', people: cold.map(who) });
  // 2) yearly repeat: an order for an occasion ~1 year ago (next 3 weeks)
  const rep = []; for (const c of cs) for (const o of crmOf(c.jid).orders || []) { const d = Date.parse(o.deliveryDate || '') || o.date || 0; const ahead = d + 365 * day - now; if (o.status !== 'ملغي' && ahead > 0 && ahead < 21 * day) { rep.push({ ...who(c), item: o.item, occasion: o.occasion || '' }); break } }
  if (rep.length) acts.push({ id: 'repeat', icon: 'i-spark', title: 'مناسبات السنة الماضية', why: `${rep.length.toLocaleString('ar-SA')} عميل طلب منك هالوقت السنة الماضية. ذكّره قبل لا يطلب من غيرك.`, score: 90 + rep.length,
    goal: 'تذكير لطيف لعميل طلب ورد بنفس الوقت السنة الماضية لمناسبة، نعرض نجهز له مثلها', template: 'هلا {الاسم} 🌸 السنة الماضية بهالوقت جهزنا لك ورد لمناسبتك، تبينا نجهز لك شي مثله أو أحلى هالسنة؟', people: rep.slice(0, MKT_DAILY) });
  // 3) the next Saudi peak date (pre-order notice 1–4 weeks before) → past buyers first
  const occ = ((await brain('/occasions', { days: 30 }))?.list || []).filter(o => o.days >= 3)[0];
  const buyers = cs.filter(c => ok(c) && (crmOf(c.jid).orders || []).some(o => o.status !== 'ملغي'));
  if (occ) acts.push({ id: 'occ', icon: 'i-bell', title: `${occ.occasion} بعد ${occ.days.toLocaleString('ar-SA')} يوم`, why: `افتح الحجز المبكر لعملائك اللي اشتروا قبل (${buyers.length.toLocaleString('ar-SA')}) قبل زحمة آخر يومين، واحجز الورد من المورد بدري.`, score: 80 - occ.days,
    goal: `إعلان حجز مبكر لـ ${occ.occasion} لعميل اشترى قبل، بأولوية في الحجز`, template: `هلا {الاسم} 🌷 ${occ.occasion} قرب، وفتحنا الحجز المبكر لعملائنا قبل الزحمة. تحب أرسل لك الخيارات وتحجز موعدك؟`, people: buyers.slice(0, MKT_DAILY).map(who) });
  // 4) win-back: bought before, silent 30–90 days
  const wb = cs.filter(c => { const l = lastOf(c).ts || c.t || 0; return ok(c) && (crmOf(c.jid).orders || []).some(o => o.status !== 'ملغي') && l < now - 30 * day && l > now - 90 * day });
  if (wb.length) acts.push({ id: 'winback', icon: 'i-user', title: 'رجّع عملاءك الغايبين', why: `${wb.length.toLocaleString('ar-SA')} عميل اشترى قبل وغاب من شهر لثلاث شهور. رسالة شخصية ترجّع أغلبهم.`, score: 70 + Math.min(20, wb.length),
    goal: 'رسالة اشتياق لعميل اشترى قبل وغاب، نخبره بتشكيلة جديدة بدون إلحاح', template: 'هلا {الاسم} 🌷 اشتقنا لك! نزلت عندنا تشكيلة جديدة حلوة، تحب أرسل لك صورها؟', people: wb.slice(0, MKT_DAILY).map(who) });
  // 5) thank-you + review / referral after a delivery (last 3 days)
  const ty = cs.filter(c => ok(c) && (crmOf(c.jid).orders || []).some(o => o.status === 'تم التوصيل' && (Date.parse(o.deliveryDate || '') || o.date || 0) > now - 3 * day));
  if (ty.length) acts.push({ id: 'thanks', icon: 'i-check', title: 'اشكر واطلب رأيهم', why: 'بعد التوصيل بيوم: اشكره، واسأله إذا يبي نذكّره بالمناسبة السنة الجاية، واطلب منه يرشحنا لأحد.', score: 60 + ty.length,
    goal: 'شكر العميل بعد توصيل الورد، وسؤاله إذا يبي تذكير بالمناسبة السنة الجاية، وترشيح المحل لأحبابه', template: 'هلا {الاسم} 🌷 إن شاء الله الورد وصل وعجبهم! تحب نذكّرك بالمناسبة السنة الجاية؟ وإذا عجبك شغلنا رشحنا لأحبابك 🤍', people: ty.slice(0, MKT_DAILY).map(who) });
  // 6) one WhatsApp Status for today (no recipients — he posts it himself)
  const wd = new Intl.DateTimeFormat('en-US', { timeZone: S().tz, weekday: 'short' }).format(new Date());
  const st = occ ? `تنسيق ${occ.occasion} جاهز للحجز المبكر 🌷 الكمية محدودة، احجز من الحين` : ['Wed', 'Thu'].includes(wd) ? 'الويكند جاي 🌷 بوكيهات جاهزة اليوم، اطلب قبل المغرب ونوصلها لك' : 'ورد اليوم وصل طازج 🌷 صوّره وانشره، واكتب: اطلب الحين ونوصله لك اليوم';
  acts.push({ id: 'status', icon: 'i-spark', title: 'حالة واتساب اليوم', why: 'صورة وحدة حلوة من ورد اليوم مع جملة قصيرة. الحالة يشوفها عملاؤك بدون ما ترسل لأحد.', score: 40, status: true,
    goal: 'نص قصير لحالة واتساب لمحل ورد يشجع على الطلب اليوم', template: st, people: [] });
  return acts.sort((a, b) => b.score - a.score).slice(0, 5);
}
r.get('/api/mkt/actions', async (q, s) => { const today = todayStr(), sent = (store.mkt ??= {})[today] || []; s.json({ actions: await mktActions(), cap: MKT_DAILY, opened: sent.length }) });
r.post('/api/mkt/draft', async (q, s) => { const b = q.body || {}; const j = await brain('/mkt_draft', { goal: String(b.goal || '').slice(0, 200), template: String(b.template || '').slice(0, 500) }, { ai: true }); if (!j) console.log(new Date().toISOString(), 'LLM mkt_draft: brain did not answer'); else if (j.engine !== 'ai') console.log(new Date().toISOString(), 'LLM mkt_draft fallback:', j.reason || ''); s.json(j || { text: b.template, engine: 'rules', reason: 'البرنامج ما رد، جرّب مرة ثانية' }); return; s.json(j || { text: b.template, engine: 'rules' }) });
r.post('/api/mkt/opened', (q, s) => { const today = todayStr(), m = store.mkt ??= {}; for (const k of Object.keys(m)) if (k < today) delete m[k]; const l = m[today] ??= []; const j = String(q.body?.jid || ''); if (j && !l.includes(j)) l.push(j); saveSoon(); s.json({ opened: l.length, cap: MKT_DAILY }) });
r.post('/api/ai/campaign', (q, s) => s.json(campaign(q.body || {}, S())));
r.post('/api/ai/reengage', (q, s) => {
  const now = Date.now(), D = S().dormantDays * 864e5;
  const list = chatsList().filter(c => now - lastOf(c).ts > D).map(c => ({ jid: c.jid, name: c.label, phone: c.phone, days: Math.floor((now - lastOf(c).ts) / 864e5), bought: (store.crm[c.jid]?.orders || []).length > 0 }))
    .sort((a, b) => b.bought - a.bought || a.days - b.days).slice(0, 40);
  s.json({ list, message: `هلا {الاسم}، اشتقنا لك في ${S().shopName} 🌷 نزلت عندنا تشكيلة جديدة، تحب أرسل لك صورها؟` });
});
// ---- simulator (FAKE_WA=1 only): lets tests and design QA drive a full flow without a phone
if (FAKE) {
  r.post('/api/sim/link', (q, s) => { fake?.link(q.body?.me || '966500000000', q.body?.history); s.json({ ok: true }) });
  r.post('/api/sim/incoming', (q, s) => { const { jid, text, name, ts, senderPn, key } = q.body || {}; s.json({ id: fake?.incoming(jid, text, name, ts, senderPn, key) }) });
  r.post('/api/sim/media', (q, s) => { const { jid, kind, body, name } = q.body || {}; if (!/^(image|video|audio|sticker|document)$/.test(kind || '')) return s.status(400).end(); s.json({ id: fake?.incomingMedia(jid, kind, body, name) }) });
  r.post('/api/sim/ev', (q, s) => { const { event, data } = q.body || {}; if (!/^(contacts|chats|lid-mapping)\./.test(event || '')) return s.status(400).end(); fake?.emit(event, data); s.json({ ok: true }) });
  r.post('/api/sim/lidrepo', async (q, s) => { const { lid, pn } = q.body || {}; fake?.signalRepository.lidMapping.set(lid, pn); await tryLidRepo(); s.json(lidStats()) });
  r.post('/api/sim/channel', (q, s) => { fake?.addChannel(q.body || {}); if (q.body?.seen) chanSeen(q.body.id, q.body.name); s.json({ ok: true }) });
  r.post('/api/sim/leak', (q, s) => { console.info('Closing session:', { _chains: {}, privKey: Buffer.from('AAAA'), rootKey: Buffer.from('BBBB') }); console.log({ indexInfo: { baseKey: Buffer.from('CC') } }); console.log('SAFE-MARKER'); s.json({ ok: true }) });
  r.get('/api/sim/outbox', (q, s) => s.json(fake?.outbox || []));
}
r.use(express.static(path.join(HERE, 'public'), { index: 'index.html' }));
app.get('/', (q, s) => s.status(404).send('Not found'));

// ---------------- WhatsApp Channel (القناة): the owner's own channels. Read info/posts; publish ONLY when he presses «انشر» and confirms. ----------------
function chanSeen(j, name) { if (!CH.isChan(j)) return; const k = store.chan.known[j] ??= { jid: j, role: 'unknown', name: '' }; if (name && !k.name) k.name = name; saveSoon() }
const chanSock = () => (state.status === 'connected' && SOCK && typeof SOCK.newsletterMetadata === 'function') ? SOCK : null;
async function chanRefresh(j) {
  const sk = chanSock(); if (!sk) return store.chan.known[j];
  try { const m = CH.parseMeta(await sk.newsletterMetadata('jid', j)); if (m) { store.chan.known[j] = { ...store.chan.known[j], ...m }; saveSoon() } } catch (e) { store.chan.known[j] && (store.chan.known[j].err = String(e?.message || e).slice(0, 80)) }
  return store.chan.known[j];
}
const chanList = () => Object.values(store.chan.known).sort((a, b) => (CH.canPost(b) - CH.canPost(a)) || (b.followers || 0) - (a.followers || 0));
r.get('/api/channels', async (q, s) => {
  if (q.query.refresh && chanSock()) await Promise.all(Object.keys(store.chan.known).slice(0, 30).map(chanRefresh));
  s.json({ connected: !!chanSock(), channels: chanList(), drafts: store.chan.drafts, reminders: store.chan.reminders.filter(x => !x.done), ideas: await chanIdeas(), tips: CH.TIPS });
});
r.post('/api/channels/add', async (q, s) => {
  const raw = String(q.body?.link || ''); const sk = chanSock(); if (!sk) return s.status(503).json({ error: 'اربط الواتساب أول' });
  try { let m = null; const code = CH.inviteCode(raw);
    if (CH.isChan(raw.trim())) m = CH.parseMeta(await sk.newsletterMetadata('jid', raw.trim())); else if (code) m = CH.parseMeta(await sk.newsletterMetadata('invite', code));
    if (!m) return s.status(404).json({ error: 'ما لقينا القناة، تأكد من الرابط' });
    store.chan.known[m.jid] = { ...store.chan.known[m.jid], ...m }; saveSoon(); s.json(store.chan.known[m.jid]) }
  catch (e) { s.status(502).json({ error: 'ما قدرنا نفتح القناة الحين: ' + String(e?.message || e).slice(0, 60) }) }
});
r.get('/api/channels/posts', async (q, s) => {
  const j = String(q.query.jid || ''); if (!store.chan.known[j]) return s.status(404).json({ error: 'قناة غير معروفة' });
  const sk = chanSock(); let posts = store.chan.posts[j] || [], live = false;
  if (sk && typeof sk.newsletterFetchMessages === 'function') try {
    const dec = b => { const P = sk._B?.proto; return P ? P.Message.decode(Buffer.isBuffer(b) ? b : Buffer.from(b)) : (typeof b === 'object' && !Buffer.isBuffer(b) ? b : {}) };
    const got = CH.parsePosts(await sk.newsletterFetchMessages(j, 20, 0, 0), dec); if (got.length) { posts = store.chan.posts[j] = got.slice(0, 30); live = true; saveSoon() } } catch (e) { }
  s.json({ channel: await chanRefresh(j), posts, live });
});
r.get('/api/channels/pic', async (q, s) => {
  const c = store.chan.known[String(q.query.jid || '')]; if (!c?.pic || !/^\/[\w\/.\-?=&%]+$/.test(c.pic)) return s.status(404).end();
  const f = path.join(DIR, 'media', 'chan-' + c.jid.split('@')[0] + '.jpg');
  try { if (!fs.existsSync(f) || q.query.fresh) { const rr = await fetch('https://mmg.whatsapp.net' + c.pic); if (!rr.ok) return s.status(404).end(); fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, Buffer.from(await rr.arrayBuffer())) }
    s.set('Cache-Control', 'private, max-age=86400'); s.type('jpg').sendFile(f) } catch { s.status(404).end() }
});
r.post('/api/channels/publish', async (q, s) => {
  const b = q.body || {}, c = store.chan.known[b.jid];
  if (b.confirm !== true) return s.status(400).json({ error: 'لازم تأكد النشر' });
  if (!c) return s.status(404).json({ error: 'قناة غير معروفة' });
  if (!CH.canPost(c)) return s.status(403).json({ error: 'تقدر تنشر في قنواتك بس (اللي أنت مالكها أو مشرف فيها)' });
  if (!realSend || !chanSock()) return s.status(503).json({ error: 'الواتساب غير متصل' });
  const kind = String(b.kind || 'text'), text = String(b.text || '').trim().slice(0, 4000);
  let content;
  if (kind === 'text') { if (!text) return s.status(400).json({ error: 'اكتب المنشور' }); content = { text } }
  else if (kind === 'poll') { const opts = (Array.isArray(b.options) ? b.options : []).map(x => String(x).trim().slice(0, 100)).filter(Boolean).slice(0, 12);
    if (!text || opts.length < 2) return s.status(400).json({ error: 'اكتب السؤال وخيارين على الأقل' }); content = { poll: { name: text.slice(0, 255), values: opts, selectableCount: 1 } } }
  else if (kind === 'image' || kind === 'video') {
    const mime = String(b.mime || ''); if (!CH.MIME_OK[kind].test(mime)) return s.status(400).json({ error: kind === 'image' ? 'الصورة لازم JPG أو PNG' : 'الفيديو لازم MP4' });
    const buf = Buffer.from(String(b.data || ''), 'base64'); if (!buf.length || buf.length > CH.MAX_BYTES[kind]) return s.status(400).json({ error: 'الملف كبير أو فاضي' });
    content = { [kind]: buf, mimetype: mime, ...(text ? { caption: text } : {}) } }
  else return s.status(400).json({ error: 'نوع غير معروف' });
  try { const m = await realSend(c.jid, content); const p = { id: m?.key?.id || '', t: Date.now(), kind, text: text.slice(0, 2000), reactions: [], views: null, mine: true };
    (store.chan.posts[c.jid] ??= []).unshift(p); store.chan.posts[c.jid] = store.chan.posts[c.jid].slice(0, 30);
    if (b.draftId) store.chan.drafts = store.chan.drafts.filter(d => d.id !== b.draftId);
    audit('channel_post', { jid: c.jid, to: c.name, kind, preview: text.slice(0, 80) }); saveSoon(); s.json({ ok: true, post: p }) }
  catch (e) { audit('channel_post_failed', { jid: c.jid, kind, err: String(e?.message || e).slice(0, 80) }); s.status(500).json({ error: 'ما انتشر: ' + String(e?.message || e).slice(0, 80) }) }
});
r.post('/api/channels/draft', async (q, s) => {   // save / delete a draft (nothing is sent)
  const b = q.body || {}; if (b.delete) { store.chan.drafts = store.chan.drafts.filter(d => d.id !== b.delete); saveSoon(); return s.json({ drafts: store.chan.drafts }) }
  const d = { id: String(b.id || crypto.randomBytes(5).toString('hex')).slice(0, 20), kind: /^(text|image|video|poll)$/.test(b.kind) ? b.kind : 'text', text: String(b.text || '').slice(0, 4000), options: (b.options || []).map(String).slice(0, 12), idea: String(b.idea || '').slice(0, 80), t: Date.now() };
  store.chan.drafts = [d, ...store.chan.drafts.filter(x => x.id !== d.id)].slice(0, 40); saveSoon(); s.json({ drafts: store.chan.drafts, id: d.id });
});
r.get('/api/channels/qr', async (q, s) => { const c = store.chan.known[String(q.query.jid || '')]; if (!c?.invite) return s.status(404).json({ error: 'ما فيه رابط للقناة' });
  const link = 'https://whatsapp.com/channel/' + c.invite; s.json({ link, qr: await QRCode.toDataURL(link, { width: 480, margin: 2 }) }) });
r.post('/api/channels/remind', (q, s) => {    // a reminder for HIM to post (the app never posts by itself)
  const b = q.body || {}; if (b.done) { const x = store.chan.reminders.find(r0 => r0.id === b.done); if (x) x.done = true; saveSoon(); return s.json({ ok: true }) }
  const at = +b.at; if (!(at > Date.now() - 6e4)) return s.status(400).json({ error: 'اختر وقت جاي' });
  const x = { id: crypto.randomBytes(5).toString('hex'), at, text: String(b.text || 'وقت منشور القناة').slice(0, 120), draftId: String(b.draftId || '').slice(0, 20) };
  store.chan.reminders.push(x); store.chan.reminders = store.chan.reminders.filter(r0 => !r0.done).slice(-30); saveSoon(); s.json(x);
});
setInterval(() => { const now = Date.now(); for (const x of store.chan?.reminders || []) if (!x.done && !x.fired && x.at <= now) { x.fired = true; alert('channel', null, '⏰ ' + x.text); saveSoon() } }, 30e3).unref?.();
r.post('/api/channels/write', async (q, s) => {   // «اكتب منشور»: local AI draft in Saudi dialect (or a ready template). Nothing is sent.
  const b = q.body || {}; const j = await brain('/chan_draft', { idea: String(b.idea || '').slice(0, 300), kind: String(b.kind || 'text'), template: String(b.template || '').slice(0, 800) }, { ai: true, timeout: 60e3 });
  s.json(j || { text: b.template || '', engine: 'rules' });
});
async function chanIdeas() {   // ranked ideas: nearest occasion first, then the weekly mix (value / product / poll / behind the scenes)
  const now = new Date(), out = [], shop = S().shopName || 'محلنا';
  const occ = ((await brain('/occasions', { days: 30 }))?.list || []);
  for (const { occasion: on, days } of occ.slice(0, 2)) out.push({ id: 'occ-' + on, tag: days <= 0 ? 'اليوم' : `بعد ${days} يوم`, title: `${on}: افتح الطلبات بدري`, why: 'الناس تقرر هدايا المناسبات قبلها بأيام، المنشور المبكر يجيب طلبات أكثر.', kind: 'image',
    template: `🌷 ${on} قرّب!\nجهزنا تنسيقات خاصة للمناسبة من ${shop}.\nاحجز بدري قبل الزحمة، رد علينا على الخاص ونرتب لك كل شي 💐` });
  out.push({ id: 'new', tag: 'منتج', title: 'صوّر تنسيق اليوم', why: 'صورة حقيقية لتنسيق جديد هي أكثر منشور يجيب طلبات.', kind: 'image', template: `وصلنا اليوم ورد طازج 🌹\nتنسيق جديد من ${shop}، يناسب الهدايا والمناسبات.\nتبيه؟ راسلنا على الخاص وحنا نوصله لك 💐` });
  out.push({ id: 'poll', tag: 'تصويت', title: 'اسأل متابعينك', why: 'التصويت أكثر شي يتفاعل معه المتابعين، ويعطيك وش يبون.', kind: 'poll', template: 'وش لونكم المفضل في البوكيه؟ 💐', options: ['أحمر', 'وردي', 'أبيض'] });
  out.push({ id: 'tip', tag: 'نصيحة', title: 'نصيحة عناية بالورد', why: 'المنشورات المفيدة تخلي الناس يتابعون وما يكتمونك.', kind: 'text', template: 'نصيحة اليوم 🌿\nغيّر موية الورد كل يومين، وقص الساق بشكل مائل، ويعيش معك أسبوع زيادة.\nعندك سؤال؟ راسلنا 🌷' });
  out.push({ id: 'bts', tag: 'من داخل المحل', title: 'ورّهم كيف تجهزون الطلب', why: 'لقطة من التجهيز تبني ثقة وتخلي المنشور ينتشر.', kind: 'video', template: `من داخل ${shop} 🎀\nكذا نجهز طلباتكم بحب.\nتبي واحد مثله؟ راسلنا على الخاص 💐` });
  return out.slice(0, 5);
}
app.use('/' + TOKEN, r); app.use((q, s) => s.status(404).send('Not found'));
const server = app.listen(PORT, HOST, () => console.log(`ENGINE READY http://${HOST}:${PORT}/<token>/`));
const bye = () => { try { save() } catch { } process.exit(0) };
process.on('SIGINT', bye); process.on('SIGTERM', bye);
if (process.env.EXIT_WITH_STDIN === '1') { process.stdin.on('end', bye); process.stdin.resume() }   // parent app closed → stop
backup(); setInterval(() => { try { save() } catch { } }, 60e3).unref(); setInterval(backup, 6 * 3600e3).unref();
export { server };
