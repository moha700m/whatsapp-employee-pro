"""Approximate previews of the Inno Setup wizard pages (modern style, RTL) from the real art + texts. Not real screenshots."""
import base64, pathlib
from playwright.sync_api import sync_playwright
A = pathlib.Path(__file__).parent; ROOT = A.parent.parent
b64 = lambda f: "data:image/png;base64," + base64.b64encode((A / f).read_bytes()).decode()
FONT = "data:font/ttf;base64," + base64.b64encode((ROOT / "app/web/static/fonts/Tajawal-Regular.ttf").read_bytes()).decode()
CSS = f"""@font-face{{font-family:T;src:url({FONT})}}*{{margin:0;box-sizing:border-box}}html,body{{width:600px;height:460px;overflow:hidden}}
body{{font-family:T,Segoe UI;direction:rtl;background:#fff;font-size:13px;color:#111}}.win{{border:1px solid #bbb;height:460px;display:flex;flex-direction:column}}
.tb{{height:30px;background:#f3f3f3;border-bottom:1px solid #ddd;display:flex;align-items:center;padding:0 10px;font-size:12px}}
.main{{flex:1;display:flex}}.side{{width:164px}}.side img{{width:164px;height:314px;display:block}}.c{{flex:1;padding:22px}}h2{{font-size:17px;margin-bottom:14px}}
p{{line-height:1.7;margin-bottom:10px}}.ft{{height:48px;border-top:1px solid #ddd;background:#f3f3f3;display:flex;gap:8px;align-items:center;padding:0 12px;justify-content:flex-start}}
.b{{border:1px solid #999;background:#fff;padding:4px 16px;font-size:12px;border-radius:2px}}.b.d{{border-color:#0067c0;box-shadow:inset 0 0 0 1px #0067c0}}
.hd{{height:58px;border-bottom:1px solid #ddd;display:flex;justify-content:space-between;align-items:center;padding:0 16px}}.hd b{{display:block}}.hd span{{font-size:12px;color:#555}}
label{{display:block;margin:8px 0}}"""
def page(body, title="إعداد - موظف واتساب"):
    return f"<html><head><style>{CSS}</style></head><body><div class=win><div class=tb>{title}</div>{body}</div></body></html>"
W = page(f"""<div class=main><div class=side><img src="{b64('side_164.png')}"></div><div class=c><h2>هلا والله! خلنا نثبت «موظف واتساب»</h2>
<p>بنثبت «موظف واتساب» 2.1.0 على جهازك.</p><p>البرنامج يرتب محادثات واتساب وطلبات محلك، ويجهز لك الردود، وما يرسل شي بدون موافقتك.</p><p>يفضّل تقفل البرامج الثانية قبل ما نكمل.</p></div></div>
<div class=ft><span class="b d">التالي &gt;</span><span class=b>إلغاء</span></div>""")
T = page(f"""<div class=hd><div><b>اختيار المهام الإضافية</b><span>وش المهام الإضافية اللي تبيها؟</span></div><img src="{b64('small_55.png')}" width=55 height=58></div>
<div class=c><p>الاختصارات:</p><label>☑ حط اختصار على سطح المكتب</label></div><div style="flex:1"></div>
<div class=ft><span class="b d">التالي &gt;</span><span class=b>&lt; السابق</span><span class=b>إلغاء</span></div>""")
F = page(f"""<div class=main><div class=side><img src="{b64('side_164.png')}"></div><div class=c><h2>تمام، خلصنا التثبيت</h2>
<p>«موظف واتساب» صار جاهز على جهازك. تلقاه في قائمة ابدأ وعلى سطح المكتب.</p><label>☑ شغّل «موظف واتساب» الحين</label><p>اضغط «إنهاء» عشان تقفل المثبت.</p></div></div>
<div class=ft><span class="b d">إنهاء</span></div>""")
I = f"<html><body style='margin:0;background:#f6f7f4;display:flex;gap:24px;align-items:end;padding:24px'>" + "".join(
    f"<img src='{b64('icon_256.png')}' width={s} height={s}>" for s in (256, 128, 64, 48, 32, 16)) + "</body></html>"
with sync_playwright() as p:
    br = p.chromium.launch()
    for name, html, vp in [("welcome", W, (600, 460)), ("tasks", T, (600, 460)), ("finish", F, (600, 460)), ("icons", I, (640, 310))]:
        pg = br.new_page(viewport={"width": vp[0], "height": vp[1]}, device_scale_factor=2); pg.set_content(html); pg.wait_for_timeout(400)
        pg.screenshot(path=str(ROOT / "screenshots" / f"installer-{name}.png")); pg.close()
    br.close()
