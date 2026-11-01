"""Intent detection, entity extraction, lead scoring, objections, upsell, reply composer and price guard."""
import random, re
from difflib import SequenceMatcher
from datetime import date, datetime, timedelta
from app.brain.normalize import norm, fuzzy_in, any_in, sar, phone966
from app.brain.knowledge import load_kb

INTENTS = {  # ordered by priority. Saudi/Gulf dialect, common typos, short words, English + Arabizi. All matched after norm().
    "complaint": ["شكوي", "اشتكي", "ما وصل", "ماوصل", "للحين ما وصل", "تاخر", "تاخرتو", "متاخر", "ذبلان", "ذابل", "ذبل", "خربان", "مكسور", "مو نفس الصوره",
                  "غير الصوره", "سيء", "سيئ", "زعلان", "استرجاع", "فلوسي", "غلط", "فيه مشكله", "عندي مشكله", "ما عجبني", "مو حلو", "complaint", "late", "problem"],
    "human": ["ابي اكلم", "ابغي اكلم", "ابغى اكلم", "موظف", "المدير", "المسؤول", "صاحب المحل", "شخص حقيقي", "انسان", "اتصل علي", "اتصلو", "كلمني", "رقمكم", "رقم التواصل", "call me"],
    "stop": ["لا ترسل", "وقف الرسايل", "لا تراسلني", "لا ترسلون", "الغاء الاشتراك", "stop", "unsubscribe"],
    "status": ["وين طلبي", "طلبي وين", "متي يوصل طلبي", "وصل طلبي", "حاله الطلب", "حالة الطلب", "رقم الطلب", "طلبي جاهز", "جهز طلبي", "تتبع", "المندوب وين", "وين المندوب", "order status", "where is my order"],
    "order": ["ابي اطلب", "ابغي اطلب", "ابغى اطلب", "ابي احجز", "ودي اطلب", "اطلب", "احجز", "اعتمد", "اكد الطلب", "جهزوا", "جهز لي", "تمام اعتمد", "ابي", "ابغي", "ابغى", "ودي", "عطني", "ابيه", "ابيها", "order", "abi", "abgha"],
    "price": ["كم السعر", "بكم", "كم سعر", "كم سعره", "السعر", "سعره", "سعرها", "الاسعار", "اسعار", "اسعاركم", "كم يكلف", "تكلفه", "كم حقه", "كم حقها", "كم", "price", "prices", "how much", "kam", "bkam", "sa3r"],
    "custom": ["تنسيق خاص", "حسب الطلب", "اختار الالوان", "لون معين", "تصميم خاص", "مثل هذي", "زي الصوره", "مثل الصوره", "بنفس الشكل", "custom"],
    "photos": ["صور", "صوره", "ارسل صور", "ابي اشوف", "وريني", "فرجني", "نماذج", "شغلكم", "اعمالكم", "photos", "pics", "pictures"],
    "location": ["موقعكم", "وين موقعكم", "وين المحل", "وينكم", "مكانكم", "لوكيشن", "اللوكيشن", "الموقع", "العنوان", "location", "address", "wenkom"],
    "hours": ["متي تفتحون", "متي تسكرون", "تفتحون", "تسكرون", "الدوام", "دوامكم", "اوقات", "ساعات العمل", "مفتوحين", "فاتحين", "مسكرين", "open", "hours"],
    "payment": ["الدفع", "ادفع", "طريقه الدفع", "تحويل", "مدي", "ابل باي", "apple pay", "stc pay", "تمارا", "تابي", "كاش", "فيزا", "دفع عند الاستلام", "payment", "pay"],
    "delivery": ["توصيل", "توصلون", "توصل", "التوصيل", "متي يوصل", "يوصل اليوم", "نفس اليوم", "رسوم", "مندوب", "شحن", "تغليف", "مفاجاه", "بدون اسم", "حجز مسبق",
                 "الغاء الطلب", "استبدال", "delivery", "deliver", "tawseel"],
    "meaning": ["وش معني", "معني", "يرمز", "وش يعني", "رمز"],
    "care": ["كيف احافظ", "يعيش اطول", "اسقي", "ذبل بسرعه", "عنايه", "كم يعيش", "كم يقعد", "متي يذبل"],
    "occasion": ["زواج", "عرس", "زفاف", "ملكه", "خطوبه", "تخرج", "مولود", "مولوده", "ولاده", "مواليد", "عيد", "عيديه", "تهنئه", "مبروك", "مريض", "مستشفي", "سلامتك",
                 "عزاء", "ميلاد", "عيد ميلاد", "يوم الام", "ترقيه", "نجاح", "اعتذار", "حب", "حبيبتي", "زوجتي", "امي", "wedding", "birthday", "graduation"],
    "product": ["ورد", "ورده", "ورود", "بوكيه", "بوكيهات", "باقه", "باقات", "تنسيق", "تنسيقات", "هديه", "هدايا", "جوري", "توليب", "اوركيد", "روز", "زهور", "زهره",
                "بوكس", "صندوق", "شوكولاته", "بالون", "flowers", "flower", "rose", "roses", "bouquet", "gift", "ward"],
    "catalog": ["وش عندكم", "ايش عندكم", "وش تبيعون", "المنيو", "الكتالوج", "المتوفر", "وش المتوفر", "منتجاتكم", "catalog", "menu"],
    "thanks": ["شكرا", "شكراً", "مشكور", "مشكورين", "يعطيك العافيه", "تسلم", "تسلمون", "الله يسعدك", "جزاك الله", "ما قصرت", "ماقصرتو", "thanks", "thank you", "thx", "tnx"],
    "greeting": ["السلام عليكم", "السلام", "سلام", "هلا", "هلا والله", "مرحبا", "مرحبتين", "مساء الخير", "صباح الخير", "هاي", "اهلين", "اهلا", "حياكم", "يا هلا",
                 "hi", "hello", "hey", "salam", "slm", "marhaba", "hala"],
}
OBJECTIONS = {"price": ["غالي", "غاليه", "مره غالي", "ارخص", "خصم", "تخفيض", "اقل"],
              "wait": ["بفكر", "افكر", "بشوف", "برجع لك", "بعدين", "مو الحين"],
              "trust": ["مضمون", "كيف اضمن", "تجربه سيئه", "مثل الصوره"]}
