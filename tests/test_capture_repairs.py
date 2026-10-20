from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

import bench.plan as plan_module
from bench.plan import implementation_provenance, load_plan
from bench.runner import speech_timeout
from bench.storage import Ledger, atomic_json, digest
from test_capture import REPO, command, make_plan, report, wait_until


APP = REPO / "tests" / "fixtures" / "persistent_app.py"
CONTROLLER = REPO / "tests" / "fixtures" / "persistent_adapter.py"


class PersistentApplications:
    def __init__(self, root, plan_path):
        self.root = root
        self.plan_path = plan_path
        self.processes = {}
        self.ports = {}

    def __enter__(self):
        plan = json.loads(self.plan_path.read_text())
        try:
            for profile in plan["profiles"]:
                name = profile["id"]
                with socket.socket() as reservation:
                    reservation.bind(("127.0.0.1", 0))
                    port = reservation.getsockname()[1]
                ready = self.root / f"{name}-ready.json"
                process = subprocess.Popen([sys.executable, str(APP), "--state", str(self.root / f"{name}-state.json"),
                                            "--scenario", str(self.root / f"{name}-scenario.json"), "--ready", str(ready),
                                            "--port", str(port)], cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                self.processes[name] = process
                self.ports[name] = port
                wait_until(lambda: ready.is_file() and json.loads(ready.read_text())["port"] == port)
                identity = json.loads(ready.read_text())
                assert self.call(name, "read_state")["pid"] == identity["pid"]
                atomic_json(self.root / f"{name}-startup.json", {"launcher_pid": process.pid, "application_pid": identity["pid"], "port": port})
                profile["adapter"] = [sys.executable, str(CONTROLLER), "--port", str(port)]
            self.plan_path.write_text(json.dumps(plan))
            return self
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise

    def call(self, profile, method, **params):
        with socket.create_connection(("127.0.0.1", self.ports[profile]), timeout=5) as connection:
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


def run_cli(args, root, label, cwd=REPO, env=None):
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=30)
    (root / f"{label}-stdout.txt").write_text(result.stdout)
    (root / f"{label}-stderr.txt").write_text(result.stderr)
    path = root / "commands.json"
    commands = json.loads(path.read_text()) if path.exists() else []
    commands.append({"label": label, "args": list(map(str, args)), "cwd": str(cwd), "returncode": result.returncode})
    atomic_json(path, commands)
    return result


def run_args(root, plan, resume=False, executable=None):
    if executable is None:
        return command(root, plan, resume)
    args = [str(executable), "run", "--root", str(root / "runs"), "--audio-backend", "clock"]
    return args + (["--resume", "smoke"] if resume else ["--plan", str(plan), "--run-id", "smoke"])


