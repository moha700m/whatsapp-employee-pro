"""Headless render of every page + workflow tab of the web UI; saves screenshots/ PNGs; fails on JS errors."""
from pathlib import Path
import pytest
pw = pytest.importorskip("playwright.sync_api")
from app.core.service import EmployeeService
from app.web.api import Api
from app.web.server import UIServer

SHOTS = Path(__file__).resolve().parent.parent / "screenshots"
PAGES = ["overview", "workflow", "inbox", "crm", "ai", "advisor", "pipeline", "campaigns", "followups", "analytics", "settings", "logs", "brain", "orders", "reports", "pro"]
TABS = ["general", "business", "rules", "templates", "prompt", "safety", "test", "io"]

def seed(svc):
    r = svc.repo
    r.add_business_info("باقة", "باقة التصميم", "شعار + هوية بصرية كاملة", "500 ريال")
    r.add_business_info("خدمة", "إدارة حسابات التواصل", "شهرياً، 12 منشور", "1200 ريال")
    for t in ["أحمد: السلام عليكم\nأحمد: كم سعر باقة التصميم؟", "نورة: ابي اطلب الحين كيف ادفع", "خالد: الطلب ما وصل وتأخر، سيء",
              "فهد: الجهاز ما يشتغل فيه عطل", "ريم: بفكر وبرجع لك", "سعد: طلبت قبل منكم، رقم الطلب 55"]:
        svc.analyze_text(t)
    r.add_campaign("عروض نهاية الشهر", "Interested", "خصم خاص لعملائنا")
    r.db.execute("INSERT INTO auto_replies(chat, reply, kind, classification, provider, sent_at) VALUES ('أحمد','هلا أحمد، باقة التصميم سعرها 500 ريال','auto','Interested','heuristic', strftime('%s','now'))")
    cid = r.db.scalar("SELECT id FROM customers WHERE name='أحمد'")
    r.db.execute("INSERT INTO drafts(chat, customer_id, incoming, reply, kind, classification, provider) VALUES ('أحمد', ?, 'السلام عليكم\nكم سعر باقة التصميم؟', 'هلا والله أحمد 🌷 باقة التصميم سعرها 500 ريال، تبيني أحجز لك؟', 'auto', 'Interested', 'heuristic')", (cid,))
    r.db.execute("INSERT INTO drafts(chat, incoming, reply, kind, classification, provider) VALUES ('خالد', 'الطلب ما وصل وتأخر، سيء', 'حقك علينا يا خالد، بيتواصل معك أحد من الفريق حالاً.', 'holding', 'Complaint', 'heuristic')")
    r.db.execute("INSERT INTO needs_attention(chat, reason, last_message) VALUES ('خالد','شكوى تحتاج تدخل موظف','الطلب ما وصل')")

@pytest.fixture
def ui(repo):
    svc = EmployeeService(repo); seed(svc)
    srv = UIServer(Api(svc)); url = srv.start()
    try:
        p = pw.sync_playwright().start(); b = p.chromium.launch()
    except Exception as e:
        srv.stop(); pytest.skip(f"no browser: {e}")
    yield b, url
    b.close(); p.stop(); srv.stop()

@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_page_renders(ui, theme):
    b, url = ui
    SHOTS.mkdir(exist_ok=True)
    pg = b.new_page(bypass_csp=True, viewport={"width": 1440, "height": 900}, locale="ar-SA")
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and errors.append(m.text))
    pg.add_init_script(f"localStorage.theme='{theme}'")
    pg.goto(url + "&nowizard#overview"); pg.wait_for_function("window.__ready === true", timeout=10000)
    for name in PAGES if theme == "light" else ["overview", "workflow", "ai"]:
        pg.evaluate(f"go('{name}')"); pg.wait_for_timeout(500)
        txt = pg.inner_text("#page")
        assert "تعذر" not in txt, f"{name}: {txt[:200]}"
        pg.screenshot(path=str(SHOTS / f"{theme}-{name}.png"), full_page=True)
    if theme == "light":
        pg.evaluate("go('workflow')"); pg.wait_for_timeout(400)
        for t in TABS:
            pg.click(f".tabs button[data-t='{t}']"); pg.wait_for_timeout(250)
            pg.screenshot(path=str(SHOTS / f"light-workflow-{t}.png"), full_page=True)
        # test box end-to-end through the UI
        pg.click(".tabs button[data-t='test']"); pg.fill("#tm", "كم سعر باقة التصميم؟"); pg.click("#go")
        pg.wait_for_selector("#tr .reply"); assert "500 ريال" in pg.inner_text("#tr .reply")
        pg.screenshot(path=str(SHOTS / "light-workflow-test-result.png"), full_page=True)
        # rules dialog
        pg.click(".tabs button[data-t='rules']"); pg.click("#ad"); pg.wait_for_selector("#rsv")
        pg.screenshot(path=str(SHOTS / "light-rule-dialog.png")); pg.click("#modalClose")
        # kill switch from the UI
        pg.click("#killBtn"); pg.wait_for_selector(".warnbar"); pg.screenshot(path=str(SHOTS / "light-kill-switch.png"))
        pg.click("#killBtn"); pg.wait_for_timeout(300)
        # status chips present
        assert "مو متصل" in pg.inner_text("#chipWa")
    assert not errors, errors


