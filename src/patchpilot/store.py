"""Transactional local job store. Approval is an auditable record, not a code push."""
from __future__ import annotations
import json
from pathlib import Path
import sqlite3
import time
import uuid
from contextlib import contextmanager

class Conflict(ValueError): pass

class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as c:
            c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, task_id TEXT NOT NULL, provider TEXT NOT NULL,
                issue TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL,
                updated REAL NOT NULL, version INTEGER NOT NULL DEFAULT 0,
                result TEXT NOT NULL DEFAULT '{}', error TEXT);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
                created REAL NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id));
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL, decision TEXT NOT NULL, note TEXT NOT NULL,
                created REAL NOT NULL, FOREIGN KEY(job_id) REFERENCES jobs(id));
            CREATE INDEX IF NOT EXISTS ix_events_job ON events(job_id,id);
            ''')

    @contextmanager
    def connection(self):
        c = sqlite3.connect(self.path,timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def create(self, task_id: str, provider: str, issue: str) -> dict:
        ident = uuid.uuid4().hex[:16]
        now = time.time()
        with self.connection() as c:
            c.execute("INSERT INTO jobs(id,task_id,provider,issue,status,created,updated) VALUES(?,?,?,?,?,?,?)",
                      (ident,task_id,provider,issue,"queued",now,now))
        self.event(ident,"queued",{"message":"Job accepted"})
        return self.get(ident)

    def get(self, ident: str) -> dict:
        with self.connection() as c:
            row = c.execute("SELECT * FROM jobs WHERE id=?",(ident,)).fetchone()
            if not row: raise KeyError(ident)
            result = dict(row); result["result"] = json.loads(result["result"])
            result["reviews"] = [dict(r) for r in c.execute("SELECT candidate_id,decision,note,created FROM reviews WHERE job_id=? ORDER BY id",(ident,))]
            return result

    def jobs(self, limit: int = 50) -> list[dict]:
        with self.connection() as c:
            return [dict(r) for r in c.execute("SELECT id,task_id,provider,status,created,updated,version FROM jobs ORDER BY created DESC LIMIT ?",(min(limit,100),))]

    def transition(self, ident: str, expected: str, status: str, result: dict | None = None, error: str | None = None):
        with self.connection() as c:
            cursor = c.execute("UPDATE jobs SET status=?,result=?,error=?,updated=?,version=version+1 WHERE id=? AND status=?",
                               (status,json.dumps(result or {}),error,time.time(),ident,expected))
            if cursor.rowcount != 1: raise Conflict("Job state changed; reload before retrying")
        self.event(ident,status,{"message":error or status.replace("_"," ")})

    def event(self, ident: str, kind: str, payload: dict):
        with self.connection() as c:
            c.execute("INSERT INTO events(job_id,created,kind,payload) VALUES(?,?,?,?)",(ident,time.time(),kind,json.dumps(payload)))

    def events(self, ident: str, after: int = 0) -> list[dict]:
        with self.connection() as c:
            rows = c.execute("SELECT * FROM events WHERE job_id=? AND id>? ORDER BY id LIMIT 200",(ident,after)).fetchall()
        return [{**dict(r),"payload":json.loads(r["payload"])} for r in rows]

    def review(self, ident: str, candidate_id: str, decision: str, note: str, version: int) -> dict:
        if decision not in {"approve","reject"}: raise ValueError("Unsupported review decision")
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM jobs WHERE id=?",(ident,)).fetchone()
            if not row: raise KeyError(ident)
            if row["status"] != "awaiting_review" or row["version"] != version:
                raise Conflict("Already reviewed or stale version; reload the job")
            candidates = json.loads(row["result"]).get("candidates",[])
            candidate = next((x for x in candidates if x["id"]==candidate_id),None)
            if not candidate: raise ValueError("Candidate does not belong to this job")
            if decision=="approve" and not candidate.get("eligible"):
                raise Conflict("Only a candidate passing every public test can be approved")
            c.execute("INSERT INTO reviews(job_id,candidate_id,decision,note,created) VALUES(?,?,?,?,?)",
                      (ident,candidate_id,decision,note,time.time()))
            status = "approved" if decision=="approve" else "rejected"
            c.execute("UPDATE jobs SET status=?,version=version+1,updated=? WHERE id=?",(status,time.time(),ident))
            c.execute("INSERT INTO events(job_id,created,kind,payload) VALUES(?,?,?,?)",
                      (ident,time.time(),"review",json.dumps({"decision":decision,"candidate_id":candidate_id,"note":note})))
        return self.get(ident)

    def interrupt_pending(self) -> int:
        with self.connection() as c:
            rows = c.execute("SELECT id FROM jobs WHERE status IN ('running','queued')").fetchall()
            for r in rows:
                c.execute("UPDATE jobs SET status='interrupted',error='Server restarted; rerun explicitly',version=version+1,updated=? WHERE id=?",(time.time(),r["id"]))
                c.execute("INSERT INTO events(job_id,created,kind,payload) VALUES(?,?,?,?)",(r["id"],time.time(),"interrupted",'{"message":"Server restart; no automatic replay of side effects"}'))
        return len(rows)
