"""Editable bot workflow: business profile, ordered rules, templates, tone, ChatGPT prompt,
working hours. Persisted as JSON in settings('workflow'); read fresh on every cycle (live)."""
import copy, json, re, uuid
from dataclasses import dataclass
from datetime import datetime
from app.ai import analyzer
from app.ai.analyzer import _norm

TRIGGERS = {"keywords": "كلمات مفتاحية", "classification": "تصنيف العميل", "price_question": "سؤال عن السعر",
            "missing_price": "سعر غير موجود في المعلومات", "greeting": "تحية", "opt_out": "طلب إيقاف الرسائل",
            "handoff": "شكوى أو طلب موظف", "faq": "سؤال من الأسئلة الشائعة", "always": "أي رسالة"}
ACTIONS = {"reply": "رد بنص القالب", "holding": "رد مؤقت + تنبيه «يحتاجك»", "stop": "إيقاف الرد على العميل",
           "mark": "تعيين التصنيف/المرحلة ثم متابعة", "ai": "رد ذكي (المحلل/ChatGPT)", "ignore": "تجاهل بدون رد"}
TERMINAL = {"reply", "holding", "stop", "ai", "ignore"}

DEFAULT_PROMPT = ("أنت موظف مبيعات في {business_name}. اكتب رداً واحداً قصيراً (أقل من {max_len} حرف) باللهجة {dialect} العامية البسيطة مثل كلام الناس في واتساب (هلا، أبشر، وش تحتاج، الحين، ما عليك أمر) — مو فصحى ولا ترجمة، "
                  "على آخر رسالة من {customer}. استخدم فقط معلومات النشاط التالية ولا تخترع أسعاراً أو وعوداً. "
                  "{emoji_rule}\n\nمعلومات النشاط:\n{business}\n\nالمحادثة:\n{chat}")

GREETING_WORDS = ["السلام عليكم", "سلام", "هلا", "مرحبا", "اهلين", "صباح الخير", "مساء الخير", "hi", "hello"]

def _rule(name, trigger, action, value="", text="", set_class="", enabled=True):
    return {"id": uuid.uuid4().hex[:8], "name": name, "enabled": enabled, "trigger": trigger, "value": value,
            "action": action, "text": text, "set_class": set_class}

def default_workflow():
    return {
        "version": 1,
        "enabled": True,          # master switch inside workflow (AND-ed with auto_reply_enabled)
        "business": {"name": "", "description": "", "location": "", "hours": "", "faq": []},
        "working_hours": {"enabled": False, "start": "09:00", "end": "23:00", "away_enabled": False},
        "templates": {"greeting": "هلا والله يا {name}، حياك! وش أقدر أخدمك فيه؟",
                      "holding": "أبشر، بيتواصل معك الزميل المختص قريب",
                      "away": "هلا {name}، وصلت رسالتك وبنرد عليك أول ما نبدأ الدوام إن شاء الله.",
                      "opt_out": "", "fallback": "هلا {name}، وصلت رسالتك وبنرد عليك بأقرب وقت."},
        "tone": {"dialect": "السعودية", "max_len": 300, "emoji": True},
        "chatgpt_prompt": DEFAULT_PROMPT,
        # seed = exact built-in behavior
        "rules": [
            _rule("طلب إيقاف الرسائل", "opt_out", "stop"),
            _rule("شكوى أو طلب موظف", "handoff", "holding"),
            _rule("سعر غير معروف", "missing_price", "holding"),
            _rule("أسئلة شائعة", "faq", "reply"),
            _rule("ترحيب بقالب ثابت", "greeting", "reply", text="{greeting}", enabled=False),
            _rule("رد ذكي لباقي الرسائل", "always", "ai"),
        ],
    }

def _merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base

