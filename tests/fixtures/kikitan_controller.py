"""Run the real JSON-line controller with only its installed-process boundary replaced."""
from __future__ import annotations

import os
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import bench.kikitan_adapter as adapter
from bench.kikitan_runtime import WindowsRuntime
from bench.native_process import _resume_primary_thread
from bench.quality_process import _WindowsJob


class FixtureRuntime(WindowsRuntime):
    def __init__(self, root):
        self.root = Path(root)
        self.executable = Path(sys._base_executable).resolve()
        self.process = self.job = None

    def instances(self):
        # Only this fixture's current owned Python process is an app instance.
        return [self.process.pid] if self.process is not None and self.identity(self.process.pid) else []

    def launch(self, persist_identity):
        self.job = _WindowsJob()
        try:
            # Bypass the venv redirector: the listening host must be the exact
            # PID/birth/executable persisted by the real controller.
            self.process = subprocess.Popen([str(self.executable), str(Path(__file__).with_name("kikitan_host.py")),
                                            "--config", str(self.root / "config.json"), "--events", str(self.root / "host.jsonl"),
                                            "--scenario", str(self.root / "scenario.json")], stdin=subprocess.DEVNULL,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=4,
                                           env={**os.environ, "PYTHONPATH": str(Path(sys.prefix) / "Lib" / "site-packages")})
            self.job.assign(self.process)
            persist_identity(self.identity(self.process.pid))
            _resume_primary_thread(self.process)
        except BaseException:
            if self.process is not None and self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=5)
            self.release()
            raise


if __name__ == "__main__":
    root = Path(os.environ["KIKITAN_FIXTURE_ROOT"])
    factory = adapter.KikitanController
    def controller(directory, executable, profile):
        instance = factory(directory, executable, profile, runtime=FixtureRuntime(root), config_path=root / "config.json",
                           ownership_root=root / "ownership", timeout=.75)
        normal_close = instance.close
        def close():
            marker = root / "abrupt-exit-once.json"
            if json.loads((root / "scenario.json").read_text()).get("abrupt_teardown") and not marker.exists():
                adapter.atomic_json(marker, {"returncode": 7})
                os._exit(7)  # lose EOF cleanup before restoration, without an error event
            normal_close()
        instance.close = close
        return instance
    adapter.KikitanController = controller
    raise SystemExit(adapter.main())
