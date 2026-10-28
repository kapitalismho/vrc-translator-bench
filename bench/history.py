"""Evidence-bound native history and exact source-availability snapshots.

This module never aligns output to source text, deduplicates strings, or treats
collector sequence numbers as native utterance IDs. Unknown relationships are
not a reconstructed translation. In particular, neither Kikitan ``final`` nor
an unstructured VRCLT display supplies an append/replace boundary.

``interpretations`` binds each derived operation to ``event_index`` (zero-based
in the supplied iterable), ``event_sha256(event)``, and a semantic ``rule`` with
``id``, ``description`` and nonempty ``evidence`` strings. Operations are append,
replace, clear, delete, or ignore. Replace/delete also require a previously
admitted ``replaces_event_index``. Local item identities are explicitly derived;
raw native IDs and all input dictionaries remain untouched. Optional text_field
and text_span select an exact native field/slice, never replacement wording.

A cutoff is a native-event snapshot: a validated event_time_interval and clock
mapping are required. Receipt timestamps alone do not establish producer time.
A horizon without a cutoff instead bounds final *observed* quality history;
receipt can establish that output was observed before that horizon, without
making it timing-eligible. Neither eligibility flag establishes complete input,
application opportunity, absence of collector gaps outside these records, or R6
admission. The caller owns those checks and protocol-defined no-output outcomes.
"""
from __future__ import annotations

import copy
import hashlib
import json


_SCOPE = {"episode_id": ("episode_id",), "profile": ("profile",),
          "attempt": ("attempt", "attempt_id", "source_attempt"),
          "pass_id": ("pass_id",), "input_channel": ("input_channel",),
          "clock_session": ("clock_session",), "target_language": ("target_language",),
          "run": ("run",), "wave": ("wave",)}
_NON_OUTPUT = {"transcript", "session_state_changed", "/chatbox/typing",
               "translation.started", "translation.failed", "chatbox.sent"}

_PURI_RULE = {
    "id": "puripuly-cli-translation-unique-utterance-v1",
    "description": "A TRANSLATION_DONE projection with a new instance/channel/utterance key introduces one output item; a repeated key has no default replacement rule.",
    "evidence": [
        "https://github.com/kapitalismho/PuriPuly-heart/blob/55377ed15768faa42ff6fa15b6a83df570e696bd/src/puripuly_heart/app/services/application_control_events.py#L25-L106",
        "docs/benchmark-final-plan.md:325-328",
    ],
}


def _puri_key(event):
    raw = event.get("raw_evidence")
    projection = raw.get("allowlisted_projection") if isinstance(raw, dict) else None
    if (event.get("transport") != "cli_jsonl" or event.get("native_endpoint") != "translation"
            or event.get("endpoint_stage") not in ("peer_post_overlay_projection", "self_pre_overlay_chatbox_projection")
            or not isinstance(projection, dict) or projection.get("topic") != "translation"
            or not isinstance(event.get("translated_text"), str)):
        return None
    instance, native_id, channel = event.get("producer_instance"), event.get("native_id"), event.get("input_channel")
    if (not isinstance(instance, str) or not instance or not isinstance(native_id, str) or not native_id
            or channel not in ("self", "peer")
            or projection.get("instance_id") != instance or projection.get("utterance_id") != native_id
            or projection.get("channel") != channel or projection.get("text") != event["translated_text"]):
        return None
    return instance, channel, native_id