def validate(wf):
    if not isinstance(wf, dict) or not isinstance(wf.get("rules", []), list):
        raise ValueError("ملف سير عمل غير صالح")
    out = _merge(default_workflow(), copy.deepcopy(wf))
    for r in out["rules"]:
        if r.get("trigger") not in TRIGGERS or r.get("action") not in ACTIONS:
            raise ValueError(f"قاعدة غير صالحة: {r.get('name')}")
        r.setdefault("id", uuid.uuid4().hex[:8]); r.setdefault("enabled", True)
        for k in ("value", "text", "set_class", "name"): r.setdefault(k, "")
    for p in ("start", "end"):
        datetime.strptime(out["working_hours"][p], "%H:%M")
    out["tone"]["max_len"] = int(out["tone"]["max_len"])
    return out

def load(repo):
    raw = repo.get_setting("workflow", "")
    if not raw:
        return default_workflow()
    try:
        return validate(json.loads(raw))
    except Exception:
        return default_workflow()

def save(repo, wf):
    wf = validate(wf)
    repo.set_setting("workflow", json.dumps(wf, ensure_ascii=False))
    return wf

def reset(repo):
    return save(repo, default_workflow())

# ---------- export / import (workflow + timing settings + products) ----------
def export_json(repo):
    from app.core.settings import AutoReplySettings
    from dataclasses import asdict
    return json.dumps({"workflow": load(repo), "settings": asdict(AutoReplySettings.load(repo)),
                       "products": [{k: b[k] for k in ("kind", "title", "content", "price")} for b in repo.business_info()]},
                      ensure_ascii=False, indent=2)

def import_json(repo, text):
    from app.core.settings import AutoReplySettings
    data = json.loads(text)
    wf = validate(data.get("workflow", data))
    s = AutoReplySettings()
    for k, v in (data.get("settings") or {}).items():
        if hasattr(s, k) and k != "auto_reply_enabled":   # never auto-enable sending via import
            setattr(s, k, type(getattr(s, k))(v))
    s.auto_reply_enabled = AutoReplySettings.load(repo).auto_reply_enabled
    with repo.db.transaction() as c:
        if "products" in data:
            c.execute("DELETE FROM business_info")
            c.executemany("INSERT INTO business_info(kind,title,content,price) VALUES (?,?,?,?)",
                          [(p.get("kind", "منتج"), p["title"], p.get("content", ""), p.get("price", "")) for p in data["products"]])
    s.save(repo); save(repo, wf)
    return wf

# ---------- runtime helpers ----------
def in_working_hours(wf, now=None):
    wh = wf["working_hours"]
    if not wh["enabled"]:
        return True
    t = (now or datetime.now()).strftime("%H:%M")
    s, e = wh["start"], wh["end"]
    return s <= t < e if s <= e else (t >= s or t < e)   # supports overnight ranges

def business_items(repo, wf):
    """Approved products + profile + FAQ, as items the orchestrator/ChatGPT may use."""
    items = list(repo.business_info())
    b = wf["business"]
    for title, val in (("اسم النشاط", b["name"]), ("عن النشاط", b["description"]), ("الموقع", b["location"]), ("أوقات العمل", b["hours"])):
        if val:
            items.append({"title": title, "content": val, "price": "", "kind": "info"})
    for f in b["faq"]:
        items.append({"title": f.get("q", ""), "content": f.get("a", ""), "price": "", "kind": "faq"})
    return items

def fill(template, wf, name=""):
    t = wf["templates"]
    s = (template or "").replace("{greeting}", t["greeting"]).replace("{holding}", t["holding"]) \
        .replace("{away}", t["away"]).replace("{fallback}", t["fallback"])
    s = s.replace("{name}", name or "").replace("{business_name}", wf["business"]["name"] or "")
    return apply_tone(s, wf)

_EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\U0001F1E6-\U0001F1FF]")
def apply_tone(text, wf):
    text = re.sub(r"\s+", " ", text).strip()
    if not wf["tone"]["emoji"]:
        text = _EMOJI.sub("", text).strip()
    m = wf["tone"]["max_len"]
    if m and len(text) > m:
        text = text[:m].rsplit(" ", 1)[0] + "…"
    return text

