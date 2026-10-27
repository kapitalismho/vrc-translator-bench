import json
import threading
import time
from datetime import datetime, timezone

import pytest

from bench.gui_operator_adapter import GuiOperator, read_observation
from test_capture import runtime


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
        reconstructed = GuiOperator(tmp_path, 123, "VRCS2", "test-session", timeout=5)
        assert reconstructed.call("read_state", {})["running"] is True
        assert reconstructed.call("identity", {})["pid"] == 456
        assert reconstructed.call("stop", {})["running"] is False
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


def persisted_successor(tmp_path, monkeypatch):
    tmp_path.mkdir(parents=True, exist_ok=True)
    bridge, alive, identities, successor = restart_fixture(tmp_path, monkeypatch)
    request = {"sequence": 1, "method": "reset_session", "params": {"episode_id": "e1", "pass_id": "A"},
               "pid": 123, "profile": "VRCS2", "session": "test-session", "requested_at_ns": time.perf_counter_ns(),
               "requested_at_utc": datetime.now(timezone.utc).isoformat(), "owned_process": dict(identities[123])}
    fresh = successor(request)
    for filename in ("request-0001.json", "pending.json"):
        (tmp_path / filename).write_text(json.dumps(request))
    path = tmp_path / "successor.json"
    path.write_text(json.dumps(fresh))
    bridge.record(path, 1)
    recorder = GuiOperator(tmp_path, 123, "VRCS2", "test-session", timeout=5)
    start = {"sequence": 2, "method": "start", "params": {}, "pid": 456, "profile": "VRCS2",
             "session": "successor-session", "requested_at_utc": datetime.now(timezone.utc).isoformat()}
    for filename in ("request-0002.json", "pending.json"):
        (tmp_path / filename).write_text(json.dumps(start))
    current = observation(pid=456, running=True)
    current.update(session="successor-session", process_identity=dict(identities[456]))
    path = tmp_path / "started.json"
    path.write_text(json.dumps(current))
    recorder.record(path, 2)
    return alive, identities


@pytest.mark.parametrize("tail_exited", [False, True])
def test_original_argv_recovers_successor_without_owning_reused_predecessor(tmp_path, monkeypatch, tail_exited):
    alive, identities = persisted_successor(tmp_path, monkeypatch)
    alive[123] = True
    identities[123].update(creation_filetime_100ns=999, executable="unrelated-bystander.exe")
    alive[456] = not tail_exited
    queried = []
    def identity(pid):
        queried.append(pid)
        assert pid == 456  # Historical PID123 may now belong to somebody else.
        return dict(identities[pid])
    monkeypatch.setattr("bench.gui_operator_adapter.process_identity", identity)
    fresh = GuiOperator(tmp_path, 123, "VRCS2", "test-session")
    assert (fresh.pid, fresh.session) == (456, "successor-session")
    assert fresh.call("read_state", {})["running"] == (not tail_exited)
    if tail_exited:
        assert fresh.call("stop", {})["running"] is False
        assert fresh.call("identity", {})["process_identity"] is None
        assert not (tmp_path / "request-0003.json").exists() and not queried
    else:
        assert fresh.call("identity", {})["process_identity"] == identities[456]
    assert alive[123] and alive[789]


@pytest.mark.parametrize("invalid", ["missing_transition", "missing_ack", "missing_request", "changed_request",
                                     "changed_birth", "changed_executable", "stale_observation", "unrelated_observation",
                                     "wrong_root", "wrong_profile", "branched_previous", "broken_link",
                                     "ambiguous_ack", "unrelated_argv"])