def event_sha256(event):
    """Identity of this JSON record, distinct from its original-wire raw hash."""
    encoded = json.dumps(event, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _evidence(value):
    return (isinstance(value, list) and bool(value)
            and all(isinstance(item, str) and item.strip() for item in value))


def _rule(value):
    return (isinstance(value, dict) and isinstance(value.get("id"), str)
            and bool(value["id"].strip()) and isinstance(value.get("description"), str)
            and bool(value["description"].strip()) and _evidence(value.get("evidence")))


def _integer(value):
    return type(value) is int


def _citation(event, index, *, full=False):
    raw = event.get("raw_evidence")
    if not full and isinstance(raw, dict):
        raw = {key: raw[key] for key in ("sha256", "byte_count", "offset", "end_offset",
                                        "source_file", "original_not_persisted") if key in raw}
    return copy.deepcopy({"event_index": index, "event_sha256": event_sha256(event),
                          "stream_sequence": event.get("stream_sequence"), "raw_evidence": raw})


def _interval(event, interpretation, session):
    interval = interpretation.get("event_time_interval", event.get("event_time_interval"))
    mapping = interpretation.get("clock_mapping", event.get("clock_mapping"))
    if not isinstance(interval, dict) or not isinstance(mapping, dict) or not _evidence(mapping.get("evidence")):
        return None, "event_time_unmapped"
    lower, upper = interval.get("earliest_ns"), interval.get("latest_ns")
    if not _integer(lower) or not _integer(upper) or lower > upper:
        return None, "invalid_event_time_interval"
    if session is None or interval.get("clock_session") != session:
        return None, "event_time_clock_mismatch"
    return copy.deepcopy(interval), None


def _field(event, name):
    values = [event[key] for key in _SCOPE[name] if event.get(key) is not None]
    if any(value != values[0] for value in values[1:]):
        return None, "conflicting_" + name
    return (values[0] if values else None), None


def _text(event, interpretation):
    field = interpretation.get("text_field", "translated_text")
    if field not in ("translated_text", "display_text"):
        return None, "unsupported_text_field"
    text = event.get(field)
    if not isinstance(text, str):
        return None, "translation_extraction_unknown"
    span = interpretation.get("text_span")
    if span is not None:
        if (not isinstance(span, list) or len(span) != 2
                or not all(_integer(value) for value in span)
                or not 0 <= span[0] <= span[1] <= len(text)):
            return None, "invalid_native_text_span"
        text = text[span[0]:span[1]]
    return text, None


def reconstruct_history(events, *, role, cutoff_ns=None, clock_session=None,
                        episode=None, profile=None, attempt=None, pass_id=None,
                        channel=None, horizon_ns=None, target_language=None,
                        interpretations=None, run=None, wave=None):
    """Return JSON-serializable history without modifying native input.

    Unselected scope values are inferred only when unambiguous. Missing role,
    channel or target extraction is unknown, not no-output. Unknown/future event
    records carry citations only: their source/target/raw payload cannot leak
    through a snapshot's audit fields. ``text`` is null when reconstruction is
    unsupported; ``observed_text`` and items retain only supported portions.

    Clear/delete archive presentation, including previous pages, rather than
    semantically retracting emitted content. A replacement changes only its
    specifically cited item, keeping earlier revisions in the audit trail.
    """
    if not isinstance(role, str) or not role:
        raise ValueError("A logical role is required")
    for name, value in (("cutoff_ns", cutoff_ns), ("horizon_ns", horizon_ns)):
        if value is not None and not _integer(value):
            raise ValueError(name + " must be an integer nanosecond boundary")
    if cutoff_ns is not None and clock_session is None:
        raise ValueError("A cutoff requires its clock_session")
    rows = list(events)
    if not all(isinstance(event, dict) for event in rows):
        raise ValueError("Native events must be JSON objects")
    by_index = {}
    for interpretation in interpretations or []:
        if not isinstance(interpretation, dict):
            raise ValueError("Interpretations must be objects")
        index = interpretation.get("event_index")
        if not _integer(index) or not 0 <= index < len(rows) or index in by_index:
            raise ValueError("Interpretation event_index must uniquely bind a supplied record")
        if interpretation.get("event_sha256") != event_sha256(rows[index]):
            raise ValueError("Interpretation does not match the cited native event")
        if not _rule(interpretation.get("rule")):
            raise ValueError("Interpretation requires semantic rule provenance")
        if interpretation.get("operation") not in ("append", "replace", "clear", "delete", "ignore"):
            raise ValueError("Unsupported derived operation")
        by_index[index] = interpretation

    scope = {"episode_id": episode, "profile": profile, "attempt": attempt,
             "pass_id": pass_id, "input_channel": channel, "clock_session": clock_session,
             "target_language": target_language, "run": run, "wave": wave}
    selected, excluded, reasons = [], [], []
    for index, event in enumerate(rows):
        interpretation = by_index.get(index, {})
        if (event.get("record") != "native_output_event" and not interpretation
                and all(event.get(field) is None for field in ("translated_text", "display_text", "translated_texts"))
                and not event.get("loss_or_gap")):
            excluded.append({"citation": _citation(event, index), "reason": "not_native_output_record"})
            continue
        actual = {}
        conflicts = []
        for name in _SCOPE:
            actual[name], conflict = _field(event, name)
            if name == "input_channel" and actual[name] is None:
                actual[name] = interpretation.get("input_channel")
            if conflict:
                conflicts.append(conflict)
        actual_role = event.get("role")
        if actual_role is None:
            actual_role = interpretation.get("role")
        mismatch = next((name for name, value in scope.items()
                         if value is not None and actual[name] is not None and actual[name] != value), None)
        if actual_role is not None and actual_role != role:
            mismatch = "role"
        phase = event.get("capture_phase")
        if phase in ("quiet_precondition", "preparation", "startup") or event.get("output_classification") == "unresolved_carryover":
            mismatch = "outside_measured_input"
        if mismatch:
            excluded.append({"citation": _citation(event, index), "reason": "scope_" + mismatch})
            continue
        selected.append((index, event, interpretation, actual, actual_role, conflicts))
    for name, value in scope.items():
        if value is None:
            values = []
            for _, _, _, actual, _, _ in selected:
                if actual[name] is not None and actual[name] not in values:
                    values.append(actual[name])
            if len(values) == 1:
                scope[name] = values[0]
            elif len(values) > 1:
                reasons.append("ambiguous_" + name)
    scope["role"] = role
    if horizon_ns is not None and scope["clock_session"] is None:
        reasons.append("horizon_clock_unknown")
    result = {"schema_version": 1, "scope": scope, "cutoff_ns": cutoff_ns,
              "horizon_ns": horizon_ns, "status": "unknown", "text": None,
              "observed_text": "", "quality_eligible": False, "timing_eligible": False,
              "no_output_certified": False, "items": [], "text_citations": [],
              "revisions": [], "events": [], "emissions": [],
              "excluded_events": excluded, "late_events": [], "uncertain_events": [],
              "reasons": reasons, "timing_reasons": [], "clear_only": False}
    items, event_items, active = [], {}, set()
    page = 0
    admitted = 0
    puri_keys = set()
    for index, event, interpretation, actual, actual_role, conflicts in selected:
        citation = _citation(event, index)
        interval, time_reason = _interval(event, interpretation, scope["clock_session"])
        received = event.get("collector_received_monotonic")
        endpoint = event.get("native_endpoint")
        non_output = (endpoint in _NON_OUTPUT or isinstance(endpoint, str) and
                      (endpoint.startswith("asr.") or endpoint.startswith("system.")))
        if event.get("endpoint_stage") == "final_log_crosscheck" and not interpretation:
            result["excluded_events"].append({"citation": citation, "reason": "separate_final_crosscheck"})
            continue
        if non_output and not interpretation and not event.get("loss_or_gap"):
            # Even diagnostics are citation-only: do not expose ASR as reference.
            result["excluded_events"].append({"citation": citation, "reason": "not_translation_output"})
            continue
        if cutoff_ns is not None and interval is not None and interval["earliest_ns"] > cutoff_ns:
            result["excluded_events"].append({"citation": citation, "reason": "after_cutoff"})
            continue
        if horizon_ns is not None:
            if interval is not None and interval["earliest_ns"] > horizon_ns:
                result["late_events"].append({"citation": citation, "event_time_interval": interval,
                                              "reason": "after_observation_horizon"})
                continue
            if interval is not None and interval["latest_ns"] > horizon_ns:
                result["uncertain_events"].append({"citation": citation, "reason": "interval_crosses_horizon"})
                reasons.append("interval_crosses_horizon")
                continue
            if interval is None and (_integer(received) and received > horizon_ns):
                result["late_events"].append({"citation": citation, "reason": "received_after_horizon_unmapped"})
                result["timing_reasons"].append(time_reason)
                continue
            if interval is None and not _integer(received):
                result["uncertain_events"].append({"citation": citation, "reason": "horizon_time_unknown"})
                reasons.append("horizon_time_unknown")
                continue
        if cutoff_ns is not None:
            if interval is None:
                result["uncertain_events"].append({"citation": citation, "reason": time_reason})
                reasons.append(time_reason)
                continue
            if interval["latest_ns"] > cutoff_ns:
                result["uncertain_events"].append({"citation": citation, "reason": "interval_crosses_cutoff"})
                reasons.append("interval_crosses_cutoff")
                continue
        if time_reason:
            result["timing_reasons"].append(time_reason)
        missing = conflicts + ["missing_" + name for name in
                               ("episode_id", "profile", "attempt", "pass_id", "input_channel", "target_language")
                               if actual[name] is None]
        missing.extend("missing_" + name for name in ("run", "wave")
                       if scope[name] is not None and actual[name] is None)
        if actual_role is None:
            missing.append("role_extraction_unknown")
        if actual["clock_session"] is None and cutoff_ns is not None and not interpretation.get("event_time_interval"):
            missing.append("missing_clock_session")
        if event.get("loss_or_gap"):
            missing.append("native_history_gap")
        if any(reason.startswith("ambiguous_") for reason in reasons):
            missing.append("scope_not_unique")
        operation = interpretation.get("operation")
        puri_key = _puri_key(event)
        if puri_key is not None:
            if operation is None and puri_key not in puri_keys:
                interpretation = {"operation": "append", "rule": _PURI_RULE}
                operation = "append"
            puri_keys.add(puri_key)
        # This immutable emission archive is distinct from reconstructed items.
        # Unknown native relations still retain their actual output and source
        # audit, but future/uncertain-time records never reach this point.
        audit = {"citation": _citation(event, index, full=True), "event": copy.deepcopy(event),
                 "derived_operation": operation, "rule": copy.deepcopy(interpretation.get("rule")),
                 "event_time_interval": interval}
        result["events"].append(audit)
        if isinstance(event.get("translated_text"), str) or isinstance(event.get("display_text"), str):
            result["emissions"].append(audit)
        if operation is None:
            missing.append("native_relationship_unknown")
        if missing:
            result["uncertain_events"].append({"citation": citation, "reasons": missing})
            reasons.extend(missing)
            continue
        if operation == "ignore":
            continue
        text, extraction_reason = (None, None)
        if operation in ("append", "replace"):
            text, extraction_reason = _text(event, interpretation)
        target = interpretation.get("replaces_event_index")
        if operation in ("replace", "delete") and (not _integer(target) or target not in event_items):
            extraction_reason = "replacement_target_unknown"
        if extraction_reason:
            result["uncertain_events"].append({"citation": citation, "reason": extraction_reason})
            reasons.append(extraction_reason)
            continue
        admitted += 1
        revision = {"citation": _citation(event, index, full=True), "derived_operation": operation,
                    "rule": copy.deepcopy(interpretation["rule"]), "event_time_interval": interval}
        if operation == "append":
            item_index = len(items)
            item = {"derived_item_id": "event:" + str(index), "native_id": event.get("native_id"),
                    "text": text, "page": page, "active": True, "citations": [_citation(event, index, full=True)]}
            items.append(item)
            active.add(item_index)
            event_items[index] = item_index
            revision.update(derived_item_id=item["derived_item_id"], text=text)
        elif operation == "replace":
            item_index = event_items[target]
            item = items[item_index]
            revision.update(derived_item_id=item["derived_item_id"], previous_text=item["text"],
                            text=text, replaces_event_index=target)
            item["text"] = text
            item["citations"].append(_citation(event, index, full=True))
            event_items[index] = item_index
        else:
            targets = set(active) if operation == "clear" else {event_items[target]}
            revision["archived_item_ids"] = [items[item_index]["derived_item_id"] for item_index in sorted(targets)]
            for item_index in targets:
                items[item_index]["active"] = False
            active.difference_update(targets)
            if operation == "delete":
                revision["replaces_event_index"] = target
                event_items[index] = event_items[target]
            else:
                page += 1
        result["revisions"].append(revision)
    result["items"] = items
    result["observed_text"] = "\n".join(item["text"] for item in items if item["text"])
    offset = 0
    for item in items:
        if item["text"]:
            if result["text_citations"]:
                offset += 1
            result["text_citations"].append({
                "start": offset, "end": offset + len(item["text"]),
                "derived_item_id": item["derived_item_id"], "citation": item["citations"][-1]})
            offset += len(item["text"])
    result["reasons"] = list(dict.fromkeys(reasons))
    result["timing_reasons"] = list(dict.fromkeys(result["timing_reasons"]))
    if not selected:
        result["reasons"].append("no_scoped_native_events")
    if not result["reasons"]:
        result["quality_eligible"] = True
        result["text"] = result["observed_text"]
        result["status"] = "reconstructed" if result["text"] else "empty"
    result["timing_eligible"] = result["quality_eligible"] and not result["timing_reasons"]
    if admitted == 0 and cutoff_ns is None and not result["reasons"]:
        result.update(quality_eligible=False, timing_eligible=False, status="unknown", text=None)
        result["reasons"].append("no_admitted_native_output")
    result["clear_only"] = bool(result["revisions"]) and all(
        revision["derived_operation"] in ("clear", "delete") for revision in result["revisions"])
    return result


def source_prefix(units, *, cutoff_ns, origin_ns, clock_session, input_available_until_ns=None):
    """Filter exact reference units by their complete availability in one pass.

    Units contain text, start_ns/end_ns relative to the actual pass input origin,
    and optional role/citations/translation_targets/context_only metadata. All
    included metadata is preserved. A cutoff or interrupted input within a unit
    does not license revealing its unheard suffix: that unit is withheld whole.
    Future and unfinished unit summaries never contain text or target spans.
    """
    if not _integer(cutoff_ns) or not _integer(origin_ns) or not isinstance(clock_session, str) or not clock_session:
        raise ValueError("Source prefix requires integer cutoff/origin and a clock_session")
    if input_available_until_ns is not None and not _integer(input_available_until_ns):
        raise ValueError("input_available_until_ns must be an integer")
    available = min(cutoff_ns, input_available_until_ns) if input_available_until_ns is not None else cutoff_ns
    included, uncertain, future, reasons = [], [], [], []
    for index, unit in enumerate(units):
        if not isinstance(unit, dict) or not isinstance(unit.get("text"), str):
            raise ValueError("Source units require exact reference text")
        start, end = unit.get("start_ns"), unit.get("end_ns")
        if not _integer(start) or not _integer(end) or not 0 <= start <= end:
            raise ValueError("Source units require ordered relative nanosecond bounds")
        if unit.get("clock_session", clock_session) != clock_session:
            reasons.append("source_clock_mismatch")
            uncertain.append({"unit_index": index, "id": unit.get("id"), "reason": "source_clock_mismatch"})
            continue
        summary = copy.deepcopy({"unit_index": index, "id": unit.get("id"),
                                 "start_ns": start, "end_ns": end, "citations": unit.get("citations", [])})
        if origin_ns + end <= available:
            included.append(copy.deepcopy(unit))
        elif origin_ns + start < available:
            uncertain.append({**summary, "reason": "incomplete_source_unit"})
            reasons.append("incomplete_source_unit")
        else:
            future.append(summary)
    return {"schema_version": 1, "status": "unknown" if reasons else "available",
            "quality_eligible": not reasons, "clock_session": clock_session,
            "origin_ns": origin_ns, "cutoff_ns": cutoff_ns, "input_available_until_ns": input_available_until_ns,
            "text": "\n".join(unit["text"] for unit in included), "units": included,
            "uncertain_units": uncertain, "future_units": future, "reasons": list(dict.fromkeys(reasons))}
