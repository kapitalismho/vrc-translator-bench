from __future__ import annotations

import json
import socket
import struct
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path

import pytest

import bench.audio as audio_module
import bench.runner as runner_module
from bench.adapter import OperationalError, ProductError
from bench.audio import ClockPlayback
from bench.osc import decode, encode
from bench.plan import load_plan
from bench.runner import Runner
from bench.storage import Journal, Ledger, atomic_json, digest

REPO = Path(__file__).resolve().parents[1]
ADAPTER = REPO / "tests" / "fixtures" / "controlled_adapter.py"


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def make_plan(root, families=None, kinds=("P1", "T1"), duration=0.12, scenarios=None):
    root.mkdir(parents=True, exist_ok=True)
    families = families or {"P1": "kikitan"}
    profiles = []
    for name, family in families.items():
        scenario = root / f"{name}-scenario.json"
        atomic_json(scenario, (scenarios or {}).get(name, {}))
        log = root / f"{name}.log"
        log.touch()
        profiles.append({"id": name, "adapter": [sys.executable, str(ADAPTER), "--state", str(root / f"{name}-state.json"), "--scenario", str(scenario)],
                         "collector": ({"family": family, "url": "ws://127.0.0.1:18378/"} if family == "kikitan" else
                                       {"family": family, "host": "127.0.0.1", "port": free_port(), "log_path": str(log)}),
                         "routes": {channel: {"output_device": f"synthetic-{name}-{channel}", "input_device": f"synthetic-{name}-{channel}-capture"} for channel in ("self", "peer")},
                         "expected_state": {"voice_output": False}, "metadata": {"model": "configured-test-model", "detected_language": None}})
    episodes = []
    for index, kind in enumerate(kinds):
        roles = {}
        for role in (("A", "B") if kind == "T1" else ("A",)):
            filename = root / f"e{index + 1}-{role}.wav"
            with wave.open(str(filename), "wb") as target:
                target.setnchannels(1)
                target.setsampwidth(2)
                target.setframerate(48000)
                target.writeframes((b"\1\0" if role == "A" else b"\2\0") * round(duration * 48000))
            roles[role] = {"audio": str(filename), "source_language": "en" if role == "A" else "zh",
                           "target_language": "zh" if role == "A" else "en",
                           "speech_intervals": [] if kind == "C1" else [[0, duration if role == "B" or kind != "T1" else duration / 2]]}
        episodes.append({"episode_id": f"e{index + 1}", "kind": kind, "wave": "W1", "language_pair": "en-zh", "profiles": list(families), "roles": roles})
    path = root / "input-plan.json"
    atomic_json(path, {"schema_version": 2, "synthetic": True, "frozen_rule_revision": "synthetic-only", "price_table_version": "not-applicable",
                       "execution_scope": {"kind": "synthetic"}, "profiles": profiles, "episodes": episodes})
    return path


def command(root, plan=None, resume=False):
    args = [sys.executable, "-m", "bench.cli", "run", "--root", str(root / "runs"), "--audio-backend", "clock"]
    return args + (["--resume", "smoke"] if resume else ["--plan", str(plan), "--run-id", "smoke"])


def execute(args, root, label):
    result = subprocess.run(args, cwd=REPO, capture_output=True, text=True, timeout=90)
    (root / f"{label}-stdout.txt").write_text(result.stdout, encoding="utf-8")
    (root / f"{label}-stderr.txt").write_text(result.stderr, encoding="utf-8")
    return result


def report(root):
    return json.loads((root / "runs" / "smoke" / "manifest.json").read_text(encoding="utf-8"))


