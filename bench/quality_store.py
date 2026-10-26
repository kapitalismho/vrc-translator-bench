from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .storage import utc_now


CALL_METADATA = "id,job,input_hash,prompt_hash,expected_model,actual_model,state,started_utc,ended_utc,response_date,result,reason,transport"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


class QualityStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "quality.sqlite")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY, job TEXT NOT NULL, input_hash TEXT NOT NULL,
                prompt_hash TEXT NOT NULL, expected_model TEXT NOT NULL, actual_model TEXT,
                state TEXT NOT NULL, started_utc TEXT NOT NULL, ended_utc TEXT,
                response_date TEXT, raw TEXT, result TEXT, reason TEXT, transport TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS cache ON calls(prompt_hash, actual_model, state);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        self.db.commit()

    def close(self):
        self.db.close()

    def set(self, key, value):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, canonical(value)))

    def get(self, key, default=None):
        row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def recover(self):
        with self.db:
            self.db.execute("UPDATE calls SET state='unresolved',reason='Process ended without durable terminal response',ended_utc=? WHERE state='running'", (utc_now(),))

    def cached(self, job, model):
        row = self.db.execute(f"SELECT {CALL_METADATA} FROM calls WHERE prompt_hash=? AND actual_model=? AND state='completed' ORDER BY id DESC LIMIT 1",
                              (job["prompt_hash"], model)).fetchone()
        return self.decode(row)

    def latest_call(self):
        return self.decode(self.db.execute(f"SELECT {CALL_METADATA} FROM calls ORDER BY id DESC LIMIT 1").fetchone())

    def history(self, include_raw=True):
        columns = "*" if include_raw else CALL_METADATA
        rows = [self.decode(row) for row in self.db.execute(f"SELECT {columns} FROM calls ORDER BY id")]
        if not include_raw:
            for row in rows:
                row["raw_artifact"] = {"database": str(self.root / "quality.sqlite"), "table": "calls", "id": row["id"]}
        return rows

    def has_attempt(self, job, model):
        return self.db.execute("SELECT 1 FROM calls WHERE prompt_hash=? AND expected_model=? LIMIT 1", (job["prompt_hash"], model)).fetchone() is not None


    @staticmethod
    def decode(row):
        if row is None:
            return None
        value = dict(row)
        for key in ("raw", "result", "transport"):
            if value.get(key) is not None:
                value[key] = json.loads(value[key])
        return value

    def start(self, job, model, transport):
        with self.db:
            cursor = self.db.execute("INSERT INTO calls(job,input_hash,prompt_hash,expected_model,state,started_utc,transport) VALUES (?,?,?,?,?,?,?)",
                                     (job["id"], job["input_hash"], job["prompt_hash"], model, "running", utc_now(), canonical(transport)))
        return cursor.lastrowid

    def raw(self, call, envelope):
        with self.db:
            self.db.execute("UPDATE calls SET raw=? WHERE id=?", (canonical(envelope), call))

    def finish(self, call, state, envelope=None, result=None, reason=None):
        envelope = envelope or {}
        with self.db:
            self.db.execute("UPDATE calls SET state=?,actual_model=?,response_date=?,ended_utc=?,result=?,reason=? WHERE id=?",
                            (state, envelope.get("actual_model"), envelope.get("response_date"), utc_now(),
                             canonical(result) if result is not None else None, reason, call))

