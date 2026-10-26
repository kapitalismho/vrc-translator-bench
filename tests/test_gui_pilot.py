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


@pytest.mark.parametrize("basis,accepted", [("screen_clear", False), ("product_new_conversation", True), ("verified_application_restart", True)])
def test_reset_requires_fresh_genuine_conversation_evidence(tmp_path, monkeypatch, basis, accepted):
    monkeypatch.setattr("bench.gui_operator_adapter.process_alive", lambda pid: True)
    save_observation(tmp_path, observation())
    bridge = GuiOperator(tmp_path, 123, "VRCS2", "test-session")
    def respond():
        wait = time.monotonic() + 5
        while not (tmp_path / "request-0001.json").exists() and time.monotonic() < wait:
            time.sleep(.01)
        fresh = observation()
        fresh["session_reset"] = {"episode_id": "e1", "pass_id": "A", "basis": basis, "evidence": ["test-only reset proof"]}
        path = tmp_path / "reset-observation.json"
        path.write_text(json.dumps(fresh))
        bridge.record(path, 1)
    worker = threading.Thread(target=respond)
    worker.start()
    try:
        if accepted:
            result = bridge.call("reset_session", {"episode_id": "e1", "pass_id": "A"})
            assert result["reset"] is True and result["basis"] == basis
        else:
            with pytest.raises(ValueError, match="screen clear"):
                bridge.call("reset_session", {"episode_id": "e1", "pass_id": "A"})
    finally:
        worker.join(5)
