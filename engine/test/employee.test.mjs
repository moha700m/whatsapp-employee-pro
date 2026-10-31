import test from 'node:test'; import assert from 'node:assert/strict';
import { decide, scheduleOpen, inWindow, AUTO_DEFAULTS } from '../employee.js';
const NOW = Date.UTC(2026, 9, 31, 20, 0);   // 23:00 Riyadh
const S = (ar = {}) => ({ hoursFrom: '09:00', hoursTo: '22:00', tz: 'Asia/Riyadh', autoReply: { ...AUTO_DEFAULTS, enabled: true, schedule: 'always', ...ar } });
const chat = (msgs = []) => ({ jid: '966511110001@s.whatsapp.net', messages: msgs });
const msg = (text = 'هلا', ts = NOW) => ({ fromMe: false, text, ts });
const ctx = (o = {}) => ({ settings: S(o.ar), connected: true, now: NOW, history: o.history || {}, brain: o.brain ?? { kind: 'greeting', reply: 'هلا والله', intents: ['greeting'], handoff: false } });
test('off by default', () => { assert.equal(AUTO_DEFAULTS.enabled, false); assert.equal(decide(chat(), msg(), { ...ctx(), settings: S({ enabled: false }) }).reason, 'off') });
test('smart reply', () => { const d = decide(chat(), msg(), ctx()); assert.equal(d.action, 'reply'); assert.equal(d.text, 'هلا والله') });
test('fixed mode', () => assert.equal(decide(chat(), msg(), ctx({ ar: { mode: 'fixed' } })).text, AUTO_DEFAULTS.message));
test('no groups / status / newsletters', () => { for (const j of ['1@g.us', 'status@broadcast', '1@newsletter']) assert.equal(decide({ jid: j, messages: [] }, msg(), ctx()).reason, 'not_customer') });
test('handoff for orders', () => { const d = decide(chat(), msg('ابي اطلب'), ctx({ brain: { kind: 'order_collect', handoff: true, intents: ['order'] } })); assert.equal(d.action, 'handoff'); assert.equal(d.text, AUTO_DEFAULTS.handoffMessage) });
test('handoff only once per 6h', () => assert.equal(decide(chat(), msg(), ctx({ brain: { handoff: true, intents: ['order'] }, history: { '966511110001@s.whatsapp.net': { times: [], handoffAt: NOW - 3600e3 } } })).reason, 'already_handed_off'));
test('stop respected', () => assert.equal(decide(chat(), msg('وقف'), ctx({ brain: { intents: ['stop'], handoff: true } })).reason, 'customer_said_stop'));
test('cooldown and daily limit', () => {
  assert.equal(decide(chat(), msg(), ctx({ history: { '966511110001@s.whatsapp.net': { times: [NOW - 30e3] } } })).reason, 'cooldown');
  assert.equal(decide(chat(), msg(), ctx({ history: { '966511110001@s.whatsapp.net': { times: Array.from({ length: 6 }, (_, i) => NOW - (i + 1) * 3600e3) } } })).reason, 'daily_limit');
});
test('owner active → quiet, but own auto replies do not count', () => {
  assert.equal(decide(chat([{ fromMe: true, ts: NOW - 60e3 }]), msg(), ctx()).reason, 'owner_active');
  assert.equal(decide(chat([{ fromMe: true, auto: true, ts: NOW - 60e3 }]), msg(), ctx()).action, 'reply');
});
test('old messages and offline ignored', () => { assert.equal(decide(chat(), msg('هلا', NOW - 10 * 60e3), ctx()).reason, 'old_message'); assert.equal(decide(chat(), msg(), { ...ctx(), connected: false }).reason, 'offline') });
test('schedules', () => {
  assert.equal(scheduleOpen({ schedule: 'offhours' }, S(), NOW), true);                  // 23:00 > 22:00 close
  assert.equal(scheduleOpen({ schedule: 'offhours' }, S(), Date.UTC(2026, 9, 31, 9)), false); // 12:00 open
  assert.equal(scheduleOpen({ schedule: 'custom', from: '22:30', to: '06:00' }, S(), NOW), true);
  assert.equal(inWindow('09:00', '09:00', '03:00'), true);
});
test('brain unavailable → fixed message fallback', () => assert.equal(decide(chat(), msg(), { ...ctx(), brain: null }).text, AUTO_DEFAULTS.message));
