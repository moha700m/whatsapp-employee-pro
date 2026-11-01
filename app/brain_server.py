"""Local brain HTTP service for the WhatsApp engine (127.0.0.1 only, shared-key protected).
Free and offline: rules + Saudi knowledge base. No model downloads, no network calls."""
import json, os, random, threading, hmac, re
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import date, timedelta
from app.brain.engine import Brain, think, SAFE_AUTO
from app.brain.knowledge import default_kb, upcoming_occasions
from app.brain.normalize import norm
from app.brain import ai as AI
from app.brain.llm import LocalLLM

LLM = None   # created lazily by BrainServer (one per app)
def llm_on(body):
    """AI is used only if the owner left it on, the model files exist, RAM ≥ 6 GB and it has not been failing."""
    return LLM is not None and body.get("ai") is True and LLM.available()[0]

AR_DAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
AR_MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
def humanize(text):
    """2026-11-01 → «الأحد ١ نوفمبر», 16:00 → «٤ العصر» — reads naturally in a WhatsApp reply."""
    import re
    def d(m):
        try: x = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError: return m.group(0)
        return f"{AR_DAYS[x.weekday()]} {x.day} {AR_MONTHS[x.month - 1]}"
    def t(m):
        h = int(m.group(1)); mi = m.group(2)
        per = "الصبح" if h < 12 else "الظهر" if h < 15 else "العصر" if h < 18 else "المغرب" if h < 19 else "الليل"
        h12 = h % 12 or 12
        return f"{h12}{'' if mi == '00' else ':' + mi} {per}"
    text = re.sub(r"(\d{4})-(\d{2})-(\d{2})", d, text)
    return re.sub(r"(?<![\d:])(\d{1,2}):(\d{2})(?![\d:])", t, text)

HANDOFF_KINDS = {"handoff", "order_confirm", "order_collect", "price", "price_unknown", "guarded", "objection", "stop"}

def make_kb(body):
    kb = default_kb()
    shop = body.get("shop") or {}
    for k in ("name", "location", "hours", "city", "delivery", "about"):
        if isinstance(shop.get(k), str) and shop[k].strip(): kb["shop"][k] = shop[k].strip()
    prods = body.get("products")
    if isinstance(prods, list) and prods:
        clean = []
        for p in prods[:200]:
            if not isinstance(p, dict) or not str(p.get("name", "")).strip(): continue
            try: price = float(p.get("price") or 0) or None
            except (TypeError, ValueError): price = None
            clean.append({"name": str(p["name"]).strip()[:60], "aliases": [str(a)[:40] for a in (p.get("aliases") or [])][:10],
                          "price": price, "unit": str(p.get("unit") or "بوكيه")[:20], "category": str(p.get("category") or "بوكيه")[:20]})
        if clean: kb["products"] = clean
    return kb

def incoming(messages, n=8):
    return [m.get("text", "") for m in (messages or []) if not m.get("fromMe") and m.get("text")][-n:]

def do_think(body):
    kb = make_kb(body); text = str(body.get("text", ""))[:2000]; teach = body.get("teach") or {}
    r = think(text, str(body.get("customer", ""))[:60], kb=kb, after_hours=bool(body.get("after_hours")))
    r["reply"] = humanize(r["reply"])
    r["handoff"] = r["kind"] in HANDOFF_KINDS or bool({"order", "price", "complaint", "human", "stop"} & set(r["intents"]))
    h = AI.handoff_hit(teach, text)
    if h: r["handoff"] = True; r["handoff_reason"] = h
    fa = AI.faq_answer(teach, text)
    if fa and not r["handoff"]: r["reply"], r["kind"], r["safe_auto"] = fa, "faq", True
    r["engine"] = "rules"
    if fa or r["kind"] in ("stop",) or not llm_on(body): return r
    try:
        out, issues = AI.ai_reply(LLM, Brain(kb=kb), kb, teach, text, AI.history_msgs([m for m in (body.get("messages") or []) if m.get("text") != text][-4:]), rule_reply=r["reply"])
        if not issues: r["reply"], r["engine"] = out, "ai"
        else: r["ai_rejected"] = issues
    except Exception as e: r["ai_error"] = str(e)[:120]
    return r

