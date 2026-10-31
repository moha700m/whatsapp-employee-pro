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
    c = by[LID_C]; assert c["hidden"] and c["label"] == "عميل #6730" and "رقم مخفي" not in raw and c["disp"] == ""
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


def test_lid_every_route(eng):
    """v2.2.1: every LID→phone route Baileys v7 offers resolves and merges the chat."""
    cl, _ = eng; P = lambda n: f"9665{n}@s.whatsapp.net"
    routes = {
        "remoteJidAlt": lambda l, p: cl.req("api/sim/incoming", {"jid": l, "text": "هلا", "key": {"remoteJidAlt": p}}),
        "participantAlt": lambda l, p: cl.req("api/sim/incoming", {"jid": l, "text": "هلا", "key": {"participant": l, "participantAlt": p}}),
        "lidRepo": lambda l, p: cl.req("api/sim/lidrepo", {"lid": l, "pn": p}),
        "lid-mapping.update": lambda l, p: cl.req("api/sim/ev", {"event": "lid-mapping.update", "data": {"lid": l, "pn": p}}),
        "contacts.upsert": lambda l, p: cl.req("api/sim/ev", {"event": "contacts.upsert", "data": [{"id": l, "phoneNumber": p, "notify": "زبون"}]}),
        "contacts.update": lambda l, p: cl.req("api/sim/ev", {"event": "contacts.update", "data": [{"id": p, "lid": l}]}),
        "chats.upsert pnJid": lambda l, p: cl.req("api/sim/ev", {"event": "chats.upsert", "data": [{"id": l, "pnJid": p}]}),
        "chats.update lidJid": lambda l, p: cl.req("api/sim/ev", {"event": "chats.update", "data": [{"id": p, "lidJid": l}]}),
    }
    base = cl.req("api/state")["lid"]["unresolved"]
    for i, (name, fire) in enumerate(routes.items()):
        lid, pn = f"5550000000{i:03d}@lid", P(f"5{i:02d}00{i:04d}"[:8])
        cl.req("api/sim/incoming", {"jid": lid, "text": "السلام عليكم", "name": "عميل"})
        assert e2e.wait(lambda: lid in {c["jid"] for c in cl.req("api/chats")}), name
        assert cl.req("api/state")["lid"]["unresolved"] >= 1
        fire(lid, pn)
        x = e2e.wait(lambda: (b := {c["jid"]: c for c in cl.req("api/chats")}).get(pn) and lid not in b and b)
        assert x, f"route {name} did not resolve"
        assert x[pn]["disp"].startswith("05") and not x[pn]["hidden"], name
    assert cl.req("api/state")["lid"]["unresolved"] == base


MEDIA = Path(__file__).resolve().parent / "media"
MEDIA_CASES = [("image", "rose.jpg", {"mimetype": "image/jpeg", "caption": "ابي مثل هذا", "width": 480, "height": 360}, "image/jpeg"),
               ("video", "video.mp4", {"mimetype": "video/mp4", "seconds": 3}, "video/mp4"),
               ("audio", "voice.ogg", {"mimetype": "audio/ogg; codecs=opus", "seconds": 6, "ptt": True}, "audio/ogg"),
               ("sticker", "sticker.webp", {"mimetype": "image/webp"}, "image/webp"),
               ("document", "price-list.pdf", {"mimetype": "application/pdf", "fileName": "price-list.pdf"}, "application/pdf")]

def get_raw(cl, path, headers=None):
    import urllib.request
    rq = urllib.request.Request(cl.base.rstrip("/") + "/" + path, headers=headers or {})
    with cl.op.open(rq) as r: return r.status, r.headers, r.read()

def test_media_open_play_cache(eng):
    """v2.2.1: customer images, videos, voice notes, stickers and documents open/play from a cached local file."""
    import base64
    cl, d = eng; jid = "966559990000@s.whatsapp.net"; ids = {}
    for kind, fn, body, mime in MEDIA_CASES:
        raw = (MEDIA / fn).read_bytes()
        ids[kind] = cl.req("api/sim/media", {"jid": jid, "kind": kind, "name": "عميل تجربة", "body": {**body, "fakeData": base64.b64encode(raw).decode()}})["id"]
    ch = e2e.wait(lambda: (c := cl.req("api/chat?jid=" + jid)) and len([m for m in c["messages"] if m.get("media")]) == 5 and c)
    by = {m["media"]["type"]: m for m in ch["messages"] if m.get("media")}
    assert by["audio"]["media"]["ptt"] and by["audio"]["media"]["secs"] == 6 and by["video"]["media"]["secs"] == 3
    assert by["document"]["media"]["name"] == "price-list.pdf" and by["image"]["text"] == "ابي مثل هذا"
    assert "fakeData" not in json.dumps(ch)                      # keys/bytes never leak into the chat JSON
    for kind, fn, body, mime in MEDIA_CASES:
        st, h, data = get_raw(cl, "api/media?id=" + ids[kind])
        assert st == 200 and data == (MEDIA / fn).read_bytes() and h["content-type"].startswith(mime), kind
    st, h, data = get_raw(cl, "api/media?id=" + ids["video"], {"Range": "bytes=0-99"})   # seeking in the video player
    assert st == 206 and len(data) == 100
    cached = [p for p in Path(d).rglob(ids["audio"] + ".*") if p.parent.name == "media"]; assert cached and cached[0].suffix == ".ogg"
    st, h, _ = get_raw(cl, "api/media?id=" + ids["document"] + "&dl=1"); assert "attachment" in h["content-disposition"]
    import urllib.error
    with pytest.raises(urllib.error.HTTPError) as e: get_raw(cl, "api/media?id=../../store")
    assert e.value.code == 404
