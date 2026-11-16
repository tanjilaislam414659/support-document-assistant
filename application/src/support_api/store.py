"""Local SQLite revisions and review events. No sending or model integration."""
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sqlite3,uuid
from .errors import AppError

LIMITS=["Local draft only; no sending endpoint.", "Review records a user action, not authenticated identity or guaranteed truth."]

def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def now():return datetime.now(timezone.utc).isoformat()
def indent(text):return "\n".join("    "+line for line in text.splitlines())

def render(content,quotes):
    parts=["LOCAL SUPPORT DRAFT — no automatic submission","",
        "USER-PROVIDED TITLE",indent(content["title"]),"USER-PROVIDED ISSUE",indent(content["issue"]),
        "EXPLICITLY SUPPLIED ENVIRONMENT"]
    parts += [indent(k+": "+v) for k,v in sorted(content["environment"].items())] or ["    (not supplied)"]
    parts += ["MISSING INFORMATION — editable"]
    parts += [indent(x) for x in content["missing_information"]] or ["    (none listed by user)"]
    parts += ["USER NOTES",indent(content["human_notes"]) or "    (none)","QUOTED DOCUMENTATION — untrusted source content"]
    for q in quotes:
        parts += [q["passage_id"]+" | "+q["source_url"]+" | version "+q["product_version"],indent(q["text"])]
    if not quotes:parts += ["    (no documentation selected)"]
    parts += ["REVIEW", "    A review event is a local user action and does not establish truth."]
    return "\n".join(parts)

class TicketStore:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript("""
            CREATE TABLE IF NOT EXISTS tickets(id TEXT PRIMARY KEY,current_revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS revisions(ticket_id TEXT NOT NULL,revision INTEGER NOT NULL,
                content_json TEXT NOT NULL,created_at TEXT NOT NULL,content_sha256 TEXT NOT NULL,
                PRIMARY KEY(ticket_id,revision),FOREIGN KEY(ticket_id) REFERENCES tickets(id));
            CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY,ticket_id TEXT NOT NULL,revision INTEGER NOT NULL,
                reviewer_label TEXT NOT NULL,note TEXT NOT NULL,recorded_at TEXT NOT NULL,content_sha256 TEXT NOT NULL,
                FOREIGN KEY(ticket_id,revision) REFERENCES revisions(ticket_id,revision));
            """)

    @contextmanager
    def connection(self):
        c=sqlite3.connect(self.path,timeout=2);c.row_factory=sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        try:
            yield c
            c.commit()
        except BaseException:
            c.rollback();raise
        finally:c.close()

    def check(self):
        with self.connection() as c:
            c.execute("SELECT id FROM tickets LIMIT 1").fetchall()

    def _get(self,c,tid):
        row=c.execute("SELECT current_revision FROM tickets WHERE id=?",(tid,)).fetchone()
        if not row:raise AppError(404,"ticket_not_found","No local ticket with that ID")
        rev=row[0]
        rows=c.execute("SELECT revision,created_at,content_sha256 FROM revisions WHERE ticket_id=? ORDER BY revision",(tid,)).fetchall()
        current=c.execute("SELECT content_json,content_sha256 FROM revisions WHERE ticket_id=? AND revision=?",(tid,rev)).fetchone()
        try:payload=json.loads(current["content_json"])
        except (ValueError,TypeError):raise AppError(503,"store_corrupt","Saved ticket content is invalid")
        if hashlib.sha256(encoded(payload).encode()).hexdigest()!=current["content_sha256"]:
            raise AppError(503,"store_corrupt","Saved ticket content integrity check failed")
        events=[{"event_id":r["id"],"revision":r["revision"],"reviewer_label":r["reviewer_label"],
            "note":r["note"],"recorded_at":r["recorded_at"],"content_sha256":r["content_sha256"],
            "identity_authenticated":False,"current_revision":r["revision"]==rev} for r in
            c.execute("SELECT * FROM reviews WHERE ticket_id=? ORDER BY rowid",(tid,))]
        return {"ticket_id":tid,"revision":rev,"review_state":"review_recorded" if any(e["current_revision"] for e in events) else "unreviewed",
            **payload,"content_sha256":current["content_sha256"],"history":[dict(r) for r in rows],
            "review_events":events,"limitations":LIMITS}

    def _save_revision(self,c,tid,rev,content,quotes):
        payload={"content":content,"documentation":quotes,"rendered_text":render(content,quotes)}
        text=encoded(payload);digest=hashlib.sha256(text.encode()).hexdigest()
        c.execute("INSERT INTO revisions VALUES(?,?,?,?,?)",(tid,rev,text,now(),digest))

    def create(self,content,quotes):
        tid=uuid.uuid4().hex
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("INSERT INTO tickets VALUES(?,1)",(tid,))
            self._save_revision(c,tid,1,content,quotes)
            return self._get(c,tid)

    def get(self,tid):
        with self.connection() as c:return self._get(c,tid)

    def edit(self,tid,expected,content,quotes):
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            old=self._get(c,tid)
            if old["revision"]!=expected:raise AppError(409,"stale_revision","Edit the latest revision")
            rev=expected+1
            self._save_revision(c,tid,rev,content,quotes)
            c.execute("UPDATE tickets SET current_revision=? WHERE id=?",(rev,tid))
            return self._get(c,tid)

    def review(self,tid,request):
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            old=self._get(c,tid)
            if old["revision"]!=request["expected_revision"]:raise AppError(409,"stale_revision","Review applies only to the current revision")
            c.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?,?)",(uuid.uuid4().hex,tid,old["revision"],
                request["reviewer_label"],request["note"],now(),old["content_sha256"]))
            return self._get(c,tid)
