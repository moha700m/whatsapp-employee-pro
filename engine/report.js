const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const d=t=>t?new Date(t).toLocaleString('ar-SA',{timeZone:'Asia/Riyadh',dateStyle:'medium',timeStyle:'short'}):'';
export function reportHTML(a,s={}){
  const rows=a.customers.map((c,i)=>`<tr><td>${i+1}</td><td>${esc(c.name||'—')}</td><td dir="ltr">+${esc(c.phone)}</td><td>${esc(c.order||'—')}${c.note?`<br><small>${esc(c.note)}</small>`:''}</td><td><span class="b ${c.status==='معلق'?'p':c.status==='مكتمل'?'ok':''}">${esc(c.status)}</span>${c.unanswered?'<br><small class="r">بدون رد</small>':''}</td><td>${d(c.lastAt)}</td></tr>`).join('');
  return `<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><style>
  body{font-family:'Noto Naskh Arabic','Noto Sans Arabic';color:#222;margin:0}h1{color:${s.brand||'#b0305a'};margin:0}
  .k{display:flex;gap:10px;margin:14px 0}.k div{flex:1;border:1px solid #eee;border-radius:10px;padding:10px;text-align:center}.k b{display:block;font-size:22px;color:${s.brand||'#b0305a'}}
  table{width:100%;border-collapse:collapse;font-size:11px}th{background:${s.brand||'#b0305a'};color:#fff;padding:6px}td{border-bottom:1px solid #eee;padding:6px;vertical-align:top}
  .b{padding:2px 8px;border-radius:9px;background:#eee}.p{background:#ffe2c2}.ok{background:#d4f5dc}.r{color:#c00}@media print{.np{display:none}}small{color:#666}</style>
  <button onclick="print()" class="np" style="float:left;padding:8px 14px">طباعة / حفظ PDF</button><h1>${esc(s.shopName||'')} — تقرير المحادثات</h1><div>${d(a.generatedAt)} — ${esc(a.engine)}</div>
  <div class="k"><div><b>${a.stats.customers}</b>عملاء</div><div><b>${a.stats.orders}</b>طلبات</div><div><b>${a.stats.pending}</b>معلقة</div><div><b>${a.stats.unanswered}</b>بدون رد</div></div>
  <p>${esc(a.summary)}</p><table><tr><th>#</th><th>الاسم</th><th>الرقم</th><th>الطلب</th><th>الحالة</th><th>آخر رسالة</th></tr>${rows}</table></html>`;
}
export const csv=a=>'\ufeffName,Phone,Status,Order\n'+a.customers.map(c=>[c.name||('عميل '+c.phone),'+'+c.phone,c.status,c.order].map(v=>`"${String(v??'').replace(/"/g,'""')}"`).join(',')).join('\n');
export const vcf=a=>a.customers.filter(c=>/^(966|971|973|965|974|968|20|1)\d{7,11}$/.test(c.phone)&&c.phone.length<=13).map(c=>`BEGIN:VCARD\nVERSION:3.0\nFN:${(c.name||'عميل '+c.phone).replace(/\n/g,' ')}\nTEL;TYPE=CELL:+${c.phone}\nNOTE:${(c.order||'').replace(/\n/g,' ')}\nEND:VCARD`).join('\n');
