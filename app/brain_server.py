"""Local brain HTTP service for the WhatsApp engine (127.0.0.1 only, shared-key protected).
Free and offline: rules + Saudi knowledge base. No model downloads, no network calls."""
import json, random, threading, hmac
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import date
from app.brain.engine import Brain, think, SAFE_AUTO
from app.brain.knowledge import default_kb

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
    for k in ("name", "location", "hours", "city"):
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
    kb = make_kb(body)
    r = think(str(body.get("text", ""))[:2000], str(body.get("customer", ""))[:60], kb=kb, after_hours=bool(body.get("after_hours")))
    r["reply"] = humanize(r["reply"])
    r["handoff"] = r["kind"] in HANDOFF_KINDS or bool({"order", "price", "complaint", "human", "stop"} & set(r["intents"]))
    return r

def do_suggest(body):
    kb = make_kb(body); texts = incoming(body.get("messages"), 3)
    if not texts: return {"replies": []}
    text = " ".join(texts); out = []
    for seed in range(12):
        r = think(text, str(body.get("customer", "")), kb=kb, rng=random.Random(seed))
        rep = humanize(r["reply"])
        if rep not in out: out.append(rep)
        if len(out) >= 3: break
    r = think(text, str(body.get("customer", "")), kb=kb, rng=random.Random(0))
    if r["upsell"] and len(out) < 4: out.append(f"وتقدر تضيف {r['upsell'][0]} يكمّل الهدية 🌷")
    return {"replies": out[:4], "intents": r["intents"], "missing": r["missing"], "score": r["lead_score"]}

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
    return {"orders": orders, "stage": stage, "score": score, "temperature": temp, "reason": "، ".join(reasons) or "استفسار عام",
            "summary": summ, "missing": b.missing_for_order(ents) if "order" in intents else [], "entities": ents}

def do_kb(_):
    kb = default_kb()
    return {"products": [{k: p.get(k) for k in ("name", "aliases", "price", "unit", "category")} for p in kb["products"]], "shop": kb["shop"]}

ROUTES = {"/think": do_think, "/suggest": do_suggest, "/extract": do_extract, "/kb": do_kb}

class BrainServer:
    def __init__(self, key, port=0):
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

if __name__ == "__main__":   # dev: python -m app.brain_server KEY PORT
    import sys
    s = BrainServer(sys.argv[1] if len(sys.argv) > 1 else "dev", int(sys.argv[2]) if len(sys.argv) > 2 else 8797)
    print(s.url, flush=True); s.httpd.serve_forever()
