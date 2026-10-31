import json, pytest
from datetime import datetime
from app.core import workflow as wfm
from app.core.settings import AutoReplySettings
from tests.test_auto_reply import FakeDriver, Clock
from app.core.auto_reply import AutoReplyEngine

OPT = AutoReplySettings().opt_out_list
BIZ = [{"title": "باقة التصميم", "content": "شعار", "price": "500 ريال"}]

def ev(wf, text, biz=BIZ):
    return wfm.evaluate(wf, [text], "أحمد", biz, OPT)

def test_defaults_match_builtin_behavior():
    wf = wfm.default_workflow()
    assert ev(wf, "لا ترسل لي").action == "stop"
    d = ev(wf, "الطلب ما وصل وتأخر"); assert d.action == "holding" and d.reply == wf["templates"]["holding"]
    assert ev(wf, "بكم الاشتراك؟").action == "holding"
    assert ev(wf, "كم سعر باقة التصميم؟").action == "ai"
    assert ev(wf, "السلام عليكم").action == "ai"   # greeting rule seeded disabled

def test_rule_order_and_enable():
    wf = wfm.default_workflow()
    wf["rules"].insert(0, wfm._rule("VIP", "keywords", "reply", "عاجل,ضروري", "أبشر {name}، معك الحين"))
    assert ev(wf, "ضروري الطلب ما وصل").reply == "أبشر أحمد، معك الحين"
    wf["rules"][0]["enabled"] = False
    assert ev(wf, "ضروري الطلب ما وصل").action == "holding"

def test_greeting_rule_template():
    wf = wfm.default_workflow()
    next(r for r in wf["rules"] if r["trigger"] == "greeting")["enabled"] = True
    d = ev(wf, "السلام عليكم"); assert d.action == "reply" and "أحمد" in d.reply

def test_classification_and_mark():
    wf = wfm.default_workflow()
    wf["rules"][0:0] = [wfm._rule("علّم VIP", "keywords", "mark", "شركة", set_class="Hot Lead"),
                        wfm._rule("Hot", "classification", "reply", "Hot Lead", "تمام {name}، نجهز الطلب")]
    d = ev(wf, "احنا شركة ونبي عرض"); assert d.reply == "تمام أحمد، نجهز الطلب" and d.classification == "Hot Lead"

def test_price_question_trigger_and_ignore():
    wf = wfm.default_workflow()
    wf["rules"].insert(0, wfm._rule("price", "price_question", "ignore"))
    assert ev(wf, "كم سعر باقة التصميم").action == "ignore"

def test_faq():
    wf = wfm.default_workflow(); wf["business"]["faq"] = [{"q": "هل يوجد توصيل؟", "a": "إيه نوصل لكل مدن المملكة"}]
    d = ev(wf, "عندكم توصيل للرياض؟"); assert d.action == "reply" and "نوصل" in d.reply

def test_tone_emoji_and_length():
    wf = wfm.default_workflow(); wf["tone"].update(emoji=False, max_len=20)
    assert wfm.apply_tone("هلا 🌷 والله حياك يا غالي ونورتنا كثير", wf).endswith("…")
    assert "🌷" not in wfm.apply_tone("هلا 🌷", wf)

def test_working_hours():
    wf = wfm.default_workflow(); wf["working_hours"].update(enabled=True, start="09:00", end="17:00")
    assert wfm.in_working_hours(wf, datetime(2026, 1, 1, 10)) and not wfm.in_working_hours(wf, datetime(2026, 1, 1, 20))
    wf["working_hours"].update(start="20:00", end="02:00")
    assert wfm.in_working_hours(wf, datetime(2026, 1, 1, 23)) and not wfm.in_working_hours(wf, datetime(2026, 1, 1, 12))