def test_recovery_rejects_incomplete_unrelated_or_identity_changed_history(tmp_path, monkeypatch, invalid):
    from bench.storage import atomic_json, digest
    alive, identities = persisted_successor(tmp_path, monkeypatch)
    if invalid == "missing_transition":
        (tmp_path / "ownership-0001.json").unlink()
    elif invalid == "missing_ack":
        (tmp_path / "response-0001.json").unlink()
    elif invalid == "missing_request":
        (tmp_path / "request-0001.json").unlink()
    elif invalid == "changed_request":
        path = tmp_path / "request-0001.json"
        value = json.loads(path.read_text())
        value["params"]["episode_id"] = "unrelated"
        atomic_json(path, value)
    elif invalid == "changed_birth":
        identities[456]["creation_filetime_100ns"] += 1
    elif invalid == "changed_executable":
        identities[456]["executable"] = "unrelated.exe"
    elif invalid in ("stale_observation", "unrelated_observation"):
        path = tmp_path / "observation.json"
        value = json.loads(path.read_text())
        if invalid == "stale_observation":
            value["observed_at_utc"] = "2000-01-01T00:00:00+00:00"
        else:
            value["pid"] = 789
        atomic_json(path, value)
    elif invalid in ("wrong_root", "wrong_profile", "branched_previous", "broken_link"):
        path = tmp_path / "ownership-0001.json"
        value = json.loads(path.read_text())
        if invalid == "wrong_root":
            value["directory"] = str(tmp_path / "another-directory")
        elif invalid == "wrong_profile":
            value["profile"] = "unrelated"
        elif invalid == "branched_previous":
            value["anchor"]["pid"] = 789
        else:
            value["previous_transition_sha256"] = "not-the-previous-transition"
        atomic_json(path, value)
        response = tmp_path / "response-0001.json"
        ack = json.loads(response.read_text())
        ack["ownership_sha256"] = digest(path)
        atomic_json(response, ack)
    elif invalid == "ambiguous_ack":
        (tmp_path / "response-9999.json").write_bytes((tmp_path / "response-0001.json").read_bytes())
    pid, session = (789, "unrelated") if invalid == "unrelated_argv" else (123, "test-session")
    with pytest.raises((ValueError, OSError)):
        GuiOperator(tmp_path, pid, "VRCS2", session)
    assert alive[456] and alive[789]


@pytest.mark.parametrize("failed_write", ["ownership-0001.json", "observation.json", "response-0001.json"])
def test_restart_persistence_failure_never_confirms_dead_predecessor_cleanup(tmp_path, monkeypatch, failed_write):
    import bench.gui_operator_adapter as module
    bridge, alive, identities, successor = restart_fixture(tmp_path, monkeypatch)
    request = {"sequence": 1, "method": "reset_session", "params": {"episode_id": "e1", "pass_id": "A"},
               "pid": 123, "profile": "VRCS2", "session": "test-session",
               "requested_at_utc": datetime.now(timezone.utc).isoformat(), "owned_process": dict(identities[123])}
    fresh = successor(request)
    for filename in ("request-0001.json", "pending.json"):
        (tmp_path / filename).write_text(json.dumps(request))
    path = tmp_path / "fresh.json"
    path.write_text(json.dumps(fresh))
    original = module.atomic_json
    def fail(path, value):
        if path.name == failed_write:
            raise OSError("controlled durable write failure")
        return original(path, value)
    monkeypatch.setattr(module, "atomic_json", fail)
    with pytest.raises(OSError, match="controlled durable write failure"):
        bridge.record(path, 1)
    try:
        recovered = GuiOperator(tmp_path, 123, "VRCS2", "test-session")
    except (ValueError, OSError):
        recovered = None
    if recovered is not None:
        with pytest.raises(ValueError, match="pending|unresolved"):
            recovered.call("read_state", {})
        with pytest.raises(ValueError, match="pending|unresolved"):
            recovered.call("stop", {})
    assert alive[456] and alive[789]


def test_multiple_transitions_validate_history_without_querying_reused_predecessors(tmp_path, monkeypatch):
    from bench.gui_operator_adapter import _filetime_utc
    alive, identities = persisted_successor(tmp_path, monkeypatch)
    recorder = GuiOperator(tmp_path, 123, "VRCS2", "test-session")
    request = {"sequence": 3, "method": "reset_session", "params": {"episode_id": "e2", "pass_id": "B"},
               "pid": 456, "profile": "VRCS2", "session": "successor-session",
               "requested_at_utc": datetime.now(timezone.utc).isoformat(), "owned_process": dict(identities[456])}
    alive[456], alive[567] = False, True
    identities[567] = {"pid": 567, "clock": "windows_filetime_utc", "executable": "fixture.exe",
                       "creation_filetime_100ns": _filetime_utc(request["requested_at_utc"]) + 10}
    fresh = observation(pid=567)
    fresh.update(session="second-successor", process_identity=dict(identities[567]))
    fresh["session_reset"] = {"episode_id": "e2", "pass_id": "B", "basis": "verified_application_restart",
                              "evidence": ["second owned replacement"],
                              "successor": {"previous_pid": 456, "previous_session": "successor-session",
                                            "pid": 567, "session": "second-successor", "evidence": ["owned fixture"]}}
    for filename in ("request-0003.json", "pending.json"):
        (tmp_path / filename).write_text(json.dumps(request))
    path = tmp_path / "second-successor.json"
    path.write_text(json.dumps(fresh))
    recorder.record(path, 3)
    for pid in (123, 456):
        alive[pid] = True
        identities[pid].update(executable="unrelated-bystander.exe", creation_filetime_100ns=999)
    def identity(pid):
        assert pid == 567
        return dict(identities[pid])
    monkeypatch.setattr("bench.gui_operator_adapter.process_identity", identity)
    recovered = GuiOperator(tmp_path, 123, "VRCS2", "test-session")
    assert recovered.call("identity", {})["pid"] == 567
    assert alive[123] and alive[456] and alive[789]
    (tmp_path / "ownership-0001.json").unlink()
    with pytest.raises((ValueError, OSError)):
        GuiOperator(tmp_path, 123, "VRCS2", "test-session")


