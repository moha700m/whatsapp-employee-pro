"""UI end-to-end: open the connect modal -> QR shown inside the app -> auto success when connected.
Also renders the first-run wizard. Saves screenshots/connect-*.png and wizard-*.png."""
import time
from pathlib import Path
import pytest
pw = pytest.importorskip("playwright.sync_api")
from app.automation.runner import EmployeeRunner
from app.core.service import EmployeeService
from app.web.api import Api
from app.web.server import UIServer
from tests.test_connection import mock_factory

SHOTS = Path(__file__).resolve().parent.parent / "screenshots"

@pytest.fixture
def browser():
    try:
        p = pw.sync_playwright().start(); b = p.chromium.launch()
    except Exception as e:
        pytest.skip(f"no browser: {e}")
    yield b
    b.close(); p.stop()

def test_connect_modal_qr_to_connected(repo, browser):
    SHOTS.mkdir(exist_ok=True)
    runner = EmployeeRunner(repo, driver_factory=mock_factory({}, 9000))
    srv = UIServer(Api(EmployeeService(repo), runner)); url = srv.start()
    try:
        pg = browser.new_page(bypass_csp=True, viewport={"width": 1440, "height": 900}, locale="ar-SA")
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(url + "&nowizard#ai"); pg.wait_for_function("window.__ready === true")
        pg.click("#openWa")
        pg.wait_for_selector("#connHost .qr-frame img", timeout=15000)
        assert "امسح الرمز" in pg.inner_text("#connHost") and "الأجهزة المرتبطة" in pg.inner_text("#connHost")
        pg.wait_for_timeout(600); pg.screenshot(path=str(SHOTS / "connect-qr.png"))
        src1 = pg.get_attribute("#connHost .qr-frame img", "src")
        pg.wait_for_function(f"document.querySelector('#connHost .qr-frame img') && document.querySelector('#connHost .qr-frame img').src !== {src1!r}", timeout=10000)
        pg.wait_for_selector("#connHost .conn.ok", timeout=20000)
        assert "تم الربط ✅" in pg.inner_text("#connHost") and "متجر ليان" in pg.inner_text("#connHost")
        pg.wait_for_timeout(400); pg.screenshot(path=str(SHOTS / "connect-connected.png"))
        pg.wait_for_selector("#modal.hidden", state="attached", timeout=6000)   # auto-closes
        assert "متصل" in pg.inner_text("#chipWa")
        pg.wait_for_timeout(500); pg.screenshot(path=str(SHOTS / "ai-page-connected.png"), full_page=True)
        assert not errs, errs
    finally:
        srv.stop(); runner.shutdown()

def test_wizard_and_missing_deps(repo, browser, monkeypatch):
    from app.core import deps
    srv = UIServer(Api(EmployeeService(repo))); url = srv.start()
    try:
        pg = browser.new_page(bypass_csp=True, viewport={"width": 1440, "height": 900}, locale="ar-SA")
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(url + "#overview"); pg.wait_for_selector(".wz-steps")
        pg.wait_for_timeout(400); pg.screenshot(path=str(SHOTS / "wizard-1-connect.png"))
        pg.click("#wzNext"); pg.wait_for_selector("#wn")
        pg.fill("#wn", "متجر ليان للورد"); pg.fill("#wd", "باقات ورد وتنسيقات للمناسبات"); pg.fill("#pt", "باقة ورد جوري"); pg.fill("#pp", "250 ريال")
        pg.screenshot(path=str(SHOTS / "wizard-2-business.png"))
        pg.click("#wzNext"); pg.wait_for_selector("#wr .reply")
        pg.fill("#wm", "كم سعر باقة ورد جوري؟"); pg.click("#wt"); pg.wait_for_function("document.querySelector('#wr .reply').innerText.includes('250')")
        pg.screenshot(path=str(SHOTS / "wizard-3-try.png"))
        pg.click("#wzNext"); pg.wait_for_selector(".final"); pg.screenshot(path=str(SHOTS / "wizard-4-start.png"))
        pg.click("#wzNext"); pg.wait_for_selector("#modal.hidden", state="attached")
        assert repo.get_setting("onboarding_done") == "1"
        assert [b["title"] for b in repo.business_info()] == ["باقة ورد جوري"]
        # missing playwright -> Arabic banner with auto-fix button
        monkeypatch.setattr(deps, "missing", lambda: ["playwright"])
        pg.wait_for_selector("#fixBtn", timeout=5000)
        assert "ناقصة" in pg.inner_text(".depbar")
        pg.screenshot(path=str(SHOTS / "missing-deps-banner.png"))
        assert not errs, errs
    finally:
        srv.stop()
