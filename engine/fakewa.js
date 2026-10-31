// Simulated WhatsApp socket used ONLY when FAKE_WA=1 (tests, demos, design QA). Mirrors the Baileys events we use.
import { EventEmitter } from 'events';
import crypto from 'crypto';
export function makeFakeSocket() {
  const ev = new EventEmitter();
  const sock = { ev, user: null, outbox: [],
    async sendMessage(jid, content) {
      const m = { key: { remoteJid: jid, fromMe: true, id: 'OUT' + crypto.randomBytes(6).toString('hex') }, messageTimestamp: Math.floor(Date.now() / 1000), message: { conversation: content.text } };
      sock.outbox.push({ jid, text: content.text, t: Date.now() });
      setImmediate(() => ev.emit('messages.upsert', { messages: [m], type: 'append' }));
      return m;
    },
    async logout() { ev.emit('connection.update', { connection: 'close', lastDisconnect: { error: { output: { statusCode: 401 } } } }); },
  };
  setTimeout(() => ev.emit('connection.update', { qr: 'SIMULATED-QR-' + Date.now() }), 50);
  sock.link = (me, history) => {
    sock.user = { id: me + '@s.whatsapp.net' };
    ev.emit('connection.update', { connection: 'open' });
    if (history) ev.emit('messaging-history.set', history);
  };
  // simulated Baileys v7 local LID store
  const repo = {}; sock.signalRepository = { lidMapping: { set: (lid, pn) => { repo[lid] = pn }, getPNForLID: async l => repo[l] || null,
    getPNsForLIDs: async ls => ls.filter(l => repo[l]).map(l => ({ lid: l, pn: repo[l] })) } };
  sock.emit = (e, d) => ev.emit(e, d);
  sock.incoming = (jid, text, pushName, ts, senderPn, extra) => {
    const m = { key: { remoteJid: jid, fromMe: false, ...(senderPn ? { senderPn } : {}), ...(extra || {}), id: 'IN' + crypto.randomBytes(6).toString('hex') }, pushName, messageTimestamp: Math.floor((ts || Date.now()) / 1000), message: { conversation: text } };
    ev.emit('messages.upsert', { messages: [m], type: 'notify' });
    return m.key.id;
  };
  // a customer sends real media bytes (the fake socket keeps them in the message so download works offline)
  sock.incomingMedia = (jid, kind, body, pushName) => {
    const m = { key: { remoteJid: jid, fromMe: false, id: 'MD' + crypto.randomBytes(6).toString('hex') }, pushName, messageTimestamp: Math.floor(Date.now() / 1000), message: { [kind + 'Message']: body } };
    ev.emit('messages.upsert', { messages: [m], type: 'notify' }); return m.key.id;
  };
  return sock;
}
