from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from pathlib import Path

from .storage import Journal, utc_now


class OperationalError(RuntimeError):
    pass


class ProductError(RuntimeError):
    def __init__(self, reason, message="", scope=None):
        super().__init__(message or reason)
        self.reason = reason
        self.scope = scope
        self.reached_wall = utc_now()
        self.reached_ns = time.perf_counter_ns()


def redact(value):
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if key.lower() in {"api_key", "password", "secret", "access_token", "refresh_token", "authorization"} else redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


class Adapter:
    def __init__(self, profile, root, session):
        self.profile = profile
        self.counter = 0
        self.timeout = profile.get("control_timeout_seconds", 30)
        self.responses = queue.Queue()
        self.events = queue.Queue()
        self.log = Journal(Path(root) / f"diagnostic-{profile['id']}-{session}.tmp")
        self.process = subprocess.Popen(profile["adapter"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        self.errors = threading.Thread(target=self._stderr, daemon=True)
        self.errors.start()

    def _read(self):
        try:
            for line in self.process.stdout:
                try:
                    message = json.loads(line)
                except (ValueError, TypeError):
                    self.responses.put(OperationalError("Adapter stdout must contain only protocol JSON"))
                    continue
                if not isinstance(message, dict):
                    self.responses.put(OperationalError("Adapter response must be an object"))
                elif "event" in message:
                    message["_received_t_ns"] = time.perf_counter_ns()
                    message["_received_wall"] = utc_now()
                    self.events.put(message)
                else:
                    self.responses.put(message)
        finally:
            self.responses.put(OperationalError("Adapter control process exited"))

    def _stderr(self):
        for line in self.process.stderr:
            self.events.put({"event": "diagnostic", "message": line.rstrip()})

    def _record(self, kind, value):
        self.log.append({"t_ns": time.perf_counter_ns(), "wall": utc_now(), "kind": kind, "value": redact(value)})

    def call(self, method, **params):
        self.counter += 1
        request = {"id": self.counter, "method": method, "params": params}
        self._record("request", request)
        try:
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
        except (OSError, ValueError):
            raise OperationalError("Adapter control process is unavailable") from None
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                reply = self.responses.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty:
                raise OperationalError(f"Adapter {method} timed out") from None
            if isinstance(reply, Exception):
                raise reply
            self._record("response", reply)
            if reply.get("id") != self.counter:
                raise OperationalError("Adapter response id does not match request")
            if "error" in reply:
                error = reply["error"]
                if error.get("kind") == "product":
                    raise ProductError(error.get("reason", "provider"), error.get("message", ""), error.get("scope"))
                raise OperationalError(error.get("message", "Adapter rejected control operation"))
            if not isinstance(reply.get("result"), dict):
                raise OperationalError("Adapter result must be an object")
            return reply["result"]

    def observe(self):
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                if self.process.poll() is not None or not self.reader.is_alive():
                    raise OperationalError("Adapter control process exited")
                return
            self._record("event", event)
            if event.get("event") == "product_failure":
                error = ProductError(event.get("reason", "provider"), event.get("message", ""), event.get("scope"))
                error.reached_ns = event["_received_t_ns"]
                error.reached_wall = event["_received_wall"]
                raise error
            if event.get("event") == "operational_error":
                raise OperationalError(event.get("message", "Adapter observed invalid application settings"))

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.reader.join(timeout=2)
        self.errors.join(timeout=2)
        while True:
            try:
                self._record("event", self.events.get_nowait())
            except queue.Empty:
                break
        for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
            try:
                pipe.close()
            except OSError:
                pass
        return self.log.finalize()
