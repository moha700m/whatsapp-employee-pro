import random, pytest
from app.ai import analyzer
from app.ai.replies import build_reply, PRICE_RE

@pytest.mark.parametrize("texts,exp", [
    (["السلام عليكم"], "New Lead"), (["كم السعر؟"], "Interested"), (["ابي اطلب الحين كيف ادفع"], "Hot Lead"),
    (["الطلب ما وصل وتأخر، سيء جداً"], "Complaint"), (["الجهاز ما يشتغل فيه عطل"], "Support"),
    (["بفكر وبرجع لك"], "Follow-up"), (["طلبت قبل منكم، رقم الطلب 55"], "Existing Customer")])
def test_classify(texts, exp):
    assert analyzer.classify(texts)[0] == exp

def test_handoff():
    assert analyzer.detect_handoff(["ابي اكلم المدير"], "Interested")[0]
    assert analyzer.detect_handoff(["سيء"], "Complaint")[0]
    assert not analyzer.detect_handoff(["هلا"], "New Lead")[0]

def test_no_invented_price():
    r = build_reply("أحمد", "Interested", [], True, rng=random.Random(1))
    assert not PRICE_RE.search(r) and "بتأكد" in r

def test_uses_approved_price():
    b = [{"title": "باقة الذهب", "content": "x", "price": "300 ريال"}]
    m = analyzer.match_business(["كم سعر باقة الذهب"], b)
    assert m and "300 ريال" in build_reply("أحمد", "Interested", m, True)

def test_no_repeat():
    first = build_reply("أ", "New Lead", [], False, rng=random.Random(0))
    assert build_reply("أ", "New Lead", [], False, recent=[first], rng=random.Random(0)) != first
