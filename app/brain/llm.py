"""Built-in local AI: llama.cpp `llama-server` + Qwen2.5-1.5B-Instruct (Q4_K_M), bundled with the app.
Light by design: starts only when first needed, few threads, small context, one slot, unloads after idle.
Never downloads anything. If RAM < 6 GB, files are missing, or anything fails, callers fall back to the rule brain."""
import json, os, socket, subprocess, sys, threading, time, urllib.request
from pathlib import Path

MIN_RAM_GB = 5.5   # a «6 GB» PC reports ~5.8

def log(msg):
    """One line in engine.log (path set by the launcher); never prompts or customer text."""
    f = os.environ.get("WAE_LOG_FILE")
    if not f: return
    try:
        with open(f, "a", encoding="utf-8") as h: h.write(time.strftime("%Y-%m-%dT%H:%M:%S") + " LLM " + msg + "\n")
    except Exception: pass
IDLE_UNLOAD_SEC = 10 * 60

def ram_gb():
    if os.environ.get("WAE_FAKE_RAM_GB"): return float(os.environ["WAE_FAKE_RAM_GB"])   # tests: simulate a small PC
    try:
        if os.name == "nt":
            import ctypes
            class M(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("avail", ctypes.c_ulonglong),
                            ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("x", ctypes.c_ulonglong)]
            m = M(); m.l = ctypes.sizeof(M); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)); return m.total / 2**30
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"): return int(line.split()[1]) / 2**20
    except Exception: pass
    return 0.0