STATUS_RE = re.compile(r"(طلبي|طلبيتي|طلبنا|البوكيه حقي|الورد حقي|اللي طلبته).{0,20}(وين|متى|وصل|جاهز|صار|خلص)|(وين|متى|ليش).{0,12}(طلبي|طلبنا|طلبيتي)|(ما وصل|تأخر|تاخر) (طلبي|الطلب)")
INTENT_AR = {"complaint": "شكوى", "price": "السعر", "order": "طلب جديد", "delivery": "التوصيل أو الدفع أو الموقع", "status": "حالة طلبه", "meaning": "معنى ورد", "care": "العناية بالورد",
             "catalog": "وش عندكم", "thanks": "شكر", "greeting": "سلام وترحيب", "human": "يبي يكلم شخص", "unknown": "سؤال عام"}
REL = {"price": r"\d|ريال|ر\.س|سعر|بـ", "delivery": r"توصيل|نوصل|يوصل|التوصيل|الحي|الدفع|ندفع|مدى|تحويل|موقع|الدوام|نفتح", "status": r"طلب|يوصل|جاهز|نتأكد|أتأكد|اتأكد|بشيك|موعد",
       "complaint": r"آسف|اسف|نعتذر|حقك|نعوضك|نعوّضك|أبشر|ابشر|نشوف", "greeting": r"هلا|حياك|أهلا|اهلا|وعليكم|مرحبا|يا هلا", "thanks": r"العفو|حياك|تسلم|الله يسعدك|بالعافية|بالعافيه|نتشرف",
       "order": r"طلب|نجهز|أبشر|ابشر|المناسبة|المناسبه|التوصيل|متى|ريال|بوكيه", "care": r"موي|ماء|قص|شمس|يعيش|برود", "meaning": r"يرمز|معنى|يعني|رمز", "catalog": r"عندنا|بوكيه|تنسيق|ورد|صور",
       "human": r"المسؤول|أكلمك|اتصل|نكلمك|يرد عليك", "unknown": r"."}
def focus_texts(messages):
    """The customer messages that are still waiting for an answer (after our last reply). That is what a suggestion must answer."""
    ms = [m for m in (messages or []) if m.get("text")]; last_out = max([i for i, m in enumerate(ms) if m.get("fromMe")], default=-1)
    t = [m["text"] for m in ms[last_out + 1:] if not m.get("fromMe")]
    return t[-4:] or [m["text"] for m in ms if not m.get("fromMe")][-1:]
def main_intent(b, text):
    if STATUS_RE.search(text): return "status"
    its = [i for i in b.intents(text) if i != "stop"]
    for k in ("complaint", "human", "status", "price", "order", "delivery", "meaning", "care", "catalog", "thanks", "greeting"):
        if k in its: return k
    return "unknown"
def relevant(reply, intent):
    return bool(reply) and bool(re.search(REL.get(intent, "."), reply))

