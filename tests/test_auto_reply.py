import pytest
from app.automation.base import ChatRef, ChatMessage
from app.core.auto_reply import AutoReplyEngine
from app.core.settings import AutoReplySettings
from app.core.kill_switch import KILL_SWITCH, KillSwitchEngaged

class FakeDriver:
    def __init__(self):
        self.chats = {}      # key -> (ChatRef, [ChatMessage])
        self.sent = []       # (chat, text)
        self.current = None
    def add(self, name, texts, group=False, prefix=None):
        ref, msgs = self.chats.get(name, (ChatRef(name, name, group, 1), []))
        for t in texts:
            msgs.append(ChatMessage(f"false_{name}_{len(msgs)}", name, t, True))
        self.chats[name] = (ref, msgs)
    def is_ready(self): return True
    def list_unread_chats(self):
        return [ref for ref, msgs in self.chats.values() if msgs and msgs[-1].incoming]
    def open_chat(self, chat): self.current = chat.key
    def read_messages(self, limit=20): return self.chats[self.current][1][-limit:]
    def chat_phone(self): return ""
    def send_text(self, text, typing_delay_ms=60):
        self.sent.append((self.current, text))
        self.chats[self.current][1].append(ChatMessage(f"true_{len(self.sent)}", "me", text, False))

class Clock:
    def __init__(self): self.t = 1_000_000.0
    def __call__(self): return self.t

@pytest.fixture
def setup(repo):
    s = AutoReplySettings(send_mode="auto", auto_reply_enabled=True, min_delay=0, max_delay=0, chat_cooldown=60,
                          max_per_chat_hour=3, global_hour_cap=5)
    d, clk, sleeps = FakeDriver(), Clock(), []
    eng = AutoReplyEngine(repo, d, settings=s, clock=clk, sleep=sleeps.append)
    repo.add_business_info("منتج", "باقة التصميم", "شعار", "500 ريال")
    return eng, d, clk, sleeps, repo

def test_disabled_by_default(repo):
    assert AutoReplySettings.load(repo).auto_reply_enabled is False
    d = FakeDriver(); d.add("أحمد", ["هلا"])
    eng = AutoReplyEngine(repo, d, sleep=lambda s: None)
    eng.run_once(); assert d.sent == []

def test_settings_roundtrip(repo):
    s = AutoReplySettings(send_mode="auto", auto_reply_enabled=True, min_delay=3, skip_groups=False); s.save(repo)
    l = AutoReplySettings.load(repo); assert l.auto_reply_enabled and l.min_delay == 3 and not l.skip_groups

def test_replies_and_updates_crm(setup):
    eng, d, clk, sleeps, repo = setup
    d.add("أحمد", ["هلا", "كم سعر باقة التصميم؟"])
    assert eng.run_once() == [("أحمد", "replied")]
    assert "500 ريال" in d.sent[0][1]
    c = repo.customers()[0]; assert c["name"] == "أحمد" and c["classification"] == "Interested" and c["last_contact"]
    assert repo.db.scalar("SELECT COUNT(*) FROM activity_log WHERE details LIKE 'رديت على%'") == 1
    assert sleeps and sleeps[0] == 0  # human delay applied (0 in test)

def test_dedupe(setup):
    eng, d, clk, *_ = setup
    d.add("أحمد", ["هلا"]); eng.run_once()
    # same message visible again (e.g. driver re-reports chat) -> no second reply
    d.chats["أحمد"][1].pop()  # remove our reply so the incoming is last again
    clk.t += 10_000; eng.run_once()
    assert len(d.sent) == 1

def test_cooldown_and_chat_cap(setup):
    eng, d, clk, *_ = setup
    d.add("سارة", ["هلا"]); eng.run_once()
    d.add("سارة", ["وش عندكم؟"]); assert eng.run_once() == [("سارة", "cooldown")]
    clk.t += 61; assert eng.run_once() == [("سارة", "replied")]
    clk.t += 61; d.add("سارة", ["طيب"]); eng.run_once()
    clk.t += 61; d.add("سارة", ["ممكن تفاصيل"]); assert eng.run_once() == [("سارة", "chat_hour_cap")]
    assert len(d.sent) == 3

def test_global_cap(setup):
    eng, d, clk, *_ = setup
    for i in range(7): d.add(f"عميل{i}", ["هلا"])
    eng.run_once()
    assert len(d.sent) == 5

