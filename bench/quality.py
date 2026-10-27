"""Auditable episode/role quality and semantic-wait orchestration (R4).

``evaluate(spec_path, output_path, *, transport_path=None)`` never dispatches
without an explicit transport and measurements-ended assertion. The report's
populations keep profile/condition and every planned role separate.
"""
from __future__ import annotations

import json
import math
from contextlib import ExitStack
from pathlib import Path

from .activity import exclusive_activity
from .aggregation import aggregate_results
from .quality_judge import SELECTED_MODEL
from .quality_prompts import VERSION, identity, prompt, provenance, validate
from .quality_store import QualityStore, canonical
from .quality_transport import invalid_constant, load_transport
from .storage import atomic_json, digest, utc_now

REPORT_VERSION = "r4-episode-quality-v1"
OFFSETS = (0, 2, 5, 10, 15)
_DIRECTIONS = {"en-zh": {"A": ("en", "zh"), "B": ("zh", "en")},
               "ja-ko": {"A": ("ja", "ko"), "B": ("ko", "ja")}}


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be finite and numeric")
    return value


def _ns(seconds):
    return round(_number(seconds, "source timeline seconds") * 1_000_000_000)


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), parse_constant=invalid_constant)


def _artifact(binding, base):
    if not isinstance(binding, dict):
        raise ValueError("Artifact binding must contain path and sha256")
    path = (base / _text(binding.get("path"), "artifact.path")).resolve()
    expected = _text(binding.get("sha256"), "artifact.sha256")
    if digest(path) != expected:
        raise ValueError(f"Artifact checksum does not match: {path.name}")
    return path


def _protect_inputs(output_path, paths):
    for target in (output_path, output_path.with_name(output_path.name + ".tmp")):
        resolved = target.resolve()
        if any(resolved == path or target.exists() and path.exists() and target.samefile(path) for path in paths):
            raise ValueError("Quality output must not overwrite an immutable input")


class StageJudge:
    """Durable, fresh-conversation executor; use as a context manager.

    Failed/unresolved/invalid/model-mismatched calls are retained and never
    automatically repeated. A changed input gets a new immutable job. This store
    is deliberately not compatible with the historical quality queue.
    """
    def __init__(self, store_path, *, transport_path=None, expected_model=SELECTED_MODEL,
                 measurements_ended=False, judge_kind=None):
        self.root = Path(store_path)
        self.expected_model = _text(expected_model, "expected_model")
        self.transport = load_transport(transport_path) if transport_path is not None else None
        if self.transport is not None and measurements_ended is not True:
            raise ValueError("Judge dispatch requires measurements_ended: true")
        self.kind = self.transport.provenance["kind"] if self.transport else (judge_kind or "chatgpt-sign-in-bridge")
        if judge_kind is not None and judge_kind != self.kind:
            raise ValueError("Transport does not match the frozen judge_kind")
        self.halted = None
        self.stack = None

    def __enter__(self):
        self.stack = ExitStack()
        try:
            self.stack.enter_context(exclusive_activity())
            self.store = QualityStore(self.root)
            self.stack.callback(self.store.close)
            version = self.store.get("r4_schema")
            if version is None:
                if self.store.history() or self.store.get("jobs") is not None:
                    raise ValueError("Historical quality stores are not compatible with R4")
                self.store.set("r4_schema", REPORT_VERSION)
            elif version != REPORT_VERSION:
                raise ValueError("Quality store version does not match R4")
            self.store.recover()
            return self
        except BaseException:
            self.stack.close()
            raise

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def run(self, stage, data, *, bindings, errors=None):
        request = prompt(stage, data, errors)
        inputs = {"schema": REPORT_VERSION, "stage": stage, "data": data, "bindings": bindings,
                  "errors": errors, "judge_kind": self.kind, "expected_model": self.expected_model}
        input_hash = identity(inputs)
        prompt_hash = identity({"input_hash": input_hash, "request": request, "method": provenance()})
        job = {"id": f"{stage}:{prompt_hash}", "input_hash": input_hash, "prompt_hash": prompt_hash,
               "inputs": inputs, "request": request, "upstream": provenance()}
        key = "r4_job:" + prompt_hash
        old = self.store.get(key)
        if old is not None and old != job:
            raise ValueError("Immutable stage job identity conflicts with stored inputs")
        if old is None:
            self.store.set(key, job)
        common = {"stage": stage, "input_hash": input_hash, "prompt_hash": prompt_hash,
                  "job_id": job["id"], "synthetic": self.kind == "synthetic-command"}
        cached = self.store.cached(job, self.expected_model)
        if cached is not None:
            return {**common, "status": "completed", "result": cached["result"],
                    "result_hash": identity(cached["result"]), "call_id": cached["id"], "cached": True,
                    "actual_model": cached["actual_model"]}
        attempts = [row for row in self.store.history(include_raw=False)
                    if row["prompt_hash"] == prompt_hash and row["expected_model"] == self.expected_model]
        if attempts:
            row = attempts[-1]
            return {**common, "status": row["state"], "result": None, "call_id": row["id"],
                    "reason": row["reason"] or "A prior uncertain/unsuccessful call requires explicit investigation; not redispatched"}
        if self.halted:
            return {**common, "status": "blocked", "result": None, "reason": self.halted}
        if self.transport is None:
            return {**common, "status": "not_judged", "result": None, "reason": "No transport selected; local derivation only"}
        call = self.store.start(job, self.expected_model, self.transport.provenance)
        try:
            envelope = self.transport.call(request, call)
            self.store.raw(call, envelope)
        except BaseException as error:
            self.store.finish(call, "unresolved", reason=f"Transport interrupted: {type(error).__name__}; completion unknown")
            raise
        state, result = envelope.get("status"), None
        reason = envelope.get("reason")
        if state == "completed":
            evidence = envelope.get("model_identity_evidence")
            valid_evidence = (isinstance(evidence, dict) and
                              (evidence.get("synthetic") is True if self.kind == "synthetic-command" else
                               evidence.get("source") == "raw inference response.model" and
                               evidence.get("model") == envelope.get("actual_model")))
            if envelope.get("actual_model") != self.expected_model or not valid_evidence:
                state, reason = "model_mismatch", "Returned model identity is absent, unsupported, or differs from expected_model"
                self.halted = reason
            else:
                try:
                    result = validate(stage, envelope.get("content"), data)
                except (ValueError, TypeError, KeyError, OverflowError) as error:
                    state, reason = "invalid_response", str(error)
        elif state not in ("unresolved", "unavailable", "failed", "quota"):
            state, reason = "unresolved", "No recognized terminal transport status; completion unknown"
        if state in ("unresolved", "quota", "model_mismatch"):
            self.halted = reason or state
        self.store.finish(call, state, envelope, result, reason)
        return {**common, "status": state, "result": result, "call_id": call, "cached": False,
                "result_hash": identity(result) if result is not None else None,
                "actual_model": envelope.get("actual_model"), "reason": reason}

    def judge_role(self, data, *, bindings):
        errors = self.run("errors", data, bindings=bindings)
        if errors["status"] != "completed":
            return {"status": errors["status"], "score": None, "errors_stage": errors, "score_stage": None}
        score = self.run("score", data, bindings=bindings, errors=errors["result"])
        return {"status": "judged" if score["status"] == "completed" else score["status"],
                "score": score["result"]["score"] if score["result"] is not None else None,
                "score_source": "controlled_synthetic" if self.kind == "synthetic-command" else "judge",
                "errors_stage": errors, "score_stage": score}


