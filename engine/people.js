// Phone numbers & WhatsApp LIDs. WhatsApp now hides many chats behind "@lid" ids (random digits, NOT a phone number).
// We learn LID -> phone mappings from history sync (pnJid/lidJid), contacts, and message keys (senderPn/participantPn),
// and never show a raw LID to the owner.
export const isLid = j => /@lid$/.test(j || '');
export const isPn = j => /@s\.whatsapp\.net$/.test(j || '');
export const bare = j => (j || '').split('@')[0].split(':')[0];
export const normJid = j => { if (!j || typeof j !== 'string' || !j.includes('@')) return null; const [u, d] = j.split('@'); return u.split(':')[0] + '@' + d };
// Saudi numbers as the owner writes them (05xxxxxxxx); others as readable international (+971 50 123 4567 style kept simple).
export function fmtPhone(digits) {
  const d = String(digits || '').replace(/\D/g, ''); if (!d) return '';
  if (/^9665\d{8}$/.test(d)) return '0' + d.slice(3);
  if (/^05\d{8}$/.test(d)) return d;
  if (d.length >= 8 && d.length <= 15) return '+' + d;
  return '';
}
// digits a search box may contain -> comparable forms
export const searchForms = p => { const d = String(p || '').replace(/\D/g, ''); return d ? [d, d.replace(/^9665/, '05'), d.replace(/^05/, '9665')] : [] };
