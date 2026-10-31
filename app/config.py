"""Paths and constants. No secrets live here."""
APP_NAME = "موظف واتساب"
APP_VERSION = "2.3.0"
import os
from pathlib import Path

import sys
_DEFAULT_HOME = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
BASE_DIR = Path(os.environ.get("WAE_HOME", _DEFAULT_HOME))   # frozen .exe: data\ lives next to WhatsAppEmployee.exe
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.environ.get("WAE_DB", DATA_DIR / "employee.db"))
BACKUP_DIR = DATA_DIR / "backups"
LOG_DIR = DATA_DIR / "logs"
MAX_BACKUPS = 10

CLASSIFICATIONS = ["New Lead", "Interested", "Hot Lead", "Existing Customer",
                   "Follow-up", "Support", "Complaint"]
CLASS_AR = {"New Lead": "عميل جديد", "Interested": "مهتم", "Hot Lead": "جاهز للشراء",
            "Existing Customer": "عميل حالي", "Follow-up": "متابعة",
            "Support": "دعم فني", "Complaint": "شكوى"}
PIPELINE_STAGES = ["New Lead", "Interested", "Hot Lead", "Existing Customer"]

def secure_data_dir():
    """Owner-only permissions on data/ (DB, Chrome profile, logs). On Windows the folder inherits the user's profile ACL."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        for p in [DATA_DIR, *DATA_DIR.rglob("*")]:
            try: os.chmod(p, 0o700 if p.is_dir() else 0o600)
            except OSError: pass