def judge_role(data, *, store_path, transport_path=None, measurements_ended=False,
               expected_model=SELECTED_MODEL, bindings=None, judge_kind=None):
    """Public minimal two-stage API, also suitable for the authorized live sample.

    data contains source_language, target_language, source, output and context;
    bindings retain native endpoint/history/source evidence outside blinded input.
    """
    with StageJudge(store_path, transport_path=transport_path, expected_model=expected_model,
                    measurements_ended=measurements_ended, judge_kind=judge_kind) as executor:
        result = executor.judge_role(data, bindings=bindings or {"input_identity": identity(data)})
        return {"schema_version": 1, "kind": "episode_quality", "report_version": REPORT_VERSION,
                "status": "complete" if result["status"] == "judged" else "incomplete", "quality": result,
                "methodology": provenance(), "calls": executor.store.history(include_raw=False),
                "store": str(executor.root / "quality.sqlite")}


def _units(reference, kind):
    """Normalize explicit R4 units and verified R2 generator shapes, not scripts."""
    if "source_units" in reference:
        units = reference["source_units"]
    elif "references" in reference and "source_to_playback" in reference:
        rate = reference.get("sample_rate", 16000)
        mapping = {row["natural_source_key"]: row for row in reference["source_to_playback"]}
        units = []
        for row in reference["references"]:
            clock = mapping[row["natural_source_key"]]
            units.append({"id": row["natural_source_key"], "role": row["role"] if kind == "T1" else "A",
                          "original_role": row["role"], "original_person": row.get("original_person"),
                          "text": row["released_human_transcript"],
                          "start_ns": _ns(clock["playback_samples"][0] / rate),
                          "end_ns": _ns(clock["playback_samples"][1] / rate),
                          "translation_targets": row["translation_targets"],
                          "citations": [{"natural_source_key": row["natural_source_key"],
                                         "reference_utf8_sha256": row["reference_utf8_sha256"]}],
                          "uncertainty": {"reference_notes": row.get("reference_notes", []),
                                          "review_level": reference.get("review_level")}})
    elif "annotations" in reference:
        rate = reference.get("sample_rate", 16000)
        units = [{"id": row["id"], "role": row.get("logical_role", "A") if kind == "T1" else "A",
                  "original_person": row.get("speaker"), "original_person_scope": "dialogue_local", "text": row["text"],
                  "start_ns": _ns(row["playback_samples"][0] / rate),
                  "end_ns": _ns(row["playback_samples"][1] / rate),
                  "citations": [{"annotation_id": row["id"]}],
                  "uncertainty": {"uncertain_marker_present": row.get("uncertain_marker_present"),
                                  "source_review_note": row.get("source_review_note")}}
                 for row in reference["annotations"]]
    else:
        raise ValueError("Reference requires explicit R4 source_units or a verified R2 generator shape; scripts are not reviewed references")
    seen = set()
    for row in units:
        _text(row.get("id"), "source unit id")
        if row["id"] in seen or row.get("role") not in ("A", "B"):
            raise ValueError("Source units require unique IDs and explicit roles")
        seen.add(row["id"])
        _text(row.get("text"), "source unit text")
        start, end = row.get("start_ns"), row.get("end_ns")
        if any(isinstance(v, bool) or not isinstance(v, int) for v in (start, end)) or not 0 <= start <= end:
            raise ValueError("Source units require ordered relative nanosecond bounds")
        if not isinstance(row.get("citations"), list) or not row["citations"]:
            raise ValueError("Source units require raw reference citations")
    return units


def _checkpoints(reference, kind):
    values = reference.get("semantic_checkpoints", reference.get("checkpoints", []))
    seen = set()
    result = []
    for row in values:
        identifier = row.get("checkpoint_id", row.get("id"))
        _text(identifier, "checkpoint id")
        role = row.get("role", "A")
        if kind != "T1" and "references" in reference and "source_to_playback" in reference:
            role = "A"
        if identifier in seen or role not in (("A", "B") if kind == "T1" else ("A",)):
            raise ValueError("Checkpoint IDs must be unique and belong to planned roles")
        seen.add(identifier)
        if row.get("observation_offsets_seconds", list(OFFSETS)) != list(OFFSETS):
            raise ValueError("R4 checkpoints require 0/2/5/10/15-second observations")
        if "evidence_end_seconds" in row:
            seconds = row["evidence_end_seconds"]
        elif "eaf_evidence_end_seconds" in row:
            seconds = row["eaf_evidence_end_seconds"]
        elif "playback_evidence_end_sample_proposal" in row:
            seconds = row["playback_evidence_end_sample_proposal"] / reference.get("sample_rate", 16000)
        elif "evidence_end_playback_sample" in row:
            seconds = row["evidence_end_playback_sample"] / reference.get("sample_rate", 16000)
        else:
            raise ValueError("Checkpoint requires an explicit source-timeline evidence endpoint")
        if _number(seconds, "checkpoint endpoint") < 0:
            raise ValueError("Checkpoint endpoint must not be negative")
        meaning = row.get("required_concepts", row.get("required_meaning"))
        if not meaning:
            raise ValueError("Checkpoint requires explicit required meaning")
        result.append({**row, "checkpoint_id": identifier, "role": role, "evidence_end_seconds": seconds})
    return result


def _semantic_data(units, role, languages, output, *, checkpoint=None, history=None):
    source, context = [], []
    for row in units:
        context.append({"role": row["role"], "text": row["text"],
                        "original_person": row.get("original_person"), "original_role": row.get("original_role"),
                        "scored": row["role"] == role and not row.get("context_only", False),
                        "uncertainty": row.get("uncertainty")})
        if "original_person_scope" in row:
            context[-1]["original_person_scope"] = row["original_person_scope"]
        if row["role"] != role or row.get("context_only", False):
            continue
        targets = row.get("translation_targets")
        if targets is None:
            source.append(row["text"])
        else:
            for span in targets:
                left, right = span["source_characters"]
                if not 0 <= left < right <= len(row["text"]):
                    raise ValueError("Translation target span is outside its exact reference")
                source.append(row["text"][left:right])
    data = {"source_language": languages[0], "target_language": languages[1], "target_role": role,
            "source": "\n".join(source), "context": context, "output": output}
    if checkpoint is not None:
        # Only semantic definitions; no whole episode/story/future answers or product metadata.
        data["checkpoint"] = {key: checkpoint[key] for key in (
            "required_concepts", "required_meaning", "allowed_paraphrase_concepts", "output_scope") if key in checkpoint}
        data["checkpoint"]["context_constraints"] = [
            {"meaning": row["meaning"], "required_in_output": False, "translation_credit": False}
            for row in checkpoint.get("unscored_context_constraints", [])]
        # Full revisions/raw citations carry product/model/time metadata. Only
        # exact output text and local opaque indexes enter the blinded request.
        data["output_history"] = [
            {"index": index, **{key: row[key] for key in ("operation", "text", "previous_text")
                                if key in row}}
            for index, row in enumerate(history or [])]
        for index, row in enumerate(history or []):
            data["output_history"][index]["operation"] = row.get("derived_operation", row.get("operation"))
    return data


