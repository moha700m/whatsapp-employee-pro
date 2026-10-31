"""Real end-to-end: Python brain + Node engine (simulated WhatsApp). Link, history, manual send, auto-reply, persistence."""
import json, shutil, tempfile, pytest
from pathlib import Path
from app.launcher import Engine
from app import e2e

pytestmark = pytest.mark.skipif(not shutil.which("node") and not Path("node").exists(), reason="node runtime required")
ENGINE = Path(__file__).resolve().parent.parent / "engine"
needs_modules = pytest.mark.skipif(not (ENGINE / "node_modules" / "express").exists(), reason="run npm ci in engine/")

@needs_modules
def test_full_flow_then_close_and_reopen_keeps_everything():
    d = tempfile.mkdtemp(); e = Engine(d, fake=True); e.start()
    try: e2e.scenario(e.url, log=lambda *_: None)
    finally: e.stop()
    store = json.loads((Path(d) / "wa" / "store.json").read_text(encoding="utf-8"))
    assert store["settings"]["autoReply"]["enabled"] is True and len(store["chats"]) >= 5
    e = Engine(d, fake=True); e.start()
    try: assert e2e.verify_persisted(e.url, log=lambda *_: None)
    finally: e.stop()

@needs_modules
def test_corrupt_store_recovers_from_backup():
    d = tempfile.mkdtemp(); e = Engine(d, fake=True); e.start()
    try:
        c = e2e.Client(e.url); c.login(); c.req("api/settings", {"shopName": "محل النسخة"})
    finally: e.stop()
    e = Engine(d, fake=True); e.start(); e.stop()                       # startup makes today's backup
    (Path(d) / "wa" / "store.json").write_text("{broken", encoding="utf-8")
    e = Engine(d, fake=True); e.start()
    try:
        c = e2e.Client(e.url); c.login(); assert c.req("api/crm")["settings"]["shopName"] == "محل النسخة"
    finally: e.stop()

@needs_modules
def test_employee_off_by_default_and_send_requires_confirm():
    d = tempfile.mkdtemp(); e = Engine(d, fake=True); e.start()
    try:
        c = e2e.Client(e.url); c.login(); s = c.req("api/crm")["settings"]
        assert s["autoReply"]["enabled"] is False and s["tourDone"] is False
        assert c.req("api/state")["employee"]["enabled"] is False
        c.req("api/sim/link", {"me": "966500000000", "history": e2e.history(0)})
        c.req("api/send", {"jid": "966511110001@s.whatsapp.net", "text": "x"}, expect=400)
        c.csrf = "wrong"; c.req("api/send", {"jid": "966511110001@s.whatsapp.net", "text": "x", "confirm": True}, expect=403)
    finally: e.stop()

@needs_modules
def test_engine_rejects_requests_without_token():
    d = tempfile.mkdtemp(); e = Engine(d, fake=True); e.start()
    try:
        import urllib.request, urllib.error
        root = e.url.rsplit("/", 2)[0] + "/"
        with pytest.raises(urllib.error.HTTPError): urllib.request.urlopen(root + "api/state", timeout=3)
    finally: e.stop()
