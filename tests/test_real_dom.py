"""Regression tests for bugs seen on the real WhatsApp Web (Arabic UI, emoji/LRM names, saved-name mismatch)."""
from pathlib import Path
import time, pytest
pw = pytest.importorskip("playwright.sync_api")
from app.automation.whatsapp_web import WhatsAppWebAgent, names_match, norm_name
from app.automation.base import ChatRef
from app.core.auto_reply import AutoReplyEngine
from app.core.settings import AutoReplySettings

def test_names_match():
    assert names_match("Sara Test 🌸", "Sara Test")
    assert names_match("\u200e+966 50 000 0123\u200e", "+966500000123")
    assert names_match("0500000123", "+966 50 000 0123")
    assert not names_match("Ahmed", "Sara") and not names_match("", "x")
    assert norm_name("\u202bأحمد\u202c 😊") == "أحمد"

@pytest.fixture
def page():
    try:
        p = pw.sync_playwright().start(); b = p.chromium.launch()
    except Exception as e:
        pytest.skip(f"no browser: {e}")
    pg = b.new_page(); pg.goto((Path(__file__).parent / "fixtures/fake_whatsapp_real.html").as_uri())
    yield pg
    b.close(); p.stop()

def test_replies_to_all_three_real_style_chats(page, repo):
    a = WhatsAppWebAgent(); a.page = page
    chats = a.list_unread_chats()
    assert [c.name.strip("\u200e") for c in chats] == ["Sara Test 🌸", "Customer 2", "+966 50 000 0123"]
    assert chats[0].last.startswith("السلام")
    repo.add_business_info("باقة", "الباقة", "x", "300 ريال")
    s = AutoReplySettings(send_mode="auto", auto_reply_enabled=True, min_delay=0, max_delay=0, typing_delay_ms=0, chat_cooldown=0)
    eng = AutoReplyEngine(repo, a, settings=s, sleep=lambda x: None)
    out = dict(eng.run_once())
    assert set(out.values()) <= {"replied", "rule_replied", "holding_sent"}, out
    assert len(page.evaluate("window.sent")) == 3
    assert len(eng.seen) == 3 and all(v["outcome_ar"] for v in eng.seen.values())
    texts = " ".join(e["text"] for e in eng.stats.last_events)
    assert "لقيت 3 محادثة" in texts and "قرأت" in texts and "رديت" in texts

def test_missing_rows_is_clear_error_not_nonetype(page):
    a = WhatsAppWebAgent(); a.page = page
    page.evaluate("document.getElementById('pane-side').remove()")
    assert a.list_unread_chats() == []
    import app.automation.whatsapp_web as w
    orig = w.retry; w.retry = lambda fn, tries=3, delay=1.0: fn()
    try:
        with pytest.raises(LookupError, match="chat_row"):
            a.open_chat(ChatRef("x", "x"))
    finally:
        w.retry = orig

def test_diagnose_report(page):
    a = WhatsAppWebAgent(); a.page = page
    rep = a.diagnose()
    assert "chat_row" in rep and "compose" in rep and "unread_badge" in rep and "outerHTML" not in rep

def test_runner_recovers_from_closed_browser(repo):
    from app.automation.runner import EmployeeRunner
    class Flaky:
        def __init__(self): self.page = object(); self.opens = 0; self.fail = True
        def open(self): self.opens += 1; self.page = object()
        def connection_state(self): return "connected"
        def is_ready(self): return True
        def list_unread_chats(self):
            if self.fail:
                self.fail = False
                raise RuntimeError("BrowserContext.new_page: Target page, context or browser has been closed")
            return []
    d = Flaky(); r = EmployeeRunner(repo, driver_factory=lambda: d)
    try:
        r.open_whatsapp()
        for _ in range(60):
            if d.opens: break
            time.sleep(0.25)
        assert d.opens >= 1
        assert any("أعيد فتحها" in e["text"] for e in r.snapshot()["events"])
    finally:
        r.shutdown()

def test_runner_diagnose_writes_file(repo, tmp_path, monkeypatch):
    from app import config
    from app.automation.runner import EmployeeRunner
    monkeypatch.setattr(config, "LOG_DIR", tmp_path)
    class D:
        page = object()
        def connection_state(self): return "connected"
        def is_ready(self): return True
        def list_unread_chats(self): return []
        def diagnose(self): return "chat_row 3 #pane-side"
    r = EmployeeRunner(repo, driver_factory=D)
    try:
        r.open_whatsapp(); r.diagnose()
        for _ in range(20):
            if (tmp_path / "selectors.txt").exists(): break
            time.sleep(0.2)
        assert "chat_row 3" in (tmp_path / "selectors.txt").read_text(encoding="utf-8-sig")
    finally:
        r.shutdown()

def test_log_file_is_utf8(tmp_path, monkeypatch):
    import logging
    from app import config
    from app.core import logger as L
    monkeypatch.setattr(config, "LOG_DIR", tmp_path); monkeypatch.setattr(L, "_logger", None)
    lg = logging.getLogger("wae"); old = lg.handlers[:]; lg.handlers.clear()
    try:
        L.log_activity(None, "test", "رديت على سارة")
        for h in lg.handlers: h.flush()
        raw = (tmp_path / "activity.log").read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf") and "رديت على سارة" in raw.decode("utf-8-sig")
    finally:
        for h in lg.handlers: h.close()
        lg.handlers[:] = old; monkeypatch.setattr(L, "_logger", None)
