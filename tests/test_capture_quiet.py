from __future__ import annotations

import json
import socket
import struct
import subprocess
import threading
from types import SimpleNamespace

import pytest

import bench.runner as runner_module
import bench.osc as osc_module
from bench.osc import Sink, encode
from bench.plan import load_plan
from bench.runner import Runner
from bench.storage import Journal
from test_capture import REPO, command, events, execute, free_port, make_plan, report, wait_until


def quiet_plan(root, scenarios=None, quiet=0.15, maximum=1.2):
    path = make_plan(root, scenarios, durations=(0.12, 0.18), tail=0.08)
    plan = json.loads(path.read_text())
    stage = plan["stages"][1]
    stage.update(kind="nonspeech", quiet_seconds=quiet, quiet_max_wait_seconds=maximum)
    stage.pop("speech_intervals")
    path.write_text(json.dumps(plan))
    return path


def stream_rows(root):
    return [json.loads(line) for path in (root / "runs" / "smoke").glob("stream-*.jsonl")
            for line in path.read_text().splitlines()]


def final_waits(root):
    return [row for row in stream_rows(root) if row.get("record") == "nonspeech_quiet_wait" and row["phase"] == "end"]


def test_delayed_udp_resets_quiet_before_cli_playback_without_restart_or_speech_work(tmp_path):
    scenario = {"chunks": {"c1": {"events": [
        {"delay": 0.04, "address": "/chatbox/input", "args": ["speech-output", True, False]},
        {"delay": 0.27, "address": "/chatbox/input", "args": ["delayed-carryover", True, False]}]},
        "c2": {"events": []}}}
    path = quiet_plan(tmp_path, {"P1": scenario})
    result = execute(command(tmp_path, path), tmp_path, "quiet")
    assert result.returncode == 0, result.stderr
    capture = events(tmp_path)
    late = next(row for row in capture if row["args"][0] == "delayed-carryover")
    wait, = final_waits(tmp_path)
    wait_payload = {key: value for key, value in wait.items() if key != "run"}
    assert late["capture_phase"] == "quiet_precondition"
    assert late["output_classification"] == "unresolved_carryover"
    assert any(source["chunk"] == "c1" for source in late["source_candidate_provenance"])
    assert not any(source["chunk"] == "c2" for source in late["source_candidate_provenance"])
    assert wait["status"] == "achieved" and wait["quiet_precondition_met"] and not wait["timed_out"]
    assert wait["profiles"]["P1"]["last_output_ns"] == late["t_ns"]
    assert wait["end_ns"] - late["t_ns"] >= 150_000_000
    manifest = report(tmp_path)
    measured = [work for work in manifest["work"] if work["kind"] in ("chunk", "repeat", "isolated")]
    assert len(measured) == 1  # Waiting is evidence, never an extra speech stage/denominator.
    assert len(manifest["work"]) == 5
    nonspeech = next(work for work in manifest["work"] if work["kind"] == "nonspeech")
    attempt = next(row for row in manifest["attempts"] if row["work_id"] == nonspeech["id"])
    detail = json.loads(attempt["detail"])
    assert detail["nonspeech_quiet_wait"] == wait_payload
    trace = [json.loads(line) for line in (tmp_path / "runs" / "smoke" / attempt["trace"]).read_text().splitlines()]
    source = next(row for row in trace if row.get("record") == "source_playback")
    assert source["playback_dac_start_ns"] >= wait["end_ns"]
    assert source["quiet_precondition_met"] and not source["unresolved_carryover"]
    assert source["playback_end_ns"] - source["playback_dac_start_ns"] == 180_000_000
    assert any(row.get("record") == "nonspeech_quiet_wait" and row["phase"] == "end" for row in trace)
    assert any(json.loads(row["detail"]) == wait_payload for row in manifest["records"] if row["kind"] == "nonspeech_quiet_wait")
    state = json.loads((tmp_path / "P1-state.json").read_text())
    assert state["starts"] == state["stops"] == 1