def faq_answer(wf, text):
    nt = _norm(text)
    best, score = None, 0
    for f in wf["business"]["faq"]:
        words = [w for w in _norm(f.get("q", "")).replace("؟", " ").split() if len(w) > 2]
        hit = sum(1 for w in words if w in nt)
        if words and hit / len(words) >= 0.5 and hit > score:
            best, score = f, hit
    return best

@dataclass
class Decision:
    action: str            # reply|holding|stop|ai|ignore
    rule: str = ""
    reply: str = ""
    classification: str = "New Lead"
    reason: str = ""
    set_class: str = ""

def evaluate(wf, texts, customer, business, opt_out_words):
    """Run enabled rules in order on the new incoming texts. Pure (no I/O)."""
    joined = " ".join(texts)
    nt = _norm(joined)
    cls, _ = analyzer.classify(texts)
    matched = analyzer.match_business(texts, business)
    if cls == "New Lead" and matched:
        cls = "Interested"
    handoff, reason = analyzer.detect_handoff(texts, cls)
    asked_price = bool(re.search(r"(سعر|بكم|كم تكلف|تكلفه|price|cost)", nt))
    priced = any(b.get("price") for b in matched)
    set_class = ""
    for r in wf["rules"]:
        if not r.get("enabled", True):
            continue
        t, v = r["trigger"], r.get("value", "")
        faq = None
        if t == "keywords":
            hit = any(_norm(k.strip()) in nt for k in re.split("[,،]", v) if k.strip())
        elif t == "classification":
            hit = cls == v or (set_class and set_class == v)
        elif t == "price_question":
            hit = asked_price
        elif t == "missing_price":
            hit = asked_price and not priced
        elif t == "greeting":
            hit = any(_norm(g) in nt for g in GREETING_WORDS) and len(joined) < 40
        elif t == "opt_out":
            hit = any(_norm(w) in nt for w in opt_out_words)
        elif t == "handoff":
            hit = handoff
        elif t == "faq":
            faq = faq_answer(wf, joined); hit = faq is not None
        else:
            hit = True
        if not hit:
            continue
        a = r["action"]
        if a == "mark":
            set_class = r.get("set_class") or set_class
            continue
        d = Decision(a, r["name"], "", set_class or cls, reason if t == "handoff" else (
            "سعر غير موجود في معلومات النشاط" if t == "missing_price" else r["name"]), set_class)
        if a == "reply":
            d.reply = apply_tone(faq["a"], wf) if (faq and not r.get("text")) else fill(r.get("text") or "{fallback}", wf, customer)
        elif a == "holding":
            d.reply = fill(r.get("text") or "{holding}", wf, customer)
        elif a == "stop":
            tmpl = r.get("text") or wf["templates"].get("opt_out", "")
            d.reply = fill(tmpl, wf, customer) if tmpl else ""
        return d
    return Decision("ai", "(افتراضي)", "", set_class or cls, "", set_class)

def simulate(repo, text, customer="عميل تجريبي", wf=None):
    """Dry run for the UI test box: which rule fires and the exact reply. Never sends.
    AI replies are generated with the offline analyzer here (ChatGPT not called)."""
    from app.core.parser import parse_chat, Message
    from app.core.settings import AutoReplySettings
    from app.ai.orchestrator import Orchestrator
    wf = wf or load(repo)
    s = AutoReplySettings.load(repo)
    msgs = parse_chat(text) or [Message(customer, text)]
    msgs = [Message(customer, m.text, m.timestamp) for m in msgs]
    texts = [m.text for m in msgs]
    business = business_items(repo, wf)
    d = evaluate(wf, texts, customer, business, s.opt_out_list)
    out = {"rule": d.rule, "action": d.action, "action_ar": ACTIONS[d.action], "classification": d.classification,
           "reply": d.reply, "reason": d.reason, "in_hours": in_working_hours(wf), "provider": "rule"}
    if d.action == "ai":
        r = Orchestrator(workflow=wf).run(msgs, customer, business, [])
        out.update(reply=r["reply"], provider=r["provider"] + " (تجربة بدون ChatGPT)")
    return out
