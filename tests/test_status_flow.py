"""Real Playwright driver against a mock WhatsApp page: disconnected -> QR -> connected -> unread -> reply."""
from pathlib import Path
import pytest
pw = pytest.importorskip("playwright.sync_api")
from app.automation.whatsapp_web import WhatsAppWebAgent
from app.core.auto_reply import AutoReplyEngine
from app.core.settings import AutoReplySettings

@pytest.fixture
def page():
    try:
        p = pw.sync_playwright().start(); b = p.chromium.launch()
    except Exception as e:
        pytest.skip(f"no browser: {e}")
    pg = b.new_page(); pg.goto((Path(__file__).parent / "fixtures/fake_whatsapp_flow.html").as_uri())
    yield pg
    b.close(); p.stop()

def test_full_flow(page, repo):
    a = WhatsAppWebAgent()
    assert a.connection_state() == "disconnected"
    a.page = page
    assert a.connection_state() == "qr"
    assert a.list_unread_chats() == []
    page.evaluate("login()")
    assert a.connection_state() == "connected"
    repo.add_business_info("منتج", "باقة التصميم", "شعار", "500 ريال")
    s = AutoReplySettings(send_mode="auto", auto_reply_enabled=True, min_delay=0, max_delay=0, typing_delay_ms=1)
    eng = AutoReplyEngine(repo, a, settings=s, sleep=lambda x: None)
    assert eng.run_once() == [("أحمد", "replied")]
    sent = page.evaluate("window.lastSent")
    assert "500 ريال" in sent
    assert eng.run_once() == []                      # badge gone -> nothing to do
    texts = [e["text"] for e in eng.stats.last_events]
    assert any(t.startswith("قرأت") for t in texts) and any(t.startswith("رديت") for t in texts)
    c = repo.customers()[0]; assert c["name"] == "أحمد" and c["classification"] == "Interested"

def test_closed_page_is_disconnected(page):
    a = WhatsAppWebAgent(); a.page = page; page.close()
    assert a.connection_state() == "disconnected"
