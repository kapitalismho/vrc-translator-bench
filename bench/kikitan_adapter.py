"""Owned installed Kikitan --no-ui controller for the episode JSON-line protocol.

The collector is separate and read-only. This process never attaches to a user's
instance. Shared settings are restored only after owned exit and an exact
field-hash comparison; credentials/state/vendor logs never enter protocol output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

from .adapter import OperationalError, ProductError
from .kikitan_runtime import WindowsRuntime, protect, restore_config
from .native_transports import KIKITAN_URL, kikitan_endpoint
from .storage import RunLock, atomic_json, digest


PUBLIC_FIELDS = {
    "recognizer": int, "translator": int,
    "source_language": str, "target_language": str, "microphone": str,
    "desktop_translation": bool, "send_user_data": bool, "send_to_chatbox": bool,
    "speech_to_text_only": bool, "disable_when_muted": bool, "translation_only": bool,
    "send_without_waiting_for_finish": bool, "chatbox_wait_per_char_ms": int, "osc_port": int,
}
VOICE_BASIS = "stock_2.0.2_microphone_TEXT_recognition_output_no_TTS_pipeline"


def _public_value(value, expected_type):
    if type(value) is not expected_type:
        raise ValueError("Invalid Kikitan public state field type")
    return value


def _failure_reason(error):
    # Only exact controller-authored messages get specific public reason codes.
    # Parser/socket exceptions may contain secrets and stay type-only.
    return {
        "Shared Kikitan settings changed outside owned configuration; preserving edits": "concurrent_settings_edit",
        "Concurrent settings edit; refusing restoration": "concurrent_settings_edit",
        "Cannot exclusively compare/restore shared Kikitan config": "settings_restore_access_denied",
        "Kikitan graceful shutdown failed; owned host terminated": "graceful_shutdown_failed_owned_host_terminated",
        "Owned PID birth/executable changed; refusing control": "owned_process_identity_changed",
        "Preexisting or concurrent Kikitan application; refusing shared settings/control": "concurrent_application",
        "Fixed Kikitan WebSocket listener is not exclusively owned": "endpoint_owner_mismatch",
        "Shared Kikitan settings have another unresolved owner directory": "unresolved_settings_owner",
        "Kikitan state readback timed out": "state_readback_timeout",
        "Exact configured microphone is not enumerated by Kikitan": "input_device_unavailable",
    }.get(str(error), "kikitan_" + type(error).__name__)


def _hashes(value):
    return {key: hashlib.sha256(json.dumps(item, ensure_ascii=False, sort_keys=True,
                                         allow_nan=False).encode("utf-8")).hexdigest() for key, item in value.items()}




class KikitanController:
    def __init__(self, directory, executable, profile, *, runtime=None, config_path=None,
                 ownership_root=None, codec=protect, connect=None, timeout=8):
        if profile not in ("KIKI1", "KIKI2"):
            raise ValueError("Kikitan controller profile must be KIKI1 or KIKI2")
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.executable = Path(executable).resolve(strict=True)
        self.profile, self.timeout, self.codec = profile, timeout, codec
        self.runtime = runtime or WindowsRuntime(self.executable)
        self.config_path = Path(config_path) if config_path else Path(os.environ["APPDATA"]) / "Kikitan Translator" / "config.json"
        self.ownership_root = Path(ownership_root) if ownership_root else Path.home() / ".cache" / "vrc-translator-bench" / "kikitan-controller"
        self.ownership_root.mkdir(parents=True, exist_ok=True)
        self.lock = RunLock(self.ownership_root)
        self.lock.__enter__()
        self.socket = None
        self.failure = None
        self.record = None
        self.closed = False
        self.connect = connect
        self.receipts = self.directory / "lifecycle.jsonl"
        self.owner_path = self.directory / "owner.json"
        self.backup_path = self.directory / "config.dpapi"
        self.pointer = self.ownership_root / "active.json"
        try:
            if self.pointer.exists():
                pointer = json.loads(self.pointer.read_text(encoding="utf-8"))
                if pointer != self._anchor():
                    raise ValueError("Shared Kikitan settings have another unresolved owner directory")
                self.record = json.loads(self.owner_path.read_text(encoding="utf-8"))
                if self.record.get("anchor") != self._anchor():
                    raise ValueError("Kikitan durable ownership is incomplete")
                if self.record.get("restored") is True:
                    # Committed restoration precedes encrypted-backup removal.
                    # Never query a retired historical PID during this recovery.
                    self.backup_path.unlink(missing_ok=True)
                    self.pointer.unlink()
                    self.record = None
                else:
                    if not self.backup_path.is_file() or digest(self.executable) != self.record["executable_sha256"]:
                        raise ValueError("Owned executable or encrypted backup changed")
                    self._owned_alive()
            elif self.owner_path.exists() or self.backup_path.exists():
                previous = json.loads(self.owner_path.read_text(encoding="utf-8"))
                if previous.get("anchor") != self._anchor() or previous.get("restored") is not True or self.backup_path.exists():
                    raise ValueError("Incomplete owner directory; recover original ownership first")
        except BaseException:
            self.lock.__exit__(None, None, None)
            raise

    def _anchor(self):
        return {"directory": str(self.directory), "executable": str(self.executable), "profile": self.profile}

    def _save(self):
        atomic_json(self.owner_path, self.record)

    def _receipt(self, action, **fields):
        with self.receipts.open("a", encoding="utf-8") as target:
            target.write(json.dumps({"action": action, "t_ns": time.perf_counter_ns(), **fields}) + "\n")
            target.flush()
            os.fsync(target.fileno())

    def _config(self):
        value = json.loads(self.config_path.read_bytes())
        if not isinstance(value, dict):
            raise ValueError("Shared Kikitan config is not an object")
        return value

    def _check_settings(self):
        value = self._config()
        allowed = [self.record["expected_hashes"], *self.record.get("pending_hashes", [])]
        if _hashes(value) not in allowed:
            raise ValueError("Shared Kikitan settings changed outside owned configuration; preserving edits")
        return value

    def _owned_alive(self):
        identity = self.record.get("process") if self.record else None
        if identity is None:
            return False
        current = self.runtime.identity(identity["pid"])
        if current is not None and current != identity:
            raise ValueError("Owned PID birth/executable changed; refusing control")
        return current is not None

    def _exclusive(self, *, listener=False):
        owned = self.record.get("process") if self.record else None
        if set(self.runtime.instances()) - ({owned["pid"]} if owned and self._owned_alive() else set()):
            raise ValueError("Preexisting or concurrent Kikitan application; refusing shared settings/control")
        listeners = self.runtime.listeners()
        expected = [("127.0.0.1", owned["pid"])] if owned and self._owned_alive() else []
        if listeners != expected and (listener or listeners):
            raise ValueError("Fixed Kikitan WebSocket listener is not exclusively owned")

    def _initialize(self):
        self._exclusive()
        original = self.config_path.read_bytes()
        config = json.loads(original)
        if not isinstance(config, dict):
            raise ValueError("Existing shared configuration required")
        # No raw config/state/log copies. DPAPI is bound to the current user.
        with self.backup_path.open("xb") as target:
            target.write(self.codec(original))
            target.flush()
            os.fsync(target.fileno())
        self.record = {"schema_version": 1, "anchor": self._anchor(), "executable_sha256": digest(self.executable),
                       "original_sha256": hashlib.sha256(original).hexdigest(), "expected_hashes": _hashes(config),
                       "pending_hashes": [], "process": None, "session": None, "channels": {},
                       "reset_for": None, "start_requested": False}
        self._save()
        atomic_json(self.pointer, self._anchor())

    def _launch(self):
        self._check_settings()
        self._exclusive()
        def claimed(identity):
            if not identity or os.path.normcase(identity["executable"]) != os.path.normcase(str(self.executable)):
                raise ValueError("Launched executable identity differs")
            self.record.update(process=identity, session=uuid.uuid4().hex, channels={}, reset_for=None,
                               start_requested=False)
            self._save()
            self._receipt("owned_launch", pid=identity["pid"], creation_filetime_100ns=identity["creation_filetime_100ns"],
                          executable_sha256=self.record["executable_sha256"], session=self.record["session"])
        self.runtime.launch(claimed)
        self._connect()
        state = self._state_until(lambda state: state["status"] == 0)
        self._receipt("initial_stopped", status=state["status"])

    def _connect(self):
        if self.socket is not None:
            return
        if not self._owned_alive():
            raise ProductError("crash", "Owned Kikitan process exited")
        deadline = time.monotonic() + self.timeout
        while True:
            if not self._owned_alive():
                raise ProductError("crash", "Owned Kikitan exited before WebSocket readiness")
            self._exclusive()
            if self.runtime.listeners():
                self._exclusive(listener=True)
                if self.connect is None:
                    from websockets.sync.client import connect
                    self.connect = connect
                self.socket = self.connect(KIKITAN_URL, open_timeout=3, close_timeout=1,
                                           max_size=None, proxy=None)
                return
            if time.monotonic() >= deadline:
                raise ValueError("Owned Kikitan WebSocket startup timed out")
            time.sleep(0.05)

    def _send(self, method, data=""):
        if not self._owned_alive():
            raise ProductError("crash", "Owned Kikitan process exited")
        self._exclusive(listener=True)
        self.socket.send(json.dumps({"method": method, "data": data}))

    def _frame(self, message):
        # This data can contain credentials inside JSON strings. Never log it or
        # include parser errors/free text in protocol replies, even on failure.
        outer = json.loads(message)
        if not isinstance(outer, dict):
            raise ValueError("Invalid Kikitan controller envelope")
        method = outer.get("method")
        if method not in ("state", "notification"):
            return None
        value = json.loads(outer["data"])
        if not isinstance(value, dict):
            raise ValueError("Invalid Kikitan controller state")
        if method == "notification":
            if value.get("level") == 2:
                self.failure = {"reason": "provider", "message": "Kikitan reported an error notification"}
                self._receipt("error_notification", payload_sha256=hashlib.sha256(message.encode("utf-8")).hexdigest())
            return None
        if type(value.get("status")) is not int or value["status"] not in (0, 1, 2) or not isinstance(value.get("config"), dict):
            raise ValueError("Invalid Kikitan state fields")
        return value

    def _receive(self, timeout):
        from websockets.exceptions import ConnectionClosed
        try:
            return self.socket.recv(timeout=timeout)
        except ConnectionClosed:
            if not self._owned_alive():
                raise ProductError("crash", "Owned Kikitan process exited") from None
            raise ProductError("disconnection", "Owned Kikitan control WebSocket disconnected") from None

    def _state_until(self, predicate):
        self._connect()
        # Discard queued state before issuing a fresh supported read request.
        while True:
            try:
                self._frame(self._receive(0))
            except TimeoutError:
                break
        self._send("send_app_state")
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                state = self._frame(self._receive(max(0, deadline - time.monotonic())))
            except TimeoutError:
                raise ValueError("Kikitan state readback timed out") from None
            if state is not None and predicate(state):
                self._check_settings()
                return state
            if time.monotonic() >= deadline:
                raise ValueError("Kikitan state readback did not match")

    def _public_state(self, state):
        config = state["config"]
        settings = {field: _public_value(config.get(field), expected_type)
                    for field, expected_type in PUBLIC_FIELDS.items()}
        channels = {}
        for channel, binding in self.record["channels"].items():
            channels[channel] = {**binding, "input_device": settings["microphone"],
                                 "source_language": settings["source_language"], "target_language": settings["target_language"]}
        return {**settings, "app_settings": settings, "running": state["status"] != 0,
                "status": state["status"], "voice_output": False, "voice_output_basis": VOICE_BASIS,
                "channels": channels, "channel_binding_basis": {"input_device_languages": "supported_app_state_readback",
                    "role_output_device": "harness_logical_binding_not_app_setting"}}

    def _stop(self):
        if not self._owned_alive():
            return {"running": False, "basis": "owned_process_exited"}
        self._connect()
        self._send("control", "OFF")
        state = self._state_until(lambda state: state["status"] == 0)
        self._receipt("observed_OFF", status=0)
        return self._public_state(state)

    def _exit(self):
        failure = None
        if self._owned_alive():
            try:
                self._stop()
                self._send("quit")
                self._receipt("quit_after_OFF")
                deadline = time.monotonic() + self.timeout
                while self._owned_alive() and time.monotonic() < deadline:
                    time.sleep(0.05)
                if self._owned_alive():
                    raise ValueError("Owned Kikitan did not exit after quit")
            except Exception as error:
                failure = error
                if self._owned_alive():
                    self.runtime.terminate(self.record["process"])
                    self._receipt("forced_owned_termination")
        if self.socket is not None:
            self.socket.close()
            self.socket = None
        if self._owned_alive():
            raise ValueError("Owned Kikitan remains alive")
        self.runtime.release()
        self._receipt("owned_exit")
        if failure is not None:
            raise ValueError("Kikitan graceful shutdown failed; owned host terminated") from None

    def _configure(self, requested):
        if set(requested) - {*PUBLIC_FIELDS, "voice_output", "channels"} or requested.get("voice_output") is not False:
            raise ValueError("Unsupported Kikitan requested state")
        bindings = requested.get("channels")
        if not isinstance(bindings, dict) or set(bindings) != {"self"}:
            raise ValueError("Kikitan supports only the microphone/self channel")
        binding = bindings["self"]
        if (set(binding) != {"role", "input_device", "output_device", "source_language", "target_language"}
                or binding["role"] not in ("A", "B") or any(not isinstance(v, str) or not v for v in binding.values())):
            raise ValueError("Explicit self input and harness role/output/language binding required")
        state = self._state_until(lambda state: state["status"] == 0)
        microphones = state.get("microphones")
        if not isinstance(microphones, list) or not any(isinstance(mic, dict) and mic.get("name") == binding["input_device"] for mic in microphones):
            raise ValueError("Exact configured microphone is not enumerated by Kikitan")
        self.failure = None
        engine = 0 if self.profile == "KIKI1" else 2
        desired = {"recognizer": engine, "translator": engine, "desktop_translation": False,
                   "send_user_data": False, "send_to_chatbox": False, "speech_to_text_only": False,
                   "disable_when_muted": False, "microphone": binding["input_device"],
                   "source_language": binding["source_language"], "target_language": binding["target_language"]}
        for field in PUBLIC_FIELDS:
            if field in requested:
                if type(requested[field]) is not PUBLIC_FIELDS[field]:
                    raise ValueError("Requested Kikitan setting has an invalid type")
                if field in desired and (type(requested[field]) is not type(desired[field]) or requested[field] != desired[field]):
                    raise ValueError("Requested settings conflict with Kikitan profile/self binding")
                desired[field] = requested[field]
        for field, value in desired.items():
            current = self._check_settings()
            if state["config"].get(field) == value and type(state["config"].get(field)) is type(value):
                continue
            expected = dict(current)
            expected[field] = value
            pending = [_hashes(expected)]
            if field in ("recognizer", "translator"):
                other = "translator" if field == "recognizer" else "recognizer"
                if value == 2:
                    expected[other] = 2
                elif expected.get(other) == 2:
                    expected[other] = 0
                pending.append(_hashes(expected))
            self.record["pending_hashes"] = pending
            self._save()  # recovery recognizes interrupted supported setters
            self._send("update_config", json.dumps({"field": field, "value": value}))
            state = self._state_until(lambda state: state["status"] == 0 and state["config"].get(field) == value
                                      and _hashes(self._config()) == _hashes(expected))
            self.record.update(expected_hashes=_hashes(expected), pending_hashes=[])
            self._save()
            self._receipt("configuration_readback", field=field)
        if any(type(state["config"].get(key)) is not type(value) or state["config"].get(key) != value for key, value in desired.items()):
            raise ValueError("Effective Kikitan app settings differ from requested profile")
        self.record["channels"] = {"self": dict(binding)}
        self._save()
        return self._public_state(state)

    def call(self, method, params):
        if method == "preflight":
            spec = params["profile"]
            if spec["id"] != self.profile:
                raise ValueError("Frozen profile differs from controller owner")
            kikitan_endpoint(spec["collector"])
            if self.record is None:
                self._initialize()
            if not self._owned_alive():
                self._launch()
            state = self._state_until(lambda state: True)
            return {"ready": True, "metadata": {"app_version": _public_value(state.get("app_version"), str), "mode": "installed_no_ui",
                    "endpoint": KIKITAN_URL, "startup_side_effects": "shared_vendor_logs_update_check_OSCQuery_device_enumeration_static_server",
                    "voice_output_basis": VOICE_BASIS}}
        if method in ("stop", "read_state") and (self.record is None or not self._owned_alive()):
            return {"running": False, "basis": "no_owned_live_process"}
        if self.record is None:
            raise ValueError("Kikitan preflight ownership required")
        if method == "stop":
            return self._stop()
        if method == "read_state":
            return self._public_state(self._state_until(lambda state: True))
        if method == "reset_session":
            before = self.record.get("process")
            if self.record["reset_for"] is not None or self.record["start_requested"] or not self._owned_alive():
                self._exit()
                self._launch()
            self.record["reset_for"] = {key: params[key] for key in ("episode_id", "pass_id")}
            self.record["channels"] = {}
            self._save()
            return {"reset": True, "basis": "verified_application_restart", "evidence": {
                "fresh_owned_process": self.record["process"]["pid"], "creation_filetime_100ns": self.record["process"]["creation_filetime_100ns"],
                "previous_pid": before["pid"] if before else None, "fresh_initial_instance_reused": before == self.record["process"],
                "session": self.record["session"], "status": 0}}
        if method == "configure":
            return self._configure(params["requested_state"])
        if method == "identity":
            if not self._owned_alive():
                raise ProductError("crash", "Owned Kikitan exited")
            return {key: self.record["process"][key] for key in ("pid", "creation_filetime_100ns", "clock")} | {
                "executable_name": self.executable.name, "executable_sha256": self.record["executable_sha256"],
                "session": self.record["session"], "profile": self.profile, "mode": "installed_no_ui"}
        if method == "start":
            if not self.record["reset_for"] or not self.record["channels"] or self.record["start_requested"]:
                raise ValueError("Start requires one configured fresh session")
            self._state_until(lambda state: state["status"] == 0)
            self.record["start_requested"] = True
            self._save()
            self._send("control", "ON")
            self._receipt("ON_requested")
            state = self._state_until(lambda state: state["status"] == 2 or self.failure is not None)
            if self.failure:
                raise ProductError(**self.failure)
            self._receipt("observed_status2", not_continuity_proof=True)
            return self._public_state(state)
        if method == "begin_pass":
            spec = params["pass_spec"]
            if self.record["reset_for"] != {key: spec[key] for key in ("episode_id", "pass_id")}:
                raise ValueError("Pass identity differs from fresh session")
            self._receipt("begin_pass", attempt=params["attempt"], **self.record["reset_for"])
            return {"begun": True}
        if method == "liveness":
            alive = self._owned_alive()
            result = {"alive": alive, "app_continuity": {"continuous": None, "evidence": [], "gaps": []},
                      "input_continuity": {"continuous": None, "evidence": [], "gaps": []}}
            if alive:
                state = self._state_until(lambda state: True)
                result["status"] = state["status"]
                if self.record["start_requested"] and state["status"] == 0:
                    result["failure"] = {"reason": "provider", "message": "Kikitan capture stopped during active pass"}
            else:
                result["failure"] = {"reason": "crash", "message": "Owned Kikitan process exited"}
            if self.failure:
                result["failure"] = dict(self.failure)
            return result
        raise ValueError("Unknown Kikitan controller method")

    def close(self):
        if self.closed:
            return
        self.closed = True
        failure = None
        try:
            if self.record is not None:
                try:
                    self._exit()
                except Exception as error:
                    failure = error
                if self._owned_alive():
                    raise ValueError("Cannot restore settings while owned process is alive")
                self._exclusive()
                # Final compare and write share one deny-sharing handle, so a
                # concurrent writer cannot edit between check and restoration.
                original = self.codec(self.backup_path.read_bytes(), decrypt=True)
                if hashlib.sha256(original).hexdigest() != self.record["original_sha256"]:
                    raise ValueError("Private original configuration checksum differs")
                def validate(current):
                    if current == original:
                        return  # completed write before durable restoration receipt
                    allowed = [self.record["expected_hashes"], *self.record.get("pending_hashes", [])]
                    if _hashes(json.loads(current)) not in allowed:
                        raise ValueError("Concurrent settings edit; refusing restoration")
                restore_config(self.config_path, original, validate)
                if self.config_path.read_bytes() != original:
                    raise ValueError("Original configuration restoration failed")
                self._receipt("exact_settings_restored", sha256=self.record["original_sha256"])
                self.record["restored"] = True
                self._save()
                self.backup_path.unlink()
                self.pointer.unlink()
            if failure is not None:
                raise failure
        finally:
            self.lock.__exit__(None, None, None)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--profile", choices=("KIKI1", "KIKI2"), required=True)
    args = parser.parse_args(argv)
    controller = None
    code = 0
    try:
        controller = KikitanController(args.directory, args.executable, args.profile)
        for line in sys.stdin:
            request_id = None
            try:
                request = json.loads(line)
                request_id = request["id"]
                result = controller.call(request["method"], request.get("params", {}))
                reply = {"id": request_id, "result": result}
            except Exception as error:
                # Even exceptions can contain key-bearing nested JSON/URLs. No
                # exception text or traceback leaves this controller boundary.
                reply = {"id": request_id, "error": {"kind": "product" if isinstance(error, ProductError) else "operational",
                         "reason": error.reason if isinstance(error, ProductError) else _failure_reason(error),
                         "message": "Kikitan control failed: " + (error.reason if isinstance(error, ProductError) else _failure_reason(error))}}
            print(json.dumps(reply, ensure_ascii=True), flush=True)
    except Exception as error:
        print(json.dumps({"event": "operational_error", "reason": _failure_reason(error),
                          "message": "Kikitan controller unavailable: " + _failure_reason(error)}), flush=True)
        code = 2
    finally:
        if controller is not None:
            try:
                controller.close()
            except Exception as error:
                print(json.dumps({"event": "operational_error", "reason": _failure_reason(error),
                                  "message": "Kikitan cleanup failed: " + _failure_reason(error) + "; retain owner directory for recovery"}), flush=True)
                code = 2
    return code


if __name__ == "__main__":
    raise SystemExit(main())
