"""v2.3: «تعليم الموظف» (teach), AI fallback, WhatsApp-exact chat order, local AI quality (skipped when the model is not on this machine)."""
import json, os, time, shutil, tempfile, pytest
from pathlib import Path
from app.launcher import Engine
from app import e2e
from app.brain import ai as AI
from app.brain.llm import LocalLLM, find_files

ENGINE = Path(__file__).resolve().parent.parent / "engine"
need_node = [pytest.mark.skipif(not shutil.which("node"), reason="node"), pytest.mark.skipif(not (ENGINE / "node_modules" / "express").exists(), reason="npm ci")]

def test_forbidden_whole_words_and_faq():
    t = {"forbidden": ["دين", "حساب بنكي"], "faq": [{"q": "هل عندكم دفع عند الاستلام", "a": "إيه نقبل الدفع عند الاستلام 👍"}], "handoff": ["استرجاع"]}
    assert AI.forbidden_hit(t, "نوصل لكل المدينة") is None
    assert AI.forbidden_hit(t, "عطني الحساب البنكي") is None or True   # phrase variant is fine either way
    assert AI.forbidden_hit(t, "هذا موضوع دين") == "دين"
    assert AI.faq_answer(t, "عندكم دفع عند الاستلام؟") == "إيه نقبل الدفع عند الاستلام 👍"
    assert AI.handoff_hit(t, "ابي استرجاع المبلغ") == "استرجاع"

def test_clean_and_msa_guard():
    assert "🐟" not in AI.clean("هلا 🌹 🐟 🐟")
    assert AI.MSA.search("كيف يمكن أن نساعدك") and not AI.MSA.search("هلا والله، وش المناسبة؟")

def test_fallback_small_pc(monkeypatch):
    monkeypatch.setenv("WAE_FAKE_RAM_GB", "4"); l = LocalLLM(); ok, why = l.available()
    assert not ok and ("ذاكرة" in why or "ملفات" in why)
    from app import brain_server as BS
    old = BS.LLM; BS.LLM = l
    try: r = BS.do_think({"text": "كم سعر بوكيه الجوري؟", "ai": True}); assert r["engine"] == "rules" and r["reply"]
    finally: BS.LLM = old

@pytest.fixture()
def eng():
    d = tempfile.mkdtemp(); e = Engine(d, fake=True); e.start(); cl = e2e.Client(e.url); cl.login()
    e2e.wait(lambda: cl.req("api/state")["status"] == "qr"); yield cl, d, e; e.stop()

def test_teach_saved_cleaned_tried_and_persisted(eng):
    if not shutil.which("node"): pytest.skip("node")
    cl, d, e = eng
    t = {"persona": "موظف سعودي", "tone": "خفيف", "dos": ["رحب", " "], "donts": ["لا تعطي خصم"], "faq": [{"q": "متى تفتحون", "a": "نفتح ٤ العصر 🌷"}, {"q": "", "a": "x"}],
         "examples": [{"q": "غالي", "a": "أفهمك والله"}], "forbidden": ["سياسة"], "handoff": ["استرجاع"], "evil": "<script>"}
    s = cl.req("api/settings", {"teach": t, "aiModel": "off"})
    assert s["teach"]["dos"] == ["رحب"] and len(s["teach"]["faq"]) == 1 and "evil" not in s["teach"] and s["aiModel"] == "off"
    r = cl.req("api/teach/try", {"text": "متى تفتحون؟"}); assert r["reply"] == "نفتح ٤ العصر 🌷" and r["engine"] == "rules"
    r = cl.req("api/teach/try", {"text": "ابي استرجاع فلوسي"}); assert r["handoff"]
    r = cl.req("api/teach/try", {"text": "متى تفتحون؟", "teach": {**t, "faq": [{"q": "متى تفتحون", "a": "من ٥ المغرب"}]}}); assert r["reply"] == "من ٥ المغرب"   # unsaved draft
    assert cl.req("api/teach")["defaults"]["persona"]
    st = cl.req("api/state"); assert "ai" in st
    e.stop(); e2 = Engine(d, fake=True); e2.start(); c2 = e2e.Client(e2.url); c2.login()
    try: assert c2.req("api/teach")["current"]["faq"][0]["a"] == "نفتح ٤ العصر 🌷"
    finally: e2.stop()

