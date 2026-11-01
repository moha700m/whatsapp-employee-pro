// Simulated WhatsApp socket used ONLY when FAKE_WA=1 (tests, demos, design QA). Mirrors the Baileys events we use.
import { EventEmitter } from 'events';
import crypto from 'crypto';
export function makeFakeSocket() {
  const ev = new EventEmitter();
  const sock = { ev, user: null, outbox: [],
    async sendMessage(jid, content) {
      const m = { key: { remoteJid: jid, fromMe: true, id: 'OUT' + crypto.randomBytes(6).toString('hex') }, messageTimestamp: Math.floor(Date.now() / 1000), message: { conversation: content.text } };
      sock.outbox.push({ jid, text: content.text ?? content.caption ?? content.poll?.name, kind: content.image ? 'image' : content.video ? 'video' : content.poll ? 'poll' : 'text', bytes: (content.image || content.video)?.length || 0, t: Date.now() });
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
  // simulated channels (newsletters): raw xwa2 metadata + a binary-node message list, like Baileys v7 returns
  sock.channels = {};
  sock.newsletterMetadata = async (type, key) => { const c = type === 'invite' ? Object.values(sock.channels).find(x => x.thread_metadata.invite === key) : sock.channels[key]; return c || null };
  sock.newsletterFetchMessages = async (jid) => ({ tag: 'iq', attrs: {}, content: [{ tag: 'messages', attrs: {}, content: (sock.channels[jid]?._posts || []).map(p => ({ tag: 'message', attrs: { server_id: String(p.id), t: String(Math.floor(p.t / 1000)) },
    content: [{ tag: 'plaintext', attrs: {}, content: p.body }, { tag: 'reactions', attrs: {}, content: (p.reactions || []).map(r => ({ tag: 'reaction', attrs: { code: r[0], count: String(r[1]) } })) }, { tag: 'views_count', attrs: { count: String(p.views || 0) } }] })) }] });
  sock.addChannel = (c) => { sock.channels[c.id] = { id: c.id, thread_metadata: { name: { text: c.name }, description: { text: c.desc || '' }, invite: c.invite, subscribers_count: String(c.followers || 0), picture: c.pic ? { direct_path: c.pic } : undefined },
    viewer_metadata: { role: c.role || 'OWNER' }, _posts: (c.posts || []).map((p, i) => ({ id: 100 + i, t: p.t || Date.now() - i * 864e5, body: p.image ? { imageMessage: { caption: p.text } } : { conversation: p.text }, reactions: p.reactions, views: p.views })) } };
  return sock;
}
