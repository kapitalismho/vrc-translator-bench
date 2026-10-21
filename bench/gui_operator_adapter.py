from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .storage import atomic_json


def process_alive(pid):
    if os.name != "nt":
        raise RuntimeError("Windows GUI process observation required")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetExitCodeProcess.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong))
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
    finally:
        kernel.CloseHandle(handle)


def read_observation(path):
    observation = json.loads(Path(path).read_text(encoding="utf-8"))
    if observation.get("basis") != "actual_visible_gui" or not observation.get("evidence"):
        raise ValueError("Actual GUI observation and evidence paths required")
    state = observation["state"]
    for field in ("microphone", "voice_output", "osc_host", "osc_port", "direction", "running"):
        if field not in state:
            raise ValueError("Incomplete GUI-observed state")
    if not isinstance(state["running"], bool):
        raise ValueError("GUI must establish actual capture state")
    return observation


class GuiOperator:
    def __init__(self, directory, pid, profile, session, timeout=600):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.pid = pid
        self.profile = profile
        self.session = session
        self.timeout = timeout
        self.sequence = max((int(path.stem.split("-")[1]) for path in self.directory.glob("request-*.json")), default=0)

    def observed(self, allow_pending=False):
        if not allow_pending and (self.directory / "invalidated.json").exists():
            raise ValueError("GUI observation retired after external configuration change or application restart; use a fresh session")
        if not allow_pending and (self.directory / "pending.json").exists():
            raise ValueError("GUI observation invalidated by pending configuration/capture mutation")
        observation = read_observation(self.directory / "observation.json")
        if observation["pid"] != self.pid or observation["profile"] != self.profile or observation["session"] != self.session:
            raise ValueError("Observation belongs to another application instance or pilot session")
        alive = process_alive(self.pid)
        return {**observation["state"], "running": observation["state"]["running"] and alive,
                "metadata": {**observation.get("metadata", {}), "observation_valid": alive,
                "capture_state_basis": "manual GUI observation while process alive; process exit establishes stopped",
                "continuous_effective_state_observation": False,
                "gui_observation": {key: observation[key] for key in ("basis", "observed_at_utc", "evidence", "profile", "session")}}}

    def record(self, path, sequence=None):
        if (self.directory / "invalidated.json").exists():
            raise ValueError("Retired GUI session cannot accept fresh observations; prepare a new session")
        observation = read_observation(path)
        if (observation["pid"], observation["profile"], observation["session"]) != (self.pid, self.profile, self.session):
            raise ValueError("Observation belongs to another application instance or pilot session")
        if sequence is None and (self.directory / "pending.json").exists():
            raise ValueError("Pending GUI mutation requires matching acknowledgment")
        if sequence is not None:
            request = json.loads((self.directory / f"request-{sequence:04d}.json").read_text(encoding="utf-8"))
            if (request["pid"], request["profile"], request["session"]) != (self.pid, self.profile, self.session):
                raise ValueError("Operator request belongs to another application instance or pilot session")
            if datetime.fromisoformat(observation["observed_at_utc"]) < datetime.fromisoformat(request["requested_at_utc"]):
                raise ValueError("GUI observation predates the operator request")
            if request["method"] in ("start", "stop") and observation["state"]["running"] != (request["method"] == "start"):
                raise ValueError("GUI observation does not establish requested capture transition")
        atomic_json(self.directory / "observation.json", observation)
        if sequence is not None:
            (self.directory / "pending.json").unlink(missing_ok=True)
            atomic_json(self.directory / f"response-{sequence:04d}.json", {"sequence": sequence})

    def operator(self, method, params):
        previous = (self.directory / "observation.json").read_bytes()
        self.sequence += 1
        request = {"sequence": self.sequence, "method": method, "params": params,
                   "pid": self.pid, "profile": self.profile, "session": self.session, "requested_at_ns": time.perf_counter_ns(),
                   "requested_at_utc": datetime.now(timezone.utc).isoformat()}
        path = self.directory / f"request-{self.sequence:04d}.json"
        atomic_json(self.directory / "pending.json", request)
        atomic_json(path, request)
        response = self.directory / f"response-{self.sequence:04d}.json"
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if response.exists():
                record = json.loads(response.read_text(encoding="utf-8"))
                if record.get("sequence") != self.sequence:
                    raise ValueError("Mismatched GUI operator response")
                if record.get("error"):
                    raise RuntimeError(record["error"])
                if (self.directory / "observation.json").read_bytes() == previous:
                    raise ValueError("Fresh GUI observation required after operator action")
                fresh = read_observation(self.directory / "observation.json")
                if datetime.fromisoformat(fresh["observed_at_utc"]) < datetime.fromisoformat(request["requested_at_utc"]):
                    raise ValueError("GUI observation predates the operator request")
                state = self.observed()
                if method in ("start", "stop") and state["running"] != (method == "start"):
                    raise ValueError("GUI observation does not establish requested capture transition")
                return state
            time.sleep(0.1)
        raise TimeoutError("GUI operator response unavailable; do not infer a completed operation")

    def call(self, method, params):
        if method == "read_state":
            return self.observed(allow_pending=not process_alive(self.pid))
        if method == "preflight":
            if not process_alive(self.pid):
                raise RuntimeError("Application process exited; previous GUI observation invalid")
            state = self.observed()
            if "CABLE Output" not in state["microphone"] or state["voice_output"] is not False:
                raise ValueError("GUI must establish safe cable-only input/output before capture")
            return {"ready": True, "metadata": state["metadata"]}
        if method == "set_direction" and self.observed()["direction"] == params["direction"]:
            return self.observed()
        if method == "stop" and not process_alive(self.pid):
            state = self.observed(allow_pending=True)
            state["metadata"]["stop_basis"] = "owned process exit independently observed"
            return state
        if method in ("start", "stop", "configure", "set_direction"):
            return self.operator(method, params)
        if method == "osc_identity":
            return {"pid": self.pid, "application": "GUI-prepared installed translator"}
        if method == "liveness":
            return {"alive": process_alive(self.pid)}
        if method == "begin_stage":
            return {}
        raise ValueError("Unsupported GUI operator method")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True)
    parser.add_argument("--owned-pid", type=int, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--record-observation", type=Path)
    parser.add_argument("--ack-sequence", type=int)
    args = parser.parse_args()
    operator = GuiOperator(args.directory, args.owned_pid, args.profile, args.session)
    if args.record_observation:
        operator.record(args.record_observation, args.ack_sequence)
        print("Recorded actual GUI observation" + (f"; acknowledged operator request {args.ack_sequence}" if args.ack_sequence else ""))
        return
    for line in sys.stdin:
        request = json.loads(line)
        try:
            response = {"id": request["id"], "result": operator.call(request["method"], request.get("params", {}))}
        except Exception as error:
            response = {"id": request["id"], "error": {"kind": "operational", "reason": "gui_control",
                        "message": type(error).__name__ + ": GUI operator observation/control failed"}}
        print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
