"""Python API bridge for the web UI. Every public method takes/returns JSON-serialisable data.
Exposed over a local HTTP endpoint (127.0.0.1 only) used by both pywebview and the browser fallback."""
import json
from dataclasses import asdict
from app.config import CLASS_AR, CLASSIFICATIONS, PIPELINE_STAGES
from app.core.kill_switch import KILL_SWITCH
from app.core.logger import log_activity
from app.core.settings import AutoReplySettings
from app.core import workflow as wfm

class ApiError(Exception):
    pass

def _to_local(v):
    """SQLite CURRENT_TIMESTAMP is UTC; show the user's local time."""
    from datetime import datetime, timezone
    try:
        return datetime.strptime(v, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return v

def _localize(obj):
    if isinstance(obj, list):
        return [_localize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: (_to_local(v) if k in ("created_at", "updated_at") and isinstance(v, str) else _localize(v)) for k, v in obj.items()}
    return obj

class Api:
    def __init__(self, service, runner=None):
        self.svc, self.repo, self.runner = service, service.repo, runner

    # ---------- dispatch ----------
    def call(self, method, params=None):
        if method.startswith("_") or method == "call" or not hasattr(self, method):
            raise ApiError(f"unknown method {method}")
        return _localize(getattr(self, method)(**(params or {})))

    # ---------- meta / status ----------
    def meta(self):
        from app.config import APP_VERSION
        _m = {"classes": CLASSIFICATIONS, "class_ar": CLASS_AR, "stages": PIPELINE_STAGES,
                "triggers": wfm.TRIGGERS, "actions": wfm.ACTIONS, "default_prompt": wfm.DEFAULT_PROMPT}
        _m["version"] = APP_VERSION
        return _m

    def status(self):
        if self.runner:
            snap = self.runner.snapshot()
        else:
            s = AutoReplySettings.load(self.repo)
            snap = {"wa": "disconnected", "wa_ar": "مو متصل", "gpt": "unused", "gpt_ar": "مو مستخدم", "emp": "stopped",
                    "emp_ar": "واقف", "status": "محرك الأتمتة غير متاح", "last_check": "", "events": [],
                    "kill": KILL_SWITCH.engaged, "auto_enabled": s.auto_reply_enabled, "provider": s.provider,
                    "counters": {"sent": 0, "drafts": 0, "holding": 0, "skipped": 0, "errors": 0}}
        db = self.repo.db
        snap["needs"] = db.scalar("SELECT COUNT(*) FROM needs_attention WHERE status='open'") or 0
        snap["today"] = db.scalar("SELECT COUNT(*) FROM auto_replies WHERE date(created_at,'localtime')=date('now','localtime')") or 0
        snap["hour"] = db.scalar("SELECT COUNT(*) FROM auto_replies WHERE sent_at>strftime('%s','now')-3600") or 0
        st = AutoReplySettings.load(self.repo)
        snap["hour_cap"] = st.global_hour_cap
        snap["show_browser"] = st.show_browser
        from app.core import deps
        snap["missing"] = [m for m in deps.missing() if m == "playwright"]   # pywebview only affects the window
        snap["fix"] = deps.FIXER.state
        snap["pending"] = db.scalar("SELECT COUNT(*) FROM drafts WHERE status='pending'") or 0
        snap["onboarding_done"] = self.repo.get_setting("onboarding_done", "0") == "1"
        snap.setdefault("qr", ""); snap.setdefault("profile", ""); snap.setdefault("error", "")
        return snap

    # ---------- approval queue ----------
    def drafts(self, status="pending", limit=50):
        rows = self.repo.db.query("""SELECT d.*, c.phone, c.classification AS cust_class FROM drafts d LEFT JOIN customers c ON c.id=d.customer_id
                                     WHERE d.status=? ORDER BY d.id DESC LIMIT ?""", (status, limit))
        from app.core.lead_score import score_customer
        for r in rows:
            r["score"] = score_customer(self.repo, r["customer_id"]) if r["customer_id"] else None
        return rows
    def draft_update(self, id, text):
        self.repo.db.execute("UPDATE drafts SET reply=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending'", (text, int(id))); return True
    def draft_send(self, id, text):
        """The ONLY path that sends a message: an explicit click on ✅ إرسال."""
        if KILL_SWITCH.engaged:
            raise ApiError("زر الإيقاف الفوري مفعّل")
        if not (text or "").strip():
            raise ApiError("الرد فاضي")
        log_activity(self.repo.db, "draft_approved", f"{id}: {text[:80]}")
        try:
            return self._need_runner().send_draft(int(id), text.strip())
        except (ValueError, PermissionError, RuntimeError) as e:
            raise ApiError(str(e))
    def draft_ignore(self, id):
        self.repo.db.execute("UPDATE drafts SET status='ignored', updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending'", (int(id),))
        log_activity(self.repo.db, "draft_ignored", id); return True
    def draft_regenerate(self, id):
        from app.core.parser import Message
        from app.ai.orchestrator import Orchestrator
        row = self.repo.db.query("SELECT * FROM drafts WHERE id=?", (int(id),))
        if not row or row[0]["status"] != "pending": raise ApiError("الرد غير موجود")
        d = row[0]; wf = wfm.load(self.repo)
        msgs = [Message(d["chat"], t) for t in (d["incoming"] or "").splitlines() if t.strip()] or [Message(d["chat"], "")]
        avoid = [d["reply"]] + [r["text"] for r in self.repo.recent_replies()]
        import random
        res = Orchestrator(workflow=wf).run(msgs, d["chat"], wfm.business_items(self.repo, wf), avoid, rng=random.Random())
        new = res["reply"]
        if new == d["reply"]:
            new = wfm.fill("{fallback}", wf, d["chat"]) if d["reply"] != wfm.fill("{fallback}", wf, d["chat"]) else new
        self.repo.db.execute("UPDATE drafts SET reply=?, provider=?, kind='auto', updated_at=CURRENT_TIMESTAMP WHERE id=?", (new, res["provider"], d["id"]))
        log_activity(self.repo.db, "draft_regenerated", id); return {"reply": new}

    # ---------- المستشار التسويقي ----------
    def _shop(self):
        return wfm.load(self.repo)["business"].get("name") or ""
    def mk_analysis(self):
        from app.core import marketing as mk
        a = mk.analyze(self.repo); a["occasions_cal"] = mk.upcoming(shop=self._shop()); return a
    def mk_followups(self):
        from app.core import marketing as mk
        a = mk.analyze(self.repo); occ = mk.upcoming()[:1]; occ = occ[0] if occ and occ[0]["days"] <= 14 else None
        seen, out = set(), []
        for c in a["lost"] + a["hot"]:
            if c["id"] in seen or self._opted_out(c["id"]): continue
            seen.add(c["id"])
            out.append({"customer_id": c["id"], "name": c["name"], "phone": c["phone"], "score": c["score"], "days": c.get("days"),
                        "why": f"كان مهتم وسكت من {c['days']} يوم" if c.get("days") else "جاهز يشتري",
                        "text": mk.followup_text(c, self._shop(), occ)})
        return out
    def _opted_out(self, cid):
        return bool(self.repo.db.scalar("SELECT opted_out FROM consents WHERE customer_id=?", (cid,))) if cid else False
    def mk_followup_draft(self, customer_id, text):
        """Puts a follow-up in the approval queue. It is NOT sent until the owner clicks ✅ إرسال."""
        c = self.repo.db.query("SELECT id, name FROM customers WHERE id=?", (int(customer_id),))
        if not c: raise ApiError("ما لقيت العميل")
        if self._opted_out(c[0]["id"]): raise ApiError("العميل طلب ما نراسله — ما نقدر نجهز له رسالة")
        if not (text or "").strip(): raise ApiError("الرسالة فاضية")
        if self.repo.db.scalar("SELECT 1 FROM drafts WHERE customer_id=? AND status='pending'", (c[0]["id"],)):
            raise ApiError("فيه رد ينتظر موافقتك لهالعميل من قبل")
        self.repo.db.execute("INSERT INTO drafts(chat, customer_id, incoming, reply, kind, provider) VALUES (?,?,?,?, 'followup', 'advisor')",
                             (c[0]["name"], c[0]["id"], "", text.strip()[:1000]))
        log_activity(self.repo.db, "followup_drafted", c[0]["name"]); return True
    def mk_ask(self, question):
        from app.core import marketing as mk
        from app.core.safety import clean_reply
        if not (question or "").strip(): raise ApiError("اكتب سؤالك أول")
        a = mk.analyze(self.repo)
        if AutoReplySettings.load(self.repo).provider == "chatgpt_web" and self.runner is not None and hasattr(self.runner, "call"):
            try:
                ans = self.runner.call(lambda r: (r._provider_factory("chatgpt_web") or (_ for _ in ()).throw(RuntimeError("ChatGPT مو جاهز"))).complete(mk.ask_prompt(question, a, self._shop())), timeout=120)
                if ans and ans.strip(): return {"answer": clean_reply(ans), "provider": "chatgpt_web"}
            except Exception as e:
                log_activity(self.repo.db, "advisor_gpt_failed", str(e)[:120], "WARNING")
        return {"answer": mk.offline_answer(question, a), "provider": "offline"}

    # ---------- orders + export (ideas from the wa-organizer dashboard) ----------
    def orders(self, customer_id):
        return self.repo.db.query("SELECT * FROM orders WHERE customer_id=? ORDER BY id DESC", (int(customer_id),))
    def order_add(self, customer_id, item, amount=0):
        if not (item or "").strip(): raise ApiError("اكتب وش الطلب")
        return self.repo.db.execute("INSERT INTO orders(customer_id, item, amount) VALUES (?,?,?)", (int(customer_id), item.strip()[:200], float(amount or 0)))
    def order_status(self, id, status):
        if status not in ("جديد", "قيد التجهيز", "تم التوصيل", "ملغي"): raise ApiError("حالة غير معروفة")
        self.repo.db.execute("UPDATE orders SET status=? WHERE id=?", (status, int(id))); return True
    def export_contacts(self, fmt="csv"):
        rows = self.repo.db.query("SELECT name, phone, classification, need, last_contact FROM customers ORDER BY name")
        def cell(v):   # CSV formula-injection guard
            v = str(v or "").replace('"', '""'); return "'" + v if v[:1] in "=+-@" else v
        if fmt == "vcf":
            return "".join(f"BEGIN:VCARD\nVERSION:3.0\nFN:{(r['name'] or '').replace(chr(10), ' ')}\nTEL:{r['phone'] or ''}\nEND:VCARD\n" for r in rows if r["phone"])
        return "\ufeffالاسم,الجوال,التصنيف,الاحتياج,آخر تواصل\n" + "".join(",".join(f'"{cell(r[k])}"' for k in ("name", "phone", "classification", "need", "last_contact")) + "\n" for r in rows)

    QUICK_DEFAULT = ["أبشر، الحين أجهزه لك 🌷", "التوصيل داخل المدينة خلال ساعتين بإذن الله", "تبي أرسل لك صور الباقات المتوفرة اليوم؟", "الدفع تحويل أو عند الاستلام، اللي يناسبك", "تسلم، نورتنا 🌸"]
    def quick_replies(self):
        v = self.repo.get_setting("ui.quick_replies")
        return json.loads(v) if v else self.QUICK_DEFAULT
    def quick_replies_save(self, items):
        items = [str(x).strip()[:300] for x in items if str(x).strip()][:30]
        self.repo.set_setting("ui.quick_replies", json.dumps(items, ensure_ascii=False)); return items

    # ---------- dependencies / onboarding ----------
    def deps_fix(self):
        from app.core import deps
        deps.FIXER.start(); log_activity(self.repo.db, "deps_fix", "started"); return True
    def deps_log(self):
        from app.core import deps
        return {"state": deps.FIXER.state, "log": deps.FIXER.log[-4000:], "missing": deps.missing()}
    def onboarding_done(self, done=True):
        self.repo.set_setting("onboarding_done", "1" if done else "0"); return True

    # ---------- employee control ----------
    def _need_runner(self):
        if not self.runner:
            raise ApiError("محرك الأتمتة غير متاح")
        return self.runner
    def wa_open(self):
        from app.core import deps
        if "playwright" in deps.missing():
            raise ApiError("مكتبة Playwright غير مثبتة في بيئة البرنامج — اضغط «إصلاح تلقائي»")
        self._need_runner().open_whatsapp(); return True
    def wa_use_here(self): self._need_runner().use_here(); return True
    def browser_visible(self, visible):
        s = AutoReplySettings.load(self.repo); s.show_browser = bool(visible); s.save(self.repo)
        if self.runner: self.runner.set_browser_visible(bool(visible))
        return bool(visible)
    def gpt_check(self): self._need_runner().check_chatgpt(); return True
    def emp_start(self):
        if not AutoReplySettings.load(self.repo).auto_reply_enabled:
            raise ApiError("فعّل «الرد التلقائي» من صفحة سير عمل البوت أولاً")
        if KILL_SWITCH.engaged:
            raise ApiError("زر الإيقاف الفوري مفعّل — أعد التشغيل أولاً")
        self._need_runner().start(); return True
    def emp_stop(self):
        if self.runner: self.runner.stop()
        return True
    def kill_toggle(self):
        if KILL_SWITCH.engaged:
            KILL_SWITCH.release(); log_activity(self.repo.db, "kill_switch", "released")
        else:
            KILL_SWITCH.engage(); log_activity(self.repo.db, "kill_switch", "engaged", "WARNING")
            if self.runner: self.runner.stop()
        return KILL_SWITCH.engaged

    # ---------- dashboards ----------
    def overview(self):
        dist = {c: self.repo.db.scalar("SELECT COUNT(*) FROM customers WHERE classification=?", (c,)) or 0 for c in CLASSIFICATIONS}
        days = self.repo.db.query("SELECT date(created_at,'localtime') d, COUNT(*) n FROM auto_replies GROUP BY d ORDER BY d DESC LIMIT 14")
        return {"stats": self.repo.stats(), "recent": self.repo.inbox()[:8], "dist": dist, "days": days[::-1]}
    def inbox(self):
        live = self.runner.snapshot().get("chats", []) if self.runner else []
        return {"live": live, "analyzed": self.repo.inbox()}
    def wa_diagnose(self):
        self._need_runner().diagnose(); return True
    def analytics(self): return self.overview()
    def logs(self, limit=300): return self.repo.activity(limit)

    # ---------- CRM ----------
    def customers(self, q=""): return self.repo.customers(q)
    def customer_update(self, id, fields):
        self.repo.update_customer(int(id), **fields); log_activity(self.repo.db, "edit_customer", id); return True
    def customer_delete(self, id):
        self.repo.db.backup("pre-delete"); self.repo.delete_customer(int(id))
        log_activity(self.repo.db, "delete_customer", id, "WARNING"); return True
    def customers_delete_all(self):
        self.repo.db.backup("pre-delete-all"); self.repo.delete_all_customer_data()
        log_activity(self.repo.db, "delete_all_customers", "", "WARNING"); return True
    def customer_optout(self, id):
        self.repo.stop_follow_ups(int(id)); log_activity(self.repo.db, "opt_out", id); return True
    def pipeline(self):
        cs = self.repo.customers()
        return {st: [c for c in cs if c["stage"] == st] for st in PIPELINE_STAGES}

    # ---------- AI employee ----------
    def analyze(self, text, customer=""):
        r = self.svc.analyze_text(text, customer.strip() or None)
        r["reply_id"] = self.repo.db.scalar("SELECT id FROM suggested_replies WHERE analysis_id=?", (r["analysis_id"],))
        return r
    def reply_status(self, id, status):
        if status not in ("approved", "rejected"): raise ApiError("bad status")
        self.repo.set_reply_status(int(id), status); log_activity(self.repo.db, "reply_" + status, id); return True
    def auto_replies(self, limit=30):
        return self.repo.db.query("SELECT id, chat, incoming, reply, kind, classification, provider, created_at FROM auto_replies ORDER BY id DESC LIMIT ?", (limit,))
    def needs(self):
        return self.repo.db.query("SELECT id, chat, reason, last_message, created_at FROM needs_attention WHERE status='open' ORDER BY id DESC")
    def need_done(self, id):
        self.repo.db.execute("UPDATE needs_attention SET status='done' WHERE id=?", (int(id),)); return True

    # ---------- campaigns / follow-ups ----------
    def campaigns(self): return self.repo.campaigns()
    def campaign_add(self, name, segment, message):
        if not name.strip(): raise ApiError("اكتب اسم الحملة")
        cid = self.repo.add_campaign(name, segment, message); log_activity(self.repo.db, "campaign_draft", name); return cid
    def followups(self): return self.repo.follow_ups()
    def followup_done(self, id): self.repo.close_follow_up(int(id)); return True

    # ---------- workflow ----------
    def workflow_get(self):
        return {"wf": wfm.load(self.repo), "settings": asdict(AutoReplySettings.load(self.repo)), "products": self.repo.business_info()}
    def workflow_save(self, wf=None, settings=None):
        if wf is not None:
            wfm.save(self.repo, wf)
        if settings is not None:
            s = AutoReplySettings.load(self.repo)
            for k, v in settings.items():
                if hasattr(s, k):
                    cur = getattr(s, k)
                    v = (v in (True, 1, "1", "true", "True")) if isinstance(cur, bool) else type(cur)(v)
                    if isinstance(v, (int, float)) and not isinstance(v, bool) and v < 0: raise ApiError(f"قيمة سالبة: {k}")
                    setattr(s, k, v)
            if s.max_delay < s.min_delay: s.max_delay = s.min_delay
            s.save(self.repo)
        log_activity(self.repo.db, "workflow_saved", "")
        return self.workflow_get()
    def product_save(self, title, kind="منتج", content="", price="", id=None):
        if not title.strip(): raise ApiError("اكتب اسم المنتج")
        if id:
            self.repo.db.execute("UPDATE business_info SET kind=?, title=?, content=?, price=? WHERE id=?", (kind, title, content, price.strip(), int(id)))
        else:
            id = self.repo.add_business_info(kind, title, content, price.strip())
        log_activity(self.repo.db, "product_saved", title); return id
    def product_delete(self, id): self.repo.delete_business_info(int(id)); return True
    def workflow_reset(self):
        self.repo.db.backup("pre-workflow-reset"); wfm.reset(self.repo); log_activity(self.repo.db, "workflow_reset"); return self.workflow_get()
    def workflow_export(self): return wfm.export_json(self.repo)
    def workflow_import(self, text):
        self.repo.db.backup("pre-workflow-import"); wfm.import_json(self.repo, text)
        log_activity(self.repo.db, "workflow_import"); return self.workflow_get()
    def simulate(self, text, name="عميل"):
        if not text.strip(): raise ApiError("اكتب رسالة للتجربة")
        return wfm.simulate(self.repo, text, name or "عميل")

    # ---------- data ----------
    def backup(self):
        d = self.repo.db.backup("manual"); log_activity(self.repo.db, "backup", d); return str(d)

    # ---------- PRO: built-in brain, orders, reports, backup, reminders, campaigns ----------
    def brain_test(self, text, customer=""):
        from app.brain import think
        return think(text or "", customer, repo=self.repo)
    def brain_kb(self):
        from app.brain.knowledge import load_kb
        return load_kb(self.repo)
    def brain_kb_save(self, kb):
        from app.brain.knowledge import save_kb, default_kb
        if not isinstance(kb, dict): raise ApiError("بيانات غير صحيحة")
        base = default_kb()
        clean = {k: v for k, v in kb.items() if k in base and isinstance(v, type(base[k]))}
        for p in clean.get("products", []):
            if not str(p.get("name", "")).strip(): raise ApiError("كل منتج يحتاج اسم")
            if p.get("price") not in (None, ""):
                try: p["price"] = float(p["price"])
                except (TypeError, ValueError): raise ApiError(f"سعر غير صحيح: {p.get('name')}")
            p.setdefault("aliases", []); p.setdefault("unit", "بوكيه"); p.setdefault("category", "بوكيه")
        save_kb(self.repo, {**self.brain_kb(), **clean}); return True
    def brain_kb_reset(self):
        self.repo.set_setting("brain.kb", ""); return True
    def ai_status(self):
        from app.ai.providers import detect_ollama
        s = AutoReplySettings.load(self.repo)
        return {"builtin": True, "ollama": detect_ollama(), "chatgpt_experimental": s.chatgpt_experimental, "provider": s.provider}
    def orders_board(self):
        from app.core import pro; return pro.orders_board(self.repo)
    def order_update(self, id, fields):
        from app.core import pro
        try: return pro.order_update(self.repo, id, fields)
        except ValueError as e: raise ApiError(str(e))
    def reports(self, days=30):
        from app.core import pro; return pro.reports(self.repo, int(days))
    def reminders_due(self):
        from app.core import pro; return pro.due_reminders(self.repo)
    def reminder_add(self, due_at, text, customer_id=None, chat=""):
        from app.core import pro
        if not (due_at and text): raise ApiError("حدد الوقت والنص")
        return pro.add_reminder(self.repo, due_at.replace("T", " "), text[:300], customer_id, chat)
    def reminder_done(self, id):
        from app.core import pro; return pro.reminder_done(self.repo, id)
    def campaign_suggestions(self, days=120):
        from app.core import pro; return pro.campaign_suggestions(self.repo, days=int(days))
    def backup_now(self):
        return str(self.repo.db.backup(tag="manual"))
    def backup_export(self):
        from app.core import pro; return pro.export_zip(self.repo.db)
    def backup_restore(self, path):
        from app.core import pro
        try: return pro.restore_zip(self.repo.db, path)
        except (ValueError, OSError, KeyError) as e: raise ApiError(f"ما قدرت أسترجع: {e}")
    def backups_list(self):
        from app import config
        return [p.name for p in sorted(config.BACKUP_DIR.glob("employee-*.db"), reverse=True)] if config.BACKUP_DIR.exists() else []
    def pro_settings(self):
        s = AutoReplySettings.load(self.repo)
        return {"after_hours_auto": s.after_hours_auto, "retention_days": s.retention_days, "backup_daily": s.backup_daily,
                "chatgpt_experimental": s.chatgpt_experimental, "provider": s.provider, "send_mode": s.send_mode}
    def pro_settings_save(self, after_hours_auto=False, retention_days=0, backup_daily=True, chatgpt_experimental=False, provider="offline"):
        s = AutoReplySettings.load(self.repo)
        if provider not in ("offline", "auto", "ollama", "chatgpt_web"): raise ApiError("مزود غير معروف")
        if provider == "chatgpt_web" and not chatgpt_experimental: raise ApiError("ChatGPT تجريبي — فعّل الخيار التجريبي أول")
        s.after_hours_auto, s.retention_days, s.backup_daily = bool(after_hours_auto), max(0, int(retention_days or 0)), bool(backup_daily)
        s.chatgpt_experimental, s.provider = bool(chatgpt_experimental), provider
        s.send_mode = "approval"   # approval stays the default; only safe after-hours intents may go out automatically
        s.save(self.repo); return True

