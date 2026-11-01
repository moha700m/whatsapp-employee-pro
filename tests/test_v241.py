"""v2.4.1: live UI events (SSE), Windows notifications + chimes, relevant reply suggestions, marketing «اكتب بالذكاء» never empty."""
import json, threading, time, shutil, tempfile, wave, pytest, urllib.request
from pathlib import Path
from app.launcher import Engine
from app import e2e, notifier
from app import brain_server as BS

ROOT = Path(__file__).resolve().parent.parent; ENGINE = ROOT / "engine"
need_node = pytest.mark.skipif(not shutil.which("node") or not (ENGINE / "node_modules" / "express").exists(), reason="node/npm ci")

@pytest.fixture()
def eng():
    d = tempfile.mkdtemp(); e = Engine(d, fake=True); e.start(); cl = e2e.Client(e.url); cl.login()
    e2e.wait(lambda: cl.req("api/state")["status"] == "qr"); cl.req("api/sim/link", {"me": "966500000000", "history": {"chats": [], "messages": []}})
    e2e.wait(lambda: cl.req("api/state")["status"] == "connected"); yield cl, e; e.stop()

def listen(cl, out):
    def run():
        r = cl.op.open(urllib.request.Request(cl.base + "api/events"), timeout=30); ev = None
        for raw in r:
            line = raw.decode("utf-8").strip()
            if line.startswith("event:"): ev = line[6:].strip()
            elif line.startswith("data:"): out.append((ev, json.loads(line[5:])))
    threading.Thread(target=run, daemon=True).start()

@need_node
def test_incoming_updates_list_and_badge_live_without_opening(eng):
    cl, e = eng; got = []; listen(cl, got); e2e.wait(lambda: any(x[0] == "hello" for x in got))
    cl.req("api/sim/incoming", {"jid": "966500000701@s.whatsapp.net", "text": "السلام عليكم", "name": "عميل"})
    assert e2e.wait(lambda: any(x[0] == "msg" and x[1]["jid"] == "966500000701@s.whatsapp.net" for x in got), timeout=5)   # pushed instantly, no polling
    time.sleep(1.1); cl.req("api/sim/incoming", {"jid": "966500000702@s.whatsapp.net", "text": "كم سعر الجوري؟", "name": "عميل"})
    assert e2e.wait(lambda: any(x[0] == "msg" and x[1]["jid"] == "966500000702@s.whatsapp.net" for x in got), timeout=5)
    L = cl.req("api/chats"); assert L[0]["jid"] == "966500000702@s.whatsapp.net" and L[0]["state"] == "wait"            # list order + waiting badge
    assert sum(c["state"] == "wait" for c in L) == 2

@need_node
def test_windows_notifications_per_type_quiet_and_sound(eng):
    cl, e = eng; notifier.SHOWN.clear()
    cl.req("api/sim/incoming", {"jid": "966500000703@s.whatsapp.net", "text": "ابي اطلب بوكيه", "name": "سارة"})
    assert e2e.wait(lambda: {x["kind"] for x in notifier.SHOWN} >= {"msg", "order"}, timeout=8)
    m = next(x for x in notifier.SHOWN if x["kind"] == "msg"); assert m["sound"] and m["volume"] == 70 and m["jid"].startswith("966500000703")
    assert "wae://chat/966500000703" in notifier.toast_xml(m) and 'silent="true"' in notifier.toast_xml(m)
    cl.req("api/settings", {"notify": {"msg": False, "quiet": True, "quietFrom": "00:00", "quietTo": "23:59", "volume": 30}}); notifier.SHOWN.clear()
    cl.req("api/sim/incoming", {"jid": "966500000704@s.whatsapp.net", "text": "ابي اطلب ورد", "name": "عميل"})
    assert e2e.wait(lambda: notifier.SHOWN, timeout=8); time.sleep(0.5)
    assert all(x["kind"] != "msg" for x in notifier.SHOWN) and all(not x["sound"] for x in notifier.SHOWN)             # type off + quiet hours = silent
    cl.req("api/settings", {"notify": {"on": False}}); notifier.SHOWN.clear(); cl.req("api/notify/test", {}); time.sleep(0.8); assert not notifier.SHOWN

def test_chimes_are_short_valid_and_distinct():
    data = {}
    for k in ("msg", "order", "alert"):
        with wave.open(str(ENGINE / "public" / "sounds" / f"{k}.wav")) as w: assert w.getframerate() == 44100 and 0.5 < w.getnframes() / 44100 < 1.5; data[k] = w.readframes(w.getnframes())
    assert len(set(data.values())) == 3
    f = notifier.scaled("msg", 30); assert f and f.exists()

CONV = {
    "price": [("هلا", 0), ("هلا والله", 1), ("كم سعر بوكيه الجوري؟", 0)],
    "delivery": [("ابي بوكيه", 0), ("أبشر", 1), ("توصلون حي النرجس اليوم؟", 0)],
    "status": [("طلبت امس بوكيه", 0), ("أبشر", 1), ("طلبي وين وصل؟", 0)],
    "greeting": [("السلام عليكم", 0)],
}
@pytest.mark.parametrize("intent", list(CONV))
def test_suggestions_answer_the_current_question(intent):
    r = BS.do_suggest({"messages": [{"text": t, "fromMe": bool(f)} for t, f in CONV[intent]]})
    assert r["intent"] == intent and 1 <= len(r["replies"]) <= 3
    for x in r["replies"]: assert BS.relevant(x, intent), x
    if intent == "price": assert all("150" in x or "ريال" in x or "ر.س" in x for x in r["replies"][:1])
    if intent != "greeting": assert not any(x.startswith(("يا هلا 🌸 آمر", "هلا والله، حياك الله")) for x in r["replies"])   # no random greeting

def test_suggestions_ignore_old_answered_topics():
    r = BS.do_suggest({"messages": [{"text": "كم سعر الجوري؟", "fromMe": False}, {"text": "150 ريال", "fromMe": True}, {"text": "شكراً", "fromMe": False}]})
    assert r["intent"] == "thanks" and not any("150" in x for x in r["replies"])

@need_node
def test_marketing_write_never_empty_without_model(eng):
    cl, e = eng; r = cl.req("api/mkt/draft", {"goal": "ترجيع عميل قديم", "template": "هلا {الاسم}"})
    assert r["text"] and r["text"] != "هلا {الاسم}" and "{الاسم}" in r["text"] and len(r.get("alts", [])) >= 3
