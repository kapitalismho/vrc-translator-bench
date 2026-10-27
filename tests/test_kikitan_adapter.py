"""Controller/transport/Runner consumers against isolated local synthetic hosts.

No installed application, provider, audio device or shared app settings are used.
The Windows process/DPAPI/job implementation is real in subprocess checks.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from bench.adapter import Adapter, OperationalError, ProductError
from bench.kikitan_adapter import KikitanController
from bench.kikitan_runtime import WindowsRuntime
from bench.native import NativeSink
from bench.storage import atomic_json
from test_capture import make_plan, command, execute, report, wait_until, trace, REPO


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Real Windows ownership/DPAPI/process containment")
ENTRY = REPO / "tests" / "fixtures" / "kikitan_controller.py"
BINDING = {"role": "A", "input_device": "synthetic-cable-capture", "output_device": "synthetic-cable-output",
           "source_language": "en", "target_language": "zh"}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    original = {"recognizer": 0, "translator": 0, "source_language": "en", "target_language": "ja",
                "microphone": "synthetic-cable-capture", "desktop_translation": False, "send_user_data": False,
                "send_to_chatbox": True, "speech_to_text_only": False, "disable_when_muted": False,
                "translation_only": False, "send_without_waiting_for_finish": False, "chatbox_wait_per_char_ms": 30,
                "osc_port": 19152, "gemini_api_key": "synthetic-private-key-marker", "unrelated_setting": "untouched"}
    config = tmp_path / "config.json"
    config.write_text(json.dumps(original, indent=3) + "\n", encoding="utf-8")
    original_bytes = config.read_bytes()
    atomic_json(tmp_path / "scenario.json", {})
    monkeypatch.setenv("KIKITAN_FIXTURE_ROOT", str(tmp_path))
    profile = {"id": "KIKI2", "collector": {"family": "kikitan", "url": "ws://127.0.0.1:18378/"},
               "adapter": [sys.executable, str(ENTRY), "--directory", str(tmp_path / "owner"),
                           "--executable", sys._base_executable, "--profile", "KIKI2"], "control_timeout_seconds": 5}
    return tmp_path, profile, original_bytes


def prepare(client, profile, pass_id="ordinary-self"):
    client.call("preflight", profile=profile, episode={}, pass_spec={})
    assert client.call("read_state")["running"] is False
    reset = client.call("reset_session", episode_id="episode", pass_id=pass_id)
    assert reset["reset"] and reset["evidence"]["status"] == 0
    configured = client.call("configure", requested_state={"voice_output": False, "channels": {"self": BINDING}})
    assert configured["channels"]["self"] == BINDING
    assert configured["recognizer"] == configured["translator"] == 2
    return reset


def host_events(root):
    return [json.loads(line) for line in (root / "host.jsonl").read_text(encoding="utf-8").splitlines()]


def test_owned_lifecycle_readback_collector_before_ON_reset_and_exact_restore(setup):
    root, profile, original = setup
    client = Adapter(profile, root, "controller")
    sink = NativeSink(root, "fixture", "native", [profile])
    try:
        first = prepare(client, profile)
        identity = client.call("identity")
        assert first["evidence"]["fresh_initial_instance_reused"] is True
        assert len([r for r in host_events(root) if r["action"] == "ready"]) == 1
        sink.start("KIKI2")
        assert client.call("start")["running"] is True
        assert next(r for r in host_events(root) if r["action"] == "control" and r["data"] == "ON")["clients"] == 2
        health = client.call("liveness")
        assert health["alive"] is True and health["status"] == 2
        assert health["app_continuity"]["continuous"] is health["input_continuity"]["continuous"] is None
        assert client.call("stop")["running"] is False
        sink.stop("KIKI2")
        second = prepare(client, profile, "B")
        replacement = client.call("identity")
        assert (identity["pid"], identity["creation_filetime_100ns"]) != (replacement["pid"], replacement["creation_filetime_100ns"])
        assert second["evidence"]["fresh_initial_instance_reused"] is False
        assert client.call("read_state")["target_language"] == "zh"
    finally:
        sink.close()
        artifact, _ = client.close()
    assert (root / "config.json").read_bytes() == original
    assert not (root / "owner" / "config.dpapi").exists()
    assert not (root / "ownership" / "active.json").exists()
    events = host_events(root)
    assert not any(row["action"] == "unsafe_quit_while_running" for row in events)
    diagnostic = (root / artifact).read_text(encoding="utf-8")
    assert "synthetic-private-key-marker" not in diagnostic and "private-provider-secret-marker" not in diagnostic
    assert WindowsRuntime.__new__(WindowsRuntime).identity(replacement["pid"]) is None


@pytest.mark.parametrize("scenario", ["refuse_configuration", "provider_error", "crash_on_start", "hang_quit"])
def test_readback_rejection_provider_failure_crash_and_cleanup_failure(setup, scenario):
    root, profile, original = setup
    atomic_json(root / "scenario.json", {scenario: True})
    client = Adapter(profile, root, scenario)
    close_error = None
    try:
        if scenario == "refuse_configuration":
            with pytest.raises(OperationalError):
                prepare(client, profile)
        else:
            prepare(client, profile)
            if scenario in ("provider_error", "crash_on_start"):
                with pytest.raises(ProductError) as observed:
                    client.call("start")
                assert observed.value.reason in ({"provider"} if scenario == "provider_error" else {"crash", "disconnection"})
            else:
                client.call("start")
    finally:
        try:
            client.close()
        except OSError as error:
            close_error = error
    assert (root / "config.json").read_bytes() == original
    assert not (root / "owner" / "config.dpapi").exists()
    if scenario == "hang_quit":
        assert close_error is not None
        assert any(row["action"] == "forced_owned_termination" for row in [json.loads(line) for line in (root / "owner" / "lifecycle.jsonl").read_text().splitlines()])
    for path in root.glob("diagnostic-*.jsonl"):
        text = path.read_text(encoding="utf-8")
        assert "synthetic-private-key-marker" not in text and "private-provider-secret-marker" not in text


def test_EOF_shutdown_without_explicit_stop_does_not_orphan_host(setup):
    root, profile, original = setup
    client = Adapter(profile, root, "eof")
    prepare(client, profile)
    client.call("start")
    identity = client.call("identity")
    client.close()
    assert WindowsRuntime.__new__(WindowsRuntime).identity(identity["pid"]) is None
    assert (root / "config.json").read_bytes() == original
    assert [row["data"] for row in host_events(root) if row["action"] == "control"][-1] == "OFF"


def test_fresh_frozen_argv_recovers_exited_owner_without_controlling_reused_PID(setup):
    root, profile, original = setup
    client = Adapter(profile, root, "interrupted")
    prepare(client, profile)
    client.call("start")
    identity = client.call("identity")
    client.process.kill()
    client.process.wait(timeout=5)
    client.close()
    wait_until(lambda: WindowsRuntime.__new__(WindowsRuntime).identity(identity["pid"]) is None)
    assert (root / "owner" / "config.dpapi").exists()
    recovered = Adapter(profile, root, "recovered")
    try:
        assert recovered.call("read_state")["running"] is False
        prepare(recovered, profile)
        assert recovered.call("identity")["creation_filetime_100ns"] != identity["creation_filetime_100ns"]
    finally:
        recovered.close()
    assert (root / "config.json").read_bytes() == original


def test_concurrent_config_edit_is_preserved_and_cleanup_failure_is_visible(setup):
    root, profile, _ = setup
    client = Adapter(profile, root, "edit")
    prepare(client, profile)
    changed = json.loads((root / "config.json").read_text())
    changed["unrelated_setting"] = "user-edited"
    atomic_json(root / "config.json", changed)
    with pytest.raises(OperationalError):
        client.call("read_state")
    with pytest.raises(OSError, match="cleanup failed"):
        client.close()
    assert json.loads((root / "config.json").read_text())["unrelated_setting"] == "user-edited"
    assert (root / "owner" / "config.dpapi").exists()  # intentional encrypted recovery evidence, never plaintext
    assert (root / "ownership" / "active.json").exists()


def test_reused_owned_PID_is_never_controlled_and_bystanders_block_launch(tmp_path):
    executable = tmp_path / "fixture.exe"
    executable.write_bytes(b"fixture")
    class Runtime:
        def identity(self, pid):
            return {"pid": pid, "creation_filetime_100ns": 2, "executable": str(executable)}
        def instances(self):
            return [123]
        def listeners(self):
            return []
    controller = KikitanController(tmp_path / "owner", executable, "KIKI2", runtime=Runtime(),
                                   config_path=tmp_path / "missing.json", ownership_root=tmp_path / "locks")
    try:
        with pytest.raises(ValueError, match="Preexisting"):
            controller._initialize()
        controller.record = {"process": {"pid": 123, "creation_filetime_100ns": 1, "executable": str(executable)}}
        with pytest.raises(ValueError, match="birth/executable"):
            controller.call("stop", {})
    finally:
        controller.record = None
        controller.close()


@pytest.mark.parametrize("cleanup_failure", [False, True])
def test_actual_CLI_Runner_controller_and_local_websocket_assembly(setup, cleanup_failure):
    root, profile, original = setup
    if cleanup_failure:
        atomic_json(root / "scenario.json", {"hang_quit": True})
    path = make_plan(root / "input", {"KIKI2": "kikitan"}, kinds=("P1",), duration=.6)
    plan = json.loads(path.read_text())
    plan["profiles"][0]["adapter"] = profile["adapter"]
    plan["profiles"][0]["control_timeout_seconds"] = 5
    plan["profiles"][0]["routes"]["self"].update(input_device=BINDING["input_device"], output_device=BINDING["output_device"])
    atomic_json(path, plan)
    result = execute(command(root, path), root, "assembled")
    assert result.returncode == (2 if cleanup_failure else 0), result.stderr
    manifest = report(root)
    assert manifest["work"][0]["outcome"] == "output_observed"
    rows = trace(root / "runs" / "smoke", manifest["attempts"][0])
    outputs = [row for row in rows if row.get("record") == "native_output_event" and row.get("capture_phase") == "input"]
    assert any(row["translated_text"] == "本地合成🦊修正" for row in outputs)
    assert not manifest["pending_passes"]
    assert next(row for row in host_events(root) if row["action"] == "control" and row["data"] == "ON")["clients"] == 2
    assert (root / "config.json").read_bytes() == original
    assert "synthetic-private-key-marker" not in json.dumps(manifest)
    assert bool([row for row in manifest["records"] if row["kind"] == "cleanup_failure"]) is cleanup_failure
    if cleanup_failure:
        failure = next(json.loads(row["detail"]) for row in manifest["records"] if row["kind"] == "cleanup_failure")
        assert failure["controller_cleanup_events"][0]["reason"] == "graceful_shutdown_failed_owned_host_terminated"
        # Terminal translated input is not replayed to repair a cleanup outcome.
        attempts = manifest["attempts"]
        resumed = execute(command(root, resume=True), root, "cleanup-resume")
        assert resumed.returncode == 0, resumed.stderr
        after = report(root)
        assert after["attempts"] == attempts and after["work"][0]["outcome"] == "output_observed"
        assert len([row for row in host_events(root) if row["action"] == "ready"]) == 1
        assert len([row for row in host_events(root) if row["action"] == "control" and row["data"] == "ON"]) == 1
        ownership = [json.loads(row["detail"]) for row in after["records"] if row["kind"] == "controller_cleanup_ownership"]
        assert ownership[-1]["owned"] is False


def test_failed_owned_startup_is_not_ready_and_restores_without_ON(setup):
    root, profile, original = setup
    atomic_json(root / "scenario.json", {"fail_startup": True})
    client = Adapter(profile, root, "failed-startup")
    try:
        with pytest.raises(ProductError) as observed:
            client.call("preflight", profile=profile, episode={}, pass_spec={})
        assert observed.value.reason == "crash"
    finally:
        client.close()
    assert (root / "config.json").read_bytes() == original
    assert not (root / "host.jsonl").exists()


def test_restoration_denies_intervening_writer_and_preserves_mismatch(tmp_path):
    from bench.kikitan_runtime import restore_config
    config = tmp_path / "config.json"
    config.write_bytes(b'{"target":"owned"}')
    def validate(current):
        assert current == b'{"target":"owned"}'
        with pytest.raises(PermissionError):
            config.write_bytes(b'{"target":"user-race"}')
    restore_config(config, b'{"target":"original"}', validate)
    assert config.read_bytes() == b'{"target":"original"}'
    config.write_bytes(b'{"target":"user-edited"}')
    def reject(current):
        raise ValueError("Unexpected current setting")
    with pytest.raises(ValueError):
        restore_config(config, b'{"target":"original"}', reject)
    assert config.read_bytes() == b'{"target":"user-edited"}'


def test_committed_restore_recovery_does_not_inspect_retired_reused_PID(tmp_path):
    executable = tmp_path / "fixture.exe"
    executable.write_bytes(b"fixture")
    directory, locks = tmp_path / "owner", tmp_path / "locks"
    directory.mkdir()
    locks.mkdir()
    anchor = {"directory": str(directory.resolve()), "executable": str(executable.resolve()), "profile": "KIKI2"}
    atomic_json(directory / "owner.json", {"anchor": anchor, "restored": True, "process": {"pid": 123}})
    atomic_json(locks / "active.json", anchor)
    (directory / "config.dpapi").write_bytes(b"synthetic encrypted recovery material")
    class RetiredRuntime:
        def identity(self, pid):
            raise AssertionError("Retired PID must never be queried")
    controller = KikitanController(directory, executable, "KIKI2", runtime=RetiredRuntime(),
                                   config_path=tmp_path / "unused.json", ownership_root=locks)
    assert controller.call("read_state", {})["running"] is False
    controller.close()
    assert not (directory / "config.dpapi").exists() and not (locks / "active.json").exists()


def test_CLI_releases_KIKI2_split_passes_before_KIKI1_wave(setup):
    root, _, original = setup
    first = json.loads(make_plan(root / "a", {"KIKI2": "kikitan"}, kinds=("T1",), duration=.4).read_text())
    second = json.loads(make_plan(root / "b", {"KIKI1": "kikitan"}, kinds=("P1",), duration=.4).read_text())
    second["episodes"][0].update(episode_id="e2", wave="W2")
    first["profiles"] += second["profiles"]
    first["episodes"] += second["episodes"]
    for profile in first["profiles"]:
        profile["adapter"] = [sys.executable, str(ENTRY), "--directory", str(root / ("owner-" + profile["id"])),
                              "--executable", sys._base_executable, "--profile", profile["id"]]
        profile["control_timeout_seconds"] = 5
        profile["routes"]["self"].update(input_device=BINDING["input_device"], output_device=BINDING["output_device"])
    plan = root / "sequential-plan.json"
    atomic_json(plan, first)
    result = execute(command(root, plan), root, "sequential")
    assert result.returncode == 0, result.stderr
    manifest = report(root)
    assert manifest["counts"]["done"] == 3 and not manifest["pending_passes"]
    assert all(work["outcome"] == "output_observed" for work in manifest["work"])
    assert [(work["profile"], work["pass_id"]) for work in manifest["work"]] == [("KIKI2", "A"), ("KIKI2", "B"), ("KIKI1", "ordinary-self")]
    events = host_events(root)
    assert len({row["pid"] for row in events if row["action"] == "ready"}) == 3
    assert len([row for row in events if row["action"] == "control" and row["data"] == "ON"]) == 3
    assert not any(row["action"] == "unsafe_quit_while_running" for row in events)
    diagnostics = [json.loads(row["detail"]) for row in manifest["records"] if row["kind"] == "diagnostic_artifact"]
    assert len(diagnostics) == len({row["path"] for row in diagnostics}) == 3
    assert not any(row["kind"] == "cleanup_failure" for row in manifest["records"])
    assert (root / "config.json").read_bytes() == original
    assert not (root / "ownership" / "active.json").exists()