def do_suggest(body):
    """3 short Saudi replies to what the customer is asking NOW (unanswered messages), grounded in the shop data; never random text."""
    kb = make_kb(body); b = Brain(kb=kb, rng=random.Random(0)); teach = body.get("teach") or {}
    texts = focus_texts(body.get("messages"))
    if not texts: return {"replies": [], "intent": None}
    text = " ".join(texts)[-800:]; intent = main_intent(b, text); out = []; engine = "rules"
    def add(x):
        x = humanize(x).strip() if x else ""
        if x and x not in out and relevant(x, intent) and not AI.forbidden_hit(teach, x) and not b.guard(x, b.extract(text)): out.append(x)
    fa = AI.faq_answer(teach, texts[-1]) or AI.faq_answer(teach, text)
    if fa: out.append(fa)
    dl = str((kb.get("shop") or {}).get("delivery") or "").strip()
    if intent == "delivery" and dl: add(dl.rstrip(".") + " 🌷")
    if intent == "status":
        for x in ("أبشر 🌷 بشيك على طلبك الحين وأرد عليك خلال دقايق.", "طلبك عندنا وبإذن الله على موعده، بتأكد من وقت التوصيل وأبلغك 🌷", "حياك، عطني اسم صاحب الطلب أو رقمه وأتأكد لك فوراً."): add(x)
    else:
        for seed in range(10):
            r = think(text, str(body.get("customer", "")), kb=kb, rng=random.Random(seed)); add(r["reply"])
            if len(out) >= 3: break
    if llm_on(body) and len(out) < 4 and intent != "status":
        try:
            hint = f"العميل الحين يسأل عن: {INTENT_AR.get(intent, '')}. رد على آخر رسالة له بس، جملة أو جملتين، وما تذكر أي سعر أو منتج مو موجود في المعلومات."
            a, issues = AI.ai_reply(LLM, Brain(kb=kb), kb, teach, text, AI.history_msgs(body.get("messages"), 10)[:-1] if body.get("messages") else [], rule_reply=out[0] if out else "", hint=hint)
            if not issues and relevant(a, intent) and a not in out: out.insert(1 if fa else 0, a); engine = "ai"
        except Exception: pass
    r = think(text, str(body.get("customer", "")), kb=kb, rng=random.Random(0))
    return {"replies": out[:3], "intent": intent, "intent_ar": INTENT_AR.get(intent), "intents": r["intents"], "missing": r["missing"], "score": r["lead_score"], "engine": engine}

def do_extract(body):
    kb = make_kb(body); b = Brain(kb=kb, rng=random.Random(0)); texts = incoming(body.get("messages"), 20)
    if not texts: return {"orders": [], "stage": "جديد", "score": 0, "reason": "ما فيه رسائل من العميل", "summary": ""}
    joined = " ".join(texts); ents = {}
    for t in texts: ents.update({k: v for k, v in b.extract(t).items() if v})
    intents = set(); [intents.update(b.intents(t)) for t in texts[-5:]]
    objections = b.objections(" ".join(texts[-3:]))
    score, temp = b.lead_score(list(intents), ents, objections)
    orders = []
    if ents.get("items"):
        tot = b.total(ents)
        addr = " - ".join(x for x in [("حي " + ents["district"]) if ents.get("district") else "", ents.get("city", ""), ents.get("location_link", "")] if x)
        orders.append({"item": (f"{ents['quantity']} × " if ents.get("quantity") else "") + "، ".join(ents["items"]),
                       "amount": tot or ents.get("amount") or 0, "deliveryDate": ents.get("date", ""), "time": ents.get("time", ""),
                       "address": addr, "occasion": ents.get("occasion", ""), "card": ents.get("card_text", "")})
    stage = "طلب" if "order" in intents and ents.get("items") else "مهتم" if intents & {"price", "order", "catalog", "delivery"} else "جديد"
    if any(w in joined for w in ("وصل", "استلمت")) and "complaint" not in intents: stage = "تم التوصيل"
    reasons = []
    if "order" in intents: reasons.append("طلب صريح")
    if "price" in intents: reasons.append("سأل عن السعر")
    if ents.get("date"): reasons.append("حدد موعد")
    if ents.get("district") or ents.get("location_link"): reasons.append("أرسل العنوان")
    if objections: reasons.append("متردد")
    if "complaint" in intents: reasons.append("عنده شكوى")
    summ = "، ".join(x for x in [", ".join(ents.get("items", [])), ents.get("occasion", ""), ents.get("date", ""), ents.get("district", "")] if x)
    res = {"orders": orders, "stage": stage, "score": score, "temperature": temp, "reason": "، ".join(reasons) or "استفسار عام",
           "summary": summ, "missing": b.missing_for_order(ents) if "order" in intents else [], "entities": ents, "engine": "rules"}
    if llm_on(body):
        try:
            names = [p["name"] for p in kb["products"]]
            j = AI.ai_json(LLM, "استخرج طلب العميل من محادثة واتساب لمحل ورد. رجّع JSON فقط بالمفاتيح: items (قائمة من هذي الأسماء فقط: " + "، ".join(names[:40]) +
                           "), quantity (رقم), date (YYYY-MM-DD أو فاضي), time (HH:MM أو فاضي), district, card (نص البطاقة), occasion, summary (جملة سعودية قصيرة عن وش يبي العميل).", "\n".join(texts[-12:]))
            its = [i for i in (j.get("items") or []) if i in names]
            if its and not orders:
                e2 = {**ents, "items": its, **({"quantity": int(j["quantity"])} if str(j.get("quantity", "")).isdigit() else {})}
                orders.append({"item": (f"{e2['quantity']} × " if e2.get("quantity") else "") + "، ".join(its), "amount": b.total(e2) or 0,
                               "deliveryDate": ents.get("date") or (j.get("date") if re.match(r"^\d{4}-\d\d-\d\d$", str(j.get("date", ""))) else ""),
                               "time": ents.get("time") or (j.get("time") if re.match(r"^\d\d:\d\d$", str(j.get("time", ""))) else ""),
                               "address": ents.get("district") or str(j.get("district") or "")[:60], "occasion": ents.get("occasion") or str(j.get("occasion") or "")[:30], "card": str(j.get("card") or "")[:120]})
            if isinstance(j.get("summary"), str) and AI.AR.search(j["summary"]): res["summary"] = j["summary"][:160]
            res["engine"] = "ai"
        except Exception: pass
    return res

