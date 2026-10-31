"""Built-in Saudi flower-shop brain: normalisation, intents, entities, scoring, composer, price guard."""
import random
from datetime import date
from app.brain import think, Brain
from app.brain.normalize import norm, fuzzy_in, phone966, sar
from app.brain.knowledge import default_kb, upcoming_occasions

T = date(2026, 10, 31)
R = lambda: random.Random(1)

def test_normalize_arabic():
    assert norm("إِبْتِسَامَة") == "ابتسامه" and norm("هلاااا") == "هلا" and norm("٠٥٥") == "055"
    assert fuzzy_in("الفيصلية", "حي الفيصليه") and fuzzy_in("بوكيه توليب", "بوكية التوليب")
    assert not fuzzy_in("باقة التصميم", "بطاقة")

def test_phone_and_currency():
    assert phone966("0551234567") == "+966551234567" == phone966("00966 55 123 4567") == phone966("+966551234567")
    assert phone966("0131234567") == "" and sar(150) == "150 ر.س" and sar(1500) == "1,500 ر.س"

def test_greeting_and_price():
    assert think("السلام عليكم", "سارة", rng=R(), today=T)["kind"] == "greeting"
    r = think("بكم بوكيه الجوري؟", rng=R(), today=T)
    assert r["intents"] == ["price"] and "150 ر.س" in r["reply"] and not r["guard_issues"]

def test_full_order_extraction():
    r = think("ابي اطلب ٢ بوكيه توليب بكره الساعه ٥ العصر حي الفيصلية الدمام 0551234567", rng=R(), today=T)
    e = r["entities"]
    assert e["items"] == ["بوكيه توليب"] and e["quantity"] == 2 and e["date"] == "2026-11-01" and e["time"] == "17:00"
    assert e["city"] == "الدمام" and e["district"] == "الفيصليه" and e["phone"] == "+966551234567"
    assert r["kind"] == "order_confirm" and r["total"] == 440 and "440 ر.س" in r["reply"] and r["lead_score"] >= 60

def test_order_missing_fields_asked():
    r = think("ابي اطلب بوكيه مشكل", rng=R(), today=T)
    assert r["kind"] == "order_collect" and "يوم التوصيل" in r["reply"] and "الحي" in r["reply"]

def test_weekday_and_khobar():
    e = think("ابي بوكس ورد يوم الخميس حي العقربية الخبر", rng=R(), today=T)["entities"]
    assert e["date"] == "2026-11-05" and e["city"] == "الخبر" and e["district"] == "العقربيه"

def test_occasions_and_upsell():
    r = think("عندي تخرج اختي وش تنصحوني", rng=R(), today=T)
    assert r["entities"]["occasion"] == "تخرج" and r["kind"] == "occasion" and "ر.س" in r["reply"]
    assert think("ابي ورد لليوم الوطني", rng=R(), today=T)["entities"]["occasion"] == "اليوم الوطني"
    assert think("هديه ليوم التاسيس", rng=R(), today=T)["entities"]["occasion"] == "يوم التأسيس"
    assert "بطاقة إهداء" in think("بكم بوكيه جوري", rng=R(), today=T)["upsell"]

def test_objections_complaint_stop():
    assert think("غالي شوي", rng=R(), today=T)["kind"] == "objection"
    assert think("بفكر وارد عليك", rng=R(), today=T)["kind"] == "objection"
    assert think("الورد وصل ذبلان", rng=R(), today=T)["kind"] == "handoff"
    assert think("لا ترسل لي", rng=R(), today=T)["kind"] == "stop"

def test_unknown_price_never_invented():
    r = think("بكم كوشة الزواج؟", rng=R(), today=T)
    assert r["kind"] == "price_unknown" and "ر.س" not in r["reply"]

def test_guard_rejects_invented_price():
    b = Brain(rng=R())
    assert b.guard("السعر 999 ر.س") and not b.guard("السعر 150 ر.س")
    kb = default_kb(); kb["templates"]["greeting"] = ["هلا، عرض خاص 77 ريال"]
    r = think("هلا", kb=kb, rng=R(), today=T)
    assert r["kind"] == "guarded" and "77" not in r["reply"]

def test_faq_meaning_care():
    assert think("توصلون الخبر؟", rng=R(), today=T)["kind"] == "delivery"
    assert "الفخامة" in think("وش معنى الاوركيد", rng=R(), today=T)["reply"]
    assert think("كيف احافظ على الورد يعيش اطول", rng=R(), today=T)["kind"] == "care"

def test_after_hours_safe_only():
    assert think("السلام عليكم", after_hours=True, rng=R(), today=T)["safe_auto"]
    r = think("ابي اطلب بوكيه جوري بكره", after_hours=True, rng=R(), today=T)
    assert not r["safe_auto"] and r["kind"] == "after_hours"

def test_saudi_calendar():
    up = upcoming_occasions(date(2026, 2, 10), 30)
    assert [(o["occasion"], o["date"]) for o in up[:2]] == [("رمضان", "2026-02-18"), ("يوم التأسيس", "2026-02-22")]   # Hijri dates included (v2.3)
    assert any(o["occasion"] == "عيد الفطر" and o["date"] == "2027-03-09" for o in upcoming_occasions(date(2027, 2, 20), 30))
    assert any(o["date"] == "2026-09-23" for o in upcoming_occasions(date(2026, 9, 1), 30))
    assert default_kb()["shop"]["weekend"] == ["Fri", "Sat"]
