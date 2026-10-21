"""Local, allowlisted cost inputs. No provider SDKs or network operations."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .storage import digest

TOKENS = ("input_tokens", "cached_tokens", "output_tokens", "reasoning_tokens")
FIELDS = {"request_id", "start", "end", "model", "upstream_provider", "key_alias", "cost", "currency", "audio_seconds", "audio_start", "audio_end", *TOKENS}
SAFE_ID = re.compile(r"[A-Za-z0-9_.:-]+\Z")


def identifier(value):
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise ValueError("Cost IDs and aliases must be non-secret safe identifiers")
    return value


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Cost timestamps require ISO-8601 strings with a timezone")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Invalid cost timestamp; ISO-8601 with timezone required") from None
    if result.utcoffset() is None:
        raise ValueError("Cost timestamps require an explicit timezone")
    return result.astimezone(timezone.utc)


def number(value):
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Cost quantities must be finite nonnegative numbers") from None
    if not result.is_finite() or result < 0:
        raise ValueError("Cost quantities must be finite nonnegative numbers")
    return result


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class Inputs:
    def __init__(self, spec_path):
        self.spec_path = Path(spec_path).resolve()
        self.base = self.spec_path.parent
        self.spec = json.loads(self.spec_path.read_text(encoding="utf-8-sig"))
        if self.spec.get("version") != 1:
            raise ValueError("Cost specification version must be 1")
        self.provenance = [{"id": "spec", "kind": "specification", "sha256": digest(self.spec_path)}]
        self.paths = {self.spec_path}
        self.hashes = {self.spec_path: self.provenance[0]["sha256"]}
        self.source_ids = {"spec"}
        for evidence in self.spec.get("evidence_files", []):
            self.file(evidence["path"], identifier(evidence["id"]), "supporting_evidence")

    def file(self, name, source_id, kind, **metadata):
        if source_id in self.source_ids:
            raise ValueError("Cost source/provenance IDs must be unique")
        self.source_ids.add(source_id)
        path = (self.base / name).resolve()
        self.paths.add(path)
        self.hashes[path] = digest(path)
        self.provenance.append({"id": source_id, "kind": kind, "sha256": self.hashes[path], **metadata})
        return path

    def _protect_manifest_paths(self, value, directory, key=""):
        """Register capture references without opening irrelevant/private payloads."""
        if isinstance(value, dict):
            for field, item in value.items():
                self._protect_manifest_paths(item, directory, "path" if key == "files" and field == "name" else field)
        elif isinstance(value, list):
            for item in value:
                self._protect_manifest_paths(item, directory, key)
        elif isinstance(value, str) and value:
            if key == "detail":
                try:
                    self._protect_manifest_paths(json.loads(value), directory)
                except ValueError:
                    pass
            path_field = key in ("path", "trace", "file", "audio", "reference", "input_plan", "ledger", "manifest", "frozen_plan", "execution_plan") or key.endswith(("_path", "_file", "_filename"))
            file_label = bool(re.fullmatch(r"\.[A-Za-z0-9_-]{1,16}", Path(value).suffix))
            if (path_field or file_label) and "://" not in value:
                self.paths.add((directory / value).resolve())

    def windows(self):
        windows, attempts = [], []
        for supplied in self.spec.get("windows", []):
            row = {key: supplied.get(key) for key in ("id", "run", "wave", "profile", "chunk", "kind", "population", "state")}
            for key in ("id", "run", "wave", "profile"):
                identifier(row[key])
            row.update(start=timestamp(supplied["start"]).isoformat(), end=timestamp(supplied["end"]).isoformat(),
                       evidence=supplied["evidence"], window_basis="explicit_observed_window")
            if timestamp(row["end"]) < timestamp(row["start"]) or not row["evidence"]:
                raise ValueError("Observed windows require ordered bounds and evidence")
            windows.append(row)
        for source in self.spec.get("manifests", []):
            self._manifest(source, windows, attempts)
        ids = [row["id"] for row in windows]
        if len(ids) != len(set(ids)):
            raise ValueError("Cost window IDs must be unique")
        return windows, attempts

    def _manifest(self, source, windows, attempts):
        sid = identifier(source["id"])
        path = self.file(source["path"], sid, "run_manifest")
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
        self._protect_manifest_paths(manifest, path.parent)
        for trace in source.get("traces", {}).values():
            self.paths.add((path.parent / trace).resolve())
        for name in ("ledger.sqlite", "frozen-plan.json", "execution-plan.json"):
            self.paths.add((path.parent / name).resolve())
        exported = {}
        if manifest.get("derived_export_notice"):
            if not source.get("export_provenance"):
                raise ValueError("Derived manifests require export_provenance linkage")
            provenance_path = self.file(source["export_provenance"], sid + ".export", "capture_export_provenance")
            provenance = json.loads(provenance_path.read_text(encoding="utf-8-sig"))
            self._protect_manifest_paths(provenance, path.parent)
            exported = {row["name"]: row for row in provenance["files"]}
            if exported[path.name]["export_sha256"] != self.hashes[path]:
                raise ValueError("Derived manifest hash differs from export provenance")
        work = {row["id"]: row for row in manifest["work"]}
        for attempt in manifest["attempts"]:
            item = work[attempt["work_id"]]
            stage = manifest["plan"]["stages"][item["stage"]]
            aid = f"{sid}.attempt-{attempt['id']}"
            retained = {"id": aid, "run": manifest["run"], "profile": item["profile"], "stage": item["stage"],
                        "kind": item["kind"], "state": attempt["state"], "work_outcome": item.get("outcome"),
                        "number": attempt["number"], "resumed": bool(attempt["resumed"]),
                        "attempt_start": attempt["start_wall"], "attempt_end": attempt["end_wall"],
                        "window_id": None, "replayed_seconds": None,
                        "reason": attempt.get("reason") if attempt.get("reason") in (None, "interrupted", "no_output", "limit") else "source_reason_retained_locally"}
            attempts.append(retained)
            if item["kind"] in ("setup", "direction", "resume_setup"):
                continue
            trace_name = source.get("traces", {}).get(str(attempt["id"]), attempt.get("trace"))
            if not trace_name:
                retained["window_reason"] = "No attempt playback trace"
                continue
            trace = path.parent / trace_name
            if not trace.is_file():
                retained["window_reason"] = "Attempt trace unavailable; no planned window substituted"
                continue
            trace = self.file(str(trace), aid, "attempt_trace", original_sha256=attempt.get("checksum"))
            expected = exported.get(trace.name, {}).get("export_sha256") if exported else attempt.get("checksum")
            if self.hashes[trace] != expected:
                raise ValueError("Attempt trace checksum differs from manifest/export provenance")
            rows = [json.loads(line) for line in trace.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
            callbacks = [row for row in rows if row.get("record") == "audio_callback" and row.get("source_frames", 0) > 0]
            anchor = next((row for row in rows if row.get("record") == "attempt_start"), None)
            playback = next((row for row in rows if row.get("record") == "source_playback"), None)
            if playback and anchor and playback.get("clock_session") != anchor.get("clock_session"):
                raise ValueError("Playback and wall-clock anchor belong to different sessions")
            if not callbacks or not anchor or not stage.get("sample_rate"):
                retained["window_reason"] = "Actual callbacks, sample rate and clock anchor required"
                continue
            frame = 0
            for callback in callbacks:
                if callback["source_frame"] != frame:
                    raise ValueError("Playback callbacks overlap or omit source frames")
                frame += callback["source_frames"]
            start_ns = playback["playback_dac_start_ns"] if playback else callbacks[0].get("dac_t_ns")
            if start_ns is None:
                retained["window_reason"] = "Actual playback start unavailable"
                continue
            seconds = frame / stage["sample_rate"]
            start = timestamp(anchor["wall"]) + timedelta(seconds=(start_ns - anchor["t_ns"]) / 1e9)
            window = {"id": aid, "run": manifest["run"], "wave": stage["wave"], "profile": item["profile"],
                      "chunk": stage.get("chunk"), "kind": item["kind"], "population": source.get("populations", {}).get(str(item["stage"]), "unspecified"),
                      "state": attempt["state"], "start": start.isoformat(), "end": (start + timedelta(seconds=seconds)).isoformat(),
                      "replayed_seconds": seconds, "attempt_id": aid, "evidence": aid,
                      "clock_session": anchor.get("clock_session"),
                      "actual_dac_observed": playback.get("actual_dac_observed") if playback else None,
                      "window_basis": "actual_submitted_callback_frames/sample_rate; UTC mapped from attempt trace wall/monotonic anchor"}
            windows.append(window)
            retained.update(window_id=aid, replayed_seconds=seconds)

    def records(self):
        records = []
        for source in self.spec.get("sources", []):
            sid = identifier(source["id"])
            if source.get("permitted") is not True:
                raise ValueError("Every local cost source requires permitted: true")
            if not source.get("selection_evidence") or not (source.get("benchmark_only") is True or source.get("select")):
                raise ValueError("Sources require an inspected benchmark_only excerpt or explicit private row selection, with selection_evidence")
            if source["kind"] == "pp_log" and source.get("benchmark_only") is not True:
                raise ValueError("PP log sources require benchmark-owned session/process selection")
            kind = source["kind"]
            path = self.file(source["path"], sid, kind, synthetic=source.get("synthetic", False),
                             selection_basis="operator_inspected_benchmark_only_excerpt" if source.get("benchmark_only") else "explicit_private_row_filter",
                             selection_evidence=source["selection_evidence"], private_filtered_row_count=0,
                             schema_validation="operator_mapped_not_provider_validated" if kind == "provider_export" else "selected_diagnostic_fields")
            if kind == "pp_log":
                parsed = parse_pp_log(path, source)
                records.extend(self._source_identity(parsed, path, source))
                continue
            if kind not in ("provider_export", "submitted_audio"):
                raise ValueError("Unknown cost source kind")
            if kind == "provider_export" and source.get("provider") not in ("openrouter", "qwen"):
                raise ValueError("Permitted provider exports are OpenRouter and Qwen")
            if source["format"] == "csv":
                with path.open(encoding="utf-8-sig", newline="") as handle:
                    rows = list(csv.DictReader(handle))
            elif source["format"] == "json":
                rows = json.loads(path.read_text(encoding="utf-8-sig"))
                for key in source.get("records_path", []):
                    rows = rows[key]
                if not isinstance(rows, list):
                    raise ValueError("Mapped JSON cost records must be an array")
            else:
                raise ValueError("Cost exports require csv or json format")
            mapping = source["fields"]
            if set(mapping) - FIELDS or set(source.get("constants", {})) - FIELDS or set(source.get("select", {})) - FIELDS:
                raise ValueError("Unknown normalized cost field")
            for index, raw in enumerate(rows, 1):
                selected = dict(source.get("constants", {}))
                for key, column in mapping.items():
                    value = raw
                    for part in column.split("."):
                        value = value.get(part) if isinstance(value, dict) else None
                    if value not in (None, ""):
                        selected[key] = value
                # Filters operate privately: unrelated rows never enter output evidence.
                if any(selected.get(key) not in values for key, values in source.get("select", {}).items()):
                    self.provenance[-1]["private_filtered_row_count"] += 1
                    continue
                for key, aliases in source.get("aliases", {}).items():
                    if key not in ("model", "key_alias"):
                        raise ValueError("Only model and key_alias can be aliased")
                    if key in selected:
                        selected[key] = aliases.get(str(selected[key]))
                records.extend(self._source_identity([normalize(selected, source, index)], path, source))
        return records

    def _source_identity(self, rows, path, source):
        source_hash = self.hashes[path]
        for row in rows:
            row["_source_hash"] = source_hash
        return rows


def normalize(selected, source, index):
    sid = source["id"]
    row = {"id": f"{sid}.row-{index}", "sources": [sid], "source_rows": [{"source": sid, "row": index}],
           "kind": source["kind"], "provider": source.get("provider"), "component": source.get("component"),
           "granularity": source.get("granularity", "request"), "scope": {key: source.get("scope", {}).get(key) for key in ("run", "wave")},
           "isolation_verified": source.get("isolation", {}).get("verified") is True,
           "isolation_evidence": source.get("isolation", {}).get("evidence"),
           "scope_evidence": source.get("scope_evidence"),
           "start": None, "end": None, "model": selected.get("model"), "key_alias": selected.get("key_alias"),
           "upstream_provider": selected.get("upstream_provider"),
           "currency": selected.get("currency", source.get("currency")), "request_hash": None}
    if row["key_alias"] is not None:
        identifier(row["key_alias"])
    if selected.get("request_id") is not None:
        row["request_hash"] = fingerprint([row["provider"], str(selected["request_id"])])
    for key in ("start", "end"):
        if selected.get(key) is not None:
            row[key] = timestamp(selected[key]).isoformat()
    for key in (*TOKENS, "cost", "audio_seconds"):
        value = selected.get(key)
        row[key] = number(value) if value is not None else None
        if key in TOKENS and row[key] is not None and row[key] != row[key].to_integral_value():
            raise ValueError("Token counts must be integers")
    if row["granularity"] != "request":
        if row["start"] is None or row["end"] is None or timestamp(row["end"]) <= timestamp(row["start"]):
            raise ValueError("Coarse exports require explicit bucket start/end")
    if row["kind"] == "submitted_audio":
        basis = source.get("basis")
        if basis not in ("vad_passed_submitted", "diagnostic_audio_sent") or not source.get("evidence"):
            raise ValueError("ASR requires evidenced actual diagnostic_audio_sent or vad_passed_submitted basis")
        if basis == "vad_passed_submitted":
            if selected.get("audio_start") is None or selected.get("audio_end") is None:
                raise ValueError("VAD-passed submitted audio requires independent source-audio interval bounds")
            begin, stop = number(selected["audio_start"]), number(selected["audio_end"])
            if stop < begin:
                raise ValueError("Submitted audio interval is reversed")
            row["audio_seconds"] = stop - begin
            row["submitted_audio_interval"] = {"start_seconds": begin, "end_seconds": stop}
        row["audio_basis"] = basis + "; request start is separate from audio interval; not replay duration"
    return row


PP_FIELDS = frozenset(("request_id utterance_id parent_utterance_id channel kind source_language target_language "
                      "provider_generation input_chars prompt_chars context_chars status request_ms queue_ms "
                      "attempts winner_attempt attempt provider model actual_model transport attempt_ms network_ms "
                      "ttft_ms first_text_to_done_ms auth_ms connection_wait_ms connect_ms connection_reused "
                      "input_tokens output_tokens cached_input_tokens reasoning_tokens requested_tier actual_tier "
                      "server_prompt_ms server_generation_ms server_generation_tps error_type http_status").split())
PP_PREFIX = re.compile(r"^(?P<wall>\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}) \[[A-Z]+\] pid=(?P<pid>\d+) [^:]+: \[Diagnostic\]\[LlmLatency\] (?P<body>.*)$")
PP_LABEL = re.compile(r"[A-Za-z0-9_./:+-]{1,128}\Z")


def parse_pp_log(path, source):
    identifier(source["session"])
    if not re.fullmatch(r"Z|[+-]\d\d:\d\d", source["timezone"]):
        raise ValueError("PP logs require an explicit session-local UTC offset, e.g. +09:00")
    if source["start_basis"] not in ("network_ms", "attempt_ms"):
        raise ValueError("PP start_basis must explicitly select network_ms or attempt_ms")
    if not source.get("timing_evidence") or not source.get("component"):
        raise ValueError("PP logs require session/process/timezone provenance and a bound component")
    rows = []
    for index, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if "[Diagnostic][LlmLatency]" not in line:
            continue
        match = PP_PREFIX.fullmatch(line)
        if not match:
            raise ValueError("PP diagnostic line does not match the production file-log prefix")
        if int(match["pid"]) != source["process_id"]:
            continue
        rows.append(parse_pp_line(match, source, index))
    return rows


def parse_pp_line(match, source, index):
    parts = match["body"].split()
    if not parts or parts[0] not in ("attempt_end", "request_end"):
        raise ValueError("Unknown PP latency event")
    values = {}
    for token in parts[1:]:
        key, separator, value = token.partition("=")
        if not separator or key not in PP_FIELDS or key in values or not PP_LABEL.fullmatch(value):
            raise ValueError("Malformed PP diagnostic fields")
        values[key] = None if value == "none" else value
    if not values.get("request_id"):
        raise ValueError("PP diagnostic requires a process-local request ID")
    event = parts[0]
    local = match["wall"].replace(" ", "T") + source["timezone"]
    end = timestamp(local)
    duration_field = "request_ms" if event == "request_end" else source["start_basis"]
    elapsed = number(values[duration_field]) if values.get(duration_field) is not None else None
    selected = {"end": end.isoformat(), "model": values.get("actual_model"),
                "key_alias": source.get("key_alias")}
    if elapsed is not None:
        selected["start"] = (end - timedelta(milliseconds=float(elapsed))).isoformat()
    if event == "attempt_end":
        for field, raw in (("input_tokens", "input_tokens"), ("output_tokens", "output_tokens"),
                           ("cached_tokens", "cached_input_tokens"), ("reasoning_tokens", "reasoning_tokens")):
            selected[field] = values.get(raw)
    row = normalize(selected, source, index)
    if values.get("provider") is not None:
        row["provider"] = source.get("provider_aliases", {}).get(values["provider"], values["provider"])
    namespace = [source["session"], source["process_id"], values["request_id"]]
    row.update(event=event, status=values.get("status"), requested_model=values.get("model"),
               actual_tier=values.get("actual_tier"), requested_tier=values.get("requested_tier"),
               logical_request_hash=fingerprint(namespace), attempt=values.get("attempt"),
               request_hash=fingerprint([*namespace, event, values.get("attempt")]),
               start_basis=f"approximate_completion_minus_{duration_field}; local_offset_operator_supplied; logging_delay_unknown",
               timing_evidence=source["timing_evidence"])
    return row
