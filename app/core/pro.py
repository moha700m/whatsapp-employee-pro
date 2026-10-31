"""Pro features: order cards, daily backup + export/restore, retention, reports, reminders, occasion campaigns.
Everything is local (SQLite in data/). Nothing is sent anywhere."""
import json, shutil, sqlite3, time, zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from app import config
from app.brain.knowledge import load_kb, upcoming_occasions
from app.brain.normalize import sar, phone966

ORDER_STATUSES = ["جديد", "مؤكد", "قيد التجهيز", "طلع للتوصيل", "تم التوصيل", "ملغي"]

# ---------- order card ----------
def order_from_brain(repo, customer_id, chat, brain):
    """Create/refresh the open order card for a chat from extracted entities (never sends anything)."""
    e = brain.get("entities") or {}
    if not e.get("items"): return None
    db = repo.db
    row = db.query("SELECT * FROM orders WHERE customer_id=? AND status IN ('جديد','مؤكد') ORDER BY id DESC LIMIT 1", (customer_id,))
    vals = {"item": "، ".join(e["items"]), "quantity": e.get("quantity"), "amount": brain.get("total") or 0,
            "delivery_date": e.get("date"), "delivery_time": e.get("time"), "city": e.get("city"), "district": e.get("district"),
            "address": e.get("location_link"), "phone": e.get("phone"), "occasion": e.get("occasion"), "card_text": e.get("card_text"), "chat": chat}
    if row:
        cur = row[0]
        if not e.get("quantity") and vals["amount"] and (cur.get("quantity") or 1) > 1:
            vals["amount"] = vals["amount"] * cur["quantity"]
        upd = {k: v for k, v in vals.items() if v not in (None, "", 0)}
        sets = ", ".join(f"{k}=?" for k in upd)
        db.execute(f"UPDATE orders SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?", (*upd.values(), cur["id"]))
        return cur["id"]
    vals["quantity"] = vals["quantity"] or 1
    cols = ["customer_id"] + list(vals)
    return db.execute(f"INSERT INTO orders({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", (customer_id, *vals.values()))

def order_update(repo, id, fields):
    allowed = {"item", "quantity", "amount", "delivery_date", "delivery_time", "city", "district", "address", "phone", "occasion", "card_text", "status"}
    f = {k: v for k, v in (fields or {}).items() if k in allowed}
    if "status" in f and f["status"] not in ORDER_STATUSES: raise ValueError("حالة غير معروفة")
    if "phone" in f and f["phone"]: f["phone"] = phone966(f["phone"]) or f["phone"]
    if not f: return False
    repo.db.execute(f"UPDATE orders SET {', '.join(k + '=?' for k in f)}, updated_at=CURRENT_TIMESTAMP WHERE id=?", (*f.values(), int(id)))
    return True

def orders_board(repo):
    rows = repo.db.query("SELECT o.*, c.name AS customer FROM orders o LEFT JOIN customers c ON c.id=o.customer_id ORDER BY COALESCE(o.delivery_date,'9999'), o.id DESC")
    for r in rows: r["amount_text"] = sar(r["amount"] or 0)
    return rows

# ---------- backup / export / restore ----------
def backup_if_due(db, repo):
    today = date.today().isoformat()
    if repo.get_setting("pro.last_backup", "") == today: return None
    dest = db.backup(tag="daily"); repo.set_setting("pro.last_backup", today)
    return str(dest)

def export_zip(db, dest_dir=None):
    dest_dir = Path(dest_dir or config.DATA_DIR / "exports"); dest_dir.mkdir(parents=True, exist_ok=True)
    snap = db.backup(tag="export")
    out = dest_dir / f"whatsapp-employee-export-{datetime.now():%Y%m%d-%H%M%S}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(snap, "employee.db")
        z.writestr("README.txt", "نسخة احتياطية من موظف واتساب. للاسترجاع: الإعدادات ← استرجاع نسخة.")
    return str(out)

def restore_zip(db, path):
    """Validate an export zip, back up the current DB, then replace contents via SQLite backup API."""
    path = Path(path)
    with zipfile.ZipFile(path) as z:
        if "employee.db" not in z.namelist(): raise ValueError("الملف مو نسخة صحيحة")
        tmp = config.DATA_DIR / "restore-tmp.db"; tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(z.read("employee.db"))
    src = sqlite3.connect(str(tmp))
    try:
        if src.execute("PRAGMA integrity_check").fetchone()[0] != "ok": raise ValueError("النسخة تالفة")
        if not src.execute("SELECT name FROM sqlite_master WHERE name='customers'").fetchone(): raise ValueError("النسخة ناقصة")
        db.backup(tag="pre-restore")
        with db._lock: src.backup(db.conn)
    finally:
        src.close(); tmp.unlink(missing_ok=True)
    db.migrate()
    return True

