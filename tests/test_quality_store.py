from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from bench.quality_store import QualityStore, canonical


ROOT = Path(__file__).resolve().parents[1]
JOB = {"id": "controlled-call", "input_hash": "input-v1", "prompt_hash": "prompt-v1"}
TRANSPORT = {"kind": "synthetic-command", "synthetic": True, "route": "controlled local process"}
ENVELOPE = {"status": "completed", "actual_model": "returned-model-v1",
            "model_identity_evidence": {"synthetic": True, "source": "controlled terminal response"},
            "response_date": "2026-10-20T12:00:00Z", "content": {"value": "안녕하세요 🌍"},
            "raw": {"events": [{"type": "controlled.complete", "text": "안녕하세요 🌍"}]}}


@pytest.fixture
def store(tmp_path):
    value = QualityStore(tmp_path / "calls")
    try:
        yield value
    finally:
        value.close()


def complete(store, job=JOB, expected="requested-alias", actual="returned-model-v1", value="first"):
    envelope = {**ENVELOPE, "actual_model": actual}
    call = store.start(job, expected, TRANSPORT)
    store.raw(call, envelope)
    store.finish(call, "completed", envelope, {"value": value})
    return call


def test_canonical_retains_unicode_sorted_compact_finite_json():
    assert canonical({"z": [True, None, {"한글": "🌍"}], "a": 2}) == '{"a":2,"z":[true,null,{"한글":"🌍"}]}'
    assert canonical({"z": 1, "a": 2}) == canonical({"a": 2, "z": 1})
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            canonical({"nested": [value]})


def test_raw_and_terminal_result_are_durable_independent_commits(tmp_path):
    root = tmp_path / "calls"
    store = QualityStore(root)
    try:
        call = store.start(JOB, "requested-alias", TRANSPORT)
        store.raw(call, ENVELOPE)
        observer = QualityStore(root)
        try:
            running = observer.latest_call()
            assert running["state"] == "running"
            assert running["actual_model"] is None
            assert running["result"] is None
            assert observer.history()[0]["raw"] == ENVELOPE
            assert observer.cached(JOB, "returned-model-v1") is None
        finally:
            observer.close()
        store.finish(call, "completed", ENVELOPE, ENVELOPE["content"])
    finally:
        store.close()
    reopened = QualityStore(root)
    try:
        row = reopened.history()[0]
        assert row["id"] == call
        assert row["job"] == JOB["id"]
        assert row["input_hash"] == JOB["input_hash"]
        assert row["prompt_hash"] == JOB["prompt_hash"]
        assert row["expected_model"] == "requested-alias"
        assert row["actual_model"] == "returned-model-v1"
        assert row["state"] == "completed"
        assert row["response_date"] == ENVELOPE["response_date"]
        assert row["raw"] == ENVELOPE
        assert row["result"] == ENVELOPE["content"]
        assert row["transport"] == TRANSPORT
        assert row["started_utc"] == running["started_utc"]
        assert row["ended_utc"] is not None
        assert row["reason"] is None
        metadata = reopened.history(include_raw=False)
        assert metadata == [{**{key: value for key, value in row.items() if key != "raw"},
                             "raw_artifact": {"database": str(root / "quality.sqlite"), "table": "calls", "id": call}}]
        assert reopened.latest_call() == {key: value for key, value in row.items() if key != "raw"}
    finally:
        reopened.close()


def test_cache_uses_prompt_and_returned_identity_not_requested_alias(store):
    first = complete(store)
    assert store.cached(JOB, "returned-model-v1")["id"] == first
    assert store.cached(JOB, "requested-alias") is None
    assert store.cached(JOB, "returned-model-v2") is None
    assert store.cached({**JOB, "prompt_hash": "changed-context-or-prompt"}, "returned-model-v1") is None
    # Job IDs can differ for byte-identical prompts; the prompt hash, not the queue label, is the binding.
    assert store.cached({**JOB, "id": "same-prompt-other-label"}, "returned-model-v1")["id"] == first
    second = complete(store, expected="another-requested-alias", value="latest")
    before = store.history()
    cached = store.cached(JOB, "returned-model-v1")
    assert cached["id"] == second
    assert cached["result"] == {"value": "latest"}
    assert "raw" not in cached
    assert store.history() == before
    assert store.has_attempt(JOB, "requested-alias")
    assert store.has_attempt(JOB, "another-requested-alias")
    assert not store.has_attempt(JOB, "returned-model-v1")
    assert not store.has_attempt({**JOB, "prompt_hash": "changed"}, "requested-alias")


