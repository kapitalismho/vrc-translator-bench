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
SCOPE_FIELDS = ("run", "wave", "profile", "episode_id", "pass_id", "role", "attempt_id", "window_id", "ledger")
FIELDS = {"request_id", "start", "end", "model", "upstream_provider", "key_alias", "cost", "currency", "audio_seconds", "audio_start", "audio_end", "product_retry", *TOKENS, *SCOPE_FIELDS}
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
        if self.spec.get("schema_version") != 2 or "denominators" in self.spec:
            raise ValueError("Cost specification requires schema_version 2; chunk/sentence normalization is historical only")
        self.provenance = [{"id": "spec", "kind": "specification", "sha256": digest(self.spec_path)}]
        self.paths = {self.spec_path}
        self.hashes = {self.spec_path: self.provenance[0]["sha256"]}
        self.source_ids = {"spec"}
        for evidence in self.spec.get("evidence_files", []):
            self.file(evidence["path"], identifier(evidence["id"]), "supporting_evidence")
        self.timelines = {}
        self.episode_sources = {}
        self.common = None
        self.common_binding = None
        mode = self.spec.get("mode", "episode")
        if mode not in ("episode", "historical_evidence_only"):
            raise ValueError("Cost mode must be episode or historical_evidence_only")
        if mode == "episode":
            from .quality import REPORT_VERSION
            path = self.artifact(self.spec["common_report"], "common-report", "frozen_common_report")
            self.common = json.loads(path.read_text(encoding="utf-8-sig"))
            if (self.common.get("schema_version") != 1 or self.common.get("kind") != "episode_quality"
                    or self.common.get("report_version") != REPORT_VERSION):
                raise ValueError("Costs bind the R4 common episode report, not a separate result schema")
            self._protect_manifest_paths(self.common, path.parent)
            original_spec = self.common.get("spec", {}).get("path")
            if original_spec:
                self._protect_manifest_paths(self.common, (path.parent / original_spec).resolve().parent)
            self.common_binding = {"schema_version": 1, "kind": self.common["kind"],
                                   "report_version": REPORT_VERSION, "sha256": self.hashes[path],
                                   "protocol_revision": self.common["protocol_revision"]}
            for timeline in self.spec.get("timelines", []):
                eid = identifier(timeline["episode_id"])
                artifact = self.artifact(timeline["artifact"], "timeline." + eid, "standalone_timeline")
                value = json.loads(artifact.read_text(encoding="utf-8-sig"))
                if value.get("episode_id") != eid or number(value["timeline_seconds"]) <= 0:
                    raise ValueError("Standalone timeline requires matching episode and positive timeline_seconds")
                self.timelines[eid] = {"seconds": value["timeline_seconds"], "sha256": self.hashes[artifact],
                                       "basis": "operator_supplied_hash_bound_timeline"}
        elif self.spec.get("common_report") or self.spec.get("timelines"):
            raise ValueError("Historical evidence cannot claim an episode/common-result binding")

    def artifact(self, definition, source_id, kind):
        path = self.file(definition["path"], source_id, kind)
        if self.hashes[path] != definition["sha256"]:
            raise ValueError(f"{kind} checksum differs from supplied SHA-256")
        return path

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
            if self.spec.get("mode") == "historical_evidence_only":
                raise ValueError("Historical evidence-only mode ingests retained manifests, not invented windows")
            ledger = supplied.get("ledger", "evaluation")
            keys = ("id", "run", "wave", "profile", "episode_id", "pass_id", "attempt_id", "kind", "purpose", "state", "roles", "clock_session", "pass_channels")
            row = {key: supplied.get(key) for key in keys}
            for key in ("id", "run", "wave", "profile"):
                identifier(row[key])
            if ledger == "evaluation":
                for key in ("episode_id", "pass_id"):
                    identifier(row[key])
                if row["attempt_id"] is None or not row["roles"] or set(row["roles"]) - {"A", "B"}:
                    raise ValueError("Observed evaluation windows require attempt and logical roles")
                if supplied.get("replayed_seconds") is None:
                    raise ValueError("Actual replayed_seconds required separately from observation bounds")
            if row["purpose"] not in ("main", "repeat", "preparation", "harness_retry"):
                raise ValueError("Windows require main/repeat/preparation/harness_retry purpose")
            if ledger not in ("evaluation", "production", "tts", "judge"):
                raise ValueError("Unknown cost ledger")
            row.update(ledger=ledger, attempt_id=str(row["attempt_id"]) if row["attempt_id"] is not None else None,
                       replayed_seconds=number(supplied["replayed_seconds"]) if supplied.get("replayed_seconds") is not None else None,
                       role_bindings=supplied.get("role_bindings", {}), input_complete=supplied.get("input_complete") is True,
                       start=timestamp(supplied["start"]).isoformat(), end=timestamp(supplied["end"]).isoformat(),
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
        path = (self.base / source["path"]).resolve()
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
        if manifest.get("schema_version") != 2:
            if self.spec.get("mode") != "historical_evidence_only":
                raise ValueError("Historical stage manifests require historical_evidence_only mode")
            return self._historical_manifest(source, windows, attempts)
        sid = identifier(source["id"])
        path = self.file(source["path"], sid, "run_manifest")
        if source.get("sha256") and source["sha256"] != self.hashes[path]:
            raise ValueError("Run manifest checksum differs from supplied SHA-256")
        self._protect_manifest_paths(manifest, path.parent)
        for name in ("ledger.sqlite", "frozen-plan.json", "execution-plan.json"):
            self.paths.add((path.parent / name).resolve())
        plan = manifest["plan"]
        episodes = {row["episode_id"]: row for row in plan["episodes"]}
        if len(episodes) != len(plan["episodes"]):
            raise ValueError("Frozen manifest contains duplicate episode IDs")
        for eid, episode in episodes.items():
            source_identity = {"kind": episode["kind"], "language_pair": episode["language_pair"],
                               "source_case_id": episode.get("source_case_id"),
                               "roles": {role: {key: value[key] for key in ("frames", "sample_rate", "audio_sha256")}
                                         for role, value in episode["roles"].items()}}
            if eid in self.episode_sources and self.episode_sources[eid] != source_identity:
                raise ValueError("Same episode ID has conflicting frozen source identities")
            self.episode_sources[eid] = source_identity
            if self.common:
                planned = next((row for row in self.common["planned_episodes"] if row["episode_id"] == eid), None)
                if planned and (any(planned.get(key) != episode.get(key) for key in ("kind", "language_pair"))
                                or planned.get("source_case_id") is not None and episode.get("source_case_id") is not None
                                and planned["source_case_id"] != episode["source_case_id"]):
                    raise ValueError("Frozen episode contradicts common report population")
            formats = {(row["frames"], row["sample_rate"]) for row in episode["roles"].values()}
            if len(formats) != 1:
                raise ValueError("Frozen roles must share one logical episode timeline")
            frames, rate = next(iter(formats))
            if type(frames) is not int or type(rate) is not int or frames <= 0 or rate <= 0:
                raise ValueError("Frozen timeline requires positive frames/sample_rate")
            seconds = Decimal(frames) / rate
            old = self.timelines.get(eid)
            if old and number(old["seconds"]) != seconds:
                raise ValueError("Frozen episode timelines contradict one another")
            self.timelines[eid] = {"seconds": seconds, "sha256": self.hashes[path],
                                   "basis": "frozen_episode_frames/sample_rate"}
        work = {row["id"]: row for row in manifest["work"]}
        if len(work) != len(manifest["work"]) or len({row["id"] for row in manifest["attempts"]}) != len(manifest["attempts"]):
            raise ValueError("Frozen manifest work and attempt identities must be unique")
        for attempt in manifest["attempts"]:
            item = work[attempt["work_id"]]
            matches = [row for row in plan["passes"] if row["episode_id"] == item["episode_id"]
                       and row["pass_id"] == item["pass_id"] and item["profile"] in row["profiles"]]
            if len(matches) != 1:
                raise ValueError("Attempt must bind exactly one frozen episode/profile/pass")
            physical = matches[0]
            aid = f"{sid}.attempt-{attempt['id']}"
            retained = {"id": aid, "run": manifest["run"], "profile": item["profile"],
                        "episode_id": item["episode_id"], "pass_id": item["pass_id"],
                        "attempt_id": str(attempt["id"]), "kind": item["kind"], "state": attempt["state"],
                        "number": attempt["number"], "resumed": bool(attempt["resumed"]),
                        "attempt_start": attempt["start_wall"], "attempt_end": attempt["end_wall"],
                        "window_id": None, "replayed_seconds": None,
                        "reason": attempt.get("reason") if attempt.get("reason") in (None, "interrupted", "no_output", "limit")
                                  else "source_reason_retained_locally"}
            attempts.append(retained)
            if attempt["state"] == "running":
                raise ValueError("Cannot reconcile a running capture attempt")
            trace_name = attempt.get("trace")
            if not trace_name or not (path.parent / trace_name).is_file():
                retained["window_reason"] = "Actual attempt trace unavailable; no planned input substituted"
                continue
            trace = self.artifact({"path": str(path.parent / trace_name), "sha256": attempt["checksum"]}, aid, "attempt_trace")
            rows = [json.loads(line) for line in trace.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
            anchor = next((row for row in rows if row.get("record") == "attempt_start"), None)
            if not anchor or anchor.get("wall") is None or anchor.get("t_ns") is None:
                retained["window_reason"] = "Actual wall/monotonic anchor unavailable"
                continue
            if any(anchor.get(key) != value for key, value in (
                    ("run", manifest["run"]), ("profile", item["profile"]), ("episode_id", item["episode_id"]),
                    ("pass_id", item["pass_id"]), ("attempt", attempt["id"]))):
                raise ValueError("Trace anchor contradicts manifest attempt identity")
            replay, origins, stops, actual, callback_integrity = {}, [], [], [], {}
            for channel, binding in physical["roles"].items():
                sources = [row for row in rows if row.get("record") == "source_playback" and row.get("input_channel") == channel]
                callbacks = [row for row in rows if row.get("record") == "audio_callback"
                             and row.get("input_channel") == channel]
                if not sources or not callbacks:
                    continue
                if len(sources) != 1:
                    raise ValueError("Ambiguous source playback identity")
                playback = sources[0]
                if (playback.get("clock_session") != anchor.get("clock_session")
                        or any(playback.get(key) != value for key, value in (
                            ("profile", item["profile"]), ("episode_id", item["episode_id"]), ("pass_id", item["pass_id"]),
                            ("attempt", attempt["id"]), ("role", binding["role"])))):
                    raise ValueError("Playback clock/role differs from retained attempt")
                frozen = episodes[item["episode_id"]]["roles"][binding["role"]]
                if playback.get("audio_sha256") != frozen["audio_sha256"]:
                    raise ValueError("Playback source differs from frozen episode")
                frame, previous_dac, valid = 0, None, bool(callbacks)
                for callback in callbacks:
                    first, count, dac = (callback.get(key) for key in ("source_frame", "source_frames", "dac_t_ns"))
                    if (any(type(value) is not int for value in (first, count, dac))
                            or first != frame or count < 0 or first + count > frozen["frames"]
                            or callback.get("status") != ""
                            or count and previous_dac is not None and dac < previous_dac):
                        valid = False
                        break
                    frame += count
                    if count:
                        previous_dac = dac
                valid = (valid and frame > 0
                         and next(callback["dac_t_ns"] for callback in callbacks if callback["source_frames"] > 0) == playback.get("playback_dac_start_ns"))
                callback_integrity[binding["role"]] = valid
                seconds = Decimal(frame) / frozen["sample_rate"] if valid else None
                start_ns = playback.get("input_origin_ns")
                start_ns = playback["playback_dac_start_ns"] if start_ns is None else start_ns
                start = timestamp(anchor["wall"]) + timedelta(seconds=(start_ns - anchor["t_ns"]) / 1e9)
                origins.append(start)
                if seconds is not None:
                    stops.append(start + timedelta(seconds=float(seconds)))
                replay[binding["role"]] = seconds
                actual.append(playback.get("actual_dac_observed"))
            if not replay:
                retained["window_reason"] = "No actual submitted source callbacks"
                continue
            detail = attempt.get("detail", {})
            detail = json.loads(detail) if isinstance(detail, str) else detail
            end_ns = detail.get("observation_end_ns", attempt.get("end_ns"))
            observed_end = (timestamp(anchor["wall"]) + timedelta(seconds=(end_ns - anchor["t_ns"]) / 1e9)
                            if type(end_ns) is int else timestamp(attempt["end_wall"]))
            stop = max(stops) if stops and all(value is not None for value in replay.values()) else None
            purpose = source.get("purpose", "main" if plan.get("execution_scope", {}).get("kind") == "main" else "preparation")
            execution_scope = plan.get("execution_scope", {}).get("kind")
            if purpose == "main" and execution_scope not in ("main", "synthetic"):
                raise ValueError("Main cost selection requires frozen main execution scope; pilot/preparation cannot be promoted")
            if purpose not in ("main", "repeat", "preparation", "harness_retry"):
                raise ValueError("Manifest purpose must distinguish main/repeat/preparation/harness_retry")
            roles = sorted(value["role"] for value in physical["roles"].values())
            complete = (set(replay) == set(roles) and
                        all(seconds == number(self.timelines[item["episode_id"]]["seconds"]) for seconds in replay.values())
                        and all(callback_integrity.values()))
            window = {**retained, "id": aid, "wave": physical["wave"], "roles": roles,
                      "ledger": "evaluation", "purpose": purpose, "manifest_sha256": self.hashes[path],
                      "frozen_execution_scope": execution_scope,
                      "pass_channels": {channel: value["role"] for channel, value in physical["roles"].items()},
                      "frozen_source_identity_sha256": fingerprint(self.episode_sources[item["episode_id"]]),
                      "callback_integrity": callback_integrity,
                      "start": min(origins).isoformat(), "end": max(stop or observed_end, observed_end).isoformat(),
                      "input_end": stop.isoformat() if stop else None,
                      "replayed_seconds": max(replay.values()) if all(value is not None for value in replay.values()) else None,
                      "role_replayed_seconds": replay, "input_complete": complete,
                      "actual_dac_observed": all(value is True for value in actual),
                      "clock_session": anchor.get("clock_session"), "evidence": aid,
                      "window_basis": "actual submitted callbacks per role; UTC from retained wall/monotonic anchor"}
            windows.append(window)
            retained.update(window_id=aid, replayed_seconds=window["replayed_seconds"])
            if not all(callback_integrity.values()):
                retained["window_reason"] = "Uncertain source callback accounting; replay duration is unknown for the affected role"
                window["window_reason"] = retained["window_reason"]

    def _historical_manifest(self, source, windows, attempts):
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
                      "state": attempt["state"], "historical": True,
                      "start": start.isoformat(), "end": (start + timedelta(seconds=seconds)).isoformat(),
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

    def consumption_summaries(self):
        """Retained owner summaries are evidence, not authenticated billing exports."""
        result = []
        for source in self.spec.get("consumption_summaries", []):
            if source.get("permitted") is not True or not source.get("selection_evidence"):
                raise ValueError("Retained consumption summaries require permission and inspected selection evidence")
            if source.get("ledger") not in ("production", "tts", "judge"):
                raise ValueError("Retained consumption summaries cannot enter evaluation billing")
            sid = identifier(source["id"])
            path = self.artifact(source["artifact"], sid, "retained_consumption_summary")
            document = json.loads(path.read_text(encoding="utf-8-sig"))
            self._protect_manifest_paths(document, path.parent)
            values = {}
            if set(source["fields"]) != {"known_subtotal", "total", "unknown_calls"}:
                raise ValueError("Summary mapping requires known_subtotal, total and unknown_calls")
            for key, pointer in source["fields"].items():
                value = document
                for field in pointer:
                    value = value[field]
                values[key] = value
            unknown = [identifier(call) for call in values["unknown_calls"]]
            subtotal = number(values["known_subtotal"]) if values["known_subtotal"] is not None else None
            total = number(values["total"]) if values["total"] is not None else None
            if unknown and total is not None:
                raise ValueError("Incomplete retained consumption summary cannot have a complete total")
            result.append({"id": sid, "ledger": source["ledger"], "currency": source["currency"],
                           "known_subtotal": subtotal, "total": total, "unknown_calls": unknown,
                           "status": "partial" if unknown or total is None else "complete",
                           "amount_basis": "retained_reported_model_consumption_not_native_export_or_cash_payment",
                           "selection_evidence": source["selection_evidence"],
                           "limitations": source.get("limitations"), "sha256": self.hashes[path]})
        return result

    def _source_identity(self, rows, path, source):
        source_hash = self.hashes[path]
        container = (source.get("format", source["kind"]),
                     tuple(source.get("records_path", [])) if source.get("format") == "json" else ())
        for row in rows:
            row["_source_hash"] = source_hash
            row["_record_container"] = container
        return rows


def normalize(selected, source, index):
    sid = source["id"]
    row = {"id": f"{sid}.row-{index}", "sources": [sid], "source_rows": [{"source": sid, "row": index}],
           "kind": source["kind"], "provider": source.get("provider"), "component": source.get("component"),
           "granularity": source.get("granularity", "request"),
           "scope": {key: selected.get(key, source.get("scope", {}).get(key)) for key in SCOPE_FIELDS},
           "product_retry": selected.get("product_retry"),
           "isolation_verified": source.get("isolation", {}).get("verified") is True,
           "isolation_evidence": source.get("isolation", {}).get("evidence"),
           "scope_evidence": source.get("scope_evidence"),
           "start": None, "end": None, "model": selected.get("model"), "key_alias": selected.get("key_alias"),
           "upstream_provider": selected.get("upstream_provider"),
           "currency": selected.get("currency", source.get("currency")), "request_hash": None}
    for key, value in row["scope"].items():
        if value is not None and key != "attempt_id":
            identifier(value)
    if row["product_retry"] is not None and type(row["product_retry"]) is not bool:
        raise ValueError("product_retry must be a boolean when observed")
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