def wait_until(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            value = predicate()
        except (OSError, ValueError):
            value = None
        if value:
            return value
        time.sleep(0.01)
    raise AssertionError("Expected externally visible state was not reached")


def trace(root, attempt):
    return [json.loads(line) for line in (root / attempt["trace"]).read_text(encoding="utf-8").splitlines()]


class VirtualClock:
    def __init__(self):
        self.now = 10_000_000_000
        self.hooks = []

    def perf_counter_ns(self):
        return self.now

    def sleep(self, seconds):
        self.now += round(seconds * 1e9)
        for hook in self.hooks:
            hook(self.now)


class FakeSink:
    instances = []
    output = False
    continuity_value = True
    fail_at = None

    def __init__(self, root, run_id, session, profiles):
        self.root, self.session = Path(root), session
        self.lock = threading.RLock()
        self.last_output, self.attempt_last_output = {}, {}
        self.context, self.targets, self.active, self.lifecycle = {}, {}, set(), []
        self.origins = {}
        self.journal = Journal(self.root / f"stream-{session}.tmp")
        self.__class__.instances.append(self)

    def attach(self, profile, context, journal):
        self.context[profile], self.targets[profile] = context, journal
        self.attempt_last_output[profile] = None
        self.origins.pop(profile, None)

    def detach(self, profile):
        self.targets.pop(profile, None)

    def start(self, profile):
        self.active.add(profile)
        self.lifecycle.append(("start", profile, runner_module.time.perf_counter_ns()))

    def stop(self, profile):
        if profile in self.active:
            self.lifecycle.append(("stop", profile, runner_module.time.perf_counter_ns()))
        self.active.discard(profile)

    def identity(self, *args):
        pass

    def source(self, profile, value):
        self.origins[profile] = value["playback_dac_start_ns"]
        self.record(value)

    def record(self, value):
        self.journal.append(value)

    def phase(self, profiles, phase, **details):
        for profile in profiles:
            self.context[profile].update(capture_phase=phase, **details)

    def continuity(self, profile):
        return {"continuous": self.continuity_value, "evidence": ["fake collector interval"], "gaps": []}

    def check(self, profile=None):
        now = runner_module.time.perf_counter_ns()
        if self.fail_at is not None and now >= self.fail_at:
            raise OperationalError("synthetic collector disconnected")
        for name in self.active:
            if (self.output and self.context[name].get("capture_phase") == "input" and self.attempt_last_output[name] is None
                    and name in self.origins and now >= self.origins[name]):
                self.last_output[name] = self.attempt_last_output[name] = now
                channel = next(iter(self.context[name]["roles"]))
                self.targets[name].append({"record": "native_output_event", "input_channel": channel,
                                           "translated_text": "fake translation", "collector_received_monotonic": now, **self.context[name]})

    def close(self):
        return self.journal.finalize()


class FakeAdapter:
    instances = {}
    all_instances = []
    failure = None
    continuous = True
    refuse = False
    bad_reset = False
    start_error = False

    def __init__(self, profile, root, session):
        self.profile = profile["id"]
        self.state = {"running": False}
        self.calls = []
        self.failed = False
        self.log = Journal(Path(root) / f"diagnostic-{self.profile}-{session}.tmp")
        self.__class__.instances[self.profile] = self
        self.__class__.all_instances.append(self)

    def observe(self):
        pass

    def call(self, method, **params):
        self.calls.append((method, params, runner_module.time.perf_counter_ns()))
        if method == "preflight":
            return {"ready": True, "metadata": {"model": "actually-observed-model", "detected_language": None}}
        if method == "reset_session":
            return {"reset": not self.bad_reset, "basis": "fake test reset", "evidence": ["fake generation"]}
        if method == "configure" and not self.refuse:
            self.state.update(params["requested_state"])
        if method == "read_state":
            return dict(self.state)
        if method in ("start", "stop"):
            self.state["running"] = method == "start"
            if method == "start" and self.start_error:
                raise OperationalError("applied before missing start acknowledgement")
            return {"running": self.state["running"]}
        if method == "liveness":
            if self.failure and not self.failed:
                self.failed = True
                raise ProductError(self.failure, "controlled product failure", "shared")
            continuity = {"continuous": self.continuous, "evidence": ["fake independently observed interval"], "gaps": []}
            return {"alive": True, "app_continuity": continuity, "input_continuity": continuity}
        return {}

    def close(self):
        return self.log.finalize()


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    clock = VirtualClock()
    FakeSink.instances, FakeSink.output, FakeSink.continuity_value, FakeSink.fail_at = [], False, True, None
    FakeAdapter.instances, FakeAdapter.failure, FakeAdapter.continuous = {}, None, True
    FakeAdapter.all_instances = []
    FakeAdapter.refuse, FakeAdapter.bad_reset, FakeAdapter.start_error = False, False, False
    monkeypatch.setattr(runner_module, "time", clock)
    monkeypatch.setattr(audio_module, "time", clock)
    monkeypatch.setattr(runner_module, "NativeSink", FakeSink)
    monkeypatch.setattr(runner_module, "Adapter", FakeAdapter)
    def run(path, resume=False, plan=None):
        plan = plan or load_plan(path, "unit")
        root = tmp_path / "unit-run"
        root.mkdir(exist_ok=True)
        runner = Runner(root, plan, plan["synthetic"], resume)
        result = runner.run()
        return root, result
    return clock, run


def test_episode_schema_role_bindings_and_approved_self_exceptions(tmp_path):
    plan = load_plan(make_plan(tmp_path, {"PP": "puripuly", "LT": "vrclt", "K": "kikitan"}), "schema")
    assert "stages" not in plan
    ordinary_peer, ordinary_self, simultaneous, a, b = plan["passes"]
    assert ordinary_peer["profiles"] == ["PP"] and ordinary_peer["roles"]["peer"]["role"] == "A"
    assert ordinary_self["profiles"] == ["LT", "K"] and ordinary_self["roles"]["self"]["source_language"] == "en"
    assert simultaneous["roles"] == {"peer": {"role": "A", "source_language": "en", "target_language": "zh"}, "self": {"role": "B", "source_language": "zh", "target_language": "en"}}
    assert a["episode_id"] == b["episode_id"] == "e2"
    assert a["pass_id"] == "A" and b["pass_id"] == "B"
    assert a["roles"]["self"]["role"] == "A" and b["roles"]["self"]["role"] == "B"
    assert a["common_last_speech_seconds"] == b["common_last_speech_seconds"] == .12
    assert all(item["tail_seconds"] == 15 for item in plan["passes"])


@pytest.mark.parametrize("mutation,match", [
    (lambda p: p.update(schema_version=1, stages=[]), "legacy"),
    (lambda p: p["profiles"][0]["routes"]["self"].pop("output_device"), "explicit output_device"),
    (lambda p: p.update(synthetic=False, execution_scope={"kind": "pilot", "reason": "calibration negative test"}), "absent offset is not zero"),
    (lambda p: p["episodes"][1]["roles"]["B"].update(source_language="en"), "fixed directions"),
    (lambda p: p["episodes"][1]["roles"]["B"].update(audio=p["episodes"][0]["roles"]["A"]["audio"], speech_intervals=[[0, 1]]), "within the common timeline"),
])
def test_plan_rejects_legacy_and_unproven_inputs(tmp_path, mutation, match):
    path = make_plan(tmp_path)
    plan = json.loads(path.read_text())
    mutation(plan)
    atomic_json(path, plan)
    with pytest.raises(ValueError, match=match):
        load_plan(path, "invalid")


@pytest.mark.parametrize("family,passes", [("puripuly", 1), ("vrclt", 2), ("kikitan", 2)])
def test_fixed_roles_full_common_horizon_and_reset_only_per_pass(tmp_path, runtime, family, passes):
    clock, run = runtime
    path = make_plan(tmp_path, {"P1": family}, kinds=("T1",), duration=2)
    root, result = run(path)
    assert result["counts"]["done"] == passes
    calls = [call for adapter in FakeAdapter.all_instances if adapter.profile == "P1" for call in adapter.calls]
    assert sum(method == "reset_session" for method, _, _ in calls) == passes
    assert sum(method == "start" for method, _, _ in calls) == passes
    for attempt in result["attempts"]:
        rows = trace(root, attempt)
        detail = json.loads(attempt["detail"])
        assert detail["common_last_speech_seconds"] == 2  # A's own speech ends at 1, still waits for original B.
        assert detail["observation_end_ns"] >= detail["observation_deadline_ns"]
        for source in (row for row in rows if row.get("record") == "source_playback"):
            assert detail["role_horizons_ns"][source["input_channel"]] == source["playback_dac_start_ns"] + 17_000_000_000
            assert source["input_origin_ns"] is None and not source["actual_dac_observed"]
            assert source["capture_phase"] == "input"
        assert attempt["checksum"] == digest(root / attempt["trace"])
        assert not detail["opportunity_established"]
    sink = FakeSink.instances[-1]
    for _, _, stopped in (entry for entry in sink.lifecycle if entry[0] == "stop"):
        assert any(json.loads(a["detail"])["observation_deadline_ns"] <= stopped for a in result["attempts"])
    assert all(work["outcome"] == "unknown_no_output" for work in result["work"])


def test_no_sixty_second_watchdog_and_no_future_failure_filling(tmp_path, runtime):
    _, run = runtime
    path = make_plan(tmp_path, {"P1": "puripuly"}, kinds=("P3", "P1"), duration=90)
    FakeAdapter.failure = "limit"
    plan = load_plan(path, "unit")
    plan["profiles"][0]["quota_scope"] = "shared"
    root, result = run(path, plan=plan)
    assert result["counts"]["product_failure"] == 1
    assert result["counts"]["pending"] == 1 and result["pending_passes"] == [1]
    detail = json.loads(result["attempts"][0]["detail"])
    assert detail["playback"]["peer"]["complete"]
    assert detail["observation_end_ns"] >= detail["playback"]["peer"]["end_ns"] + 15_000_000_000
    assert not detail["opportunity_established"]


@pytest.mark.parametrize("failure", ["collector", "settings", "reset", "start"])
def test_harness_invalidity_stays_invalid_and_cleans_capture(tmp_path, runtime, failure):
    _, run = runtime
    path = make_plan(tmp_path, kinds=("P1",))
    if failure == "collector":
        FakeSink.fail_at = 11_000_000_000
    elif failure == "settings":
        FakeAdapter.refuse = True
    elif failure == "reset":
        FakeAdapter.bad_reset = True
    else:
        FakeAdapter.start_error = True
    with pytest.raises(OperationalError):
        run(path)
    root = tmp_path / "unit-run"
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["counts"]["invalid"] == 1 and manifest["counts"]["product_failure"] == 0
    assert manifest["work"][0]["outcome"] == "invalid"
    assert FakeAdapter.instances["P1"].state["running"] is False


def test_independent_continuity_and_partial_role_output(tmp_path, runtime):
    _, run = runtime
    FakeSink.output = True
    FakeAdapter.continuous = None
    root, result = run(make_plan(tmp_path, {"P1": "puripuly"}, kinds=("T1",)))
    detail = json.loads(result["attempts"][0]["detail"])
    assert detail["continuity_established"] == {"app": False, "input": False, "collector": True}
    assert detail["role_outcomes"]["A"]["status"] == "output_observed"
    assert detail["role_outcomes"]["B"]["status"] == "unknown_no_output"
    assert result["work"][0]["outcome"] == "mixed_role_outcomes"


def test_wave_concurrency_and_model_observations_are_preserved(tmp_path, runtime):
    _, run = runtime
    path = make_plan(tmp_path, {"P1": "puripuly", "P2": "vrct"}, kinds=("T1",))
    root, result = run(path)
    sources = [row for attempt in result["attempts"] for row in trace(root, attempt) if row.get("record") == "source_playback"]
    assert len({row["playback_dac_start_ns"] for row in sources}) == 1
    assert {row["profile"] for row in sources} == {"P1", "P2"}
    metadata = [json.loads(record["detail"])["metadata"] for record in result["records"] if record["kind"] == "profile_metadata"]
    assert all(row["model"] == "actually-observed-model" and row["detected_language"] is None for row in metadata)


def test_trace_finalized_before_terminal_and_attempts_immutable(tmp_path):
    plan = load_plan(make_plan(tmp_path / "input", kinds=("P1",)), "atomic")
    ledger = Ledger(tmp_path)
    try:
        ledger.seed(plan["passes"])
        attempt = ledger.begin(ledger.work(0)[0], False)
        journal = Journal(tmp_path / attempt["trace"])
        journal.append({"partial": True})
        assert ledger.work(0)[0]["state"] == "running"
        filename, checksum = journal.finalize()
        ledger.finish(attempt, "done", None, filename, checksum)
        with pytest.raises(RuntimeError, match="immutable"):
            ledger.finish(attempt, "invalid", "rewrite", filename, checksum)
    finally:
        ledger.close()


def test_osc_bundle_wire_order_and_malformed_rejection():
    packets = [encode("/chatbox/typing", [True]), encode("/chatbox/input", ["translated", True, False])]
    packet = b"#bundle\0" + b"\0" * 8 + b"".join(struct.pack(">I", len(part)) + part for part in packets)
    assert decode(packet) == [("/chatbox/typing", [True]), ("/chatbox/input", ["translated", True, False])]
    with pytest.raises(ValueError):
        decode(packet[:-2])


@pytest.mark.parametrize("kind", ["P1", "T1"])
def test_mixed_family_first_passes_share_one_concurrent_round(tmp_path, runtime, kind):
    _, run = runtime
    path = make_plan(tmp_path, {"PP4": "puripuly", "VRCT3": "vrct", "VRCLT1": "vrclt", "KIKI2": "kikitan"}, kinds=(kind,))
    plan = load_plan(path, "mixed")
    assert len(plan["rounds"]) == (2 if kind == "T1" else 1)
    assert {name for index in plan["rounds"][0]["pass_indices"] for name in plan["passes"][index]["profiles"]} == {"PP4", "VRCT3", "VRCLT1", "KIKI2"}
    root, result = run(path)
    by_profile = {}
    for attempt in result["attempts"]:
        work = next(work for work in result["work"] if work["id"] == attempt["work_id"])
        sources = [row for row in trace(root, attempt) if row.get("record") == "source_playback"]
        by_profile.setdefault(work["profile"], []).append((work["pass_id"], sources))
    origins = {entries[0][1][0]["playback_dac_start_ns"] for entries in by_profile.values()}
    assert len(origins) == 1
    assert by_profile["PP4"][0][1][0]["input_channel"] == "peer"
    assert by_profile["VRCLT1"][0][1][0]["input_channel"] == by_profile["KIKI2"][0][1][0]["input_channel"] == "self"
    if kind == "T1":
        assert len(by_profile["PP4"]) == len(by_profile["VRCT3"]) == 1
        assert [entry[0] for entry in by_profile["KIKI2"]] == ["A", "B"]
        assert by_profile["KIKI2"][1][1][0]["playback_dac_start_ns"] >= next(iter(origins)) + 15_120_000_000


def test_incompatible_role_buffers_on_same_device_are_invalid(tmp_path, runtime):
    _, run = runtime
    path = make_plan(tmp_path, {"PP4": "puripuly", "KIKI2": "kikitan"}, kinds=("T1",))
    plan = json.loads(path.read_text())
    for profile in plan["profiles"]:
        profile["routes"]["self"]["output_device"] = "same-device"
    atomic_json(path, plan)
    with pytest.raises(OperationalError, match="Different role buffers"):
        run(path)


def test_route_audio_length_must_preserve_common_timeline(tmp_path):
    path = make_plan(tmp_path, kinds=("P1", "T1"), duration=1)
    plan = json.loads(path.read_text())
    shorter = Path(plan["episodes"][0]["roles"]["A"]["audio"])
    with wave.open(str(shorter), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(48000)
        target.writeframes(b"\0\0" * 4800)
    plan["episodes"][1]["roles"]["A"].update(audio=str(shorter), speech_intervals=[[0, .1]])
    plan["episodes"] = [plan["episodes"][1]]
    atomic_json(path, plan)
    with pytest.raises(ValueError, match="common timeline"):
        load_plan(path, "length")


def test_main_wave_membership_and_explicit_pilot_subset(tmp_path, monkeypatch):
    import bench.plan as plan_module
    monkeypatch.setattr(plan_module, "_calibration", lambda *args: {"status": "measured", "offset_ns": 0})
    path = make_plan(tmp_path, {"PP4": "puripuly", "KIKI2": "kikitan", "VRCLT1": "vrclt", "VRCT3": "vrct"}, kinds=("P1", "T1"))
    plan = json.loads(path.read_text())
    plan.update(synthetic=False, execution_scope={"kind": "main"})
    atomic_json(path, plan)
    frozen = load_plan(path, "wave")
    assert frozen["wave_catalog"]["sha256"] == digest(REPO / "profiles" / "catalog.json")
    assert len(frozen["rounds"]) == 3
    for profile in ("PP4", "VRCT3"):
        assigned = [item for item in frozen["passes"] if profile in item["profiles"]]
        assert [(item["pass_id"], item["roles"]) for item in assigned] == [
            ("ordinary-peer", {"peer": {"role": "A", "source_language": "en", "target_language": "zh"}}),
            ("simultaneous", {"peer": {"role": "A", "source_language": "en", "target_language": "zh"},
                              "self": {"role": "B", "source_language": "zh", "target_language": "en"}})]
    for profile in ("KIKI2", "VRCLT1"):
        assigned = [item for item in frozen["passes"] if profile in item["profiles"]]
        assert [item["pass_id"] for item in assigned] == ["ordinary-self", "A", "B"]
        assert all(set(item["roles"]) == {"self"} for item in assigned)
        assert [item["roles"]["self"]["role"] for item in assigned] == ["A", "A", "B"]
    plan["episodes"][0]["profiles"].remove("KIKI2")
    atomic_json(path, plan)
    with pytest.raises(ValueError, match="exact catalog wave membership"):
        load_plan(path, "invalid-wave")
    plan["execution_scope"] = {"kind": "pilot"}
    atomic_json(path, plan)
    with pytest.raises(ValueError, match="explicit reason"):
        load_plan(path, "invalid-pilot")
    plan["execution_scope"]["reason"] = "bounded route check, not concurrent-wave admission"
    atomic_json(path, plan)
    assert load_plan(path, "pilot")["execution_scope"]["kind"] == "pilot"


@pytest.mark.parametrize("scope", ["main", "pilot"])
def test_canonical_ids_cannot_change_family_or_measurement_condition(tmp_path, monkeypatch, scope):
    import bench.plan as plan_module
    monkeypatch.setattr(plan_module, "_calibration", lambda *args: {"status": "measured", "offset_ns": 0})
    path = make_plan(tmp_path, {"PP4": "vrclt", "KIKI2": "vrclt", "VRCLT1": "vrclt", "VRCT3": "vrclt"}, kinds=("T1",))
    plan = json.loads(path.read_text())
    plan.update(synthetic=False, execution_scope={"kind": scope, "reason": "bounded family-admission check"})
    atomic_json(path, plan)
    with pytest.raises(ValueError, match="Canonical profile PP4 requires collector.family=puripuly"):
        load_plan(path, "family")
    for profile in plan["profiles"]:
        profile["collector"]["family"] = {"PP4": "puripuly", "KIKI2": "kikitan", "VRCLT1": "vrclt", "VRCT3": "vrct"}[profile["id"]]
        if profile["collector"]["family"] == "kikitan":
            profile["collector"] = {"family": "kikitan", "url": "ws://127.0.0.1:18378/"}
    plan["profiles"][0]["condition"] = {"ordinary_input": "self", "t1_mode": "split_self", "roles": {"A": "self", "B": "self"}}
    atomic_json(path, plan)
    with pytest.raises(ValueError, match="cannot override its approved measurement condition"):
        load_plan(path, "condition")
