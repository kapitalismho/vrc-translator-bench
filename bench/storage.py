from __future__ import annotations

import hashlib
import json
import os
import platform
import sqlite3
import time
import threading
from datetime import datetime, timezone
from pathlib import Path


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as target:
        json.dump(value, target, ensure_ascii=False, indent=2, allow_nan=False)
        target.write("\n")
        target.flush()
        os.fsync(target.fileno())
    os.replace(temporary, path)


class Journal:
    def __init__(self, path):
        self.path = Path(path)
        self.file = self.path.open("x", encoding="utf-8", newline="\n")
        self.lock = threading.Lock()

    def append(self, record):
        with self.lock:
            self.file.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            self.file.flush()

    def finalize(self, suffix=".jsonl"):
        with self.lock:
            self.file.flush()
            os.fsync(self.file.fileno())
            self.file.close()
            final = self.path.with_suffix(suffix)
            os.replace(self.path, final)
            return str(final.name), digest(final)


class RunLock:
    def __init__(self, root):
        self.path = Path(root) / "run.lock"
        self.file = None

    def __enter__(self):
        self.file = self.path.open("a+b")
        self.file.seek(0)
        self.file.write(b"0")
        self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError("Run is already owned by another runner") from None
        return self

    def __exit__(self, *args):
        self.file.close()


