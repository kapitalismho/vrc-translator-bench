"""Windows regression for launcher descendants retaining collector pipe handles."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import pytest

from bench import native_process, quality_process
from bench.native import NativeSink
from test_native_collectors import outputs, profile, wait_for


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Actual Windows Job/suspended-launch regression")


def test_real_launcher_descendant_pipe_ownership_and_stop(tmp_path, monkeypatch):
    child_pid_path = tmp_path / "owned-child.pid"
    launcher = tmp_path / "launcher.py"
    launcher.write_text(
        "import json,subprocess,sys\n"
        "from pathlib import Path\n"
        "child=subprocess.Popen([sys.executable,'-u','-c','import time; time.sleep(60)'],stdout=sys.stdout,stderr=sys.stderr)\n"
        f"Path({str(child_pid_path)!r}).write_text(str(child.pid))\n"
        "print(json.dumps({'output_version':1,'topic':'translation','channel':'peer','text':'synthetic output','sequence':1,'instance_id':'synthetic-host'}),flush=True)\n",
        encoding="utf-8")
    real_popen = subprocess.Popen
    def launch(args, **kwargs):
        assert args[0] == "synthetic-launcher"
        assert kwargs["creationflags"] == 4  # suspended before Job assignment
        return real_popen([sys.executable, str(launcher), *args[1:]], **kwargs)
    sink = NativeSink(tmp_path, "run", "s", [profile("puripuly", executable="synthetic-launcher", channels=["peer"])])
    # A separately owned process stands in for the existing host. It must not
    # enter the collector Job or be affected by collector-tree termination.
    bystander = real_popen([sys.executable, "-c", "import time; time.sleep(60)"],
                          stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    monkeypatch.setattr(native_process.subprocess, "Popen", launch)
    child_handle = None
    api = None
    try:
        sink.start("P")
        wait_for(lambda: child_pid_path.exists() and len(outputs(tmp_path)) == 1)
        transport = sink.transports["P"][0]
        owner = transport.owners[0]
        wait_for(lambda: owner.process.poll() is not None)
        child_pid = int(child_pid_path.read_text())
        api = owner.job.api
        assert child_pid in owner.job._process_ids()
        assert bystander.pid not in owner.job._process_ids()
        child_handle = api.OpenProcess(0x101000, False, child_pid)
        assert child_handle and api.WaitForSingleObject(child_handle, 0) == 258
        started = time.perf_counter()
        sink.stop("P")
        elapsed = time.perf_counter() - started
        assert elapsed < 5
        assert api.WaitForSingleObject(child_handle, 0) == 0
        assert all(not thread.is_alive() for thread in transport.threads)
        assert owner.process.stdout.closed and owner.process.stderr.closed
        assert bystander.poll() is None
    finally:
        sink.close()
        if child_handle:
            api.CloseHandle(child_handle)
        bystander.terminate()
        bystander.wait(timeout=5)


@pytest.mark.parametrize("failure_at", ["assign", "resume"])
def test_suspended_start_failure_cleans_process_and_preserves_original(tmp_path, monkeypatch, failure_at):
    marker = tmp_path / "must-not-execute"
    script = tmp_path / "suspended.py"
    script.write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n", encoding="utf-8")
    real_popen = subprocess.Popen
    created = []
    def launch(args, **kwargs):
        process = real_popen(args, **kwargs)
        created.append(process)
        return process
    original = OSError("synthetic " + failure_at + " failure")
    def fail(*args):
        raise original
    monkeypatch.setattr(native_process.subprocess, "Popen", launch)
    if failure_at == "assign":
        monkeypatch.setattr(quality_process._WindowsJob, "assign", fail)
    else:
        monkeypatch.setattr(native_process, "_resume_primary_thread", fail)
    with pytest.raises(OSError) as observed:
        native_process.CLIProcess([sys.executable, str(script)], os.environ.copy())
    assert observed.value is original
    assert len(created) == 1 and created[0].poll() is not None
    assert created[0].stdout.closed and created[0].stderr.closed
    assert not marker.exists()