SAFE_AUTO = {"greeting", "thanks", "delivery", "meaning", "care", "catalog", "product", "photos", "location", "hours", "payment", "occasion", "clarify"}   # allowed to auto-send after-hours

NUM_WORDS = {"واحد": 1, "وحده": 1, "اثنين": 2, "ثنتين": 2, "ثلاث": 3, "ثلاثه": 3, "اربع": 4, "اربعه": 4, "خمس": 5, "خمسه": 5,
             "ست": 6, "سته": 6, "سبع": 7, "ثمان": 8, "عشر": 10, "عشره": 10, "درزن": 12, "دزينه": 12}
WEEKDAYS = {"الاحد": 6, "الاثنين": 0, "الثلاثاء": 1, "الثلاثا": 1, "الاربعاء": 2, "الاربعا": 2, "الخميس": 3, "الجمعه": 4, "السبت": 5}

def _tok(w):
    w = re.sub(r"[^\w]", "", w)
    for p in ("وال", "بال", "فال", "لل", "ال"):
        if w.startswith(p) and len(w) - len(p) >= 2: return w[len(p):]
    if len(w) > 4 and w[0] in "وب": return w[1:]
    return w

def _hit(k, n, toks):
    """phrase → fuzzy phrase match; single word → whole-token match (with ال/و/ب stripped, tolerant to 1 typo on long words)."""
    if " " in k: return fuzzy_in(k, n, 0.88)
    kt = _tok(k)
    for t in toks:
        if t == kt or t == k: return True
        if len(kt) >= 6 and abs(len(t) - len(kt)) <= 1 and SequenceMatcher(None, t, kt).ratio() >= 0.85: return True
    return False