POS = ["شكرا", "تسلم", "يعطيك العافيه", "حلو", "روعه", "جميل", "ممتاز", "الله يسعدك", "تجنن", "عجبني", "عجبها", "مشكور", "❤", "😍", "🌹"]
NEG = ["سيء", "زعلان", "متاخر", "تاخر", "ما وصل", "ذابل", "ذبلان", "غالي", "مو حلو", "خربان", "مو نفس", "استرجاع", "😡", "😠"]
NAME_RX = re.compile(r"(?:معك|معاك|اسمي|أنا|انا)\s+([\u0621-\u064A]{2,15}(?:\s+[\u0621-\u064A]{2,15})?)")

def do_profile(body):
    """Auto customer profile from the whole chat (local, offline). Never invents prices; amounts come from the chat or the owner's orders."""
    kb = make_kb(body); b = Brain(kb=kb, rng=random.Random(0))
    msgs = [m for m in (body.get("messages") or []) if m.get("text")][-300:]
    inc = [m["text"] for m in msgs if not m.get("fromMe")]
    orders = [o for o in (body.get("orders") or []) if isinstance(o, dict)]
    today = date.today()
    if not inc and not orders: return {"empty": True}
    ents, items, occs, amounts, intents = {}, [], [], [], set()
    for t in inc:
        e = b.extract(t, today)
        for k in ("district", "city", "location_link", "phone", "date", "time", "card_text"):
            if e.get(k): ents[k] = e[k]
        for it in e.get("items", []):
            if it not in items: items.append(it)
        if e.get("occasion") and e["occasion"] not in occs: occs.append(e["occasion"])
        if e.get("amount"): amounts.append(e["amount"])
        intents.update(b.intents(t))
    name = ""
    for t in inc:
        m = NAME_RX.search(t)
        if m and not any(w in m.group(1) for w in ("ابي", "ابغي", "ودي", "طالب", "بطلب", "محتاج")): name = m.group(1)
    nt = norm(" ".join(inc[-20:]))
    pos = sum(nt.count(norm(w)) for w in POS); neg = sum(nt.count(norm(w)) for w in NEG)
    sentiment = "سلبي" if neg > pos else "إيجابي" if pos > 0 else "محايد"
    spent = sum(float(o.get("amount") or 0) for o in orders if o.get("status") != "ملغي")
    done = [o for o in orders if o.get("status") == "تم التوصيل"]
    budget = max(amounts) if amounts else None
    asked_price = [b.price_of(i) for i in items if b.price_of(i)]
    potential = spent or budget or (max(asked_price) if asked_price else 0)
    value = "VIP" if spent >= 1000 or len(done) >= 3 else "عالي" if spent >= 400 or len(orders) >= 2 else "متوسط" if (spent or budget or items) else "جديد"
    last = msgs[-1] if msgs else {}
    score, temp = b.lead_score(list(intents), {**ents, "items": items, "occasion": occs[0] if occs else None, "amount": budget}, b.objections(" ".join(inc[-3:])))
    # next best action
    if "complaint" in intents and sentiment == "سلبي": nba, fu = "اتصل عليه وحل الشكوى قبل أي عرض", 0
    elif last and not last.get("fromMe") and ({"order", "price"} & intents): nba, fu = "رد عليه الحين بالسعر وأكّد الطلب", 0
    elif items and not orders: nba, fu = "أرسل له صور " + items[0] + " واسأله عن الموعد", 1
    elif done: nba, fu = "اشكره واطلب رأيه، واقترح " + (b.upsell({"items": items})[:1] or ["بطاقة إهداء"])[0] + " للطلب الجاي", 14
    elif "wait" in b.objections(" ".join(inc[-3:])): nba, fu = "ذكّره بلطف وثبّت له الموعد", 2
    else: nba, fu = "رحّب فيه واسأله وش المناسبة", 1
    follow = (today + timedelta(days=fu)).isoformat()
    for o in occs:
        od = kb["occasions"].get(o, {}).get("date")
        if od:
            m_, d_ = map(int, od.split("-")); nd = date(today.year, m_, d_)
            if nd < today: nd = date(today.year + 1, m_, d_)
            if (nd - today).days <= 60: follow = min(follow, (nd - timedelta(days=5)).isoformat()) if nd - timedelta(days=5) > today else follow
    ai_note = ""
    if body.get("deep") and llm_on(body):
        try:
            j = AI.ai_json(LLM, "أنت مساعد مبيعات لمحل ورد سعودي. اقرأ رسائل العميل ورجّع JSON فقط: {\"summary\": جملة سعودية قصيرة تلخص العميل ووش يبي, \"next\": أفضل خطوة جاية لصاحب المحل بجملة قصيرة}.", "\n".join(inc[-15:]), 140, wait=1)
            if isinstance(j.get("next"), str) and AI.AR.search(j["next"]) and not AI.guard(b, j["next"], body.get("teach")): nba = j["next"][:120]
            if isinstance(j.get("summary"), str) and AI.AR.search(j["summary"]): ai_note = j["summary"][:160]
        except Exception: pass
    return {"summary": ai_note, "name": name, "district": ents.get("district", ""), "city": ents.get("city", ""), "location": ents.get("location_link", ""),
            "occasions": occs, "items": items[:8], "budget": budget, "amounts": amounts[-5:], "orders": len(orders), "spent": spent,
            "value": value, "potential": potential, "sentiment": sentiment, "score": score, "temperature": temp,
            "nextAction": nba, "followUp": follow, "intents": sorted(intents - {"unknown"})}

