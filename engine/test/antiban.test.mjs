import test from 'node:test'; import assert from 'node:assert/strict';
import { typingMs, limits, canSend, humanSend } from '../antiban.js';
import { fmtPhone, isLid } from '../people.js';
test('typing time grows with length and stays bounded', () => {
  const r = () => 0.5; assert.ok(typingMs('هلا', { rnd: r }) >= 1500); assert.ok(typingMs('x'.repeat(2000), { rnd: r }) <= 14000);
  assert.ok(typingMs('x'.repeat(40), { rnd: r }) < typingMs('x'.repeat(200), { rnd: r })); assert.ok(typingMs('x'.repeat(500), { manual: true }) <= 2500);
});
test('warm-up lowers the daily cap for a new number', () => {
  const now = Date.now(); assert.equal(limits({}, now - 3600e3, now).perDay, 15); assert.equal(limits({}, now - 2 * 864e5, now).perDay, 30);
  assert.equal(limits({ maxTotalPerDay: 80 }, now - 30 * 864e5, now).perDay, 80); assert.equal(limits({}, now - 30 * 864e5, now).warm, false);
});
test('hourly cap, daily cap and min gap', () => {
  const now = Date.now(), lim = { perHour: 3, perDay: 5, minGapMs: 20000 };
  assert.equal(canSend([], lim, now).ok, true);
  assert.ok(canSend([{ t: now - 5000, auto: true }], lim, now).wait > 0);
  assert.equal(canSend([1, 2, 3].map(i => ({ t: now - i * 60e3, auto: true })), lim, now).ok, false);
  assert.equal(canSend([1, 2, 3, 4, 5].map(i => ({ t: now - i * 3 * 3600e3, auto: true })), lim, now).ok, false);
  assert.equal(canSend([1, 2, 3].map(i => ({ t: now - i * 60e3, auto: false })), lim, now).ok, true);   // manual sends don't count
});
test('human sequence: read → composing → paused → send', async () => {
  const log = []; const orig = setTimeout; globalThis.setTimeout = (f) => orig(f, 0);
  try { await humanSend({ jid: 'j', text: 'هلا', send: async () => log.push('send'), presence: async s => log.push(s), read: async () => log.push('read'), readKey: { id: 1 } }) } finally { globalThis.setTimeout = orig }
  assert.deepEqual(log, ['read', 'composing', 'paused', 'send']);
});
test('phones: Saudi 05 format, LIDs never formatted', () => {
  assert.equal(fmtPhone('966551234567'), '0551234567'); assert.equal(fmtPhone('971501234567'), '+971501234567'); assert.equal(fmtPhone(''), '');
  assert.ok(isLid('217398493896730@lid')); assert.ok(!isLid('966551234567@s.whatsapp.net'));
});
