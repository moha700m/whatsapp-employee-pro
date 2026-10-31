"""Background worker that owns Playwright (its sync API is bound to one thread) and runs the engine.
The UI only calls open_whatsapp()/start()/stop()/check_chatgpt() and reads snapshot()."""
import asyncio, queue, sys, threading, time
from collections import deque
from app.core.kill_switch import KILL_SWITCH, KillSwitchEngaged
from app.core.logger import log_activity, get_logger
from app.core.settings import AutoReplySettings
from app.core.auto_reply import AutoReplyEngine
from app.ai.orchestrator import Orchestrator
from app.ai.providers import ChatGPTWebProvider

import base64
WA_AR = {"disconnected": "مو متصل", "loading": "لحظة…", "qr": "ينتظرك تمسح QR", "connected": "متصل",
         "conflict": "مفتوح في مكان ثاني", "phone_offline": "جوالك مو متصل", "missing_deps": "فيه شي ناقص", "error": "فيه مشكلة"}
WA_EVENT = {"connected": "✅ واتساب متصل — قائمة المحادثات ظاهرة", "qr": "📱 ظهر رمز QR — امسحه من جوالك",
            "loading": "لحظة، قاعد أفتح واتساب…", "disconnected": "⚠️ نافذة واتساب مقفلة أو مو متصلة",
            "conflict": "⚠️ واتساب مفتوح في نافذة/جهاز آخر — اضغط «استخدام هنا»",
            "phone_offline": "⚠️ جوالك مو متصل بالنت — واتساب ويب ما يقدر يستقبل", "missing_deps": "⚠️ مكونات ناقصة (Playwright)",
            "error": "⚠️ ما قدرت أفتح المتصفح"}
GPT_AR = {"unused": "مو مستخدم (المحلل المحلي)", "unknown": "ما فحصته للحين", "ready": "جاهز", "login": "سجّل دخولك في ChatGPT", "error": "مو شغال"}
EMP_AR = {"stopped": "واقف", "watching": "يتابع الرسائل", "replying": "يجهّز رد", "waiting": "ينتظر واتساب يتصل"}

