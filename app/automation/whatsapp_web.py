"""WhatsApp Web driver via Playwright (UI automation of the user's own logged-in page).
No WhatsApp API, no cookie/token access, no session modification."""
import hashlib, random, time
from app.automation.base import ChatRef, ChatMessage
from app.automation.selectors import WA, WA_URL
from app.core.logger import get_logger

log = get_logger()

MEDIA_AR = {"voice": "[رسالة صوتية]", "image": "[صورة]", "video": "[فيديو]", "document": "[ملف]", "sticker": "[ملصق]"}

def self_test(page, in_chat=False):
    """Startup selector self-test: returns list of selector keys that matched nothing (empty = healthy)."""
    from app.automation.selectors import SELF_TEST_KEYS, SELF_TEST_CHAT_KEYS
    missing = []
    for k in SELF_TEST_KEYS + (SELF_TEST_CHAT_KEYS if in_chat else []):
        try:
            if _first(page, WA[k]) is None: missing.append(k)
        except Exception:
            missing.append(k)
    return missing

class SendingDisabled(RuntimeError):
    pass

import re, unicodedata
_BIDI = re.compile("[\u200e\u200f\u202a-\u202e\u2066-\u2069\u200b-\u200d\ufeff]")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]")

def norm_name(s):
    """Tolerant chat-name key: NFKC, no bidi/zero-width marks, no emoji, no spaces/punctuation, lowercase."""
    s = unicodedata.normalize("NFKC", s or "")
    s = _EMOJI.sub("", _BIDI.sub("", s))
    return re.sub(r"[\s\-_.()\u00a0~]+", "", s).lower()

def names_match(a, b):
    a, b = norm_name(a), norm_name(b)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    da, db = re.sub(r"\D", "", a), re.sub(r"\D", "", b)       # phone numbers: compare last 9 digits
    return len(da) >= 9 and len(db) >= 9 and da[-9:] == db[-9:]

def _first(scope, sels, timeout=0, what=""):
    """First selector in the list that matches; None (and a debug log naming the key) if none do."""
    if scope is None:
        return None
    if timeout:   # wait until ANY of the selectors appears (not just the first one)
        try: scope.locator(", ".join(x for x in sels if not x.startswith("text="))).first.wait_for(timeout=timeout)
        except Exception as e:
            if "closed" in str(e).lower(): raise
    for s in sels:
        try:
            loc = scope.locator(s)
            if loc.count():
                return loc
        except Exception as e:
            if "closed" in str(e).lower():
                raise
            continue
    if what:
        log.warning("selector miss: %s (tried %d)", what, len(sels))
    return None

def _title(loc):
    """Name shown on a row/header: title attribute, else visible text."""
    if loc is None:
        return ""
    el = loc.first
    try:
        t = el.get_attribute("title")
        return (t or el.inner_text() or "").strip()
    except Exception:
        return ""

def retry(fn, tries=3, delay=1.0):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last = e; log.warning("retry %s/%s: %s", i + 1, tries, e); time.sleep(delay * (i + 1))
    raise last

