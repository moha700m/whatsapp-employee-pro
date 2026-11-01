// The "employee": decides whether to auto-reply to an incoming customer message.
// Pure logic (no I/O) so it can be unit-tested. OFF by default; the owner turns it on.
export const AUTO_DEFAULTS = {
  enabled: false,            // master switch
  schedule: 'offhours',      // 'always' | 'offhours' (outside shop hours) | 'custom' (from→to)
  from: '23:00', to: '09:00',
  mode: 'smart',             // 'smart' = local Saudi brain answers simple questions | 'fixed' = one fixed message
  message: 'هلا والله 🌷 وصلت رسالتك، ونرد عليك بأقرب وقت.',
  handoff: true,             // orders / prices / complaints → polite hold + alert the owner
  handoffMessage: 'أبشر 🌷 وصلت رسالتك، وبيرد عليك المسؤول خلال دقايق إن شاء الله.',
  delaySec: 15,              // wait before replying (feels human, lets the owner jump in)
  cooldownMin: 2,            // min minutes between two auto replies to the same customer
  maxPerDay: 6,              // max auto replies per customer per day
  ownerActiveMin: 10,        // if the owner replied by hand within this window, stay quiet
  maxPerHour: 20,            // anti-ban: all customers together, per hour
  maxTotalPerDay: 80,        // anti-ban: all customers together, per day (lower while a new number warms up)
  humanTyping: true,         // anti-ban: read → typing… → send, with human timing
};
export const BAD_JID = j => !j || j.endsWith('@g.us') || j.endsWith('@broadcast') || j === 'status@broadcast' || j.endsWith('@newsletter');
export const hm = (d, tz) => new Intl.DateTimeFormat('en-GB', { timeZone: tz || 'Asia/Riyadh', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(d);
export const inWindow = (from, to, t) => from === to ? true : from < to ? (t >= from && t < to) : (t >= from || t < to);

export function scheduleOpen(ar, settings, now) {
  const t = hm(new Date(now), settings.tz);
  if (ar.schedule === 'always') return true;
  if (ar.schedule === 'custom') return inWindow(ar.from, ar.to, t);
  return !inWindow(settings.hoursFrom, settings.hoursTo, t);   // offhours
}

/**
 * @param chat {jid,isGroup,messages:[{id,fromMe,ts,text,auto}]}
 * @param msg incoming message
 * @param ctx {settings, connected, now, history:{[jid]:{times:[ts], handoffAt}}, brain: result of think() or null}
 * @returns {action:'skip'|'reply'|'handoff', reason, text?, kind?}
 */
export function decide(chat, msg, ctx) {
  const s = ctx.settings, ar = { ...AUTO_DEFAULTS, ...(s.autoReply || {}) }, now = ctx.now ?? Date.now();
  const skip = reason => ({ action: 'skip', reason });
  if (!ar.enabled) return skip('off');
  if (BAD_JID(chat.jid) || chat.isGroup) return skip('not_customer');
  if (msg.fromMe) return skip('from_me');
  if (!msg.text || !msg.text.trim()) return skip('empty');
  if (now - (msg.at || msg.ts) > 10 * 60e3) return skip('old_message');   // arrival time on this PC; server time only for history
  if (!ctx.connected) return skip('offline');
  if (!scheduleOpen(ar, s, now)) return skip('outside_schedule');
  // owner is handling it: he wrote by hand to this customer in the last few minutes (arrival time when we have it, so a wrong PC clock can't freeze the employee)
  const T = m => m.at || m.ts, manual = chat.messages.filter(m => m.fromMe && !m.auto && (msg.id == null || m.id !== msg.id)).sort((a, b) => T(b) - T(a))[0];
  if (manual && now - T(manual) >= 0 && now - T(manual) < ar.ownerActiveMin * 60e3) return skip('owner_active');
  const h = ctx.history?.[chat.jid] || { times: [] };
  const today = h.times.filter(t => now - t < 864e5);
  if (today.length && now - Math.max(...today) < ar.cooldownMin * 60e3) return skip('cooldown');
  if (today.length >= ar.maxPerDay) return skip('daily_limit');
  const b = ctx.brain;
  if (b && b.intents?.includes('stop')) return skip('customer_said_stop');
  if (ar.handoff && b && b.handoff) {
    if (h.handoffAt && now - h.handoffAt < 6 * 3600e3) return skip('already_handed_off');
    return { action: 'handoff', reason: b.kind, kind: b.kind, text: ar.handoffMessage };
  }
  if (ar.mode === 'smart' && b && b.reply) return { action: 'reply', reason: b.kind, kind: b.kind, text: b.reply };
  return { action: 'reply', reason: 'fixed', kind: 'fixed', text: ar.message };
}
export const SKIP_AR = { off: 'الموظف مطفي', not_customer: 'مو عميل (قروب/حالة)', from_me: 'رسالة منك', empty: 'رسالة بدون نص', old_message: 'رسالة قديمة',
  offline: 'الواتساب غير متصل', outside_schedule: 'خارج وقت عمل الموظف', owner_active: 'أنت ترد عليه بنفسك', cooldown: 'رد عليه قبل شوي', daily_limit: 'وصل حد الردود اليومي',
  customer_said_stop: 'العميل طلب ما نراسله', already_handed_off: 'سبق حوّلناه لك وما رد عليه أحد للحين', rate_limit: 'حماية الرقم: وصل حد الإرسال',
  off_before_send: 'انطفى الموظف قبل الإرسال', owner_replied: 'رديت عليه بنفسك قبل الموظف', not_first: 'هو ما راسلنا أول، الموظف ما يبدأ محادثات', send_failed: 'الإرسال فشل' };
