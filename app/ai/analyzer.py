"""Offline heuristic analyzer (Arabic/Saudi + English keywords)."""
import re

def _norm(t):
    t = re.sub("[إأآا]", "ا", t)
    return t.replace("ة", "ه").replace("ى", "ي").lower()

KEYWORDS = {
    "Complaint": ["شكوى","اشتكي","سيء","سيئ","زعلان","متضايق","مو راضي","ما وصل","تاخر","تأخر","خربان","مغشوش","استرجاع","ارجاع","فلوسي","حرام عليكم","complaint","refund","worst"],
    "Support": ["مشكله","عطل","ما يشتغل","مايشتغل","خلل","مساعده","كيف اشغل","كيف استخدم","تعليق","support","not working","help"],
    "Hot Lead": ["ابي اطلب","ابغى اطلب","ابي اشتري","ابغى اشتري","ابي احجز","ابغى احجز","احجز لي","اطلب","كيف ادفع","رابط الدفع","تحويل","حولت","جاهز","متى توصل","ارسل الفاتوره","اكد الطلب","خلاص","buy","order","pay"],
    "Existing Customer": ["طلبي","طلبت قبل","اشتريت منكم","عميل عندكم","الطلب السابق","رقم الطلب","مره ثانيه"],
    "Follow-up": ["بفكر","افكر","بشوف","اشوف وارد","برجع لك","ارد عليك","بعدين","لاحقا","الاسبوع الجاي","later"],
    "Interested": ["كم السعر","بكم","سعر","الاسعار","وش عندكم","ايش عندكم","تفاصيل","متوفر","فيه","عندكم","عرض","خصم","price","available","details"],
}
HANDOFF = ["ابي اكلم","ابغى اكلم","موظف","مدير","انسان","شخص حقيقي","محامي","قانوني","بلغ","بشتكي","manager","human"]
PRIORITY = ["Complaint", "Support", "Hot Lead", "Existing Customer", "Follow-up", "Interested"]

def classify(customer_texts):
    text = _norm(" ".join(customer_texts))
    scores = {c: sum(text.count(_norm(k)) for k in kws) for c, kws in KEYWORDS.items()}
    best = [c for c in PRIORITY if scores[c] > 0]
    if not best:
        return "New Lead", scores
    # complaints/support dominate; otherwise highest score, ties by priority
    for c in ("Complaint", "Support"):
        if scores[c] > 0:
            return c, scores
    return max(best, key=lambda c: (scores[c], -PRIORITY.index(c))), scores

def detect_handoff(customer_texts, classification):
    text = _norm(" ".join(customer_texts))
    for k in HANDOFF:
        if _norm(k) in text:
            return True, f"العميل طلب تواصل بشري ({k})"
    if classification == "Complaint":
        return True, "شكوى تحتاج تدخل موظف"
    return False, ""

def match_business(customer_texts, business_info):
    text = _norm(" ".join(customer_texts))
    hits = []
    for b in business_info:
        words = [w for w in _norm(b["title"]).split() if len(w) > 2]
        if any(w in text for w in words):
            hits.append(b)
    return hits

def extract_need(customer_texts, matched):
    if matched:
        return "مهتم بـ: " + "، ".join(b["title"] for b in matched)
    qs = [t for t in customer_texts if "؟" in t or "?" in t]
    src = qs[-1] if qs else (customer_texts[-1] if customer_texts else "")
    return (src[:120] + "…") if len(src) > 120 else (src or "غير واضح بعد")

def summarize(msgs, customer, classification):
    from app.config import CLASS_AR
    c_msgs = [m for m in msgs if m.sender == customer]
    first = c_msgs[0].text[:80] if c_msgs else ""
    last = c_msgs[-1].text[:80] if c_msgs else ""
    s = f"محادثة مع {customer} ({len(msgs)} رسالة). التصنيف: {CLASS_AR[classification]}. بدأ بـ: «{first}»"
    if last and last != first:
        s += f"، وآخر رسالة: «{last}»"
    return s + "."