def do_insight(body):
    """Short 'why it matters' for a waiting chat: intents + items + an estimated value from the price table (no invented prices)."""
    kb = make_kb(body); b = Brain(kb=kb, rng=random.Random(0)); texts = incoming(body.get("messages"), 4)
    if not texts: return {"intents": [], "items": [], "value": 0}
    t = " ".join(texts); e = b.extract(t); it = b.intents(t)
    val = b.total(e) or max([b.price_of(i) or 0 for i in e.get("items", [])] or [0]) or e.get("amount") or 0
    return {"intents": it, "items": e.get("items", []), "occasion": e.get("occasion"), "value": val, "objections": b.objections(t)}

def do_plan_text(body):
    """2 short Saudi sentences that open the daily plan (AI if on, otherwise a simple rule sentence)."""
    items = [str(x)[:120] for x in (body.get("items") or [])][:6]
    base = ("عندك اليوم " + str(len(items)) + " مهام، ابدأ بأولها 💪") if items else "يومك هادي، استغله في متابعة عملائك القدامى 🌷"
    if not items or not llm_on(body): return {"text": base, "engine": "rules"}
    try:
        t = LLM.chat([{"role": "system", "content": "أنت مساعد سعودي لصاحب محل ورد. اكتب جملتين قصيرتين باللهجة السعودية تشجعه وتقول له وش يبدأ فيه اليوم، بدون أرقام أسعار وبدون قوائم."},
                      {"role": "user", "content": "مهام اليوم:\n" + "\n".join(items)}], max_tokens=90, temperature=0.6, wait=1)
        t = AI.clean(t)
        if AI.AR.search(t) and not re.search(r"\d{3,}", t): return {"text": t, "engine": "ai"}
    except Exception: pass
    return {"text": base, "engine": "rules"}

