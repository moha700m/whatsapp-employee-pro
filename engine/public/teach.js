// «تعليم الموظف» — the owner teaches the AI: personality, do/don't, shop info, prices, FAQ, examples, forbidden words, handoff + a live «جرّب» box.
// Every change saves by itself (and applies to the next reply immediately).
let TEACH = null, TDEF = null, TSAVE = null;
const TSECS = [
  ['persona', 'الشخصية والأسلوب', 'كيف يتكلم الموظف مع عملائك. اكتبها بكلامك، مثل ما توصف موظف جديد.'],
  ['dos', 'سوّ كذا', 'أشياء تبي الموظف يسويها دايم. كل سطر قاعدة.'],
  ['donts', 'لا تسوّي كذا', 'أشياء ممنوع يسويها أبد. الموظف يلتزم فيها حتى لو العميل أصر.'],
  ['shop', 'معلومات المحل', 'وش تبيعون، التوصيل والدفع. الموظف يرد منها بدل ما يخمّن.'],
  ['prices', 'قائمة الأسعار', 'الموظف ما يذكر أي سعر غير اللي هنا. أي سعر ثاني يحوله لك.'],
  ['faq', 'أسئلة يسألونها كثير', 'إذا العميل سأل سؤال قريب، الموظف يرد بجوابك نفسه حرفياً.'],
  ['examples', 'أمثلة ردود', 'علّمه بالمثال: العميل يقول كذا ← ترد كذا. يتعلم منها طريقتك.'],
  ['forbidden', 'كلمات ومواضيع ممنوعة', 'إذا الرد فيه وحدة منها ما ينرسل، ويرجع للرد الآمن.'],
  ['handoff', 'متى يحوّل لك', 'إذا العميل جاب طاري وحدة من هذي، الموظف يوقف ويقول له إنك بترد عليه بنفسك.'],
];
const tv = (k) => TEACH[k] ?? TDEF?.[k];
function teachSave(extra) {
  $('#tsv').textContent = 'يحفظ…'; $('#tsv').className = 'tsv busy'; clearTimeout(TSAVE);
  TSAVE = setTimeout(async () => { try { SET = await api('api/settings', { teach: { ...TDEF, ...TEACH }, ...(extra || {}) }); $('#tsv').textContent = 'محفوظ ✓'; $('#tsv').className = 'tsv ok' } catch (e) { $('#tsv').textContent = 'ما انحفظ، جرّب مرة ثانية'; $('#tsv').className = 'tsv bad' } }, 500);
}
const aiLine = a => {
  if (!a || a.state === 'unknown') return ['', 'نتأكد من المساعد…'];
  if (SET.aiModel === 'off') return ['off', 'مطفي — الموظف يستخدم الردود الذكية العادية بدون الذكاء المحلي'];
  if (!a.available) return ['off', 'ما يقدر يشتغل على هذا الجهاز: ' + (a.reason || '') + ' — الموظف يستخدم الردود العادية'];
  return [a.state === 'ready' ? 'on' : 'idle', { ready: 'جاهز', loading: 'يجهز…', idle: 'نايم (يصحى مع أول رسالة)' }[a.state] || a.state];
};
async function renderTeach(box) {
  box.innerHTML = '<div class="skel" style="height:300px"></div>';
  try { const j = await api('api/teach'); TDEF = j.defaults || {}; TEACH = JSON.parse(JSON.stringify(j.current || TDEF)) } catch { box.innerHTML = '<p class="err">ما قدرنا نفتح الصفحة</p>'; return }
  const a = ST.ai || {}; const [cls, txt] = aiLine(a);
  box.innerHTML = `<div class="teach"><div class="tmain">
    <div class="tintro"><div><h3>علّم موظفك</h3><p>كل اللي تكتبه هنا يمشي عليه الموظف في الردود المقترحة والرد التلقائي. التعديل ينحفظ لحاله.</p></div><span id="tsv" class="tsv ok">محفوظ ✓</span></div>
    <div class="tcard aist"><div class="grow"><b>الذكاء المحلي على جهازك</b><div class="ailine"><i class="dot ${cls}"></i><span id="ail">${esc(txt)}</span></div>
      <small class="ainote">الرد التلقائي يرسل من ردودك وأسئلتك وقواعدك بس. الذكاء يكتب اقتراحات تراجعها وترسلها بنفسك، ومسودات التسويق وملف العميل.</small><small class="muted" id="aim">${a.ram_gb ? `ذاكرة الجهاز ${num(Math.round(a.ram_gb))} ج.ب` : ''}${a.avg_ms ? ` · الرد ياخذ تقريباً ${num((a.avg_ms / 1000).toFixed(1))} ث` : ''}</small></div>
      <label class="switch"><input type="checkbox" id="aim1" ${SET.aiModel !== 'off' ? 'checked' : ''} aria-label="تشغيل الذكاء المحلي"><span></span></label></div>
    ${TSECS.map(([k, t, h], i) => `<section class="tcard" id="ts-${k}"><header><span class="tn">${num(i + 1)}</span><div><h4>${t}</h4><p>${h}</p></div></header><div class="tbody" data-k="${k}"></div></section>`).join('')}
  </div><aside class="ttry"><div class="tcard"><header><span class="tn"><svg aria-hidden="true"><use href="#i-spark"/></svg></span><div><h4>جرّب</h4><p>اكتب رسالة كأنك عميل وشوف الرد المقترح. ما ينرسل شي.</p></div></header>
    <textarea id="tq" rows="3" aria-label="رسالة تجربة من عميل" placeholder="مثلاً: كم سعر بوكيه الجوري؟ وتوصلون العليا؟"></textarea>
    <div class="tqs">${['السلام عليكم عندكم توليب؟', 'كم سعر بوكيه الجوري؟', 'غالي مره', 'ابي ارجع الطلب'].map(x => `<button class="chip" data-q="${esc(x)}">${esc(x)}</button>`).join('')}</div>
    <button class="btn primary" id="tgo" style="width:100%;margin-top:10px">جرّب الرد</button><div id="ta" class="tans" aria-live="polite"></div></div></aside></div>`;
  for (const [k] of TSECS) drawSec(k);
  $('#aim1').onchange = async e => { SET = await api('api/settings', { aiModel: e.target.checked ? 'auto' : 'off' }); toast(e.target.checked ? 'شغّلنا الذكاء المحلي' : 'طفّينا الذكاء المحلي'); const [c, t] = aiLine(ST.ai); $('#ail').textContent = t; $('.aist .dot').className = 'dot ' + c };
  box.querySelectorAll('[data-q]').forEach(b => b.onclick = () => { $('#tq').value = b.dataset.q; tryIt() });
  $('#tgo').onclick = tryIt; $('#tq').onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); tryIt() } };
}
async function tryIt() {
  const text = $('#tq').value.trim(); if (!text) return $('#tq').focus(); const out = $('#ta'), b = $('#tgo');
  b.disabled = true; out.innerHTML = '<div class="tthink"><span></span><span></span><span></span> يفكر…</div>';
  try { const r = await api('api/teach/try', { text, teach: { ...TDEF, ...TEACH } });
    out.innerHTML = `<div class="m them tq1">${esc(text)}</div><div class="m me">${esc(r.reply)}</div>
      <div class="tmeta">${r.handoff ? '<span class="chip r">بيحوّلها لك</span>' : ''}<span class="chip">${r.engine === 'ai' ? 'الذكاء المحلي' : r.kind === 'faq' ? 'من أسئلتك' : 'الردود العادية'}</span><span class="muted">${num((r.ms / 1000).toFixed(1))} ث</span></div>`;
  } catch (e) { out.innerHTML = `<p class="err">${esc(e.message || 'ما ضبط')}</p>` } finally { b.disabled = false }
}
function drawSec(k) {
  const el = document.querySelector(`.tbody[data-k="${k}"]`); if (!el) return;
  const list = (key, ph) => { const L = TEACH[key] ??= [...(TDEF[key] || [])];
    el.innerHTML = `<div class="tlist">${L.map((x, i) => `<div class="trow"><input value="${esc(x)}" data-i="${i}" aria-label="${esc(ph)}"><button class="icon-btn" data-d="${i}" aria-label="احذف"><svg><use href="#i-x"/></svg></button></div>`).join('') || '<p class="muted">ما فيه شي، أضف أول وحدة.</p>'}</div>
      <div class="tadd"><input placeholder="${esc(ph)}" aria-label="${esc(ph)}"><button class="btn sm">+ أضف</button></div>`;
    el.querySelectorAll('[data-i]').forEach(e => e.oninput = () => { L[e.dataset.i] = e.value; teachSave() });
    el.querySelectorAll('[data-d]').forEach(e => e.onclick = () => { L.splice(e.dataset.d, 1); teachSave(); drawSec(k) });
    const inp = el.querySelector('.tadd input'), add = () => { if (!inp.value.trim()) return inp.focus(); L.push(inp.value.trim()); teachSave(); drawSec(k); el.querySelector('.tadd input').focus() };
    el.querySelector('.tadd button').onclick = add; inp.onkeydown = e => { if (e.key === 'Enter') add() } };
  const qa = (key, ql, al) => { const L = TEACH[key] ??= JSON.parse(JSON.stringify(TDEF[key] || []));
    el.innerHTML = `<div class="tqa">${L.map((x, i) => `<div class="tqrow"><label><span>${ql}</span><textarea rows="2" data-q="${i}">${esc(x.q)}</textarea></label><span class="arr" aria-hidden="true">←</span><label><span>${al}</span><textarea rows="2" data-a="${i}">${esc(x.a)}</textarea></label><button class="icon-btn" data-d="${i}" aria-label="احذف"><svg><use href="#i-x"/></svg></button></div>`).join('') || '<p class="muted">ما فيه شي للحين.</p>'}</div>
      <button class="btn sm tqadd">+ أضف ${key === 'faq' ? 'سؤال' : 'مثال'}</button>`;
    el.querySelectorAll('[data-q]').forEach(e => e.oninput = () => { L[e.dataset.q].q = e.value; teachSave() });
    el.querySelectorAll('[data-a]').forEach(e => e.oninput = () => { L[e.dataset.a].a = e.value; teachSave() });
    el.querySelectorAll('[data-d]').forEach(e => e.onclick = () => { L.splice(e.dataset.d, 1); teachSave(); drawSec(k) });
    el.querySelector('.tqadd').onclick = () => { L.push({ q: '', a: '' }); drawSec(k); el.querySelector(`[data-q="${L.length - 1}"]`).focus() } };
  if (k === 'persona') { el.innerHTML = `<label class="lbl" for="tp1">مين هو الموظف؟</label><textarea id="tp1" rows="2">${esc(tv('persona'))}</textarea>
      <label class="lbl" for="tp2">طريقة كلامه</label><textarea id="tp2" rows="2">${esc(tv('tone'))}</textarea>
      <div class="tqs">${['سعودي ودود ومختصر', 'رسمي ومحترم', 'شبابي وخفيف', 'فخم وراقي'].map(x => `<button class="chip" data-t="${x}">${x}</button>`).join('')}</div>`;
    $('#tp1').oninput = e => { TEACH.persona = e.target.value; teachSave() }; $('#tp2').oninput = e => { TEACH.tone = e.target.value; teachSave() };
    el.querySelectorAll('[data-t]').forEach(b => b.onclick = () => { $('#tp2').value = TEACH.tone = b.dataset.t + '، باللهجة السعودية، جمل قصيرة'; teachSave() }) }
  if (k === 'dos') list('dos', 'مثلاً: اسأل عن المناسبة');
  if (k === 'donts') list('donts', 'مثلاً: لا تعطي خصم');
  if (k === 'forbidden') list('forbidden', 'كلمة أو موضوع');
  if (k === 'handoff') list('handoff', 'مثلاً: شكوى، دفع، طلب شركات');
  if (k === 'faq') qa('faq', 'العميل يسأل', 'جوابك');
  if (k === 'examples') qa('examples', 'العميل يقول', 'الموظف يرد');
  if (k === 'shop') { el.innerHTML = `<label class="lbl" for="tsh1">عن المحل</label><textarea id="tsh1" rows="2" placeholder="وش تبيعون، وش يميزكم">${esc(SET.about || '')}</textarea>
      <label class="lbl" for="tsh2">التوصيل والدفع</label><textarea id="tsh2" rows="2" placeholder="مثلاً: نوصل داخل المدينة بـ ٣٠ ريال">${esc(SET.delivery || '')}</textarea>`;
    $('#tsh1').oninput = e => teachSave({ about: e.target.value }); $('#tsh2').oninput = e => teachSave({ delivery: e.target.value }) }
  if (k === 'prices') { const P = (SET.products || []).map(x => ({ ...x }));
    const draw = () => { el.innerHTML = `${P.length ? '' : '<div class="notice b">تستخدم الأسعار الافتراضية الحين. أضف أسعار محلك هنا.</div>'}<div class="tlist">${P.map((p, i) => `<div class="tprice"><input data-n="${i}" value="${esc(p.name)}" aria-label="اسم المنتج" placeholder="المنتج"><input data-p="${i}" type="number" min="0" value="${p.price || ''}" aria-label="السعر بالريال" placeholder="السعر"><span class="muted">ر.س</span><button class="icon-btn" data-d="${i}" aria-label="احذف"><svg><use href="#i-x"/></svg></button></div>`).join('')}</div><button class="btn sm" id="tpa">+ أضف منتج</button>`;
      const sv = () => teachSave({ products: P.filter(p => p.name.trim()) });
      el.querySelectorAll('[data-n]').forEach(e => e.oninput = () => { P[e.dataset.n].name = e.value; sv() }); el.querySelectorAll('[data-p]').forEach(e => e.oninput = () => { P[e.dataset.p].price = +e.value; sv() });
      el.querySelectorAll('[data-d]').forEach(e => e.onclick = () => { P.splice(e.dataset.d, 1); sv(); draw() }); $('#tpa').onclick = () => { P.push({ name: '', price: 0, aliases: [] }); draw(); el.querySelector(`[data-n="${P.length - 1}"]`).focus() } };
    draw() }
}
