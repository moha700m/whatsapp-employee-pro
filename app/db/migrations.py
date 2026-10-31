"""Ordered schema migrations. Append new entries; never edit old ones."""
MIGRATIONS = [
(1, """
CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT,
  classification TEXT DEFAULT 'New Lead', stage TEXT DEFAULT 'New Lead', need TEXT,
  interests TEXT, notes TEXT, last_contact TEXT, follow_up_date TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE conversations(id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id) ON DELETE CASCADE,
  title TEXT, source TEXT DEFAULT 'paste', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE messages(id INTEGER PRIMARY KEY, conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
  sender TEXT, text TEXT, timestamp TEXT);
CREATE TABLE analyses(id INTEGER PRIMARY KEY, conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
  summary TEXT, need TEXT, classification TEXT, handoff INTEGER DEFAULT 0, handoff_reason TEXT,
  provider TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE suggested_replies(id INTEGER PRIMARY KEY, analysis_id INTEGER REFERENCES analyses(id) ON DELETE CASCADE,
  text TEXT, status TEXT DEFAULT 'pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE follow_ups(id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id) ON DELETE CASCADE,
  due_date TEXT, message TEXT, status TEXT DEFAULT 'open', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE campaigns(id INTEGER PRIMARY KEY, name TEXT, segment TEXT, message TEXT,
  status TEXT DEFAULT 'draft', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE consents(id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id) ON DELETE CASCADE,
  marketing INTEGER DEFAULT 0, opted_out INTEGER DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE activity_log(id INTEGER PRIMARY KEY, action TEXT, details TEXT, level TEXT DEFAULT 'INFO',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE business_info(id INTEGER PRIMARY KEY, kind TEXT, title TEXT, content TEXT, price TEXT,
  approved INTEGER DEFAULT 1);
CREATE INDEX idx_cust_class ON customers(classification);
"""),
(2, """
CREATE TABLE processed_messages(id INTEGER PRIMARY KEY, msg_key TEXT UNIQUE NOT NULL, chat TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE auto_replies(id INTEGER PRIMARY KEY, chat TEXT, customer_id INTEGER, incoming TEXT, reply TEXT,
  kind TEXT DEFAULT 'auto', classification TEXT, provider TEXT, sent_at REAL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE needs_attention(id INTEGER PRIMARY KEY, chat TEXT, customer_id INTEGER, reason TEXT, last_message TEXT,
  status TEXT DEFAULT 'open', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX idx_auto_chat ON auto_replies(chat, sent_at);
"""),
(3, """
CREATE TABLE drafts(id INTEGER PRIMARY KEY, chat TEXT NOT NULL, customer_id INTEGER, incoming TEXT, reply TEXT,
  kind TEXT DEFAULT 'auto', rule TEXT, classification TEXT, provider TEXT, status TEXT DEFAULT 'pending',
  error TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, sent_at REAL);
CREATE INDEX idx_drafts_status ON drafts(status, chat);
INSERT INTO settings(key, value) VALUES ('ar.send_mode', 'approval') ON CONFLICT(key) DO UPDATE SET value='approval';
"""),
(4, """
CREATE TABLE orders(id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id) ON DELETE CASCADE,
  item TEXT NOT NULL, amount REAL DEFAULT 0, status TEXT DEFAULT 'جديد', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""),
(5, """
ALTER TABLE orders ADD COLUMN chat TEXT;
ALTER TABLE orders ADD COLUMN quantity INTEGER DEFAULT 1;
ALTER TABLE orders ADD COLUMN delivery_date TEXT;
ALTER TABLE orders ADD COLUMN delivery_time TEXT;
ALTER TABLE orders ADD COLUMN city TEXT;
ALTER TABLE orders ADD COLUMN district TEXT;
ALTER TABLE orders ADD COLUMN address TEXT;
ALTER TABLE orders ADD COLUMN phone TEXT;
ALTER TABLE orders ADD COLUMN occasion TEXT;
ALTER TABLE orders ADD COLUMN card_text TEXT;
ALTER TABLE orders ADD COLUMN updated_at TEXT;
ALTER TABLE customers ADD COLUMN lead_score INTEGER DEFAULT 0;
ALTER TABLE customers ADD COLUMN occasion TEXT;
CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY, customer_id INTEGER, chat TEXT, due_at TEXT NOT NULL, text TEXT,
  status TEXT DEFAULT 'open', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS incoming_log(id INTEGER PRIMARY KEY, chat TEXT, received_at REAL, answered_at REAL);
CREATE INDEX IF NOT EXISTS idx_rem_due ON reminders(status, due_at);
"""),
]
