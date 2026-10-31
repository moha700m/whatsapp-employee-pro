"""Runs the real Playwright WhatsApp driver against a local mock page (not real WhatsApp)."""
from pathlib import Path
import pytest
pw = pytest.importorskip("playwright.sync_api")
from app.automation.whatsapp_web import WhatsAppWebAgent

def test_driver_on_mock_page():
    try:
        p = pw.sync_playwright().start(); b = p.chromium.launch()
    except Exception as e:
        pytest.skip(f"no browser: {e}")
    try:
        page = b.new_page(); page.goto((Path(__file__).parent / "fixtures/fake_whatsapp.html").as_uri())
        a = WhatsAppWebAgent(); a.page = page
        assert a.is_ready()
        chats = a.list_unread_chats()
        assert [(c.name, c.is_group, c.unread) for c in chats] == [("أحمد", False, 2), ("قروب", True, 1)]
        a.open_chat(chats[0])
        msgs = a.read_messages()
        assert [m.text for m in msgs] == ["هلا", "كم السعر؟"] and all(m.incoming for m in msgs)
        assert msgs[0].msg_id == "false_1@c.us_A1" and msgs[0].sender == "أحمد"
        a.send_text("هلا والله\nحياك", typing_delay_ms=1)
        assert page.evaluate("window.lastSent").replace("\r", "") == "هلا والله\nحياك"
    finally:
        b.close(); p.stop()
