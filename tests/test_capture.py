from __future__ import annotations

import json
import socket
import sqlite3
import struct
import subprocess
import sys
import time
import wave
from pathlib import Path

import pytest

from bench.runner import speech_timeout
from bench.osc import decode, encode
from bench.plan import load_plan
from bench.storage import Journal, Ledger, digest


REPO = Path(__file__).resolve().parents[1]
ADAPTER = REPO / "tests" / "fixtures" / "controlled_adapter.py"


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def make_plan(root, scenarios=None, durations=(0.12, 0.12), tail=0.08):
    root.mkdir(parents=True, exist_ok=True)
    scenarios = scenarios or {"P1": {}}
    profiles = []
    for name, scenario in scenarios.items():
        scenario_path = root / f"{name}-scenario.json"
        scenario_path.write_text(json.dumps(scenario), encoding="utf-8")
        port = free_port()
        profiles.append({"id": name, "adapter": [sys.executable, str(ADAPTER), "--state", str(root / f"{name}-state.json"), "--scenario", str(scenario_path)],
                         "quota_scope": "shared" if len(scenarios) > 1 else name,
                         "osc": {"host": "127.0.0.1", "port": port},
                         "expected_state": {"microphone": "CABLE Output (synthetic)", "voice_output": False, "osc_host": "127.0.0.1", "osc_port": port},
                         "metadata": {"version": "synthetic-fixture", "provider": None, "model": None}, "key_aliases": []})
    def audio(name, duration):
        path = root / f"{name}.wav"
        with wave.open(str(path), "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(48000)
            target.writeframes(b"\0\0" * round(duration * 48000))
        return str(path)
    check = {"audio": audio("check", 0.1), "tail_seconds": 0.04}
    stages = [{"kind": "chunk", "wave": "W1", "direction": "D1", "chunk": f"c{index + 1}",
               "audio": audio(f"c{index + 1}", duration), "profiles": list(scenarios), "tail_seconds": tail,
               "speech_intervals": [[0, duration]]} for index, duration in enumerate(durations)]
    plan = {"synthetic": True, "frozen_rule_revision": "test-rules-only", "price_table_version": "not-applicable-synthetic",
            "profiles": profiles, "output_check": check, "stages": stages}
    path = root / "input-plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def command(root, plan=None, resume=False):
    args = [sys.executable, "-m", "bench.cli", "run", "--root", str(root / "runs"), "--audio-backend", "clock"]
    return args + (["--resume", "smoke"] if resume else ["--plan", str(plan), "--run-id", "smoke"])


def execute(args, root, label):
    result = subprocess.run(args, cwd=REPO, capture_output=True, text=True, timeout=30)
    (root / f"{label}-stdout.txt").write_text(result.stdout, encoding="utf-8")
    (root / f"{label}-stderr.txt").write_text(result.stderr, encoding="utf-8")
    return result


def report(root):
    return json.loads((root / "runs" / "smoke" / "manifest.json").read_text(encoding="utf-8"))


def events(root):
    result = []
    for path in (root / "runs" / "smoke").glob("stream-*.jsonl"):
        result.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    return sorted((item for item in result if "recv_seq" in item), key=lambda item: item["recv_seq"])


def wait_until(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            value = predicate()
        except (OSError, ValueError, sqlite3.Error):
            value = None
        if value:
            return value
        time.sleep(0.01)
    raise AssertionError("Expected externally visible state was not reached")


def test_cli_order_tail_cross_chunk_and_durable_status(tmp_path):
    scenario = {"chunks": {"c1": {"events": [
        {"delay": 0.025, "address": "/chatbox/typing", "args": [True]},
        {"delay": 0.04, "address": "/chatbox/input", "args": ["first", True, False]},
        {"delay": 0.16, "address": "/chatbox/input", "args": ["tail", True, False]},
        {"delay": 0.27, "address": "/chatbox/input", "args": ["late-c1", True, False]}]}}}
    plan = make_plan(tmp_path, {"P1": scenario})
    completed = execute(command(tmp_path, plan), tmp_path, "run")
    assert completed.returncode == 0, completed.stderr
    capture = events(tmp_path)
    assert [item["recv_seq"] for item in capture] == list(range(1, len(capture) + 1))
    assert [item["args"][0] for item in capture if item["chunk"] == "c1" and item["address"] == "/chatbox/input"] == ["c1 translation", "first", "tail"]
    late = next(item for item in capture if item["args"][0] == "late-c1")
    assert late["chunk"] == "c2"
    assert any(item["chunk"] == "c1" for item in late["source_candidate_provenance"])
    tail_event = next(item for item in capture if item["args"][0] == "tail")
    source = tail_event["source_candidate_provenance"][-1]
    assert source["playback_end_ns"] < tail_event["t_ns"] < source["observation_end_ns"]
    manifest = report(tmp_path)
    assert manifest["counts"] == {"pending": 0, "running": 0, "done": 5, "product_failure": 0, "invalid": 0}
    assert manifest["plan"]["calibration"]["status"] == "absent"
    assert manifest["plan"]["calibration"]["offset_ns"] is None
    for attempt in manifest["attempts"]:
        path = tmp_path / "runs" / "smoke" / attempt["trace"]
        assert digest(path) == attempt["checksum"]
        assert attempt["end_wall"] and attempt["end_ns"]
    state = json.loads((tmp_path / "P1-state.json").read_text())
    assert state["starts"] == 1
    assert state["stops"] == 1
    status = execute([sys.executable, "-m", "bench.cli", "status", "smoke", "--root", str(tmp_path / "runs")], tmp_path, "status")
    assert status.returncode == 0
    assert json.loads(status.stdout)["estimated_remaining_seconds"] == 0


def test_hard_interruption_resume_preserves_history_and_replays_only_unfinished(tmp_path):
    plan = make_plan(tmp_path, durations=(0.12, 0.7))
    args = command(tmp_path, plan)
    process = subprocess.Popen(args, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        def second_running():
            state = json.loads((tmp_path / "P1-state.json").read_text())
            return state.get("last_stage", {}).get("chunk") == "c2"
        wait_until(second_running)
        time.sleep(0.07)
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
        (tmp_path / "interrupted-stdout.txt").write_text(stdout)
        (tmp_path / "interrupted-stderr.txt").write_text(stderr)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    database = tmp_path / "runs" / "smoke" / "ledger.sqlite"
    with sqlite3.connect(database) as db:
        before = db.execute("SELECT id,state,trace,checksum FROM attempts WHERE state='done' ORDER BY id").fetchall()
        assert db.execute("SELECT COUNT(*) FROM attempts WHERE state='running'").fetchone()[0] == 1
    state_path = tmp_path / "P1-state.json"
    changed_state = json.loads(state_path.read_text())
    changed_state["microphone"] = "wrong-device-after-interruption"
    state_path.write_text(json.dumps(changed_state))
    resumed = execute(command(tmp_path, resume=True), tmp_path, "resume")
    assert resumed.returncode == 0, resumed.stderr
    manifest = report(tmp_path)
    invalid = [item for item in manifest["attempts"] if item["state"] == "invalid"]
    assert len(invalid) == 1 and invalid[0]["reason"] == "interrupted"
    retried = [item for item in manifest["attempts"] if item["work_id"] == invalid[0]["work_id"]]
    assert [item["number"] for item in retried] == [1, 2]
    assert retried[1]["resumed"] == 1 and retried[1]["state"] == "done"
    for identity, state, trace, checksum in before:
        current = next(item for item in manifest["attempts"] if item["id"] == identity)
        assert (current["state"], current["trace"], current["checksum"]) == (state, trace, checksum)
    assert any(item["kind"] == "resume_check" for item in manifest["work"])
    assert manifest["counts"]["pending"] == manifest["counts"]["invalid"] == 0
    capture = events(tmp_path)
    assert any(item.get("stage") == "resume_setup" and item.get("corrected") for item in manifest["application_observations"])
    assert len({item["recv_seq"] for item in capture}) == len(capture)
    assert any(item["source_candidate_provenance"] and len({entry["clock_session"] for entry in item["source_candidate_provenance"]}) > 1 for item in capture)


@pytest.mark.parametrize("reason,starts", [("provider", 1), ("crash", 2)])
def test_product_failure_is_retained_and_only_crash_restarts_next_chunk(tmp_path, reason, starts):
    plan = make_plan(tmp_path, {"P1": {"chunks": {"c1": {"events": [{"delay": 0.04, "failure": {"reason": reason, "message": "controlled failure"}}]}}}})
    result = execute(command(tmp_path, plan), tmp_path, "product")
    assert result.returncode == 1, result.stderr
    manifest = report(tmp_path)
    failures = [item for item in manifest["attempts"] if item["state"] == "product_failure"]
    assert len(failures) == 1 and failures[0]["reason"] == reason
    assert not [item for item in manifest["attempts"] if item["state"] == "invalid"]
    state = json.loads((tmp_path / "P1-state.json").read_text())
    assert state["starts"] == starts
    original = failures[0]
    result = execute(command(tmp_path, resume=True), tmp_path, "product-resume")
    assert result.returncode == 1
    assert next(item for item in report(tmp_path)["attempts"] if item["id"] == original["id"]) == original


def test_quota_propagates_without_replacing_completed_profile_work(tmp_path):
    limit = {"chunks": {"c2": {"events": [{"delay": 0.04, "failure": {"reason": "limit", "scope": "shared", "message": "controlled quota"}}]}}}
    plan = make_plan(tmp_path, {"P1": limit, "P2": {}}, durations=(0.12, 0.12, 0.12))
    result = execute(command(tmp_path, plan), tmp_path, "quota")
    assert result.returncode == 1, result.stderr
    manifest = report(tmp_path)
    for work in manifest["work"]:
        stage = manifest["plan"]["stages"][work["stage"]]
        if stage["kind"] == "chunk":
            assert work["state"] == ("done" if stage["chunk"] == "c1" else "product_failure")
    failed = [item for item in manifest["attempts"] if item["state"] == "product_failure"]
    assert len(failed) == 4 and {item["reason"] for item in failed} == {"limit"}
    assert all(json.loads(item["detail"])["reached_wall"] for item in failed)
    assert not manifest["pending_stages"]


def test_unsupported_is_na_and_settings_mismatch_is_operational_invalid(tmp_path):
    unsupported = tmp_path / "unsupported"
    plan = make_plan(unsupported, {"P1": {"unsupported": ["D1"]}})
    result = execute(command(unsupported, plan), unsupported, "na")
    assert result.returncode == 0
    assert {item["outcome"] for item in report(unsupported)["work"]} == {"N/A"}
    invalid = tmp_path / "invalid"
    plan = make_plan(invalid, {"P1": {"refuse_configuration": True}})
    result = execute(command(invalid, plan), invalid, "invalid")
    assert result.returncode == 2
    manifest = report(invalid)
    assert manifest["counts"]["invalid"] == 1
    assert manifest["counts"]["product_failure"] == 0
    assert "mismatch" in manifest["attempts"][0]["reason"]


def test_typing_never_satisfies_output_check(tmp_path):
    plan = make_plan(tmp_path, {"P1": {"check": {"events": [{"delay": 0.025, "address": "/chatbox/typing", "args": [True]}]}}})
    result = execute(command(tmp_path, plan), tmp_path, "typing")
    assert result.returncode == 2
    assert report(tmp_path)["attempts"][-1]["reason"] == "output_check_no_output"
    assert events(tmp_path)[0]["address"] == "/chatbox/typing"


def test_trace_finalized_before_terminal_state_and_immutable(tmp_path):
    plan_path = make_plan(tmp_path)
    plan = load_plan(plan_path, "atomic")
    root = tmp_path / "ledger"
    root.mkdir()
    ledger = Ledger(root)
    ledger.seed(plan["stages"])
    work = ledger.work(0)[0]
    attempt = ledger.begin(work, False)
    journal = Journal(root / attempt["trace"])
    journal.append({"partial": True})
    assert ledger.work(0)[0]["state"] == "running"
    trace, checksum = journal.finalize()
    assert (root / trace).exists() and not (root / attempt["trace"]).exists()
    ledger.finish(attempt, "done", None, trace, checksum)
    with pytest.raises(RuntimeError, match="immutable"):
        ledger.finish(attempt, "invalid", "not_allowed", trace, checksum)
    ledger.close()


def test_osc_bundle_wire_order_and_malformed_rejection():
    first = encode("/chatbox/typing", [True])
    second = encode("/chatbox/input", ["translated", True, False])
    packet = b"#bundle\0" + b"\0" * 8 + struct.pack(">I", len(first)) + first + struct.pack(">I", len(second)) + second
    assert decode(packet) == [("/chatbox/typing", [True]), ("/chatbox/input", ["translated", True, False])]
    with pytest.raises(ValueError):
        decode(packet[:-2])


def test_real_run_rejects_missing_measured_calibration(tmp_path):
    path = make_plan(tmp_path)
    plan = json.loads(path.read_text())
    plan["synthetic"] = False
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="absent offset is not zero"):
        load_plan(path, "missing-calibration")


def test_shared_wave_resume_never_replays_product_failed_profile(tmp_path):
    scenario = {"chunks": {"c2": {"events": [{"delay": 0.04, "failure": {"reason": "provider", "message": "retained-first-attempt"}}]}}}
    plan = make_plan(tmp_path, {"P1": scenario, "P2": {}}, durations=(0.12, 0.7))
    process = subprocess.Popen(command(tmp_path, plan), cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    database = tmp_path / "runs" / "smoke" / "ledger.sqlite"
    try:
        def partly_finished():
            with sqlite3.connect(database) as db:
                return db.execute("SELECT COUNT(*) FROM attempts WHERE state='product_failure'").fetchone()[0] == 1 and db.execute("SELECT COUNT(*) FROM attempts WHERE state='running'").fetchone()[0] == 1
        wait_until(partly_finished)
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
        (tmp_path / "interrupted-stdout.txt").write_text(stdout)
        (tmp_path / "interrupted-stderr.txt").write_text(stderr)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    with sqlite3.connect(database) as db:
        p1_before = db.execute("SELECT a.id,a.state,a.trace,a.checksum FROM attempts a JOIN work w ON a.work_id=w.id WHERE w.profile='P1' ORDER BY a.id").fetchall()
    result = execute(command(tmp_path, resume=True), tmp_path, "shared-resume")
    assert result.returncode == 1, result.stderr
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT a.id,a.state,a.trace,a.checksum FROM attempts a JOIN work w ON a.work_id=w.id WHERE w.profile='P1' ORDER BY a.id").fetchall() == p1_before
    manifest = report(tmp_path)
    assert not manifest["pending_stages"]
    assert all(work["profile"] == "P2" for work in manifest["work"] if work["kind"] in ("resume_setup", "resume_check"))
    assert json.loads((tmp_path / "P1-state.json").read_text())["starts"] == 1


def test_continuing_speech_timeout_preserves_progress_and_silence():
    second = 1_000_000_000
    assert not speech_timeout(59 * second, 0, 0, [[0, 120]], None)
    assert speech_timeout(60 * second, 0, 0, [[0, 120]], None)
    assert not speech_timeout(61 * second, 0, 0, [[0, 120]], 5 * second)
    assert not speech_timeout(80 * second, 0, 0, [[0, 50], [100, 180]], None)
    assert not speech_timeout(150 * second, 0, 0, [[100, 180]], None)
    assert speech_timeout(161 * second, 0, second, [[100, 180]], None)


def test_stage_kinds_direction_change_and_source_port_fallback(tmp_path):
    scenarios = {"P1": {"source_port": free_port()}, "P2": {"source_port": free_port()}}
    path = make_plan(tmp_path, scenarios, durations=(0.12, 0.12, 0.12))
    plan = json.loads(path.read_text())
    destination = plan["profiles"][0]["osc"]["port"]
    for profile in plan["profiles"]:
        profile["osc"]["port"] = destination
        profile["osc"]["source_port"] = scenarios[profile["id"]]["source_port"]
        profile["expected_state"]["osc_port"] = destination
    plan["stages"][0]["kind"] = "isolated"
    plan["stages"][1]["kind"] = "nonspeech"
    plan["stages"][1].pop("speech_intervals")
    plan["stages"][2]["kind"] = "repeat"
    plan["stages"][2]["direction"] = "D2"
    path.write_text(json.dumps(plan))
    result = execute(command(tmp_path, path), tmp_path, "stages")
    assert result.returncode == 0, result.stderr
    manifest = report(tmp_path)
    assert {"isolated", "nonspeech", "repeat", "direction", "setup", "output_check"} <= {item["kind"] for item in manifest["work"]}
    capture = events(tmp_path)
    assert {item["config"] for item in capture} == {"P1", "P2"}
    assert all(item["source_port"] == scenarios[item["config"]]["source_port"] for item in capture)
    assert any(item["direction"] == "D2" for item in capture)
    assert all(json.loads((tmp_path / f"{profile}-state.json").read_text())["starts"] == 1 for profile in scenarios)


def test_wave_transition_stops_leaving_retains_shared_and_starts_entering(tmp_path):
    late = {"chunks": {"c1": {"events": [
        {"delay": 0.04, "address": "/chatbox/input", "args": ["first-wave", True, False]},
        {"delay": 0.65, "address": "/chatbox/input", "args": ["delayed-first-wave", True, False]}]}}}
    path = make_plan(tmp_path, {"P1": late, "P2": {}, "P3": {}}, durations=(0.12, 0.12, 0.5))
    plan = json.loads(path.read_text())
    plan["stages"][0]["profiles"] = ["P1", "P2"]
    plan["stages"][1]["profiles"] = ["P2"]
    plan["stages"][2]["profiles"] = ["P2", "P3"]
    plan["stages"][2]["wave"] = "W2"
    path.write_text(json.dumps(plan))
    result = execute(command(tmp_path, path), tmp_path, "waves")
    assert result.returncode == 0, result.stderr
    states = {profile: json.loads((tmp_path / f"{profile}-state.json").read_text()) for profile in ("P1", "P2", "P3")}
    assert all(item["starts"] == item["stops"] == 1 for item in states.values())
    first_stop = next(item["t_ns"] for item in states["P1"]["lifecycle"] if item["action"] == "stop")
    entering_start = next(item["t_ns"] for item in states["P3"]["lifecycle"] if item["action"] == "start")
    retained_stop = next(item["t_ns"] for item in states["P2"]["lifecycle"] if item["action"] == "stop")
    assert first_stop < entering_start < retained_stop
    manifest = report(tmp_path)
    transitions = [json.loads(item["detail"]) for item in manifest["records"] if item["kind"] == "wave_enter"]
    assert transitions[-1]["retained"] == ["P2"]
    delayed = next(item for item in events(tmp_path) if item["args"][0] == "delayed-first-wave")
    assert delayed["config"] == "P1" and any(item["chunk"] == "c1" for item in delayed["source_candidate_provenance"])


def test_exited_adapter_is_invalid_and_diagnostics_are_finalized(tmp_path):
    path = make_plan(tmp_path)
    plan = json.loads(path.read_text())
    plan["profiles"][0]["adapter"] = [sys.executable, "-c", "import sys; print('not protocol JSON', flush=True); sys.exit(7)"]
    path.write_text(json.dumps(plan))
    result = execute(command(tmp_path, path), tmp_path, "adapter-exit")
    assert result.returncode == 2
    manifest = report(tmp_path)
    assert manifest["counts"]["invalid"] == 1 and manifest["counts"]["product_failure"] == 0
    diagnostic = next(json.loads(item["detail"]) for item in manifest["records"] if item["kind"] == "diagnostic_artifact")
    assert digest(tmp_path / "runs" / "smoke" / diagnostic["path"]) == diagnostic["sha256"]


def test_resume_preparation_does_not_start_future_wave_early(tmp_path):
    path = make_plan(tmp_path, {"P1": {}, "P2": {}}, durations=(0.7, 0.12))
    plan = json.loads(path.read_text())
    plan["stages"][0]["profiles"] = ["P1"]
    plan["stages"][1]["profiles"] = ["P2"]
    plan["stages"][1]["wave"] = "W2"
    path.write_text(json.dumps(plan))
    process = subprocess.Popen(command(tmp_path, path), cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        def source_running():
            state = json.loads((tmp_path / "P1-state.json").read_text())
            return state.get("last_stage", {}).get("kind") == "chunk"
        wait_until(source_running)
        assert not (tmp_path / "P2-state.json").exists()
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
        (tmp_path / "interrupted-stdout.txt").write_text(stdout)
        (tmp_path / "interrupted-stderr.txt").write_text(stderr)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    resumed = execute(command(tmp_path, resume=True), tmp_path, "wave-resume")
    assert resumed.returncode == 0, resumed.stderr
    first = json.loads((tmp_path / "P1-state.json").read_text())
    second = json.loads((tmp_path / "P2-state.json").read_text())
    stopped = max(item["t_ns"] for item in first["lifecycle"] if item["action"] == "stop")
    started = min(item["t_ns"] for item in second["lifecycle"] if item["action"] == "start")
    assert stopped < started
    manifest = report(tmp_path)
    assert {manifest["plan"]["stages"][work["stage"]]["wave"] for work in manifest["work"] if work["kind"] == "resume_check"} == {"W1", "W2"}
    assert not manifest["pending_stages"]
