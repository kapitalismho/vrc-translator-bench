import json
import threading
import time
from datetime import datetime, timezone

import pytest

from bench.gui_operator_adapter import GuiOperator, read_observation


def observation(pid=123, running=False):
    return {"basis": "actual_visible_gui", "observed_at_utc": datetime.now(timezone.utc).isoformat(), "pid": pid,
            "profile": "VRCS2", "session": "test-session", "evidence": ["safe-gui-state.png"],
            "state": {"voice_output": False, "running": running,
                      "channels": {"peer": {"role": "A", "input_device": "named loopback", "output_device": "named render",
                                            "source_language": "en", "target_language": "zh"}}}}


def save_observation(directory, record):
    (directory / "observation.json").write_text(json.dumps(record), encoding="utf-8")


def test_gui_observation_requires_actual_evidence(tmp_path):
    record = observation()
    record["evidence"] = []
    save_observation(tmp_path, record)
    with pytest.raises(ValueError, match="evidence"):
        read_observation(tmp_path / "observation.json")


def test_bridge_returns_observed_state_not_requested_echo(tmp_path):
    save_observation(tmp_path, observation())
    bridge = GuiOperator(tmp_path, 123, "VRCS2", "test-session")
    state = bridge.call("read_state", {"requested_state": {"voice_output": True, "running": True}})
    assert state["voice_output"] is False
    assert state["channels"]["peer"]["source_language"] == "en"
    assert state["running"] is False
    assert bridge.call("identity", {})["pid"] == 123
    assert not (tmp_path / "request-0001.json").exists()


def test_bridge_rejects_unrelated_instance_and_dead_running_process(tmp_path, monkeypatch):
    save_observation(tmp_path, observation(pid=999))
    bridge = GuiOperator(tmp_path, 123, "VRCS2", "test-session")
    with pytest.raises(ValueError, match="another application"):
        bridge.call("read_state", {})
    save_observation(tmp_path, observation(running=True))
    monkeypatch.setattr("bench.gui_operator_adapter.process_alive", lambda pid: False)
    state = bridge.call("read_state", {})
    assert state["running"] is False
    assert state["metadata"]["observation_valid"] is False
    with pytest.raises(RuntimeError, match="exited"):
        bridge.call("preflight", {})
    health = bridge.call("liveness", {})
    assert health["alive"] is False
    assert health["app_continuity"]["continuous"] is None
    assert health["input_continuity"]["continuous"] is None


def test_stop_needs_independent_stopped_gui_observation(tmp_path, monkeypatch):
    save_observation(tmp_path, observation(running=True))
    monkeypatch.setattr("bench.gui_operator_adapter.process_alive", lambda pid: True)
    bridge = GuiOperator(tmp_path, 123, "VRCS2", "test-session")
    (tmp_path / "response-0001.json").write_text('{"sequence":1}', encoding="utf-8")
    with pytest.raises(ValueError, match="Fresh GUI"):
        bridge.call("stop", {})
    request = json.loads((tmp_path / "request-0001.json").read_text())
    assert request["method"] == "stop"
    def operator_response():
        deadline = time.monotonic() + 5
        while not (tmp_path / "request-0002.json").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        fresh_path = tmp_path / "fresh-observation.json"
        fresh_path.write_text(json.dumps(observation(running=False)), encoding="utf-8")
        bridge.record(fresh_path, 2)
    responder = threading.Thread(target=operator_response)
    responder.start()
    assert bridge.call("stop", {})["running"] is False
    responder.join()


def test_retired_observation_cannot_ready_running_or_rebind_after_external_mutation(tmp_path, monkeypatch):
    save_observation(tmp_path, observation(running=True))
    monkeypatch.setattr("bench.gui_operator_adapter.process_alive", lambda pid: True)
    bridge = GuiOperator(tmp_path, 123, "VRCS2", "test-session")
    assert bridge.call("preflight", {})["ready"] is True
    (tmp_path / "invalidated.json").write_text('{"reason":"actual GUI selected another direction/profile"}', encoding="utf-8")
    with pytest.raises(ValueError, match="retired"):
        bridge.call("read_state", {})
    restarted = GuiOperator(tmp_path, 123, "VRCS2", "test-session")
    with pytest.raises(ValueError, match="retired"):
        restarted.call("preflight", {})
    fresh = tmp_path / "new-observation.json"
    fresh.write_text(json.dumps(observation(running=False)), encoding="utf-8")
    with pytest.raises(ValueError, match="Retired"):
        restarted.record(fresh)
    monkeypatch.setattr("bench.gui_operator_adapter.process_alive", lambda pid: False)
    assert restarted.call("stop", {})["running"] is False
    assert restarted.call("read_state", {})["running"] is False
    assert restarted.call("read_state", {})["metadata"]["observation_valid"] is False