@pytest.mark.parametrize("state", ["running", "unresolved", "failed", "quota", "unavailable"])
def test_noncompleted_attempts_never_replace_successful_cache(store, state):
    completed = complete(store)
    job = {**JOB, "prompt_hash": "only-noncompleted"}
    for candidate in (JOB, job):
        call = store.start(candidate, "requested-alias", TRANSPORT)
        store.raw(call, ENVELOPE)
        if state != "running":
            store.finish(call, state, ENVELOPE, reason="Controlled non-success outcome")
    assert store.cached(JOB, "returned-model-v1")["id"] == completed
    assert store.cached(job, "returned-model-v1") is None
    assert store.has_attempt(job, "requested-alias")
    assert store.latest_call()["state"] == state


def test_completed_without_actual_identity_cannot_hit_requested_model_cache(store):
    call = store.start(JOB, "requested-alias", TRANSPORT)
    store.finish(call, "completed", result={"synthetic": True})
    assert store.cached(JOB, "requested-alias") is None
    assert store.cached(JOB, "returned-model-v1") is None
    assert store.latest_call()["actual_model"] is None
    assert store.has_attempt(JOB, "requested-alias")


def test_abrupt_writer_exit_and_fresh_process_recovery_preserve_attempt_history(tmp_path):
    root = tmp_path / "calls"
    store = QualityStore(root)
    try:
        complete(store)
        original = store.history()[0]
    finally:
        store.close()
    writer = """import json, os, sys
from bench.quality_store import QualityStore
store = QualityStore(sys.argv[1])
call = store.start(json.loads(sys.argv[2]), 'requested-alias', {'synthetic': True})
store.raw(call, {'synthetic': True, 'partial': 'admitted but no terminal response'})
os._exit(19)
"""
    result = subprocess.run([sys.executable, "-B", "-c", writer, str(root), json.dumps(JOB)], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert result.returncode == 19, result.stderr + result.stdout
    store = QualityStore(root)
    try:
        before = store.history()
        assert before[0] == original
        assert before[1]["state"] == "running"
        assert before[1]["ended_utc"] is None
    finally:
        store.close()
    recover = """import json, sys
from bench.quality_store import QualityStore
store = QualityStore(sys.argv[1])
try:
    store.recover()
    print(json.dumps(store.history(), ensure_ascii=False))
finally:
    store.close()
"""
    result = subprocess.run([sys.executable, "-B", "-c", recover, str(root)], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stderr + result.stdout
    recovered = json.loads(result.stdout)
    assert recovered[0] == original
    expected = {**before[1], "state": "unresolved", "ended_utc": recovered[1]["ended_utc"],
                "reason": "Process ended without durable terminal response"}
    assert recovered[1] == expected
    assert recovered[1]["ended_utc"] is not None
    assert recovered[1]["result"] is None
    store = QualityStore(root)
    try:
        store.recover()
        assert store.history() == recovered
        assert store.cached(JOB, "returned-model-v1")["id"] == original["id"]
        assert store.has_attempt(JOB, "requested-alias")
    finally:
        store.close()


def test_settings_and_empty_history_keep_low_level_meaning(store):
    assert store.history() == []
    assert store.history(include_raw=False) == []
    assert store.latest_call() is None
    assert store.cached(JOB, "returned-model-v1") is None
    assert not store.has_attempt(JOB, "requested-alias")
    assert store.get("absent") is None
    assert store.get("absent", {"default": True}) == {"default": True}
    store.set("selection", {"model": "returned-model-v1", "notes": ["한글", None]})
    observer = QualityStore(store.root)
    try:
        assert observer.get("selection") == {"model": "returned-model-v1", "notes": ["한글", None]}
        store.set("selection", {"model": "returned-model-v2"})
        assert observer.get("selection") == {"model": "returned-model-v2"}
        store.set("explicit-null", None)
        assert observer.get("explicit-null", "missing") is None
    finally:
        observer.close()