def test_timeout_preserves_concurrent_playback_with_group_contamination_and_profile_evidence(tmp_path):
    noisy = {"chunks": {"c1": {"events": [
        {"delay": 0.27, "address": "/chatbox/input", "args": ["carryover-one", True, False]},
        {"delay": 0.37, "address": "/chatbox/input", "args": ["carryover-two", True, False]},
        {"delay": 0.52, "address": "/chatbox/input", "args": ["unresolved-during-nonspeech", True, False]}]},
        "c2": {"events": []}}}
    silent = {"chunks": {"c1": {"events": []}, "c2": {"events": []}}}
    path = quiet_plan(tmp_path, {"P1": noisy, "P2": silent}, quiet=0.2, maximum=0.25)
    result = execute(command(tmp_path, path), tmp_path, "timeout")
    assert result.returncode == 0, result.stderr
    wait, = final_waits(tmp_path)
    assert wait["status"] == "timeout" and wait["timed_out"]
    assert not wait["quiet_precondition_met"] and wait["unresolved_carryover"]
    assert not wait["profiles"]["P1"]["quiet_precondition_met"]
    assert wait["profiles"]["P2"]["quiet_precondition_met"]
    manifest = report(tmp_path)
    nonspeech = [work for work in manifest["work"] if work["kind"] == "nonspeech"]
    assert len(nonspeech) == 2 and all(work["state"] == "done" for work in nonspeech)
    for work in nonspeech:
        attempt = next(row for row in manifest["attempts"] if row["work_id"] == work["id"])
        detail = json.loads(attempt["detail"])
        assert not detail["quiet_precondition_met"] and detail["unresolved_carryover"]
        trace = [json.loads(line) for line in (tmp_path / "runs" / "smoke" / attempt["trace"]).read_text().splitlines()]
        source = next(row for row in trace if row.get("record") == "source_playback")
        assert source["playback_dac_start_ns"] >= wait["end_ns"]
        assert not source["quiet_precondition_met"] and source["unresolved_carryover"]
        assert any(row.get("record") == "playback" for row in trace)
    output = next(row for row in events(tmp_path) if row["args"][0] == "unresolved-during-nonspeech")
    assert output["capture_phase"] == "nonspeech"
    assert not output["quiet_precondition_met"] and output["unresolved_carryover"]


@pytest.mark.parametrize("failure,exit_code,state", [("product", 1, "product_failure"), ("operational", 2, "invalid")])
def test_failure_during_quiet_retains_existing_product_and_operational_semantics(tmp_path, failure, exit_code, state):
    event = {"delay": 0.27}
    event.update({"failure": {"reason": "provider", "message": "quiet provider failure"}} if failure == "product"
                 else {"invalid": "quiet control failure"})
    scenario = {"chunks": {"c1": {"events": [event]}, "c2": {"events": []}}}
    path = quiet_plan(tmp_path, {"P1": scenario}, quiet=0.3, maximum=1.2)
    result = execute(command(tmp_path, path), tmp_path, failure)
    assert result.returncode == exit_code, result.stderr
    manifest = report(tmp_path)
    work = next(row for row in manifest["work"] if row["kind"] == "nonspeech")
    assert work["state"] == state
    attempt = next(row for row in manifest["attempts"] if row["work_id"] == work["id"])
    assert attempt["reason"] == ("provider" if failure == "product" else "quiet control failure")
    trace = [json.loads(line) for line in (tmp_path / "runs" / "smoke" / attempt["trace"]).read_text().splitlines()]
    assert not any(row.get("record") == "source_playback" for row in trace)
    assert final_waits(tmp_path)[0]["status"] == "aborted"


class QuietClock:
    def __init__(self, sink, outputs):
        self.now = 10_000_000_000
        self.started = self.now
        self.sink = sink
        self.outputs = list(outputs)

    def perf_counter_ns(self):
        return self.now

    def sleep(self, seconds):
        self.now += round(seconds * 1e9)
        while self.outputs and self.outputs[0][0] <= self.now - self.started:
            delay, profile = self.outputs.pop(0)
            self.sink.last_output[profile] = self.started + delay