def test_new_conversation_reset_keeps_owned_process_and_session(tmp_path, monkeypatch):
    identity = {"pid": 123, "creation_filetime_100ns": 1, "clock": "windows_filetime_utc", "executable": "fixture.exe"}
    monkeypatch.setattr("bench.gui_operator_adapter.process_alive", lambda pid: pid == 123)
    monkeypatch.setattr("bench.gui_operator_adapter.process_identity", lambda pid: identity)
    save_observation(tmp_path, observation())
    bridge = GuiOperator(tmp_path, 123, "VRCS2", "test-session")
    def respond():
        wait = time.monotonic() + 5
        while not (tmp_path / "request-0001.json").exists() and time.monotonic() < wait:
            time.sleep(.01)
        fresh = observation()
        fresh["session_reset"] = {"episode_id": "e1", "pass_id": "A", "basis": "product_new_conversation", "evidence": ["test-only reset proof"]}
        path = tmp_path / "reset-observation.json"
        path.write_text(json.dumps(fresh))
        bridge.record(path, 1)
    worker = threading.Thread(target=respond)
    worker.start()
    try:
        assert bridge.call("reset_session", {"episode_id": "e1", "pass_id": "A"})["reset"] is True
        assert bridge.call("identity", {})["pid"] == 123 and bridge.session == "test-session"
    finally:
        worker.join(5)


def restart_fixture(tmp_path, monkeypatch):
    from bench.gui_operator_adapter import _filetime_utc
    alive = {123: True, 456: False, 789: True}
    identities = {pid: {"pid": pid, "creation_filetime_100ns": 1, "clock": "windows_filetime_utc", "executable": "fixture.exe"} for pid in alive}
    monkeypatch.setattr("bench.gui_operator_adapter.process_alive", lambda pid: alive.get(pid, False))
    monkeypatch.setattr("bench.gui_operator_adapter.process_identity", lambda pid: dict(identities[pid]))
    save_observation(tmp_path, observation())
    bridge = GuiOperator(tmp_path, 123, "VRCS2", "test-session", timeout=5)
    def successor(request):
        alive[123], alive[456] = False, True
        identities[456]["creation_filetime_100ns"] = _filetime_utc(request["requested_at_utc"]) + 10
        fresh = observation(pid=456)
        fresh["session"] = "successor-session"
        fresh["process_identity"] = dict(identities[456])
        fresh["session_reset"] = {"episode_id": "e1", "pass_id": "A", "basis": "verified_application_restart",
                                  "evidence": ["test-only supported restart"],
                                  "successor": {"previous_pid": 123, "previous_session": "test-session",
                                                "pid": 456, "session": "successor-session", "evidence": ["owned successor fixture"]}}
        return fresh
    return bridge, alive, identities, successor


