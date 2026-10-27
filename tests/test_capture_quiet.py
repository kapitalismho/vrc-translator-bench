from __future__ import annotations

import json
import socket
import struct

import pytest

from bench.native import NativeSink
from bench.osc import encode
from bench.plan import load_plan
from bench.storage import Journal, atomic_json
from test_capture import FakeSink, free_port, make_plan, runtime, trace, wait_until


def test_common_quiet_window_restarts_after_each_profiles_output(tmp_path, runtime):
    clock, run = runtime
    path = make_plan(tmp_path, {"P1": "puripuly", "P2": "vrct"}, kinds=("C1",), duration=.2)
    plan = json.loads(path.read_text())
    plan["episodes"][0].update(quiet_seconds=.15, quiet_max_wait_seconds=1)
    atomic_json(path, plan)
    pending = [(10_120_000_000, "P1"), (10_200_000_000, "P2")]
    def output(now):
        while pending and pending[0][0] <= now:
            stamp, profile = pending.pop(0)
            FakeSink.instances[-1].last_output[profile] = stamp
    clock.hooks.append(output)
    root, result = run(path)
    for attempt in result["attempts"]:
        quiet = json.loads(attempt["detail"])["quiet"]
        assert quiet["status"] == "achieved" and quiet["quiet_precondition_met"]
        assert quiet["end_ns"] >= 10_350_000_000
        source = next(row for row in trace(root, attempt) if row.get("record") == "source_playback")
        assert source["scheduled_start_ns"] > quiet["end_ns"]
    assert all(work["outcome"] == "control" for work in result["work"])


def test_quiet_timeout_retains_contamination_not_fake_success(tmp_path, runtime):
    clock, run = runtime
    path = make_plan(tmp_path, kinds=("C1",))
    plan = json.loads(path.read_text())
    plan["episodes"][0].update(quiet_seconds=.2, quiet_max_wait_seconds=.25)
    atomic_json(path, plan)
    def output(now):
        sink = FakeSink.instances[-1]
        if now <= 10_250_000_000:
            sink.last_output["P1"] = now
    clock.hooks.append(output)
    _, result = run(path)
    detail = json.loads(result["attempts"][0]["detail"])
    assert detail["quiet"]["status"] == "timeout"
    assert detail["quiet"]["unresolved_carryover"] and not detail["opportunity_established"]


@pytest.mark.parametrize("fields", [
    {"quiet_seconds": -1, "quiet_max_wait_seconds": 120},
    {"quiet_seconds": float("nan"), "quiet_max_wait_seconds": 120},
    {"quiet_seconds": 15, "quiet_max_wait_seconds": float("inf")},
    {"quiet_seconds": 15, "quiet_max_wait_seconds": 14},
    {"quiet_seconds": 15}, {"quiet_max_wait_seconds": 120},
    {"quiet_seconds": True, "quiet_max_wait_seconds": 120},
])
def test_quiet_parameters_reject_invalid_or_partial_contract(tmp_path, fields):
    path = make_plan(tmp_path, kinds=("C1",))
    plan = json.loads(path.read_text())
    plan["episodes"][0].update(fields)
    # Input parser must reject non-finite JSON values too, not turn them into timeouts.
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="quiet"):
        load_plan(path, "invalid")


def test_quiet_only_on_c1(tmp_path):
    path = make_plan(tmp_path, kinds=("P1",))
    plan = json.loads(path.read_text())
    plan["episodes"][0].update(quiet_seconds=0, quiet_max_wait_seconds=0)
    atomic_json(path, plan)
    with pytest.raises(ValueError, match="C1"):
        load_plan(path, "invalid")


def test_native_udp_bundle_history_and_fresh_attempt_output(tmp_path):
    log = tmp_path / "crosscheck.log"
    log.touch()
    profile = {"id": "P1", "collector": {"family": "vrclt", "host": "127.0.0.1", "port": free_port(), "log_path": str(log)}}
    sink = NativeSink(tmp_path, "wire-test", "session", [profile])
    first, second = Journal(tmp_path / "first.tmp"), Journal(tmp_path / "second.tmp")
    roles = {"self": {"role": "A", "source_language": "en", "target_language": "zh"}}
    try:
        sink.attach("P1", {"episode_id": "e1", "pass_id": "A", "attempt": 1, "roles": roles, "capture_phase": "input"}, first)
        sink.start("P1")
        packets = [encode("/chatbox/typing", [True]), encode("/chatbox/input", ["actual nonempty", True, False])]
        bundle = b"#bundle\0" + struct.pack(">Q", 1) + b"".join(struct.pack(">I", len(packet)) + packet for packet in packets)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            destination = ("127.0.0.1", profile["collector"]["port"])
            sender.sendto(bundle, destination)
            previous = wait_until(lambda: sink.last_output.get("P1"))
            sink.detach("P1")
            sink.attach("P1", {"episode_id": "e1", "pass_id": "A", "attempt": 2, "roles": roles, "capture_phase": "quiet_precondition"}, second)
            assert sink.last_output["P1"] == previous and sink.attempt_last_output["P1"] is None
            before = sink.sequence
            sender.sendto(encode("/chatbox/typing", [True]), destination)
            sender.sendto(encode("/chatbox/input", ["   ", True, False]), destination)
            wait_until(lambda: sink.sequence >= before + 2)
            sink.check()
            assert sink.last_output["P1"] == previous and sink.attempt_last_output["P1"] is None
    finally:
        filename, _ = sink.close()
        first.finalize()
        second.finalize()
    rows = [json.loads(line) for line in (tmp_path / filename).read_text().splitlines()]
    native = [row for row in rows if row.get("record") == "native_output_event"]
    assert len(native) == 4
    assert [row["stream_sequence"] for row in native] == sorted({row["stream_sequence"] for row in native})
    assert native[0]["collector_received_monotonic"] == native[1]["collector_received_monotonic"]
    assert [row["native_endpoint"] for row in native] == ["/chatbox/typing", "/chatbox/input", "/chatbox/typing", "/chatbox/input"]
    assert native[1]["display_text"] == "actual nonempty" and native[3]["display_text"] == "   "
    assert all(row["input_channel"] == "self" and row["role"] == "A" for row in native)
