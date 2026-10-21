from __future__ import annotations

import base64
import json
import selectors
import socket
import struct
import threading
import time
from pathlib import Path

from .adapter import OperationalError
from .storage import Journal


def _string(data, offset):
    end = data.index(b"\0", offset)
    return data[offset:end].decode("utf-8"), (end + 4) & ~3


def decode(data):
    if data.startswith(b"#bundle\0"):
        if len(data) < 16:
            raise ValueError("Truncated OSC bundle")
        offset = 16
        result = []
        while offset < len(data):
            size = struct.unpack_from(">I", data, offset)[0]
            offset += 4
            if size == 0 or offset + size > len(data):
                raise ValueError("Invalid OSC bundle element")
            result.extend(decode(data[offset:offset + size]))
            offset += size
        return result
    address, offset = _string(data, 0)
    tags, offset = _string(data, offset)
    if not address.startswith("/") or not tags.startswith(","):
        raise ValueError("Invalid OSC address/type tags")
    args = []
    for tag in tags[1:]:
        if tag in "TFNI":
            args.append({"T": True, "F": False, "N": None, "I": "Infinity"}[tag])
        elif tag in "sS":
            value, offset = _string(data, offset)
            args.append(value)
        elif tag == "b":
            size = struct.unpack_from(">I", data, offset)[0]
            offset += 4
            if offset + size > len(data):
                raise ValueError("Truncated OSC blob")
            args.append({"base64": base64.b64encode(data[offset:offset + size]).decode("ascii")})
            offset = (offset + size + 3) & ~3
        elif tag in "ifhdtrcm":
            fmt = {"i": ">i", "f": ">f", "h": ">q", "d": ">d", "t": ">Q", "r": ">I", "c": ">I", "m": ">I"}[tag]
            value = struct.unpack_from(fmt, data, offset)[0]
            offset += struct.calcsize(fmt)
            if isinstance(value, float) and not (-float("inf") < value < float("inf")):
                value = str(value)
            args.append(value)
        else:
            raise ValueError(f"Unsupported OSC type tag: {tag}")
    if offset != len(data):
        raise ValueError("Trailing OSC bytes")
    return [(address, args)]


def encode(address, args):
    def text(value):
        raw = value.encode("utf-8") + b"\0"
        return raw + b"\0" * (-len(raw) % 4)
    tags, payload = ",", b""
    for value in args:
        if isinstance(value, bool):
            tags += "T" if value else "F"
        elif isinstance(value, str):
            tags += "s"
            payload += text(value)
        elif isinstance(value, int):
            tags += "i"
            payload += struct.pack(">i", value)
        else:
            raise ValueError("Unsupported outgoing OSC argument")
    return text(address) + text(tags) + payload


def previous_sequence(root):
    maximum = 0
    for path in Path(root).glob("stream-*.jsonl"):
        with path.open(encoding="utf-8") as source:
            for line in source:
                try:
                    maximum = max(maximum, json.loads(line).get("recv_seq", 0))
                except ValueError:
                    continue
    return maximum