def test_verified_restart_adopts_successor_for_following_controls(tmp_path, monkeypatch):
    bridge, alive, identities, successor = restart_fixture(tmp_path, monkeypatch)
    requests = []
    errors = []
    def respond():
        try:
            for sequence, method in ((1, "reset_session"), (2, "start"), (3, "stop")):
                path = tmp_path / f"request-{sequence:04d}.json"
                wait = time.monotonic() + 5
                while not path.exists() and time.monotonic() < wait:
                    time.sleep(.01)
                request = json.loads(path.read_text())
                requests.append(request)
                assert request["method"] == method
                if sequence == 1:
                    fresh = successor(request)
                else:
                    assert request["pid"] == 456 and request["session"] == "successor-session"
                    fresh = observation(pid=456, running=method == "start")
                    fresh.update(session="successor-session", process_identity=dict(identities[456]))
                record = tmp_path / f"fresh-{sequence}.json"
                record.write_text(json.dumps(fresh))
                bridge.record(record, sequence)
        except BaseException as error:
            errors.append(error)
    worker = threading.Thread(target=respond)
    worker.start()
    try:
        assert bridge.call("reset_session", {"episode_id": "e1", "pass_id": "A"})["reset"] is True
        assert (bridge.pid, bridge.session) == (456, "successor-session")
        assert bridge.call("identity", {})["process_identity"] == identities[456]
        assert bridge.call("liveness", {})["process_observation"]["pid"] == 456
        assert bridge.call("read_state", {})["metadata"]["observation_valid"] is True
        assert bridge.call("start", {})["running"] is True
        assert bridge.call("stop", {})["running"] is False
    finally:
        worker.join(5)
    assert not errors and len(requests) == 3
    assert not alive[123] and alive[456] and alive[789]  # Bystander remains outside ownership.


@pytest.mark.parametrize("invalid", ["old_alive", "successor_dead", "stale_observation", "preexisting_process",
                                     "wrong_executable", "missing_identity", "identity_mismatch", "wrong_previous",
                                     "wrong_profile", "reused_session", "ambiguous_successor", "same_pid",
                                     "wrong_episode", "wrong_pending", "screen_clear", "restart_without_successor"])
def test_restart_rejects_unowned_stale_or_ambiguous_successor(tmp_path, monkeypatch, invalid):
    bridge, alive, identities, successor = restart_fixture(tmp_path, monkeypatch)
    request = {"sequence": 1, "method": "reset_session", "params": {"episode_id": "e1", "pass_id": "A"},
               "pid": 123, "profile": "VRCS2", "session": "test-session", "requested_at_ns": time.perf_counter_ns(),
               "requested_at_utc": datetime.now(timezone.utc).isoformat(), "owned_process": dict(identities[123])}
    fresh = successor(request)
    if invalid == "old_alive":
        alive[123] = True
    elif invalid == "successor_dead":
        alive[456] = False
    elif invalid == "stale_observation":
        fresh["observed_at_utc"] = "2000-01-01T00:00:00+00:00"
    elif invalid == "preexisting_process":
        identities[456]["creation_filetime_100ns"] = 1
        fresh["process_identity"] = dict(identities[456])
    elif invalid == "wrong_executable":
        identities[456]["executable"] = "unrelated.exe"
        fresh["process_identity"] = dict(identities[456])
    elif invalid == "missing_identity":
        fresh.pop("process_identity")
    elif invalid == "identity_mismatch":
        fresh["process_identity"]["creation_filetime_100ns"] += 1
    elif invalid == "wrong_previous":
        fresh["session_reset"]["successor"]["previous_pid"] = 999
    elif invalid == "wrong_profile":
        fresh["profile"] = "unrelated"
    elif invalid == "reused_session":
        fresh["session"] = fresh["session_reset"]["successor"]["session"] = "test-session"
    elif invalid == "ambiguous_successor":
        fresh["session_reset"]["successor"] = [fresh["session_reset"]["successor"]]
    elif invalid == "same_pid":
        fresh["pid"] = fresh["session_reset"]["successor"]["pid"] = 123
    elif invalid == "wrong_episode":
        fresh["session_reset"]["episode_id"] = "another-episode"
    elif invalid == "screen_clear":
        fresh["session_reset"]["basis"] = "screen_clear"
    elif invalid == "restart_without_successor":
        fresh.update(pid=123, session="test-session")
        fresh["session_reset"].pop("successor")
    for filename in ("request-0001.json", "pending.json"):
        (tmp_path / filename).write_text(json.dumps(request))
    if invalid == "wrong_pending":
        (tmp_path / "pending.json").write_text(json.dumps({**request, "sequence": 2}))
    path = tmp_path / "rejected.json"
    path.write_text(json.dumps(fresh))
    original = (tmp_path / "observation.json").read_bytes()
    with pytest.raises(ValueError):
        bridge.record(path, 1)
    assert (bridge.pid, bridge.session) == (123, "test-session")
    assert (tmp_path / "observation.json").read_bytes() == original
    assert not (tmp_path / "response-0001.json").exists()
