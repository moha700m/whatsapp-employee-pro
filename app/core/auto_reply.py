"""Auto-reply engine. UI-independent; driver/clock/sleep injectable for tests.

Safety gates (all checked before every send):
  kill switch, auto_reply_enabled setting, groups skip, dedupe of incoming message ids,
  opt-out keywords, per-chat cooldown, per-chat hourly cap, global hourly cap,
  human-like random delay + typing delay, holding reply sent ONCE for handoff cases."""
import hashlib, random, time
from dataclasses import dataclass, field
from app.core.kill_switch import KILL_SWITCH, KillSwitchEngaged
from app.core.logger import log_activity
from app.core.parser import Message, find_phone
from app.core.settings import AutoReplySettings
from app.ai.orchestrator import Orchestrator
from app.core import workflow as wfm

@dataclass
class EngineStats:
    sent: int = 0
    drafts: int = 0
    holding: int = 0
    skipped: int = 0
    errors: int = 0
    status: str = "متوقف"
    state: str = "stopped"          # stopped | watching | replying
    last_check: str = ""
    last_events: list = field(default_factory=list)   # [{"t","text","level"}] newest first

class AutoReplyEngine:
    def __init__(self, repo, driver, orchestrator=None, settings=None, kill_switch=KILL_SWITCH,
                 clock=time.time, sleep=None, rng=None):
        self.repo, self.driver = repo, driver
        self.orch = orchestrator or Orchestrator()
        self._live = settings is None          # reload settings each cycle unless injected (tests)
        self.settings = settings or AutoReplySettings.load(repo)
        self.wf = wfm.load(repo)
        self.ks, self.clock = kill_switch, clock
        self.rng = rng or random.Random()
        self._sleep = sleep or self._interruptible_sleep
        self.stats = EngineStats()
        self.seen = {}          # chat key -> {"name","last","unread","group","outcome","outcome_ar","t"} for the Inbox page
        self.on_event = None   # UI callback(str)

    # ---------- helpers ----------
    def _interruptible_sleep(self, secs):
        end = time.time() + secs
        while time.time() < end:
            self.ks.check()
            time.sleep(min(0.2, max(0, end - time.time())))

    def _event(self, text, level="INFO"):
        self.stats.last_events = ([{"t": time.strftime("%H:%M:%S"), "text": text, "level": level}] + self.stats.last_events)[:80]
        log_activity(self.repo.db, "auto_reply", text, level)
        if self.on_event:
            try: self.on_event(text)
            except Exception: pass

    @staticmethod
    def msg_key(chat_key, m):
        base = m.msg_id or hashlib.sha1(f"{chat_key}|{m.timestamp}|{m.sender}|{m.text}".encode()).hexdigest()
        return f"{chat_key}::{base}"

    def _seen(self, key):
        return self.repo.db.scalar("SELECT 1 FROM processed_messages WHERE msg_key=?", (key,)) is not None

    def _mark(self, keys, chat):
        with self.repo.db.transaction() as c:
            c.executemany("INSERT OR IGNORE INTO processed_messages(msg_key, chat) VALUES (?,?)", [(k, chat) for k in keys])

    def _count(self, where, params):
        return self.repo.db.scalar(f"SELECT COUNT(*) FROM auto_replies WHERE {where}", params) or 0

    def is_opted_out(self, customer_id):
        return bool(self.repo.db.scalar("SELECT opted_out FROM consents WHERE customer_id=?", (customer_id,)))

    def rate_block(self, chat_key):
        now, s = self.clock(), self.settings
        last = self.repo.db.scalar("SELECT MAX(sent_at) FROM auto_replies WHERE chat=?", (chat_key,))
        if last and now - last < s.chat_cooldown:
            return "cooldown"
        if self._count("chat=? AND sent_at>?", (chat_key, now - 3600)) >= s.max_per_chat_hour:
            return "chat_hour_cap"
        if self._count("sent_at>?", (now - 3600,)) >= s.global_hour_cap:
            return "global_hour_cap"
        return None

    def _holding_sent(self, chat_key):
        return self._count("chat=? AND kind='holding'", (chat_key,)) > 0

    def _flag(self, chat, cid, reason, last):
        exists = self.repo.db.scalar("SELECT 1 FROM needs_attention WHERE chat=? AND status='open'", (chat,))
        if exists:
            self.repo.db.execute("UPDATE needs_attention SET reason=?, last_message=? WHERE chat=? AND status='open'", (reason, last, chat))
        else:
            self.repo.db.execute("INSERT INTO needs_attention(chat, customer_id, reason, last_message) VALUES (?,?,?,?)", (chat, cid, reason, last))

    # ---------- approval queue ----------
    @property
    def approval(self):
        return self.settings.send_mode != "auto"

    def _draft(self, chat_key, cid, incoming, reply, kind, cls, provider, rule=""):
        """Approval mode: store the proposed reply; nothing is sent until the user approves it."""
        self.ks.check()
        db = self.repo.db
        cur = db.query("SELECT id, incoming FROM drafts WHERE chat=? AND status='pending' ORDER BY id DESC LIMIT 1", (chat_key,))
        if cur:   # one card per chat: merge new messages, refresh the proposal
            merged = (cur[0]["incoming"] + "\n" + incoming)[-2000:]
            db.execute("UPDATE drafts SET incoming=?, reply=?, kind=?, rule=?, classification=?, provider=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                       (merged, reply, kind, rule, cls, provider, cur[0]["id"]))
            did = cur[0]["id"]
        else:
            did = db.execute("INSERT INTO drafts(chat, customer_id, incoming, reply, kind, rule, classification, provider) VALUES (?,?,?,?,?,?,?,?)",
                             (chat_key, cid, incoming[-2000:], reply, kind, rule, cls, provider))
        self.stats.drafts += 1
        self._event(f"📝 جهّزت رد لـ {chat_key} — بانتظار موافقتك")
        return did

    def send_draft(self, draft_id, text=None):
        """Called only from an explicit user click. Sends exactly `text` (or the stored reply) once."""
        self.ks.check()
        db = self.repo.db
        with db.transaction() as c:
            row = c.execute("SELECT * FROM drafts WHERE id=?", (int(draft_id),)).fetchone()
            if row is None or row["status"] != "pending":
                raise ValueError("هالرد انرسل أو انلغى من قبل")
            c.execute("UPDATE drafts SET status='sending' WHERE id=?", (row["id"],))
        row = dict(row)
        body = (text if text is not None else row["reply"] or "").strip()
        try:
            if not body:
                raise ValueError("الرد فاضي")
            if row["customer_id"] and self.is_opted_out(row["customer_id"]):
                raise PermissionError("العميل طلب إيقاف الرسائل")
            from app.automation.base import ChatRef
            self.driver.open_chat(ChatRef(row["chat"], row["chat"]))
            self.driver.send_text(body, self.settings.typing_delay_ms)
        except Exception as e:
            db.execute("UPDATE drafts SET status='pending', error=? WHERE id=?", (str(e)[:300], row["id"]))
            self._event(f"ما قدرت أرسل الرد لـ {row['chat']}: {str(e)[:120]}", "ERROR")
            raise
        db.execute("UPDATE drafts SET status='sent', reply=?, sent_at=?, error=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?", (body, self.clock(), row["id"]))
        db.execute("INSERT INTO auto_replies(chat, customer_id, incoming, reply, kind, classification, provider, sent_at) VALUES (?,?,?,?,?,?,?,?)",
                   (row["chat"], row["customer_id"], (row["incoming"] or "")[:1000], body, "approved" if row["kind"] != "holding" else "holding",
                    row["classification"], row["provider"], self.clock()))
        if row["customer_id"]:
            self.repo.update_customer(row["customer_id"], last_contact=time.strftime("%Y-%m-%d %H:%M:%S"))
        try:
            from app.core import pro; pro.log_answered(self.repo, row["chat"])
        except Exception: pass
        self.stats.sent += 1
        self._event(f"✅ أرسلت ردك المعتمد لـ {row['chat']}: {body[:60]}")
        return True

    def _send_direct(self, chat_key, cid, incoming, reply, kind, cls, provider):
        """After-hours safe-intent path: bypasses approval but keeps delays, kill switch and the enabled check."""
        was = self.settings.send_mode
        try:
            self.settings.send_mode = "auto"
            return self._send(chat_key, cid, incoming, reply, kind, cls, provider)
        finally:
            self.settings.send_mode = was

    def _send(self, chat_key, cid, incoming, reply, kind, cls, provider):
        if self.approval:
            return self._draft(chat_key, cid, incoming, reply, kind, cls, provider)
        s = self.settings
        self.ks.check()
        self.stats.state = "replying"
        self._event(f"أجهز رد لـ {chat_key}… (تأخير بشري)")
        self._sleep(self.rng.uniform(s.min_delay, s.max_delay))
        self.ks.check()
        if not s.auto_reply_enabled:
            raise PermissionError("الرد التلقائي غير مفعّل")
        self.driver.send_text(reply, s.typing_delay_ms)
        self.repo.db.execute("INSERT INTO auto_replies(chat, customer_id, incoming, reply, kind, classification, provider, sent_at) VALUES (?,?,?,?,?,?,?,?)",
                             (chat_key, cid, incoming[:1000], reply, kind, cls, provider, self.clock()))
        self.repo.update_customer(cid, last_contact=time.strftime("%Y-%m-%d %H:%M:%S"))
        try:
            from app.core import pro; pro.log_answered(self.repo, chat_key)
        except Exception: pass
        if kind == "holding": self.stats.holding += 1
        else: self.stats.sent += 1
        self.stats.state = "watching"
        self._event(f"رديت على {chat_key}: {reply[:60]}")

    # ---------- core ----------
    def reload(self):
        if self._live:
            self.settings = AutoReplySettings.load(self.repo)
        self.wf = wfm.load(self.repo)
        self.orch.workflow = self.wf
        pf = getattr(self, "provider_factory", None)
        if pf and getattr(self, "_prov_name", None) != self.settings.provider:
            self.orch.provider = pf(self.settings.provider); self._prov_name = self.settings.provider

    def _sent_kind_today(self, chat_key, kind):
        return self._count("chat=? AND kind=? AND date(created_at,'localtime')=date('now','localtime')", (chat_key, kind)) > 0

    def process_chat(self, chat):
        """Returns a short outcome string (for tests/UI)."""
        s, wf = self.settings, self.wf
        self.ks.check()
        if not s.auto_reply_enabled or not wf.get("enabled", True):
            return "disabled"
        if chat.is_group and s.skip_groups:
            self.stats.skipped += 1
            return "group_skipped"
        self.driver.open_chat(chat)
        msgs = self.driver.read_messages(20)
        tail = []
        for m in reversed(msgs):       # incoming messages after our last outgoing
            if not m.incoming:
                break
            tail.append(m)
        tail.reverse()
        new = [m for m in tail if not self._seen(self.msg_key(chat.key, m))]
        if not new:
            return "nothing_new"
        keys = [self.msg_key(chat.key, m) for m in new]
        phone = ""
        try: phone = self.driver.chat_phone() or ""
        except Exception: pass
        conv = [Message(chat.name if m.incoming else "أنا", m.text, m.timestamp) for m in msgs]
        phone = phone or find_phone(conv, chat.name)
        cid = self.repo.upsert_customer(chat.name, phone)
        incoming_text = "\n".join(m.text for m in new)
        try:
            from app.core import pro
            pro.log_incoming(self.repo, chat.key)
        except Exception: pass
        self._event(f"قرأت {len(new)} رسالة جديدة من {chat.name}: «{new[-1].text[:50]}»")

        if self.is_opted_out(cid):
            self._mark(keys, chat.key)
            return "opted_out"
        media = [m for m in new if getattr(m, "media", "")]
        if media:   # voice notes / images are never auto-answered: flag for the owner (nothing is downloaded)
            from app.automation.whatsapp_web import MEDIA_AR
            kinds = "، ".join(sorted({MEDIA_AR.get(m.media, m.media) for m in media}))
            self._flag(chat.key, cid, f"وصل {kinds} — يحتاج تسمعه/تشوفه بنفسك", incoming_text[:200])
            if len(media) == len(new):
                self._mark(keys, chat.key)
                self._event(f"🎤 {chat.name} أرسل {kinds} — حطيته في «يحتاجونك»")
                return "media_flagged"
        business = wfm.business_items(self.repo, wf)
        d = wfm.evaluate(wf, [m.text for m in new], chat.name, business, s.opt_out_list)
        from app.core.safety import is_injection
        if d.action not in ("stop", "ignore") and any(is_injection(m.text) for m in new):
            d.action, d.reason, d.rule = "holding", "رسالة فيها محاولة توجيه للبوت — راجعها بنفسك", "حماية"
        if d.action == "stop":
            self.repo.stop_follow_ups(cid)
            self._mark(keys, chat.key)
            self._flag(chat.key, cid, "العميل طلب إيقاف الرسائل", incoming_text[:200])
            self._event(f"إيقاف الردود لـ {chat.name} ({d.rule})")
            if d.reply and not self.rate_block(chat.key):
                self._send(chat.key, cid, incoming_text, d.reply, "opt_out", d.classification, "rule")
            return "opted_out_now"

        if not wfm.in_working_hours(wf):
            if getattr(s, "after_hours_auto", False) and not self.rate_block(chat.key):
                from app.brain.engine import think
                br = think(incoming_text, chat.name, repo=self.repo, after_hours=True)
                if br["safe_auto"]:   # only safe intents (greeting/thanks/FAQ/...) go out automatically after-hours
                    self._mark(keys, chat.key)
                    self._send_direct(chat.key, cid, incoming_text, br["reply"], "after_hours", d.classification, "brain")
                    return "after_hours_auto"
            if wf["working_hours"].get("away_enabled") and not self._sent_kind_today(chat.key, "away") and not self.rate_block(chat.key):
                self._mark(keys, chat.key)
                self._send(chat.key, cid, incoming_text, wfm.fill("{away}", wf, chat.name), "away", d.classification, "rule")
                return "away_sent"
            return "outside_hours"     # not marked: answered when hours start

        block = None if self.approval else self.rate_block(chat.key)
        if block:
            self.stats.skipped += 1
            return block

        cls = d.classification
        self.repo.update_customer(cid, classification=cls,
                                  stage=cls if cls in ("New Lead","Interested","Hot Lead","Existing Customer") else None)
        if d.action == "holding":
            self._flag(chat.key, cid, d.reason or d.rule, incoming_text[:200])
            self._mark(keys, chat.key)
            if self._holding_sent(chat.key) or (self.approval and self.repo.db.scalar(
                    "SELECT 1 FROM drafts WHERE chat=? AND kind='holding' AND status IN ('pending','sent')", (chat.key,))):
                self._event(f"{chat.name} يحتاجك ({d.reason}) — الرد المؤقت أُرسل مسبقاً")
                return "flagged_only"
            self._send(chat.key, cid, incoming_text, d.reply, "holding", cls, "rule")
            return "holding_sent"
        if d.action == "ignore":
            self._mark(keys, chat.key)
            return "ignored"
        if d.action == "reply":
            self._mark(keys, chat.key)
            self._send(chat.key, cid, incoming_text, d.reply, "rule", cls, "rule")
            return "rule_replied"
        res = self.orch.run(conv, chat.name, business, [r["text"] for r in self.repo.recent_replies()])
        self.repo.update_customer(cid, need=res["need"])
        if res.get("brain"):
            try:
                from app.core import pro
                br = res["brain"]
                self.repo.db.execute("UPDATE customers SET lead_score=?, occasion=COALESCE(?, occasion) WHERE id=?",
                                     (br["lead_score"], br["entities"].get("occasion"), cid))
                pro.order_from_brain(self.repo, cid, chat.key, br)
            except Exception: pass
        self._mark(keys, chat.key)
        self._send(chat.key, cid, incoming_text, res["reply"], "auto", d.set_class or res["classification"], res["provider"])
        return "replied"

    OUTCOME_AR = {"drafted": "📝 رد جاهز — بانتظار موافقتك", "holding_drafted": "📝 رد مؤقت جاهز + يحتاجك","replied": "رديت (ذكي)", "rule_replied": "رديت (قاعدة)", "holding_sent": "رد مؤقت + يحتاجك",
                  "flagged_only": "يحتاجك", "opted_out_now": "طلب الإيقاف", "opted_out": "موقوف", "group_skipped": "مجموعة (تجاهل)",
                  "nothing_new": "لا جديد", "disabled": "الرد التلقائي مقفل", "cooldown": "انتظار الفاصل", "chat_hour_cap": "وصل حد المحادثة",
                  "global_hour_cap": "وصل الحد الكلي", "outside_hours": "خارج الدوام", "away_sent": "رسالة خارج الدوام", "ignored": "تجاهل (قاعدة)",
                  "error": "خطأ", "media_flagged": "🎤 صوت/صورة — يحتاجك", "after_hours_auto": "رد آمن خارج الدوام"}

    def run_once(self):
        self.ks.check()
        self.reload()
        self.stats.last_check = time.strftime("%H:%M:%S")
        if self.stats.state == "stopped": self.stats.state = "watching"
        chats = self.driver.list_unread_chats()
        if chats:
            self._event(f"لقيت {len(chats)} محادثة غير مقروءة: " + "، ".join(c.name for c in chats[:6]))
        out = []
        for c in chats:
            try:
                res = self.process_chat(c)
            except KillSwitchEngaged:
                raise
            except Exception as e:
                if "closed" in str(e).lower() or "target" in str(e).lower():
                    raise
                self.stats.errors += 1
                self._event(f"خطأ في محادثة {c.name}: {str(e)[:160]}", "ERROR")
                res = "error"
            if self.approval and res in ("replied", "rule_replied", "away_sent"):
                res = "drafted"
            elif self.approval and res == "holding_sent":
                res = "holding_drafted"
            out.append((c.key, res))
            self.seen[c.key] = {"name": c.name, "last": getattr(c, "last", ""), "unread": c.unread, "group": c.is_group,
                                "outcome": res, "outcome_ar": self.OUTCOME_AR.get(res, res), "t": time.strftime("%H:%M:%S")}
            if res in ("group_skipped", "cooldown", "chat_hour_cap", "global_hour_cap", "outside_hours", "disabled", "nothing_new"):
                self._event(f"{c.name}: {self.OUTCOME_AR.get(res, res)}")
        return out

    def run_forever(self, stop_event):
        self.stats.status = "يعمل"
        self._event("بدأ الموظف الرد التلقائي")
        try:
            while not stop_event.is_set():
                self.run_once()
                self._sleep(self.settings.poll_interval)
        except KillSwitchEngaged:
            self._event("وقفت كل شي (زر الإيقاف الفوري)", "WARNING")
        finally:
            self.stats.status = "متوقف"