class Ledger:
    def __init__(self, root):
        self.root = Path(root)
        self.db = sqlite3.connect(self.root / "ledger.sqlite")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS work (
                id INTEGER PRIMARY KEY, pass_index INTEGER NOT NULL, profile TEXT NOT NULL,
                episode_id TEXT NOT NULL, pass_id TEXT NOT NULL, kind TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending', outcome TEXT,
                UNIQUE(pass_index, profile)
            );
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY, work_id INTEGER NOT NULL, number INTEGER NOT NULL,
                state TEXT NOT NULL, reason TEXT, resumed INTEGER NOT NULL,
                start_wall TEXT NOT NULL, end_wall TEXT, start_ns INTEGER NOT NULL,
                end_ns INTEGER, trace TEXT NOT NULL, checksum TEXT, detail TEXT,
                UNIQUE(work_id, number)
            );
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY, wall TEXT NOT NULL, t_ns INTEGER NOT NULL,
                kind TEXT NOT NULL, detail TEXT NOT NULL
            );
        """)

    def seed(self, passes):
        with self.db:
            for index, item in enumerate(passes):
                for profile in item["profiles"]:
                    self.db.execute("INSERT OR IGNORE INTO work(pass_index,profile,episode_id,pass_id,kind) VALUES(?,?,?,?,?)",
                                    (index, profile, item["episode_id"], item["pass_id"], item["kind"]))

    def record(self, kind, detail):
        with self.db:
            self.db.execute("INSERT INTO records(wall,t_ns,kind,detail) VALUES(?,?,?,?)",
                            (utc_now(), time.perf_counter_ns(), kind, json.dumps(detail)))

    def owned_profiles(self):
        owned = set()
        for row in self.db.execute("SELECT kind,detail FROM records WHERE kind IN ('capture_ownership','application_state') ORDER BY id"):
            detail = json.loads(row["detail"])
            profile = detail.get("profile")
            if row["kind"] == "capture_ownership":
                if detail["owned"]:
                    owned.add(profile)
                else:
                    owned.discard(profile)
            elif detail.get("state", {}).get("running") is True:
                owned.add(profile)
        return owned

    def work(self, pass_index):
        return [dict(row) for row in self.db.execute("SELECT * FROM work WHERE pass_index=? ORDER BY id", (pass_index,))]

    def begin(self, work, resumed):
        state = self.db.execute("SELECT state FROM work WHERE id=?", (work["id"],)).fetchone()[0]
        if state not in ("pending", "invalid"):
            raise RuntimeError("Only unfinished or operational-invalid work may be attempted")
        number = self.db.execute("SELECT COALESCE(MAX(number),0)+1 FROM attempts WHERE work_id=?", (work["id"],)).fetchone()[0]
        trace = f"attempt-{work['id']:04d}-{number:03d}.tmp"
        with self.db:
            cursor = self.db.execute("INSERT INTO attempts(work_id,number,state,resumed,start_wall,start_ns,trace) VALUES(?,?,'running',?,?,?,?)",
                                     (work["id"], number, int(resumed), utc_now(), time.perf_counter_ns(), trace))
            self.db.execute("UPDATE work SET state='running',outcome=NULL WHERE id=?", (work["id"],))
        return dict(self.db.execute("SELECT * FROM attempts WHERE id=?", (cursor.lastrowid,)).fetchone())

    def finish(self, attempt, state, reason, trace, checksum, detail=None, outcome=None):
        if not trace.endswith(".jsonl") or not checksum or not (self.root / trace).is_file():
            raise RuntimeError("Finalize a checksummed trace before recording a terminal outcome")
        with self.db:
            changed = self.db.execute("UPDATE attempts SET state=?,reason=?,end_wall=?,end_ns=?,trace=?,checksum=?,detail=? WHERE id=? AND state='running'",
                                      (state, reason, utc_now(), time.perf_counter_ns(), trace, checksum, json.dumps(detail or {}), attempt["id"])).rowcount
            if changed != 1:
                raise RuntimeError("Historical attempt outcomes are immutable")
            self.db.execute("UPDATE work SET state=?,outcome=? WHERE id=?", (state, outcome or state, attempt["work_id"]))

    def recover(self):
        for row in self.db.execute("SELECT * FROM attempts WHERE state='running'").fetchall():
            attempt = dict(row)
            path = self.root / attempt["trace"]
            if path.exists():
                final = path.with_suffix(".interrupted.jsonl")
                os.replace(path, final)
            else:
                candidates = sorted(self.root.glob(path.stem + "*.jsonl"))
                if candidates:
                    final = path.with_suffix(".interrupted.jsonl")
                    if candidates[0] != final:
                        os.replace(candidates[0], final)
                else:
                    final = path.with_suffix(".interrupted.jsonl")
                    with final.open("x", encoding="utf-8") as target:
                        target.flush()
                        os.fsync(target.fileno())
            with final.open("r+b") as recovered:
                os.fsync(recovered.fileno())
            self.finish(attempt, "invalid", "interrupted", final.name, digest(final), {"recovered": True})
        for pattern in ("stream-*.tmp", "diagnostic-*.tmp"):
            for path in self.root.glob(pattern):
                final = path.with_suffix(".interrupted.jsonl")
                os.replace(path, final)
                with final.open("r+b") as recovered:
                    os.fsync(recovered.fileno())
                self.record("interrupted_artifact", {"path": final.name, "sha256": digest(final)})
        self.record("resume", {"reason": "operator_resume"})

    def export(self, plan):
        work = [dict(row) for row in self.db.execute("SELECT * FROM work ORDER BY id")]
        attempts = [dict(row) for row in self.db.execute("SELECT * FROM attempts ORDER BY id")]
        records = [dict(row) for row in self.db.execute("SELECT * FROM records ORDER BY id")]
        remaining = sorted({row["pass_index"] for row in work if row["state"] in ("pending", "running", "invalid")})
        seconds = sum(max(max(plan["passes"][index]["duration_seconds"],
                              plan["passes"][index]["common_last_speech_seconds"] + 15)
                          for index in execution_round["pass_indices"] if index in remaining)
                      for execution_round in plan["rounds"] if set(execution_round["pass_indices"]) & set(remaining))
        counts = {state: sum(row["state"] == state for row in work) for state in ("pending", "running", "done", "product_failure", "invalid")}
        return {"run": plan["run_id"], "counts": counts, "pending_passes": remaining,
                "estimated_remaining_seconds": seconds, "estimate_excludes": "adapter/setup/reset time and future retries",
                "work": work, "attempts": attempts, "records": records}

    def manifest(self, plan):
        report = self.export(plan)
        report.update({"schema_version": 2, "plan": plan, "host": {"cpu": platform.processor(), "os": platform.platform()},
                       "clock": "perf_counter_ns", "updated_wall": utc_now(),
                       "session_implementations": [json.loads(record["detail"]) for record in report["records"]
                                                   if record["kind"] == "session_start"],
                       "application_observations": [json.loads(record["detail"]) for record in report["records"]
                                                    if record["kind"] in ("application_state", "profile_metadata")],
                       "wall_windows": [{"start": item["start_wall"], "end": item["end_wall"], "attempt": item["id"]} for item in report["attempts"]],
                       "streams": [{"path": path.name, "sha256": digest(path)} for path in sorted(self.root.glob("stream-*.jsonl"))]})
        atomic_json(self.root / "manifest.json", report)
        return report

    def close(self):
        self.db.close()
