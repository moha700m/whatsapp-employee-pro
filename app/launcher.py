"""Starts the local brain + the WhatsApp engine (bundled Node) and returns the UI URL.
All user data lives in the per-user data folder (survives restarts, upgrades and uninstall)."""
import json, os, secrets, shutil, socket, subprocess, sys, time, urllib.request
from pathlib import Path
from app import config
from app.brain_server import BrainServer

def user_data_dir() -> Path:
    if os.environ.get("WAE_DATA"): return Path(os.environ["WAE_DATA"])
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"): return Path(os.environ["LOCALAPPDATA"]) / "WhatsAppEmployee"
    return config.DATA_DIR

def find_node() -> str:
    for p in (config.BASE_DIR / "node" / "node.exe", config.BASE_DIR / "node" / "bin" / "node", config.BASE_DIR / "node" / "node"):
        if p.exists(): return str(p)
    n = shutil.which("node")
    if not n: raise RuntimeError("Node runtime not found (expected node\\node.exe next to the app)")
    return n

def engine_dir() -> Path:
    for p in (config.BASE_DIR / "engine", Path(__file__).resolve().parent.parent / "engine"):
        if (p / "server.js").exists(): return p
    raise RuntimeError("engine folder not found")

def free_port(preferred=8796):
    for port in (preferred, 0):
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", port)); return s.getsockname()[1]
        except OSError: continue
        finally: s.close()

def http_json(url, data=None, headers=None, timeout=5):
    req = urllib.request.Request(url, data=None if data is None else json.dumps(data).encode(), headers={"content-type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read().decode("utf-8"))

class Engine:
    def __init__(self, data_dir=None, fake=False, port=None, extra_env=None, log_path=None):
        self.data = Path(data_dir or user_data_dir()) / "wa"; self.data.mkdir(parents=True, exist_ok=True)
        self.fake, self.port, self.extra = fake, port, extra_env or {}
        self.token = secrets.token_urlsafe(16); self.brain = BrainServer(secrets.token_hex(16)); self.proc = None
        self.log_path = Path(log_path) if log_path else (Path(data_dir or user_data_dir()) / "logs" / "engine.log")
        self.url = None

    def start(self, timeout=40):
        self.brain.start(); port = self.port or free_port()
        env = dict(os.environ, DATA_DIR=str(self.data), PORT=str(port), TOKEN=self.token, BRAIN_URL=self.brain.url, BRAIN_KEY=self.brain.key,
                   APP_VERSION=config.APP_VERSION, EXIT_WITH_STDIN="1", **({"FAKE_WA": "1"} if self.fake else {}), **self.extra)
        self.log_path.parent.mkdir(parents=True, exist_ok=True); self._log = open(self.log_path, "a", encoding="utf-8")
        flags = 0x08000000 if os.name == "nt" else 0       # CREATE_NO_WINDOW
        self.proc = subprocess.Popen([find_node(), str(engine_dir() / "server.js")], cwd=str(engine_dir()), env=env, stdin=subprocess.PIPE,
                                     stdout=self._log, stderr=subprocess.STDOUT, creationflags=flags)
        self.url = f"http://127.0.0.1:{port}/{self.token}/"
        end = time.time() + timeout
        while time.time() < end:
            if self.proc.poll() is not None: raise RuntimeError(f"engine exited with code {self.proc.returncode} (see {self.log_path})")
            try:
                if http_json(self.url + "healthz", timeout=2).get("ok"): return self.url
            except Exception: time.sleep(0.3)
        raise RuntimeError("engine did not start in time")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try: self.proc.stdin.close()                    # engine saves and exits when stdin closes
            except Exception: pass
            try: self.proc.wait(8)
            except subprocess.TimeoutExpired: self.proc.terminate(); self.proc.wait(5)
        try: self.brain.stop()
        except Exception: pass
        try: self._log.close()
        except Exception: pass
