"""Drives a chatgpt.com tab in the same persistent profile. User logs in himself once."""
import time
from app.automation.selectors import GPT, CHATGPT_URL
from app.automation.whatsapp_web import _first

class ChatGPTWebBrowser:
    def __init__(self, session, timeout=90):
        self.session, self.timeout, self.page = session, timeout, None

    def open(self):
        self.page = self.session.page_for("https://chatgpt.com", CHATGPT_URL)
        return self.page

    def is_ready(self):
        try:
            if self.page is None: self.open()
            return _first(self.page, GPT["prompt"]) is not None and _first(self.page, GPT["login_hint"]) is None
        except Exception:
            return False

    def ask_chatgpt(self, prompt):
        p = self.page or self.open()
        p.goto(CHATGPT_URL, wait_until="domcontentloaded")  # fresh chat each time
        box = _first(p, GPT["prompt"], timeout=15000)
        if not box: raise RuntimeError("ChatGPT prompt box not found")
        before = p.locator(GPT["assistant_msg"][0]).count()
        box.first.click(); p.keyboard.insert_text(prompt)
        btn = _first(p, GPT["send"], timeout=5000)
        (btn.first.click() if btn else p.keyboard.press("Enter"))
        end = time.time() + self.timeout
        while time.time() < end:  # wait for new message and for streaming to stop
            time.sleep(1.5)
            msgs = p.locator(GPT["assistant_msg"][0])
            if msgs.count() > before and _first(p, GPT["stop"]) is None:
                t1 = msgs.last.inner_text(); time.sleep(1.5)
                if msgs.last.inner_text() == t1 and t1.strip():
                    return t1.strip()
        raise TimeoutError("ChatGPT timeout")