# ---------- retention ----------
def apply_retention(repo, days):
    days = int(days or 0)
    if days <= 0: return 0
    cut = f"-{days} days"; db = repo.db; n = 0
    for t in ("messages", "auto_replies", "drafts", "activity_log", "processed_messages", "incoming_log"):
        col = "created_at" if t not in ("messages", "incoming_log") else None
        if t == "messages":
            n += db.scalar("SELECT COUNT(*) FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE created_at < datetime('now', ?))", (cut,)) or 0
            db.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE created_at < datetime('now', ?))", (cut,))
        elif t == "incoming_log":
            db.execute("DELETE FROM incoming_log WHERE received_at < ?", (time.time() - days * 86400,))
        else:
            n += db.scalar(f"SELECT COUNT(*) FROM {t} WHERE {col} < datetime('now', ?)", (cut,)) or 0
            db.execute(f"DELETE FROM {t} WHERE {col} < datetime('now', ?)", (cut,))
    return n

# ---------- reports ----------
def log_incoming(repo, chat, ts=None):
    repo.db.execute("INSERT INTO incoming_log(chat, received_at) VALUES (?,?)", (chat, ts or time.time()))

def log_answered(repo, chat, ts=None):
    repo.db.execute("UPDATE incoming_log SET answered_at=? WHERE chat=? AND answered_at IS NULL", (ts or time.time(), chat))

def reports(repo, days=30):
    db = repo.db
    rt = db.query("SELECT answered_at - received_at AS s FROM incoming_log WHERE answered_at IS NOT NULL AND received_at > ?", (time.time() - days * 86400,))
    secs = sorted(r["s"] for r in rt if r["s"] is not None and r["s"] >= 0)
    med = secs[len(secs) // 2] if secs else None
    unanswered = db.scalar("SELECT COUNT(DISTINCT chat) FROM incoming_log WHERE answered_at IS NULL") or 0
    cust = db.scalar("SELECT COUNT(*) FROM customers") or 0
    buyers = db.scalar("SELECT COUNT(DISTINCT customer_id) FROM orders WHERE status NOT IN ('ملغي')") or 0
    delivered = db.query("SELECT COUNT(*) n, COALESCE(SUM(amount),0) s FROM orders WHERE status='تم التوصيل'")[0]
    pipeline = {s: db.scalar("SELECT COUNT(*) FROM orders WHERE status=?", (s,)) or 0 for s in ORDER_STATUSES}
    by_occ = db.query("SELECT COALESCE(occasion,'بدون') occasion, COUNT(*) n, COALESCE(SUM(amount),0) s FROM orders WHERE status!='ملغي' GROUP BY 1 ORDER BY 2 DESC")
    fmt = lambda s: "—" if s is None else (f"{int(s)} ث" if s < 60 else f"{int(s // 60)} د" if s < 3600 else f"{s / 3600:.1f} س")
    return {"median_response": fmt(med), "avg_response": fmt(sum(secs) / len(secs) if secs else None), "answered": len(secs),
            "unanswered_chats": unanswered, "customers": cust, "buyers": buyers,
            "conversion": f"{(buyers / cust * 100):.0f}%" if cust else "0%", "delivered": delivered["n"], "revenue": sar(delivered["s"]),
            "pipeline": pipeline, "by_occasion": by_occ}

# ---------- reminders ----------
def add_reminder(repo, due_at, text, customer_id=None, chat=""):
    return repo.db.execute("INSERT INTO reminders(customer_id, chat, due_at, text) VALUES (?,?,?,?)", (customer_id, chat, due_at, text))

def due_reminders(repo, now=None):
    now = (now or datetime.now()).strftime("%Y-%m-%d %H:%M")
    rows = repo.db.query("SELECT * FROM reminders WHERE status='open' AND due_at <= ? ORDER BY due_at", (now,))
    fu = repo.db.query("SELECT f.id, f.customer_id, c.name AS chat, f.due_date AS due_at, COALESCE(f.message,'تابع العميل') AS text FROM follow_ups f "
                       "JOIN customers c ON c.id=f.customer_id WHERE f.status='open' AND f.due_date <= date('now','localtime')")
    for r in fu: r["kind"] = "followup"
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    dl = repo.db.query("SELECT o.id, o.customer_id, c.name AS chat, o.delivery_date AS due_at, 'توصيل: ' || o.item AS text FROM orders o "
                       "LEFT JOIN customers c ON c.id=o.customer_id WHERE o.status IN ('جديد','مؤكد','قيد التجهيز') AND o.delivery_date <= ?", (tomorrow,))
    for r in dl: r["kind"] = "delivery"
    return [dict(r, kind=r.get("kind", "reminder")) for r in rows] + fu + dl

def reminder_done(repo, id):
    repo.db.execute("UPDATE reminders SET status='done' WHERE id=?", (int(id),)); return True

# ---------- occasion campaigns (drafts only) ----------
def campaign_suggestions(repo, today=None, days=60):
    kb = load_kb(repo); out = []
    for u in upcoming_occasions(today, days, kb):
        o = kb["occasions"][u["occasion"]]
        items = [p for p in kb["products"] if p["name"] in o.get("suggest", []) and p.get("price")]
        offer = "، ".join(f"{p['name']} بـ{sar(p['price'])}" for p in items) or "تنسيقات خاصة"
        msg = (f"هلا والله 🌷 {u['occasion']} قرب ({u['date']})، جهزنا لكم بألوان {o.get('colors','')}: {offer}. "
               f"احجز بدري ونوصل لك في الوقت اللي تبيه 🌸\nلإيقاف الرسائل اكتب: وقف")
        out.append({**u, "message": msg, "segment": "كل العملاء الموافقين على التسويق"})
    return out
