import pytest
from app import config
from app.db.database import Database
from app.db.repository import Repository
from app.core.kill_switch import KILL_SWITCH

@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    db = Database(tmp_path / "t.db")
    yield Repository(db)
    KILL_SWITCH.release(); db.close()
