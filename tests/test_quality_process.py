from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from bench import activity
from bench.quality_store import QualityStore
from bench.quality_transport import CommandTransport


ROOT = Path(__file__).resolve().parents[1]
PROMPT = {"version": "controlled-process-v1", "messages": [
    {"role": "system", "content": "Return the controlled structured response."},
    {"role": "user", "content": '{"source":"Hello","output":"안녕하세요"}'},
]}
JOB = {"id": "controlled-call", "input_hash": "controlled-input-v1", "prompt_hash": "controlled-prompt-v1"}
MODEL = "synthetic-judge-v1"
RESPONSE = {"status": "completed", "actual_model": MODEL, "model_identity_evidence": {"synthetic": True},
            "content": {"synthetic": True, "value": "controlled terminal result"}, "response_date": None,
            "raw": {"synthetic": True}}
DRIVER = """import json, sys
from pathlib import Path
from bench import activity
from bench.quality_store import QualityStore
from bench.quality_transport import load_transport
root, specification, lock = sys.argv[1:4]
job, prompt = map(json.loads, sys.argv[4:6])
model = 'synthetic-judge-v1'
activity.ACTIVITY_PATH = Path(lock)
transport = load_transport(specification)
assert transport.synthetic, 'This test driver must never dispatch a real judge'
with activity.exclusive_activity():
    store = QualityStore(root)
    try:
        store.recover()
        if store.cached(job, model) is None:
            call = store.start(job, model, transport.provenance)
            envelope = transport.call(prompt, call)
            store.raw(call, envelope)
            store.finish(call, envelope['status'], envelope, result=envelope.get('content'), reason=envelope.get('reason'))
        completed = store.cached(job, model) is not None
    finally:
        store.close()
raise SystemExit(0 if completed else 2)
"""
BLOCKED = """import json, os, subprocess, sys, time
from pathlib import Path
marker = Path(sys.argv[1])
marker.with_suffix('.started').write_text(str(os.getpid()), encoding='utf-8')
try:
    request = json.load(sys.stdin)
except (ValueError, EOFError):
    sys.exit(0)
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
marker.write_text(json.dumps({'pid': os.getpid(), 'descendant': child.pid}), encoding='utf-8')
print('controlled admitted request', flush=True)
time.sleep(120)
"""


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def setup_process(tmp_path):
    root = tmp_path / "calls"
    marker = tmp_path / "admitted.json"
    child = tmp_path / "blocked_judge.py"
    child.write_text(BLOCKED, encoding="utf-8")
    return root, marker, child


def driver_command(root, spec, lock):
    # One explicit synthetic attempt, not a benchmark queue or a replacement CLI.
    return [sys.executable, "-B", "-c", DRIVER, str(root), str(spec), str(lock),
            json.dumps(JOB), json.dumps(PROMPT, ensure_ascii=False)]


def observe_store(root):
    store = QualityStore(root)
    try:
        calls = store.history()
        return {"calls": calls, "call_states": dict(Counter(row["state"] for row in calls)),
                "cached": store.cached(JOB, MODEL)}
    finally:
        store.close()


def response_command():
    return [sys.executable, "-c",
            "import json,sys; request=json.load(sys.stdin); assert request['schema_version']==1; "
            "print(sys.argv[1]); print('controlled completion diagnostic',file=sys.stderr)",
            json.dumps(RESPONSE)]


def wait_until(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while not predicate():
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.02)
    return True


class OwnedProcess:
    def __init__(self, pid):
        from ctypes import wintypes
        self.pid = pid
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "OpenProcess": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            "WaitForSingleObject": ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            "TerminateProcess": ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = arguments, result
        self.handle = self.api.OpenProcess(0x100001, False, pid)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def exited(self):
        result = self.api.WaitForSingleObject(self.handle, 0)
        assert result in (0, 258), ctypes.WinError(ctypes.get_last_error())
        return result == 0

    def close(self):
        try:
            if not self.exited():
                assert self.api.TerminateProcess(self.handle, 1), ctypes.WinError(ctypes.get_last_error())
                assert self.api.WaitForSingleObject(self.handle, 10000) == 0
        finally:
            self.api.CloseHandle(self.handle)


