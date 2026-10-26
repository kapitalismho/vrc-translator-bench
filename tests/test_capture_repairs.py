from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import bench.plan as plan_module
import bench.runner as runner_module
from bench.audio import ClockPlayback, Playback
from bench.plan import implementation_provenance, load_plan
from bench.storage import Journal, Ledger, atomic_json, digest
from test_capture import FakeAdapter, FakeSink, REPO, command, execute, make_plan, report, runtime, trace, wait_until

APP = REPO / "tests" / "fixtures" / "persistent_app.py"
CONTROLLER = REPO / "tests" / "fixtures" / "persistent_adapter.py"


class PersistentApplications:
    def __init__(self, root, path):
        self.root, self.path = root, path
        self.processes, self.ports = {}, {}

    def __enter__(self):
        plan = json.loads(self.path.read_text())
        try:
            for profile in plan["profiles"]:
                name = profile["id"]
                with socket.socket() as reservation:
                    reservation.bind(("127.0.0.1", 0))
                    port = reservation.getsockname()[1]
                ready = self.root / f"{name}-ready.json"
                process = subprocess.Popen([sys.executable, str(APP), "--state", str(self.root / f"{name}-state.json"),
                                            "--scenario", str(self.root / f"{name}-scenario.json"), "--ready", str(ready), "--port", str(port)],
                                           cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                self.processes[name], self.ports[name] = process, port
                wait_until(lambda: ready.exists())
                profile["adapter"] = [sys.executable, str(CONTROLLER), "--port", str(port)]
            atomic_json(self.path, plan)
            return self
        except BaseException:
            self.__exit__()
            raise

    def call(self, name, method, **params):
        with socket.create_connection(("127.0.0.1", self.ports[name]), timeout=5) as connection:
            with connection.makefile("rwb") as stream:
                stream.write((json.dumps({"id": 9000, "method": method, "params": params, "controller_pid": 0}) + "\n").encode())
                stream.flush()
                reply = json.loads(stream.readline())
        assert "error" not in reply, reply
        return reply["result"]

    def __exit__(self, *args):
        for name, process in self.processes.items():
            if process.poll() is None:
                try:
                    self.call(name, "shutdown")
                except (OSError, ValueError):
                    process.kill()
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate(timeout=5)
            (self.root / f"{name}-app-stdout.txt").write_text(stdout)
            (self.root / f"{name}-app-stderr.txt").write_text(stderr)


def test_fresh_process_resume_stops_prior_owned_capture_and_replays_only_unfinished(tmp_path):
    path = make_plan(tmp_path, {"P1": "vrclt"}, kinds=("P1",))
    with PersistentApplications(tmp_path, path) as apps:
        process = subprocess.Popen(command(tmp_path, path), cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            wait_until(lambda: apps.call("P1", "read_state").get("last_pass", {}).get("episode_id") == "e1")
            process.terminate()
            process.communicate(timeout=10)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        assert apps.call("P1", "read_state")["running"] is True
        frozen = digest(tmp_path / "runs" / "smoke" / "frozen-plan.json")
        completed = execute(command(tmp_path, resume=True), tmp_path, "resume")
        assert completed.returncode == 0, completed.stderr
        manifest = report(tmp_path)
        assert not manifest["pending_passes"]
        assert [attempt["state"] for attempt in manifest["attempts"]] == ["invalid", "done"]
        assert [attempt["number"] for attempt in manifest["attempts"]] == [1, 2]
        assert manifest["attempts"][0]["reason"] == "interrupted"
        state = apps.call("P1", "read_state")
        assert state["running"] is False and state["starts"] == state["stops"] == state["resets"] == 2
        assert digest(tmp_path / "runs" / "smoke" / "frozen-plan.json") == frozen
        assert len(manifest["session_implementations"]) == 2
        for attempt in manifest["attempts"]:
            assert digest(tmp_path / "runs" / "smoke" / attempt["trace"]) == attempt["checksum"]


@pytest.mark.parametrize("failure", ["start_reply_error", "post_start_state_mismatch"])
def test_actual_independent_fixture_capture_stopped_after_invalidity(tmp_path, failure):
    path = make_plan(tmp_path, {"P1": "vrclt"}, kinds=("P1",), scenarios={"P1": {failure: True}})
    with PersistentApplications(tmp_path, path) as apps:
        result = execute(command(tmp_path, path), tmp_path, failure)
        assert result.returncode == 2
        state = apps.call("P1", "read_state")
        assert state["running"] is False and state["starts"] == state["stops"] == 1
        assert report(tmp_path)["counts"]["invalid"] == 1


def test_resume_never_rewrites_terminal_attempts_or_starts_terminal_profiles(tmp_path, runtime):
    _, run = runtime
    path = make_plan(tmp_path, {"P1": "puripuly", "P2": "vrct"}, kinds=("P1",))
    root, first = run(path)
    old = first["attempts"]
    FakeAdapter.instances = {}
    _, second = run(path, resume=True)
    assert second["attempts"] == old and not FakeAdapter.instances
    assert all(digest(root / attempt["trace"]) == attempt["checksum"] for attempt in old)


@pytest.mark.parametrize("kind", [None, "app", "input", "collector"])
def test_no_output_needs_each_independent_opportunity_axis(tmp_path, runtime, monkeypatch, kind):
    _, run = runtime
    path = make_plan(tmp_path, {"P1": "puripuly"}, kinds=("P1",))
    plan = load_plan(path, "unit")
    plan["synthetic"] = False
    for channel, route in plan["profiles"][0]["routes"].items():
        route["calibration"] = {"status": "measured", "offset_ns": 50_000_000,
                                "devices": {"output": [channel, {"name": route["output_device"]}]}}
    class TestPlayback(ClockPlayback):
        def __init__(self, path, device):
            super().__init__(path, device)
            channel = "self" if device.endswith("self") else "peer"
            self.devices = {"output": [channel, {"name": device}]}
    monkeypatch.setattr(runner_module, "Playback", TestPlayback)
    original = FakeAdapter.call
    def call(self, method, **params):
        result = original(self, method, **params)
        if method == "liveness" and kind in ("app", "input"):
            result[kind + "_continuity"] = {"continuous": None, "evidence": [], "gaps": []}
        return result
    monkeypatch.setattr(FakeAdapter, "call", call)
    if kind == "collector":
        FakeSink.continuity_value = None
    root, result = run(path, plan=plan)
    assert result["work"][0]["outcome"] == ("product_no_output" if kind is None else "unknown_no_output")
    detail = json.loads(result["attempts"][0]["detail"])
    assert detail["opportunity_established"] == (kind is None)
    if kind is None:
        source = next(row for row in trace(root, result["attempts"][0]) if row.get("record") == "source_playback")
        assert detail["role_horizons_ns"]["peer"] == source["playback_dac_start_ns"] + 15_170_000_000


def test_callback_origin_uses_dac_clock_and_scheduled_silence(tmp_path, monkeypatch):
    import numpy as np
    import bench.audio as audio
    path = make_plan(tmp_path, kinds=("P1",), duration=.01)
    source = load_plan(path, "callback")["episodes"][0]["roles"]["A"]
    import wave
    player = object.__new__(Playback)
    player.info = {key: source[key] for key in ("frames", "sample_rate", "channels")}
    player.source = wave.open(source["audio"], "rb")
    player.np = np
    class Stop(Exception):
        pass
    player.sd = SimpleNamespace(CallbackStop=Stop, CallbackAbort=Stop)
    player.first_dac_ns = player.finished_ns = None
    player.scheduled_start_ns = 1_005_000_000
    player.position, player.records = 0, []
    monkeypatch.setattr(audio, "time", SimpleNamespace(perf_counter_ns=lambda: 1_000_000_000))
    output = np.zeros((480, 1), dtype="int16")
    timing = SimpleNamespace(outputBufferDacTime=20, currentTime=20)
    player._render(output, 480, timing, False)
    assert player.records[0]["scheduled_silence_frames"] == 240
    assert player.first_dac_ns == 1_005_000_000
    assert np.all(output[:240] == 0) and np.all(output[240:] == 1)
    assert player.source_time_ns(.005) == 1_010_000_000
    player.source.close()


def test_provenance_uses_loaded_checkout_not_operator_directory(tmp_path, monkeypatch):
    expected = implementation_provenance()
    monkeypatch.chdir(tmp_path)
    assert implementation_provenance() == expected
    assert expected["package_path"] == str(REPO / "bench")
    assert expected["kind"] == "checkout" and expected["revision"] != "unknown"


def test_git_unavailable_is_unknown_not_operator_revision(tmp_path, monkeypatch):
    def unavailable(*args, **kwargs):
        assert kwargs["cwd"] == REPO
        raise FileNotFoundError("isolated test")
    monkeypatch.setattr(plan_module.subprocess, "run", unavailable)
    identity = implementation_provenance()
    assert identity["kind"] == "checkout" and identity["revision"] == "unknown"
    assert identity["revision_reason"] == "git_unavailable"


def test_owned_capture_recovery_and_trace_immutability(tmp_path):
    plan = load_plan(make_plan(tmp_path / "input", kinds=("P1",)), "recovery")
    ledger = Ledger(tmp_path)
    try:
        ledger.seed(plan["passes"])
        ledger.record("capture_ownership", {"profile": "P1", "owned": True})
        attempt = ledger.begin(ledger.work(0)[0], False)
        journal = Journal(tmp_path / attempt["trace"])
        journal.append({"raw": "partial evidence"})
        journal.file.close()  # Simulate an interrupted process leaving its journal.
        ledger.recover()
        assert ledger.owned_profiles() == {"P1"}
        recovered = ledger.export(plan)["attempts"][0]
        assert recovered["state"] == "invalid" and recovered["reason"] == "interrupted"
        assert digest(tmp_path / recovered["trace"]) == recovered["checksum"]
        second = ledger.begin(ledger.work(0)[0], True)
        assert second["number"] == 2 and second["resumed"] == 1
    finally:
        ledger.close()


def test_reconciliation_failure_cleans_all_prior_owners_without_replay(tmp_path, runtime, monkeypatch):
    _, run = runtime
    path = make_plan(tmp_path, {"P1": "puripuly", "P2": "vrct"}, kinds=("P1",))
    root, original = run(path)
    ledger = Ledger(root)
    try:
        for profile in ("P1", "P2"):
            ledger.record("capture_ownership", {"profile": profile, "owned": True, "reason": "simulated surviving app"})
    finally:
        ledger.close()
    old_init, old_call = FakeAdapter.__init__, FakeAdapter.call
    def initialize(self, *args):
        old_init(self, *args)
        self.state["running"] = True
        self.reconcile_failed = False
    def call(self, method, **params):
        if self.profile == "P1" and method == "read_state" and not self.reconcile_failed:
            self.reconcile_failed = True
            raise OperationalError("reconciliation state unavailable")
        return old_call(self, method, **params)
    from bench.adapter import OperationalError
    monkeypatch.setattr(FakeAdapter, "__init__", initialize)
    monkeypatch.setattr(FakeAdapter, "call", call)
    with pytest.raises(OperationalError, match="reconciliation state unavailable"):
        run(path, resume=True)
    assert all(not adapter.state["running"] for adapter in FakeAdapter.instances.values())
    current = json.loads((root / "manifest.json").read_text())
    assert current["attempts"] == original["attempts"]


def test_resume_records_current_implementation_without_replacing_frozen_identity(tmp_path, runtime, monkeypatch):
    _, run = runtime
    path = make_plan(tmp_path, kinds=("P1",))
    frozen = load_plan(path, "unit")
    root, first = run(path, plan=frozen)
    changed = {"kind": "package", "revision": "unknown", "package_version": "test-resume", "sources": {"runner.py": "different"}}
    monkeypatch.setattr(runner_module, "implementation_provenance", lambda: changed)
    _, resumed = run(path, resume=True, plan=frozen)
    assert resumed["attempts"] == first["attempts"]
    sessions = [json.loads(record["detail"]) for record in resumed["records"] if record["kind"] == "session_start"]
    assert sessions[-1]["implementation"] == changed
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["plan"]["harness_revision"] == frozen["harness_revision"]
    assert manifest["plan"]["harness_sources"] == frozen["harness_sources"]


def test_output_receipts_do_not_admit_preparation_future_or_unattributed_text(tmp_path):
    journal = runner_module._AttemptJournal(tmp_path / "bounded.tmp")
    try:
        for timestamp, text in ((90, "startup"), (120, "  "), (210, "late")):
            journal.append({"record": "native_output_event", "capture_phase": "input", "input_channel": "peer",
                            "collector_received_monotonic": timestamp, "translated_text": text})
        assert journal.outputs_between({"peer": (100, 200)}) == (set(), False)
        journal.append({"record": "native_output_event", "capture_phase": "input", "input_channel": "peer",
                        "collector_received_monotonic": 150, "translated_text": "within observation"})
        assert journal.outputs_between({"peer": (100, 200)}) == ({"peer"}, False)
        journal.append({"record": "native_output_event", "capture_phase": "input", "input_channel": None,
                        "collector_received_monotonic": 160, "translated_text": "role unproven"})
        assert journal.outputs_between({"peer": (100, 200)}) == ({"peer"}, True)
    finally:
        journal.finalize()


@pytest.mark.parametrize("phase,observed", [("preparation", False), ("quiet_precondition", False), ("observation_end", False), ("input", True)])
def test_nonmeasurement_native_text_cannot_satisfy_role_output(tmp_path, runtime, monkeypatch, phase, observed):
    clock, run = runtime
    original = FakeSink.check
    injected = set()
    def check(self, profile=None):
        original(self, profile)
        for name in self.active:
            if name not in injected and name in self.origins and clock.now >= self.origins[name]:
                injected.add(name)
                self.attempt_last_output[name] = clock.now  # Even the broad collector counter must not admit it.
                self.targets[name].append({"record": "native_output_event", **self.context[name],
                                           "input_channel": "peer", "capture_phase": phase,
                                           "collector_received_monotonic": clock.now, "translated_text": "phase-specific text"})
    monkeypatch.setattr(FakeSink, "check", check)
    root, result = run(make_plan(tmp_path, {"P1": "puripuly"}, kinds=("P1",)))
    detail = json.loads(result["attempts"][0]["detail"])
    assert detail["role_outcomes"]["A"]["status"] == ("output_observed" if observed else "unknown_no_output")
    raw = [row for row in trace(root, result["attempts"][0]) if row.get("record") == "native_output_event"]
    assert len(raw) == 1 and raw[0]["capture_phase"] == phase and raw[0]["translated_text"] == "phase-specific text"


@pytest.mark.parametrize("shared_scope", [False, True])
def test_preparation_quota_retains_actual_failure_and_leaves_all_unplayed_work_pending(tmp_path, runtime, monkeypatch, shared_scope):
    _, run = runtime
    families = {"P1": "puripuly", "P2": "vrct"} if shared_scope else {"P1": "puripuly"}
    path = make_plan(tmp_path, families, kinds=("P1", "P2"))
    plan = load_plan(path, "unit")
    if shared_scope:
        for profile in plan["profiles"]:
            profile["quota_scope"] = "shared"
    original = FakeAdapter.call
    def call(self, method, **params):
        if self.profile == "P1" and method == "preflight":
            from bench.adapter import ProductError
            raise ProductError("limit", "actual preparation rejection", "shared")
        return original(self, method, **params)
    monkeypatch.setattr(FakeAdapter, "call", call)
    root, result = run(path, plan=plan)
    assert result["counts"]["product_failure"] == 1 and result["counts"]["pending"] == len(families) * 2 - 1
    assert len(result["attempts"]) == 1 and set(FakeAdapter.instances) == {"P1"}
    failure = result["attempts"][0]
    assert failure["reason"] == "limit" and json.loads(failure["detail"])["opportunity"] == "not_played"
    assert not any(row.get("record") == "source_playback" for row in trace(root, failure))
    assert result["work"][0]["outcome"] == "unknown"
    assert all(work["state"] == "pending" for work in result["work"][1:])


@pytest.mark.parametrize("receipt_ns,expected", [(25_700_000_000, "output_observed"), (26_500_000_000, "product_no_output")])
def test_simultaneous_roles_use_common_actual_cutoff_with_independent_origins(tmp_path, runtime, monkeypatch, receipt_ns, expected):
    clock, run = runtime
    path = make_plan(tmp_path, {"P1": "puripuly"}, kinds=("T1",), duration=20)
    plan = load_plan(path, "unit")
    plan["synthetic"] = False
    plan["passes"][0]["common_last_speech_seconds"] = .12
    for source in plan["episodes"][0]["roles"].values():
        source["speech_intervals"] = [[0, .12]]
    for channel, route in plan["profiles"][0]["routes"].items():
        route["calibration"] = {"status": "measured", "offset_ns": 0,
                                "devices": {"output": [channel, {"name": route["output_device"]}]}}
    class SkewedPlayback(ClockPlayback):
        def __init__(self, path, device):
            super().__init__(path, device)
            self.channel = "self" if device.endswith("self") else "peer"
            self.devices = {"output": [self.channel, {"name": device}]}
        def start(self, scheduled_start_ns=None):
            super().start(scheduled_start_ns + (1_000_000_000 if self.channel == "self" else 0))
    monkeypatch.setattr(runner_module, "Playback", SkewedPlayback)
    injected = []
    def output(now):
        if not injected and now >= receipt_ns:
            injected.append(now)
            sink = FakeSink.instances[-1]
            sink.targets["P1"].append({"record": "native_output_event", **sink.context["P1"],
                                      "input_channel": "peer", "collector_received_monotonic": now,
                                      "translated_text": "peer output near common boundary"})
    clock.hooks.append(output)
    root, result = run(path, plan=plan)
    detail = json.loads(result["attempts"][0]["detail"])
    assert detail["role_horizons_ns"] == {"peer": 25_320_000_000, "self": 26_320_000_000}
    assert detail["output_windows_ns"] == {"peer": [10_200_000_000, 26_320_000_000], "self": [11_200_000_000, 26_320_000_000]}
    window, = [row for row in trace(root, result["attempts"][0]) if row.get("record") == "observation_window"]
    assert window["observation_end_ns"] == 26_320_000_000 and window["role_horizons_ns"] == detail["role_horizons_ns"]
    assert detail["role_outcomes"]["A"]["status"] == expected
    assert detail["opportunity_established"] and all(value["complete"] for value in detail["playback"].values())
    native = [row for row in trace(root, result["attempts"][0]) if row.get("record") == "native_output_event"]
    assert len(native) == 1 and native[0]["collector_received_monotonic"] == receipt_ns
