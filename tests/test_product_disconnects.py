"""Controlled app/audio boundaries; real Runner/NativeSink/ledger policy.

No translator, provider, audio device or network listener is started here. The
standalone smoke separately exercises actual local WebSocket transports.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from websockets.exceptions import ConnectionClosedError
from websockets.frames import Close

import bench.adapter as adapter_module
import bench.native as native_module
import bench.runner as runner_module
from bench.adapter import OperationalError, ProductError
from bench.native import NativeSink
from bench.native_transports import WebSocket
from bench.storage import atomic_json, digest
from test_capture import FakeAdapter, make_plan, runtime, trace


def translated_event():
    return {"api_version": "1.0", "event_id": "synthetic-output", "type": "translation.completed",
            "timestamp": "2026-10-27T00:00:00Z", "message_id": "synthetic-turn", "source": "speaker",
            "payload": {"translation": {"text": "受控健康输出", "source_language": "en", "target_language": "zh",
                                        "source_group": {"subtitle_ids": [1], "text": "controlled source"}}}}


class ControlledTransport:
    def __init__(self, sink, profile, config):
        self.sink, self.profile = sink, profile
    def start(self):
        self.sink.ready(self.profile, "controlled_transport")
    def stop(self):
        return None


class Scenario:
    def __init__(self, clock, run, sinks, mode):
        self.clock, self.run, self.sinks, self.mode = clock, run, sinks, mode
        self.fired = self.app_failed = self.controller_failed = False
        self.emitted = set()
        self.reason = "crash"

    @property
    def sink(self):
        return self.sinks[-1]

    def fail(self):
        if self.fired:
            return
        self.fired = True
        self.app_failed = self.mode not in ("uncorroborated", "malformed", "controller_operational")
        self.controller_failed = self.mode == "controller_operational"
        if self.mode == "collector_fault":
            self.sink.failed("FAILED", "ConnectionClosedError")  # class name alone is not transport provenance
        elif self.mode != "malformed":
            self.sink.failed("FAILED", "ConnectionClosedError", transport_disconnected=True)
        if self.mode == "mixed_fault":
            self.sink.failed("FAILED", "OSError")
        if self.mode in ("malformed", "mixed"):
            self.sink.json("FAILED", "kikitan", json.dumps({"method": "recognition", "data": json.dumps({
                "transcription": "source", "translation": "坏模式", "final": 1})}), self.clock.now)

    def advance(self, now):
        for profile, context in list(self.sink.context.items()):
            if context.get("capture_phase") != "input" or not self.sink.history[profile]:
                continue
            source = self.sink.history[profile][-1]
            key = (profile, context["episode_id"])
            if now < source["playback_dac_start_ns"] or key in self.emitted:
                continue
            if profile == "FAILED" and context["episode_id"] == "e1":
                continue
            self.emitted.add(key)
            if profile == "FAILED":
                wire = {"method": "recognition", "data": json.dumps({"transcription": "new source", "translation": "新一轮", "final": False})}
                self.sink.json(profile, "kikitan", json.dumps(wire), now)
            else:
                self.sink.json(profile, "vrcs", json.dumps(translated_event()), now)
        if self.fired or "FAILED" not in self.sink.context or self.sink.context["FAILED"]["episode_id"] != "e1":
            return
        if now >= 10_250_000_000:
            if self.mode == "health_first":
                self.app_failed = True
            elif self.mode not in ("preparation", "final"):
                self.fail()

    def plan(self, root, *, quiet=False, renew=False):
        kinds = ("C1" if quiet else "P1", "P2", "P3") if renew else ("C1" if quiet else "P1", "P2")
        path = make_plan(root / "inputs", {"FAILED": "kikitan", "HEALTHY": "vrcs", "LATER": "vrcs"}, kinds=kinds)
        value = json.loads(path.read_text())
        value["episodes"][0]["profiles"] = ["FAILED", "HEALTHY"]
        value["episodes"][1].update(profiles=["LATER"], wave="W2")
        if quiet:
            value["episodes"][0].update(quiet_seconds=.3, quiet_max_wait_seconds=1)
        if renew:
            value["episodes"][2].update(profiles=["FAILED"], wave="W3")
        atomic_json(path, value)
        return path


@pytest.fixture
def controlled(tmp_path, runtime, monkeypatch):
    clock, run = runtime
    sinks = []
    class TrackingSink(NativeSink):
        def __init__(self, *args):
            super().__init__(*args)
            sinks.append(self)
    monkeypatch.setattr(runner_module, "NativeSink", TrackingSink)
    monkeypatch.setattr(native_module, "WebSocket", ControlledTransport)
    monkeypatch.setattr(native_module, "time", clock)
    monkeypatch.setattr(adapter_module, "time", clock)
    original_call = FakeAdapter.call
    original_record = runner_module.Runner._record
    scenario = Scenario(clock, run, sinks, "socket_first")
    def call(self, method, **params):
        value = original_call(self, method, **params)
        if method == "preflight":
            self.episode = params["episode"]["episode_id"]
        if self.profile == "FAILED" and getattr(self, "episode", None) == "e1":
            if method == "start" and scenario.mode == "preparation":
                scenario.fail()
                self.state["running"] = False
                raise ProductError("crash", "controlled preparation crash")
            if method == "liveness":
                if scenario.mode == "final" and scenario.sink.context["FAILED"]["capture_phase"] == "observation_end":
                    scenario.fail()
                if scenario.controller_failed:
                    raise OperationalError("controlled controller unavailable")
                if scenario.app_failed:
                    self.state["running"] = False
                    raise ProductError(scenario.reason, "controlled application failure", "shared" if scenario.reason == "limit" else None)
        return value
    def record(self, profile, row):
        original_record(self, profile, row)
        if scenario.mode == "health_first" and profile == "FAILED" and row.get("record") == "product_failure_observed":
            scenario.fail()
    monkeypatch.setattr(FakeAdapter, "call", call)
    monkeypatch.setattr(runner_module.Runner, "_record", record)
    clock.hooks.append(scenario.advance)
    return scenario


def assert_healthy(root, attempt):
    detail = json.loads(attempt["detail"])
    assert attempt["state"] == "done"
    assert not detail["product_errors"]
    assert detail["role_outcomes"]["A"]["status"] in ("output_observed", "control")
    assert detail["collector"]["continuous"] is True
    assert all(value["complete"] for value in detail["playback"].values())
    assert detail["observation_end_ns"] >= detail["observation_deadline_ns"]
    assert any(row.get("record") == "native_output_event" for row in trace(root, attempt))


@pytest.mark.parametrize("mode", ["health_first", "socket_first", "preparation", "final"])
def test_confirmed_crash_disconnect_preserves_wave_later_history_and_terminal_attempts(tmp_path, controlled, mode):
    controlled.mode = mode
    path = controlled.plan(tmp_path)
    root, result = controlled.run(path)
    assert result["counts"]["product_failure"] == 1 and result["counts"]["done"] == 2
    assert result["counts"]["invalid"] == 0 and not result["pending_passes"]
    failed, healthy, later = result["attempts"]
    assert failed["state"] == "product_failure" and failed["reason"] == "crash"
    detail = json.loads(failed["detail"])
    assert detail["opportunity_established"] is False
    assert detail["product_errors"][0]["reason"] == "crash"
    assert type(detail["product_errors"][0]["reached_ns"]) is int
    assert detail["product_errors"][0]["reached_wall"]
    assert detail["collector"]["continuous"] is False
    assert all(gap["failure_kind"] == "transport_disconnect" for gap in detail["collector"]["gaps"])
    assert_healthy(root, healthy)
    assert_healthy(root, later)
    if mode == "socket_first":
        observed = [row for row in trace(root, failed) if row.get("record") == "product_failure_observed"]
        assert observed[0]["reached_ns"] < 11_000_000_000  # immediate poll, not the next scheduled health tick
    original = result["attempts"]
    checksums = [digest(root / item["trace"]) for item in original]
    FakeAdapter.instances = {}
    _, resumed = controlled.run(path, resume=True)
    assert resumed["attempts"] == original and not FakeAdapter.instances
    assert [digest(root / item["trace"]) for item in original] == checksums


def test_quiet_boundary_and_same_profile_new_generation_preserve_historical_gap(tmp_path, controlled):
    controlled.mode = "socket_first"
    root, result = controlled.run(controlled.plan(tmp_path, quiet=True, renew=True))
    assert result["counts"]["product_failure"] == 1 and result["counts"]["done"] == 3
    assert result["counts"]["invalid"] == 0
    assert_healthy(root, result["attempts"][1])
    assert_healthy(root, result["attempts"][2])
    fresh = json.loads(result["attempts"][3]["detail"])
    assert result["attempts"][3]["state"] == "done" and not fresh["product_errors"]
    assert fresh["collector"]["generation"] == 2 and fresh["collector"]["gaps"] == []
    assert fresh["role_outcomes"]["A"]["status"] == "output_observed"
    rows = [json.loads(line) for line in next(root.glob("stream-*.jsonl")).read_text(encoding="utf-8").splitlines()]
    assert any(row.get("kind") == "gap" and row["profile"] == "FAILED" and row["generation"] == 1 for row in rows)
    assert json.loads(result["attempts"][0]["detail"])["collector"]["gaps"]  # old evidence not cleared


def test_correlated_quota_failure_keeps_future_shared_work_pending(tmp_path, controlled):
    controlled.reason = "limit"
    path = controlled.plan(tmp_path)
    value = json.loads(path.read_text())
    for profile in value["profiles"]:
        if profile["id"] in ("FAILED", "LATER"):
            profile["quota_scope"] = "shared"
    atomic_json(path, value)
    root, result = controlled.run(path)
    assert result["counts"]["product_failure"] == result["counts"]["done"] == result["counts"]["pending"] == 1
    later, = [work for work in result["work"] if work["profile"] == "LATER"]
    assert result["counts"]["invalid"] == 0 and result["pending_passes"] == [later["pass_index"]]
    assert result["attempts"][0]["reason"] == "limit"
    detail = json.loads(result["attempts"][0]["detail"])
    assert detail["product_errors"][0]["scope"] == "shared"
    assert detail["collector"]["continuous"] is False and detail["collector"]["gaps"]
    assert_healthy(root, result["attempts"][1])
    assert later["state"] == "pending"


@pytest.mark.parametrize("mode,product_observed", [
    ("uncorroborated", False), ("malformed", False), ("mixed", True),
    ("collector_fault", True), ("mixed_fault", True), ("controller_operational", False),
])
def test_independent_instrumentation_stays_invalid_with_observed_product_detail(tmp_path, controlled, mode, product_observed):
    controlled.mode = mode
    with pytest.raises(OperationalError):
        controlled.run(controlled.plan(tmp_path))
    root = tmp_path / "unit-run"
    result = json.loads((root / "manifest.json").read_text())
    assert result["counts"]["invalid"] == 2 and result["counts"]["product_failure"] == 0
    assert result["counts"]["pending"] == 1
    failed = json.loads(result["attempts"][0]["detail"])
    assert bool(failed["product_errors"]) is product_observed
    if product_observed:
        assert failed["product_errors"][0]["reason"] == "crash" and failed["product_errors"][0]["reached_ns"]
    assert failed["collector"]["gaps"] and failed["collector"]["continuous"] is False
    assert failed["opportunity_established"] is False
    assert all(work["outcome"] != "product_no_output" for work in result["work"])


@pytest.mark.parametrize("fault_code", [None, 1007, 1008, 1010])
def test_socket_receive_marks_protocol_fault_separately_from_transport_close(tmp_path, fault_code):
    profile = {"id": "P", "collector": {"family": "kikitan", "url": "ws://127.0.0.1:18378/"}}
    sink = NativeSink(tmp_path, "run", "classification", [profile])
    transport = WebSocket(sink, "P", profile["collector"])
    closed = ConnectionClosedError(None, Close(fault_code, ""), None) if fault_code else ConnectionClosedError(None, None, None)
    class Socket:
        def recv(self, timeout):
            raise closed
    transport.socket = Socket()
    transport.startup_done = threading.Event()
    try:
        transport.thread(transport.receive)
        transport.threads[0].join(timeout=5)
        assert not transport.threads[0].is_alive()
        gap, = sink.continuity("P")["gaps"]
        assert gap["failure_kind"] == ("collector_fault" if fault_code else "transport_disconnect")
    finally:
        sink.close()
