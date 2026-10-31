from app.brain_server import do_think, do_suggest, do_extract, make_kb, BrainServer
import json, urllib.request, urllib.error, pytest

def test_think_handoff_for_order_price_complaint():
    assert do_think({"text": "ابي اطلب بوكيه جوري بكره"})["handoff"]
    assert do_think({"text": "كم سعر التوليب؟"})["handoff"]
    assert do_think({"text": "الورد وصل ذابل وزعلان"})["handoff"]
    assert not do_think({"text": "السلام عليكم"})["handoff"]

def test_custom_prices_are_respected():
    r = do_think({"text": "كم سعر الجوري؟", "products": [{"name": "بوكيه جوري خاص", "aliases": ["جوري"], "price": 99}]})
    assert "99" in r["reply"] and "150" not in r["reply"]

def test_extract_order_from_conversation():
    j = do_extract({"messages": [{"fromMe": False, "text": "ابي اطلب بوكيه توليب"}, {"fromMe": True, "text": "أبشر"}, {"fromMe": False, "text": "بكره العصر حي النرجس"}]})
    assert j["orders"][0]["amount"] == 220 and j["orders"][0]["deliveryDate"] and j["stage"] == "طلب" and j["score"] >= 60

def test_suggest_returns_distinct_replies():
    j = do_suggest({"messages": [{"fromMe": False, "text": "السلام عليكم"}]})
    assert j["replies"] and len(set(j["replies"])) == len(j["replies"])

def test_server_requires_key():
    s = BrainServer("k1"); s.start()
    try:
        bad = urllib.request.Request(s.url + "/think", data=b"{}", headers={"X-Brain-Key": "nope"})
        with pytest.raises(urllib.error.HTTPError): urllib.request.urlopen(bad, timeout=3)
        ok = urllib.request.Request(s.url + "/think", data=json.dumps({"text": "هلا"}).encode(), headers={"X-Brain-Key": "k1"})
        assert json.loads(urllib.request.urlopen(ok, timeout=3).read())["kind"]
    finally: s.stop()

def test_make_kb_ignores_garbage():
    kb = make_kb({"products": [None, {"name": ""}, {"name": "x", "price": "abc"}]})
    assert kb["products"][0]["name"] == "x" and kb["products"][0]["price"] is None