def _records(path):
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line, parse_constant=invalid_constant)
                for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    value = _load(path)
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get("events"), list):
        return value["events"]
    raise ValueError("Native history artifact must be JSONL records or an events array")


def _source_time(clock, relative_ns):
    """Map a source endpoint with Playback.source_time_ns's callback-local rule."""
    mapping = clock.get("callbacks")
    if mapping is None:
        return clock["origin_ns"] + relative_ns
    frame = round(relative_ns * clock["sample_rate"] / 1_000_000_000)
    for callback in mapping:
        if callback["source_frame"] <= frame <= callback["source_frame"] + callback["source_frames"]:
            return (callback["dac_t_ns"] + round((frame - callback["source_frame"]) / clock["sample_rate"] * 1e9)
                    + clock["calibration_offset_ns"])
    return None


def _run_source_clock(manifest, records, source, detail, episode_id, trace_sha256):
    """Validate retained frame accounting before exposing a Runner input clock."""
    episodes = [row for row in manifest.get("plan", {}).get("episodes", []) if row.get("episode_id") == episode_id]
    frozen = episodes[0].get("roles", {}).get(source["role"], {}) if len(episodes) == 1 else {}
    rate, frames = frozen.get("sample_rate"), frozen.get("frames")
    calibration = source.get("calibration", {})
    offset = calibration.get("offset_ns")
    if (not frozen.get("audio_sha256") or source.get("audio_sha256") != frozen["audio_sha256"]
            or type(rate) is not int or rate <= 0 or type(frames) is not int or frames <= 0):
        return {}, "Frozen source format or identity is not established", False
    channel = source["input_channel"]
    callbacks, position, previous_dac = [], 0, None
    for record in records:
        if record.get("record") != "audio_callback" or record.get("input_channel") != channel:
            continue
        start, count, dac = (record.get(key) for key in ("source_frame", "source_frames", "dac_t_ns"))
        if (any(type(value) is not int for value in (start, count, dac))
                or start != position or count < 0 or start + count > frames or record.get("status") != ""
                or count and previous_dac is not None and dac < previous_dac):
            return {}, "Retained source callbacks contain a gap, overlap, invalid frame or callback status", True
        position += count
        if count:
            previous_dac = dac
            callbacks.append(record)
    if not callbacks:
        return {}, "No retained source callback mapping", False
    if position != frames:
        return {}, "Retained source callbacks do not cover the complete frozen input", True
    profiles = [row for row in manifest.get("plan", {}).get("profiles", []) if row.get("id") == source.get("profile")]
    route_calibration = profiles[0].get("routes", {}).get(channel, {}).get("calibration", {}) if len(profiles) == 1 else {}
    if (source.get("actual_dac_observed") is not True or calibration.get("status") != "measured" or type(offset) is not int
            or not calibration.get("record_sha256") or not calibration.get("raw_evidence")
            or any(calibration.get(key) != route_calibration.get(key) for key in ("offset_ns", "record_sha256", "raw_evidence"))
            or not isinstance(source.get("clock_session"), str) or not source["clock_session"]):
        return {}, "Measured calibration or source clock session is not established", False
    origin = callbacks[0]["dac_t_ns"] + offset
    window = detail.get("output_windows_ns", {}).get(channel)
    if (source.get("playback_dac_start_ns") != callbacks[0]["dac_t_ns"] or source.get("input_origin_ns") != origin
            or not isinstance(window, (list, tuple)) or len(window) != 2
            or any(type(value) is not int for value in window) or window[0] != origin or window[1] < origin
            or detail.get("observation_deadline_ns") != window[1]
            or type(detail.get("observation_end_ns")) is not int or detail["observation_end_ns"] < window[1]):
        return {}, "Source origin or profile observation horizon disagrees with retained callback evidence", False
    clock = {"origin_ns": origin, "horizon_ns": window[1], "clock_session": source["clock_session"],
             "sample_rate": rate, "frames": frames, "calibration_offset_ns": offset, "callbacks": callbacks}
    common_last = detail.get("common_last_speech_seconds")
    if isinstance(common_last, bool) or not isinstance(common_last, (int, float)) or not math.isfinite(common_last) or common_last < 0:
        return {}, "No validated common final-speech boundary", False
    passes = [row for row in manifest.get("plan", {}).get("passes", [])
              if row.get("episode_id") == episode_id and row.get("pass_id") == source.get("pass_id")
              and source.get("profile") in row.get("profiles", [])]
    if len(passes) != 1 or passes[0].get("common_last_speech_seconds") != common_last:
        return {}, "Common final-speech boundary does not match the frozen selected pass", False
    common_end = _source_time(clock, _ns(common_last))
    role_horizons = detail.get("role_horizons_ns", {})
    role_horizon = role_horizons.get(channel)
    if (common_end is None or not role_horizons or any(type(value) is not int for value in role_horizons.values())
            or role_horizon != common_end + 15_000_000_000 or role_horizon > window[1]
            or window[1] != max(role_horizons.values())):
        return {}, "Common final-speech horizon is not callback-mapped", False
    horizons = [row for row in records if row.get("record") == "role_horizon" and row.get("input_channel") == channel]
    if (len(horizons) != 1 or horizons[0].get("common_last_speech_seconds") != common_last
            or horizons[0].get("common_speech_end_dac_ns") != common_end - offset
            or horizons[0].get("calibration_offset_ns") != offset or horizons[0].get("role_horizon_ns") != role_horizon
            or horizons[0].get("synthetic") is not False):
        return {}, "Retained role horizon does not confirm the callback mapping", False
    clock["evidence"] = [{"trace_sha256": trace_sha256, "source_playback": source,
                          "frozen_source": frozen, "role_horizon": horizons[0], "output_window": window}]
    return clock, None, False


def _source_prefix(bound, units, cutoff):
    from .history import source_prefix
    clock = bound["clock"]
    if "callbacks" not in clock:
        return source_prefix(units, cutoff_ns=cutoff, origin_ns=clock["origin_ns"],
                             clock_session=clock["clock_session"],
                             input_available_until_ns=clock.get("input_available_until_ns"))
    included, eligible = [], True
    for unit in units:
        unit_clock = bound["source_clocks"].get(unit["role"])
        if unit["role"] not in bound["source_clocks"]:
            # An inactive split-pass role did not enter this input stream.
            continue
        if not unit_clock or unit_clock["clock_session"] != clock["clock_session"]:
            return {"quality_eligible": False, "units": []}
        start, end = (_source_time(unit_clock, unit[key]) for key in ("start_ns", "end_ns"))
        if start is None or end is None or end < start:
            return {"quality_eligible": False, "units": []}
        if unit.get("clock_session", clock["clock_session"]) != clock["clock_session"]:
            eligible = False
        elif end <= cutoff:
            included.append(unit)
        elif start < cutoff:
            eligible = False
    return {"quality_eligible": eligible, "units": included}


