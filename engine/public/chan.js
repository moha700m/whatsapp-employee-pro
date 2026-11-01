// «القناة» — the owner's WhatsApp Channel: see it, get ideas, write (with the local AI), keep drafts, set a reminder,
// and publish ONLY after he presses «انشر» and confirms. Nothing is ever posted by itself.
let CHN = null, CHSEL = null, CMP = { kind: 'text', text: '', options: ['', ''], file: null, draftId: '' };
const KIND_AR = { text: 'نص', image: 'صورة', video: 'فيديو', poll: 'تصويت' };
const fmtN = n => n == null ? '—' : n >= 1000 ? num((n / 1000).toFixed(n >= 1e4 ? 0 : 1)) + ' ألف' : num(n);
const ROLE_AR = { owner: 'قناتك', admin: 'أنت مشرف', follower: 'متابَعة', guest: 'زائر', unknown: '' };
const chPic = c => c.pic ? `<img src="api/channels/pic?jid=${encodeURIComponent(c.jid)}" alt="" loading="lazy">` : `<span>${esc((c.name || 'ق').trim()[0] || 'ق')}</span>`;
async function renderChan() {
  const el = $('#p-chan');
  el.innerHTML = `<div class="page-h"><div><h1>القناة</h1><p>قناة واتساب حقتك: انشر فيها عروضك وتنسيقاتك لكل متابعينك مرة وحدة. نجهز لك أفكار ونكتب معك، و<b>ما ينتشر شي إلا لما تضغط «انشر» وتأكد</b>.</p></div></div><div id="chb"><div class="skel" style="height:320px"></div></div>`;
  try { CHN = await api('api/channels?refresh=1') } catch { $('#chb').innerHTML = errBox('ما قدرنا نفتح القناة', renderChan); return }
  const mine = CHN.channels.filter(c => c.role === 'owner' || c.role === 'admin');
  if (!CHSEL || !CHN.channels.find(c => c.jid === CHSEL)) CHSEL = (mine[0] || CHN.channels[0])?.jid || null;
  const c = CHN.channels.find(x => x.jid === CHSEL), can = c && (c.role === 'owner' || c.role === 'admin');
  $('#chb').innerHTML = `${CHN.connected ? '' : '<div class="notice w">الواتساب مو متصل الحين. تقدر تكتب وتحفظ مسودات، والنشر يرجع لما يتصل.</div>'}
  <div class="ch-bar" role="tablist" aria-label="قنواتك">${CHN.channels.map(x => `<button class="ch-pill ${x.jid === CHSEL ? 'on' : ''}" data-ch="${esc(x.jid)}" role="tab" aria-selected="${x.jid === CHSEL}"><span class="ch-av">${chPic(x)}</span><span class="grow"><b>${esc(x.name || 'قناة')}</b><small>${fmtN(x.followers)} متابع${ROLE_AR[x.role] ? ' · ' + ROLE_AR[x.role] : ''}</small></span></button>`).join('')}
    <button class="ch-pill add" id="chadd"><span class="ch-av">+</span><span class="grow"><b>أضف قناتك</b><small>برابط القناة</small></span></button></div>
  ${!c ? `<div class="ch-empty"><svg aria-hidden="true"><use href="#i-chat"/></svg><h2>ما لقينا قناتك للحين</h2><p>افتح واتساب في الجوال ← «المستجدات» ← قناتك ← «مشاركة الرابط»، وانسخ الرابط وحطه هنا.<br>ما عندك قناة؟ سوّها من نفس المكان بـ «+ قناة جديدة»، وترجع لها هنا.</p>
      <div class="ch-addrow"><input id="chlink" placeholder="https://whatsapp.com/channel/…" aria-label="رابط القناة" dir="ltr"><button class="btn primary" id="chgo">أضف</button></div></div>` :
  `<div class="ch-grid"><div class="ch-main">
    <section class="ch-card ch-head"><span class="ch-av xl">${chPic(c)}</span><div class="grow"><h2>${esc(c.name || 'قناة')}${c.verified ? ' <span class="chip g">موثقة</span>' : ''}</h2><p class="muted">${esc(c.desc || '').slice(0, 160)}</p></div>
      <div class="ch-stat"><b>${fmtN(c.followers)}</b><small>متابع</small></div></section>
    ${can ? `<section class="ch-card"><h3>أفكار جاهزة لك</h3><p class="muted">مرتبة من الأهم. اضغط فكرة وتنزل في المنشور تحت، عدّلها وانشر.</p>
      <div class="ch-ideas">${CHN.ideas.map((i, n) => `<button class="ch-idea ${n === 0 ? 'top' : ''}" data-idea="${esc(i.id)}"><span class="chip ${n === 0 ? 'g' : ''}">${esc(i.tag)}</span><b>${esc(i.title)}</b><small>${esc(i.why)}</small><span class="ch-k">${KIND_AR[i.kind]}</span></button>`).join('')}</div></section>
    <section class="ch-card" id="cmp"></section>` : `<div class="notice b">هذي قناة تتابعها بس. تقدر تشوف منشوراتها، والنشر يكون في قنواتك أنت.</div>`}
    <section class="ch-card"><h3>آخر المنشورات</h3><div id="chposts"><div class="skel" style="height:120px"></div></div></section>
  </div><aside class="ch-side">
    ${CHN.drafts.length ? `<section class="ch-card"><h3>مسوداتك</h3>${CHN.drafts.map(d => `<div class="ch-draft"><button class="grow" data-dr="${esc(d.id)}"><span class="chip">${KIND_AR[d.kind]}</span> ${esc(d.text.slice(0, 70) || '…')}</button><button class="icon-btn" data-drx="${esc(d.id)}" aria-label="احذف المسودة"><svg><use href="#i-x"/></svg></button></div>`).join('')}</section>` : ''}
    ${CHN.reminders.length ? `<section class="ch-card"><h3>تذكيراتك</h3>${CHN.reminders.map(r => `<div class="ch-rem"><svg aria-hidden="true"><use href="#i-clock"/></svg><span class="grow">${esc(r.text)}<small>${new Date(r.at).toLocaleString('ar-SA', { weekday: 'long', hour: 'numeric', minute: '2-digit' })}</small></span><button class="btn sm ghost" data-rmd="${esc(r.id)}">تم</button></div>`).join('')}</section>` : ''}
    ${c.invite ? `<section class="ch-card ch-grow"><h3>كبّر قناتك</h3><p class="muted">حط الرابط في بايو انستقرام وسناب، واطبع الرمز على كرت الطلب.</p><div id="chqr" class="ch-qr"></div>
      <div class="ch-act"><button class="btn sm" id="chcp">انسخ الرابط</button><a class="btn sm ghost" id="chdl" download="qr-channel.png">نزّل الرمز</a></div></section>` : ''}
    <section class="ch-card"><h3>عشان قناتك تنجح</h3><ol class="ch-tips">${CHN.tips.map(t => `<li><b>${esc(t.t)}</b><span>${esc(t.b)}</span></li>`).join('')}</ol></section>
  </aside></div>`}`;
  $$('[data-ch]').forEach(b => b.onclick = () => { CHSEL = b.dataset.ch; renderChan() });
  $('#chadd').onclick = () => addChan();
  if ($('#chgo')) { $('#chgo').onclick = () => addChan($('#chlink').value); $('#chlink').onkeydown = e => { if (e.key === 'Enter') addChan($('#chlink').value) } }
  if (!c) return;
  $$('[data-idea]').forEach(b => b.onclick = () => { const i = CHN.ideas.find(x => x.id === b.dataset.idea); CMP = { kind: i.kind, text: i.template, options: i.options ? [...i.options] : ['', ''], file: null, draftId: '', idea: i.title }; drawCmp(); $('#cmp').scrollIntoView({ behavior: 'smooth', block: 'start' }); $('#ctext').focus() });
  $$('[data-dr]').forEach(b => b.onclick = () => { const d = CHN.drafts.find(x => x.id === b.dataset.dr); CMP = { kind: d.kind, text: d.text, options: d.options?.length ? d.options : ['', ''], file: null, draftId: d.id }; drawCmp(); $('#cmp').scrollIntoView({ behavior: 'smooth' }) });
  $$('[data-drx]').forEach(b => b.onclick = async () => { await api('api/channels/draft', { delete: b.dataset.drx }); renderChan() });
  $$('[data-rmd]').forEach(b => b.onclick = async () => { await api('api/channels/remind', { done: b.dataset.rmd }); renderChan() });
  if (c.invite) api('api/channels/qr?jid=' + encodeURIComponent(c.jid)).then(q => { $('#chqr').innerHTML = `<img src="${q.qr}" alt="رمز QR لقناتك"><small dir="ltr">${esc(q.link)}</small>`; $('#chdl').href = q.qr;
    $('#chcp').onclick = () => navigator.clipboard.writeText(q.link).then(() => toast('انسخ الرابط ✓'), () => toast('ما قدرنا ننسخ')) }).catch(() => { });
  if (can) drawCmp(); loadPosts(c.jid);
}
async function addChan(link) {
  if (link === undefined) { const ok = await ask('أضف قناتك', `<p>افتح واتساب في الجوال ← «المستجدات» ← قناتك ← «مشاركة الرابط»، والصق الرابط هنا:</p><input id="chl2" dir="ltr" placeholder="https://whatsapp.com/channel/…" aria-label="رابط القناة" style="width:100%">`, 'أضف'); if (!ok) return; link = $('#chl2')?.value }
  if (!String(link || '').trim()) return toast('حط رابط القناة');
  try { const c = await api('api/channels/add', { link }); CHSEL = c.jid; toast('أضفنا ' + (c.name || 'القناة') + ' ✓'); renderChan() } catch (e) { toast(e.message) }
}
async function loadPosts(jid) {
  try { const j = await api('api/channels/posts?jid=' + encodeURIComponent(jid)); if (CHSEL !== jid || !$('#chposts')) return;
    $('#chposts').innerHTML = j.posts.length ? `<ul class="ch-posts">${j.posts.slice(0, 12).map(p => `<li><div class="ch-pk"><span class="chip">${KIND_AR[p.kind] || 'منشور'}</span><small class="muted">${p.t ? clock(p.t) : ''}</small></div><p>${esc(p.text || '—')}</p>
      <div class="ch-rx">${p.views != null ? `<span title="المشاهدات"><svg aria-hidden="true"><use href="#i-eye"/></svg>${fmtN(p.views)}</span>` : ''}${(p.reactions || []).map(r => `<span>${esc(r.e)} ${fmtN(r.n)}</span>`).join('')}${p.mine && p.views == null ? '<small class="muted">انتشر من البرنامج</small>' : ''}</div></li>`).join('')}</ul>`
      : '<p class="muted">ما فيه منشورات للحين. ابدأ بفكرة من فوق 👆</p>' } catch { if ($('#chposts')) $('#chposts').innerHTML = '<p class="muted">ما قدرنا نجيب المنشورات الحين.</p>' }
}
function drawCmp() {
  const el = $('#cmp'); if (!el) return; const k = CMP.kind;
  el.innerHTML = `<h3>منشور جديد${CMP.idea ? ` <small class="muted">· ${esc(CMP.idea)}</small>` : ''}</h3>
  <div class="seg" role="radiogroup" aria-label="نوع المنشور">${Object.entries(KIND_AR).map(([v, l]) => `<button role="radio" aria-checked="${k === v}" class="${k === v ? 'on' : ''}" data-kind="${v}">${l}</button>`).join('')}</div>
  ${k === 'image' || k === 'video' ? `<label class="ch-drop ${CMP.file ? 'has' : ''}" for="cfile">${CMP.file ? (k === 'image' ? `<img src="${CMP.file.url}" alt="معاينة الصورة">` : `<div class="ch-vid"><svg aria-hidden="true"><use href="#i-play"/></svg><b>${esc(CMP.file.name)}</b><small>${num((CMP.file.size / 1048576).toFixed(1))} م.ب</small></div>`) + '<span class="btn sm ghost">غيّر</span>'
      : `<svg aria-hidden="true"><use href="#i-plus"/></svg><b>اختر ${k === 'image' ? 'صورة' : 'فيديو'}</b><small>${k === 'image' ? 'JPG أو PNG، صورة حقيقية لتنسيقك أحسن شي' : 'MP4 قصير، أقل من ٦٤ م.ب'}</small>`}
      <input type="file" id="cfile" accept="${k === 'image' ? 'image/jpeg,image/png,image/webp' : 'video/mp4,video/3gpp,video/quicktime'}" hidden></label>` : ''}
  <label class="lbl" for="ctext">${k === 'poll' ? 'السؤال' : k === 'text' ? 'نص المنشور' : 'الوصف (اختياري)'}</label>
  <textarea id="ctext" rows="${k === 'poll' ? 2 : 5}" placeholder="${k === 'poll' ? 'مثلاً: وش لونكم المفضل في البوكيه؟' : 'اكتب منشورك، أو اضغط «اكتب منشور» ونكتبه لك'}">${esc(CMP.text)}</textarea>
  <div class="ch-meta"><small class="muted" id="ccnt">${num(CMP.text.length)} حرف</small>${/راسل|احجز|اطلب|تواصل|كلمنا|الخاص/.test(CMP.text) || k === 'poll' ? '' : '<small class="ch-hint">💡 اختم بطلب واضح مثل «راسلنا على الخاص»</small>'}</div>
  ${k === 'poll' ? `<div class="ch-opts">${CMP.options.map((o, i) => `<div class="trow"><input data-op="${i}" value="${esc(o)}" placeholder="خيار ${num(i + 1)}" aria-label="خيار ${i + 1}">${CMP.options.length > 2 ? `<button class="icon-btn" data-opx="${i}" aria-label="احذف الخيار"><svg><use href="#i-x"/></svg></button>` : ''}</div>`).join('')}
    ${CMP.options.length < 3 ? '<button class="btn sm ghost" id="copa">+ خيار</button>' : ''}<small class="muted">٣ خيارات بالكثير يخلي الناس يصوتون أكثر.</small></div>` : ''}
  <div class="ch-tools"><button class="btn soft" id="cai"><svg aria-hidden="true"><use href="#i-spark"/></svg>اكتب منشور</button><button class="btn ghost" id="csv">احفظ مسودة</button><button class="btn ghost" id="crm"><svg aria-hidden="true"><use href="#i-clock"/></svg>ذكّرني أنشره</button>
    <span class="grow"></span><button class="btn primary big" id="cgo">انشر في القناة</button></div>`;
  $$('[data-kind]').forEach(b => b.onclick = () => { CMP.kind = b.dataset.kind; if (CMP.kind !== 'image' && CMP.kind !== 'video') CMP.file = null; else if (CMP.file && CMP.file.kind !== CMP.kind) CMP.file = null; drawCmp() });
  $('#ctext').oninput = e => { CMP.text = e.target.value; $('#ccnt').textContent = num(CMP.text.length) + ' حرف' };
  $$('[data-op]').forEach(i => i.oninput = () => CMP.options[i.dataset.op] = i.value);
  $$('[data-opx]').forEach(b => b.onclick = () => { CMP.options.splice(b.dataset.opx, 1); drawCmp() });
  if ($('#copa')) $('#copa').onclick = () => { CMP.options.push(''); drawCmp() };
  if ($('#cfile')) $('#cfile').onchange = e => { const f = e.target.files[0]; if (!f) return; const max = k === 'image' ? 16 : 64; if (f.size > max * 1048576) return toast(`الملف أكبر من ${num(max)} م.ب`);
    const rd = new FileReader(); rd.onload = () => { CMP.file = { kind: k, name: f.name, size: f.size, mime: f.type, url: rd.result }; drawCmp() }; rd.readAsDataURL(f) };
  $('#cai').onclick = async () => { const b = $('#cai'), o = b.innerHTML; b.disabled = true; b.textContent = 'يكتب…';
    try { const r = await api('api/channels/write', { idea: CMP.idea || CMP.text.slice(0, 120) || 'منشور عن ورد اليوم', kind: k, template: CMP.text }); CMP.text = r.text; drawCmp(); toast(r.engine === 'ai' ? 'كتبه الذكاء، راجعه قبل النشر' : 'الذكاء مو متاح الحين، خليناه على النص الجاهز') }
    catch (e) { toast(e.message) } finally { if ($('#cai')) { $('#cai').disabled = false; $('#cai').innerHTML = o } } };
  $('#csv').onclick = async () => { const j = await api('api/channels/draft', { id: CMP.draftId || undefined, kind: k, text: CMP.text, options: CMP.options, idea: CMP.idea }); CMP.draftId = j.id; toast('انحفظت المسودة ✓'); CHN.drafts = j.drafts };
  $('#crm').onclick = async () => {
    const d = new Date(Date.now() + 3600e3); const pad = n => String(n).padStart(2, '0'); const v = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:00`;
    const ok = await ask('ذكّرني أنشره', `<p>نحفظ المنشور مسودة، ونطلع لك تنبيه بالوقت اللي تختاره. <b>ما ينتشر لحاله</b>، أنت اللي تنشره.</p><label class="lbl" for="rmat">متى؟</label><input type="datetime-local" id="rmat" value="${v}" style="width:100%"><small class="muted">أحسن وقت غالباً: ٤–٦ العصر أو ٨–١٠ الليل.</small>`, 'ذكّرني'); if (!ok) return;
    const at = new Date($('#rmat').value).getTime(); const j = await api('api/channels/draft', { id: CMP.draftId || undefined, kind: k, text: CMP.text, options: CMP.options, idea: CMP.idea }); CMP.draftId = j.id;
    try { await api('api/channels/remind', { at, text: 'وقت منشور القناة: ' + (CMP.text.split('\n')[0] || '').slice(0, 60), draftId: j.id }); toast('بنذكرك ✓'); renderChan() } catch (e) { toast(e.message) } };
  $('#cgo').onclick = publish;
}
async function publish() {
  const c = CHN.channels.find(x => x.jid === CHSEL), k = CMP.kind, text = CMP.text.trim(), opts = CMP.options.map(s => s.trim()).filter(Boolean);
  if ((k === 'text' || k === 'poll') && !text) return toast(k === 'poll' ? 'اكتب السؤال' : 'اكتب المنشور');
  if (k === 'poll' && opts.length < 2) return toast('حط خيارين على الأقل'); if ((k === 'image' || k === 'video') && !CMP.file) return toast(k === 'image' ? 'اختر صورة' : 'اختر فيديو');
  const prev = `<div class="ch-prev">${k === 'image' ? `<img src="${CMP.file.url}" alt="">` : k === 'video' ? `<div class="ch-vid"><svg aria-hidden="true"><use href="#i-play"/></svg><b>${esc(CMP.file.name)}</b></div>` : ''}${text ? `<p>${esc(text)}</p>` : ''}${k === 'poll' ? `<ul>${opts.map(o => `<li>${esc(o)}</li>`).join('')}</ul>` : ''}</div>`;
  const ok = await ask('تأكيد النشر', `<p>بينتشر الحين في <b>${esc(c.name)}</b> ويشوفه <b>${fmtN(c.followers)}</b> متابع. ما تقدر ترجعه من البرنامج.</p>${prev}`, 'انشر الحين'); if (!ok) return;
  const b = $('#cgo'); b.disabled = true; b.textContent = 'ينشر…';
  try { await api('api/channels/publish', { jid: c.jid, kind: k, text, options: opts, confirm: true, draftId: CMP.draftId || undefined, ...(CMP.file ? { mime: CMP.file.mime, data: CMP.file.url.split(',')[1] } : {}) });
    toast('انتشر في القناة ✓'); CMP = { kind: 'text', text: '', options: ['', ''], file: null, draftId: '' }; renderChan() }
  catch (e) { toast(e.message); b.disabled = false; b.textContent = 'انشر في القناة' }
}
