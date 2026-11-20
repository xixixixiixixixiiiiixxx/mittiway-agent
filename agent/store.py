"""SQLite persistence with per-browser ownership and idempotent local tickets."""
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
import json
import re
import secrets
import sqlite3

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def redact(text):
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已脱敏]", text)
    return re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[邮箱已脱敏]", text)

class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL, state TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id), role TEXT NOT NULL, content TEXT NOT NULL, payload TEXT, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS tickets(id TEXT PRIMARY KEY, owner TEXT NOT NULL, conversation_id TEXT NOT NULL REFERENCES conversations(id), category TEXT NOT NULL, summary TEXT NOT NULL, details TEXT NOT NULL, slots TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'local_pending', idempotency_key TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(owner,idempotency_key));
            CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY, owner TEXT NOT NULL, message_id TEXT NOT NULL REFERENCES messages(id), rating TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(owner,message_id));
            CREATE INDEX IF NOT EXISTS conversation_owner ON conversations(owner);
            CREATE INDEX IF NOT EXISTS message_conversation ON messages(conversation_id,created_at);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def create_conversation(self, owner):
        cid = secrets.token_hex(16)
        stamp = now()
        with self.connect() as db:
            db.execute("INSERT INTO conversations VALUES(?,?,?,?,?,?)", (cid,owner,"新咨询","{}",stamp,stamp))
        return {"id":cid,"title":"新咨询","created_at":stamp,"messages":[],"state":{}}

    def conversation(self, owner, cid):
        with self.connect() as db:
            row = db.execute("SELECT * FROM conversations WHERE id=? AND owner=?", (cid,owner)).fetchone()
            if not row:
                return None
            result = dict(row)
            result.pop("owner")
            result["state"] = json.loads(result["state"])
            result["messages"] = []
            for message in db.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY rowid", (cid,)):
                m = dict(message)
                m["payload"] = json.loads(m["payload"]) if m["payload"] else None
                result["messages"].append(m)
            return result

    def list_conversations(self, owner):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT id,title,updated_at FROM conversations WHERE owner=? ORDER BY updated_at DESC LIMIT 50", (owner,))]

    def save_turn(self, owner, cid, question, result):
        user_id, answer_id = secrets.token_hex(12), secrets.token_hex(12)
        stamp = now()
        safe_question = redact(question)
        # Redact before any storage; the current transient browser input is not an audit log.
        safe_result = json.loads(redact(json.dumps(result,ensure_ascii=False)))
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM conversations WHERE id=? AND owner=?", (cid,owner)).fetchone():
                raise PermissionError("会话不存在或无权访问")
            db.execute("INSERT INTO messages VALUES(?,?,?,?,?,?)", (user_id,cid,"user",safe_question,None,stamp))
            db.execute("INSERT INTO messages VALUES(?,?,?,?,?,?)", (answer_id,cid,"assistant",safe_result["answer"],json.dumps(safe_result,ensure_ascii=False),stamp))
            db.execute("UPDATE conversations SET title=CASE WHEN title='新咨询' THEN ? ELSE title END, state=?,updated_at=? WHERE id=? AND owner=?", (safe_question[:36],json.dumps(safe_result["state"],ensure_ascii=False),stamp,cid,owner))
        return answer_id

    def tickets(self, owner):
        with self.connect() as db:
            result = [dict(r) for r in db.execute("SELECT id,conversation_id,category,summary,details,slots,status,created_at FROM tickets WHERE owner=? ORDER BY created_at DESC", (owner,))]
            for row in result:
                row["slots"] = json.loads(row["slots"])
            return result

    def create_ticket(self, owner, cid, category, details, idempotency_key):
        conv = self.conversation(owner,cid)
        if not conv:
            raise PermissionError("会话不存在或无权访问")
        ticket_id = "DEMO-"+secrets.token_hex(4).upper()
        summary = next((m["content"] for m in reversed(conv["messages"]) if m["role"]=="user"), "设备咨询")[:120]
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO tickets(id,owner,conversation_id,category,summary,details,slots,idempotency_key,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (ticket_id,owner,cid,category,summary,redact(details),json.dumps(conv["state"].get("slots",{}),ensure_ascii=False),idempotency_key,now()))
            row = db.execute("SELECT id,status,created_at FROM tickets WHERE owner=? AND idempotency_key=?", (owner,idempotency_key)).fetchone()
        return {**dict(row), "delivery":"local_only", "message":"已保存到本机；未发送厂家，未分配真实工程师。"}

    def feedback(self, owner, message_id, rating):
        with self.connect() as db:
            row = db.execute("SELECT m.id FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE m.id=? AND c.owner=? AND m.role='assistant'", (message_id,owner)).fetchone()
            if not row:
                raise PermissionError("答复不存在或无权访问")
            db.execute("INSERT INTO feedback(owner,message_id,rating,created_at) VALUES(?,?,?,?) ON CONFLICT(owner,message_id) DO UPDATE SET rating=excluded.rating,created_at=excluded.created_at", (owner,message_id,rating,now()))
