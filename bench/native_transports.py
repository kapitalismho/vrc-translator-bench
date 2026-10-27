"""Local read-only transports. No reconnect, application start or control path."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import socket
import threading
import time
from pathlib import Path
from .storage import RunLock
from urllib.parse import urlencode, urlsplit, urlunsplit

from .native_formats import LOG_TIME, VRCS_EVENTS
from .native_file import open_log_readonly
from .native_process import CLIProcess


class Transport:
    def __init__(self, sink, profile, config):
        self.sink, self.profile, self.config = sink, profile, config
        self.stopping = threading.Event()
        self.threads = []

    def thread(self, function):
        def guarded():
            try:
                function()
            except Exception as error:
                if not self.stopping.is_set():
                    # Exception strings can contain auth URLs or provider diagnostics.
                    self.record_failure(error)
        thread = threading.Thread(target=guarded, daemon=True)
        self.threads.append(thread)
        thread.start()

    def record_failure(self, error):
        self.sink.failed(self.profile, type(error).__name__)

    def stop(self):
        self.stopping.set()
        self.interrupt()
        for thread in self.threads:
            thread.join(timeout=5)
        if any(thread.is_alive() for thread in self.threads):
            raise RuntimeError("Native collector thread did not stop")

    def interrupt(self):
        pass


def loopback(host):
    if not ipaddress.ip_address(host).is_loopback:
        raise ValueError("Native collector requires a literal loopback address")
    return host


KIKITAN_URL = "ws://127.0.0.1:18378/"


def kikitan_endpoint(config):
    if set(config) != {"family", "url"} or config.get("url") != KIKITAN_URL:
        raise ValueError("Kikitan requires only family and url=ws://127.0.0.1:18378/")


class WebSocket(Transport):
    def start(self):
        from websockets.sync.client import connect

        config = self.config
        url = urlsplit(config["url"])
        loopback(url.hostname)
        if url.scheme != "ws" or url.username or url.password or url.query or url.fragment:
            raise ValueError("Use a loopback ws URL without credentials, query or fragment")
        family = config["family"]
        if family == "kikitan":
            kikitan_endpoint(config)
            # WebSockets permit duplicate clients. Serialize this endpoint across
            # harness processes so two profiles cannot consume the same app.
            directory = Path.home() / ".cache" / "vrc-translator-bench" / "kikitan-collector"
            directory.mkdir(parents=True, exist_ok=True)
            self.endpoint_owner = RunLock(directory)
            self.endpoint_owner.__enter__()
        if family == "vrcs" and url.path != "/v1/events":
            raise ValueError("VRCS collector requires /v1/events")
        self.startup_done = threading.Event()
        self.startup_error = None
        token_env = config.get("token_env")
        token = None
        if family == "vrct" or "token_env" in config:
            if not isinstance(token_env, str) or not token_env:
                raise ValueError("Native WebSocket token_env must name an environment variable")
            token = os.environ.get(token_env, "")
            if not token:
                raise ValueError("Native WebSocket token environment variable is missing or empty")
            self.sink.secret(token)
        kwargs = {"open_timeout": 5, "close_timeout": 2, "max_size": None, "max_queue": 256,
                  "proxy": None}
        if family == "vrct":
            endpoint = urlunsplit(url._replace(query=urlencode({"token": token})))
        else:
            endpoint = config["url"]
            if token is not None:
                kwargs["additional_headers"] = {"Authorization": "Bearer " + token}
        self.socket = connect(endpoint, **kwargs)
        # HTTP 101 has accepted the configured authentication, but VRCS still
        # requires its application-level subscription acknowledgement.
        if family == "vrct":
            self.sink.ready(self.profile, "authenticated_websocket_upgrade")
        elif family == "kikitan":
            self.sink.ready(self.profile, "exclusive_readonly_websocket_connected", completeness_unknown=True)
        else:
            self.connected = None
            self.subscribed = False
            self.startup_deadline = time.monotonic() + 5
            self.socket.send(json.dumps({"type": "subscribe", "events": list(VRCS_EVENTS)}))
        self.thread(self.receive)
        if family == "vrcs":
            if not self.startup_done.wait(max(0, self.startup_deadline - time.monotonic())):
                raise TimeoutError("VRCS subscription acknowledgement missing")
            if self.startup_error is not None or not self.subscribed:
                raise ConnectionError("VRCS subscription did not become ready")
            self.sink.check(self.profile)

    def record_failure(self, error):
        from websockets.exceptions import ConnectionClosed
        disconnected = isinstance(error, ConnectionClosed)
        if disconnected:
            # Framing/data, policy and extension failures remain instrumentation
            # faults, even when a separate ProductError has already been observed.
            disconnected = not any(frame is not None and frame.code in (1002, 1003, 1007, 1008, 1009, 1010)
                                   for frame in (error.rcvd, error.sent))
        self.sink.failed(self.profile, type(error).__name__, transport_disconnected=disconnected)

    def receive(self):
        try:
            self._receive()
        except Exception as error:
            self.startup_error = type(error).__name__
            self.startup_done.set()
            raise

    def _receive(self):
        family = self.config["family"]
        deadline = getattr(self, "startup_deadline", None)
        while not self.stopping.is_set():
            try:
                with self.sink.lock:
                    message = self.socket.recv(timeout=0)
                    received = time.perf_counter_ns()
                    value = self.sink.json(self.profile, family, message, received)
                    if family == "vrcs" and isinstance(value, dict):
                        kind = value.get("type")
                        if kind == "system.connected":
                            payload = value.get("payload")
                            connection = payload.get("connection_id") if isinstance(payload, dict) else None
                            if (value.get("api_version") != "1.0" or value.get("source") != "system"
                                    or not isinstance(connection, str) or not connection
                                    or value.get("message_id") != connection):
                                raise ValueError("Invalid VRCS connection acknowledgement")
                            self.connected = connection
                        elif kind == "system.subscribed":
                            payload = value.get("payload")
                            events = payload.get("events") if isinstance(payload, dict) else None
                            if (not self.connected or value.get("api_version") != "1.0"
                                    or value.get("source") != "system" or value.get("message_id") != self.connected
                                    or not isinstance(events, list) or set(events) != set(VRCS_EVENTS)):
                                raise ValueError("VRCS subscription acknowledgement differs")
                            self.subscribed = True
                        elif kind == "system.error":
                            raise ValueError("VRCS subscription rejected")
                        if self.connected and self.subscribed:
                            self.sink.ready(self.profile, "authenticated_subscription_acknowledged")
                            self.startup_done.set()
            except TimeoutError:
                if family == "vrcs" and not self.subscribed and time.monotonic() > deadline:
                    raise TimeoutError("VRCS subscription acknowledgement missing")
                self.stopping.wait(0.01)

    def interrupt(self):
        try:
            if hasattr(self, "socket"):
                self.socket.close()
        finally:
            if getattr(self, "endpoint_owner", None) is not None:
                self.endpoint_owner.__exit__(None, None, None)
                self.endpoint_owner = None


class UDP(Transport):
    def start(self):
        config = self.config
        host = loopback(config.get("host", "127.0.0.1"))
        port = config["port"]
        loopback(config.get("source_host", "127.0.0.1"))
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # No SO_REUSEADDR: a fixed endpoint must have exactly one owner.
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            self.socket.bind((host, port))
            self.socket.setblocking(False)
        except BaseException:
            self.socket.close()
            raise
        self.sink.ready(self.profile, "exclusive_udp_listener_bound", completeness_unknown=True)
        self.thread(self.receive)

    def receive(self):
        while not self.stopping.is_set():
            try:
                with self.sink.lock:
                    data, source = self.socket.recvfrom(65535)
                    received = time.perf_counter_ns()
                    self.sink.udp(self.profile, data, source, received)
            except BlockingIOError:
                self.stopping.wait(0.01)

    def interrupt(self):
        self.socket.close()


class CLI(Transport):
    def start(self):
        config = self.config
        channels = config.get("channels", ["self", "peer"])
        if not channels or len(set(channels)) != len(channels) or any(c not in ("self", "peer") for c in channels):
            raise ValueError("PuriPuly channels must be unique self/peer values")
        self.processes = []
        self.owners = []
        self.ready_channels = set()
        for channel in channels:
            args = [str(config["executable"])]
            if config.get("config_path"):
                args += ["--config", str(config["config_path"])]
            args += ["events", "follow", "--topic", "translation", "--topic", "session_state_changed",
                     "--channel", channel, "--include-translations"]
            owner = CLIProcess(args, env={**os.environ, "PYTHONUNBUFFERED": "1"})
            self.owners.append(owner)
            process = owner.process
            self.processes.append(process)
            self.thread(lambda p=process, c=channel: self.receive(p, c))
            self.thread(lambda p=process: self.stderr(p))

    def receive(self, process, channel):
        for line in iter(process.stdout.readline, b""):
            if self.stopping.is_set():
                return
            with self.sink.lock:
                received = time.perf_counter_ns()
                if not line.endswith(b"\n"):
                    self.sink.gap(self.profile, "cli_incomplete_line")
                    continue
                value = self.sink.json(self.profile, "puripuly", line, received, expected_channel=channel)
                if isinstance(value, dict) and value.get("topic") in ("translation", "session_state_changed"):
                    self.ready_channels.add(channel)
                    if self.ready_channels == set(self.config.get("channels", ["self", "peer"])):
                        self.sink.ready(self.profile, "projected_event_observed_on_each_subscription")
        if not self.stopping.is_set():
            self.sink.failed(self.profile, "cli_disconnected", transport_disconnected=True)

    def stderr(self, process):
        # Never persist stderr text: host diagnostics may disclose settings or keys.
        for line in iter(process.stderr.readline, b""):
            if not self.stopping.is_set():
                self.sink.diagnostic(self.profile, "cli_stderr", byte_count=len(line), sha256=hashlib.sha256(line).hexdigest())

    def stop(self):
        self.stopping.set()
        failures = []
        for owner in self.owners:
            try:
                owner.terminate()
            except Exception as error:
                failures.append(error)
        # Closing a buffered pipe before its reader exits can deadlock on the
        # reader's internal lock when a launcher descendant still holds stdout.
        for thread in self.threads:
            thread.join(timeout=5)
        if any(thread.is_alive() for thread in self.threads):
            raise RuntimeError("Owned CLI readers did not stop") from None
        for owner in self.owners:
            try:
                owner.close()
            except Exception as error:
                failures.append(error)
        if failures:
            raise RuntimeError("Owned CLI cleanup failed: " + type(failures[0]).__name__) from None


class FileTail(Transport):
    def start(self):
        self.file = None
        self.path = None
        self.offset = 0
        self.pending = b""
        self.pending_offset = 0
        self.fingerprint = b""
        self.current_role = None
        self._open(initial=True)
        self.sink.ready(self.profile, "read_only_file_tail_opened")
        self.thread(self.receive)

    def candidate(self):
        if "log_path" in self.config:
            return Path(self.config["log_path"])
        directory = Path(self.config["log_dir"])
        paths = list(directory.glob("vrcls-*.log"))
        if not paths:
            raise FileNotFoundError("No VRCLS log file")
        return max(paths, key=lambda path: path.name)

    def _open(self, initial=False):
        path = self.candidate()
        source = open_log_readonly(path)
        try:
            stat = os.fstat(source.fileno())
            self.path, self.file = path, source
            self.file_identity = (stat.st_dev, stat.st_ino)
            self.offset = stat.st_size if initial else 0
            # A restart is a new observation segment, never implicit history replay.
            source.seek(self.offset)
            self.pending_offset = self.offset
            self.pending = b""
            self.current_role = None
            self._fingerprint()
        except BaseException:
            source.close()
            self.file = None
            raise

    def _fingerprint(self):
        position = self.file.tell()
        self.file.seek(max(0, self.offset - 64))
        self.fingerprint = self.file.read(min(64, self.offset))
        self.file.seek(position)

    def _changed_in_place(self):
        position = self.file.tell()
        self.file.seek(max(0, self.offset - 64))
        sample = self.file.read(min(64, self.offset))
        self.file.seek(position)
        return sample != self.fingerprint

    def _read(self):
        with self.sink.lock:
            data = self.file.read()
            if not data:
                return
            received = time.perf_counter_ns()
            self.offset += len(data)
            self.pending += data
            while b"\n" in self.pending:
                line, self.pending = self.pending.split(b"\n", 1)
                line += b"\n"
                self.sink.line(self.profile, line, received, str(self.path), self.file_identity,
                               self.pending_offset, self.current_role)
                decoded = line.decode("utf-8", errors="replace")
                if LOG_TIME.match(decoded):
                    self.current_role = None
                    if "[Desktop] " in decoded:
                        self.current_role = "peer"
                    elif "[Mic] " in decoded or "FINAL [" in decoded:
                        self.current_role = "self"
                self.pending_offset += len(line)
            self._fingerprint()

    def _partial(self, reason):
        if self.pending:
            self.sink.diagnostic(self.profile, "file_partial_line", reason=reason,
                                 byte_count=len(self.pending), sha256=hashlib.sha256(self.pending).hexdigest(),
                                 offset=self.pending_offset)
            self.sink.gap(self.profile, "file_partial_line")
            self.pending = b""

    def receive(self):
        while not self.stopping.wait(0.02):
            try:
                candidate = self.candidate()
                stat = candidate.stat()
            except FileNotFoundError:
                self.sink.gap(self.profile, "file_temporarily_missing")
                # Do not reconnect and imply the interval was complete.
                raise
            identity = (stat.st_dev, stat.st_ino)
            if candidate != self.path or identity != self.file_identity:
                self._read()  # drain the old open handle, without backdating
                self._partial("rotation")
                self.file.close()
                self.sink.gap(self.profile, "log_rotation_unobserved_interval")
                self._open()
            elif stat.st_size < self.offset or self._changed_in_place():
                self._partial("truncation")
                self.sink.gap(self.profile, "log_truncated_or_rewritten")
                self.file.seek(0)
                self.offset = self.pending_offset = 0
                self.fingerprint = b""
                self.current_role = None
            self._read()
        self._read()  # final delivery uses the actual current read time
        self._partial("stop")
        self.file.close()

    def stop(self):
        try:
            super().stop()
        finally:
            if getattr(self, "file", None) is not None and not any(thread.is_alive() for thread in self.threads):
                self.file.close()

    def interrupt(self):
        # The reader owns the handle and drains it before terminating.
        pass
