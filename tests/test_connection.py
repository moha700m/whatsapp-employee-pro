"""Connection states + in-app QR capture against a mock WhatsApp Web page (real Playwright driver)."""
import threading, time
from pathlib import Path
import pytest
pw = pytest.importorskip("playwright.sync_api")
from app.automation.whatsapp_web import WhatsAppWebAgent
from app.automation.runner import EmployeeRunner
from app.core import deps

MOCK = (Path(__file__).parent / "fixtures/fake_whatsapp_states.html").as_uri()

@pytest.fixture
def page():
    try:
        p = pw.sync_playwright().start(); b = p.chromium.launch()
    except Exception as e:
        pytest.skip(f"no browser: {e}")
    pg = b.new_page(); pg.goto(MOCK)
    yield pg
    b.close(); p.stop()

def test_states_and_qr_capture(page):
    a = WhatsAppWebAgent(); a.page = page
    assert a.connection_state() == "qr"
    q1 = a.capture_qr(); assert q1 and q1[:4] == b"\x89PNG"
    page.wait_for_timeout(2300); q2 = a.capture_qr()
    assert q2 != q1                                   # WhatsApp rotates the QR -> new capture
    page.evaluate("conflict()"); assert a.connection_state() == "conflict"
    assert a.use_here() and a.connection_state() == "connected"
    assert a.profile_info() == "متجر ليان"
    page.evaluate("phoneOffline()"); assert a.connection_state() == "phone_offline"
    assert a.capture_qr() is None

def mock_factory(holder, delay_ms):
    def make():   # runs inside the runner thread (Playwright sync objects are thread-bound)
        p = pw.sync_playwright().start(); b = p.chromium.launch()
        pg = b.new_page(); pg.goto(MOCK + f"#autologin={delay_ms}")
        holder.update(p=p, b=b)
        a = WhatsAppWebAgent(); a.page = pg; return a
    return make

def test_runner_qr_then_connected(repo):
    holder = {}
    r = EmployeeRunner(repo, driver_factory=mock_factory(holder, 4000))
    try:
        r.open_whatsapp()
        for _ in range(40):
            if r.snapshot()["qr"]: break
            time.sleep(0.25)
        s = r.snapshot(); assert s["wa"] == "qr" and s["qr"].startswith("data:image/png;base64,") and s["wa_ar"] == "ينتظرك تمسح QR"
        for _ in range(60):
            if r.snapshot()["wa"] == "connected": break
            time.sleep(0.25)
        s = r.snapshot(); assert s["wa"] == "connected" and s["qr"] == "" and s["profile"] == "متجر ليان"
        texts = [e["text"] for e in s["events"]]
        assert any("QR" in t for t in texts) and any("متصل" in t for t in texts)
    finally:
        r.shutdown()

def test_missing_playwright_reported(repo, monkeypatch):
    def boom():
        raise ModuleNotFoundError("No module named 'playwright'", name="playwright")
    r = EmployeeRunner(repo, driver_factory=boom)
    try:
        r.open_whatsapp(); time.sleep(1)
        s = r.snapshot(); assert s["wa"] == "missing_deps" and "playwright" in s["error"]
        assert any("Playwright" in e["text"] for e in s["events"])
    finally:
        r.shutdown()

def test_api_blocks_open_when_missing(repo, monkeypatch):
    from app.core.service import EmployeeService
    from app.web.api import Api, ApiError
    monkeypatch.setattr(deps, "missing", lambda: ["playwright"])
    api = Api(EmployeeService(repo), runner=object())
    with pytest.raises(ApiError, match="Playwright"): api.call("wa_open")
    assert Api(EmployeeService(repo)).call("status")["missing"] == ["playwright"]

def test_fixer_runs_pip_in_venv(monkeypatch):
    calls = []
    class R:  returncode = 0; stdout = "ok"; stderr = ""
    f = deps.Fixer(runner=lambda cmd, **k: calls.append(cmd) or R())
    monkeypatch.setattr(deps, "missing", lambda: [])
    f.start()
    for _ in range(20):
        if f.state != "running": break
        time.sleep(0.05)
    assert f.state == "done" and calls[0][1:4] == ["-m", "pip", "install"] and calls[0][-1].endswith("requirements.txt")
    class Bad: returncode = 1; stdout = ""; stderr = "network"
    g = deps.Fixer(runner=lambda cmd, **k: Bad()); g.start(); time.sleep(0.2); assert g.state == "failed" and "network" in g.log

def test_ensure_venv_reexec(tmp_path, monkeypatch):
    import main, subprocess, sys, os
    from app import config
    monkeypatch.setattr(config, "BASE_DIR", tmp_path)
    monkeypatch.delenv("WAE_NO_REEXEC", raising=False)
    monkeypatch.setattr(sys, "argv", ["main.py"])
    main.ensure_venv()                                   # no venv -> no-op
    vdir = tmp_path / ".venv" / ("Scripts" if os.name == "nt" else "bin"); vdir.mkdir(parents=True)
    (vdir / ("python.exe" if os.name == "nt" else "python")).write_text("")
    seen = {}
    class P:
        def __init__(self, args, env, cwd): seen.update(args=args, env=env)
        def wait(self): return 0
    monkeypatch.setattr(subprocess, "Popen", P)
    with pytest.raises(SystemExit):
        main.ensure_venv()
    assert seen["args"][0].startswith(str(vdir)) and seen["env"]["WAE_NO_REEXEC"] == "1"