def exercise_persistent_resume(root, terminal_outcome, executable=None, reconcile_error=False):
    scenario = {"chunks": {"c1": {"failure": {"reason": "provider", "message": "persistent first-attempt failure"}}}} if terminal_outcome == "product_failure" else {}
    if reconcile_error:
        scenario["reconcile_state_error"] = True
    path = make_plan(root, {"P1": scenario, "P2": {}, "P3": {}}, durations=(0.12, 0.7, 0.12))
    plan = json.loads(path.read_text())
    plan["stages"][0]["profiles"] = ["P1", "P2"]
    plan["stages"][1]["profiles"] = ["P2"]
    plan["stages"][2]["profiles"] = ["P3"]
    plan["stages"][2]["wave"] = "W2"
    path.write_text(json.dumps(plan))
    with PersistentApplications(root, path) as apps:
        args = run_args(root, path, executable=executable)
        process = subprocess.Popen(args, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            wait_until(lambda: apps.call("P2", "read_state").get("last_stage", {}).get("chunk") == "c2")
            process.terminate()
            stdout, stderr = process.communicate(timeout=10)
            (root / "interrupted-stdout.txt").write_text(stdout)
            (root / "interrupted-stderr.txt").write_text(stderr)
            atomic_json(root / "interruption-command.json", {"args": args, "returncode": process.returncode})
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        cut = time.perf_counter_ns()
        surviving = apps.call("P1", "read_state")
        assert surviving["running"] is True and apps.processes["P1"].poll() is None
        assert apps.call("P2", "read_state")["running"] is True
        assert apps.call("P3", "read_state")["starts"] == 0
        database = root / "runs" / "smoke" / "ledger.sqlite"
        with sqlite3.connect(database) as db:
            before = db.execute("SELECT a.* FROM attempts a JOIN work w ON w.id=a.work_id WHERE w.profile='P1' ORDER BY a.id").fetchall()
            assert all(row[3] in ("done", "product_failure") for row in before)
            assert any(row[3] == terminal_outcome for row in before)
        resumed = run_cli(run_args(root, path, resume=True, executable=executable), root, "resume")
        assert resumed.returncode == (2 if reconcile_error else 1 if terminal_outcome == "product_failure" else 0), resumed.stderr
        with sqlite3.connect(database) as db:
            after = db.execute("SELECT a.* FROM attempts a JOIN work w ON w.id=a.work_id WHERE w.profile='P1' ORDER BY a.id").fetchall()
        assert after == before
        if reconcile_error:
            assert "reconciliation state unavailable" in resumed.stderr
            assert all(apps.call(name, "read_state")["running"] is False for name in ("P1", "P2"))
            assert apps.call("P3", "read_state")["starts"] == 0
            atomic_json(root / "observations.json", {"terminal_attempts_unchanged": True,
                                                    "all_prior_capture_stopped": True, "future_capture_starts": 0,
                                                    "preserved_invalidity": resumed.stderr.strip()})
            return
        first = apps.call("P1", "read_state")
        entering = apps.call("P3", "read_state")
        assert first["pid"] == surviving["pid"] and first["running"] is False
        assert first["starts"] == first["stops"] == 1
        stopped = next(item["t_ns"] for item in first["lifecycle"] if item["action"] == "stop")
        started = next(item["t_ns"] for item in entering["lifecycle"] if item["action"] == "start")
        assert cut < stopped < started
        resumed_methods = [item["method"] for item in first["requests"] if item["t_ns"] > cut and item["controller_pid"] != 0]
        assert resumed_methods and set(resumed_methods) <= {"read_state", "stop"}
        manifest = report(root)
        assert not manifest["pending_stages"]
        assert all(item["profile"] != "P1" for item in manifest["work"] if item["kind"] in ("resume_setup", "resume_check"))
        assert apps.call("P2", "read_state")["starts"] == 1
        assert all(apps.call(name, "read_state")["running"] is False for name in apps.processes)
        observations = {"terminal_outcome": terminal_outcome, "surviving_app_pid": surviving["pid"],
                        "running_after_runner_termination": surviving["running"], "terminal_attempts_unchanged": before == after,
                        "resume_terminal_control_methods": resumed_methods, "stop_ns": stopped, "entering_start_ns": started,
                        "all_capture_stopped_before_app_shutdown": True, "final_counts": manifest["counts"]}
        atomic_json(root / "observations.json", observations)
        return observations


@pytest.mark.parametrize("terminal_outcome", ["done", "product_failure"])
def test_resume_reconciles_surviving_terminal_capture_without_replay(tmp_path, terminal_outcome):
    exercise_persistent_resume(tmp_path, terminal_outcome)


def exercise_post_start_invalidity(tmp_path, failure, executable=None):
    scenario = {"post_start_state_mismatch": True} if failure == "observed_running" else ({failure: True} if failure != "source_identity" else {})
    path = make_plan(tmp_path, {"P1": scenario}, durations=(0.12,))
    with PersistentApplications(tmp_path, path) as apps:
        if failure == "observed_running":
            profile = json.loads(path.read_text())["profiles"][0]
            apps.call("P1", "configure", requested_state={**profile["expected_state"], "direction": "D1"})
            apps.call("P1", "start")
        if failure == "source_identity":
            identity = apps.call("P1", "osc_identity")
            plan = json.loads(path.read_text())
            plan["profiles"][0]["osc"]["source_port"] = 1 if identity["source_port"] != 1 else 2
            path.write_text(json.dumps(plan))
        result = run_cli(run_args(tmp_path, path, executable=executable), tmp_path, "invalid")
        assert result.returncode == 2
        state = apps.call("P1", "read_state")
        assert apps.processes["P1"].poll() is None
        assert state["starts"] == state["stops"] == 1 and state["running"] is False
        manifest = report(tmp_path)
        invalid = [item for item in manifest["attempts"] if item["state"] == "invalid"]
        assert len(invalid) == 1
        expected = {"source_identity": "source-port identity", "post_start_state_mismatch": "settings mismatch",
                    "observed_running": "settings mismatch", "start_reply_error": "start applied but acknowledgement failed"}[failure]
        assert expected in invalid[0]["reason"]
        assert not [item for item in manifest["records"] if item["kind"] == "cleanup_failure"]
        assert any(item["kind"] == "capture_ownership" for item in manifest["records"])
        atomic_json(tmp_path / "observations.json", {"failure": failure, "original_invalidity": invalid[0]["reason"],
                                                    "running_after_invalid_run": state["running"], "lifecycle": state["lifecycle"]})


@pytest.mark.parametrize("failure", ["source_identity", "post_start_state_mismatch", "start_reply_error", "observed_running"])
def test_post_start_invalidity_stops_independent_capture(tmp_path, failure):
    exercise_post_start_invalidity(tmp_path, failure)


@pytest.mark.parametrize("now", [59, 60, 61, 89, 90])
def test_adjacent_speech_annotations_equal_merged_watchdog(now):
    second = 1_000_000_000
    merged = [[0, 90]]
    adjacent = [[0, 30], [30, 60], [60, 90]]
    assert speech_timeout(now * second, 0, 0, merged, None) == (now >= 60)
    assert speech_timeout(now * second, 0, 0, adjacent, None) == speech_timeout(now * second, 0, 0, merged, None)
    assert not speech_timeout(now * second, 0, 0, adjacent, max(0, now - 20) * second)
    assert not speech_timeout(89 * second, 0, 0, [[0, 30], [31, 90]], None)


def test_provenance_uses_loaded_checkout_not_operator_directory(tmp_path, monkeypatch):
    expected = implementation_provenance()
    monkeypatch.chdir(tmp_path)
    loaded = implementation_provenance()
    assert loaded == expected
    assert loaded["package_path"] == str(REPO / "bench")
    assert loaded["kind"] == "checkout" and loaded["revision"] != "unknown"


def test_git_unavailable_is_unknown_checkout_not_operator_revision(tmp_path, monkeypatch):
    def unavailable(*args, **kwargs):
        assert kwargs["cwd"] == REPO
        raise FileNotFoundError("git unavailable in isolated test")
    monkeypatch.setattr(plan_module.subprocess, "run", unavailable)
    identity = implementation_provenance()
    assert identity["revision"] == "unknown" and identity["revision_reason"] == "git_unavailable"
    assert identity["kind"] == "checkout" and identity["sources"]
    assert load_plan(make_plan(tmp_path), "no-git")["harness_revision"] == "unknown"


def exercise_session_provenance(root, executable=None, operator_cwd=REPO):
    path = make_plan(root, durations=(0.12, 0.7))
    args = run_args(root, path, executable=executable)
    process = subprocess.Popen(args, cwd=operator_cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        wait_until(lambda: json.loads((root / "P1-state.json").read_text()).get("last_stage", {}).get("chunk") == "c2")
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
        (root / "interrupted-stdout.txt").write_text(stdout)
        (root / "interrupted-stderr.txt").write_text(stderr)
        atomic_json(root / "interruption-command.json", {"args": args, "cwd": str(operator_cwd), "returncode": process.returncode})
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    run_root = root / "runs" / "smoke"
    frozen_before = digest(run_root / "frozen-plan.json")
    frozen = json.loads((run_root / "frozen-plan.json").read_text())
    assert frozen["harness_implementation"]["package_path"] == str(REPO / "bench")
    copied_root = root / "installed-package"
    shutil.copytree(REPO / "bench", copied_root / "bench", ignore=shutil.ignore_patterns("__pycache__"))
    (copied_root / "bench" / "__init__.py").write_text('__version__ = "0.2.0+synthetic-resume"\n')
    env = {**os.environ, "PYTHONPATH": str(copied_root)}
    resume_args = run_args(root, path, resume=True, executable=executable)
    resumed = run_cli(resume_args, root, "package-resume", cwd=copied_root, env=env)
    assert resumed.returncode == 0, resumed.stderr
    manifest = report(root)
    assert digest(run_root / "frozen-plan.json") == frozen_before
    assert manifest["plan"]["harness_revision"] == frozen["harness_revision"]
    assert manifest["plan"]["harness_sources"] == frozen["harness_sources"]
    sessions = manifest["session_implementations"]
    assert len(sessions) == 2
    original, actual = [item["implementation"] for item in sessions]
    assert original["package_path"] == str(REPO / "bench")
    assert actual["package_path"] == str(copied_root / "bench")
    assert actual["kind"] == "package" and actual["revision"] == "unknown"
    assert actual["package_version"] == "0.2.0+synthetic-resume"
    assert actual["sources"]["__init__.py"] != original["sources"]["__init__.py"]
    atomic_json(root / "observations.json", {"frozen_plan_unchanged": True, "session_implementations": sessions})
    return manifest


def test_resume_records_loaded_package_without_rewriting_original_provenance(tmp_path):
    exercise_session_provenance(tmp_path)


def test_prior_candidate_ownership_is_reconciled_from_historical_state(tmp_path):
    ledger = Ledger(tmp_path)
    try:
        ledger.record("application_state", {"profile": "P1", "state": {"running": True}})
        ledger.record("application_state", {"profile": "P2", "state": {"running": False}})
        assert ledger.owned_profiles() == {"P1"}
        ledger.record("capture_ownership", {"profile": "P1", "owned": False, "reason": "confirmed_stop"})
        assert ledger.owned_profiles() == set()
        ledger.record("capture_ownership", {"profile": "P2", "owned": True, "reason": "start_requested"})
        assert ledger.owned_profiles() == {"P2"}
    finally:
        ledger.close()


def test_reconciliation_failure_still_cleans_other_prior_owned_capture(tmp_path):
    exercise_persistent_resume(tmp_path, "product_failure", reconcile_error=True)
