"""Renders installer/app art with Chromium (correct Arabic shaping) -> PNG/BMP/ICO. Run: python packaging/art/gen.py"""
import os, pathlib
from playwright.sync_api import sync_playwright
from PIL import Image
OUT = pathlib.Path(__file__).parent; ROOT = OUT.parent.parent
import base64
FONT = "data:font/ttf;base64," + base64.b64encode((ROOT / "app/web/static/fonts/Tajawal-Bold.ttf").read_bytes()).decode()
ICON = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="100%" height="100%">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1fb26b"/><stop offset="1" stop-color="#0e6f3f"/></linearGradient></defs>
<rect x="8" y="8" width="240" height="240" rx="56" fill="url(#g)"/>
<path d="M128 46c-48 0-86 35-86 80 0 16 5 31 14 44l-10 38 40-11c12 6 27 9 42 9 48 0 86-35 86-80s-38-80-86-80z" fill="#fff"/>
<g transform="translate(128 124)">
<circle r="15" fill="#f0a830"/>
<g fill="#e8547a"><ellipse rx="15" ry="24" transform="translate(0 -26)"/><ellipse rx="15" ry="24" transform="rotate(72) translate(0 -26)"/>
<ellipse rx="15" ry="24" transform="rotate(144) translate(0 -26)"/><ellipse rx="15" ry="24" transform="rotate(216) translate(0 -26)"/>
<ellipse rx="15" ry="24" transform="rotate(288) translate(0 -26)"/></g><circle r="13" fill="#f6c453"/></g></svg>'''
def side(w, h):
    s = w / 164
    return f'''<html><head><style>@font-face{{font-family:T;src:url({FONT})}}*{{margin:0;padding:0}}html{{width:{w}px;height:{h}px;background:#0b5a34;overflow:hidden}}::-webkit-scrollbar{{display:none}}body{{width:{w}px;height:{h}px;overflow:hidden;font-family:T;direction:rtl;
background:linear-gradient(170deg,#128a4f 0%,#0b5a34 100%);color:#fff;position:relative}}
.i{{position:absolute;top:{36*s}px;left:50%;transform:translateX(-50%);width:{92*s}px;height:{92*s}px;filter:drop-shadow(0 {6*s}px {12*s}px rgba(0,0,0,.25))}}
.t{{position:absolute;top:{146*s}px;width:100%;text-align:center;font-size:{21*s}px;line-height:1.25;white-space:nowrap}}
.s{{position:absolute;top:{186*s}px;width:100%;text-align:center;font-size:{12.5*s}px;opacity:.85;line-height:1.5}}
.p{{position:absolute;bottom:-{30*s}px;left:-{30*s}px;width:{130*s}px;height:{130*s}px;border-radius:50%;background:rgba(255,255,255,.07)}}
.v{{position:absolute;bottom:{12*s}px;width:100%;text-align:center;font-size:{10*s}px;opacity:.6}}</style></head>
<body><div class="p"></div><div class="i">{ICON}</div><div class="t">موظف واتساب</div><div class="s">يرتب طلبات محلك<br>ويجهز ردودك</div><div class="v">v2.2.1 · Mohammed alzhrani</div></body></html>'''
def small(w, h):
    return f'<html><body style="margin:0;width:{w}px;height:{h}px;background:#fff;display:grid;place-items:center"><div style="width:{int(w*.86)}px;height:{int(w*.86)}px">{ICON}</div></body></html>'
with sync_playwright() as p:
    b = p.chromium.launch()
    def shot(html, w, h, name):
        pg = b.new_page(viewport={"width": w, "height": h}); pg.set_content(html); pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(300)
        pg.screenshot(path=str(OUT / name)); pg.close()
    for i, (w, h) in enumerate([(164, 314), (192, 386), (246, 459), (273, 556), (328, 604), (410, 797)]):
        shot(side(w, h), w, h, f"side_{w}.png")
    for w, h in [(55, 58), (64, 68), (83, 80), (92, 97), (110, 106), (119, 123), (138, 140)]:
        shot(small(w, h), w, h, f"small_{w}.png")
    pg = b.new_page(viewport={"width": 256, "height": 256}); pg.set_content(f'<body style="margin:0;background:transparent">{ICON}</body>')
    pg.screenshot(path=str(OUT / "icon_256.png"), omit_background=True); b.close()
for f in OUT.glob("side_*.png"): Image.open(f).convert("RGB").save(f.with_suffix(".bmp"))
for f in OUT.glob("small_*.png"): Image.open(f).convert("RGB").save(f.with_suffix(".bmp"))
ico = Image.open(OUT / "icon_256.png").convert("RGBA")
ico.save(ROOT / "app/web/static/icon.ico", sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)])
ico.resize((128, 128), Image.LANCZOS).save(ROOT / "app/web/static/icon.png")
print("ok")
