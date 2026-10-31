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
    if os.environ.get("WAE_NO_REEXEC") or "--smoke" in sys.argv or "--qr-test" in sys.argv or "--ai-test" in sys.argv or any(a.startswith("--persist-test") for a in sys.argv) or getattr(sys, "frozen", False):
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

def smoke():
    """Self-test of the packaged app: brain + Node engine in simulator mode, full scenario, restart, persistence."""
    import tempfile
    from app.launcher import Engine
    from app import e2e
    from app.brain import think
    b = think("ابي اطلب ٢ بوكيه توليب بكره حي الفيصلية الدمام")
    assert b["kind"] == "order_confirm" and b["total"] == 440, b
    d = tempfile.mkdtemp(prefix="wae-smoke-"); lines = []
    eng = Engine(d, fake=True)
    try:
        eng.start(); e2e.scenario(eng.url, log=lines.append)
    finally:
        eng.stop()
    eng = Engine(d, fake=True)
    try:
        eng.start(); e2e.verify_persisted(eng.url, log=lines.append)
    finally:
        eng.stop()
    msg = f"SMOKE OK v{config.APP_VERSION}: brain={b['kind']} total={b['total']}\n" + "\n".join(lines)
    try:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True); (config.LOG_DIR / "smoke.txt").write_text(msg, encoding="utf-8")
    except Exception: pass
    try: print(msg, flush=True)
    except Exception: pass
    return 0

def single_instance(data_dir):
    """If the app is already running, return its URL (we just open another window on it)."""
    import json, urllib.request
    lock = data_dir / "running.json"
    try:
        info = json.loads(lock.read_text(encoding="utf-8"))
        with urllib.request.urlopen(info["url"] + "healthz", timeout=2) as r:
            if json.loads(r.read()).get("ok"): return info["url"], lock
    except Exception: pass
    return None, lock

def run_app(force_browser=False):
    import json
    from app.launcher import Engine, user_data_dir
    data_dir = user_data_dir(); data_dir.mkdir(parents=True, exist_ok=True)
    url, lock = single_instance(data_dir); eng = None
    if not url:
        eng = Engine(data_dir); url = eng.start()
        lock.write_text(json.dumps({"url": url}), encoding="utf-8")
        startup_log(f"engine started, data in {data_dir} (token not logged)")
    def shutdown():
        if eng:
            try: eng.stop()
            except Exception: traceback.print_exc()
            try: lock.unlink()
            except Exception: pass
    try:
        if force_browser:
            raise RuntimeError("browser mode requested")
        import webview  # pywebview -> Edge WebView2 on Windows 10/11
        win = webview.create_window(f"{config.APP_NAME} {config.APP_VERSION}", url, width=1440, height=900, min_size=(1100, 680),
                                    background_color="#FFFFFF", text_select=True)
        start_tray(win, shutdown)
        webview.start(private_mode=False, storage_path=str(data_dir / "webview"))
        startup_log("window closed")
    except Exception as e:
        startup_log(f"native window unavailable ({e}); opening default browser")
        import webbrowser, time
        webbrowser.open(url)
        print("\n  الواجهة مفتوحة في المتصفح.\n  اقفل هالنافذة لإيقاف البرنامج (Ctrl+C).", flush=True)
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            pass
    finally:
        shutdown()

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

def persist_test(mode):
    """CI check that user data survives close/reopen and installer upgrade/uninstall. Uses the real user data folder."""
    from app.launcher import Engine, user_data_dir
    from app import e2e
    eng = Engine(user_data_dir(), fake=True); eng.start()
    try:
        if mode == "write": e2e.scenario(eng.url, log=print)
        else: e2e.verify_persisted(eng.url, log=print)
    finally: eng.stop()
    msg = f"PERSIST {mode.upper()} OK in {user_data_dir()}"
    print(msg, flush=True)
    try: config.LOG_DIR.mkdir(parents=True, exist_ok=True); (config.LOG_DIR / f"persist-{mode}.txt").write_text(msg, encoding="utf-8")
    except Exception: pass
    return 0

def qr_test(limit=60):
    """CI/support check: start the REAL engine (no simulator) in a temp folder and require a real WhatsApp QR within `limit` seconds."""
    import tempfile, time
    from app.launcher import Engine
    from app import e2e
    d = tempfile.mkdtemp(prefix="wae-qr-"); eng = Engine(d, fake=False); t0 = time.time(); st = {}
    try:
        eng.start(); c = e2e.Client(eng.url); c.login()
        while time.time() - t0 < limit:
            st = c.req("api/state")
            if st.get("status") == "qr" and str(st.get("qr") or "").startswith("data:image/png;base64,"): break
            time.sleep(1)
        ok = st.get("status") == "qr" and bool(st.get("qr"))
    finally: eng.stop()
    log = ""
    try: log = eng.log_path.read_text(encoding="utf-8", errors="replace")[-3000:]
    except Exception: pass
    msg = (f"QR TEST {'OK' if ok else 'FAILED'} v{config.APP_VERSION} after {time.time()-t0:.1f}s status={st.get('status')} "
           f"qrlen={len(st.get('qr') or '')} error={st.get('error')}\n--- engine log ---\n{log}")
    print(msg, flush=True)
    try: config.LOG_DIR.mkdir(parents=True, exist_ok=True); (config.LOG_DIR / "qr-test.txt").write_text(msg, encoding="utf-8")
    except Exception: pass
    return 0 if ok else 3

def ai_test():
    from app import ai_check
    o = ai_check.run(); msg = ai_check.report(o); print(msg, flush=True)
    try: config.LOG_DIR.mkdir(parents=True, exist_ok=True); (config.LOG_DIR / "ai-test.txt").write_text(msg, encoding="utf-8")
    except Exception: pass
    return 0 if o["ok"] else 4

def main():
    if "--ai-test" in sys.argv:
        try: return ai_test()
        except Exception:
            startup_log("AI TEST FAILED:\n" + traceback.format_exc()); traceback.print_exc(); return 1
    if "--qr-test" in sys.argv:
        try: return qr_test()
        except Exception:
            startup_log("QR TEST FAILED:\n" + traceback.format_exc()); traceback.print_exc(); return 1
    for mode in ("write", "check"):
        if f"--persist-test={mode}" in sys.argv:
            try: return persist_test(mode)
            except Exception:
                startup_log("PERSIST TEST FAILED:\n" + traceback.format_exc()); traceback.print_exc(); return 1
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