def _attempt_bounds(records, attempt, work, manifest, scope):
    starts = [row for row in records if row.get("record") == "attempt_start"]
    ends = [row for row in records if row.get("record") == "attempt_end"]
    unknown = {"status": "unknown", "reason": "Selected trace lacks unique, valid attempt boundaries"}
    if len(starts) != 1 or len(ends) != 1:
        return unknown
    start, end = starts[0], ends[0]
    lower, upper = start.get("t_ns"), end.get("t_ns")
    if (type(lower) is not int or type(upper) is not int or not 0 <= lower <= upper
            or any(start.get(key) != value for key, value in (
                ("profile", work["profile"]), ("episode_id", work["episode_id"]),
                ("attempt", attempt["id"]), ("pass_id", work["pass_id"])))
            or end.get("state") != attempt["state"]
            or not isinstance(start.get("clock_session"), str) or not start["clock_session"]
            or scope.get("clock_session", start["clock_session"]) != start["clock_session"]
            or not isinstance(manifest.get("run"), str) or not manifest["run"]
            or start.get("run") != manifest["run"]):
        return unknown
    for key, boundary in (("start_ns", lower), ("end_ns", upper)):
        if key in attempt and (type(attempt[key]) is not int
                or key == "start_ns" and attempt[key] > boundary
                or key == "end_ns" and attempt[key] < boundary):
            return unknown
    return {"status": "bounded", "start_ns": lower, "end_ns": upper,
            "clock_session": start["clock_session"], "run": manifest["run"],
            "attempt_start": start, "attempt_end": end}


def _unrelated_diagnostics(events, origins, bounds, interpretations, profile):
    if bounds["status"] != "bounded":
        return []
    protected = {row.get(key) for row in interpretations or [] if isinstance(row, dict)
                 for key in ("event_index", "replaces_event_index") if type(row.get(key)) is int}
    excluded = []
    for index, (event, origin) in enumerate(zip(events, origins)):
        if (origin["source"] != "run_stream" or index in protected
                or event.get("record") != "native_collector_evidence"
                or not isinstance(event.get("loss_or_gap"), str) or not event["loss_or_gap"]
                or event.get("profile") != profile or event.get("config", profile) != profile
                or event.get("run") != bounds["run"] or event.get("clock_session") != bounds["clock_session"]
                or any(event.get(key) is not None for key in (
                    "episode_id", "attempt", "attempt_id", "pass_id", "role", "input_channel", "channel", "target_language", "capture_phase"))):
            continue
        interval = event.get("event_time_interval")
        if interval is not None:
            mapping = event.get("clock_mapping", {})
            evidence = mapping.get("evidence") if isinstance(mapping, dict) else None
            if (not isinstance(interval, dict) or interval.get("clock_session") != bounds["clock_session"]
                    or not isinstance(evidence, list) or not evidence
                    or not all(isinstance(item, str) and item.strip() for item in evidence)):
                continue
            lower, upper = interval.get("earliest_ns"), interval.get("latest_ns")
        else:
            lower = upper = event.get("collector_received_monotonic")
            if (type(event.get("t_ns")) is not int or event["t_ns"] != lower
                    or event.get("clock_mapping") is not None
                    or any(key in event for key in ("start_ns", "end_ns", "gap_start_ns", "gap_end_ns"))):
                continue
        if type(lower) is not int or type(upper) is not int or lower > upper:
            continue
        if upper < bounds["start_ns"] or lower > bounds["end_ns"]:
            excluded.append({"event_index": index, "event": event, "origin": origin,
                             "reason": "diagnostic_interval_before_selected_attempt" if upper < bounds["start_ns"]
                                       else "diagnostic_interval_after_selected_attempt"})
    return excluded