def test_persistence_roundtrip_and_invalid(repo):
    wf = wfm.load(repo); wf["templates"]["greeting"] = "يا هلا"; wf["rules"].pop(); wfm.save(repo, wf)
    l = wfm.load(repo); assert l["templates"]["greeting"] == "يا هلا" and len(l["rules"]) == 5
    with pytest.raises(ValueError):
        wfm.save(repo, {"rules": [{"trigger": "bogus", "action": "reply"}]})
    repo.set_setting("workflow", "{broken"); assert wfm.load(repo)["rules"]  # corrupt -> defaults
    wfm.reset(repo); assert len(wfm.load(repo)["rules"]) == 6

def test_export_import(repo, tmp_path):
    repo.add_business_info("منتج", "باقة", "x", "100 ريال")
    wf = wfm.load(repo); wf["business"]["name"] = "متجر ليان"; wfm.save(repo, wf)
    AutoReplySettings(send_mode="auto", auto_reply_enabled=True, min_delay=3).save(repo)
    data = wfm.export_json(repo)
    assert json.loads(data)["workflow"]["business"]["name"] == "متجر ليان"
    wfm.reset(repo); repo.delete_all_customer_data()
    AutoReplySettings(auto_reply_enabled=False).save(repo)
    wfm.import_json(repo, data)
    assert wfm.load(repo)["business"]["name"] == "متجر ليان"
    assert [b["title"] for b in repo.business_info()] == ["باقة"]
    s = AutoReplySettings.load(repo); assert s.min_delay == 3 and s.auto_reply_enabled is False  # import never enables
    with pytest.raises(Exception): wfm.import_json(repo, "not json")

def test_simulate_never_sends(repo):
    repo.add_business_info("منتج", "باقة التصميم", "شعار", "500 ريال")
    r = wfm.simulate(repo, "كم سعر باقة التصميم؟", "أحمد")
    assert r["action"] == "ai" and "500 ريال" in r["reply"]
    assert repo.db.scalar("SELECT COUNT(*) FROM auto_replies") == 0

def _engine(repo):
    s = AutoReplySettings(send_mode="auto", auto_reply_enabled=True, min_delay=0, max_delay=0, chat_cooldown=0)
    d = FakeDriver(); return AutoReplyEngine(repo, d, settings=s, clock=Clock(), sleep=lambda x: None), d

def test_engine_uses_live_rules(repo):
    eng, d = _engine(repo)
    wf = wfm.load(repo); wf["rules"].insert(0, wfm._rule("عرض", "keywords", "reply", "عرض", "عرض اليوم خصم 10٪ يا {name}")); wfm.save(repo, wf)
    d.add("سعد", ["فيه عرض؟"]); assert eng.run_once() == [("سعد", "rule_replied")]
    assert d.sent[0][1] == "عرض اليوم خصم 10٪ يا سعد"

def test_engine_workflow_disabled_and_hours(repo):
    eng, d = _engine(repo)
    wf = wfm.load(repo); wf["enabled"] = False; wfm.save(repo, wf)
    d.add("سعد", ["هلا"]); assert eng.run_once() == [("سعد", "disabled")]
    wf["enabled"] = True; wf["working_hours"].update(enabled=True, start="00:00", end="00:00", away_enabled=True)
    wf["working_hours"]["start"], wf["working_hours"]["end"] = "23:59", "23:59"  # zero-length -> always outside
    wfm.save(repo, wf)
    assert eng.run_once() == [("سعد", "away_sent")] and "الدوام" in d.sent[0][1]
    d.add("سعد", ["؟"]); assert eng.run_once() == [("سعد", "outside_hours")]   # away only once/day

def test_opt_out_confirmation_template(repo):
    eng, d = _engine(repo)
    wf = wfm.load(repo); wf["templates"]["opt_out"] = "تم، ما راح نراسلك"; wfm.save(repo, wf)
    d.add("هند", ["وقف الرسائل"]); assert eng.run_once() == [("هند", "opted_out_now")]
    assert d.sent == [("هند", "تم، ما راح نراسلك")]
