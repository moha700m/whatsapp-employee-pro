"""Pro features: order card, reports, reminders, backup export/restore, retention, Ollama optional."""
import time, zipfile
from datetime import date
from app.brain import think
from app.core import pro
from app.ai.providers import OllamaProvider, ChatGPTWebProvider
from app.core.settings import AutoReplySettings

def test_order_card_from_chat(repo):
    cid = repo.upsert_customer("سارة", "")
    b = think("ابي اطلب ٢ بوكيه توليب بكره حي الفيصلية الدمام", today=date(2026, 10, 31))
    oid = pro.order_from_brain(repo, cid, "سارة", b)
    pro.order_from_brain(repo, cid, "سارة", think("اكتب: كل عام وانتي بخير يا امي، بوكيه توليب"))
    o = pro.orders_board(repo)[0]
    assert o["id"] == oid and o["quantity"] == 2 and o["amount_text"] == "440 ر.س" and o["district"] == "الفيصليه"
    assert pro.order_update(repo, oid, {"status": "مؤكد", "phone": "0551234567"})
    assert pro.orders_board(repo)[0]["phone"] == "+966551234567"

def test_reports_and_reminders(repo):
    cid = repo.upsert_customer("نوره", "")
    now = time.time(); pro.log_incoming(repo, "نوره", now - 120); pro.log_answered(repo, "نوره", now)
    pro.log_incoming(repo, "خالد", now)
    repo.db.execute("INSERT INTO orders(customer_id, item, amount, status) VALUES (?,?,?,?)", (cid, "بوكيه", 150, "تم التوصيل"))
    r = pro.reports(repo)
    assert r["median_response"] == "2 د" and r["unanswered_chats"] == 1 and r["revenue"] == "150 ر.س" and r["conversion"] == "100%"
    pro.add_reminder(repo, "2000-01-01 10:00", "كلم نوره عن طلب العرس", cid, "نوره")
    assert any(x["text"].startswith("كلم نوره") for x in pro.due_reminders(repo))

def test_campaign_drafts(repo):
    c = pro.campaign_suggestions(repo, today=date(2026, 9, 1), days=30)
    assert c and c[0]["occasion"] == "اليوم الوطني" and "وقف" in c[0]["message"] and "ر.س" in c[0]["message"]

def test_backup_export_restore_and_retention(repo, tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "b"); monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    repo.upsert_customer("قبل", "")
    z = pro.export_zip(repo.db, tmp_path)
    assert "employee.db" in zipfile.ZipFile(z).namelist()
    repo.upsert_customer("بعد", "")
    assert pro.restore_zip(repo.db, z)
    names = [c["name"] for c in repo.customers()]
    assert "قبل" in names and "بعد" not in names
    assert pro.backup_if_due(repo.db, repo) and pro.backup_if_due(repo.db, repo) is None
    repo.db.execute("INSERT INTO activity_log(action, created_at) VALUES ('old', datetime('now','-100 days'))")
    assert pro.apply_retention(repo, 30) >= 1 and pro.apply_retention(repo, 0) == 0

def test_ollama_optional_and_chatgpt_off(repo):
    assert not OllamaProvider(host="http://127.0.0.1:9").available()
    s = AutoReplySettings()
    assert s.provider == "offline" and not s.chatgpt_experimental and s.send_mode == "approval" and not s.after_hours_auto
    assert not ChatGPTWebProvider().available()