@pytest.mark.parametrize("outputs,expected_wait,status", [
    ([], 15, "achieved"), ([(12, "P1")], 27, "achieved"), ([(12, "P1"), (20, "P2")], 35, "achieved"),
    ([(delay, "P1") for delay in range(14, 120, 14)], 120, "timeout"),
])
def test_full_fifteen_second_window_resets_for_every_profile(tmp_path, monkeypatch, outputs, expected_wait, status):
    recorded = []
    sink = SimpleNamespace(lock=threading.RLock(), last_output={}, check=lambda: None,
                           record=recorded.append, phase=lambda *args, **kwargs: None)
    clock = QuietClock(sink, [(round(delay * 1e9), profile) for delay, profile in outputs])
    monkeypatch.setattr(runner_module, "time", clock)
    runner = Runner(tmp_path, {"synthetic": True, "profiles": [{"id": "P1"}, {"id": "P2"}]}, synthetic=True)
    runner.sink = sink
    journals = [SimpleNamespace(append=lambda row: None) for _ in range(2)]
    runner.open_attempts = {profile: ({"id": index}, journals[index]) for index, profile in enumerate(("P1", "P2"))}
    adapter = SimpleNamespace(observe=lambda: None, call=lambda method: {"alive": True})
    runner.adapters = {"P1": adapter, "P2": adapter}
    starts = []
    player = SimpleNamespace(start=lambda: starts.append(clock.now))
    stage = {"wave": "W1", "direction": "D1", "chunk": "ns", "quiet_seconds": 15, "quiet_max_wait_seconds": 120}
    try:
        result = runner._wait_for_quiet(4, stage, {"P1", "P2"}, player)
        assert result["status"] == status
        assert result["waited_seconds"] == pytest.approx(expected_wait, abs=0.01)
        assert result["quiet_precondition_met"] == (status == "achieved")
        assert result["timed_out"] == result["unresolved_carryover"] == (status == "timeout")
        assert all(profile["quiet_precondition_met"] for profile in result["profiles"].values()) == (status == "achieved")
        assert starts == [result["end_ns"]]
        assert [row["phase"] for row in recorded] == ["start", "end"]
    finally:
        runner.ledger.close()


@pytest.mark.parametrize("fields", [
    {"quiet_seconds": -1, "quiet_max_wait_seconds": 120},
    {"quiet_seconds": float("nan"), "quiet_max_wait_seconds": 120},
    {"quiet_seconds": 15, "quiet_max_wait_seconds": float("inf")},
    {"quiet_seconds": 15, "quiet_max_wait_seconds": 14},
    {"quiet_seconds": 15},
    {"quiet_max_wait_seconds": 120},
    {"quiet_seconds": True, "quiet_max_wait_seconds": 120},
])
def test_quiet_parameters_reject_invalid_or_partial_contract(tmp_path, fields):
    path = quiet_plan(tmp_path)
    plan = json.loads(path.read_text())
    stage = plan["stages"][1]
    stage.pop("quiet_seconds")
    stage.pop("quiet_max_wait_seconds")
    stage.update(fields)
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="quiet"):
        load_plan(path, "invalid-quiet")


def test_quiet_contract_is_opt_in_and_nonspeech_only(tmp_path):
    historical = load_plan(make_plan(tmp_path), "historical")
    assert all("quiet_seconds" not in stage for stage in historical["stages"])
    path = quiet_plan(tmp_path / "wrong-kind", quiet=0, maximum=0)
    assert load_plan(path, "zero")["stages"][-1]["quiet_seconds"] == 0
    plan = json.loads(path.read_text())
    plan["stages"][1]["kind"] = "chunk"
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="nonspeech"):
        load_plan(path, "wrong-kind")


def test_sink_preserves_session_output_across_attach_but_checks_require_fresh_output(tmp_path):
    profile = {"id": "P1", "osc": {"host": "127.0.0.1", "port": free_port()}}
    sink = Sink(tmp_path, "sink-test", "new-session", [profile])
    first = Journal(tmp_path / "first.tmp")
    second = Journal(tmp_path / "second.tmp")
    try:
        sink.attach("P1", {"attempt": 1}, first)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            sender.sendto(encode("/chatbox/input", ["actual nonempty", True, False]), ("127.0.0.1", profile["osc"]["port"]))
            previous = wait_until(lambda: sink.last_output.get("P1"))
            sink.detach("P1")
            sink.attach("P1", {"attempt": 2, "capture_phase": "quiet_precondition"}, second)
            assert sink.last_output["P1"] == previous
            assert sink.attempt_last_output["P1"] is None
            sender.sendto(encode("/chatbox/typing", [True]), ("127.0.0.1", profile["osc"]["port"]))
            sender.sendto(encode("/chatbox/input", ["   ", True, False]), ("127.0.0.1", profile["osc"]["port"]))
            wait_until(lambda: sink.sequence == 3)
            assert sink.last_output["P1"] == previous and sink.attempt_last_output["P1"] is None
    finally:
        sink.close()
        first.finalize()
        second.finalize()
    fresh = Sink(tmp_path, "sink-test", "resumed-session", [profile])
    try:
        assert fresh.last_output == {}  # Never reconstruct monotonic quiet from historical streams.
    finally:
        fresh.close()


