from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
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


def process_identity(pid):
    """Read a live Windows process birth time/path, never a guessed instance ID."""
    if os.name != "nt":
        raise RuntimeError("Windows process identity observation required")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetProcessTimes.argtypes = (ctypes.c_void_p,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
    kernel.QueryFullProcessImageNameW.argtypes = (ctypes.c_void_p, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise ValueError("Cannot establish live owned process identity")
    try:
        created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
        name, size = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
        if (not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel_time), ctypes.byref(user_time))
                or not kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)) or not process_alive(pid)):
            raise ValueError("Cannot establish live owned process identity")
        return {"pid": pid, "creation_filetime_100ns": (created.dwHighDateTime << 32) | created.dwLowDateTime,
                "clock": "windows_filetime_utc", "executable": name.value}
    finally:
        kernel.CloseHandle(handle)


def _utc(value):
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise ValueError("Observation/request timestamps require an explicit timezone")
    return stamp.astimezone(timezone.utc)


def _filetime_utc(value):
    # Compare two UTC wall-clock representations, never a process birth time to
    # requested_at_ns or the collector's independent monotonic receipt clock.
    delta = _utc(value) - datetime(1601, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86400 + delta.seconds) * 10_000_000 + delta.microseconds * 10


def read_observation(path):
    observation = json.loads(Path(path).read_text(encoding="utf-8"))
    if observation.get("basis") != "actual_visible_gui" or not observation.get("evidence"):
        raise ValueError("Actual GUI observation and evidence paths required")
    state = observation["state"]
    for field in ("voice_output", "channels", "running"):
        if field not in state:
            raise ValueError("Incomplete GUI-observed episode state")
    if not isinstance(state["running"], bool):
        raise ValueError("GUI must establish actual capture state")
    if not isinstance(state["channels"], dict) or set(state["channels"]) - {"self", "peer"}:
        raise ValueError("GUI must identify actual self/peer routes")
    for channel in state["channels"].values():
        if any(field not in channel for field in ("role", "input_device", "output_device", "source_language", "target_language")):
            raise ValueError("Incomplete GUI-observed channel binding")
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

    def _validate_ack(self, observation, request, previous):
        owned = (request["pid"], request["profile"], request["session"])
        if (previous["pid"], previous["profile"], previous["session"]) != owned or request["profile"] != self.profile:
            raise ValueError("Operator request does not match previous owned application/session")
        if _utc(observation["observed_at_utc"]) < _utc(request["requested_at_utc"]):
            raise ValueError("GUI observation predates the operator request")
        current = (observation["pid"], observation["profile"], observation["session"])
        reset = observation.get("session_reset", {})
        if request["method"] == "reset_session":
            params = request["params"]
            if (reset.get("episode_id"), reset.get("pass_id")) != (params["episode_id"], params["pass_id"]):
                raise ValueError("Reset evidence belongs to another episode/pass")
            if reset.get("basis") not in ("product_new_conversation", "verified_application_restart") or not reset.get("evidence"):
                raise ValueError("Genuine conversation reset evidence required; screen clear is insufficient")
        if current == owned:
            if request["method"] == "reset_session":
                if reset["basis"] == "verified_application_restart":
                    raise ValueError("Verified application restart requires an explicit owned successor")
                if not process_alive(request["pid"]) or process_identity(request["pid"]) != request["owned_process"]:
                    raise ValueError("Original owned process identity changed during conversation reset")
        else:
            successor = reset.get("successor")
            if (request["method"] != "reset_session" or reset.get("basis") != "verified_application_restart"
                    or not isinstance(successor, dict) or observation["profile"] != request["profile"]):
                raise ValueError("Observation belongs to another application instance or pilot session")
            if ((successor.get("previous_pid"), successor.get("previous_session")) != (request["pid"], request["session"])
                    or (successor.get("pid"), successor.get("session")) != (observation["pid"], observation["session"])
                    or not isinstance(successor.get("evidence"), list) or not successor["evidence"]):
                raise ValueError("Successor evidence must explicitly bind previous and new ownership")
            if (type(observation["pid"]) is not int or observation["pid"] <= 0 or observation["pid"] == request["pid"]
                    or not isinstance(observation["session"], str) or not observation["session"]):
                raise ValueError("Restart requires a distinct successor PID and fresh session")
            for path in self.directory.glob("request-*.json"):
                if json.loads(path.read_text(encoding="utf-8"))["session"] == observation["session"]:
                    raise ValueError("Successor session was already used")
            if process_alive(request["pid"]) or not process_alive(observation["pid"]):
                raise ValueError("Previous owned process must exit and successor must be alive")
            identity = process_identity(observation["pid"])
            old = request.get("owned_process", {})
            if (identity != observation.get("process_identity") or old.get("pid") != request["pid"]
                    or identity.get("clock") != "windows_filetime_utc" or old.get("clock") != "windows_filetime_utc"
                    or os.path.normcase(identity["executable"]) != os.path.normcase(old["executable"])
                    or identity["creation_filetime_100ns"] < _filetime_utc(request["requested_at_utc"])):
                raise ValueError("Successor live identity must match fresh post-request same-application evidence")
            if observation["state"]["running"] is not False:
                raise ValueError("Restart must establish stopped successor capture before configuration")
        if request["method"] in ("start", "stop") and observation["state"]["running"] != (request["method"] == "start"):
            raise ValueError("GUI observation does not establish requested capture transition")

    def record(self, path, sequence=None):
        if (self.directory / "invalidated.json").exists():
            raise ValueError("Retired GUI session cannot accept fresh observations; prepare a new session")
        observation = read_observation(path)
        if sequence is None:
            if (observation["pid"], observation["profile"], observation["session"]) != (self.pid, self.profile, self.session):
                raise ValueError("Observation belongs to another application instance or pilot session")
            if (self.directory / "pending.json").exists():
                raise ValueError("Pending GUI mutation requires matching acknowledgment")
        else:
            request = json.loads((self.directory / f"request-{sequence:04d}.json").read_text(encoding="utf-8"))
            if (request["pid"], request["profile"], request["session"]) != (self.pid, self.profile, self.session):
                raise ValueError("Operator request belongs to another application instance or pilot session")
            pending = json.loads((self.directory / "pending.json").read_text(encoding="utf-8"))
            if pending != request or pending["sequence"] != sequence:
                raise ValueError("Acknowledgment does not match the current pending operator request")
            previous = read_observation(self.directory / "observation.json")
            self._validate_ack(observation, request, previous)
        atomic_json(self.directory / "observation.json", observation)
        if sequence is not None:
            (self.directory / "pending.json").unlink()
            atomic_json(self.directory / f"response-{sequence:04d}.json", {"sequence": sequence})

    def operator(self, method, params):
        previous = (self.directory / "observation.json").read_bytes()
        self.sequence += 1
        request = {"sequence": self.sequence, "method": method, "params": params,
                   "pid": self.pid, "profile": self.profile, "session": self.session, "requested_at_ns": time.perf_counter_ns(),
                   "requested_at_utc": datetime.now(timezone.utc).isoformat()}
        if method == "reset_session":
            if not process_alive(self.pid):
                raise ValueError("Reset requires a live previously owned application")
            request["owned_process"] = process_identity(self.pid)
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
                self._validate_ack(fresh, request, json.loads(previous))
                self.pid, self.session = fresh["pid"], fresh["session"]
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
            if state["voice_output"] is not False:
                raise ValueError("GUI must establish voice_output false before capture")
            return {"ready": True, "metadata": state["metadata"]}
        if method == "stop" and not process_alive(self.pid):
            state = self.observed(allow_pending=True)
            state["metadata"]["stop_basis"] = "owned process exit independently observed"
            return state
        if method == "reset_session":
            self.operator(method, params)
            reset = read_observation(self.directory / "observation.json").get("session_reset", {})
            if (reset.get("episode_id"), reset.get("pass_id")) != (params["episode_id"], params["pass_id"]):
                raise ValueError("Reset evidence belongs to another episode/pass")
            if reset.get("basis") not in ("product_new_conversation", "verified_application_restart") or not reset.get("evidence"):
                raise ValueError("Genuine conversation reset evidence required; screen clear is insufficient")
            return {**reset, "reset": True}
        if method in ("start", "stop", "configure"):
            return self.operator(method, params)
        if method == "identity":
            return {"pid": self.pid, "session": self.session, "application": "GUI-prepared installed translator",
                    "process_identity": process_identity(self.pid) if process_alive(self.pid) else None}
        if method == "liveness":
            alive = process_alive(self.pid)
            unknown = {"continuous": None, "evidence": [], "gaps": []}
            return {"alive": alive, "app_continuity": unknown, "input_continuity": unknown,
                    "process_observation": {"pid": self.pid, "alive": alive, "basis": "process query only"}}
        if method == "begin_pass":
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
