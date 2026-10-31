"""Simple transparent lead score 0-100 (Hot/Warm/Cold).
Pattern (not code) inspired by open-source CRMs: intent points + customer initiative + recency decay."""
from datetime import datetime

INTENT = {"Hot Lead": 60, "Interested": 40, "Existing Customer": 35, "Follow-up": 25, "New Lead": 15, "Support": 10, "Complaint": 0}

def decay(days):
    return 0 if days <= 3 else -5 if days <= 7 else -10 if days <= 14 else -20 if days <= 30 else -30

def score(classification, inbound_msgs, conversations, last_contact):
    s = INTENT.get(classification or "New Lead", 15)
    s += min(inbound_msgs, 10) * 2           # how much the customer talks to us
    s += min(conversations, 5) * 3            # repeat conversations
    if last_contact:
        try:
            days = (datetime.now() - datetime.fromisoformat(str(last_contact).replace(" ", "T")[:19])).days
            s += decay(days)
        except ValueError:
            pass
    s = max(0, min(100, s))
    return {"value": s, "band": "Hot" if s >= 60 else "Warm" if s >= 35 else "Cold",
            "band_ar": "🔥 جاهز يشتري" if s >= 60 else "👀 مهتم" if s >= 35 else "💤 ما بعد قرر"}

def score_customer(repo, cid):
    c = repo.db.query("SELECT classification, last_contact FROM customers WHERE id=?", (cid,))
    if not c:
        return None
    inbound = (repo.db.scalar("SELECT COUNT(*) FROM messages m JOIN conversations v ON v.id=m.conversation_id WHERE v.customer_id=?", (cid,)) or 0) \
        + (repo.db.scalar("SELECT COUNT(*) FROM drafts WHERE customer_id=?", (cid,)) or 0)
    convs = repo.db.scalar("SELECT COUNT(*) FROM conversations WHERE customer_id=?", (cid,)) or 0
    return score(c[0]["classification"], inbound, convs, c[0]["last_contact"])
