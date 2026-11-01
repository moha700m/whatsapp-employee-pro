// Anti-ban pacing for the auto-reply employee (and a light touch for manual sends).
// Based on public guidance: Baileys README (presence expires ~10s), Baileys issue #2309 / discussion #2358 (baileys-antiban:
// gaussian jitter, warm-up, rate caps, typing model), whatsapp-web.js #532 (bulk/unsolicited = bans), OpenWA "safe sending",
// wasender.dev ban-risk guide. Rules: reply only to people who wrote first, human typing time, jittered gaps, hourly/daily caps,
// gentler limits for a freshly linked number, auto-pause on repeated failures. Nothing here ever starts a conversation.
export const sleep = ms => new Promise(r => setTimeout(r, ms));
export function gauss(mean, sd, rnd = Math.random) { let u = 0, v = 0; while (!u) u = rnd(); while (!v) v = rnd(); return mean + sd * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v) }
// typing time ~ 35–55 words/min, 1.5s..14s for the employee; manual sends get a short 0.6..2.5s indicator
export function typingMs(text, { manual = false, rnd = Math.random } = {}) {
  const cps = Math.max(3, gauss(4.5, 1, rnd)); const t = (String(text || '').length / cps) * 1000;
  return manual ? Math.min(2500, Math.max(600, t / 4)) : Math.min(14000, Math.max(1500, t));
}
// "reading" pause before typing: 1–4s, longer for long incoming messages
export const readMs = (incoming, rnd = Math.random) => Math.min(6000, 1000 + rnd() * 3000 + String(incoming || '').length * 15);
export const WARMUP = [[1, 15], [3, 30], [7, 60]];   // [days since linking, max auto replies per day]
export function limits(ar, linkedAt, now = Date.now()) {
  const days = linkedAt ? (now - linkedAt) / 864e5 : 99; let day = Math.min(1000, Math.max(1, +ar.maxTotalPerDay || 500)), warm = false;
  for (const [d, cap] of WARMUP) if (days < d) { if (cap < day) { day = cap; warm = true } break }
  return { perHour: Math.min(200, Math.max(1, +ar.maxPerHour || 60)), perDay: day, warm, minGapMs: 20000 };
}
// sends: [{t, auto}] -> may we send one more auto reply now?
export function canSend(sends, lim, now = Date.now()) {
  const auto = sends.filter(x => x.auto), h = auto.filter(x => now - x.t < 36e5).length, d = auto.filter(x => now - x.t < 864e5).length;
  if (h >= lim.perHour) return { ok: false, why: 'وصل حد الساعة' }; if (d >= lim.perDay) return { ok: false, why: lim.warm ? 'حد التسخين للرقم الجديد' : 'وصل حد اليوم' };
  const last = Math.max(0, ...auto.map(x => x.t)); if (now - last < lim.minGapMs) return { ok: false, wait: lim.minGapMs - (now - last) + Math.random() * 15000 };
  return { ok: true };
}
// The human sequence: (mark the customer's message read) -> composing (refreshed every ~8s) -> paused -> send.
export async function humanSend({ jid, text, send, presence, read, readKey, manual = false, incoming = '' }) {
  if (read && readKey) { await sleep(manual ? 200 : readMs(incoming)); try { await read([readKey]) } catch { } }
  let left = typingMs(text, { manual });
  if (presence) { try { await presence('composing', jid) } catch { } }
  while (left > 0) { const step = Math.min(left, 8000); await sleep(step); left -= step; if (left > 0 && presence) try { await presence('composing', jid) } catch { } }
  if (presence) { try { await presence('paused', jid) } catch { } }
  return send(jid, { text });
}