MKT_LIB = {
    "cold": ["هلا {الاسم} 🌷 سألتنا قبل عن الورد، حبيت أطمن هل لقيت اللي تبيه؟ إذا تبي أرسل لك صور تنسيقات اليوم أبشر.",
             "هلا {الاسم}، عساك بخير 🌸 للحين نقدر نجهز لك اللي سألت عنه، تحب أحجزه لك؟",
             "هلا {الاسم} 🌹 ما نسيناك! وصلنا ورد طازج اليوم، وش رأيك أوريك كم تنسيق يناسب طلبك؟"],
    "winback": ["هلا {الاسم} 🌷 اشتقنا لك والله! وصلنا ورد طازج هالأسبوع وجهزنا تنسيقات جديدة، تحب أرسل لك صورها؟",
                "هلا {الاسم}، عساك طيب 🌸 من زمان ما شفناك، إذا عندك مناسبة قريبة نجهز لك شي يفرّح، وش رأيك؟",
                "هلا {الاسم} 🌹 حبينا نسلم عليك ونقولك إننا موجودين لأي هدية أو مناسبة، تبي نرتب لك شي؟"],
    "occasion": ["هلا {الاسم} 🌷 {المناسبة} قربت! جهزنا تنسيقات خاصة لها، تحب أحجز لك واحد قبل الزحمة؟",
                 "هلا {الاسم}، {المناسبة} على الأبواب 🌸 لا تفوتك الهدية، نجهزها لك ونوصلها بوقتها. وش اللون اللي تحبه؟",
                 "هلا {الاسم} 🌹 بمناسبة {المناسبة} عندنا تنسيقات جديدة تنحب، تبي أرسل لك صورها؟"],
    "general": ["هلا {الاسم} 🌷 وصلنا ورد طازج اليوم وتنسيقاته تجنن، تحب أرسل لك صورها؟",
                "هلا {الاسم}، عساك بخير 🌸 إذا عندك مناسبة أو تبي تفرّح أحد، حنا جاهزين نجهز لك أحلى بوكيه. وش رأيك؟",
                "هلا {الاسم} 🌹 حبينا نذكرك إننا موجودين لأي هدية، ونوصلها لين الباب. تبي نرتب لك شي؟"],
}
def mkt_library(goal, base):
    g = goal or ""; key = "cold" if re.search(r"سأل|سعر|ما رد|متابع", g) else "winback" if re.search(r"قديم|رجع|ترجيع|اشتقنا", g) else "occasion" if re.search(r"مناسب|عيد|يوم|رمضان|تخرج|زواج|الأم|الحب", g) else "general"
    occ = re.search(r"(عيد [^\s،]+|يوم [^\s،]+|رمضان|التخرج|الزواج)", g + " " + base)
    return [x.replace("{المناسبة}", occ.group(1) if occ else "المناسبة") for x in MKT_LIB[key]]

