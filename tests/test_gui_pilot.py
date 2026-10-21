import json
import wave
import threading
import time
from datetime import datetime, timezone

import pytest

from bench.gui_operator_adapter import GuiOperator, read_observation
from tools.prepare_gui_pilot import prepare, render_slice


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


def test_rendered_slice_copies_source_pcm_without_resynthesis(tmp_path):
    source = tmp_path / "source.wav"
    pcm = bytes(range(256)) * 1500
    with wave.open(str(source), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(48000)
        writer.writeframes(pcm)
    destination = tmp_path / "slice.wav"
    provenance = render_slice(source, destination, 1, 2)
    with wave.open(str(destination), "rb") as reader:
        assert reader.getnframes() == 48000
        assert reader.readframes(48000) == pcm[96000:192000]
    assert provenance["source_start_frame"] == 48000
    assert provenance["source_end_frame"] == 96000
    assert provenance["frames"] == 48000


def test_plan_uses_native_lexical_intervals_and_retains_gaps(tmp_path):
    audio = tmp_path / ".data/english/audio"
    audio.mkdir(parents=True)
    source = audio / "development-01.wav"
    with wave.open(str(source), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(48000)
        writer.writeframes(b"\0\0" * 48000 * 75)
    reference = tmp_path / "corpus/english/timelines"
    reference.mkdir(parents=True)
    words = [{"scored": True, "kind": "w", "punctuation": False, "playback_start": 34 * 48000 + 10080,
              "playback_end": 34 * 48000 + 71520},
             {"scored": True, "kind": "w", "punctuation": False, "playback_start": 48 * 48000,
              "playback_end": 49 * 48000},
             {"scored": False, "kind": "w", "punctuation": False, "playback_start": 40 * 48000,
              "playback_end": 44 * 48000}]
    (reference / "development-01.json").write_text(json.dumps({"words_and_events": words}), encoding="utf-8")
    path = prepare(tmp_path, "VRCS2", 123, 19122)
    plan = json.loads(path.read_text())
    intervals = plan["stages"][0]["speech_intervals"]
    assert intervals[0] == pytest.approx([0.21, 1.49])
    assert intervals[1] == [14, 15]
    assert len(intervals) == 2
    assert plan["profiles"][0]["expected_state"]["osc_port"] == 19122
    assert plan["stages"][0]["tail_seconds"] == 20
    assert plan["stages"][0]["direction"] == "D1"


def test_direction_resume_plan_plays_only_check_and_unscored_silence(tmp_path):
    path = prepare(tmp_path, "VRCS2", 123, 19122, direction="D2", check_only=True)
    plan = json.loads(path.read_text())
    stage = plan["stages"][0]
    assert stage["direction"] == "D2"
    assert stage["kind"] == "nonspeech"
    assert stage["speech_intervals"] == []
    with wave.open(stage["audio"], "rb") as reader:
        assert reader.getnframes() == 48000
        assert reader.readframes(48000) == b"\0\0" * 48000
    assert plan["output_check"]["audio"].endswith("en-output-check.wav")
    provenance = json.loads((path.parent / "provenance.json").read_text())
    assert provenance["scored_source"] is False
    with pytest.raises(ValueError, match="source-matching"):
        prepare(tmp_path, "VRCS2", 123, 19122, direction="D3")


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