@pytest.mark.parametrize("gated", [False, True])
def test_sink_publishes_bundle_in_wire_order_and_keeps_receiving(tmp_path, gated):
    profile = {"id": "P1", "osc": {"host": "127.0.0.1", "port": free_port()}}
    sink = Sink(tmp_path, "bundle-test", "bundle-session", [profile])
    journal = Journal(tmp_path / "attempt.tmp")
    context = {"attempt": 1}
    if gated:
        context.update(capture_phase="nonspeech", quiet_precondition_met=False, unresolved_carryover=True)
    sink.attach("P1", context, journal)
    messages = [encode("/chatbox/typing", [True]), encode("/chatbox/input", ["bundled output", True, False])]
    bundle = b"#bundle\0" + struct.pack(">Q", 1) + b"".join(struct.pack(">I", len(message)) + message for message in messages)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            destination = ("127.0.0.1", profile["osc"]["port"])
            sender.sendto(bundle, destination)
            bundled_output = wait_until(lambda: sink.attempt_last_output.get("P1"))
            sink.check()
            assert sink.sequence == 2 and sink.last_output["P1"] == bundled_output
            sender.sendto(encode("/chatbox/input", ["continued output", True, False]), destination)
            wait_until(lambda: sink.sequence == 3)
            with sink.lock:
                sink.check()
                assert sink.attempt_last_output["P1"] == sink.last_output["P1"] > bundled_output
    finally:
        stream, _ = sink.close()
        trace, _ = journal.finalize()
    rows = [json.loads(line) for line in (tmp_path / stream).read_text().splitlines()]
    assert rows == [json.loads(line) for line in (tmp_path / trace).read_text().splitlines()]
    assert [row["recv_seq"] for row in rows] == [1, 2, 3]
    assert [(row["address"], row["args"][0]) for row in rows] == [
        ("/chatbox/typing", True), ("/chatbox/input", "bundled output"), ("/chatbox/input", "continued output")]
    assert rows[0]["t_ns"] == rows[1]["t_ns"] == bundled_output
    if gated:
        assert all(row["capture_phase"] == "nonspeech" and row["quiet_precondition_met"] is False
                   and row["unresolved_carryover"] is True for row in rows)
    else:
        assert all("capture_phase" not in row and "quiet_precondition_met" not in row for row in rows)


def test_pending_udp_receipt_blocks_admission_then_resets_full_quiet_window(tmp_path, monkeypatch):
    received = threading.Event()
    release = threading.Event()
    admission_attempted = threading.Event()
    blocked = []
    controller_errors = []
    starts = []
    gate_thread = threading.current_thread()
    profile = {"id": "P1", "osc": {"host": "127.0.0.1", "port": free_port()}}

    class Clock:
        now = 10_000_000_000
        sent = False

        def perf_counter_ns(self):
            return self.now

        def sleep(self, seconds):
            self.now += round(seconds * 1e9)
            if not self.sent and self.now >= 24_000_000_000:
                self.sent = True
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                    sender.sendto(encode("/chatbox/input", ["pending carryover", True, False]),
                                  ("127.0.0.1", profile["osc"]["port"]))
                assert received.wait(2), "Receiver did not reach the post-recv clock sample"
                self.now = 25_000_000_000

    clock = Clock()

    def receipt_time():
        stamp = clock.now
        received.set()
        assert release.wait(5), "Controller did not release pending receipt"
        return stamp

    class AdmissionLock:
        def __init__(self, lock):
            self.lock = lock

        def __enter__(self):
            if threading.current_thread() is gate_thread and received.is_set() and not admission_attempted.is_set():
                acquired = self.lock.acquire(blocking=False)
                blocked.append(not acquired)
                admission_attempted.set()
                if acquired:
                    return self
            self.lock.acquire()
            return self

        def __exit__(self, *args):
            self.lock.release()

    def control_publication():
        try:
            assert admission_attempted.wait(3), "Gate did not attempt admission with receipt pending"
            assert blocked == [True], "Admission overtook an already-received packet"
            assert not starts, "Playback started before pending receipt was published"
        except BaseException as error:
            controller_errors.append(error)
        finally:
            release.set()

    monkeypatch.setattr(osc_module, "time", SimpleNamespace(perf_counter_ns=receipt_time))
    monkeypatch.setattr(runner_module, "time", clock)
    sink = Sink(tmp_path, "pending-test", "receipt-session", [profile])
    sink.lock = AdmissionLock(sink.lock)
    journal = Journal(tmp_path / "attempt.tmp")
    sink.attach("P1", {"attempt": 1, "capture_phase": "quiet_precondition"}, journal)
    runner = Runner(tmp_path, {"synthetic": True, "profiles": [profile]}, synthetic=True)
    runner.sink = sink
    runner.session = "receipt-session"
    runner.open_attempts = {"P1": ({"id": 1}, journal)}
    runner.adapters = {"P1": SimpleNamespace(observe=lambda: None, call=lambda method: {"alive": True})}
    controller = threading.Thread(target=control_publication)
    controller.start()
    try:
        result = runner._wait_for_quiet(0, {"wave": "W1", "direction": "D1", "chunk": "ns",
                                         "quiet_seconds": 15, "quiet_max_wait_seconds": 120}, {"P1"},
                                        SimpleNamespace(start=lambda: starts.append(clock.now)))
        sink.check()
        assert not controller_errors, controller_errors
        assert blocked == [True]
        assert result["status"] == "achieved" and result["quiet_precondition_met"]
        assert result["profiles"]["P1"]["last_output_ns"] == 24_000_000_000
        assert result["profiles"]["P1"]["achieved_quiet_seconds"] == 15
        assert starts == [result["end_ns"]] == [39_000_000_000]
    finally:
        release.set()
        controller.join(5)
        stream, _ = sink.close()
        journal.finalize()
        runner.ledger.close()
    assert not controller.is_alive()
    rows = [json.loads(line) for line in (tmp_path / stream).read_text().splitlines()]
    event, = [row for row in rows if row.get("address") == "/chatbox/input"]
    assert event["t_ns"] == 24_000_000_000
    assert event["capture_phase"] == "quiet_precondition"
    assert event["output_classification"] == "unresolved_carryover"


