"""Approval mode (default): nothing is sent without an explicit click."""
import pytest
from app.core.auto_reply import AutoReplyEngine
from app.core.settings import AutoReplySettings
from app.core.kill_switch import KILL_SWITCH, KillSwitchEngaged
from app.core.service import EmployeeService
from app.web.api import Api, ApiError
from tests.test_auto_reply import FakeDriver, Clock

@pytest.fixture
def env(repo):
    s = AutoReplySettings(auto_reply_enabled=True, min_delay=0, max_delay=0)
    assert s.send_mode == "approval"
    d = FakeDriver(); eng = AutoReplyEngine(repo, d, settings=s, clock=Clock(), sleep=lambda x: None)
    repo.add_business_info("باقة", "باقة ورد جوري", "x", "250 ريال")
    return eng, d, repo

def pending(repo):
    return repo.db.query("SELECT * FROM drafts WHERE status='pending'")

def test_default_mode_is_approval_and_migration_forces_it(repo):
    assert repo.get_setting("ar.send_mode") == "approval" and AutoReplySettings.load(repo).send_mode == "approval"

def test_no_send_without_approval(env):
    eng, d, repo = env
    d.add("أحمد", ["كم سعر باقة ورد جوري؟"])
    assert eng.run_once() == [("أحمد", "drafted")]
    assert d.sent == [] and len(pending(repo)) == 1 and "250 ريال" in pending(repo)[0]["reply"]
    assert all(r != "drafted" for _, r in eng.run_once())   # same message: deduped, not re-drafted
    d.add("أحمد", ["وتوصلون؟"]); d.chats["أحمد"][0].unread = 1
    eng.run_once()
    p = pending(repo); assert len(p) == 1 and "وتوصلون" in p[0]["incoming"]   # merged into one card
    assert d.sent == []

def test_approve_sends_edited_text_once(env):
    eng, d, repo = env
    d.add("أحمد", ["هلا"]); eng.run_once()
    did = pending(repo)[0]["id"]
    eng.send_draft(did, "هلا والله يا أحمد، كيف أخدمك؟")
    assert d.sent == [("أحمد", "هلا والله يا أحمد، كيف أخدمك؟")]
    assert repo.db.scalar("SELECT status FROM drafts WHERE id=?", (did,)) == "sent"
    assert repo.db.scalar("SELECT kind FROM auto_replies") == "approved"
    with pytest.raises(ValueError): eng.send_draft(did, "again")
    assert len(d.sent) == 1

def test_holding_and_optout_are_drafts(env):
    eng, d, repo = env
    d.add("ريم", ["الطلب ما وصل وتأخر، سيء"])
    assert eng.run_once() == [("ريم", "holding_drafted")]
    assert d.sent == [] and pending(repo)[0]["kind"] == "holding"
    assert repo.db.scalar("SELECT COUNT(*) FROM needs_attention WHERE status='open'") == 1
    d.add("فهد", ["لا ترسل لي"]); eng.run_once()
    assert d.sent == []
    cid = repo.db.scalar("SELECT id FROM customers WHERE name='فهد'")
    repo.db.execute("INSERT INTO drafts(chat, customer_id, reply) VALUES ('فهد', ?, 'x')", (cid,))
    did = repo.db.scalar("SELECT id FROM drafts WHERE chat='فهد'")
    with pytest.raises(PermissionError): eng.send_draft(did, "عرض خاص")       # opted-out customers can't be messaged
    assert d.sent == [] and repo.db.scalar("SELECT status FROM drafts WHERE id=?", (did,)) == "pending"

def test_kill_switch_blocks_approved_send(env):
    eng, d, repo = env
    d.add("أحمد", ["هلا"]); eng.run_once(); did = pending(repo)[0]["id"]
    KILL_SWITCH.engage()
    try:
        with pytest.raises(KillSwitchEngaged): eng.send_draft(did, "هلا")
    finally: KILL_SWITCH.release()
    assert d.sent == []

def test_api_ignore_regenerate_and_send(env):
    eng, d, repo = env
    d.add("سارة", ["السلام عليكم"]); d.add("نوف", ["كم سعر باقة ورد جوري؟"]); eng.run_once()
    class R:      # stands in for the runner thread
        engine = eng; status = ""
        def snapshot(self): return {"chats": []}
        def send_draft(self, i, t): return eng.send_draft(i, t)
    api = Api(EmployeeService(repo), R())
    ds = api.call("drafts"); assert len(ds) == 2 and ds[0]["score"]["band_ar"]
    nouf = next(x for x in ds if x["chat"] == "نوف"); sara = next(x for x in ds if x["chat"] == "سارة")
    old = sara["reply"]; new = api.call("draft_regenerate", {"id": sara["id"]})["reply"]
    assert new and new != old
    api.call("draft_ignore", {"id": sara["id"]})
    with pytest.raises(ApiError): api.call("draft_send", {"id": nouf["id"], "text": "  "})
    api.call("draft_send", {"id": nouf["id"], "text": "أبشري، باقة ورد جوري بـ 250 ريال 🌹"})
    assert d.sent == [("نوف", "أبشري، باقة ورد جوري بـ 250 ريال 🌹")]
    assert api.call("drafts") == [] and api.call("status")["pending"] == 0
    with pytest.raises(ApiError): api.call("draft_send", {"id": sara["id"], "text": "x"})   # ignored -> never sent
    assert len(d.sent) == 1

def test_runner_send_draft_runs_in_worker_thread(repo):
    import time
    from app.automation.runner import EmployeeRunner
    AutoReplySettings(auto_reply_enabled=True, min_delay=0, max_delay=0, poll_interval=0.1).save(repo)
    d = FakeDriver(); d.connection_state = lambda: "connected"; d.page = object()
    d.add("أحمد", ["هلا"])
    r = EmployeeRunner(repo, driver_factory=lambda: d); r.start()
    try:
        for _ in range(50):
            if repo.db.scalar("SELECT COUNT(*) FROM drafts"): break
            time.sleep(0.1)
        assert d.sent == []
        did = repo.db.scalar("SELECT id FROM drafts")
        assert r.send_draft(did, "هلا فيك") is True and d.sent == [("أحمد", "هلا فيك")]
    finally:
        r.stop(); r.shutdown()

def test_lead_score():
    from app.core.lead_score import score
    assert score("Hot Lead", 5, 2, None)["band"] == "Hot"
    assert score("New Lead", 1, 1, "2020-01-01 00:00:00")["band"] == "Cold"
