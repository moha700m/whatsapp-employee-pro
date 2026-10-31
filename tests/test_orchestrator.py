import pytest
from app.core.parser import parse_chat
from app.ai.orchestrator import Orchestrator
from app.ai.providers import AIProvider, ChatGPTWebProvider
from app.core.kill_switch import KILL_SWITCH, KillSwitchEngaged
from app.core.service import EmployeeService
from app.automation.whatsapp_web import WhatsAppWebAgent, SendingDisabled

BIZ = [{"title": "باقة التصميم", "content": "شعار", "price": "500 ريال"}]

class Liar(AIProvider):
    name = "liar"
    def available(self): return True
    def complete(self, p): return "السعر 99 ريال بس!"

def test_pipeline():
    r = Orchestrator().run(parse_chat("أحمد: كم سعر باقة التصميم؟"), "أحمد", BIZ)
    assert r["classification"] == "Interested" and "500 ريال" in r["reply"] and r["follow_up"]

def test_quality_rejects_invented_price():
    r = Orchestrator(provider=Liar()).run(parse_chat("أحمد: بكم؟"), "أحمد", BIZ)
    assert "99" not in r["reply"] and r["provider"] == "heuristic" and r["quality_issues"]

def test_chatgpt_stub_unavailable():
    p = ChatGPTWebProvider(); assert not p.available()
    with pytest.raises(NotImplementedError): p.complete("x")
    assert Orchestrator(provider=p).run(parse_chat("س: هلا"), "س", [])["provider"] == "heuristic"

def test_kill_switch():
    KILL_SWITCH.engage()
    try:
        with pytest.raises(KillSwitchEngaged):
            Orchestrator().run(parse_chat("س: هلا"), "س", [])
    finally:
        KILL_SWITCH.release()

def test_service_persists(repo):
    svc = EmployeeService(repo); repo.add_business_info("منتج", "باقة التصميم", "شعار", "500 ريال")
    r = svc.analyze_text("ريم: ابي اكلم المدير، الطلب ما وصل")
    assert r["classification"] == "Complaint" and r["handoff"]
    assert repo.stats()["total"] == 1 and repo.stats()["replies"] == 1
    assert repo.db.scalar("SELECT COUNT(*) FROM activity_log WHERE action='analyze'") == 1
    with pytest.raises(ValueError): svc.analyze_text("   ")

def test_manual_send_path_blocked():
    with pytest.raises(SendingDisabled): WhatsAppWebAgent().send("x", "y")