class Sink:
    def __init__(self, root, run_id, session, profiles):
        self.run_id = run_id
        self.session = session
        self.journal = Journal(Path(root) / f"stream-{session}.tmp")
        self.selector = selectors.DefaultSelector()
        self.profiles = {profile["id"]: profile for profile in profiles}
        self.identities = {}
        self.context = {}
        self.history = {profile["id"]: [] for profile in profiles}
        for path in sorted(Path(root).glob("attempt-*.jsonl")):
            profile = None
            with path.open(encoding="utf-8") as source:
                for line in source:
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    if record.get("record") == "attempt_start":
                        profile = record.get("config")
                    if record.get("record") == "source_playback" and profile in self.history:
                        self.history[profile].append({key: value for key, value in record.items()
                                                      if key not in ("record", "actual_dac_observed", "audio_sha256")})
        self.targets = {}
        self.last_output = {}
        self.attempt_last_output = {}
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.failure = None
        self.sequence = previous_sequence(root)
        try:
            endpoints = {(profile["osc"]["host"], profile["osc"]["port"]) for profile in profiles}
            for host, port in sorted(endpoints):
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    sock.bind((host, port))
                    sock.setblocking(False)
                    self.selector.register(sock, selectors.EVENT_READ, (host, port))
                except BaseException:
                    sock.close()
                    raise
        except BaseException:
            for key in list(self.selector.get_map().values()):
                key.fileobj.close()
            self.selector.close()
            self.journal.finalize(".invalid.jsonl")
            raise
        self.thread = threading.Thread(target=self._receive, daemon=True)
        self.thread.start()

    def identity(self, profile, identity):
        with self.lock:
            self.identities[profile] = identity

    def record(self, record):
        with self.lock:
            self.journal.append({"run": self.run_id, "clock_session": self.session, **record})

    def attach(self, profile, context, journal):
        with self.lock:
            self.context[profile] = context
            self.targets[profile] = journal
            self.attempt_last_output[profile] = None

    def phase(self, profiles, phase, **details):
        with self.lock:
            for profile in profiles:
                self.context[profile].update(capture_phase=phase, **details)

    def source(self, profile, source):
        with self.lock:
            self.history[profile].append(source)

    def detach(self, profile):
        with self.lock:
            self.targets.pop(profile, None)

    def check(self):
        if self.failure:
            raise OperationalError(f"OSC collection failed: {self.failure}")

    def _receive(self):
        try:
            while not self.stop_event.is_set():
                for key, _ in self.selector.select(timeout=0.02):
                    # Receipt, its clock sample and publication are one admission
                    # boundary: quiet snapshots must not overtake a received packet.
                    with self.lock:
                        data, source = key.fileobj.recvfrom(65535)
                        received = time.perf_counter_ns()
                        try:
                            messages = decode(data)
                        except (ValueError, UnicodeError, struct.error, IndexError) as error:
                            self.journal.append({"t_ns": received, "run": self.run_id, "clock_session": self.session,
                                                 "diagnostic": "osc_decode_error", "source": source,
                                                 "error": str(error), "packet_base64": base64.b64encode(data).decode("ascii")})
                            continue
                        candidates = [profile for profile in self.profiles.values() if (profile["osc"]["host"], profile["osc"]["port"]) == key.data
                                      and (profile["osc"].get("source_port") is None or profile["osc"]["source_port"] == source[1])
                                      and source[0] == profile["osc"].get("source_host", "127.0.0.1")]
                        profile = candidates[0]["id"] if len(candidates) == 1 else None
                        for address, args in messages:
                            if address not in ("/chatbox/input", "/chatbox/typing"):
                                continue
                            self.sequence += 1
                            context = self.context.get(profile, {})
                            event = {"t_ns": received, "run": self.run_id, "wave": context.get("wave"),
                                     "config": profile, "direction": context.get("direction"), "chunk": context.get("chunk"),
                                     "attempt": context.get("attempt"), "observer": f"udp:{key.data[0]}:{key.data[1]}",
                                     "address": address, "args": args, "recv_seq": self.sequence,
                                     "source_host": source[0], "source_port": source[1],
                                     "process_identity": self.identities.get(profile), "clock_session": self.session,
                                     "source_candidate_provenance": list(self.history.get(profile, [])),
                                     "attribution": "unassigned" if profile is None else "endpoint_identity"}
                            phase = context.get("capture_phase")
                            if phase:
                                event["capture_phase"] = phase
                            for field in ("quiet_precondition_met", "unresolved_carryover"):
                                if field in context:
                                    event[field] = context[field]
                            nonempty = address == "/chatbox/input" and args and isinstance(args[0], str) and args[0].strip()
                            if phase == "quiet_precondition" and nonempty:
                                event["output_classification"] = "unresolved_carryover"
                            self.journal.append(event)
                            if profile in self.targets:
                                self.targets[profile].append(event)
                            if profile and nonempty:
                                self.last_output[profile] = received
                                if profile in self.targets:
                                    self.attempt_last_output[profile] = received
        except BaseException as error:
            self.failure = error

    def close(self):
        self.stop_event.set()
        self.thread.join()
        for key in list(self.selector.get_map().values()):
            key.fileobj.close()
        self.selector.close()
        return self.journal.finalize(".invalid.jsonl" if self.failure else ".jsonl")