class Brain:
    def __init__(self, kb=None, repo=None, rng=None):
        self.kb = kb or load_kb(repo)
        self.rng = rng or random.Random()

    # ---------- understanding ----------
    def intents(self, text):
        n = norm(text); toks = [_tok(w) for w in n.split()]; found = []
        for it, kws in INTENTS.items():
            if any(_hit(norm(k), n, toks) for k in kws): found.append(it)
        if "order" in found and "price" in found and not re.search(r"(اطلب|احجز|اكد|اعتمد|جهز)", n):
            found.remove("order")      # "ابي اعرف بكم" is a price question
        if "order" in found and not re.search(r"(اطلب|احجز|اكد|اعتمد|جهز|order)", n) and ({"product", "occasion"} & set(found)):
            found.remove("order")      # «ابي ورد» = interested, not a confirmed order yet
        if "status" in found and "order" in found: found.remove("order")
        if "price" in found and "delivery" in found and not self.find_products(text): found.remove("price")   # «التوصيل بكم»
        return found or ["unknown"]

    def objections(self, text):
        return [k for k, kws in OBJECTIONS.items() if any_in(kws, text, 0.9)]

    def find_products(self, text):
        hits = []
        for p in self.kb["products"]:
            if p["category"] == "خدمات": continue
            if any_in([p["name"], *p.get("aliases", [])], text, 0.86):
                hits.append(p)
        return hits

    def find_occasion(self, text):
        for name, o in self.kb["occasions"].items():
            if any_in([name, *o.get("aliases", [])], text, 0.88): return name
        return None

    def extract(self, text, today=None):
        today = today or date.today(); n = norm(text); e = {}
        prods = self.find_products(text)
        if prods: e["items"] = [p["name"] for p in prods]
        q = re.search(r"(\d{1,3})\s*(بوكيه|بوكس|صندوق|حبه|حبات|قطع|قطعه|باقه|باقات|وحده)", n)
        if q: e["quantity"] = int(q.group(1))
        else:
            for w, v in NUM_WORDS.items():
                if re.search(r"(^|\s)" + w + r"\s+(بوكيه|بوكس|صناديق|باقات|حبات|قطع)", n): e["quantity"] = v; break
        a = re.search(r"(\d{2,5}(?:\.\d+)?)\s*(ريال|ر\.?س|sar|rs)", n) or re.search(r"(ميزانيتي|حدود|بحدود)\s*(\d{2,5})", n)
        if a: e["amount"] = float(a.group(1) if a.group(1)[0].isdigit() else a.group(2))
        # date
        if "بكره" in n or "بكرا" in n: e["date"] = (today + timedelta(days=1)).isoformat()
        elif "بعد بكره" in n: e["date"] = (today + timedelta(days=2)).isoformat()
        elif re.search(r"(^|\s)(اليوم|الحين)($|\s)", n): e["date"] = today.isoformat()
        else:
            for w, wd in WEEKDAYS.items():
                if re.search(r"(^|\s)(يوم\s+)?" + w + r"($|\s)", n):
                    e["date"] = (today + timedelta(days=(wd - today.weekday()) % 7 or 7)).isoformat(); break
            m = re.search(r"(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?", n)
            if m and "date" not in e:
                d, mo = int(m.group(1)), int(m.group(2)); y = int(m.group(3) or today.year); y += 2000 if y < 100 else 0
                try: e["date"] = date(y, mo, d).isoformat()
                except ValueError: pass
        t = re.search(r"(الساعه|ساعه)\s*(\d{1,2})(?::(\d{2}))?\s*(الصبح|صباحا|الظهر|العصر|المغرب|العشاء|الليل|مساء|م|ص)?", n)
        if t:
            h = int(t.group(2)); per = t.group(4) or ""
            if per in ("العصر", "المغرب", "العشاء", "الليل", "مساء", "م") and h < 12: h += 12
            e["time"] = f"{h:02d}:{t.group(3) or '00'}"
        else:
            for w, h in (("الصبح", "10:00"), ("الظهر", "13:00"), ("العصر", "16:00"), ("المغرب", "18:00"), ("العشاء", "20:00"), ("الليل", "21:00")):
                if re.search(r"(^|\s)" + w + r"($|\s)", n): e["time"] = h; break
        for city, districts in self.kb["cities"].items():
            if fuzzy_in(city, n, 0.9): e["city"] = city
            for dist in districts:
                if re.search(r"(حي\s+)?(ال)?" + re.escape(norm(dist).removeprefix("ال")) + r"($|\s)", n) and len(dist) > 2 and ("حي" in n or fuzzy_in(dist, n, 0.95)):
                    e["district"] = dist; e.setdefault("city_guess", city)
        if "district" in e and "city" not in e: e["city"] = e.pop("city_guess")
        e.pop("city_guess", None)
        loc = re.search(r"(maps\.app\.goo\.gl\S+|goo\.gl/maps\S+|google\.com/maps\S+)", text)
        if loc: e["location_link"] = loc.group(1)
        ph = re.search(r"(\+?966|0)?5\d[\d\s]{7,9}", text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
        if ph and phone966(ph.group(0)): e["phone"] = phone966(ph.group(0))
        occ = self.find_occasion(text)
        if occ: e["occasion"] = occ
        nm = re.search(r"(اكتب|البطاقه|الكرت)\s*[:：]?\s*(.{3,60})", text)
        if nm and "اكتب" in norm(nm.group(1)): e["card_text"] = nm.group(2).strip()
        return e

    def price_of(self, item):
        for p in self.kb["products"]:
            if p["name"] == item: return p.get("price")
        return None

    def total(self, e):
        items = e.get("items") or []
        prices = [self.price_of(i) for i in items]
        if not items or any(p in (None, "", 0) for p in prices): return None
        qty = e.get("quantity", 1) if len(items) == 1 else 1
        return sum(float(p) for p in prices) * qty

    def lead_score(self, intents, e, objections=()):
        s = 10
        s += 25 if "order" in intents else 0
        s += 10 if "price" in intents else 0
        s += 10 * bool(e.get("items")) + 10 * bool(e.get("date")) + 10 * bool(e.get("district") or e.get("location_link"))
        s += 8 * bool(e.get("occasion")) + 5 * bool(e.get("time")) + 7 * bool(e.get("amount"))
        s -= 10 * ("wait" in objections) + 5 * ("price" in objections)
        s -= 30 * bool({"complaint", "stop"} & set(intents))
        s = max(0, min(100, s))
        return s, ("ساخن 🔥" if s >= 60 else "دافي" if s >= 35 else "بارد")

    def upsell(self, e):
        cats = {p["category"] for p in self.kb["products"] if p["name"] in (e.get("items") or [])}
        out = []
        for c in cats:
            for name in self.kb["upsell"].get(c, []):
                if name not in (e.get("items") or []) and name not in out: out.append(name)
        if e.get("occasion"):
            for name in self.kb["occasions"][e["occasion"]].get("suggest", []):
                if name not in (e.get("items") or []) and name not in out: out.append(name)
        return out[:3]

    def missing_for_order(self, e):
        miss = []
        if not e.get("items"): miss.append("نوع الورد")
        if not e.get("date"): miss.append("يوم التوصيل")
        if not (e.get("district") or e.get("location_link")): miss.append("الحي أو اللوكيشن")
        return miss

    # ---------- composing ----------
    def _t(self, key, **kw):
        tpl = self.rng.choice(self.kb["templates"].get(key) or [""])
        shop = self.kb["shop"]
        kw.setdefault("hours", shop.get("hours", "")); kw.setdefault("location", shop.get("location", ""))
        kw.setdefault("name", "")
        out = tpl
        for k, v in kw.items(): out = out.replace("{" + k + "}", str(v))
        return re.sub(r"\s+([،.!؟])", r"\1", re.sub(r" {2,}", " ", out)).strip()

    def _price_line(self, p):
        if p.get("price_text"): return p["price_text"]
        return sar(p["price"]) + ("" if p["unit"] == "بوكيه" else f" لل{p['unit']}" if not p["unit"].startswith("حسب") else "")

    def compose(self, text, customer="", e=None, intents=None, objections=None, after_hours=False):
        e = e if e is not None else self.extract(text); intents = intents or self.intents(text)
        objections = objections if objections is not None else self.objections(text)
        name = (customer or "").split()[0] if customer and not re.search(r"\d", customer) else ""
        if "stop" in intents: return "أبشر، ما راح نرسل لك شي بعد 🙏", "stop"
        if "complaint" in intents or "human" in intents: return self._t("complaint"), "handoff"
        if after_hours and (not (set(intents) & SAFE_AUTO) or {"order", "price"} & set(intents)): return self._t("after_hours", name=name), "after_hours"
        if "price" in objections:
            cheap = sorted([p for p in self.kb["products"] if p.get("price") and p["category"] in ("بوكيه",)], key=lambda p: p["price"])
            if cheap: return self._t("objection_price", cheaper=cheap[0]["name"], price=sar(cheap[0]["price"])), "objection"
        if "wait" in objections: return self._t("objection_wait"), "objection"
        if "trust" in objections: return self._t("objection_trust"), "objection"
        prods = [p for p in self.kb["products"] if p["name"] in (e.get("items") or [])]
        if "order" in intents and (prods or e.get("occasion")):
            miss = self.missing_for_order(e)
            if miss and not prods and e.get("occasion"): pass
            elif miss: return self._t("ask_missing", missing=" و".join(miss)), "order_collect"
            else:
                tot = self.total(e)
                items = "، ".join(((f"{e['quantity']} × " if e.get("quantity") and len(prods) == 1 else "") + p["name"]) for p in prods)
                when = f"، التوصيل {e['date']}" + (f" الساعة {e['time']}" if e.get("time") else "")
                where = f"، {('حي ' + e['district']) if e.get('district') else 'اللوكيشن المرسل'}" + (f" - {e['city']}" if e.get("city") else "")
                total = f"، المجموع {sar(tot)} (بدون التوصيل)" if tot else ""
                return self._t("order_confirm", items=items, total=total, when=when, where=where), "order_confirm"
        if "price" in intents or ("order" in intents and prods):
            if prods:
                known = [p for p in prods if p.get("price")]
                if known:
                    p = known[0]; reply = self._t("price", item=p["name"], price=self._price_line(p))
                    ups = self.upsell(e)
                    if ups: reply += f" وتقدر تضيف {ups[0]}."
                    return reply, "price"
                return self._t("price_unknown", item=prods[0]["name"]), "price_unknown"
            return self._t("catalog"), "catalog"
        if e.get("occasion"):
            o = self.kb["occasions"][e["occasion"]]
            sug = [s for s in o.get("suggest", []) if self.price_of(s)]
            sug_txt = " أو ".join(f"{s} ({sar(self.price_of(s))})" for s in sug[:2]) or "تنسيق خاص"
            return self._t("occasion", occasion=e["occasion"], suggest=sug_txt, colors=o.get("colors", "")), "occasion"
        if "meaning" in intents:
            for f, m in self.kb["meanings"].items():
                if fuzzy_in(f.split()[0], text): return self._t("meaning", flower=f, meaning=m), "meaning"
        if "care" in intents: return self._t("care", tip=self.rng.choice(self.kb["care"])), "care"
        if "delivery" in intents:
            for f in self.kb["faq"]:
                if any_in(f["q"], text, 0.9):
                    return self._t("delivery", answer=f["a"].replace("{location}", self.kb["shop"].get("location", "")).replace("{hours}", self.kb["shop"].get("hours", ""))), "delivery"
        shop = self.kb["shop"]
        if "status" in intents: return self._t("status"), "status"
        if "location" in intents: return self._t("location", location=shop.get("location", "")), "location"
        if "hours" in intents: return self._t("hours", hours=shop.get("hours", "")), "hours"
        if "payment" in intents:
            f = next((f for f in self.kb["faq"] if "الدفع" in f["q"]), None)
            return (f["a"] if f else self._t("payment")), "payment"
        if "delivery" in intents: return self._t("delivery_general"), "delivery"
        if "custom" in intents: return self._t("custom"), "custom"
        if "photos" in intents: return self._t("photos"), "photos"
        if "product" in intents or "catalog" in intents:
            cheap = sorted([p for p in self.kb["products"] if p.get("price") and p["category"] != "خدمات"], key=lambda p: p["price"])
            frm = f" وتبدأ الأسعار من {sar(cheap[0]['price'])}" if cheap else ""
            return self._t("catalog", from_price=frm), "catalog"
        if "occasion" in intents: return self._t("occasion_general"), "occasion"
        if "thanks" in intents: return self._t("thanks"), "thanks"
        if "greeting" in intents: return self._t("greeting", name=name), "greeting"
        return self._t("clarify", name=name), "clarify"

    # ---------- guard ----------
    def allowed_prices(self):
        out = set()
        for p in self.kb["products"]:
            if p.get("price"):
                v = float(p["price"]); out.add(v)
        return out

    def guard(self, reply, e=None):
        """Return list of issues: any SAR amount not in the price table (or a computed total) is rejected."""
        allowed = self.allowed_prices()
        if e:
            t = self.total(e)
            if t: allowed.add(float(t))
        issues = []
        txt = norm(reply).replace(",", "")
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(ر\.?س|ريال|sar)", txt):
            if float(m.group(1)) not in allowed: issues.append(f"سعر غير معتمد: {m.group(1)}")
        return issues

def think(text, customer="", repo=None, kb=None, after_hours=False, rng=None, today=None):
    b = Brain(kb=kb, repo=repo, rng=rng)
    intents, e, obj = b.intents(text), b.extract(text, today), b.objections(text)
    reply, kind = b.compose(text, customer, e, intents, obj, after_hours)
    issues = b.guard(reply, e)
    if issues: reply, kind = b._t("price_unknown", item=(e.get("items") or ["الطلب"])[0]), "guarded"
    score, temp = b.lead_score(intents, e, obj)
    return {"intents": intents, "entities": e, "objections": obj, "reply": reply, "kind": kind, "lead_score": score,
            "temperature": temp, "upsell": b.upsell(e), "missing": b.missing_for_order(e) if "order" in intents else [],
            "total": b.total(e), "safe_auto": kind in SAFE_AUTO, "guard_issues": issues}