def rss_mb(pid):
    """Resident memory of a process in MB (no psutil)."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("a", ctypes.c_size_t), ("b", ctypes.c_size_t), ("c", ctypes.c_size_t), ("d", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
            h = ctypes.windll.kernel32.OpenProcess(0x1000 | 0x0010, False, pid); m = PMC(); m.cb = ctypes.sizeof(PMC)
            ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(m), m.cb); ctypes.windll.kernel32.CloseHandle(h); return m.WorkingSetSize / 2**20
        for line in open(f"/proc/{pid}/status"):
            if line.startswith("VmRSS"): return int(line.split()[1]) / 1024
    except Exception: pass
    return 0.0

def _dirs():
    out = []
    if os.environ.get("WAE_LLM_DIR"): out.append(Path(os.environ["WAE_LLM_DIR"]))
    base = Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "frozen", False) else None
    exe_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    out += [exe_dir / "llm"] + ([base / "llm"] if base else [])
    return out

def find_files():
    for d in _dirs():
        exe = next((p for p in (d / "llama-server.exe", d / "llama-server", d / "bin" / "llama-server") if p.exists()), None)
        model = next(iter(sorted(d.glob("*.gguf"))), None) if d.exists() else None
        if exe and model: return exe, model
    return None, None

class LocalLLM:
    def __init__(self, threads=None, ctx=2048, idle=IDLE_UNLOAD_SEC):
        self.exe, self.model = find_files()
        self.ram = round(ram_gb(), 1)
        self.threads = threads or max(2, min(4, (os.cpu_count() or 4) // 2))
        self.ctx, self.idle = ctx, idle
        self.proc = None; self.port = None; self.state = "idle"; self.error = ""; self.last = 0.0; self.lock = threading.Lock(); self.slot = threading.Semaphore(1)
        self.stats = {"calls": 0, "fails": 0, "avg_ms": 0, "last_ms": 0, "load_ms": 0}
        threading.Thread(target=self._reaper, daemon=True).start()
        ok, why = self.available()
        log(f"init exe={'found' if self.exe else 'MISSING'} model={self.model.name if self.model else 'MISSING'} dirs={[str(d) for d in _dirs()]} ram={self.ram}GB threads={self.threads} available={ok} {why}")

    def available(self):
        if not self.exe or not self.model: return False, "ملفات الذكاء غير موجودة في هذا الإصدار"
        if self.ram and self.ram < MIN_RAM_GB: return False, f"ذاكرة الجهاز {self.ram:g} جيجا (أقل من {MIN_RAM_GB:g}) — نستخدم المساعد الخفيف"
        if self.stats["fails"] >= 5 and self.state == "error": return False, "تعطل أكثر من مرة — نستخدم المساعد الخفيف"
        return True, ""

    def status(self):
        ok, why = self.available()
        return {"available": ok, "reason": why, "state": self.state if ok else "unavailable", "ram_gb": self.ram, "threads": self.threads,
                "model": self.model.name if self.model else "", "rss_mb": round(rss_mb(self.proc.pid)) if self.proc and self.proc.poll() is None else 0, **self.stats}

    def _free_port(self):
        s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

    def ensure(self, wait=120):
        ok, why = self.available()
        if not ok: raise RuntimeError(why)
        with self.lock:
            if self.proc and self.proc.poll() is None and self.state == "ready": return
            self.state = "loading"; t0 = time.time(); self.port = self._free_port()
            args = [str(self.exe), "-m", str(self.model), "--host", "127.0.0.1", "--port", str(self.port), "-c", str(self.ctx), "-t", str(self.threads),
                    "-np", "1", "-ngl", "0", "--no-webui", "--log-disable"]
            flags = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
            log(f"start port={self.port} exe={self.exe}")
            self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, creationflags=flags)
            while time.time() - t0 < wait:
                if self.proc.poll() is not None: self.state = "error"; self.error = f"exit {self.proc.returncode}"; self.stats["fails"] += 1; log(f"FAILED exit={self.proc.returncode}"); raise RuntimeError("الذكاء ما اشتغل")
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=2) as r:
                        if r.status == 200: self.state = "ready"; self.stats["load_ms"] = int((time.time() - t0) * 1000); self.last = time.time(); log(f"ready in {self.stats['load_ms']}ms"); return
                except Exception: pass
                time.sleep(0.4)
            self.stop(); self.state = "error"; self.stats["fails"] += 1; log(f"FAILED start timeout {wait}s"); raise RuntimeError("الذكاء تأخر في التشغيل")

    def chat(self, messages, max_tokens=160, temperature=0.5, timeout=60, json_mode=False, wait=30):
        """One request at a time (CPU). If the model is busy longer than `wait` seconds we give up → caller uses the rule brain (UI never hangs)."""
        if not self.slot.acquire(timeout=wait): log(f"busy (waited {wait}s)"); raise RuntimeError("busy")
        try: return self._chat(messages, max_tokens, temperature, timeout, json_mode)
        finally: self.slot.release()

    def _chat(self, messages, max_tokens, temperature, timeout, json_mode):
        self.ensure(); t0 = time.time()
        body = {"messages": messages, "max_tokens": max_tokens, "temperature": temperature, "top_p": 0.9, "repeat_penalty": 1.1, "cache_prompt": True, "stream": False}
        if json_mode: body["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/chat/completions", data=json.dumps(body).encode(), headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r: out = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            self.stats["fails"] += 1; log(f"request failed: {type(e).__name__}"); raise
        self.last = time.time(); ms = int((self.last - t0) * 1000); n = self.stats["calls"] = self.stats["calls"] + 1
        self.stats["last_ms"] = ms; self.stats["avg_ms"] = int((self.stats["avg_ms"] * (n - 1) + ms) / n); self.stats["fails"] = 0
        return out["choices"][0]["message"]["content"].strip()

    def stop(self):
        p, self.proc = self.proc, None
        if p and p.poll() is None:
            p.terminate()
            try: p.wait(5)
            except Exception: p.kill()
        if self.state != "error": self.state = "idle"

    def _reaper(self):
        while True:
            time.sleep(20)
            if self.proc and self.state == "ready" and time.time() - self.last > self.idle and not self.lock.locked():
                self.stop()   # free the RAM when idle; it reloads in a few seconds on next use