@pytest.mark.parametrize("reverse_stream_order", [False, True])
def test_resume_reobserves_quiet_in_fresh_process_and_preserves_interruption(tmp_path, reverse_stream_order):
    path = quiet_plan(tmp_path, {"P1": {"chunks": {"c2": {"events": []}}}}, quiet=0.3, maximum=1.2)
    process = subprocess.Popen(command(tmp_path, path), cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        wait_until(lambda: any(row.get("record") == "nonspeech_quiet_wait" and row["phase"] == "start"
                               for file in (tmp_path / "runs" / "smoke").glob("stream-*.tmp")
                               for row in map(json.loads, file.read_text().splitlines())))
        process.terminate()
        process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    resumed = execute(command(tmp_path, resume=True), tmp_path, "resume-quiet")
    assert resumed.returncode == 0, resumed.stderr
    manifest = report(tmp_path)
    interrupted = [attempt for attempt in manifest["attempts"] if attempt["reason"] == "interrupted"]
    assert len(interrupted) == 1
    rows = stream_rows(tmp_path)
    if reverse_stream_order:
        rows.reverse()
    wait, = [row for row in rows if row.get("record") == "nonspeech_quiet_wait"
             and row["phase"] == "end" and row["status"] == "achieved"]
    assert wait["waited_seconds"] >= 0.3
    starts = [row for row in rows if row.get("record") == "nonspeech_quiet_wait" and row["phase"] == "start"]
    assert len(starts) == 2 and starts[0]["clock_session"] != starts[1]["clock_session"]
    original_session, = [row["session"] for row in manifest["session_implementations"] if not row["resumed"]]
    resumed_session, = [row["session"] for row in manifest["session_implementations"] if row["resumed"]]
    assert {row["clock_session"] for row in starts} == {original_session, resumed_session}
    resumed_start = next(row for row in starts if row["clock_session"] == resumed_session)
    assert wait["clock_session"] == resumed_session
    assert wait["start_ns"] == resumed_start["start_ns"]
    resumed_outputs = [row["t_ns"] for row in rows if row.get("clock_session") == resumed_session
                       and row.get("config") == "P1" and row.get("address") == "/chatbox/input"
                       and row.get("args") and isinstance(row["args"][0], str) and row["args"][0].strip()
                       and row["t_ns"] <= wait["end_ns"]]
    assert resumed_outputs
    assert wait["profiles"]["P1"]["last_output_ns"] == max(resumed_outputs)