class WhatsAppWebAgent:
    def __init__(self, session=None):
        self.session = session
        self.page = None

    def open(self):
        self.page = self.session.page_for("https://web.whatsapp.com", WA_URL)
        return self.page

    def is_ready(self):
        try:
            return self.connection_state() == "connected"
        except Exception:
            return False

    def connection_state(self):
        """disconnected | loading | qr | conflict | phone_offline | connected  (read from what the page shows)."""
        try:
            if self.page is None or self.page.is_closed():
                return "disconnected"
            if _first(self.page, WA["use_here"]) is not None or _first(self.page, WA["conflict"]) is not None:
                return "conflict"
            if _first(self.page, WA["ready"]) is not None:
                return "phone_offline" if _first(self.page, WA["phone_offline"]) is not None else "connected"
            if _first(self.page, WA["qr"]) is not None:
                return "qr"
            return "loading"
        except Exception:
            return "disconnected"

    def capture_qr(self):
        """PNG bytes of the QR as WhatsApp currently renders it (element screenshot; nothing is read from storage)."""
        if self.page is None:
            return None
        for sels in (WA["qr_container"], WA["qr"]):
            loc = _first(self.page, sels)
            if loc is not None:
                try:
                    if sels is WA["qr_container"] and _first(loc.first, WA["qr"]) is None:
                        continue
                    return loc.first.screenshot(type="png", timeout=4000)
                except Exception as e:
                    log.debug("qr capture failed: %s", e)
        return None

    def diagnose(self):
        """Which selectors match on the live page (for fast fixes). Returns text report."""
        lines = [f"url: {self.page.url if self.page else None}", f"state: {self.connection_state()}"]
        for key, sels in WA.items():
            for sel in sels:
                try:
                    n = self.page.locator(sel).count()
                    sample = ""
                    if n:
                        try: sample = (_title(self.page.locator(sel)) or "")[:60].replace("\n", " ")
                        except Exception: pass
                    lines.append(f"{key:16} {n:4}  {sel}   {sample}")
                except Exception as e:
                    lines.append(f"{key:16}  ERR  {sel}  {e}")
        try:
            rows = _first(self.page, WA["chat_row"])
            if rows is not None:
                lines.append("--- first chat row html (truncated) ---")
                lines.append(rows.first.evaluate("e => e.outerHTML")[:3000])
        except Exception:
            pass
        return "\n".join(lines)

    def use_here(self):
        btn = _first(self.page, WA["use_here"])
        if btn is None:
            return False
        btn.first.click(); return True

    def profile_info(self):
        """Best effort: visible profile name, if WhatsApp shows one. May be empty."""
        try:
            el = _first(self.page, WA["profile_name"])
            if el is not None:
                return el.first.inner_text().strip()
            img = _first(self.page, WA["profile_button"])
            if img is not None:
                return (img.first.get_attribute("alt") or "").strip()
        except Exception:
            pass
        return ""

    def needs_qr(self):
        return self.page is not None and _first(self.page, WA["qr"]) is not None

    def list_unread_chats(self):
        rows = _first(self.page, WA["chat_row"], what="chat_row")
        out = []
        if rows is None:
            return out
        for i in range(min(rows.count(), 40)):
            r = rows.nth(i)
            badge = _first(r, WA["unread_badge"])
            if not badge:
                continue
            name = _title(_first(r, WA["row_title"])) or f"chat-{i}"
            last = _title(_first(r, WA["row_last_msg"]))
            try: n = int("".join(ch for ch in badge.first.inner_text() if ch.isdigit()) or 1)
            except Exception: n = 1
            out.append(ChatRef(key=name, name=name, is_group=_first(r, WA["group_hint"]) is not None, unread=n, last=last))
        return out

    def open_chat(self, chat):
        def go():
            rows = _first(self.page, WA["chat_row"], what="chat_row")
            if rows is None:
                raise LookupError("قائمة المحادثات غير ظاهرة (chat_row)")
            target = None
            for i in range(min(rows.count(), 60)):
                if names_match(_title(_first(rows.nth(i), WA["row_title"])), chat.name):
                    target = rows.nth(i); break
            if target is None:
                raise LookupError(f"ما لقيت المحادثة في القائمة: {chat.name}")
            target.click()
            hdr = _first(self.page, WA["header_title"], timeout=5000, what="header_title")
            shown = _title(hdr)
            if hdr is not None and names_match(shown, chat.name):
                return
            # fallback verification: row is marked selected, or the compose box of an open chat is visible
            try:
                selected = (target.get_attribute("aria-selected") == "true") or target.locator("[aria-selected='true']").count() > 0
            except Exception:
                selected = False
            if selected or _first(self.page, WA["compose"]) is not None:
                log.info("header '%s' != row '%s' — accepted via selected/compose check", shown, chat.name)
                return
            raise RuntimeError(f"chat header mismatch: header={shown!r} row={chat.name!r}")
        retry(go)
        time.sleep(1.0)

    def read_messages(self, limit=20):
        msgs = _first(self.page, WA["message"], timeout=3000, what="message")
        out = []
        if msgs is None:
            return out
        n = msgs.count()
        for i in range(max(0, n - limit), n):
            m = msgs.nth(i)
            mid = m.get_attribute("data-id") or ""
            if mid.startswith(("false_", "true_")):
                incoming = mid.startswith("false_")
            else:
                cls = m.get_attribute("class") or ""
                incoming = "message-in" in cls or m.locator(".message-in").count() > 0
            meta = _first(m, WA["message_meta"])
            pre = meta.first.get_attribute("data-pre-plain-text") if meta else ""
            txt_loc = _first(m, WA["message_text"])
            text = txt_loc.first.inner_text().strip() if txt_loc else ""
            media = ""
            if not text:
                for kind in ("voice", "image", "video", "document", "sticker"):
                    try:
                        if _first(m, WA["media_" + kind]) is not None:
                            media = kind; break
                    except Exception:
                        pass
                if not media:
                    continue
                text = MEDIA_AR[media]
            sender = (pre or "").split("]")[-1].strip().rstrip(":") if pre else ""
            ts = (pre or "").split("]")[0].strip("[ ") if pre else ""
            out.append(ChatMessage(mid or hashlib.sha1(f"{ts}{text}".encode()).hexdigest(), sender, text, incoming, ts, media))
        return out

    def chat_phone(self):
        hdr = _first(self.page, WA["header_title"])
        t = hdr.first.get_attribute("title") if hdr else ""
        digits = "".join(c for c in t if c.isdigit() or c == "+")
        return digits if len(digits) >= 9 else ""

    def send_text(self, text, typing_delay_ms=60):
        box = _first(self.page, WA["compose"], timeout=5000, what="compose")
        if box is None:
            raise RuntimeError("ما لقيت مربع الكتابة (compose) — شغّل «تشخيص واتساب»")
        box.first.click()
        for line_i, line in enumerate(text.split("\n")):
            if line_i:
                self.page.keyboard.press("Shift+Enter")
            for ch in line:
                self.page.keyboard.type(ch)
                time.sleep(max(0, random.gauss(typing_delay_ms, typing_delay_ms / 3)) / 1000)
        btn = _first(self.page, WA["send_button"], what="send_button")
        (btn.first.click() if btn else self.page.keyboard.press("Enter"))
        time.sleep(1.0)

    # V1-style suggestion path still never sends:
    def send(self, *_a, **_k):
        raise SendingDisabled("الإرسال اليدوي من شاشة الاقتراحات معطّل — الإرسال فقط عبر الرد التلقائي المفعّل")