def _selection(selection, base, profile, episode_id, role):
    """Load only explicitly selected, checksummed native evidence, read-only."""
    if not isinstance(selection, dict):
        raise ValueError("Role selection must be an object")
    if ("run_manifest" in selection) == ("history" in selection):
        raise ValueError("Select exactly one run_manifest or standalone history binding")
    artifacts, origins = [], []
    manifest, source_clocks, clock_status, input_error, horizon_ns = None, {}, {}, None, None
    if "history" in selection:
        path = _artifact(selection["history"], base)
        events = _records(path)
        artifacts.append({"path": str(path), "sha256": digest(path)})
        scope = dict(selection.get("scope", {}))
        outcome = dict(selection.get("outcome", {}))
    else:
        manifest_path = _artifact(selection["run_manifest"], base)
        manifest = _load(manifest_path)
        if manifest.get("schema_version") != 2:
            raise ValueError("Only episode-native run manifest schema 2 is supported")
        matching = [a for a in manifest["attempts"] if a["id"] == selection.get("attempt_id")]
        if len(matching) != 1:
            raise ValueError("Selected attempt must exist exactly once in manifest")
        attempt = matching[0]
        work = next((w for w in manifest["work"] if w["id"] == attempt["work_id"]), None)
        if work is None or work["profile"] != profile or work["episode_id"] != episode_id or work["pass_id"] != selection.get("pass_id"):
            raise ValueError("Selected attempt does not bind planned profile, episode and pass")
        if attempt["state"] == "running":
            raise ValueError("Cannot evaluate an active capture attempt")
        trace = _artifact({"path": attempt["trace"], "sha256": attempt["checksum"]}, manifest_path.parent)
        trace_records = _records(trace)
        events = list(trace_records)
        artifacts.extend([{"path": str(manifest_path), "sha256": digest(manifest_path)},
                          {"path": str(trace), "sha256": digest(trace)}])
        origins = [{"source": "selected_trace", "artifact": artifacts[1], "record_index": index}
                   for index in range(len(trace_records))]
        for stream in manifest.get("streams", []):
            path = _artifact(stream, manifest_path.parent)
            artifact = {"path": str(path), "sha256": digest(path)}
            existing = {canonical(event) for event in events}
            for index, event in enumerate(_records(path)):
                if canonical(event) not in existing:
                    events.append(event)
                    origins.append({"source": "run_stream", "artifact": artifact,
                                    "record_index": index})
            artifacts.append(artifact)
        scope = {"episode": episode_id, "profile": profile, "attempt": attempt["id"], "pass_id": work["pass_id"],
                 **selection.get("scope", {})}
        if scope["episode"] != episode_id or scope["profile"] != profile or scope["attempt"] != attempt["id"] or scope["pass_id"] != work["pass_id"]:
            raise ValueError("Selection scope cannot override manifest attempt provenance")
        detail = attempt.get("detail", {})
        detail = json.loads(detail) if isinstance(detail, str) else detail
        outcome = {"state": attempt["state"], "reason": attempt.get("reason"), "outcome": work.get("outcome"), **detail}
        sources = [e for e in trace_records if e.get("record") == "source_playback"]
        for source in sources:
            if any(source.get(key) != value for key, value in (
                    ("profile", profile), ("episode_id", episode_id), ("attempt", attempt["id"]), ("pass_id", work["pass_id"]))):
                continue
            source_role = source.get("role")
            if source_role not in ("A", "B") or source_role in source_clocks:
                input_error = "Source role mapping is ambiguous"
                source_clocks = {}
                break
            mapped, mapping_reason, incomplete = _run_source_clock(manifest, trace_records, source, detail, episode_id, digest(trace))
            source_clocks[source_role] = mapped
            clock_status[source_role] = {"status": "mapped" if mapped else "unknown", "reason": mapping_reason}
            if incomplete:
                input_error = mapping_reason
            if source_role == role:
                if any(scope.get(key, source[field]) != source[field] for key, field in (
                        ("channel", "input_channel"), ("clock_session", "clock_session"))):
                    raise ValueError("Selection scope cannot override manifest source channel or clock session")
                scope.setdefault("channel", source["input_channel"])
                scope.setdefault("clock_session", source["clock_session"])
                window = detail.get("output_windows_ns", {}).get(source["input_channel"])
                if (isinstance(window, (list, tuple)) and len(window) == 2
                        and all(type(value) is int for value in window) and window[0] <= window[1]):
                    horizon_ns = window[1]
        if "clock" in selection:
            raise ValueError("Run-manifest clocks must derive from retained callbacks; explicit linear clocks require standalone history")
        clock = source_clocks.get(role, {})
    interpretations = selection.get("interpretations")
    if isinstance(interpretations, dict):
        path = _artifact(interpretations, base)
        interpretations = _load(path)
        artifacts.append({"path": str(path), "sha256": digest(path)})
    if interpretations is not None and not isinstance(interpretations, list):
        raise ValueError("Interpretations require an evidence-bound list or artifact")
    clock = selection.get("clock", {}) if manifest is None else clock
    required_clock = ("origin_ns", "horizon_ns", "clock_session")
    if clock and any(key not in clock for key in required_clock):
        raise ValueError("Clock binding requires origin_ns, horizon_ns and clock_session")
    if clock:
        if not clock.get("evidence"):
            raise ValueError("Clock mapping requires retained evidence")
        for key in ("origin_ns", "horizon_ns"):
            if isinstance(clock[key], bool) or not isinstance(clock[key], int):
                raise ValueError("Clock bounds must be integer nanoseconds")
        if clock["horizon_ns"] < clock["origin_ns"]:
            raise ValueError("Clock horizon cannot precede source origin")
        _text(clock["clock_session"], "clock.clock_session")
        if "input_available_until_ns" in clock and type(clock["input_available_until_ns"]) is not int:
            raise ValueError("Input availability must be integer nanoseconds")
        scope["clock_session"] = clock["clock_session"]
    bounds = _attempt_bounds(trace_records, attempt, work, manifest, scope) if manifest is not None else {"status": "standalone"}
    if manifest is not None:
        bounds["trace"] = artifacts[1]
    exclusions = _unrelated_diagnostics(events, origins, bounds, interpretations, profile)
    excluded_indexes = {row["event_index"] for row in exclusions}
    return {"events": events, "scope": scope, "outcome": outcome, "clock": clock,
            "source_clocks": source_clocks, "input_error": input_error, "horizon_ns": horizon_ns if manifest is not None else clock.get("horizon_ns"),
            "history_event_indexes": [index for index in range(len(events)) if index not in excluded_indexes],
            "diagnostic_exclusions": exclusions,
            "interpretations": interpretations, "artifacts": artifacts, "manifest": manifest,
            "binding": {"selection": selection, "artifacts": artifacts, "role": role,
                        "source_clock_kind": ("runner_callbacks" if manifest is not None else "standalone_linear") if clock else "unavailable",
                        "source_clocks": source_clocks, "source_clock_status": clock_status, "input_error": input_error,
                        "attempt_bounds": bounds, "excluded_stream_diagnostics": exclusions}}


def _outcome(bound, role):
    outcome = bound["outcome"]
    if outcome.get("state") == "invalid" or outcome.get("harness_interrupted") is True:
        return "invalid", "Harness/control/input interruption invalidates this attempt"
    if outcome.get("state") in ("unsupported", "pending", "unknown"):
        return outcome["state"], outcome.get("reason", "No established evaluation opportunity")
    if outcome.get("outcome") == "N/A":
        return "unsupported", outcome.get("reason", "Unsupported direction; no played opportunity")
    # The native runner's per-role proof is intentionally not inferred from process liveness.
    role_outcome = outcome.get("roles", {}).get(role, outcome.get("role_outcomes", {}).get(role, {}))
    if isinstance(role_outcome, str):
        role_outcome = {"outcome": role_outcome}
    name = role_outcome.get("outcome", role_outcome.get("status", outcome.get("outcome")))
    if name == "unsupported":
        return "unsupported", role_outcome.get("reason", "Unsupported target direction")
    if bound["input_error"]:
        return "unknown", bound["input_error"]
    opportunity = role_outcome.get("opportunity", outcome.get("opportunity", {}))
    opportunity = opportunity if isinstance(opportunity, dict) else {}
    continuity = outcome.get("continuity_established", {})
    complete = (all(opportunity.get(key) is True for key in (
        "input_complete", "app_opportunity", "observation_complete")) or
        (outcome.get("opportunity_established") is True and outcome.get("synthetic") is False
         and all(continuity.get(key) is True for key in ("app", "input", "collector"))))
    if name == "product_no_output" and complete and (bound["manifest"] is None or bound["clock"]):
        return "no_output", "Complete established input/app/observation opportunity; protocol-defined zero"
    if name in ("unknown_no_output", "product_no_output"):
        return "unknown", "No-output opportunity is not completely established"
    return "eligible", None


def _final_input_reason(bound, units, role):
    available = bound["clock"].get("input_available_until_ns")
    if available is None:
        return None
    for unit in units:
        if unit["role"] != role:
            continue
        end = _source_time(bound["clock"], unit["end_ns"])
        if end is None or end > available:
            return "Retained input availability ends before the full required role input; final quality is unavailable"
    return None


def _restore_history_indexes(history, indexes):
    """Restore derived view indexes without touching raw event/rule payloads."""
    visited = set()
    def item_id(value):
        if isinstance(value, str) and value.startswith("event:") and value[6:].isdigit():
            index = int(value[6:])
            if index < len(indexes):
                return "event:" + str(indexes[index])
        return value
    def visit(value):
        if not isinstance(value, (dict, list)) or id(value) in visited:
            return
        visited.add(id(value))
        if isinstance(value, list):
            for child in value:
                visit(child)
            return
        for key in ("event_index", "replaces_event_index"):
            index = value.get(key)
            if type(index) is int and 0 <= index < len(indexes):
                value[key] = indexes[index]
        if "derived_item_id" in value:
            value["derived_item_id"] = item_id(value["derived_item_id"])
        if "archived_item_ids" in value:
            value["archived_item_ids"] = [item_id(item) for item in value["archived_item_ids"]]
        for key, child in value.items():
            if key not in ("event", "raw_evidence", "rule"):
                visit(child)
    visit(history)
    return history


