"""BLOCKER regression (v2.3.1 real phone: employee «شغال», connected, yet no reply). Real incoming messages through the Baileys event path:
PN and LID, new and history chats, wrong PC clock, handoff, no matching rule → a reply is ALWAYS sent (or a visible reason is given)."""
import time, shutil, tempfile, pytest
from pathlib import Path
from app.launcher import Engine
from app import e2e

ENGINE = Path(__file__).resolve().parent.parent / "engine"
pytestmark = [pytest.mark.skipif(not shutil.which("node"), reason="node"), pytest.mark.skipif(not (ENGINE / "node_modules" / "express").exists(), reason="npm ci")]
day = 86400_000

@pytest.fixture()
def eng():
    d = tempfile.mkdtemp(); e = Engine(d, fake=True); e.start(); cl = e2e.Client(e.url); cl.login()
    e2e.wait(lambda: cl.req("api/state")["status"] == "qr"); now = int(time.time() * 1000)
    hist = {"chats": [{"id": "966500000404@s.whatsapp.net", "conversationTimestamp": (now - 2 * day) // 1000}], "messages": [
        {"key": {"remoteJid": "966500000404@s.whatsapp.net", "fromMe": False, "id": "H1"}, "messageTimestamp": (now - 2 * day) // 1000, "message": {"conversation": "شكراً"}},
        {"key": {"remoteJid": "966500000404@s.whatsapp.net", "fromMe": True, "id": "H2"}, "messageTimestamp": (now - 2 * day + 60_000) // 1000, "message": {"conversation": "العفو 🌷"}}]}
    cl.req("api/sim/link", {"me": "966500000000", "history": hist}); e2e.wait(lambda: cl.req("api/state")["status"] == "connected")
    cl.req("api/settings", {"autoReply": {"enabled": True, "schedule": "offhours", "delaySec": 0, "humanTyping": False}})   # default schedule; we flip to «always» below
    cl.req("api/settings", {"autoReply": {"enabled": True, "schedule": "always", "delaySec": 0, "humanTyping": False}})
    yield cl, e; e.stop()

def sent_to(cl, jid): return [o for o in cl.req("api/sim/outbox") if o["jid"] == jid]

def test_every_kind_of_incoming_gets_a_reply(eng):
    cl, e = eng; now = int(time.time() * 1000)
    cases = [("966500000401@s.whatsapp.net", "السلام عليكم", {}, None),                                          # new chat, phone number
             ("88000000000402@lid", "مرحبا عندكم ورد؟", {"senderPn": "966500000402@s.whatsapp.net"}, None),       # Baileys v7 LID with senderPn
             ("88000000000403@lid", "هلا", {}, None),                                                             # LID we can't resolve
             ("966500000404@s.whatsapp.net", "هلا مرة ثانية", {}, None),                                          # old customer from history sync
             ("966500000405@s.whatsapp.net", "ققق", {}, None),                                                    # no rule matches → polite fixed reply
             ("966500000406@s.whatsapp.net", "صباح الخير", {}, now - 3 * 3600_000)]                               # PC clock / time zone off by 3h
    for jid, text, extra, ts in cases:
        sp = extra.pop("senderPn", None)
        cl.req("api/sim/incoming", {"jid": jid, "text": text, "name": "عميل", "senderPn": sp, "ts": ts})
    for jid, *_ in cases:
        assert e2e.wait(lambda: sent_to(cl, jid), timeout=20), f"no reply to {jid}: {[a for a in cl.req('api/audit') if a.get('jid', '').startswith(jid[:12])][:3]}"
    assert all(o["text"] for o in cl.req("api/sim/outbox"))

def test_handoff_sends_holding_message_and_alerts(eng):
    cl, e = eng; j = "966500000407@s.whatsapp.net"
    cl.req("api/sim/incoming", {"jid": j, "text": "كم سعر بوكيه الجوري؟ ابي اطلب", "name": "عميل"})
    assert e2e.wait(lambda: sent_to(cl, j), timeout=20)
    assert "المسؤول" in sent_to(cl, j)[0]["text"] or "دقايق" in sent_to(cl, j)[0]["text"]
    assert any(a["kind"] == "human" for a in cl.req("api/alerts"))

def test_skip_has_visible_reason_and_check_button(eng):
    cl, e = eng; j = "966500000408@s.whatsapp.net"
    cl.req("api/sim/incoming", {"jid": j, "text": "هلا", "name": "عميل"}); assert e2e.wait(lambda: sent_to(cl, j), timeout=20)
    cl.req("api/send", {"jid": j, "text": "هلا والله، أبشر", "confirm": True}); time.sleep(0.5)     # owner takes over by hand
    cl.req("api/sim/incoming", {"jid": j, "text": "طيب", "name": "عميل"})
    assert e2e.wait(lambda: (cl.req("api/chat?jid=" + j) or {}).get("autoWhy", {}).get("code") in ("owner_active", "cooldown"), timeout=10)
    assert "ترد عليه بنفسك" in cl.req("api/chat?jid=" + j)["autoWhy"]["why"] or "قبل شوي" in cl.req("api/chat?jid=" + j)["autoWhy"]["why"]
    k = cl.req("api/employee/check"); assert k["ok"] and {c["id"] for c in k["checks"]} >= {"on", "wa", "time", "day"} and k["recent"]
    cl.req("api/settings", {"autoReply": {"enabled": True, "schedule": "custom", "from": "03:00", "to": "03:01"}})
    k = cl.req("api/employee/check"); assert not k["ok"] and not next(c for c in k["checks"] if c["id"] == "time")["ok"]

def _sends(cl, j): return [o for o in cl.req("api/sim/outbox") if o["jid"] == j]

def test_burst_of_three_gets_one_reply(eng):
    cl, e = eng; j = "966500000601@s.whatsapp.net"
    for t in ("السلام عليكم", "عندكم ورد جوري؟", "كم سعر البوكيه؟"): cl.req("api/sim/incoming", {"jid": j, "text": t, "name": "عميل"}); time.sleep(0.1)
    assert e2e.wait(lambda: _sends(cl, j), timeout=20); time.sleep(2.5)
    out = _sends(cl, j); assert len(out) == 1, out                          # ONE reply for the burst
    assert "المسؤول" in out[0]["text"] or "دقايق" in out[0]["text"]          # price/order beats greeting

def test_message_during_cooldown_is_answered_later(eng):
    cl, e = eng; j = "966500000602@s.whatsapp.net"
    cl.req("api/settings", {"autoReply": {"enabled": True, "schedule": "always", "delaySec": 0, "humanTyping": False, "cooldownMin": 0.05}})
    cl.req("api/sim/incoming", {"jid": j, "text": "هلا", "name": "عميل"}); assert e2e.wait(lambda: len(_sends(cl, j)) == 1, timeout=20)
    cl.req("api/sim/incoming", {"jid": j, "text": "متى تفتحون؟", "name": "عميل"})        # inside the cooldown
    assert e2e.wait(lambda: len(_sends(cl, j)) == 2, timeout=30)
    o = _sends(cl, j); assert o[0]["text"] != o[1]["text"]                                 # never the same text twice in a row

def test_sticker_or_voice_gets_ack_and_alert(eng):
    cl, e = eng; j = "966500000603@s.whatsapp.net"
    cl.req("api/sim/media", {"jid": j, "kind": "sticker", "body": {"mimetype": "image/webp"}, "name": "عميل"})
    assert e2e.wait(lambda: _sends(cl, j), timeout=20) and "وصلت" in _sends(cl, j)[0]["text"]
    assert any(a["kind"] == "human" and a.get("jid") == j for a in cl.req("api/alerts"))

@pytest.mark.parametrize("word", ["ورده", "ورد", "وردة", "ورررده 🌹", "بوكيه", "باقة", "تنسيق", "ك"])
def test_single_word_gets_reply(eng, word):
    cl, e = eng; j = "966500000701@s.whatsapp.net"
    cl.req("api/sim/incoming", {"jid": j, "text": word, "name": "عميل"})
    assert e2e.wait(lambda: _sends(cl, j), timeout=20), [a for a in cl.req("api/audit")][:5]
    t = _sends(cl, j)[0]["text"]; assert t.strip() and "🌷" not in t
    if word != "ك": assert "ورد" in t or "تنسيق" in t, t
    else: assert "وش" in t or "خارج الدوام" in t, t

def test_single_salam_gets_greeting(eng):
    cl, e = eng; j = "966500000702@s.whatsapp.net"
    cl.req("api/sim/incoming", {"jid": j, "text": "السلام", "name": "عميل"})
    assert e2e.wait(lambda: _sends(cl, j), timeout=20)
    assert any(w in _sends(cl, j)[0]["text"] for w in ("السلام", "هلا", "حياك"))

def test_after_handoff_still_answers_and_alerts(eng):
    cl, e = eng; j = "966500000703@s.whatsapp.net"
    cl.req("api/settings", {"autoReply": {"enabled": True, "schedule": "always", "delaySec": 0, "humanTyping": False, "cooldownMin": 0}})
    cl.req("api/sim/incoming", {"jid": j, "text": "ابي اطلب بوكيه جوري", "name": "عميل"}); assert e2e.wait(lambda: len(_sends(cl, j)) == 1, timeout=20)
    cl.req("api/sim/incoming", {"jid": j, "text": "وين موقعكم", "name": "عميل"})
    assert e2e.wait(lambda: len(_sends(cl, j)) == 2, timeout=20), cl.req("api/chats")
    assert "موقع" in _sends(cl, j)[1]["text"]

def test_new_defaults_daily_cap():
    from pathlib import Path
    src = (ENGINE / "employee.js").read_text(encoding="utf-8").split("OLD_DEFAULTS")[0]
    assert "maxPerDay: 30" in src and "maxTotalPerDay: 500" in src and "🌷" not in src

def test_own_number_hint(eng):
    cl, e = eng; me = "966500000000@s.whatsapp.net"
    cl.req("api/sim/incoming", {"jid": me, "text": "ورده", "key": {"fromMe": True}})
    def hint(): return ((cl.req("api/chat?jid=" + me) or {}).get("autoWhy") or {}).get("code") == "own_number"
    assert e2e.wait(hint, timeout=10)
    assert not _sends(cl, me)

def test_after_hours_text_only_once(eng):
    cl, e = eng; j = "966500000704@s.whatsapp.net"
    cl.req("api/settings", {"hoursFrom": "03:00", "hoursTo": "03:01", "autoReply": {"enabled": True, "schedule": "always", "delaySec": 0, "humanTyping": False, "cooldownMin": 0}})
    cl.req("api/sim/incoming", {"jid": j, "text": "حسب الطلب", "name": "عميل"}); assert e2e.wait(lambda: len(_sends(cl, j)) == 1, timeout=20)
    time.sleep(1.1); cl.req("api/sim/incoming", {"jid": j, "text": "تصميم خاص حسب الطلب", "name": "عميل"}); assert e2e.wait(lambda: len(_sends(cl, j)) == 2, timeout=20)
    a, b = [o["text"] for o in _sends(cl, j)]
    assert "خارج الدوام" in a and "خارج الدوام" not in b and a != b, (a, b)
