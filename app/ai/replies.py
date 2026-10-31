"""Short Saudi-dialect reply builder. Uses ONLY approved business info; never invents prices."""
import random, re

PRICE_RE = re.compile(r"\d+\s*(?:ريال|ر\.س|sar|رس|\$)|(?:ريال|sar)\s*\d+", re.I)

def _price_line(b):
    return f"{b['title']} سعره {b['price']}" if b.get("price") else f"{b['title']}: {b['content'][:80]}"

TEMPLATES = {
    "Complaint": ["حقك علينا يا {n}، ونعتذر عن اللي صار. بحوّل موضوعك الحين لزميل مختص يتابعه معك شخصياً.",
                  "آسفين جداً يا {n} على الإزعاج، موضوعك مهم لنا وبيتواصل معك أحد من الفريق بأسرع وقت."],
    "Support": ["أبشر يا {n}، عطني تفاصيل أكثر عن المشكلة (وإذا فيه صورة يكون أفضل) ونساعدك على طول.",
                "ولا يهمك يا {n}، وش اللي يظهر لك بالضبط؟ عشان نحلها معك خطوة خطوة."],
    "Hot Lead": ["ممتاز يا {n}! {info} أأكد لك الطلب؟ وأرسل لك الخطوة الجاية.",
                 "أبشر يا {n}، {info} تبيني أجهز لك الطلب الحين؟"],
    "Existing Customer": ["هلا وغلا يا {n}، نورتنا مرة ثانية! {info} وش أقدر أخدمك فيه اليوم؟"],
    "Follow-up": ["على راحتك يا {n}، وإذا عندك أي سؤال أنا موجود. {info}",
                  "خذ وقتك يا {n}، وأتواصل معك لاحقاً إذا حاب."],
    "Interested": ["هلا {n}، {info} تحب أرسل لك تفاصيل أكثر؟",
                   "أهلين {n}، {info} وش يناسبك أكثر؟"],
    "New Lead": ["هلا والله يا {n}، حياك! وش أقدر أخدمك فيه؟",
                 "أهلاً {n}، نورتنا! كيف أقدر أساعدك؟"],
}

def build_reply(name, classification, matched, asked_price, recent=(), rng=None):
    rng = rng or random.Random()
    if matched:
        info = "، ".join(_price_line(b) for b in matched[:2]) + "."
    elif asked_price:
        info = "بتأكد لك من السعر من الفريق وأرد عليك."
    else:
        info = ""
    options = TEMPLATES.get(classification, TEMPLATES["New Lead"])[:]
    rng.shuffle(options)
    recent = set(recent)
    for t in options:
        r = re.sub(r"\s+", " ", t.format(n=name, info=info)).strip()
        if r not in recent:
            return r
    return re.sub(r"\s+", " ", options[0].format(n=name, info=info)).strip() + " 🌷"
