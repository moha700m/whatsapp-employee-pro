import json, time, urllib.request, pytest
from app.core.service import EmployeeService
from app.web.api import Api, ApiError
from app.web.server import UIServer
from app.core.kill_switch import KILL_SWITCH

@pytest.fixture
def api(repo):
    return Api(EmployeeService(repo))

def test_dispatch_rejects_private(api):
    for m in ("_need_runner", "call", "nope"):
        with pytest.raises(ApiError): api.call(m)

def test_status_without_runner(api):
    s = api.call("status"); assert s["wa"] == "disconnected" and s["needs"] == 0 and "events" in s

def test_crm_and_analyze(api):
    r = api.call("analyze", {"text": "سارة: كم السعر؟"}); assert r["reply_id"]
    assert api.call("reply_status", {"id": r["reply_id"], "status": "approved"})
    cs = api.call("customers"); assert cs[0]["name"] == "سارة"
    api.call("customer_update", {"id": cs[0]["id"], "fields": {"notes": "VIP"}})
    assert api.call("customers", {"q": "سار"})[0]["notes"] == "VIP"
    assert api.call("pipeline")["Interested"]
    api.call("customer_delete", {"id": cs[0]["id"]}); assert api.call("customers") == []

def test_workflow_roundtrip(api):
    d = api.call("workflow_get"); assert len(d["wf"]["rules"]) == 6 and d["settings"]["auto_reply_enabled"] is False
    pid = api.call("product_save", {"title": "باقة", "price": "100 ريال"})
    d["wf"]["business"]["name"] = "متجر"
    d = api.call("workflow_save", {"wf": d["wf"], "settings": {"min_delay": "3", "skip_groups": False}})
    assert d["wf"]["business"]["name"] == "متجر" and d["settings"]["min_delay"] == 3 and d["settings"]["skip_groups"] is False
    with pytest.raises(ApiError): api.call("workflow_save", {"settings": {"min_delay": -1}})
    ex = api.call("workflow_export"); api.call("workflow_reset")
    assert api.call("workflow_import", {"text": ex})["wf"]["business"]["name"] == "متجر"
    assert api.call("simulate", {"text": "كم سعر باقة"})["reply"]
    api.call("product_delete", {"id": pid})

def test_start_requires_enabled_and_kill(api):
    with pytest.raises(ApiError): api.call("emp_start")
    assert api.call("kill_toggle") is True and KILL_SWITCH.engaged
    assert api.call("kill_toggle") is False

def test_campaign_followup_logs(api):
    with pytest.raises(ApiError): api.call("campaign_add", {"name": " ", "segment": "Interested", "message": ""})
    api.call("campaign_add", {"name": "رمضان", "segment": "Interested", "message": "x"})
    assert api.call("campaigns")[0]["name"] == "رمضان" and api.call("logs")
    assert "stats" in api.call("overview") and api.call("backup")

def test_http_bridge_token(api):
    srv = UIServer(api); url = srv.start()
    try:
        def post(m, body, tok):
            req = urllib.request.Request(url.split("?")[0] + "api/" + m, data=json.dumps(body).encode(), headers={"X-Token": tok, "Content-Type": "application/json"})
            try: return json.loads(urllib.request.urlopen(req, timeout=5).read())
            except urllib.error.HTTPError as e: return {"status": e.code}
        assert post("status", {}, "bad") == {"status": 403}
        assert post("status", {}, srv.token)["ok"]
        r = post("simulate", {"text": ""}, srv.token); assert r["ok"] is False and r["error"]
        assert srv.token in urllib.request.urlopen(url, timeout=5).read().decode()
        base = srv.base
        with pytest.raises(urllib.error.HTTPError) as e: urllib.request.urlopen(base + "app.js", timeout=5)
        assert e.value.code == 403                                   # static files need the token too
        ck = {"Cookie": "wae_t=" + srv.token}
        assert urllib.request.urlopen(urllib.request.Request(base + "fonts/Tajawal-Regular.ttf", headers=ck), timeout=5).status == 200
        with pytest.raises(urllib.error.HTTPError): urllib.request.urlopen(urllib.request.Request(base + "../main.py", headers=ck), timeout=5)
        # CSRF: right token but foreign Origin, or form content-type -> refused
        req = urllib.request.Request(base + "api/status", data=b"{}", headers={"X-Token": srv.token, "Content-Type": "application/json", "Origin": "http://evil.example"})
        with pytest.raises(urllib.error.HTTPError): urllib.request.urlopen(req, timeout=5)
        req = urllib.request.Request(base + "api/status", data=b"{}", headers={"X-Token": srv.token, "Content-Type": "text/plain"})
        with pytest.raises(urllib.error.HTTPError): urllib.request.urlopen(req, timeout=5)
        req = urllib.request.Request(base + "api/status", data=b"{}", headers={"X-Token": srv.token, "Content-Type": "application/json", "Host": "evil.example"})
        with pytest.raises(urllib.error.HTTPError): urllib.request.urlopen(req, timeout=5)   # DNS rebinding
    finally:
        srv.stop()

def test_runner_snapshot(repo):
    from app.automation.runner import EmployeeRunner
    from tests.test_auto_reply import FakeDriver
    r = EmployeeRunner(repo, driver_factory=FakeDriver); api = Api(EmployeeService(repo), r)
    api.call("wa_open"); time.sleep(3)
    s = api.call("status"); assert s["wa"] == "connected" and s["wa_ar"] == "متصل"
    assert any("متصل" in e["text"] for e in s["events"]); r.shutdown()
