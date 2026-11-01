"""v2.4: «القناة» tab — the owner's WhatsApp Channel. Read info/posts, ideas, drafts, reminders, AI draft; publish ONLY with confirm, ONLY to his own channel."""
import base64, json, time, shutil, tempfile, pytest
from pathlib import Path
from app.launcher import Engine
from app import e2e

ENGINE = Path(__file__).resolve().parent.parent / "engine"
pytestmark = [pytest.mark.skipif(not shutil.which("node"), reason="node"), pytest.mark.skipif(not (ENGINE / "node_modules" / "express").exists(), reason="npm ci")]
MINE, OTHER = "120363000000000001@newsletter", "120363000000000002@newsletter"
PNG = base64.b64encode(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000")).decode()

@pytest.fixture()
def eng():
    d = tempfile.mkdtemp(); e = Engine(d, fake=True); e.start(); cl = e2e.Client(e.url); cl.login()
    e2e.wait(lambda: cl.req("api/state")["status"] == "qr"); cl.req("api/sim/link", {"me": "966500000000", "history": {"chats": [{"id": MINE, "name": "ورد التجربة"}], "messages": []}})
    e2e.wait(lambda: cl.req("api/state")["status"] == "connected")
    cl.req("api/sim/channel", {"id": MINE, "name": "ورد التجربة", "invite": "0029VaTESTTESTTEST1234", "followers": 1840, "role": "OWNER",
                                 "posts": [{"text": "وصلنا جوري طازج 🌹", "reactions": [["❤️", 31], ["😍", 5]], "views": 920}, {"text": "تنسيق اليوم", "image": True, "views": 400}]})
    cl.req("api/sim/channel", {"id": OTHER, "name": "قناة أحد ثاني", "invite": "0029VaOTHEROTHEROTHE12", "followers": 99000, "role": "SUBSCRIBER"})
    yield cl, d, e; e.stop()

def test_list_info_posts_and_add_by_link(eng):
    cl, d, e = eng
    j = cl.req("api/channels?refresh=1"); c = j["channels"][0]
    assert c["jid"] == MINE and c["name"] == "ورد التجربة" and c["followers"] == 1840 and c["role"] == "owner"   # discovered from history sync
    assert 1 <= len(j["ideas"]) <= 5 and all(i["template"] for i in j["ideas"]) and len(j["tips"]) >= 4
    p = cl.req("api/channels/posts?jid=" + MINE)
    assert p["live"] and p["posts"][0]["text"] == "وصلنا جوري طازج 🌹" and p["posts"][0]["views"] == 920 and {"e": "❤️", "n": 31} in p["posts"][0]["reactions"]
    assert p["posts"][1]["kind"] == "image"
    a = cl.req("api/channels/add", {"link": "https://whatsapp.com/channel/0029VaOTHEROTHEROTHE12"}); assert a["jid"] == OTHER and a["role"] == "follower"
    q = cl.req("api/channels/qr?jid=" + MINE); assert q["link"].endswith("0029VaTESTTESTTEST1234") and q["qr"].startswith("data:image/png")

def test_publish_needs_confirm_and_own_channel(eng):
    cl, d, e = eng; cl.req("api/channels?refresh=1"); cl.req("api/channels/add", {"link": "0029VaOTHEROTHEROTHE12"})
    for bad in ({"jid": MINE, "kind": "text", "text": "هلا"},                         # no confirm
                {"jid": OTHER, "kind": "text", "text": "هلا", "confirm": True},        # not his channel
                {"jid": MINE, "kind": "image", "mime": "image/gif", "data": PNG, "confirm": True},
                {"jid": MINE, "kind": "poll", "text": "سؤال", "options": ["واحد"], "confirm": True}):
        with pytest.raises(Exception): cl.req("api/channels/publish", bad)
    assert cl.req("api/sim/outbox") == []                                                  # nothing went out
    time.sleep(1.5)
    assert cl.req("api/sim/outbox") == []                                                  # and nothing goes out by itself
    cl.req("api/channels/publish", {"jid": MINE, "kind": "text", "text": "عرض الخميس 🌷 راسلنا على الخاص", "confirm": True})
    cl.req("api/channels/publish", {"jid": MINE, "kind": "image", "mime": "image/png", "data": PNG, "text": "تنسيق اليوم", "confirm": True})
    cl.req("api/channels/publish", {"jid": MINE, "kind": "poll", "text": "وش لونكم المفضل؟", "options": ["أحمر", "أبيض"], "confirm": True})
    out = cl.req("api/sim/outbox"); assert [o["jid"] for o in out] == [MINE] * 3 and [o["kind"] for o in out] == ["text", "image", "poll"] and out[1]["bytes"] > 0
    au = [a for a in cl.req("api/audit") if a["type"] == "channel_post"]; assert len(au) == 3

def test_drafts_reminders_ai_draft_persist(eng):
    cl, d, e = eng
    j = cl.req("api/channels/draft", {"kind": "text", "text": "مسودة عيد 🌹", "idea": "العيد"}); did = j["id"]
    cl.req("api/channels/remind", {"at": int(time.time() * 1000) + 500, "text": "وقت منشور القناة", "draftId": did})
    with pytest.raises(Exception): cl.req("api/channels/remind", {"at": 1000})
    w = cl.req("api/channels/write", {"idea": "ورد اليوم", "kind": "text", "template": "وصلنا ورد 🌹"}); assert w["text"]
    assert cl.req("api/sim/outbox") == []
    e.stop(); e2 = Engine(d, fake=True); e2.start(); c2 = e2e.Client(e2.url); c2.login()
    try:
        j = c2.req("api/channels"); assert j["drafts"][0]["text"] == "مسودة عيد 🌹" and j["channels"][0]["jid"] == MINE
        assert e2e.wait(lambda: any(a["kind"] == "channel" for a in c2.req("api/alerts")), timeout=45)     # reminder → an alert for him; never a post
        assert c2.req("api/sim/outbox") == []
    finally: e2.stop()

def test_log_never_keeps_signal_keys(tmp_path):
    from app.launcher import scrub_log
    p = tmp_path / "engine.log"; p.write_text("2026 ENGINE READY\nClosing session: SessionEntry {\n  _chains: {\n    privKey: <Buffer 01 02>\n  },\n  rootKey: <Buffer aa>\n}\n2026 WA open\n", encoding="utf-8")
    scrub_log(p); t = p.read_text(encoding="utf-8"); assert "privKey" not in t and "rootKey" not in t and "SessionEntry" not in t and "WA open" in t and "ENGINE READY" in t

def test_engine_console_drops_session_dumps(eng):
    cl, d, e = eng; cl.req("api/sim/incoming", {"jid": "966500000501@s.whatsapp.net", "text": "هلا", "name": "عميل"}); cl.req("api/sim/leak", {}); time.sleep(0.5)
    log = Path(e.log_path).read_text(encoding="utf-8")
    assert " IN type=notify" in log and "privKey" not in log and "SessionEntry" not in log and "Closing session" not in log and "SAFE-MARKER" in log
