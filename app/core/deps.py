"""Dependency check + one-click repair (pip install into the app's own .venv)."""
import importlib.util, subprocess, sys, threading
from pathlib import Path
from app import config

REQUIRED = {"playwright": "playwright", "webview": "pywebview"}

def venv_python():
    win = config.BASE_DIR / ".venv" / "Scripts" / "python.exe"
    nix = config.BASE_DIR / ".venv" / "bin" / "python"
    return win if win.exists() else nix if nix.exists() else Path(sys.executable)

def in_venv():
    return Path(sys.prefix).resolve() == (config.BASE_DIR / ".venv").resolve()

def missing():
    return [pkg for mod, pkg in REQUIRED.items() if importlib.util.find_spec(mod) is None]

class Fixer:
    def __init__(self, runner=subprocess.run):
        self.state = "idle"; self.log = ""; self._run = runner
    def start(self):
        if self.state == "running":
            return False
        self.state = "running"; self.log = ""
        threading.Thread(target=self._work, daemon=True).start()
        return True
    def _work(self):
        py = str(venv_python())
        steps = [[py, "-m", "pip", "install", "--disable-pip-version-check", "-r", str(config.BASE_DIR / "requirements.txt")]]
        try:
            for cmd in steps:
                r = self._run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.log += (r.stdout or "")[-3000:] + (r.stderr or "")[-3000:]
                if r.returncode != 0:
                    self.state = "failed"; return
            importlib.invalidate_caches()
            self.state = "done" if not missing() else "restart"
        except Exception as e:
            self.log += str(e); self.state = "failed"

FIXER = Fixer()
