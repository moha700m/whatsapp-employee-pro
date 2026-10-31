"""Activity logging to rotating file + DB."""
import logging
from logging.handlers import RotatingFileHandler
from app import config

_logger = None

def get_logger():
    global _logger
    if _logger is None:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        _logger = logging.getLogger("wae")
        _logger.setLevel(logging.INFO)
        if not _logger.handlers:
            path = config.LOG_DIR / "activity.log"
            if not path.exists() or path.stat().st_size == 0:
                path.write_bytes(b"\xef\xbb\xbf")      # UTF-8 BOM so Notepad shows Arabic correctly
            h = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=5, encoding="utf-8", errors="backslashreplace")
            h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            _logger.addHandler(h)
    return _logger

def log_activity(db, action, details="", level="INFO"):
    get_logger().log(getattr(logging, level, logging.INFO), "%s | %s", action, details)
    if db is not None:
        try:
            db.execute("INSERT INTO activity_log(action, details, level) VALUES (?,?,?)",
                       (action, str(details)[:2000], level))
        except Exception as e:  # never let logging crash the app
            get_logger().error("db log failed: %s", e)
