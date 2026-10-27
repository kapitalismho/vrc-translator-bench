"""Read-only native collectors with independent producer and receipt clocks.

Construction opens only a journal. ``start`` opens one explicitly configured
transport after the application is ready; it never starts/configures an app.
``continuous`` is collector evidence only, never input or application liveness.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
import struct
import threading
import time
from pathlib import Path

from .adapter import OperationalError
from .native_formats import LOG_TIME, kikitan, kikitan_json, log_record, osc, puripuly, vrct, vrcs
from .native_transports import CLI, UDP, FileTail, WebSocket
from .osc import decode
from .storage import Journal


_SECRET_KEY = re.compile(r"token|secret|password|authorization|api[_-]?key|config_snapshot", re.I)


class NativeSink:
    def __init__(self, root, run_id, session, profiles):
        self.root = Path(root)
        self.run_id, self.session = run_id, session
        self.profiles = {profile["id"]: profile for profile in profiles}
        self.lock = threading.RLock()
        self.journal = Journal(self.root / f"stream-{session}.tmp")
        self.context, self.targets, self.identities = {}, {}, {}
        self.history = {profile: [] for profile in self.profiles}
        self.last_output, self.attempt_last_output = {}, {}
        self.transports, self.states = {}, {}
        self._secrets = set()
        self.sequence = 0
        self.closed = False
        self._result = None
        self._instances, self._native_sequences = {}, {}
        for profile in self.profiles:
            self.states[profile] = {"generation": 0, "connection": "not_started", "ready": False,
                                    "gaps": [], "evidence": [], "failure": None,
                                    "completeness_unknown": False}

    def _profile(self, profile):
        key = profile["id"] if isinstance(profile, dict) else profile
        if key not in self.profiles:
            raise ValueError("Unknown native collector profile")
        return key

    def secret(self, value):
        with self.lock:
            self._secrets.add(value)

    def _safe(self, value):
        if isinstance(value, dict):
            return {key: ("[REDACTED]" if _SECRET_KEY.search(str(key)) else self._safe(item))
                    for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._safe(item) for item in value]
        if isinstance(value, str):
            if "CONFIG_SNAPSHOT" in value:
                return "[REDACTED_CONFIG_SNAPSHOT]"
            for secret in self._secrets:
                value = value.replace(secret, "[REDACTED]")
        return value

    def _append(self, event, profile=None):
        if self.closed:
            raise OperationalError("Native collector journal is closed")
        self.sequence += 1
        received = event.get("collector_received_monotonic", time.perf_counter_ns())
        row = self._safe({"run": self.run_id, "clock_session": self.session,
                          **event, "stream_sequence": self.sequence,
                          "collector_received_monotonic": received, "t_ns": received})
        self.journal.append(row)
        if profile in self.targets:
            self.targets[profile].append(row)
        return row

    def record(self, record):
        with self.lock:
            self._append(record)

    def identity(self, profile, identity):
        with self.lock:
            self.identities[self._profile(profile)] = self._safe(copy.deepcopy(identity))

    def attach(self, profile, context, journal):
        with self.lock:
            profile = self._profile(profile)
            self.context[profile] = copy.deepcopy(context)
            self.targets[profile] = journal
            self.attempt_last_output[profile] = None

    def detach(self, profile):
        with self.lock:
            profile = self._profile(profile)
            self.targets.pop(profile, None)
            # Late/unattached output must not inherit a completed attempt.
            self.context.pop(profile, None)

    def phase(self, profiles, phase, **details):
        with self.lock:
            for profile in profiles:
                profile = self._profile(profile)
                self.context.setdefault(profile, {}).update(capture_phase=phase, **copy.deepcopy(details))

    def source(self, profile, source):
        with self.lock:
            self.history[self._profile(profile)].append(self._safe(copy.deepcopy(source)))

    def diagnostic(self, profile, kind, **details):
        with self.lock:
            profile = self._profile(profile)
            return self._append({"record": "native_collector_evidence", "profile": profile,
                                 "config": profile, "kind": kind, **details}, profile)

    def gap(self, profile, reason, **details):
        with self.lock:
            profile = self._profile(profile)
            row = self.diagnostic(profile, "gap", loss_or_gap=reason, **details)
            self.states[profile]["gaps"].append(row)

    def failed(self, profile, reason, *, transport_disconnected=False):
        with self.lock:
            profile = self._profile(profile)
            state = self.states[profile]
            if state["failure"] is None:
                state["failure"] = reason
            state.update(ready=False, connection="disconnected")
            # Independent readers/faults must remain visible after an initial
            # transport close; a confirmed app failure cannot hide them.
            self.gap(profile, "collector_disconnected", error_kind=reason, generation=state["generation"],
                     failure_kind="transport_disconnect" if transport_disconnected else "collector_fault")

    def ready(self, profile, reason, completeness_unknown=False):
        with self.lock:
            profile = self._profile(profile)
            state = self.states[profile]
            if state["failure"] is not None:
                return
            if not state["ready"]:
                state.update(ready=True, connection="observing", completeness_unknown=completeness_unknown)
                state["evidence"].append(self.diagnostic(profile, "collector_ready", basis=reason,
                                                         transport_completeness="unknown" if completeness_unknown else "not_reported_lost"))

    def start(self, profile):
        profile = self._profile(profile)
        with self.lock:
            if self.closed:
                raise OperationalError("Native collector journal is closed")
            if profile in self.transports:
                raise OperationalError("Native collector already started")
            config = self.profiles[profile]["collector"]
            family = config["family"]
            factory = {"puripuly": CLI, "vrct": WebSocket, "vrcs": WebSocket,
                       "vrclt": UDP, "kikitan": WebSocket, "vrcls": FileTail}.get(family)
            if factory is None:
                raise ValueError("Unsupported native collector family")
            if family == "vrclt" and not config.get("log_path"):
                raise ValueError("VRCLT requires a separate FINAL log crosscheck")
            if family == "vrclt":
                endpoint = (config.get("host", "127.0.0.1"), config["port"])
                for other in self.transports:
                    other_config = self.profiles[other]["collector"]
                    if other_config["family"] == "vrclt" and endpoint == (other_config.get("host", "127.0.0.1"), other_config["port"]):
                        raise OperationalError("OSC bind identity is already owned by another profile")
            state = self.states[profile]
            generation = state["generation"] + 1
            state.update(generation=generation, connection="starting", ready=False,
                         failure=None, completeness_unknown=False, gaps=[], evidence=[])
            self._instances.pop(profile, None)
            for key in list(self._native_sequences):
                if key[0] == profile:
                    self._native_sequences.pop(key)
            state["evidence"].append(self.diagnostic(profile, "collector_start", generation=generation))
            transport = factory(self, profile, config)
            transports = [transport]
            if family == "vrclt":
                transports.append(FileTail(self, profile, config))
            self.transports[profile] = transports
        try:
            for item in transports:
                item.start()
        except Exception as error:
            self.failed(profile, type(error).__name__)
            for item in reversed(transports):
                try:
                    item.stop()
                except Exception:
                    pass
            with self.lock:
                self.transports.pop(profile, None)
            raise OperationalError("Native collector start failed: " + type(error).__name__) from None

    def stop(self, profile):
        profile = self._profile(profile)
        with self.lock:
            transports = self.transports.get(profile)
        if transports is None:
            return
        errors = []
        for transport in reversed(transports):
            try:
                transport.stop()
            except Exception as error:
                errors.append(type(error).__name__)
        with self.lock:
            self.transports.pop(profile, None)
            self.states[profile].update(connection="stopped", ready=False)
            self.states[profile]["evidence"].append(self.diagnostic(profile, "collector_stop"))
            if errors:
                self.failed(profile, errors[0])
        if errors:
            raise OperationalError("Native collector failed to stop")

    def continuity(self, profile):
        with self.lock:
            profile = self._profile(profile)
            state = self.states[profile]
            if not state["ready"] or state["gaps"]:
                continuous = False
            elif state["completeness_unknown"]:
                continuous = None
            else:
                continuous = True
            return copy.deepcopy({"continuous": continuous, "evidence": state["evidence"],
                                  "gaps": state["gaps"], "connection": state["connection"],
                                  "generation": state["generation"],
                                  "listener_uninterrupted": state["ready"] and not state["gaps"],
                                  "transport_completeness": "unknown" if state["completeness_unknown"] else "not_reported_lost",
                                  "scope": "collector_only"})

    def check(self, profile=None):
        with self.lock:
            keys = [self._profile(profile)] if profile is not None else list(self.states)
            for key in keys:
                if self.states[key]["failure"]:
                    raise OperationalError(f"Native collector {key} disconnected: {self.states[key]['failure']}")
                if self.states[key]["gaps"]:
                    raise OperationalError(f"Native collector {key} has an observation gap")

    def _event(self, profile, fields, raw, received, transport):
        context = self.context.get(profile, {})
        channel = fields.get("input_channel")
        role = context.get("roles", {}).get(channel, {})
        metadata = self.profiles[profile].get("metadata", {})
        row = {"record": "native_output_event", "profile": profile, "config": profile,
               "app_version": self.profiles[profile].get("app_version", metadata.get("version")),
               "instance": {"asserted": self.identities.get(profile), "producer": fields.get("producer_instance")},
               **{key: context.get(key) for key in ("episode_id", "pass_id", "wave", "attempt", "capture_phase")},
               "role": role.get("role"), "source_language": role.get("source_language"),
               "target_language": role.get("target_language"),
               "attribution": "manifest_channel" if role else "unassigned",
               "transport": transport, "native_id": None, "revision": None, "update_kind": None,
               "translated_text": None, "source_text": None, "producer_time_raw": None,
               "producer_clock": None, "event_time_interval": None, "resolution": None,
               "clock_mapping": None, "uncertainty": "event_time_unmapped",
               "loss_or_gap": None, **fields,
               "collector_received_monotonic": received, "raw_evidence": raw,
               "source_candidate_provenance": list(self.history.get(profile, []))}
        texts = [row.get("translated_text"), row.get("display_text")]
        if isinstance(row.get("translated_texts"), list):
            texts.extend(row["translated_texts"])
        nonempty = any(isinstance(text, str) and text.strip() for text in texts)
        if context.get("capture_phase") == "quiet_precondition" and nonempty:
            row["output_classification"] = "unresolved_carryover"
        row = self._append(row, profile)
        if nonempty:
            self.last_output[profile] = received
            if profile in self.targets:
                self.attempt_last_output[profile] = received
        return row

    def _raw(self, data, **details):
        if isinstance(data, str):
            data = data.encode("utf-8")
        return {"sha256": hashlib.sha256(data).hexdigest(), "byte_count": len(data), **details}

    def json(self, profile, family, data, received, expected_channel=None):
        try:
            value = kikitan_json(data) if family == "kikitan" else json.loads(data)
            if not isinstance(value, dict):
                raise ValueError("Not an object")
        except (UnicodeError, ValueError, TypeError):
            self.diagnostic(profile, "invalid_native_json", raw_evidence=self._raw(data))
            self.gap(profile, "unparseable_native_message")
            return None
        if family == "kikitan":
            # Filter before any raw/base64 persistence: non-recognition data is
            # intentionally never inspected or retained, even as nested strings.
            try:
                fields = kikitan(value)
            except (ValueError, TypeError):
                self.diagnostic(profile, "invalid_recognition", raw_evidence=self._raw(data))
                self.gap(profile, "malformed_recognition")
                return None
            if fields is None:
                self.diagnostic(profile, "excluded_nonrecognition", raw_evidence=self._raw(data))
                return None
            encoded = data.encode("utf-8") if isinstance(data, str) else data
            evidence = self._raw(encoded, message_base64=base64.b64encode(encoded).decode("ascii"),
                                 original_not_persisted=False)
            self._event(profile, fields, evidence, received, "websocket")
            return value
        raw, fields = {"puripuly": puripuly, "vrct": vrct, "vrcs": vrcs}[family](value)
        evidence = self._raw(data, allowlisted_projection=raw, original_not_persisted=True)
        if not fields:
            self.diagnostic(profile, "unrecognized_native_event", raw_evidence=evidence)
            return value
        if family == "vrct" and fields.get("input_channel") == "peer":
            config = self.profiles[profile]["collector"]
            if config.get("ocr_disabled") is not True or not config.get("ocr_evidence"):
                fields.update(input_channel=None, boundary="ocr_exclusion_unverified")
                self.gap(profile, "ocr_exclusion_unverified")
        if expected_channel is not None and fields.get("input_channel") not in (None, expected_channel):
            self.gap(profile, "cli_channel_mismatch")
            fields.update(input_channel=None, boundary="cli_channel_mismatch")
        if family == "puripuly":
            instance = fields.get("producer_instance")
            previous = self._instances.get(profile)
            if instance and previous and instance != previous:
                self.gap(profile, "producer_instance_changed")
            if instance:
                self._instances[profile] = instance
            key = (profile, expected_channel)
            sequence = fields.get("native_sequence")
            if isinstance(sequence, int):
                previous = self._native_sequences.get(key)
                if previous is not None and sequence <= previous:
                    self.gap(profile, "native_sequence_not_increasing")
                self._native_sequences[key] = sequence
        if fields.get("loss_or_gap"):
            self.gap(profile, fields["loss_or_gap"], raw_evidence=evidence)
        elif fields.get("control") or fields.get("excluded"):
            self.diagnostic(profile, fields.get("control") or "excluded_native_event", raw_evidence=evidence)
        else:
            self._event(profile, fields, evidence, received, "cli_jsonl" if family == "puripuly" else "websocket")
        return value

    def udp(self, profile, data, source, received):
        config = self.profiles[profile]["collector"]
        if source[0] != config.get("source_host", "127.0.0.1") or (config.get("source_port") is not None and source[1] != config["source_port"]):
            self.diagnostic(profile, "unattributed_udp_source", source_host=source[0], source_port=source[1],
                            raw_evidence=self._raw(data))
            self.gap(profile, "unexpected_udp_sender")
            return
        try:
            messages = decode(data)
        except (ValueError, UnicodeError, struct.error, IndexError):
            self.diagnostic(profile, "osc_decode_error", raw_evidence=self._raw(data))
            self.gap(profile, "unparseable_osc_packet")
            return
        packet_allowed = all(osc(config["family"], address, args) is not None for address, args in messages)
        packet_sensitive = b"CONFIG_SNAPSHOT" in data or any(secret.encode("utf-8") in data for secret in self._secrets)
        for index, (address, args) in enumerate(messages):
            fields = osc(config["family"], address, args)
            if fields is None:
                continue
            fields.update(source_host=source[0], source_port=source[1])
            raw = self._raw(data, packet_message_index=index, allowlisted_projection={"address": address, "args": args},
                            original_not_persisted=True)
            if packet_allowed and not packet_sensitive:
                raw.update(packet_base64=base64.b64encode(data).decode("ascii"), original_not_persisted=False)
            self._event(profile, fields, raw, received, "osc_udp")

    def line(self, profile, data, received, path, identity, offset, prior_role):
        config = self.profiles[profile]["collector"]
        evidence = self._raw(data, path=path, file_identity=identity, offset=offset, end_offset=offset + len(data))
        try:
            text = data.decode("utf-8")
        except UnicodeError:
            self.diagnostic(profile, "invalid_log_encoding", raw_evidence=evidence)
            self.gap(profile, "invalid_log_encoding")
            return
        fields = log_record(config["family"], text)
        if fields and fields.get("excluded"):
            self.diagnostic(profile, "excluded_config_snapshot", raw_evidence=evidence)
            return
        if not fields:
            # Unknown/config lines are hashes only, never a copy of arbitrary logs.
            if prior_role and not LOG_TIME.match(text):
                self._event(profile, {"input_channel": prior_role, "native_endpoint": "log_continuation",
                                      "endpoint_stage": "file_log_boundary", "boundary": "multiline_log_record",
                                      "text_completeness": "unknown"}, evidence, received, "file_tail")
            return
        evidence["allowlisted_output_line"] = text.rstrip("\r\n")
        # A newline is observable now; an unframed continuation can still follow.
        fields["text_completeness"] = "physical_line_only"
        self._event(profile, fields, evidence, received, "file_tail")

    def close(self):
        if self.closed:
            return self._result
        errors = []
        for profile in list(self.transports):
            try:
                self.stop(profile)
            except OperationalError as error:
                errors.append(error)
        with self.lock:
            invalid = errors or any(state["failure"] for state in self.states.values())
            self._result = self.journal.finalize(".invalid.jsonl" if invalid else ".jsonl")
            self.closed = True
        if errors:
            raise errors[0]
        return self._result
