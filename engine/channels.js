// WhatsApp Channels (newsletters) for the owner: list his channels, read info + recent posts, publish ONLY after he presses «انشر» and confirms.
// Never posts by itself, never broadcasts to people. Baileys v7 newsletter APIs (newsletterMetadata / newsletterFetchMessages / sendMessage to @newsletter).
export const isChan = j => typeof j === 'string' && /^\d{6,30}@newsletter$/.test(j);
export const inviteCode = s => { s = String(s || '').trim(); const m = s.match(/whatsapp\.com\/channel\/([A-Za-z0-9_-]{10,40})/) || s.match(/^([A-Za-z0-9_-]{10,40})$/); return m ? m[1] : null };
const txt = v => typeof v === 'string' ? v : (v?.text || '');
const ROLE = { OWNER: 'owner', ADMIN: 'admin', SUBSCRIBER: 'follower', GUEST: 'guest' };
// raw xwa2 metadata → small, stable object (field names differ between WA versions, so read defensively)
export function parseMeta(m) {
  if (!m || !m.id) return null; const t = m.thread_metadata || m.threadMetadata || m, v = m.viewer_metadata || m.viewerMetadata || {};
  const pic = t.picture?.direct_path || t.picture?.directPath || t.preview?.direct_path || t.preview?.directPath || '';
  const role = String(v.role || m.role || '').toUpperCase();
  const n = Number(t.subscribers_count ?? t.subscribersCount ?? m.subscribers ?? NaN);
  return { jid: m.id, name: txt(t.name) || m.name || '', desc: txt(t.description) || m.description || '', invite: t.invite || m.invite || '', pic, role: ROLE[role] || (role ? role.toLowerCase() : 'unknown'),
    followers: Number.isFinite(n) ? n : null, verified: String(t.verification || '').toUpperCase() === 'VERIFIED', created: Number(t.creation_time || 0) * 1000 || null, at: Date.now() };
}
const kids = n => Array.isArray(n?.content) ? n.content : [];
const child = (n, tag) => kids(n).find(x => x.tag === tag);
// newsletterFetchMessages returns a binary node: <messages><message server_id t type><plaintext>proto</plaintext><reactions><reaction code count/></reactions><views_count count/></message>
export function parsePosts(node, decode) {
  const box = node?.tag === 'messages' ? node : child(node, 'messages') || kids(node).find(x => kids(x).some(y => y.tag === 'message')) || node; const out = [];
  for (const m of kids(box).filter(x => x.tag === 'message')) {
    let body = {}; const pt = child(m, 'plaintext');
    try { if (pt && pt.content && decode) body = decode(pt.content) || {} } catch {}
    const k = body.imageMessage ? 'image' : body.videoMessage ? 'video' : body.audioMessage ? 'audio' : body.documentMessage ? 'document' : body.stickerMessage ? 'sticker' : 'text';
    const text = body.conversation || body.extendedTextMessage?.text || body.imageMessage?.caption || body.videoMessage?.caption || body.documentMessage?.fileName || '';
    const reactions = kids(child(m, 'reactions')).map(r => ({ e: r.attrs?.code || '', n: +(r.attrs?.count || 0) })).filter(r => r.e);
    const vc = child(m, 'views_count'); const views = vc ? +(vc.attrs?.count || 0) : null;
    out.push({ id: m.attrs?.server_id || m.attrs?.id || '', t: +(m.attrs?.t || 0) * 1000, kind: k, text: String(text).slice(0, 2000), reactions, views });
  }
  return out.sort((a, b) => b.t - a.t);
}
export const canPost = c => c && (c.role === 'owner' || c.role === 'admin');
export const KINDS = { text: 1, image: 1, video: 1 };
export const MAX_BYTES = { image: 16 << 20, video: 64 << 20 };
export const MIME_OK = { image: /^image\/(jpeg|png|webp)$/, video: /^video\/(mp4|3gpp|quicktime)$/ };
// growth tips shown in the tab (sources: qualimero.com/en/blog/whatsapp-channel, zenweb.my/blog/whatsapp-channels-malaysia, sproutsocial.com/insights/whatsapp-marketing-for-small-business)
export const TIPS = [
  { t: 'انشر ٢ إلى ٤ مرات بالأسبوع', b: 'أكثر من كذا يكتمونك، وأقل يتركونك. كل منشور يكون فيه فايدة.' },
  { t: 'كل منشور له طلب واحد واضح', b: 'مثل «راسلنا على الخاص» أو «احجز بدري». المتابع ما يقدر يرد على القناة.' },
  { t: 'أحسن وقت: العصر وبعد العشاء', b: 'جرّب ٤–٦ العصر و٨–١٠ الليل، وخميس وجمعة للهدايا. شوف المشاهدات وعدّل.' },
  { t: 'المناسبات قبلها بأسبوع', b: 'الناس تقرر الهدية بدري. انشر قبل الزحمة بأيام.' },
  { t: 'وزّع رابط القناة', b: 'حطه في بايو انستقرام وسناب، وعلى كرت الطلب والكيس كرمز QR.' },
];