def test_approval_queue_ui(ui):
    b, url = ui
    pg = b.new_page(bypass_csp=True, viewport={"width": 1400, "height": 950}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url + "&nowizard#inbox"); pg.wait_for_selector(".qcard")
    assert pg.locator(".qcard").count() == 2 and pg.locator("nav .badge.q").inner_text() == "2"
    card = pg.locator(".qcard", has_text="أحمد")
    card.locator("textarea").fill("نص معدّل من محمد")
    pg.wait_for_timeout(1500)                          # polling must not wipe the edit
    assert card.locator("textarea").input_value() == "نص معدّل من محمد"
    card.locator("[data-a=regen]").click(); pg.wait_for_timeout(600)
    assert card.locator("textarea").input_value() not in ("", "نص معدّل من محمد")
    pg.screenshot(path=str(SHOTS / "light-approval-queue.png"), full_page=True)
    pg.locator(".qcard", has_text="خالد").locator("[data-a=ignore]").click()
    pg.wait_for_function("document.querySelectorAll('.qcard').length === 1")
    card.locator("[data-a=send]").click()               # no WhatsApp runner in this test -> clear error, nothing sent
    pg.wait_for_selector(".toast")
    pg.goto(url + "&nowizard#ai"); pg.wait_for_selector("#queue .qcard")
    pg.screenshot(path=str(SHOTS / "light-ai-with-queue.png"), full_page=True)
    assert not errs, errs

def test_xss_customer_text_is_escaped(ui, repo):
    b, url = ui
    evil = '<img src=x onerror="window.__pwned=1"><script>window.__pwned=2</script>'
    repo.db.execute("INSERT INTO customers(name, need, classification, last_contact) VALUES (?, ?, 'Hot Lead', '2020-01-01 00:00:00')", (evil, evil))
    repo.db.execute("INSERT INTO drafts(chat, incoming, reply, classification) VALUES (?, ?, ?, ?)", (evil, evil + "\nورد جوري", evil, evil))
    repo.db.execute("INSERT INTO needs_attention(chat, reason, last_message) VALUES (?, ?, ?)", (evil, evil, evil))
    pg = b.new_page(bypass_csp=True, viewport={"width": 1400, "height": 950}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: (errs.append("dialog"), d.dismiss()))
    for p in ["inbox", "ai", "crm", "advisor", "overview"]:
        pg.goto(url + "&nowizard#" + p); pg.wait_for_timeout(900)
        assert pg.evaluate("window.__pwned") is None, p
        assert pg.locator("#page img[src='x']").count() == 0 and pg.locator("#page script").count() == 0
    pg.goto(url + "&nowizard#inbox"); pg.wait_for_selector(".qcard")
    assert pg.evaluate("window.__pwned") is None and evil[:10] in pg.inner_text(".qcard >> nth=0") and not errs, errs

def test_advisor_page(ui):
    b, url = ui
    pg = b.new_page(bypass_csp=True, viewport={"width": 1400, "height": 1000}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url + "&nowizard#advisor"); pg.wait_for_selector(".occ-card")
    pg.fill("#askq", "اقترح عروض للمناسبة الجاية"); pg.click("#askb"); pg.wait_for_selector(".answer")
    assert "عروض" in pg.inner_text(".answer")
    if pg.locator("[data-fd]").count():
        pg.locator("[data-fd]").first.click(); pg.wait_for_selector("text=تنتظر موافقتك")
    pg.screenshot(path=str(SHOTS / "light-advisor.png"), full_page=True)
    assert not errs, errs


def test_simple_nav_and_home(ui):
    """Simple mode: 4 big main items, advanced pages hidden behind «متقدم», one primary action on home."""
    b, url = ui
    if True:
        pg = b.new_page(bypass_csp=True, viewport={"width": 1280, "height": 800}, locale="ar-SA")
        pg.goto(url + ("&" if "?" in url else "?") + "nowizard=1"); pg.wait_for_function("window.__ready === true", timeout=15000)
        pg.evaluate("localStorage.adv='0'; renderNav()")
        mains = pg.locator("#nav a.main").all_inner_texts()
        assert [m.split("\n")[0].strip() for m in mains] == ["الرئيسية", "المحادثات", "الطلبات", "الإعدادات"]
        assert pg.locator("#nav .adv a").count() == 0
        pg.click("#advT"); assert pg.locator("#nav .adv a").count() >= 10
        pg.evaluate("go('overview')"); pg.wait_for_selector("#heroBtn")
        pg.wait_for_selector("#splash", state="detached"); assert pg.locator(".btn.primary.xl").count() == 1
        assert "نسخة" in pg.inner_text("#ver")
        pg.screenshot(path=str(SHOTS / "simple-home.png")); pg.close()
