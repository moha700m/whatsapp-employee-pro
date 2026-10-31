"""High-level data operations used by UI and orchestrator."""
from datetime import datetime

class Repository:
    def __init__(self, db):
        self.db = db
    # customers
    def upsert_customer(self, name, phone="", **fields):
        row = self.db.query("SELECT id FROM customers WHERE name=? AND IFNULL(phone,'')=?", (name, phone or ""))
        now = datetime.now().isoformat(timespec="seconds")
        if row:
            cid = row[0]["id"]
            if fields:
                sets = ",".join(f"{k}=?" for k in fields)
                self.db.execute(f"UPDATE customers SET {sets}, updated_at=? WHERE id=?", (*fields.values(), now, cid))
            return cid
        cols = ["name", "phone", "last_contact"] + list(fields)
        vals = [name, phone, now] + list(fields.values())
        cid = self.db.execute(f"INSERT INTO customers({','.join(cols)}) VALUES ({','.join('?'*len(cols))})", vals)
        self.db.execute("INSERT INTO consents(customer_id) VALUES (?)", (cid,))
        return cid
    def update_customer(self, cid, **fields):
        allowed = {"name","phone","classification","stage","need","interests","notes","follow_up_date","last_contact"}
        fields = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if fields:
            sets = ",".join(f"{k}=?" for k in fields)
            self.db.execute(f"UPDATE customers SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?", (*fields.values(), cid))
    def customers(self, search=""):
        q = f"%{search}%"
        return self.db.query("SELECT * FROM customers WHERE name LIKE ? OR IFNULL(phone,'') LIKE ? ORDER BY updated_at DESC", (q, q))
    def delete_customer(self, cid):
        """Hard delete: cascades to conversations, messages, analyses, replies, follow-ups, consents."""
        self.db.execute("DELETE FROM customers WHERE id=?", (cid,))
    def delete_all_customer_data(self):
        with self.db.transaction() as c:
            for t in ("suggested_replies","analyses","messages","conversations","follow_ups","consents","customers"):
                c.execute(f"DELETE FROM {t}")
    # conversations
    def add_conversation(self, customer_id, messages, title="", source="paste"):
        with self.db.transaction() as c:
            conv = c.execute("INSERT INTO conversations(customer_id,title,source) VALUES (?,?,?)",
                             (customer_id, title, source)).lastrowid
            c.executemany("INSERT INTO messages(conversation_id,sender,text,timestamp) VALUES (?,?,?,?)",
                          [(conv, m.sender, m.text, m.timestamp) for m in messages])
        return conv
    def save_analysis(self, conv_id, a, provider):
        with self.db.transaction() as c:
            aid = c.execute("INSERT INTO analyses(conversation_id,summary,need,classification,handoff,handoff_reason,provider) VALUES (?,?,?,?,?,?,?)",
                            (conv_id, a["summary"], a["need"], a["classification"], int(a["handoff"]), a.get("handoff_reason",""), provider)).lastrowid
            c.execute("INSERT INTO suggested_replies(analysis_id,text) VALUES (?,?)", (aid, a["reply"]))
        return aid
    def recent_replies(self, limit=20):
        return self.db.query("SELECT text FROM suggested_replies ORDER BY id DESC LIMIT ?", (limit,))
    def set_reply_status(self, rid, status):
        self.db.execute("UPDATE suggested_replies SET status=? WHERE id=?", (status, rid))
    def inbox(self):
        return self.db.query("""SELECT cv.id, c.name, a.classification, a.summary, a.handoff, cv.created_at
            FROM conversations cv JOIN customers c ON c.id=cv.customer_id
            LEFT JOIN analyses a ON a.conversation_id=cv.id ORDER BY cv.id DESC""")
    def replies(self):
        return self.db.query("""SELECT r.id, c.name, r.text, r.status, r.created_at FROM suggested_replies r
            JOIN analyses a ON a.id=r.analysis_id JOIN conversations cv ON cv.id=a.conversation_id
            JOIN customers c ON c.id=cv.customer_id ORDER BY r.id DESC""")
    # follow-ups / campaigns / consents
    def add_follow_up(self, cid, due, message):
        return self.db.execute("INSERT INTO follow_ups(customer_id,due_date,message) VALUES (?,?,?)", (cid, due, message))
    def follow_ups(self):
        return self.db.query("SELECT f.*, c.name FROM follow_ups f JOIN customers c ON c.id=f.customer_id ORDER BY due_date")
    def close_follow_up(self, fid):
        self.db.execute("UPDATE follow_ups SET status='done' WHERE id=?", (fid,))
    def stop_follow_ups(self, cid):
        self.db.execute("UPDATE follow_ups SET status='stopped' WHERE customer_id=? AND status='open'", (cid,))
        self.db.execute("UPDATE consents SET opted_out=1, marketing=0, updated_at=CURRENT_TIMESTAMP WHERE customer_id=?", (cid,))
    def add_campaign(self, name, segment, message):
        return self.db.execute("INSERT INTO campaigns(name,segment,message) VALUES (?,?,?)", (name, segment, message))
    def campaigns(self):
        return self.db.query("SELECT * FROM campaigns ORDER BY id DESC")
    def set_consent(self, cid, marketing):
        self.db.execute("UPDATE consents SET marketing=?, updated_at=CURRENT_TIMESTAMP WHERE customer_id=?", (int(marketing), cid))
    # business info / settings
    def add_business_info(self, kind, title, content, price=""):
        return self.db.execute("INSERT INTO business_info(kind,title,content,price) VALUES (?,?,?,?)", (kind, title, content, price))
    def business_info(self):
        return self.db.query("SELECT * FROM business_info WHERE approved=1")
    def delete_business_info(self, bid):
        self.db.execute("DELETE FROM business_info WHERE id=?", (bid,))
    def get_setting(self, key, default=""):
        v = self.db.scalar("SELECT value FROM settings WHERE key=?", (key,))
        return default if v is None else v
    def set_setting(self, key, value):
        self.db.execute("INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
    def activity(self, limit=300):
        return self.db.query("SELECT * FROM activity_log ORDER BY id DESC LIMIT ?", (limit,))
    def stats(self):
        s = lambda q: self.db.scalar(q) or 0
        return {
            "total": s("SELECT COUNT(*) FROM customers"),
            "new": s("SELECT COUNT(*) FROM customers WHERE classification='New Lead'"),
            "interested": s("SELECT COUNT(*) FROM customers WHERE classification='Interested'"),
            "hot": s("SELECT COUNT(*) FROM customers WHERE classification='Hot Lead'"),
            "follow": s("SELECT COUNT(*) FROM follow_ups WHERE status='open'"),
            "replies": s("SELECT COUNT(*) FROM suggested_replies"),
            "sales": s("SELECT COUNT(*) FROM customers WHERE stage='Existing Customer'"),
            "approved": s("SELECT COUNT(*) FROM suggested_replies WHERE status='approved'"),
        }
