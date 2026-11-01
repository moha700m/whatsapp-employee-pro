"""v2.4.2: big Saudi rule base — every common phrasing gets a sensible reply, nothing silent, no flower emoji."""
import pytest
from app.brain.engine import think, Brain

S = [  # (message, acceptable kinds)
 ("ورده", {"catalog"}), ("ورد", {"catalog"}), ("وردة", {"catalog"}), ("الورد", {"catalog"}), ("وررررده", {"catalog"}), ("وَرْدَة 🌹", {"catalog"}),
 ("بوكيه", {"catalog"}), ("باقة", {"catalog"}), ("باقه ورد", {"catalog"}), ("تنسيق", {"catalog"}), ("ابي ورد", {"catalog"}), ("ابغى بوكيه", {"catalog"}),
 ("هدية لزوجتي", {"catalog", "occasion"}), ("flowers", {"catalog"}), ("bouquet", {"catalog"}),
 ("السلام", {"greeting"}), ("السلام عليكم", {"greeting"}), ("سلام", {"greeting"}), ("هلا", {"greeting"}), ("هلااا", {"greeting"}), ("مرحبا", {"greeting"}),
 ("صباح الخير", {"greeting"}), ("hi", {"greeting"}), ("hello", {"greeting"}), ("salam", {"greeting"}), ("اهلين", {"greeting"}),
 ("كم السعر", {"catalog", "price"}), ("بكم", {"catalog", "price"}), ("الاسعار", {"catalog", "price"}), ("how much", {"catalog", "price"}), ("كم سعر الجوري", {"price"}),
 ("توصلون؟", {"delivery"}), ("فيه توصيل", {"delivery"}), ("التوصيل بكم", {"delivery"}), ("delivery", {"delivery"}),
 ("وين موقعكم", {"location", "delivery"}), ("وينكم", {"location"}), ("location", {"location"}),
 ("متى تفتحون", {"hours", "delivery"}), ("الدوام", {"hours", "delivery"}), ("فاتحين الحين؟", {"hours"}),
 ("طريقة الدفع", {"payment", "delivery"}), ("تقبلون مدى؟", {"payment", "delivery"}), ("ابل باي", {"payment", "delivery"}),
 ("وين طلبي", {"status"}), ("متى يوصل طلبي", {"status"}),
 ("ابي تنسيق خاص", {"custom", "catalog"}), ("ارسل صور", {"photos", "delivery"}), ("وريني شغلكم", {"photos"}),
 ("زواج اختي", {"occasion"}), ("تخرج", {"occasion"}), ("مولود جديد", {"occasion"}), ("عيد ميلاد", {"occasion"}), ("مريض بالمستشفى", {"occasion"}),
 ("شكرا", {"thanks"}), ("مشكورين", {"thanks"}), ("thx", {"thanks"}), ("يعطيك العافية", {"thanks"}),
 ("الورد وصل ذابل", {"handoff"}), ("ابي اكلم المسؤول", {"handoff"}),
 ("ققق", {"clarify"}), ("؟", {"clarify"}), ("ك", {"clarify"}), ("asdf", {"clarify"}),
]

@pytest.mark.parametrize("text,kinds", S)
def test_every_message_gets_a_sensible_reply(text, kinds):
    r = think(text)
    assert r["reply"].strip(), text
    assert r["kind"] in kinds, (text, r["kind"], r["intents"], r["reply"])
    assert "🌷" not in r["reply"] and "🌸" not in r["reply"]

def test_at_least_fifty_samples(): assert len(S) >= 50

def test_clarify_varies():
    b = Brain(); outs = {b._t("clarify", name="") for _ in range(40)}
    assert len(outs) >= 2

def test_no_flower_emoji_in_any_template():
    from app.brain.knowledge import TEMPLATES, DELIVERY_FAQ
    for k, v in TEMPLATES.items():
        for t in v: assert "🌷" not in t and "🌸" not in t, k
    for f in DELIVERY_FAQ: assert "🌷" not in f["a"]