def resume_and_reuse(root, tmp_path, lock):
    normal = dump(tmp_path / "normal.json", {"kind": "synthetic-command", "command": response_command()})
    before = observe_store(root)["calls"]
    result = subprocess.run(driver_command(root, normal, lock), cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr + result.stdout
    after = observe_store(root)
    assert after["call_states"] == {"unresolved": 1, "completed": 1}
    assert after["calls"][0]["id"] == before[0]["id"]
    assert after["calls"][0]["started_utc"] == before[0]["started_utc"]
    assert after["calls"][0]["state"] == "unresolved"
    assert after["calls"][0]["ended_utc"] is not None
    assert after["cached"]["result"] == RESPONSE["content"]
    assert after["cached"]["actual_model"] == MODEL
    assert after["calls"][1]["raw"]["transport_raw"]["stderr"] == "controlled completion diagnostic\n"
    repeated = subprocess.run(driver_command(root, normal, lock), cwd=ROOT, capture_output=True,
                              text=True, encoding="utf-8", timeout=30)
    assert repeated.returncode == 0, repeated.stderr + repeated.stdout
    assert observe_store(root)["calls"] == after["calls"]
    return {"call_states": after["call_states"], "calls_after_reuse": len(after["calls"])}


@pytest.mark.skipif(os.name != "nt", reason="Actual Windows Job Object parent-death observation")
def test_driver_parent_only_termination_contains_admitted_tree_and_recovery(tmp_path, monkeypatch):
    root, marker, child = setup_process(tmp_path)
    lock = tmp_path / "activity.lock"
    monkeypatch.setattr(activity, "ACTIVITY_PATH", lock)
    spec = dump(tmp_path / "blocked.json", {"kind": "synthetic-command", "command": [sys.executable, str(child), str(marker)]})
    process = subprocess.Popen(driver_command(root, spec, lock), cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    owned = []
    try:
        assert wait_until(marker.exists), "Controlled child did not receive a complete request"
        owned = [OwnedProcess(pid) for pid in json.loads(marker.read_text(encoding="utf-8")).values()]
        assert all(not child.exited() for child in owned)
        with pytest.raises(ValueError, match="capture or scoring operation is active"):
            with activity.exclusive_activity():
                pytest.fail("Capture admitted while controlled judge is active")
        process.kill()
        process.wait(timeout=10)
        gone = wait_until(lambda: all(child.exited() for child in owned), seconds=5)
        lock_available = False
        try:
            with activity.exclusive_activity():
                lock_available = True
        except ValueError:
            pass
        dump(tmp_path / "parent-only-observation.json", {"scorer_pid": process.pid, "terminated_only_parent": True,
            "owned_pids": [child.pid for child in owned], "children_gone": gone, "original_handles_signaled": gone, "capture_lock_available": lock_available,
            "call_states": observe_store(root)["call_states"]})
        assert gone or not lock_available, "Parent-only death released capture exclusion while its admitted child survived"
        assert gone, "Owned Windows judge tree must terminate when scoring parent exits"
        process.communicate(timeout=10)
        assert observe_store(root)["call_states"] == {"running": 1}
        result = resume_and_reuse(root, tmp_path, lock)
        dump(tmp_path / "resume-observation.json", result)
    finally:
        if process.poll() is None:
            process.kill()
        for child in owned:
            child.close()
        process.communicate(timeout=10)


@pytest.mark.skipif(os.name != "nt", reason="Actual Windows Job Object timeout tree observation")
def test_timeout_cleans_owned_tree_before_release_and_retains_unresolved(tmp_path, monkeypatch):
    root, marker, child = setup_process(tmp_path)
    lock = tmp_path / "activity.lock"
    monkeypatch.setattr(activity, "ACTIVITY_PATH", lock)
    spec = dump(tmp_path / "blocked.json", {"kind": "synthetic-command", "command": [sys.executable, str(child), str(marker)],
                                           "timeout_seconds": 1.5})
    process = subprocess.Popen(driver_command(root, spec, lock), cwd=ROOT, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding="utf-8")
    owned = []
    try:
        assert wait_until(marker.exists), "Timeout must cover an actually admitted child"
        owned = [OwnedProcess(pid) for pid in json.loads(marker.read_text(encoding="utf-8")).values()]
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == 2, stderr + stdout
        assert all(child.exited() for child in owned)
        with activity.exclusive_activity():
            pass
        observed = observe_store(root)
        assert observed["call_states"] == {"unresolved": 1}
        assert "timed out" in observed["calls"][0]["reason"]
        assert "controlled admitted request" in observed["calls"][0]["raw"]["raw"]["stdout"]
        dump(tmp_path / "timeout-observation.json", {"owned_pids": [child.pid for child in owned], "children_gone_before_return": True,
            "original_handles_signaled": True, "capture_lock_available": True, "call_states": observed["call_states"],
            "resume": resume_and_reuse(root, tmp_path, lock)})
    finally:
        if process.poll() is None:
            process.kill()
        for child in owned:
            child.close()
        process.communicate(timeout=10)


def test_ordinary_completion_preserves_envelope_and_streams():
    expected = {"schema_version": 1, "request_id": 7, "prompt": PROMPT}
    code = ("import json,sys; request=json.load(sys.stdin); assert request==json.loads(sys.argv[1]); "
            "print(sys.argv[2]); print('controlled diagnostic',file=sys.stderr)")
    transport = CommandTransport({"kind": "synthetic-command", "command": [
        sys.executable, "-c", code, json.dumps(expected, ensure_ascii=False), json.dumps(RESPONSE)]})
    envelope = transport.call(PROMPT, 7)
    assert {key: value for key, value in envelope.items() if key != "transport_raw"} == RESPONSE
    assert envelope["transport_raw"]["returncode"] == 0
    assert envelope["transport_raw"]["stderr"] == "controlled diagnostic\n"


def test_empty_bridge_input_exits_without_auth_or_inference():
    bun = shutil.which("bun")
    if not bun:
        pytest.skip("Early-EOF bridge observation requires installed Bun, not authentication")
    result = subprocess.run([bun, "--no-env-file", str(ROOT / "bench" / "quality_bridge.mjs"), "--model", "gpt-6-astra",
                             "--package-root", "nonexistent-auth-must-not-load", "--timeout-seconds", "1"],
                            input="", text=True, encoding="utf-8", capture_output=True, timeout=10)
    assert result.returncode == 0
    envelope = json.loads(result.stdout)
    assert envelope["status"] == "failed"
    assert envelope["raw"] is None
    assert "no inference attempted" in envelope["reason"]


def test_nonwindows_real_transport_fails_before_subprocess_spawn(monkeypatch):
    from bench import quality_process
    monkeypatch.setattr(quality_process, "WINDOWS", False)
    def forbidden(*args, **kwargs):
        pytest.fail("Unsupported real platform must not launch a process")
    monkeypatch.setattr(quality_process.subprocess, "Popen", forbidden)
    transport = CommandTransport({"kind": "chatgpt-sign-in-bridge", "route": "Sign in with ChatGPT",
                                  "command": [sys.executable, "-c", "raise SystemExit(99)"]})
    result = transport.call({"version": "synthetic", "messages": []}, 1)
    assert result["status"] == "unavailable"
    assert "requires Windows" in result["reason"]
    assert "no subprocess was started" in result["reason"]


def test_nonwindows_controlled_synthetic_transport_remains_available(monkeypatch):
    from bench import quality_process
    monkeypatch.setattr(quality_process, "WINDOWS", False)
    transport = CommandTransport({"kind": "synthetic-command", "command": [sys.executable, "-c",
        "import sys,json; value=json.load(sys.stdin); assert value['request_id']==1; "
        "print(json.dumps({'status':'unresolved','raw':{'synthetic':True}}))"]})
    result = transport.call({"version": "controlled-synthetic", "messages": []}, 1)
    assert result["status"] == "unresolved"
    assert result["raw"] == {"synthetic": True}
    assert result["transport_raw"]["returncode"] == 0


@pytest.mark.skipif(os.name != "nt", reason="Windows assignment must succeed before complete stdin is sent")
def test_assignment_failure_sends_no_payload_and_cleans_child(tmp_path, monkeypatch):
    from bench import quality_process
    root, marker, child = setup_process(tmp_path)
    owned = []
    def rejected(job, process):
        owned.append(process)
        raise OSError("Controlled assignment failure")
    monkeypatch.setattr(quality_process._WindowsJob, "assign", rejected)
    transport = CommandTransport({"kind": "synthetic-command", "command": [sys.executable, str(child), str(marker)]})
    with pytest.raises(OSError, match="Controlled assignment failure"):
        transport.call({"version": "controlled-synthetic", "messages": []}, 1)
    assert owned and all(process.returncode is not None for process in owned)
    assert not marker.exists(), "Child must not admit a request before successful containment assignment"


def completion_command(marker, release):
    code = (
        "import json,subprocess,sys,time; from pathlib import Path; request=json.load(sys.stdin); "
        "assert request['schema_version']==1; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
        "Path(sys.argv[1]).write_text(json.dumps({'pid':child.pid}),encoding='utf-8'); "
        "release=Path(sys.argv[2])\n"
        "while not release.exists(): time.sleep(.01)\n"
        "print(sys.argv[3]); print('controlled completion diagnostic',file=sys.stderr)"
    )
    return [sys.executable, "-c", code, str(marker), str(release), json.dumps(RESPONSE)]


@pytest.mark.skipif(os.name != "nt", reason="Windows normal completion must also drain owned descendants")
def test_driver_normal_completion_waits_for_original_descendant_handle(tmp_path, monkeypatch):
    root, marker, child = setup_process(tmp_path)
    release = tmp_path / "finish"
    lock = tmp_path / "activity.lock"
    monkeypatch.setattr(activity, "ACTIVITY_PATH", lock)
    spec = dump(tmp_path / "normal-descendant.json", {"kind": "synthetic-command", "command": completion_command(marker, release)})
    process = subprocess.Popen(driver_command(root, spec, lock), cwd=ROOT, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding="utf-8")
    owned = []
    try:
        assert wait_until(marker.exists), "Controlled descendant was not started"
        owned = [OwnedProcess(pid) for pid in json.loads(marker.read_text(encoding="utf-8")).values()]
        assert all(not child.exited() for child in owned)
        release.touch()
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == 0, stderr + stdout
        assert all(child.exited() for child in owned)
        observed = observe_store(root)
        assert observed["call_states"] == {"completed": 1}
        assert observed["calls"][0]["raw"]["transport_raw"]["returncode"] == 0
        assert observed["cached"]["result"] == RESPONSE["content"]
        assert observed["calls"][0]["raw"]["transport_raw"]["stderr"] == "controlled completion diagnostic\n"
        with activity.exclusive_activity():
            pass
        dump(tmp_path / "normal-observation.json", {"owned_pids": [child.pid for child in owned],
            "original_handles_signaled_before_return": True, "scorer_returncode": process.returncode,
            "call_states": observed["call_states"], "capture_lock_available": True})
    finally:
        release.touch()
        if process.poll() is None:
            process.kill()
        for child in owned:
            child.close()
        process.communicate(timeout=10)


@pytest.mark.skipif(os.name != "nt", reason="Windows job teardown must reject concurrent descendant admission")
def test_cleanup_closes_spawn_gate_before_snapshot_and_waits_original_handles(tmp_path, monkeypatch):
    from bench import quality_process
    marker, attempted = tmp_path / "members.json", tmp_path / "attempted.json"
    code = (
        "import json,os,subprocess,sys,time; from pathlib import Path; sys.stdin.readline(); "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
        "Path(sys.argv[1]).write_text(json.dumps({'pid':os.getpid(),'descendant':child.pid}),encoding='utf-8'); sys.stdin.readline()\n"
        "try:\n"
        " extra=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)']); result={'spawned':extra.pid}\n"
        "except OSError as error:\n"
        " result={'denied':error.winerror}\n"
        "Path(sys.argv[2]).write_text(json.dumps(result),encoding='utf-8'); time.sleep(120)"
    )
    job = quality_process._WindowsJob()
    process = subprocess.Popen([sys.executable, "-c", code, str(marker), str(attempted)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    owned = []
    try:
        job.assign(process)
        process.stdin.write("start\n")
        process.stdin.flush()
        assert wait_until(marker.exists)
        owned = [OwnedProcess(pid) for pid in json.loads(marker.read_text(encoding="utf-8")).values()]
        original = job._process_ids
        def snapshot():
            assert all(not child.exited() for child in owned)
            process.stdin.write("attempt\n")
            process.stdin.flush()
            assert wait_until(attempted.exists)
            assert json.loads(attempted.read_text(encoding="utf-8")) == {"denied": 1816}
            return original()
        monkeypatch.setattr(job, "_process_ids", snapshot)
        job.stop()
        assert all(child.exited() for child in owned)
        dump(tmp_path / "spawn-gate-observation.json", {"new_descendant_denied": 1816, "original_handles_signaled_before_stop_return": True})
    finally:
        job.close()
        for child in owned:
            child.close()
        process.communicate(timeout=10)


@pytest.mark.skipif(os.name != "nt", reason="Windows PID reuse must not retain an unrelated process handle")
def test_snapshot_rejects_handle_no_longer_in_owned_job(monkeypatch):
    from bench import quality_process
    job = quality_process._WindowsJob()
    try:
        monkeypatch.setattr(job, "_process_ids", lambda: [os.getpid()])
        assert job._process_handles() == []
        job.stop()
    finally:
        job.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows cleanup return requires original process handles signaled immediately")
def test_ordinary_completion_removes_owned_descendant_before_return(tmp_path):
    marker = tmp_path / "admitted.json"
    release = tmp_path / "finish"
    transport = CommandTransport({"kind": "synthetic-command", "command": completion_command(marker, release)})
    owned = []
    def call_and_observe():
        result = transport.call(PROMPT, 1)
        return result, [child.exited() for child in owned]
    with ThreadPoolExecutor(max_workers=1) as worker:
        pending = worker.submit(call_and_observe)
        try:
            assert wait_until(marker.exists)
            owned = [OwnedProcess(pid) for pid in json.loads(marker.read_text(encoding="utf-8")).values()]
            assert all(not child.exited() for child in owned)
            release.touch()
            result, signaled_at_return = pending.result(timeout=15)
            assert result["status"] == "completed"
            assert result["transport_raw"]["returncode"] == 0
            assert signaled_at_return and all(signaled_at_return)
            dump(tmp_path / "direct-barrier-observation.json", {"owned_pids": [child.pid for child in owned],
                "original_handles_signaled_in_calling_thread_immediately_after_transport_return": signaled_at_return,
                "transport_status": result["status"], "transport_returncode": result["transport_raw"]["returncode"]})
        finally:
            release.touch()
            for child in owned:
                child.close()
