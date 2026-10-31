"""Engine-level: media flagged (never answered), after-hours only safe intents, approval drafts + order card."""
from app.automation.base import ChatRef, ChatMessage
from app.core.auto_reply import AutoReplyEngine
from app.core.settings import AutoReplySettings
from app.core import workflow as wfm
from tests.test_auto_reply import FakeDriver

def _eng(repo, **kw):
    s = AutoReplySettings(auto_reply_enabled=True, min_delay=0, max_delay=0, **kw)
    d = FakeDriver(); return AutoReplyEngine(repo, d, settings=s, sleep=lambda x: None), d

def test_voice_note_flagged_not_answered(repo):
    eng, d = _eng(repo)
    d.chats["ريم"] = (ChatRef("ريم", "ريم", False, 1), [ChatMessage("false_1", "ريم", "[رسالة صوتية]", True, "", "voice")])
    assert eng.process_chat(d.chats["ريم"][0]) == "media_flagged" and d.sent == []
    assert repo.db.scalar("SELECT COUNT(*) FROM needs_attention WHERE chat='ريم'") == 1

def test_after_hours_only_safe_intents(repo, monkeypatch):
    monkeypatch.setattr(wfm, "in_working_hours", lambda wf: False)
    eng, d = _eng(repo, after_hours_auto=True)
    d.add("فهد", ["السلام عليكم"])
    assert eng.process_chat(d.chats["فهد"][0]) == "after_hours_auto" and len(d.sent) == 1
    d.add("سلمان", ["ابي اطلب بوكيه جوري بكره"])
    assert eng.process_chat(d.chats["سلمان"][0]) != "after_hours_auto"
    assert all(c != "سلمان" for c, _ in d.sent)

def test_approval_mode_drafts_and_fills_order(repo):
    eng, d = _eng(repo)
    d.add("نوف", ["ابي اطلب بوكيه توليب بكره حي النرجس الرياض"])
    eng.process_chat(d.chats["نوف"][0])
    assert d.sent == [] and repo.db.scalar("SELECT COUNT(*) FROM drafts WHERE chat='نوف'") == 1
    o = repo.db.query("SELECT * FROM orders")[0]
    assert o["item"] == "بوكيه توليب" and o["city"] == "الرياض" and o["district"] == "النرجس"
