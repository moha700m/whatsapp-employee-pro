"""Design QA: screenshots of every screen/state at 3 sizes + automated layout/text/contrast checks.
usage: python qa/shoot.py OUTDIR"""
import json, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent)); sys.path.insert(0, str(Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
from app.launcher import Engine
from app import e2e
import demo

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/workspace/wa-design/qa"); OUT.mkdir(parents=True, exist_ok=True)
SIZES = [("1280x800", 1280, 800, 1), ("1920x1080", 1920, 1080, 1), ("125pct", 1229, 691, 1.25)]
CHECK_JS = r"""() => {
 const issues = []; const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' };
 if (document.documentElement.scrollWidth > innerWidth + 1) issues.push('horizontal page overflow ' + document.documentElement.scrollWidth);
 const lum = c => { const m = c.match(/[\d.]+/g); if (!m) return null; const [r, g, b] = m.slice(0, 3).map(v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4 }); return { l: .2126 * r + .7152 * g + .0722 * b, a: m[3] === undefined ? 1 : +m[3] } };
 const bgOf = e => { while (e) { const c = getComputedStyle(e).backgroundColor; const L = lum(c); if (L && L.a > .9) return L.l; if (getComputedStyle(e).backgroundImage !== 'none' && e.classList.contains('skel')) return null; e = e.parentElement } return 1 };
 const seen = new Set();
 for (const e of document.querySelectorAll('body *')) {
  if (!vis(e) || e.closest('[hidden]') || e.closest('svg')) continue;
  const own = [...e.childNodes].filter(n => n.nodeType === 3 && n.textContent.trim()).map(n => n.textContent.trim()).join(' ');
  if (own) {
    const eng = own.match(/[A-Za-z]{3,}/g)?.filter(w => !['QR', 'VCF', 'CSV', 'Excel', 'PDF', 'Mohammed', 'alzhrani', 'Windows'].includes(w)); if (eng?.length) issues.push('english: ' + eng.join(',') + ' in "' + own.slice(0, 40) + '"');
    if (/lorem|undefined|NaN|null|\[object/i.test(own)) issues.push('placeholder text: ' + own.slice(0, 50));
    const fg = lum(getComputedStyle(e).color), bg = bgOf(e);
    if (fg && bg != null) { const ratio = (Math.max(fg.l, bg) + .05) / (Math.min(fg.l, bg) + .05); const fs = parseFloat(getComputedStyle(e).fontSize), bold = +getComputedStyle(e).fontWeight >= 700;
      const need = (fs >= 24 || (fs >= 18.66 && bold)) ? 3 : 4.5; if (ratio < need && !seen.has(own)) { seen.add(own); issues.push(`contrast ${ratio.toFixed(2)} < ${need}: "${own.slice(0, 30)}"`) } }
    const st = getComputedStyle(e); if (parseFloat(st.fontSize) < 12) issues.push('tiny text ' + st.fontSize + ': ' + own.slice(0, 30));
    if (e.scrollWidth > e.clientWidth + 2 && st.overflow !== 'visible' && st.textOverflow !== 'ellipsis' && !['TEXTAREA', 'INPUT', 'SELECT'].includes(e.tagName) && !/(auto|scroll)/.test(st.overflowX)) issues.push('clipped text: ' + own.slice(0, 40));
  }
  if ((e.tagName === 'BUTTON' || e.tagName === 'A') && !(e.textContent.trim() || e.getAttribute('aria-label') || e.title)) issues.push('button without name: ' + e.outerHTML.slice(0, 80));
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.tagName) && e.type !== 'hidden' && e.type !== 'file' && !(e.labels?.length || e.getAttribute('aria-label'))) issues.push('field without label: ' + (e.id || e.name || e.outerHTML.slice(0, 60)));
  if (e.tagName === 'BUTTON' && !e.closest('.filters,.sugs,.setnav,.tabs,.modal-act,.tour-card') ) { const r = e.getBoundingClientRect(); if (r.height < 32) issues.push(`small target ${Math.round(r.height)}px: ` + (e.textContent.trim() || e.getAttribute('aria-label')).slice(0, 30)) }
 }
 // overlapping siblings in topbar
 const tb = [...document.querySelectorAll('.topbar > *')].filter(vis).map(e => e.getBoundingClientRect());
 for (let i = 0; i < tb.length; i++) for (let j = i + 1; j < tb.length; j++) { const a = tb[i], b = tb[j]; if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) issues.push('topbar overlap') }
 return [...new Set(issues)];
}"""

def main():
    d = tempfile.mkdtemp(prefix="wae-qa-"); eng = Engine(d, fake=True); eng.start(); report = {}
    cl = e2e.Client(eng.url); cl.login()
    try:
        with sync_playwright() as p:
            br = p.chromium.launch()
            def page_for(w, h, dsf):
                ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=dsf, locale="ar-SA", timezone_id="Asia/Riyadh"); pg = ctx.new_page()
                errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and errs.append(m.text)); pg.errs = errs; return pg
            def shot(pg, name, tag):
                pg.wait_for_timeout(450); f = OUT / f"{tag}_{name}.png"; pg.screenshot(path=str(f))
                iss = pg.evaluate(CHECK_JS) + [f"js error: {x}" for x in pg.errs]; pg.errs.clear(); report[f.name] = iss; print(f.name, len(iss), iss[:6], flush=True)
            # --- first run: tour + link screen (before linking)
            pg = page_for(1280, 800, 1); pg.goto(eng.url); pg.wait_for_selector("#tour:not([hidden])")
            shot(pg, "00_tour_welcome", "1280x800"); pg.click("#tourNext"); shot(pg, "01_tour_link", "1280x800")
            for _ in range(4): pg.click("#tourNext")
            shot(pg, "02_tour_employee", "1280x800"); pg.click("#tourSkip"); pg.wait_for_selector(".qrbox img"); shot(pg, "03_link_qr", "1280x800")
            pg.context.close()
            cl.req("api/sim/link", {"me": "966500000000", "history": demo.history()})
            pg = page_for(1280, 800, 1); pg.goto(eng.url + "#home"); pg.wait_for_selector("#syncBar:not([hidden])", timeout=8000); shot(pg, "04_loading_history_sync", "1280x800"); pg.context.close()
            # seed some state: orders, tags, alerts, employee reply
            J = lambda k: f"9665000{k:05d}@s.whatsapp.net"
            cl.req("api/crm", {"jid": J(2), "data": {"tag": "تم التوصيل", "orders": [{"item": "بوكيه توليب", "amount": 220, "status": "تم التوصيل", "deliveryDate": "2026-10-30", "date": int(time.time() * 1000) - 2 * 86400_000}]}})
            cl.req("api/crm", {"jid": J(5), "data": {"tag": "طلب", "orders": [{"item": "صندوق ورد فاخر", "amount": 350, "status": "قيد التجهيز", "deliveryDate": "2026-11-02", "date": int(time.time() * 1000)}]}})
            cl.req("api/crm", {"jid": J(1), "data": {"tag": "مهتم"}}); cl.req("api/crm", {"jid": J(0), "data": {"tag": "مهتم"}})
            cl.req("api/ai/score-all", {}); cl.req("api/ai/briefing", {})
            cl.req("api/settings", {"shopName": "ورد الريحان", "city": "الرياض", "tourDone": True, "autoReply": {"enabled": True, "schedule": "always", "delaySec": 0}})
            import base64; MD = Path(__file__).resolve().parent.parent / "tests" / "media"
            for kind, fn, body in [("image", "rose.jpg", {"mimetype": "image/jpeg", "caption": "ابي بوكيه مثل هذا"}), ("audio", "voice.ogg", {"mimetype": "audio/ogg; codecs=opus", "seconds": 6, "ptt": True}),
                                   ("video", "video.mp4", {"mimetype": "video/mp4", "seconds": 3}), ("sticker", "sticker.webp", {"mimetype": "image/webp"}),
                                   ("document", "price-list.pdf", {"mimetype": "application/pdf", "fileName": "قائمة-المناسبة.pdf", "fileLength": 193})]:
                cl.req("api/sim/media", {"jid": J(3), "kind": kind, "body": {**body, "fakeData": base64.b64encode((MD / fn).read_bytes()).decode()}})
            cl.req("api/sim/incoming", {"jid": J(11), "text": "متى تفتحون اليوم؟", "name": "تركي"}); cl.req("api/sim/incoming", {"jid": J(9), "text": "ابي اطلب ستاند تهنئة", "name": "فيصل"})
            time.sleep(1.5); cl.req("api/settings", {"autoReply": {"enabled": False}})
            for theme, (tag0, w, h, dsf) in [(t, z) for t in ("light", "dark") for z in SIZES]:
                tag = f"{theme}_{tag0}"; cl.req("api/settings", {"theme": theme})
                pg = page_for(w, h, dsf); pg.goto(eng.url + "#home"); pg.wait_for_selector(".kpis"); pg.wait_for_timeout(400); shot(pg, "05_home", tag)
                pg.click("[data-p=chats]"); pg.wait_for_selector(".ci"); pg.click(f".ci[data-j='{J(0)}']"); pg.wait_for_selector(".m"); pg.wait_for_timeout(600); shot(pg, "06_chat_thread", tag)
                pg.click(f".ci[data-j='{J(11)}']"); pg.wait_for_selector(".m.auto"); shot(pg, "07_chat_auto_reply", tag)
                pg.click(f".ci[data-j='{J(0)}']"); pg.wait_for_timeout(500); pg.click("#ex"); pg.wait_for_selector("#exo .notice"); shot(pg, "08_chat_extract_order", tag)
                pg.fill("#tx", "أبشري، نوصله بكرة الساعة ٤ العصر 🌷"); pg.click("#sd"); pg.wait_for_selector("#modal:not([hidden])"); shot(pg, "09_send_confirm", tag); pg.click("#mNo")
                pg.select_option("#cfs", "resolved"); shot(pg, "10_chats_empty_filter", tag); pg.click("#cf [data-f=all]")
                pg.click("[data-p=sales]"); pg.wait_for_selector(".pipe"); shot(pg, "11_sales", tag)
                pg.click("[data-p=mkt]"); pg.wait_for_selector("#gen"); pg.click("#gen"); pg.wait_for_selector("#cmp pre"); shot(pg, "12_marketing", tag)
                pg.click("[data-p=emp]"); pg.wait_for_selector(".emp-hero"); shot(pg, "13_employee_off", tag)
                pg.click(".bigswitch input", force=True); pg.wait_for_selector("#modal:not([hidden])"); shot(pg, "14_employee_confirm", tag); pg.click("#mOk"); pg.wait_for_selector(".emp-hero.on"); shot(pg, "15_employee_on", tag)
                pg.fill("#et", "متى تفتحون؟"); pg.click("#etb"); pg.wait_for_selector("#eto .notice"); shot(pg, "16_employee_test", tag)
                pg.click(".bigswitch input", force=True); pg.wait_for_selector(".emp-hero:not(.on)")
                pg.click("[data-p=chats]"); pg.wait_for_selector(".ci"); pg.click("#cf [data-f=wait]"); pg.wait_for_timeout(300); shot(pg, "06b_chats_waiting_badges", tag); pg.click("#cf [data-f=all]")
                pg.click(".ci[data-j='966551230001@s.whatsapp.net']"); pg.wait_for_selector(".pf-r"); pg.wait_for_timeout(300); shot(pg, "06c_chat_profile_lid_resolved", tag)
                pg.click(".ci[data-j='63308489647951@lid']"); pg.wait_for_selector(".m"); pg.wait_for_timeout(300); shot(pg, "06d_chat_hidden_number", tag)
                pg.click(f".ci[data-j='{J(3)}']"); pg.wait_for_selector(".mau"); pg.wait_for_timeout(900); pg.eval_on_selector("#ms", "e => e.scrollTop = e.scrollHeight"); pg.wait_for_timeout(300); shot(pg, "06e_chat_media", tag)
                pg.click(".mspd"); pg.click(".mplay"); pg.wait_for_timeout(1200); shot(pg, "06f_voice_playing_1_5x", tag); pg.click(".mplay")
                pg.click(".mimg"); pg.wait_for_selector("#lightbox[open]"); pg.wait_for_timeout(300); shot(pg, "06g_image_lightbox", tag); pg.keyboard.press("Escape")
                for k in ["shop", "prices", "tpl", "brain", "rules", "brand", "sec", "log", "wa", "about"]:
                    pg.click("[data-p=set]"); pg.click(f".setnav [data-t={k}]"); pg.wait_for_timeout(250); shot(pg, f"17_settings_{k}", tag)
                pg.click("[data-p=set]"); pg.click(".setnav [data-t=wa]"); pg.click("#w1"); pg.wait_for_selector("#modal:not([hidden])"); shot(pg, "17z_disconnect_dialog", tag); pg.click("#mNo")
                pg.click("#bell"); pg.wait_for_selector("#alertsPop:not([hidden])"); shot(pg, "18_alerts", tag); pg.keyboard.press("Escape")
                pg.click("#help"); shot(pg, "19_help_menu", tag); pg.keyboard.press("Escape")
                pg.click("[data-p=home]"); pg.keyboard.press("Tab"); pg.keyboard.press("Tab"); pg.keyboard.press("Tab"); shot(pg, "20_focus_ring", tag)
                pg.context.close()
            # error state: engine stops while the app is open
            pg = page_for(1280, 800, 1); pg.goto(eng.url + "#home"); pg.wait_for_selector(".kpis"); eng.stop(); pg.click("[data-p=sales]"); pg.wait_for_timeout(6000); pg.errs.clear(); shot(pg, "21_error_engine_down", "1280x800")
            br.close()
    finally:
        try: eng.stop()
        except Exception: pass
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = {k: v for k, v in report.items() if v}; print("SCREENS", len(report), "WITH ISSUES", len(bad))
main()
