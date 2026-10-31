from app.core.parser import parse_chat, guess_customer, find_phone

def test_android_export():
    t = "12/31/23, 9:15 PM - Messages and calls are end-to-end encrypted.\n12/31/23, 9:16 PM - خالد: السلام عليكم\n12/31/23, 9:17 PM - خالد: كم السعر؟\nسطر ثاني\n12/31/23, 9:18 PM - أنا: هلا"
    m = parse_chat(t)
    assert len(m) == 3 and m[0].sender == "خالد" and "سطر ثاني" in m[1].text and m[0].timestamp

def test_ios_export():
    m = parse_chat("[31/12/2023, 21:15:03] نورة: ابي اطلب\n[31/12/2023, 21:16:00] Me: أبشري")
    assert [x.sender for x in m] == ["نورة", "Me"]

def test_simple_and_guess():
    m = parse_chat("فهد: هلا رقمي 0551234567\nأنا: هلا فيك")
    assert guess_customer(m) == "فهد" and find_phone(m) == "0551234567"

def test_plain_text():
    m = parse_chat("وش عندكم من عروض")
    assert len(m) == 1 and m[0].sender == "العميل"

def test_empty():
    assert parse_chat("") == []