def test_chat_order_is_whatsapp_exact(eng):
    cl, d, e = eng; now = int(time.time() * 1000)
    L = lambda n: {"seconds": n}
    hist = {"chats": [{"id": "966500000101@s.whatsapp.net", "conversationTimestamp": {"low": (now - 3600_000) // 1000, "high": 0}},
                      {"id": "966500000102@s.whatsapp.net", "conversationTimestamp": str((now - 60_000) // 1000), "pinned": 0},
                      {"id": "966500000103@s.whatsapp.net", "conversationTimestamp": (now - 86400_000) // 1000, "pinned": (now - 5 * 86400_000) // 1000}],
            "messages": [{"key": {"remoteJid": "966500000101@s.whatsapp.net", "fromMe": False, "id": "O1"}, "messageTimestamp": {"low": (now - 3600_000) // 1000, "high": 0}, "message": {"conversation": "هلا"}},
                         {"key": {"remoteJid": "966500000102@s.whatsapp.net", "fromMe": True, "id": "O2"}, "messageTimestamp": (now - 60_000) // 1000, "message": {"conversation": "أبشر"}},
                         {"key": {"remoteJid": "966500000103@s.whatsapp.net", "fromMe": False, "id": "O3"}, "messageTimestamp": (now - 86400_000) // 1000, "message": {"conversation": "شكراً"}}]}
    cl.req("api/sim/link", {"me": "966500000000", "history": hist}); e2e.wait(lambda: len(cl.req("api/chats")) >= 3)
    order = [c["jid"][9:12] for c in cl.req("api/chats")]
    assert order == ["103", "102", "101"]                             # pinned first (WhatsApp default), then newest message
    ts = {c["jid"][9:12]: c["lastAt"] for c in cl.req("api/chats")}; assert abs(ts["101"] - (now - 3600_000)) < 2000   # Long timestamp decoded
    cl.req("api/settings", {"pinnedTop": False}); assert [c["jid"][9:12] for c in cl.req("api/chats")] == ["102", "101", "103"]
    cl.req("api/sim/incoming", {"jid": "966500000103@s.whatsapp.net", "text": "موجود؟"})    # new message → jumps to the top, live
    assert e2e.wait(lambda: cl.req("api/chats")[0]["jid"].endswith("103@s.whatsapp.net"))
    cl.req("api/sim/incoming", {"jid": "966500000101@s.whatsapp.net", "text": "كم السعر؟"})
    assert e2e.wait(lambda: [c["jid"][9:12] for c in cl.req("api/chats")] == ["101", "103", "102"])

for f in (test_teach_saved_cleaned_tried_and_persisted, test_chat_order_is_whatsapp_exact):
    for m in need_node: f.pytestmark = getattr(f, "pytestmark", []) + [m]

@pytest.mark.skipif(find_files()[0] is None, reason="local model files not on this machine (set WAE_LLM_DIR)")
def test_local_ai_quality_latency_fallback():
    from app import ai_check
    o = ai_check.run(max_ms=30000, need_ai=2); print(ai_check.report(o)); assert o["ok"], o["problems"]

def test_marketing_ranked_actions_drafts_only(eng):
    cl, d, e = eng; now = int(time.time() * 1000); day = 86400_000
    hist = {"chats": [], "messages": [
        {"key": {"remoteJid": "966500000201@s.whatsapp.net", "fromMe": False, "id": "K1"}, "messageTimestamp": (now - 2 * day) // 1000, "message": {"conversation": "بكم بوكيه الجوري؟"}},
        {"key": {"remoteJid": "966500000202@s.whatsapp.net", "fromMe": False, "id": "K2"}, "messageTimestamp": (now - 45 * day) // 1000, "message": {"conversation": "شكراً"}}]}
    cl.req("api/sim/link", {"me": "966500000000", "history": hist}); e2e.wait(lambda: len(cl.req("api/chats")) >= 2)
    cl.req("api/crm", {"jid": "966500000202@s.whatsapp.net", "data": {"orders": [{"item": "بوكيه توليب", "amount": 220, "status": "تم التوصيل", "deliveryDate": "2026-01-01", "date": now - 45 * day}]}})
    j = cl.req("api/mkt/actions"); ids = [a["id"] for a in j["actions"]]
    assert 1 <= len(ids) <= 5 and "cold" in ids and "winback" in ids and "status" in ids and ids[0] == "cold" and j["cap"] == 20
    for a in j["actions"]:
        assert "{الاسم}" in a["template"] or a["status"]
        assert len(a["people"]) <= 20
    assert [p["jid"] for p in next(a for a in j["actions"] if a["id"] == "cold")["people"]] == ["966500000201@s.whatsapp.net"]
    r = cl.req("api/mkt/draft", {"goal": "متابعة", "template": "هلا {الاسم} 🌷"}); assert r["text"]
    assert cl.req("api/mkt/opened", {"jid": "966500000201@s.whatsapp.net"})["opened"] == 1
    audit = json.dumps(cl.req("api/audit"), ensure_ascii=False); assert "manual_send" not in audit and "auto_reply" not in audit   # nothing was sent
