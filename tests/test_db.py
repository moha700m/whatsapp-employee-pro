from app.db.database import Database
from app.core.parser import Message
from app.ai.orchestrator import Orchestrator

TABLES = ["customers","conversations","messages","analyses","suggested_replies","follow_ups",
          "campaigns","consents","activity_log","settings","business_info","processed_messages","auto_replies","needs_attention","drafts"]

def test_schema(repo):
    names = {r["name"] for r in repo.db.query("SELECT name FROM sqlite_master WHERE type='table'")}
    assert set(TABLES) <= names and repo.db.version == 5

def test_migration_idempotent(repo):
    Database(repo.db.path).close(); assert repo.db.version == 5

def test_cascade_delete(repo):
    cid = repo.upsert_customer("سارة", "0500000000")
    conv = repo.add_conversation(cid, [Message("سارة", "هلا")])
    repo.save_analysis(conv, {"summary":"s","need":"n","classification":"New Lead","handoff":False,"reply":"r"}, "h")
    repo.add_follow_up(cid, "2026-11-01", "")
    repo.delete_customer(cid)
    for t in ("customers","messages","analyses","suggested_replies","follow_ups","consents"):
        assert repo.db.scalar(f"SELECT COUNT(*) FROM {t}") == 0

def test_transaction_rollback(repo):
    try:
        with repo.db.transaction() as c:
            c.execute("INSERT INTO settings VALUES ('a','1')"); raise RuntimeError
    except RuntimeError:
        pass
    assert repo.get_setting("a", None) is None

def test_backup_and_settings(repo):
    repo.set_setting("x", 5); repo.set_setting("x", 6)
    assert repo.get_setting("x") == "6"
    assert repo.db.backup("t").exists()

def test_opt_out(repo):
    cid = repo.upsert_customer("علي"); repo.add_follow_up(cid, "2026-11-02", "")
    repo.stop_follow_ups(cid)
    assert repo.follow_ups()[0]["status"] == "stopped"
    assert repo.db.scalar("SELECT opted_out FROM consents WHERE customer_id=?", (cid,)) == 1

def test_upgrade_from_v1_keeps_data(tmp_path, monkeypatch):
    import sqlite3
    from app import config
    from app.db import migrations
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "b")
    monkeypatch.setattr(migrations, "MIGRATIONS", migrations.MIGRATIONS[:1])
    import app.db.database as dbm
    monkeypatch.setattr(dbm, "MIGRATIONS", migrations.MIGRATIONS[:1])
    d = Database(tmp_path / "u.db"); d.execute("INSERT INTO customers(name) VALUES ('قديم')"); d.close()
    monkeypatch.undo(); monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "b")
    d = Database(tmp_path / "u.db")
    assert d.version == 5 and d.scalar("SELECT name FROM customers") == "قديم"
    assert list((tmp_path / "b").glob("*pre-migration-2*"))
