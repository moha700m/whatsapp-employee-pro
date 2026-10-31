"""v2.2: LID → phone resolution (never show raw LIDs), status badges, smart plan, auto profile, disconnect keep/wipe."""
import json, re, shutil, tempfile, time, pytest
from pathlib import Path
from app.launcher import Engine
from app import e2e

ENGINE = Path(__file__).resolve().parent.parent / "engine"
pytestmark = [pytest.mark.skipif(not shutil.which("node"), reason="node"),
              pytest.mark.skipif(not (ENGINE / "node_modules" / "express").exists(), reason="npm ci")]
DAY = 86400_000
LID_A, LID_B, LID_C = "182772702413028@lid", "63308489647951@lid", "217398493896730@lid"

def hist(now):
    def m(jid, i, text, fromMe, mins):
        return {"key": {"remoteJid": jid, "fromMe": fromMe, "id": f"V{abs(hash(jid)) % 9999}{i}"}, "messageTimestamp": (now - mins * 60000) // 1000, "message": {"conversation": text}}
    return {"chats": [{"id": LID_A, "pnJid": "966551112222@s.whatsapp.net", "conversationTimestamp": now // 1000},
                      {"id": "966553334444@s.whatsapp.net", "lidJid": LID_B},
                      {"id": LID_C}],
            "contacts": [{"id": "966553334444@s.whatsapp.net", "notify": "أبو فهد"}],
            "messages": [m(LID_A, 1, "السلام عليكم معك سارة، بكم بوكيه الجوري؟ ابيه بكره حي الفيصلية", False, 190),
                         m(LID_B, 1, "ابي اطلب بوكيه توليب", False, 30), m(LID_B, 2, "أبشر", True, 20),
                         m(LID_C, 1, "هلا", False, 10)]}

@pytest.fixture()
def eng():
    d = tempfile.mkdtemp(); e = Engine(d, fake=True); e.start(); cl = e2e.Client(e.url); cl.login()
    e2e.wait(lambda: cl.req("api/state")["status"] == "qr")
    cl.req("api/sim/link", {"me": "966500000000", "history": hist(int(time.time() * 1000))})
    e2e.wait(lambda: len(cl.req("api/chats")) >= 3)
    yield cl, d
    e.stop()

def test_lids_resolved_never_shown(eng):
    cl, _ = eng; chats = cl.req("api/chats"); raw = json.dumps(chats, ensure_ascii=False)
    by = {c["jid"]: c for c in chats}
    a = by["966551112222@s.whatsapp.net"]; assert a["disp"] == "0551112222" and not a["hidden"]
    b = by["966553334444@s.whatsapp.net"]; assert b["label"] == "أبو فهد" and b["disp"] == "0553334444" and len(b["n"] if isinstance(b["n"], list) else [0] * b["n"]) == 2
    c = by[LID_C]; assert c["hidden"] and c["label"] == "رقم مخفي" and c["disp"] == ""
    assert "217398493896730" not in json.dumps({k: v for k, v in c.items() if k != "jid"}, ensure_ascii=False)
    assert "182772702413028" not in raw                                    # merged into the phone chat
    # a live message from the hidden LID that carries sender_pn resolves it and merges
    cl.req("api/sim/incoming", {"jid": LID_C, "text": "كم التوصيل؟", "name": "نورة", "senderPn": "966557778888@s.whatsapp.net"})
    n = e2e.wait(lambda: (x := {c["jid"]: c for c in cl.req("api/chats")}).get("966557778888@s.whatsapp.net") and x)
    m = n["966557778888@s.whatsapp.net"]; assert m["disp"] == "0557778888" and m["n"] == 2 and LID_C not in n

def test_badges_plan_profile(eng):
    cl, _ = eng; by = {c["jid"]: c for c in cl.req("api/chats")}
    assert by["966551112222@s.whatsapp.net"]["state"] == "wait" and by["966551112222@s.whatsapp.net"]["waitMs"] > 3 * 3600e3 - 60e3 * 20
    assert by["966553334444@s.whatsapp.net"]["state"] in ("replied", "new")
    p = cl.req("api/plan"); assert p["greeting"] and p["progress"]["total"] >= 1
    it = [i for i in p["items"] if i.get("jid") == "966551112222@s.whatsapp.net"][0]
    assert it["type"] == "reply" and "السعر" in it["why"] and it["value"] > 0
    vis = json.dumps([[i.get(k) for k in ("title", "why", "label", "disp")] for i in p["items"]] + p["summary"], ensure_ascii=False)
    assert not re.search(r"\d{11,}", vis) and "@" not in vis, "raw ids in plan text"
    assert all(" ٠ ر.س" not in s for s in p["summary"])
    cl.req("api/plan/done", {"id": it["id"]}); p2 = cl.req("api/plan"); assert p2["progress"]["done"] >= 1 and it["id"] not in [i["id"] for i in p2["items"]]
    ch = cl.req("api/chat?profile=1&jid=966551112222@s.whatsapp.net"); pf = ch["profile"]
    assert pf["name"] == "سارة" and pf["district"] == "الفيصليه" and pf["items"] and pf["nextAction"]
    cl.req("api/crm", {"jid": "966551112222@s.whatsapp.net", "data": {"profileEdit": {"district": "النور"}}})
    assert cl.req("api/chat?profile=1&jid=966551112222@s.whatsapp.net")["profile"]["district"] == "النور"

def test_disconnect_keep_then_wipe(eng):
    cl, d = eng
    r = cl.req("api/logout", {"wipe": False}); assert r["ok"] and not r["wiped"]
    assert len(cl.req("api/chats")) >= 3, "keep must keep chats"
    st = e2e.wait(lambda: (s := cl.req("api/state"))["status"] == "qr" and s); assert st["qr"]       # ready to re-link
    cl.req("api/logout", {"wipe": True}); assert cl.req("api/chats") == []
    store = json.loads((Path(d) / "wa" / "store.json").read_text(encoding="utf-8")); assert store["chats"] == {} and store["lidMap"] == {}
