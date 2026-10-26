import json
import threading
import time
from datetime import datetime, timezone

import pytest

from bench.gui_operator_adapter import GuiOperator, read_observation


def observation(pid=123, running=False):
    return {"basis": "actual_visible_gui", "observed_at_utc": datetime.now(timezone.utc).isoformat(), "pid": pid,
            "profile": "VRCS2", "session": "test-session", "evidence": ["safe-gui-state.png"],
            "state": {"microphone": "CABLE Output(VB-Audio Virtual Cable)", "voice_output": False,
                      "osc_host": "127.0.0.1", "osc_port": 19122, "direction": "D1", "running": running}}


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
    state = bridge.call("read_state", {"requested_state": {"osc_port": 9000, "running": True}})
    assert state["osc_port"] == 19122
    assert state["running"] is False
    assert bridge.call("set_direction", {"direction": "D1"})["direction"] == "D1"
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
    assert bridge.call("liveness", {}) == {"alive": False}


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