def _history(bound, role, cutoff=None):
    from .history import event_sha256, reconstruct_history
    exclusions = bound["diagnostic_exclusions"]
    if not exclusions:
        return reconstruct_history(bound["events"], role=role, cutoff_ns=cutoff,
                                   horizon_ns=bound["horizon_ns"],
                                   interpretations=bound["interpretations"], **bound["scope"])
    indexes = bound["history_event_indexes"]
    positions = {raw: view for view, raw in enumerate(indexes)}
    interpretations = []
    for row in bound["interpretations"] or []:
        if not isinstance(row, dict):
            interpretations.append(row)  # Let the shared validator reject it.
            continue
        mapped = dict(row)
        for key in ("event_index", "replaces_event_index"):
            if type(row.get(key)) is int and row[key] in positions:
                mapped[key] = positions[row[key]]
        interpretations.append(mapped)
    history = reconstruct_history([bound["events"][index] for index in indexes], role=role, cutoff_ns=cutoff,
                                  horizon_ns=bound["horizon_ns"], interpretations=interpretations, **bound["scope"])
    _restore_history_indexes(history, indexes)
    for row in exclusions:
        event = row["event"]
        history["excluded_events"].append({
            "citation": {"event_index": row["event_index"], "event_sha256": event_sha256(event),
                         "stream_sequence": event.get("stream_sequence"), "raw_evidence": event.get("raw_evidence")},
            "reason": row["reason"]})
    return history


def _no_output_observed(history):
    """An empty primary field is not proof that an entire native record is empty."""
    if (history["uncertain_events"] or history["timing_reasons"]
            or set(history["reasons"]) - {"no_scoped_native_events", "no_admitted_native_output"}
            or any(row["reason"] == "scope_clock_session" for row in history["excluded_events"])):
        return False
    for row in history["events"]:
        event = row["event"]
        for field in ("translated_text", "display_text"):
            if field in event and (not isinstance(event[field], str) or event[field].strip()):
                return False
        if "translated_texts" in event:
            values = event["translated_texts"]
            if not isinstance(values, list) or any(not isinstance(text, str) or text.strip() for text in values):
                return False
        if not any(field in event for field in ("translated_text", "display_text", "translated_texts")):
            if row["derived_operation"] not in ("clear", "delete", "ignore"):
                return False
    return True


def _missing_checkpoints(checkpoints, reason):
    return [{"checkpoint_id": row["checkpoint_id"], "status": "unknown", "interval_seconds": None,
             "reason": reason, "observations": []} for row in checkpoints]

def _stage_bindings(bound, units, history):
    """Identity only of this stage's available evidence, not future/late data.

    The report retains full checksummed artifact/selection/cost provenance. Stage
    jobs durably retain the actual source units and visible raw events below;
    appending an excluded late event cannot invalidate an earlier snapshot.
    """
    return {"protocol_revision": bound["binding"]["protocol_revision"],
            "measurement_condition": bound["binding"]["measurement_condition"],
            "condition": bound["binding"]["condition"],
            "source_units": units, "native_scope": history["scope"],
            "native_events": history["events"], "native_revisions": history["revisions"],
            "native_items": history["items"]}



def _checkpoint_results(executor, bound, role, units, languages, checkpoints, *, no_output=False):
    results = []
    clock = bound["clock"]
    for cp in checkpoints:
        observations, first, last_unmet, unknown_before = [], None, 0, False
        reversals, corrections = [], []
        seen_revisions = 0
        for offset in OFFSETS:
            if not clock:
                observations.append({"offset_seconds": offset, "status": "unknown", "reason": "No validated per-pass input clock binding"})
                unknown_before = True
                continue
            evidence_end = _source_time(clock, _ns(cp["evidence_end_seconds"]))
            if evidence_end is None:
                observations.append({"offset_seconds": offset, "status": "unknown", "reason": "Checkpoint source endpoint has no callback mapping"})
                unknown_before = True
                continue
            available = clock.get("input_available_until_ns")
            if available is not None and evidence_end > available:
                observations.append({"offset_seconds": offset, "status": "unknown", "reason": "Required checkpoint source was not fully input"})
                unknown_before = True
                continue
            cutoff = evidence_end + _ns(offset)
            if cutoff > clock["horizon_ns"]:
                observations.append({"offset_seconds": offset, "status": "unknown", "reason": "Observation horizon ended before checkpoint"})
                unknown_before = True
                continue
            prefix = _source_prefix(bound, units, cutoff)
            snapshot = _history(bound, role, cutoff)
            if no_output and prefix["quality_eligible"]:
                decision = {"status": "unmet", "reason": "Established complete no-output opportunity", "evidence": []}
                stage = None
            elif not prefix["quality_eligible"] or not snapshot["timing_eligible"]:
                decision = {"status": "unknown", "reason": "Source/native clock or output history is ambiguous", "evidence": []}
                stage = None
            else:
                data = _semantic_data(prefix["units"], role, languages, snapshot["text"],
                                      checkpoint=cp, history=snapshot.get("revisions", []))
                if not data["source"].strip():
                    decision = {"status": "unknown", "reason": "Required source meaning is not yet available", "evidence": []}
                    stage = None
                else:
                    stage = executor.run("checkpoint", data, bindings={
                                         **_stage_bindings(bound, prefix["units"], snapshot),
                                         "checkpoint_id": cp["checkpoint_id"], "offset_seconds": offset})
                    decision = stage["result"] if stage["status"] == "completed" else {
                        "status": "unknown", "reason": stage.get("reason", stage["status"]), "evidence": []}
            status = decision["status"]
            revisions = snapshot.get("revisions", [])
            operations = {r.get("derived_operation", r.get("operation", r.get("update_kind")))
                          for r in revisions[seen_revisions:]}
            seen_revisions = max(seen_revisions, len(revisions))
            reversal = bool(decision.get("reversal") and "replace" in operations)
            correction = bool(decision.get("correction") and "replace" in operations)
            observations.append({"offset_seconds": offset, "cutoff_ns": cutoff, "source_evidence_end_ns": evidence_end,
                                 **decision, "reversal": reversal, "correction": correction,
                                 "judgment": stage, "native_citations": snapshot.get("items", [])})
            observations[-1]["native_history_citations"] = [
                {"index": index, "citation": row["citation"]} for index, row in enumerate(revisions)]
            if status == "met" and first is None:
                first = [0 if unknown_before else last_unmet, offset]
            elif first is None and status == "unmet":
                last_unmet = offset
            elif first is None:
                unknown_before = True
            # Only a newly observed substantive replacement can reverse/correct
            # meaning; archived clear/delete and unchanged snapshots cannot.
            if reversal:
                reversals.append(offset)
            if correction:
                corrections.append(offset)
        status = "met" if first is not None else "unmet" if observations and all(o["status"] == "unmet" for o in observations) else "unknown"
        results.append({"checkpoint_id": cp["checkpoint_id"], "status": status, "interval_seconds": first,
                        "observations": observations, "first_met": first, "later_reversals_seconds": reversals,
                        "later_corrections_seconds": corrections, "source_checkpoint": cp})
    return results


