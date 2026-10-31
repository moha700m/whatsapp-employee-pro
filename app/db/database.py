"""SQLite access with migrations, WAL, transactional safe writes and backups."""
import shutil, sqlite3, threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from app import config
from app.db.migrations import MIGRATIONS

class Database:
    def __init__(self, path=None):
        self.path = Path(path or config.DB_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        if str(self.path) != ":memory:":
            self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.migrate()

    def migrate(self):
        with self._lock:
            self.conn.execute("CREATE TABLE IF NOT EXISTS schema_version(version INTEGER)")
            cur = self.conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] or 0
            for ver, sql in MIGRATIONS:
                if ver > cur:
                    if cur > 0:
                        self.backup(tag=f"pre-migration-{ver}")
                    with self.transaction() as c:
                        for stmt in sql.split(";"):
                            if stmt.strip():
                                c.execute(stmt)
                        c.execute("INSERT INTO schema_version VALUES (?)", (ver,))
    @property
    def version(self):
        return self.conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]

    @contextmanager
    def transaction(self):
        with self._lock:
            try:
                self.conn.execute("BEGIN")
                yield self.conn
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise

    def execute(self, sql, params=()):
        with self.transaction() as c:
            return c.execute(sql, params).lastrowid

    def query(self, sql, params=()):
        with self._lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def scalar(self, sql, params=()):
        with self._lock:
            r = self.conn.execute(sql, params).fetchone()
            return r[0] if r else None

    def backup(self, tag="manual"):
        config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        dest = config.BACKUP_DIR / f"employee-{datetime.now():%Y%m%d-%H%M%S-%f}-{tag}.db"
        with self._lock:
            b = sqlite3.connect(str(dest))
            self.conn.backup(b)
            b.close()
        backups = sorted(config.BACKUP_DIR.glob("employee-*.db"))
        for old in backups[:-config.MAX_BACKUPS]:
            old.unlink(missing_ok=True)
        return dest

    def close(self):
        self.conn.close()