def do_mkt_draft(body):
    """Saudi WhatsApp marketing draft (one short message with {الاسم}). AI if available; else the ready template + a clear reason. Never sends anything."""
    import time as _t
    from app.brain.llm import log as llog
    base = str(body.get("template", ""))[:500]; goal = str(body.get("goal", ""))[:200]
    lib = mkt_library(goal, base); fb = lambda why: {"text": random.choice([x for x in lib if x != base] or lib), "engine": "library", "reason": why, "alts": lib}
    if LLM is None: llog("mkt_draft: AI off (no model object)"); return fb("الذكاء المحلي مطفي في هذا التشغيل")
    ok, why = LLM.available()
    if body.get("ai") is not True: return fb("الذكاء المحلي مطفي من الإعدادات")
    if not ok: llog(f"mkt_draft: unavailable: {why}"); return fb(why)
    kb = make_kb(body); teach = body.get("teach") or {}; t0 = _t.time(); last = ""
    msgs = [{"role": "system", "content": "أنت تكتب رسائل واتساب قصيرة لمحل ورد سعودي باللهجة السعودية العامية. رسالة وحدة، سطرين أو ثلاثة، تبدأ بـ «هلا {الاسم}»، لطيفة ومو ملحّة، "
                                         "وتنتهي بسؤال بسيط يخلي العميل يرد. لا تذكر أسعار ولا أرقام. لا تستخدم الفصحى. اكتب الرسالة فقط."},
            {"role": "user", "content": "الهدف: ترجيع عميل قديم\nاسم المحل: ورد الربيع\nمسودة تقدر تحسنها:\nهلا {الاسم} اشتقنا لك"},
            {"role": "assistant", "content": "هلا {الاسم} 🌷 اشتقنا لك والله! وصلنا ورد طازج هالأسبوع وجهزنا تنسيقات جديدة، تحب أرسل لك صورها؟"},
            {"role": "user", "content": f"الهدف: {goal}\nاسم المحل: {kb['shop'].get('name','')}\nمسودة تقدر تحسنها:\n{base}"}]
    for temp in (0.4, 0.7):
        try: t = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", AI.clean(LLM.chat(msgs, max_tokens=120, temperature=temp, wait=60))).strip()
        except Exception as e: last = "الذكاء مشغول أو ما اشتغل" if "busy" in str(e) else "الذكاء ما اشتغل على هذا الجهاز"; llog(f"mkt_draft: error {type(e).__name__} {str(e)[:60]}"); break
        if "{الاسم}" not in t: t = re.sub(r"^(هلا|مرحبا|اهلا|أهلا)[^،,\n]*[،,]?", "هلا {الاسم}،", t, count=1) if re.match(r"^(هلا|مرحبا|اهلا|أهلا)", t) else "هلا {الاسم}، " + t
        bad = [x for x in ("فصحى" if AI.MSA.search(t) else "", "إنجليزي" if re.search(r"[A-Za-z]{4,}", t) else "", "أرقام" if re.search(r"\d{2,}", t) else "",
                           "كلمة ممنوعة" if AI.forbidden_hit(teach, t) else "", "طويل" if len(t) > 320 else "", "فاضي" if len(t) < 15 else "",
                           "مو سعودي" if not re.search(r"(اشتقنا|حياك|تبي|تحب|وش|ودنا|نجهز|جهزنا|عندنا|وصلنا|أبشر|ابشر|والله)", t) else "",
                           "كلام غريب" if re.search(r"(علما|نصيحة|دعوة|لعملية|يشوفك|اشتقتلك|بيتنا|علينا|أرسل لنا|ارسل لنا)", t) else "") if x]
        if not bad: llog(f"mkt_draft: ok in {int((_t.time() - t0) * 1000)}ms"); return {"text": t, "engine": "ai", "alts": lib}
        last = "الذكاء كتب نص ما يناسب (" + "، ".join(bad) + ")"; llog(f"mkt_draft: rejected {bad}")
    lib = mkt_library(goal, base); pick = random.choice([x for x in lib if x != base] or lib)
    return {"text": pick, "engine": "library", "reason": last or "ما ضبط", "alts": lib}