class EmployeeRunner:
    def __init__(self, repo, session_factory=None, driver_factory=None):
        self.repo = repo
        self.session_factory, self.driver_factory = session_factory, driver_factory
        self.q = queue.Queue()
        self.running = threading.Event()
        self.status = "غير متصل"
        self.wa_state, self.gpt_state, self.emp_state = "disconnected", "unknown", "stopped"
        self.last_check = ""
        self.chats_preview = {}; self._last_list = 0
        self.qr_png = None; self.qr_time = ""; self.profile = ""; self.error = ""
        self.events = deque(maxlen=100)
        self.engine = None
        self.session = self.driver = self.gpt = None
        self._t = threading.Thread(target=self._loop, daemon=True, name="employee")
        self._t.start()

    # ---- UI API ----
    def open_whatsapp(self): self.q.put("open")
    def start(self): self.q.put("start")
    def stop(self): self.running.clear(); self.q.put("stop")
    def check_chatgpt(self): self.q.put("gpt")
    def use_here(self): self.q.put("use_here")
    def diagnose(self): self.q.put("diag")

    def call(self, fn, timeout=90):
        """Run fn(runner) inside the Playwright thread and wait for its result (used for approved sends)."""
        import concurrent.futures as cf
        fut = cf.Future(); self.q.put(("call", fn, fut))
        return fut.result(timeout=timeout)

    def send_draft(self, draft_id, text):
        def work(r):
            if r.driver is None or (hasattr(r.driver, "connection_state") and r.driver.connection_state() != "connected"):
                raise RuntimeError("واتساب غير متصل — اربطه أول")
            eng = r.engine or r._make_engine()
            if r.engine is None: r.engine = eng
            eng.reload()
            return eng.send_draft(draft_id, text)
        return self.call(work)
    def set_browser_visible(self, visible): self.q.put(("visible", bool(visible)))
    def shutdown(self): self.running.clear(); self.q.put("quit"); self._t.join(timeout=5)

    def event(self, text, level="INFO"):
        self.events.appendleft({"t": time.strftime("%H:%M:%S"), "text": text, "level": level})

    def snapshot(self):
        s = AutoReplySettings.load(self.repo)
        gpt = self.gpt_state if s.provider == "chatgpt_web" else "unused"
        evs = list(self.events)
        if self.engine:
            evs = sorted(evs + self.engine.stats.last_events, key=lambda e: e["t"], reverse=True)[:60]
        st = self.engine.stats if self.engine else None
        chats = dict(self.chats_preview)
        if self.engine: chats.update(self.engine.seen)
        return {"wa": self.wa_state, "wa_ar": WA_AR[self.wa_state], "profile": self.profile, "error": self.error,
                "qr": ("data:image/png;base64," + base64.b64encode(self.qr_png).decode()) if (self.qr_png and self.wa_state == "qr") else "",
                "qr_time": self.qr_time, "chats": list(chats.values()), "gpt": gpt, "gpt_ar": GPT_AR[gpt],
                "emp": self.emp_state, "emp_ar": EMP_AR[self.emp_state], "status": self.status,
                "last_check": (st.last_check if st and st.last_check else self.last_check), "events": evs,
                "kill": KILL_SWITCH.engaged, "auto_enabled": s.auto_reply_enabled, "provider": s.provider,
                "counters": {"sent": st.sent if st else 0, "drafts": st.drafts if st else 0, "holding": st.holding if st else 0,
                             "skipped": st.skipped if st else 0, "errors": st.errors if st else 0}}

    # ---- worker ----
    def _ensure_driver(self):
        if self.driver is None:
            if self.driver_factory:
                self.driver = self.driver_factory()
            else:
                from app.automation.browser import BrowserSession
                from app.automation.whatsapp_web import WhatsAppWebAgent
                self.session = (self.session_factory or BrowserSession)()
                self.driver = WhatsAppWebAgent(self.session)
        if hasattr(self.driver, "open") and (getattr(self.driver, "page", 1) is None or
                                              (hasattr(self.driver.page, "is_closed") and self.driver.page.is_closed())):
            self.event("أفتح نافذة Chrome الخاصة بالبرنامج على WhatsApp Web…")
            self.driver.open()
        return self.driver

    def _provider_factory(self, name):
        if name in ("ollama", "auto", "offline"):
            from app.ai.providers import OllamaProvider
            p = OllamaProvider()
            return p if (name == "ollama" or name == "auto") and p.available() else None
        if name == "chatgpt_web" and self.session is not None and AutoReplySettings.load(self.repo).chatgpt_experimental:
            from app.automation.chatgpt_web import ChatGPTWebBrowser
            self.gpt = self.gpt or ChatGPTWebBrowser(self.session)
            return ChatGPTWebProvider(self.gpt)
        return None

    def _make_engine(self):
        eng = AutoReplyEngine(self.repo, self.driver, Orchestrator())   # settings/workflow reloaded live
        eng.provider_factory = self._provider_factory
        if self.engine: eng.stats = self.engine.stats
        def sleep(secs):
            end = time.time() + secs
            while time.time() < end:
                KILL_SWITCH.check()
                if not self.running.is_set():
                    raise KillSwitchEngaged("stopped by user")
                time.sleep(0.2)
        eng._sleep = sleep
        return eng

    def _update_wa_state(self):
        if self.driver is None:
            new = "missing_deps" if self.wa_state == "missing_deps" else "error" if self.wa_state == "error" else "disconnected"
        elif hasattr(self.driver, "connection_state"):
            new = self.driver.connection_state()
        else:
            new = "connected" if self.driver.is_ready() else "disconnected"
        if new == "qr" and hasattr(self.driver, "capture_qr"):
            png = self.driver.capture_qr()
            if png and png != self.qr_png:
                self.qr_png, self.qr_time = png, time.strftime("%H:%M:%S")
        if new == "connected" and self.wa_state != "connected" and hasattr(self.driver, "profile_info"):
            self.profile = self.driver.profile_info() or ""
        if new != self.wa_state:
            prev, self.wa_state = self.wa_state, new
            self.event(WA_EVENT[new], "INFO" if new in ("connected", "qr", "loading") else "WARNING")
            if new == "connected":
                self.qr_png = None
                try:
                    from app.automation.whatsapp_web import self_test
                    miss = self_test(self.driver.page) if getattr(self.driver, "page", None) is not None else []
                    self.selftest_missing = miss
                    if miss:
                        self.event("⚠️ الفحص الذاتي: واتساب غيّر شكل الصفحة (" + "، ".join(miss) + ") — القراءة ممكن تتعطل، شغّل التشخيص", "WARNING")
                    else:
                        self.event("✅ الفحص الذاتي سليم — كل عناصر واتساب ظاهرة")
                except Exception as e:
                    get_logger().warning("self-test: %s", e)
                if self.session is not None and not AutoReplySettings.load(self.repo).show_browser:
                    try: self.session.set_visible(self.driver.page, False)
                    except Exception: pass
        self.last_check = time.strftime("%H:%M:%S")

    def _handle(self, cmd):
        if isinstance(cmd, tuple) and cmd[0] == "call":
            _, fn, fut = cmd
            try: fut.set_result(fn(self))
            except Exception as e: fut.set_exception(e)
            return
        if isinstance(cmd, tuple) and cmd[0] == "visible":
            if self.session is not None and self.driver is not None and getattr(self.driver, "page", None) is not None:
                self.session.set_visible(self.driver.page, cmd[1])
            self.event("👁 أظهرت نافذة Chrome" if cmd[1] else "🙈 أخفيت نافذة Chrome (تشتغل بالخلفية)")
            return
        if cmd == "diag":
            from app import config
            path = config.LOG_DIR / "selectors.txt"
            try:
                rep = self.driver.diagnose() if self.driver is not None and hasattr(self.driver, "diagnose") else "no WhatsApp window"
            except Exception as e:
                rep = f"diagnose failed: {e}"
            config.LOG_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n" + rep, encoding="utf-8-sig")
            self.event(f"🩺 حفظت تقرير تشخيص واتساب في {path}")
            return
        if cmd == "use_here":
            if self.driver is not None and hasattr(self.driver, "use_here") and self.driver.use_here():
                self.event("ضغطت «استخدام هنا» — واتساب صار يشتغل في البرنامج")
            return
        if cmd == "open":
            try:
                self._ensure_driver(); self.error = ""
            except ModuleNotFoundError as e:
                self.driver = self.session = None
                self.wa_state = "missing_deps"; self.error = f"مكون ناقص: {e.name}"
                self.event("⚠️ ما قدرت أفتح واتساب: مكتبة Playwright غير مثبتة. اضغط «إصلاح تلقائي».", "ERROR"); return
            except Exception as e:
                try:
                    if self.session: self.session.close()
                except Exception: pass
                self.driver = self.session = None
                self.wa_state = "error"; self.error = str(e)[:300]
                self.event(f"⚠️ ما قدرت أفتح Chrome: {str(e)[:150]}", "ERROR"); get_logger().exception("open"); return
            self._update_wa_state()
        elif cmd == "gpt":
            self._ensure_driver()
            try:
                self.gpt = self.gpt or __import__("app.automation.chatgpt_web", fromlist=["x"]).ChatGPTWebBrowser(self.session)
                self.gpt_state = "ready" if self.gpt.is_ready() else "login"
            except Exception as e:
                self.gpt_state = "error"; get_logger().warning("gpt check: %s", e)
            self.event(f"ChatGPT: {GPT_AR[self.gpt_state]}")
        elif cmd == "start":
            s = AutoReplySettings.load(self.repo)
            if not s.auto_reply_enabled:
                self.status = "الرد التلقائي غير مفعّل من صفحة سير العمل"; self.event(self.status, "WARNING"); return
            if KILL_SWITCH.engaged:
                self.status = "زر الإيقاف الفوري مفعّل"; self.event(self.status, "WARNING"); return
            try:
                self._ensure_driver()
            except Exception as e:
                self.status = f"ما قدرت أفتح واتساب: {e}"; self.event(self.status, "ERROR"); return
            self.engine = self._make_engine(); self.running.set()
            self.emp_state = "watching"; self.event("▶ بدأ الموظف")
            log_activity(self.repo.db, "employee_start", s.provider)
        elif cmd == "stop":
            self.emp_state = "stopped"; self.status = "متوقف"
            if self.engine: self.engine.stats.state = "stopped"
            self.event("■ أوقفت الموظف"); log_activity(self.repo.db, "employee_stop")

    def _recover(self, e):
        """Chrome/context closed or page detached -> relaunch the persistent context and reopen WhatsApp."""
        msg = str(e).lower()
        if not any(k in msg for k in ("closed", "target", "detached", "disconnected")):
            return
        self.event("⚠️ انقفلت نافذة Chrome أو انقطع الاتصال بها — أعيد فتحها…", "WARNING")
        try:
            if self.session is not None:
                self.session.close()
            if self.driver is not None and hasattr(self.driver, "page"):
                self.driver.page = None
            self._ensure_driver(); self._update_wa_state()
            self.event("✅ رجعت فتحت واتساب")
        except Exception as e2:
            self.wa_state = "error"; self.error = str(e2)[:300]
            self.event(f"ما قدرت أرجع أفتح Chrome: {str(e2)[:120]}", "ERROR")

    def _loop(self):
        if sys.platform == "win32":   # Playwright needs a Proactor loop in this thread on Windows
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        last_probe = 0
        while True:
            try:
                cmd = self.q.get(timeout=0.3)
                if cmd == "quit":
                    break
                self._handle(cmd)
            except queue.Empty:
                pass
            except Exception as e:
                self.status = f"خطأ: {e}"; self.event(self.status, "ERROR"); get_logger().exception("runner")
            if self.driver is not None and time.time() - last_probe > 2:
                last_probe = time.time()
                try:
                    self._update_wa_state()
                    if self.wa_state == "connected" and not self.running.is_set() and time.time() - self._last_list > 8:
                        self._last_list = time.time()
                        for c in self.driver.list_unread_chats():
                            self.chats_preview[c.key] = {"name": c.name, "last": c.last, "unread": c.unread, "group": c.is_group,
                                                         "outcome": "waiting", "outcome_ar": "بانتظار تشغيل الموظف", "t": time.strftime("%H:%M:%S")}
                except Exception as e:
                    get_logger().exception("probe"); self._recover(e)
            if self.running.is_set() and self.engine:
                if KILL_SWITCH.engaged:
                    self.running.clear(); self.emp_state = "stopped"; self.status = "⛔ أوقفه زر الإيقاف الفوري"
                    self.event(self.status, "WARNING"); continue
                try:
                    if self.wa_state not in ("connected",):
                        self.emp_state = "waiting"; self.status = "بانتظار اتصال واتساب (امسح QR)"; time.sleep(1); continue
                    self.status = "🟢 يعمل — يفحص الرسائل الجديدة"
                    self.emp_state = "watching"
                    self.engine.run_once()
                    self.emp_state = "watching"
                    end = time.time() + self.engine.settings.poll_interval
                    while time.time() < end and self.running.is_set() and self.q.empty() and not KILL_SWITCH.engaged:
                        time.sleep(0.2)
                except KillSwitchEngaged:
                    self.running.clear(); self.emp_state = "stopped"; self.status = "⛔ تم الإيقاف"
                except Exception as e:
                    self.status = f"خطأ مؤقت: {str(e)[:120]}"; self.event(self.status, "ERROR"); get_logger().exception("engine")
                    self._recover(e); time.sleep(3)
        if self.session:
            try: self.session.close()
            except Exception: pass