def _condition_selection(bound, episode, role, condition):
    channel = condition["roles"][role] if episode["kind"] == "T1" else condition["ordinary_input"]
    pass_id = (role if condition["t1_mode"] == "split_self" else "simultaneous") if episode["kind"] == "T1" else "ordinary-" + channel
    roles = ({channel: role} if episode["kind"] != "T1" or condition["t1_mode"] == "split_self"
             else {value: key for key, value in condition["roles"].items()})
    scope = bound["scope"]
    if scope.get("channel", channel) != channel:
        raise ValueError("Selected physical channel contradicts the authoritative measurement condition")
    selected_pass = scope.get("pass_id")
    semantic_passes = {"A", "B", "simultaneous", "ordinary-self", "ordinary-peer"}
    if selected_pass in semantic_passes and selected_pass != pass_id:
        raise ValueError("Selected pass contradicts the authoritative measurement condition")
    if bound["manifest"] is not None:
        passes = [row for row in bound["manifest"].get("plan", {}).get("passes", [])
                  if row.get("episode_id") == episode["episode_id"] and row.get("pass_id") == selected_pass
                  and scope["profile"] in row.get("profiles", [])]
        if (selected_pass != pass_id or len(passes) != 1
                or {key: value.get("role") for key, value in passes[0].get("roles", {}).items()} != roles):
            raise ValueError("Frozen pass role/channel routing contradicts the authoritative measurement condition")
    for event in bound["events"]:
        if event.get("record") not in ("native_output_event", "source_playback"):
            continue
        if event.get("capture_phase") in ("quiet_precondition", "preparation", "startup"):
            continue
        if any(event.get(field) is not None and value is not None and event[field] != value for field, value in (
                ("profile", scope.get("profile")), ("episode_id", episode["episode_id"]),
                ("attempt", scope.get("attempt")), ("pass_id", selected_pass),
                ("run", scope.get("run")), ("wave", scope.get("wave")))):
            continue
        actual_role = event.get("role")
        actual_channel = event.get("input_channel", event.get("channel"))
        if (actual_channel is not None and actual_channel not in roles
                or actual_role is not None and (actual_role not in roles.values()
                    or actual_channel is not None and roles.get(actual_channel) != actual_role)):
            raise ValueError("Native role/channel evidence contradicts the authoritative measurement condition")


def _measurement_condition(population, bindings, episodes, catalog, catalog_artifact):
    profile, label = population["profile"], population["measurement_condition"]
    canonical_profile = next((row for row in catalog["profiles"] if row["id"] == profile), None)
    condition = canonical_profile["native_protocol"]["condition"] if canonical_profile else None
    evidence = [{"source": "profile_catalog", **catalog_artifact, "profile": profile}] if condition else []
    declared = population.get("condition")
    candidates = [(declared, {"source": "explicit_population"})] if declared is not None else []
    for bound in bindings.values():
        if bound["manifest"] is None:
            continue
        profiles = [row for row in bound["manifest"].get("plan", {}).get("profiles", []) if row.get("id") == profile]
        if len(profiles) == 1 and profiles[0].get("condition") is not None:
            candidates.append((profiles[0]["condition"], {
                "source": "run_manifest", **bound["artifacts"][0], "profile": profile}))
    for candidate, citation in candidates:
        if condition is not None and candidate != condition:
            raise ValueError("Profile/manifest/population measurement conditions contradict one another")
        condition = candidate
        evidence.append(citation)
    if condition is None:
        return {"condition": {"label": label}, "evidence": [{"source": "explicit_population"}]}
    if (not isinstance(condition, dict) or condition.get("ordinary_input") not in ("self", "peer")
            or condition.get("t1_mode") not in ("split_self", "simultaneous")
            or not isinstance(condition.get("roles"), dict) or set(condition["roles"]) != {"A", "B"}
            or any(value not in ("self", "peer") for value in condition["roles"].values())
            or condition["t1_mode"] == "split_self" and set(condition["roles"].values()) != {"self"}
            or condition["t1_mode"] == "simultaneous" and len(set(condition["roles"].values())) != 2):
        raise ValueError("Structured measurement condition requires physical input, T1 mode and A/B channels")
    expected_label = condition["ordinary_input"] + ("/split" if condition["t1_mode"] == "split_self" else "/simultaneous")
    if label != expected_label:
        raise ValueError(f"measurement_condition must be {expected_label!r} for the authoritative profile condition")
    for (episode_id, role), bound in bindings.items():
        if bound["scope"].get("profile", profile) != profile:
            raise ValueError("Selected profile scope contradicts the authoritative measurement condition")
        episode = next(row for row in episodes if row["episode_id"] == episode_id)
        _condition_selection(bound, episode, role, condition)
    return {"condition": condition, "evidence": evidence}