def test_kill_switch_stops(setup):
    eng, d, *_ = setup
    d.add("أحمد", ["هلا"]); KILL_SWITCH.engage()
    try:
        with pytest.raises(KillSwitchEngaged): eng.run_once()
    finally: KILL_SWITCH.release()
    assert d.sent == []

def test_kill_switch_during_delay(setup):
    eng, d, *_ = setup
    def sleep(_): KILL_SWITCH.engage()
    eng._sleep = sleep; d.add("أحمد", ["هلا"])
    try:
        with pytest.raises(KillSwitchEngaged): eng.run_once()
    finally: KILL_SWITCH.release()
    assert d.sent == []

def test_opt_out(setup):
    eng, d, clk, _, repo = setup
    d.add("فهد", ["لا ترسل لي رسائل"])
    assert eng.run_once() == [("فهد", "opted_out_now")] and d.sent == []
    clk.t += 10_000; d.add("فهد", ["هلا"])
    assert eng.run_once() == [("فهد", "opted_out")] and d.sent == []
    assert repo.db.scalar("SELECT COUNT(*) FROM needs_attention") == 1

def test_handoff_holding_once(setup):
    eng, d, clk, _, repo = setup
    d.add("ريم", ["الطلب ما وصل وتأخر، سيء"])
    assert eng.run_once() == [("ريم", "holding_sent")]
    assert d.sent[0][1] == eng.wf['templates']['holding']
    clk.t += 10_000; d.add("ريم", ["ابي اكلم المدير"])
    assert eng.run_once() == [("ريم", "flagged_only")]
    assert len(d.sent) == 1
    assert repo.db.scalar("SELECT COUNT(*) FROM needs_attention WHERE status='open'") == 1

def test_missing_price_holding(setup):
    eng, d, *_ = setup
    d.add("خالد", ["بكم الاشتراك الشهري؟"])
    assert eng.run_once() == [("خالد", "holding_sent")]

def test_greeting_not_price(setup):
    eng, d, *_ = setup
    d.add("نوف", ["السلام عليكم"])
    assert eng.run_once() == [("نوف", "replied")]

def test_groups_skipped(setup):
    eng, d, *_ = setup
    d.add("قروب العائلة", ["هلا"], group=True)
    assert eng.run_once() == [("قروب العائلة", "group_skipped")] and d.sent == []
    eng.settings.skip_groups = False
    assert eng.run_once() == [("قروب العائلة", "replied")]

def test_driver_error_isolated(setup):
    eng, d, *_ = setup
    d.add("أ", ["هلا"]); d.add("ب", ["هلا"])
    orig = d.open_chat
    def bad(c):
        if c.key == "أ": raise RuntimeError("selector broke")
        orig(c)
    d.open_chat = bad
    assert dict(eng.run_once()) == {"أ": "error", "ب": "replied"}

def test_chatgpt_provider_fallback(setup):
    from app.ai.orchestrator import Orchestrator
    from app.ai.providers import ChatGPTWebProvider
    class Br:
        def is_ready(self): return True
        def ask_chatgpt(self, p): raise TimeoutError
    eng, d, *_ = setup
    eng.orch = Orchestrator(provider=ChatGPTWebProvider(Br()))
    d.add("أحمد", ["هلا"]); assert eng.run_once() == [("أحمد", "replied")]
    assert eng.repo.db.scalar("SELECT provider FROM auto_replies") == "heuristic"

def test_chatgpt_provider_used_when_clean(setup):
    from app.ai.orchestrator import Orchestrator
    from app.ai.providers import ChatGPTWebProvider
    class Br:
        def is_ready(self): return True
        def ask_chatgpt(self, p):
            assert "باقة التصميم" in p; return "هلا والله، باقة التصميم بـ 500 ريال"
    eng, d, *_ = setup
    eng.orch = Orchestrator(provider=ChatGPTWebProvider(Br()))
    d.add("أحمد", ["هلا"]); eng.run_once()
    assert d.sent[0][1].startswith("هلا والله")

def test_runner_with_fake_driver(repo):
    import time
    from app.automation.runner import EmployeeRunner
    AutoReplySettings(send_mode="auto", auto_reply_enabled=True, min_delay=0, max_delay=0, poll_interval=0.1).save(repo)
    d = FakeDriver(); d.add("أحمد", ["هلا"])
    r = EmployeeRunner(repo, driver_factory=lambda: d); r.start()
    for _ in range(50):
        if d.sent: break
        time.sleep(0.1)
    r.stop(); r.shutdown()
    assert len(d.sent) == 1