def do_chan_draft(body):
    """«اكتب منشور» for the owner's WhatsApp Channel: short Saudi post with one clear CTA. AI if on, else the ready template. Never sends."""
    base = str(body.get("template", ""))[:800]; idea = str(body.get("idea", ""))[:300]; kind = str(body.get("kind", "text"))
    if not llm_on(body): return {"text": base, "engine": "rules"}
    kb = make_kb(body); teach = body.get("teach") or {}
    try:
        t = LLM.chat([{"role": "system", "content": "أنت تكتب منشورات قناة واتساب لمحل ورد سعودي باللهجة السعودية العامية. المنشور ٢ إلى ٤ أسطر قصيرة، يبدأ بالفكرة مباشرة، "
                                                    "فيه إيموجي ورد واحد أو اثنين، وينتهي بطلب واحد واضح مثل «راسلنا على الخاص». لا تذكر أسعار. لا تستخدم الفصحى. اكتب المنشور فقط."
                                                    + (" هذا تعليق على صورة أو فيديو، خله قصير." if kind in ("image", "video") else "") + (" هذا سؤال تصويت، اكتب السؤال فقط بسطر واحد." if kind == "poll" else "")},
                      {"role": "user", "content": f"الفكرة: {idea}\nاسم المحل: {kb['shop'].get('name','')}\nمسودة تقدر تحسنها:\n{base}"}], max_tokens=160, temperature=0.6, wait=30)
        t = AI.clean(t).strip()
        if t and not AI.guard(Brain(kb=kb), t, teach) and not re.search(r"\d{3,}", t) and len(t) < 500: return {"text": t, "engine": "ai"}
    except Exception: pass
    return {"text": base, "engine": "rules"}

def do_ai_status(body):
    return LLM.status() if LLM else {"available": False, "reason": "غير مفعّل", "state": "unavailable"}

def do_ai_try(body):
    """«جرّب» box in تعليم الموظف: what would it reply right now (rules + AI), with timing. Sends nothing."""
    import time as _t
    t0 = _t.time(); r = do_think({**body, "ai": body.get("ai") is True})
    return {"reply": r["reply"], "engine": r.get("engine"), "handoff": r.get("handoff"), "kind": r.get("kind"), "ms": int((_t.time() - t0) * 1000),
            "rejected": r.get("ai_rejected"), "error": r.get("ai_error"), "intents": r.get("intents")}

def do_occasions(body):
    return {"list": upcoming_occasions(days=int(body.get("days") or 30), kb=make_kb(body))}

def do_kb(_):
    kb = default_kb()
    return {"products": [{k: p.get(k) for k in ("name", "aliases", "price", "unit", "category")} for p in kb["products"]], "shop": kb["shop"]}

ROUTES = {"/think": do_think, "/suggest": do_suggest, "/extract": do_extract, "/kb": do_kb, "/profile": do_profile, "/insight": do_insight, "/occasions": do_occasions, "/plan_text": do_plan_text, "/ai/status": do_ai_status, "/ai/try": do_ai_try, "/mkt_draft": do_mkt_draft, "/chan_draft": do_chan_draft, "/teach_defaults": lambda b: AI.DEFAULT_TEACH}

class BrainServer:
    def __init__(self, key, port=0, llm=True):
        global LLM
        if llm and LLM is None and os.environ.get("WAE_NO_LLM") != "1": LLM = LocalLLM()
        self.key = key
        outer = self
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_POST(self):
                if not hmac.compare_digest(self.headers.get("X-Brain-Key", ""), outer.key): return self._send(403, {"error": "forbidden"})
                fn = ROUTES.get(self.path)
                if not fn: return self._send(404, {"error": "not found"})
                try:
                    n = min(int(self.headers.get("Content-Length") or 0), 2_000_000)
                    body = json.loads(self.rfile.read(n) or b"{}")
                    self._send(200, fn(body if isinstance(body, dict) else {}))
                except Exception as e:
                    self._send(500, {"error": str(e)[:200]})
            def _send(self, code, obj):
                data = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
                self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
        self.port = self.httpd.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
    def start(self):
        threading.Thread(target=self.httpd.serve_forever, daemon=True, name="brain").start(); return self.url
    def stop(self):
        self.httpd.shutdown(); self.httpd.server_close()
        if LLM: LLM.stop()

if __name__ == "__main__":   # dev: python -m app.brain_server KEY PORT
    import sys
    s = BrainServer(sys.argv[1] if len(sys.argv) > 1 else "dev", int(sys.argv[2]) if len(sys.argv) > 2 else 8797)
    print(s.url, flush=True); s.httpd.serve_forever()