def test_runner_resume_reconciles_persisted_gui_successor_from_original_argv(tmp_path, monkeypatch, runtime):
    import sys
    import bench.runner as runner_module
    from bench.plan import load_plan
    from bench.runner import Runner
    from bench.storage import Journal, Ledger
    from test_capture import make_plan
    operator_root = tmp_path / "operator"
    alive, identities = persisted_successor(operator_root, monkeypatch)
    plan = load_plan(make_plan(tmp_path / "input", {"VRCS2": "vrcs"}, kinds=("P1",)), "resume")
    plan["profiles"][0]["adapter"] = [sys.executable, "-m", "bench.gui_operator_adapter", "--directory", str(operator_root),
                                       "--owned-pid", "123", "--profile", "VRCS2", "--session", "test-session"]
    root = tmp_path / "runner"
    root.mkdir()
    ledger = Ledger(root)
    ledger.seed(plan["passes"])
    attempt = ledger.begin(ledger.work(0)[0], False)
    journal = Journal(root / attempt["trace"])
    journal.append({"record": "prior_completed_synthetic_work"})
    name, checksum = journal.finalize()
    ledger.finish(attempt, "done", None, name, checksum)
    ledger.record("capture_ownership", {"profile": "VRCS2", "owned": True, "reason": "surviving synthetic successor"})
    original = ledger.export(plan)["attempts"]
    ledger.close()
    calls, errors = [], []
    class GuiBackedAdapter:
        def __init__(self, profile, output_root, session):
            argv = profile["adapter"]
            self.bridge = GuiOperator(argv[argv.index("--directory") + 1], int(argv[argv.index("--owned-pid") + 1]),
                                      profile["id"], argv[argv.index("--session") + 1], timeout=5)
            self.log = Journal(output_root / f"diagnostic-{profile['id']}-{session}.tmp")
        def call(self, method, **params):
            calls.append(method)
            return self.bridge.call(method, params)
        def close(self):
            return self.log.finalize()
    monkeypatch.setattr(runner_module, "Adapter", GuiBackedAdapter)
    def acknowledge_stop():
        try:
            request_path = operator_root / "request-0003.json"
            deadline = time.monotonic() + 5
            while not request_path.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            request = json.loads(request_path.read_text())
            assert (request["method"], request["pid"], request["session"]) == ("stop", 456, "successor-session")
            fresh = observation(pid=456, running=False)
            fresh.update(session="successor-session", process_identity=dict(identities[456]))
            path = operator_root / "stopped.json"
            path.write_text(json.dumps(fresh))
            GuiOperator(operator_root, 123, "VRCS2", "test-session").record(path, 3)
        except BaseException as error:
            errors.append(error)
    worker = threading.Thread(target=acknowledge_stop)
    worker.start()
    try:
        report = Runner(root, plan, synthetic=True, resume=True).run()
    finally:
        worker.join(5)
    assert not errors and calls == ["read_state", "stop", "read_state"]
    assert report["attempts"] == original
    ownership = [json.loads(row["detail"]) for row in report["records"] if row["kind"] == "capture_ownership"]
    assert ownership[-1]["owned"] is False
    assert json.loads((operator_root / "observation.json").read_text())["state"]["running"] is False
    assert alive[456] and alive[789]