def evaluate(spec_path, output_path, *, transport_path=None):
    """Evaluate the explicit frozen episode and selected-attempt specification."""
    spec_path, output_path = Path(spec_path).resolve(), Path(output_path).resolve()
    spec = _load(spec_path)
    if spec.get("schema_version") != 1:
        raise ValueError("R4 evaluation specification requires schema_version 1")
    _text(spec.get("protocol_revision"), "protocol_revision")
    if not isinstance(spec.get("episodes"), list) or not spec["episodes"] or not isinstance(spec.get("populations"), list) or not spec["populations"]:
        raise ValueError("Explicit planned episodes and profile/condition populations are required")
    episodes, reference_data = [], {}
    for episode in spec["episodes"]:
        identifier = _text(episode.get("episode_id"), "episode_id")
        if identifier in reference_data or episode.get("language_pair") not in _DIRECTIONS or episode.get("kind") not in ("P1", "P2", "P3", "P4", "T1", "C1"):
            raise ValueError("Planned episode identity, language_pair or kind is invalid")
        path = _artifact(episode["reference"], spec_path.parent)
        reference = _load(path)
        if episode["reference"].get("case_id") is not None:
            cases = reference.get("episodes", reference.get("cases", []))
            matches = [c for c in cases if c.get("id", c.get("episode_id")) == episode["reference"]["case_id"]]
            if len(matches) != 1:
                raise ValueError("Reference case_id must select exactly one case")
            reference = matches[0]
        if reference.get("source_case_id", reference.get("id")) != episode.get("source_case_id", identifier):
            raise ValueError("Reference source case does not match planned episode")
        units = [] if episode["kind"] == "C1" else _units(reference, episode["kind"])
        checkpoints = _checkpoints(reference, episode["kind"])
        roles = ("A", "B") if episode["kind"] == "T1" else ("A",)
        if episode["kind"] != "C1" and any(not any(cp["role"] == role for cp in checkpoints) for role in roles):
            raise ValueError("Every planned scored role requires explicit semantic checkpoints")
        planned = {**episode, "checkpoint_ids": {role: [cp["checkpoint_id"] for cp in checkpoints if cp["role"] == role] for role in roles}}
        episodes.append(planned)
        reference_data[identifier] = {"reference": reference, "units": units, "checkpoints": checkpoints,
                                      "artifact": {"path": str(path), "sha256": digest(path)}}
    input_paths = {spec_path, *(Path(ref["artifact"]["path"]) for ref in reference_data.values())}
    if transport_path is not None:
        input_paths.add(Path(transport_path).resolve())
    catalog_path = Path(__file__).resolve().parent.parent / "profiles" / "catalog.json"
    catalog = _load(catalog_path)
    catalog_artifact = {"path": str(catalog_path), "sha256": digest(catalog_path)}
    input_paths.add(catalog_path)
    prepared, seen = [], set()
    for population in spec["populations"]:
        profile = _text(population.get("profile"), "population.profile")
        condition = _text(population.get("measurement_condition"), "measurement_condition")
        if (profile, condition) in seen:
            raise ValueError("Duplicate profile/measurement-condition population")
        seen.add((profile, condition))
        selections, bindings = {}, {}
        for row in population.get("roles", []):
            key = row.get("episode_id"), row.get("role")
            if key in selections or key[0] not in reference_data:
                raise ValueError("Duplicate or unplanned selected role")
            planned = next(e for e in episodes if e["episode_id"] == key[0])
            if key[1] not in planned["checkpoint_ids"]:
                raise ValueError("Selected role is outside planned episode")
            selections[key] = row
            if row.get("selection") is not None:
                bindings[key] = _selection(row["selection"], spec_path.parent, profile, *key)
                input_paths.update(Path(artifact["path"]) for artifact in bindings[key]["artifacts"])
        condition_binding = _measurement_condition(population, bindings, episodes, catalog, catalog_artifact)
        prepared.append((population, profile, condition, selections, bindings, condition_binding))
    _protect_inputs(output_path, input_paths)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    populations = []
    with StageJudge(str(output_path) + ".store", transport_path=transport_path,
                    measurements_ended=spec.get("measurements_ended", False),
                    expected_model=spec.get("expected_model", SELECTED_MODEL), judge_kind=spec.get("judge_kind")) as executor:
        for population, profile, condition, selections, bindings, condition_binding in prepared:
            role_results = []
            for episode in episodes:
                identifier, kind = episode["episode_id"], episode["kind"]
                ref = reference_data[identifier]
                for role in episode["checkpoint_ids"]:
                    languages = _DIRECTIONS[episode["language_pair"]][role]
                    cps = [cp for cp in ref["checkpoints"] if cp["role"] == role]
                    row = selections.get((identifier, role))
                    result = {"episode_id": identifier, "role": role, "source_language": languages[0],
                              "target_language": languages[1], "measurement_condition": condition,
                              "condition": condition_binding["condition"], "condition_evidence": condition_binding["evidence"],
                              "selection": row.get("selection") if row else None,
                              "cost_binding_id": (row.get("cost_binding_id") if row else None) or episode.get("cost_binding_id")}
                    if row is None or row.get("selection") is None:
                        reason = row.get("reason", "Planned role has no selected attempt") if row else "Planned role has no selected attempt"
                        result.update(quality={"status": "missing_attempt", "score": None, "reason": reason},
                                      checkpoints=_missing_checkpoints(cps, reason))
                    else:
                        bound = bindings[(identifier, role)]
                        bound["binding"].update(reference=ref["artifact"], protocol_revision=spec["protocol_revision"],
                                                measurement_condition=condition, condition=condition_binding["condition"],
                                                condition_evidence=condition_binding["evidence"])
                        status, reason = _outcome(bound, role)
                        history = _history(bound, role)
                        result.update(history=history, outcome=bound["outcome"], provenance=bound["binding"])
                        if kind == "C1":
                            result.update(quality={"status": "control", "score": None, "reason": "No translatable meaning; excluded from primary metrics"}, checkpoints=[])
                        elif status not in ("eligible", "no_output"):
                            result.update(quality={"status": status, "score": None, "reason": reason}, checkpoints=_missing_checkpoints(cps, reason))
                        elif ref["reference"].get("quality_eligible") is False:
                            reason = "Reference explicitly declares unresolved/unsupported scored meaning"
                            result.update(quality={"status": "unknown_reference", "score": None, "reason": reason},
                                          checkpoints=_missing_checkpoints(cps, reason))
                        elif (input_reason := _final_input_reason(bound, ref["units"], role)) is not None:
                            result.update(quality={"status": "unknown_input", "score": None, "reason": input_reason},
                                          checkpoints=_checkpoint_results(executor, bound, role, ref["units"], languages, cps))
                        elif status == "no_output" and _no_output_observed(history):
                            data = _semantic_data(ref["units"], role, languages, "")
                            if not data["source"].strip():
                                result.update(quality={"status": "unknown_reference", "score": None, "reason": "No nonempty translation target"},
                                              checkpoints=_missing_checkpoints(cps, "No nonempty translation target"))
                            else:
                                result.update(quality={"status": "no_output", "score": 0, "score_source": "protocol", "reason": reason,
                                                       "errors_stage": None, "score_stage": None},
                                              checkpoints=_checkpoint_results(executor, bound, role, ref["units"], languages, cps, no_output=True))
                        elif status == "no_output" and (not history["quality_eligible"] or not (history.get("text") or "").strip()):
                            reason = "Native evidence does not establish total no-output"
                            result.update(quality={"status": "unknown_output", "score": None, "reason": reason},
                                          checkpoints=_missing_checkpoints(cps, reason))
                        elif not history["quality_eligible"] or not (history.get("text") or "").strip():
                            reason = "Native output relation/completeness or opportunity is unknown"
                            result.update(quality={"status": "unknown_output", "score": None, "reason": reason},
                                          checkpoints=_checkpoint_results(executor, bound, role, ref["units"], languages, cps))
                        else:
                            data = _semantic_data(ref["units"], role, languages, history["text"])
                            if not data["source"].strip():
                                result.update(quality={"status": "unknown_reference", "score": None, "reason": "No nonempty translation target"},
                                              checkpoints=_missing_checkpoints(cps, "No nonempty translation target"))
                            else:
                                result.update(quality=executor.judge_role(data, bindings=_stage_bindings(bound, ref["units"], history)),
                                              checkpoints=_checkpoint_results(executor, bound, role, ref["units"], languages, cps))
                    role_results.append(result)
            populations.append({"profile": profile, "measurement_condition": condition,
                                "condition": condition_binding["condition"], "condition_evidence": condition_binding["evidence"],
                                "cost_binding_id": population.get("cost_binding_id"), "role_results": role_results,
                                "aggregate": aggregate_results(episodes, role_results)})
        complete = all(pop["aggregate"][metric]["status"] == "complete"
                       for pop in populations for metric in ("quality", "semantic_wait"))
        report = {"schema_version": 1, "kind": "episode_quality", "report_version": REPORT_VERSION,
                  "status": "complete" if complete else "incomplete", "created_utc": utc_now(),
                  "protocol_revision": spec["protocol_revision"], "spec": {"path": str(spec_path), "sha256": digest(spec_path)},
                  "methodology": provenance(), "expected_model": executor.expected_model,
                  "synthetic_judgments": executor.kind == "synthetic-command", "planned_episodes": episodes,
                  "populations": populations, "calls": executor.store.history(include_raw=False),
                  "store": str(executor.root / "quality.sqlite"), "dispatch_halted": executor.halted}
        atomic_json(output_path, report)
        return report
