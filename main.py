"""Entry point.
  python main.py            -> start app (native window via pywebview/WebView2, else default browser)
  python main.py --browser  -> force browser mode
  python main.py --smoke    -> headless self-test (no UI)
"""
import os, sys, traceback
os.environ.setdefault("PYTHONUTF8", "1")
for stream in (sys.stdout, sys.stderr):          # Arabic in Windows console (pythonw has none)
    try: stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

from app import config

def ensure_venv():
    """If launched with another Python (e.g. double-clicking main.py with the system Python),
    re-launch with the app's own .venv interpreter so all packages are present."""
    if os.environ.get("WAE_NO_REEXEC") or "--smoke" in sys.argv or getattr(sys, "frozen", False):
        return
    venv = config.BASE_DIR / ".venv"
    exe_dir = venv / ("Scripts" if os.name == "nt" else "bin")
    target = exe_dir / ("python.exe" if os.name == "nt" else "python")
    if not target.exists():
        return
    try:
        if os.path.samefile(sys.prefix, venv):
            return
    except OSError:
        pass
    if os.name == "nt" and os.path.basename(sys.executable).lower() == "pythonw.exe" and (exe_dir / "pythonw.exe").exists():
        target = exe_dir / "pythonw.exe"
    import subprocess
    env = dict(os.environ, WAE_NO_REEXEC="1")
    startup_log(f"re-launching with venv python: {target} (was {sys.executable})")
    proc = subprocess.Popen([str(target), str(config.BASE_DIR / "main.py"), *sys.argv[1:]], env=env, cwd=str(config.BASE_DIR))
    sys.exit(proc.wait() if sys.stdout else 0)

def startup_log(msg):
    try:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(config.LOG_DIR / "startup.log", "a", encoding="utf-8") as f:
            from datetime import datetime
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")
    except Exception:
        pass
    try: print(msg, flush=True)
    except Exception: pass

def build(db_path=None):
    from app.db.database import Database
    from app.db.repository import Repository
    from app.core.service import EmployeeService
    return EmployeeService(Repository(Database(db_path)))

def smoke():
    import tempfile
    svc = build(os.path.join(tempfile.mkdtemp(), "smoke.db"))
    svc.repo.add_business_info("منتج", "باقة التصميم", "تصميم شعار وهوية", "500 ريال")
    r = svc.analyze_text("أحمد: السلام عليكم\nأحمد: كم سعر باقة التصميم؟\nأنا: هلا")
    assert r["classification"] in ("Interested", "Hot Lead"), r
    from app.web.api import Api
    from app.web.server import UIServer
    import json, urllib.request
    srv = UIServer(Api(svc)); url = srv.start()
    html = urllib.request.urlopen(url, timeout=5).read().decode("utf-8")
    assert "موظف واتساب" in html and srv.token in html
    req = urllib.request.Request(url.split("?")[0] + "api/overview", data=b"{}", headers={"X-Token": srv.token, "Content-Type": "application/json"})
    assert json.loads(urllib.request.urlopen(req, timeout=5).read())["ok"]
    srv.stop()
    from app.brain import think
    b = think("ابي اطلب ٢ بوكيه توليب بكره حي الفيصلية الدمام")
    assert b["kind"] == "order_confirm" and b["total"] == 440, b
    msg = f"SMOKE OK v{config.APP_VERSION}: {r['classification']} | brain={b['kind']} total={b['total']}"
    try:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True); (config.LOG_DIR / "smoke.txt").write_text(msg, encoding="utf-8")
    except Exception: pass
    try: print(msg, flush=True)
    except Exception: pass
    return 0

def run_app(force_browser=False):
    from app.core.logger import log_activity
    from app.web.api import Api
    from app.web.server import UIServer
    from app.automation.runner import EmployeeRunner
    svc = build()
    log_activity(svc.repo.db, "app_start")
    runner = EmployeeRunner(svc.repo)
    import threading, time as _t
    def housekeeping():   # daily backup + data retention, all local
        from app.core import pro
        from app.core.settings import AutoReplySettings
        while True:
            try:
                st = AutoReplySettings.load(svc.repo)
                if st.backup_daily: pro.backup_if_due(svc.repo.db, svc.repo)
                pro.apply_retention(svc.repo, st.retention_days)
            except Exception:
                traceback.print_exc()
            _t.sleep(3600)
    threading.Thread(target=housekeeping, daemon=True, name="housekeeping").start()
    srv = UIServer(Api(svc, runner)); url = srv.start()
    startup_log(f"UI server at {srv.base} (token not logged)")
    (config.DATA_DIR / "first_run_ok").write_text("ok", encoding="utf-8")
    def shutdown():
        try:
            runner.shutdown(); svc.repo.db.backup("on-exit"); log_activity(svc.repo.db, "app_close")
        except Exception:
            traceback.print_exc()
    try:
        if force_browser:
            raise RuntimeError("browser mode requested")
        import webview  # pywebview -> Edge WebView2 on Windows 10/11
        win = webview.create_window(f"{config.APP_NAME} {config.APP_VERSION}", url, width=1360, height=860, min_size=(1000, 650),
                                    background_color="#F6F7F4", text_select=True)
        start_tray(win, shutdown)
        webview.start()
        startup_log("window closed")
    except Exception as e:
        startup_log(f"native window unavailable ({e}); opening default browser")
        import webbrowser, time
        webbrowser.open(url)
        print("\n  الواجهة مفتوحة في المتصفح:", url, "\n  اقفل هالنافذة لإيقاف البرنامج (Ctrl+C).", flush=True)
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            pass
    finally:
        shutdown(); srv.stop()

def start_tray(win, on_quit):
    """Optional system-tray icon (pystray). Silently skipped if pystray/Pillow are missing."""
    try:
        import pystray
        from PIL import Image
    except Exception:
        return None
    try:
        img = Image.open(str(config.BASE_DIR / "app" / "web" / "static" / "icon.png")) if (config.BASE_DIR / "app" / "web" / "static" / "icon.png").exists() \
            else Image.open(os.path.join(os.path.dirname(__file__), "app", "web", "static", "icon.png"))
        def show(icon, item):
            try: win.show(); win.restore()
            except Exception: pass
        def quit_(icon, item):
            icon.stop()
            try: win.destroy()
            except Exception: pass
        icon = pystray.Icon("wa-employee", img, f"{config.APP_NAME} {config.APP_VERSION}",
                            pystray.Menu(pystray.MenuItem("إظهار البرنامج", show, default=True), pystray.MenuItem("خروج", quit_)))
        icon.run_detached()
        return icon
    except Exception as e:
        startup_log(f"tray unavailable: {e}")
        return None

def main():
    if "--smoke" in sys.argv:
        try:
            return smoke()
        except Exception:
            startup_log("SMOKE FAILED:\n" + traceback.format_exc()); traceback.print_exc(); return 1
    ensure_venv()
    config.secure_data_dir()
    try:
        startup_log(f"start python={sys.version.split()[0]} exe={sys.executable} base={config.BASE_DIR}")
        run_app("--browser" in sys.argv)
        return 0
    except Exception:
        startup_log("FATAL:\n" + traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())
