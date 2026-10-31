"""End-to-end scenario against a running engine in simulator mode (FAKE_WA=1). Used by --smoke and the tests.
Synthetic data only — no real names or numbers."""
import json, time, urllib.request, http.cookiejar

class Client:
    def __init__(self, base):
        self.base = base; self.csrf = ""
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def req(self, path, body=None, expect=200):
        data = None if body is None else json.dumps(body).encode()
        r = urllib.request.Request(self.base + path, data=data, headers={"content-type": "application/json", "x-csrf": self.csrf})
        try:
            with self.op.open(r, timeout=10) as res: code, raw = res.status, res.read()
        except urllib.error.HTTPError as e: code, raw = e.code, e.read()
        if expect is not None and code != expect: raise AssertionError(f"{path} -> {code}: {raw[:200]!r}")
        try: return json.loads(raw.decode("utf-8"))
        except ValueError: return raw.decode("utf-8", "replace")
    def login(self):
        a = self.req("api/auth"); assert a["loggedIn"], a; self.csrf = a["csrf"]; return a

def wait(fn, timeout=10, step=0.15):
    end = time.time() + timeout; last = None
    while time.time() < end:
        last = fn()
        if last: return last
        time.sleep(step)
    raise AssertionError("timed out waiting")

DAY = 86400_000
def history(now_ms):
    def m(jid, i, text, fromMe, days):
        return {"key": {"remoteJid": jid, "fromMe": fromMe, "id": f"H{jid[:6]}{i}"}, "messageTimestamp": (now_ms - days * DAY) // 1000 + i, "message": {"conversation": text}, "pushName": None if fromMe else None}
    a, b, c = "966511110001@s.whatsapp.net", "966511110002@s.whatsapp.net", "966511110003@s.whatsapp.net"
    return {"chats": [{"id": a, "name": "عميل تجريبي أ"}, {"id": b, "name": "عميل تجريبي ب"}, {"id": c, "name": "عميل تجريبي ج"}, {"id": "1203630@g.us", "name": "قروب"}],
            "contacts": [], "messages": [m(a, 1, "السلام عليكم كم سعر بوكيه الجوري؟", False, 40), m(a, 2, "هلا والله، ١٥٠ ريال", True, 40),
                                        m(b, 1, "ابي بوكيه توليب للتخرج بكره", False, 3), m(c, 1, "شكراً وصل الطلب", False, 1),
                                        m("1203630@g.us", 1, "رسالة قروب", False, 1)]}

def scenario(base, log=print):
    cl = Client(base); cl.login(); out = {}
    st = wait(lambda: (s := cl.req("api/state")) and s["status"] == "qr" and s["qr"] and s); log("1 QR shown")
    assert st["qr"].startswith("data:image/png;base64,")
    now = int(time.time() * 1000)
    cl.req("api/sim/link", {"me": "966500000000", "history": history(now)})
    wait(lambda: cl.req("api/state")["status"] == "connected"); chats = wait(lambda: len(c := cl.req("api/chats")) >= 3 and c)
    assert len(chats) == 3, chats; assert all("@g.us" not in c["jid"] for c in chats); log(f"2 linked, history loaded: {len(chats)} chats (group hidden)")
    a = "966511110001@s.whatsapp.net"; ch = cl.req("api/chat?jid=" + a); assert len(ch["messages"]) == 2
    cl.req("api/send", {"jid": a, "text": "تجربة"}, expect=400)                              # no confirm → refused
    cl.req("api/send", {"jid": a, "text": "أبشر، نجهزه لك", "confirm": True})
    ob = wait(lambda: (o := cl.req("api/sim/outbox")) and o); assert ob[-1]["text"] == "أبشر، نجهزه لك" and ob[-1]["jid"] == a
    wait(lambda: any(m["text"] == "أبشر، نجهزه لك" and m["fromMe"] for m in cl.req("api/chat?jid=" + a)["messages"])); log("3 manual send OK (needs confirm)")
    # employee OFF: incoming gets no reply
    n0 = len(cl.req("api/sim/outbox")); cl.req("api/sim/incoming", {"jid": "966511110009@s.whatsapp.net", "text": "السلام عليكم", "name": "عميل تجريبي د"})
    time.sleep(1.0); assert len(cl.req("api/sim/outbox")) == n0, "employee is off but replied"; log("4 employee OFF → no auto reply")
    cl.req("api/settings", {"autoReply": {"enabled": True, "schedule": "always", "mode": "smart", "delaySec": 0, "cooldownMin": 2, "handoff": True}})
    assert cl.req("api/state")["employee"]["active"] is True
    j1 = "966511110010@s.whatsapp.net"; cl.req("api/sim/incoming", {"jid": j1, "text": "السلام عليكم", "name": "عميل تجريبي هـ"})
    r1 = wait(lambda: [o for o in cl.req("api/sim/outbox") if o["jid"] == j1]); assert "هلا" in r1[0]["text"] or "حياك" in r1[0]["text"], r1
    log(f"5 auto reply to greeting: {r1[0]['text']}")
    j2 = "966511110011@s.whatsapp.net"; cl.req("api/sim/incoming", {"jid": j2, "text": "ابي اطلب بوكيه جوري بكره حي النرجس", "name": "عميل تجريبي و"})
    r2 = wait(lambda: [o for o in cl.req("api/sim/outbox") if o["jid"] == j2]); assert "المسؤول" in r2[0]["text"], r2
    assert wait(lambda: any(x["kind"] == "human" and x["jid"] == j2 for x in cl.req("api/alerts"))); log("6 order → handoff message + owner alert")
    cl.req("api/sim/incoming", {"jid": "1203630@g.us", "text": "السلام عليكم", "name": "x"}); cl.req("api/sim/incoming", {"jid": j1, "text": "متى تفتحون؟"})
    time.sleep(1.2); ob = cl.req("api/sim/outbox")
    assert not [o for o in ob if o["jid"].endswith("@g.us")], "replied to group"; assert len([o for o in ob if o["jid"] == j1]) == 1, "cooldown ignored"
    log("7 group ignored, per-customer cooldown respected")
    au = cl.req("api/audit"); assert any(x["type"] == "auto_reply" for x in au) and any(x["type"] == "auto_handoff" for x in au) and any(x["type"] == "manual_send" for x in au)
    log("8 every auto reply/handoff/manual send is in the log")
    cl.req("api/crm", {"jid": a, "data": {"tag": "طلب", "note": "ملاحظة", "orders": [{"item": "بوكيه جوري", "amount": 150, "status": "جديد", "date": now}]}})
    cl.req("api/settings", {"tourDone": True, "shopName": "محل تجريبي"})
    d = cl.req("api/dashboard"); assert d["analytics"]["revenue"] == 150 and d["analytics"]["orders"] == 1; log("9 order saved → dashboard revenue 150")
    out.update(chats=len(cl.req("api/chats")), outbox=len(cl.req("api/sim/outbox"))); return out

def verify_persisted(base, log=print):
    cl = Client(base); cl.login(); s = cl.req("api/crm")
    st = wait(lambda: (x := cl.req("api/state")) and x["chats"] >= 5 and x)
    assert s["settings"]["tourDone"] is True and s["settings"]["shopName"] == "محل تجريبي", "settings lost"
    assert s["settings"]["autoReply"]["enabled"] is True, "employee state lost"
    a = "966511110001@s.whatsapp.net"; assert s["crm"][a]["tag"] == "طلب" and s["crm"][a]["orders"][0]["amount"] == 150, "crm lost"
    assert len(cl.req("api/chat?jid=" + a)["messages"]) >= 3, "messages lost"
    assert cl.req("api/dashboard")["analytics"]["revenue"] == 150
    assert any(x["type"] == "auto_reply" for x in cl.req("api/audit")), "log lost"
    log(f"persisted after restart: {st['chats']} chats, {st['messages']} messages, settings, employee ON, orders, log")
    return True
