"""Pluggable AI providers. No API keys are ever used. Default = built-in brain (offline, no downloads)."""
import json, urllib.request
from abc import ABC, abstractmethod

class AIProvider(ABC):
    name = "base"
    @abstractmethod
    def available(self) -> bool: ...
    @abstractmethod
    def complete(self, prompt: str) -> str: ...

class OllamaProvider(AIProvider):
    """OPTIONAL: used only if an Ollama server is ALREADY running on this PC (127.0.0.1:11434) with a model pulled.
    Never installs, starts or downloads anything. Falls back silently to the built-in brain."""
    name = "ollama"
    PREFERRED = ("qwen2.5", "qwen3", "gemma", "llama3", "mistral", "aya")
    def __init__(self, host="http://127.0.0.1:11434", model=None, timeout=60):
        self.host, self.model, self.timeout = host, model, timeout
        self._ok = None
    def _get(self, path, t=1.5):
        with urllib.request.urlopen(self.host + path, timeout=t) as r:
            return json.loads(r.read().decode("utf-8"))
    def models(self):
        try: return [m["name"] for m in self._get("/api/tags").get("models", [])]
        except Exception: return []
    def available(self):
        if self._ok is None:
            ms = self.models()
            if ms and not self.model:
                self.model = next((m for pref in self.PREFERRED for m in ms if m.startswith(pref)), ms[0])
            self._ok = bool(ms)
        return self._ok
    def complete(self, prompt):
        if not self.available(): raise RuntimeError("Ollama not running")
        body = json.dumps({"model": self.model, "stream": False, "options": {"temperature": 0.4},
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request(self.host + "/api/chat", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))["message"]["content"]

def detect_ollama():
    p = OllamaProvider()
    return {"running": p.available(), "model": p.model or "", "models": p.models() if p._ok else []}

class ChatGPTWebProvider(AIProvider):
    """EXPERIMENTAL (off by default): drives the user's own ChatGPT tab. Fragile (UI changes, captchas, rate limits)
    and may violate ChatGPT terms — keep it off for customers. Never reads cookies/tokens."""
    name = "chatgpt_web"
    def __init__(self, browser=None):
        self.browser = browser
    def available(self):
        return self.browser is not None and self.browser.is_ready()
    def complete(self, prompt):
        if not self.available():
            raise NotImplementedError("مزود ChatGPT عبر المتصفح تجريبي ومقفل")
        return self.browser.ask_chatgpt(prompt)
