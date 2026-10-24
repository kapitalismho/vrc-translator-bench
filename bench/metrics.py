from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .metrics_alignment import Alignment, cache_binding, final_outputs, interpret, is_translation
from .metrics_inputs import VERSION, ingest, load_applicability, metric
from .storage import atomic_json, utc_now


DEFINITIONS = {
    "version": VERSION, "source_clock": "callback-mapped DAC plus positive cable correction; perf_counter_ns within clock_session",
    "alignment": "SimAlign lexical proposals are provisional; only explicit inspected bound-cache adjudication establishes source correspondence",
    "output_clock": "OSC receipt, not app internal events", "deadline": "containing turn end + 15 seconds, inclusive",
    "fol": "first related output <= deadline minus sentence start", "sentence_lul": "last related content change <= deadline minus sentence end",
    "turn_lul": "last related content change <= turn end + 15 seconds minus turn end",
    "delivery": "sentences with known corresponding output by deadline / eligible reference sentences; unknown correspondence retained in denominator and separately counted",
    "unaligned": "translation outputs without linked reference sentences / all nonempty interpreted chatbox/input translation outputs, including known-unrelated, resends and late/orphan output; unknown and known-unrelated statuses remain distinct",
    "isolated": "all output in [utterance start, utterance end + 10 seconds], inclusive, no language alignment",
    "quality": "about 30 seconds at reference sentence ends; TWO previous reference turns as unscored context; a merged output crossing segment cuts has one display placement and all source-linked segments are scoring N/A until allocation is supported",
    "output_role": "Unresolved extraction retains raw endpoint activity and possible correspondence, never translated-content or quality credit",
    "uncertainty": "session-clustered percentile 95% bootstrap; excludes reference, alignment and judge bias",
    "policies": "product failure included; operational-invalid and unsupported N/A retained but excluded from headline measurement denominators; first eligible attempt primary; repeats separate; no overall score",
}


def prepare_sentences(attempts):
    sentences, turns = [], []
    for attempt in attempts:
        references = attempt["reference"]
        turn_map = {row["id"]: row for row in references["turns"]}
        for kind, destination in (("sentences", sentences), ("turns", turns)):
            for reference in references[kind]:
                row = dict(reference)
                row.update({"id": f"{attempt['id']}:{reference['id']}", "reference_id": reference["id"],
                            "attempt_id": attempt["id"], "attempt_number": attempt["number"], "resumed": bool(attempt["resumed"]),
                            "config": attempt["config"], "direction": attempt["direction"], "clock_session": attempt["clock_session"],
                            "run": attempt["run"], "kind": attempt["kind"], "status": attempt["state"], "outcome": attempt.get("outcome"),
                            "failure_reason": attempt.get("reason"), "audio_sha256": attempt["stage_data"].get("audio_sha256"),
                            "start_ns": reference.get("start_ns"), "end_ns": reference.get("end_ns")})
                if "applicability" in attempt:
                    row["applicability"] = attempt["applicability"]
                row["eligibility_reason"] = row.get("eligibility_reason") or ("unsupported" if row["outcome"] == "N/A" else "operational_invalid" if row["status"] not in ("done", "product_failure") else None)
                if row["eligibility_reason"] is None and (row["start_ns"] is None or row["end_ns"] is None):
                    row["eligibility_reason"] = "source_timing_unavailable"
                row["eligible"] = row["scored"] and row["eligibility_reason"] is None
                if kind == "sentences":
                    turn = turn_map.get(reference["turn_id"])
                    row["turn_id"] = f"{attempt['id']}:{reference['turn_id']}" if turn else None
                    row["candidate_turn_ids"] = [f"{attempt['id']}:{identity}" for identity in reference["candidate_turn_ids"]]
                    row["deadline_ns"] = turn.get("end_ns") + 15_000_000_000 if turn and turn.get("end_ns") is not None else None
                    row["duration_seconds"] = row["end"] - row["start"]
                    row["duration_bin"] = "below_2s" if row["duration_seconds"] < 2 else "2_to_5s" if row["duration_seconds"] <= 5 else "above_5s"
                else:
                    row["deadline_ns"] = row["end_ns"] + 15_000_000_000 if row["end_ns"] is not None else None
                destination.append(row)
    return sentences, turns


def coverage(manifest, attempts, events):
    result = defaultdict(int)
    for attempt in attempts:
        if attempt["clock_session"] and attempt.get("end_ns") is not None:
            result[attempt["clock_session"]] = max(result[attempt["clock_session"]], attempt["end_ns"])
    for row in manifest.get("records", []):
        if row.get("kind") == "session_end":
            detail = json.loads(row["detail"]) if isinstance(row["detail"], str) else row["detail"]
            result[detail["session"]] = max(result[detail["session"]], row["t_ns"])
    for event in events:
        if event.get("clock_session"):
            result[event["clock_session"]] = max(result[event["clock_session"]], event["t_ns"])
    return result


def timing(row, outputs, covered_until):
    related = [output for output in outputs if row["id"] in output["alignment"]["sentence_ids"]]
    deadline = row["deadline_ns"]
    on_time = [output for output in related if deadline is not None and output["raw"]["t_ns"] <= deadline]
    late = [output["id"] for output in related if deadline is not None and output["raw"]["t_ns"] > deadline]
    possible = [output["id"] for output in outputs if output["alignment"]["status"] == "unknown" and row["id"] in output["alignment"].get("candidate_ids", [])
                and deadline is not None and output["raw"]["t_ns"] <= deadline]
    complete = deadline is not None and covered_until >= deadline
    reason = row.get("eligibility_reason") if not row["eligible"] else "Source timing unavailable" if deadline is None or row["start_ns"] is None or row["end_ns"] is None else None
    if reason:
        status = "N/A"
    elif on_time:
        status = "delivered"
    elif possible:
        status = "unknown_correspondence"
    elif not complete:
        status = "incomplete_observation"
    else:
        status = "no_output_before_deadline"
    changes = [output for output in on_time if output["content_changed"] is True]
    ambiguous = any(output["content_changed"] is None for output in on_time)
    row.update({"delivery_status": status, "related_output_ids": [output["id"] for output in related], "late_output_ids": late,
                "unknown_candidate_ids": possible, "observation_complete": complete,
                "fol": metric((min(output["raw"]["t_ns"] for output in on_time) - row["start_ns"]) / 1e9 if on_time and not reason else None,
                              reason or (None if on_time else status)),
                "lul": metric((max(output["raw"]["t_ns"] for output in changes) - row["end_ns"]) / 1e9 if changes and not ambiguous and not reason else None,
                              reason or ("Ambiguous content-change interpretation" if ambiguous else None if changes else status))})


def assemble_segments(sentences, turns, outputs, scores):
    groups = defaultdict(list)
    for row in sentences:
        if row["scored"]:
            groups[(row["attempt_id"], row["chunk_id"], row["session_id"], row["category"])].append(row)
    segments = []
    for key, rows in groups.items():
        rows.sort(key=lambda row: (row["start"], row["end"], row["id"]))
        pending = []
        for index, row in enumerate(rows):
            pending.append(row)
            if row["end"] - pending[0]["start"] < 30 and index + 1 < len(rows):
                continue
            first, last = pending[0], pending[-1]
            earlier_turns = sorted([turn for turn in turns if turn["attempt_id"] == first["attempt_id"] and turn["session_id"] == first["session_id"]
                                    and turn["end"] <= first["start"]], key=lambda turn: (turn["end"], turn["start"]))
            context = [turn for turn in earlier_turns if turn["text"].strip()][-2:]
            source_context = [turn for turn in first.get("earlier_source_turns", []) if turn["text"].strip()][-(2 - len(context)):] if len(context) < 2 else []
            identity = f"{first['attempt_id']}:{first['chunk_id']}:quality-{len(segments) + 1}"
            reference_eligible = first["status"] in ("done", "product_failure") and first.get("outcome") != "N/A"
            segments.append({"id": identity, "shared_id": f"{first['audio_sha256']}:{first['direction']}:{first['chunk_id']}:{first['start']}:{last['end']}",
                             "attempt_id": first["attempt_id"], "config": first["config"], "direction": first["direction"], "clock_session": first["clock_session"],
                             "session_id": first["session_id"], "category": first["category"], "casual": True if all(item["casual"] is True for item in pending) else None if any(item["casual"] is None for item in pending) else False,
                             "kind": first["kind"], "status": first["status"], "eligible": reference_eligible, "reference_eligible": reference_eligible, "timing_eligible": all(item["eligible"] for item in pending),
                             "resumed": first["resumed"], "start": first["start"], "end": last["end"], "start_ns": first["start_ns"], "end_ns": last["end_ns"],
                             "reference": [{"sentence_id": item["id"], "speaker": item["speaker"], "text": item["text"], "uncertainty": item["uncertainty"],
                                            "reference_level": item["reference_level"], "partial": item.get("partial", False), "timing_eligibility_reason": item.get("eligibility_reason")} for item in pending],
                             "context": [*source_context, *[{"turn_id": turn["id"], "speaker": turn["speaker"], "text": turn["text"], "scored": False} for turn in context]],
                             "unavailable_context_turn_ids": [turn["id"] for turn in earlier_turns[-2:] if not turn["text"].strip()],
                             "output_ids": [], "unaligned_output_ids": [], "quality_score": scores.get(identity), "attempt_number": first["attempt_number"]})
            pending = []
    reference_populations = {row["attempt_id"]: row["kind"] for row in sentences}
    for output in outputs:
        aligned = set(output["alignment"]["sentence_ids"])
        capture_kind = output.get("capture_kind", reference_populations.get(output["raw"].get("attempt"), "unassigned"))
        capture_attempt = output.get("capture_attempt_id", output["raw"].get("attempt"))
        output["capture_kind"], output["capture_attempt_id"] = capture_kind, capture_attempt
        candidates = [segment for segment in segments if any(row["sentence_id"] in aligned for row in segment["reference"])]
        output["source_quality_segment_ids"] = [segment["id"] for segment in candidates]
        for linked_segment in candidates:
            linked_segment.setdefault("source_linked_output_ids", []).append(output["id"])
            if len(candidates) > 1:
                linked_segment.setdefault("cross_segment_output_ids", []).append(output["id"])
                linked_segment["eligible"] = False
                if linked_segment.get("quality_eligibility_reason") != "unresolved_output_role":
                    linked_segment["quality_eligibility_reason"] = "unresolved_merged_output_allocation"
        if not candidates:
            candidates = [segment for segment in segments if segment["clock_session"] == output["raw"].get("clock_session")
                          and segment["config"] == output["raw"].get("config") and segment["direction"] == output["raw"].get("direction")
                          and segment["kind"] == capture_kind and (capture_kind in ("chunk", "repeat") or segment.get("attempt_id") == capture_attempt)
                          and segment["start_ns"] is not None and segment["end_ns"] is not None]
        if candidates:
            timestamp = output["raw"]["t_ns"]
            segment = min(candidates, key=lambda item: (max(item["start_ns"] - timestamp, 0, timestamp - item["end_ns"]), item["start_ns"])) if all(item["start_ns"] is not None and item["end_ns"] is not None for item in candidates) else candidates[0]
        else:
            identity = f"orphan:{output['raw'].get('clock_session')}:{output['raw'].get('config')}:{capture_kind}:{capture_attempt}"
            segment = next((item for item in segments if item["id"] == identity), None)
            if segment is None:
                segment = {"id": identity, "shared_id": None, "config": output["raw"].get("config"), "direction": output["raw"].get("direction"),
                           "clock_session": output["raw"].get("clock_session"), "session_id": None, "category": "unknown", "casual": False,
                           "kind": capture_kind, "attempt_id": capture_attempt,
                           "eligible": False, "reference_eligible": False, "reason": "No captured source timeline in this clock/config", "reference": [], "context": [], "output_ids": [],
                           "unaligned_output_ids": [], "quality_score": None, "start_ns": None, "end_ns": None}
                segments.append(segment)
        if is_translation(output):
            segment["output_ids"].append(output["id"])
            if not aligned:
                segment["unaligned_output_ids"].append(output["id"])
        else:
            possible = set(output["alignment"].get("candidate_ids", []))
            affected = [item for item in segments if any(row["sentence_id"] in possible for row in item["reference"])]
            if capture_kind not in ("chunk", "repeat"):
                affected = list(candidates)
            # Missing timing cannot allocate within the captured attempt/stage's reference coverage.
            untimed_capture = [item for item in segments if item["reference"] and item.get("attempt_id") == capture_attempt
                               and item["clock_session"] == output["raw"].get("clock_session")
                               and item["config"] == output["raw"].get("config") and item["direction"] == output["raw"].get("direction")
                               and item["kind"] == capture_kind and (item["start_ns"] is None or item["end_ns"] is None)]
            output["untimed_capture_quality_segment_ids"] = [item["id"] for item in untimed_capture]
            for item in untimed_capture:
                if item not in affected:
                    affected.append(item)
            if segment not in affected:
                affected.append(segment)
            output["unresolved_quality_segment_ids"] = [item["id"] for item in affected]
            for item in affected:
                item.setdefault("unresolved_output_ids", []).append(output["id"])
                item["eligible"] = False
                item["quality_eligibility_reason"] = "unresolved_output_role"
        output["quality_segment_id"] = segment["id"]
    by_id = {output["id"]: output for output in outputs}
    group_locations = defaultdict(set)
    for output in outputs:
        group_locations[output["group_id"]].update(output["source_quality_segment_ids"] or [output["quality_segment_id"]])
    for segment in segments:
        segment.setdefault("source_linked_output_ids", [])
        segment.setdefault("cross_segment_output_ids", [])
        segment.setdefault("quality_eligibility_reason", None)
        segment.setdefault("unresolved_output_ids", [])
        selected = [by_id[identity] for identity in segment["output_ids"]]
        final = final_outputs(selected)
        segment["final_output"] = [{"output_id": row["id"], "text": row["text"], "relation": row["relation"]} for row in final]
        related = [by_id[identity] for identity in dict.fromkeys(segment["output_ids"] + segment["source_linked_output_ids"])]
        segment["cross_segment_group_ids"] = sorted({row["group_id"] for row in related if len(group_locations[row["group_id"]]) > 1})
        segment["reconstruction_status"] = "N/A_unresolved_merged_output_allocation" if segment["cross_segment_output_ids"] else "unknown_observed_order_only" if segment["cross_segment_group_ids"] or any(row["relation"] == "unknown" for row in selected) else "estimated_under_versioned_rules"
        if segment["unresolved_output_ids"]:
            segment["reconstruction_status"] = "N/A_unresolved_output_role"
    return segments


def exclude_inapplicable(attempts, sentences, turns, segments, outputs, applicability):
    """Retain observations and source links, but never infer their provider."""
    direct = {(entry["config"], entry["attempt_id"]): {
        "population": applicability["population"], **entry, "exclusion_kind": "direct"}
        for entry in applicability["exclusions"]}
    dependencies = defaultdict(dict)
    sources = {row["id"]: row for row in sentences}
    segment_index = {row["id"]: row for row in segments}

    # Only explicitly selected capture origins seed dependencies. A clean
    # origin does not become mixed because its source population is excluded.
    for output in outputs:
        origin = direct.get((output["raw"].get("config"), output.get("capture_attempt_id")))
        if origin is None:
            continue
        output.update(population_eligible=False, applicability=origin)
        affected = set(output["alignment"]["sentence_ids"])
        if output["alignment"]["status"] == "unknown":
            affected.update(output["alignment"].get("candidate_ids", []))
        # Isolated results associate by the existing utterance window rather
        # than source alignment; that consumer must retain the same uncertainty.
        for attempt in attempts:
            if (attempt["kind"] != "isolated" or attempt["config"] != output["raw"].get("config")
                    or attempt["clock_session"] != output["raw"].get("clock_session")):
                continue
            refs = [row for row in sentences if row["attempt_id"] == attempt["id"] and row["scored"]]
            start = min((row["start_ns"] for row in refs if row["start_ns"] is not None), default=None)
            end = max((row["end_ns"] for row in refs if row["end_ns"] is not None), default=None)
            if start is not None and end is not None and start <= output["raw"]["t_ns"] <= end + 10_000_000_000:
                affected.update(row["id"] for row in refs)
        segment_ids = {output.get("quality_segment_id"), *output.get("source_quality_segment_ids", []),
                       *output.get("unresolved_quality_segment_ids", []),
                       *output.get("untimed_capture_quality_segment_ids", [])}
        for identity in segment_ids:
            segment = segment_index.get(identity)
            if segment is not None:
                dependencies[("quality_segments", identity)][output["id"]] = origin
                # Unaligned display allocation is not source correspondence:
                # its whole reference population remains uncertain.
                if not output["alignment"]["sentence_ids"]:
                    affected.update(member["sentence_id"] for member in segment["reference"])
        for identity in affected:
            source = sources.get(identity)
            if source is None or source["config"] != output["raw"].get("config") or source["clock_session"] != output["raw"].get("clock_session"):
                continue
            dependencies[("sentences", identity)][output["id"]] = origin
            for turn_id in {source.get("turn_id"), *source.get("candidate_turn_ids", [])} - {None}:
                dependencies[("turns", turn_id)][output["id"]] = origin
            for segment in segments:
                if any(member["sentence_id"] == identity for member in segment["reference"]):
                    dependencies[("quality_segments", segment["id"])][output["id"]] = origin

    # An affected first-attempt population cannot be classified as a clean
    # product success/failure. Keep its original status and incident evidence.
    for name, rows in (("sentences", sentences), ("turns", turns), ("quality_segments", segments)):
        for row in rows:
            dependencies[("attempts", (row["config"], row.get("attempt_id")))].update(
                dependencies.get((name, row["id"]), {}))

    totals, counts = {}, {"direct": {}, "dependent": {}}
    collections = (("attempts", attempts), ("sentences", sentences), ("turns", turns), ("quality_segments", segments))
    for name, rows in collections:
        counts["direct"][name] = counts["dependent"][name] = 0
        for row in rows:
            attempt_id = row["id"] if name == "attempts" else row.get("attempt_id")
            origin = direct.get((row["config"], attempt_id))
            dependency_key = (row["config"], attempt_id) if name == "attempts" else row["id"]
            linked = dependencies.get((name, dependency_key), {})
            if origin is None and not linked:
                continue
            kind = "direct" if origin is not None else "dependent"
            decision = dict(origin) if origin is not None else {
                "population": applicability["population"], "reason": "excluded_capture_output_dependency",
                "exclusion_kind": kind}
            if linked:
                decision["dependent_output_ids"] = sorted(linked)
                decision["origin_exclusions"] = list({(item["config"], item["attempt_id"]): item for item in linked.values()}.values())
            row.update(population_eligible=False, applicability=decision)
            if name != "attempts":
                row["pre_applicability_eligible"] = row["eligible"]
                row["eligible"] = False
                if "timing_eligible" in row:
                    row["pre_applicability_timing_eligible"] = row["timing_eligible"]
                    row["timing_eligible"] = False
                reason_key = "quality_eligibility_reason" if name == "quality_segments" else "eligibility_reason"
                row[f"pre_applicability_{reason_key}"] = row.get(reason_key)
                row[reason_key] = row.get(reason_key) or (
                    "analysis_applicability_excluded" if kind == "direct" else "excluded_capture_output_dependency")
            counts[kind][name] += 1
        totals[name] = counts["direct"][name] + counts["dependent"][name]
    applicability["excluded_counts"] = totals
    applicability["direct_excluded_counts"] = counts["direct"]
    applicability["dependent_excluded_counts"] = counts["dependent"]
    applicability["excluded_output_ids"] = [row["id"] for row in outputs if row.get("population_eligible") is False]


def isolated_results(attempts, outputs):
    results = []
    for attempt in attempts:
        if attempt["kind"] != "isolated":
            continue
        refs = [row for row in attempt["reference"]["sentences"] if row["scored"]]
        start = min((row["start_ns"] for row in refs if row.get("start_ns") is not None), default=None)
        end = max((row["end_ns"] for row in refs if row.get("end_ns") is not None), default=None)
        if start is None or end is None:
            results.append({"attempt_id": attempt["id"], "status": "N/A", "reason": "Utterance timing unavailable"})
            continue
        deadline = end + 10_000_000_000
        observed = [output for output in outputs if output["raw"].get("config") == attempt["config"] and output["raw"].get("clock_session") == attempt["clock_session"]
                    and start <= output["raw"]["t_ns"] <= deadline]
        selected = [output for output in observed if is_translation(output)]
        unresolved = [output["id"] for output in observed if not is_translation(output)]
        changes = [output for output in selected if output["content_changed"] is True]
        late = [output["id"] for output in outputs if output["raw"].get("config") == attempt["config"] and output["raw"].get("clock_session") == attempt["clock_session"]
                and output["raw"]["t_ns"] > deadline and (output["raw"].get("attempt") == attempt["id"] or any(str(identity).startswith(f"{attempt['id']}:") for identity in output["alignment"]["sentence_ids"]))]
        results.append({"attempt_id": attempt["id"], "test": "isolated_response_not_continuous_latency", "start_ns": start, "end_ns": end, "deadline_ns": deadline,
                        "attempt_status": attempt["state"], "outcome": attempt.get("outcome"),
                        "measurement_eligible": attempt["state"] in ("done", "product_failure") and attempt.get("outcome") != "N/A" and attempt.get("population_eligible", True),
                        "output_ids": [row["id"] for row in selected], "late_carryover_ids": late,
                        "raw_activity_ids": [row["id"] for row in observed], "unresolved_output_ids": unresolved,
                        "carryover_uncertainty": "All in-window output associated by time only; earlier-utterance carryover may contaminate quality",
                        "status": "response" if selected else "unknown_output_role" if unresolved else "timeout" if attempt.get("covered_until_ns", 0) >= deadline else "incomplete_observation",
                        "first_from_start": metric((selected[0]["raw"]["t_ns"] - start) / 1e9 if selected else None, None if selected else "unresolved_output_role" if unresolved else "No in-window response"),
                        "first_from_end": metric((selected[0]["raw"]["t_ns"] - end) / 1e9 if selected else None, None if selected else "unresolved_output_role" if unresolved else "No in-window response"),
                        "last_content_change_from_end": metric((changes[-1]["raw"]["t_ns"] - end) / 1e9 if changes and not unresolved and not any(row["content_changed"] is None for row in selected) else None,
                                                               "Ambiguous or absent content change" if not changes or unresolved or any(row["content_changed"] is None for row in selected) else None),
                        "quality_segment_ids": sorted({row["quality_segment_id"] for row in selected})})
        results[-1]["quality"] = {"reference": [{"text": row["text"], "speaker": row["speaker"], "uncertainty": row["uncertainty"]} for row in refs],
                                  "final_output": [{"output_id": row["id"], "text": row["text"]} for row in final_outputs(selected)],
                                  "quality_score": None if unresolved else attempt.get("isolated_quality_score"), "association": "window_only_no_alignment",
                                  "eligible": results[-1]["measurement_eligible"] and not unresolved, "quality_eligibility_reason": "unresolved_output_role" if unresolved else None,
                                  "unresolved_output_ids": unresolved}
        if attempt.get("population_eligible") is False:
            results[-1]["applicability"] = attempt["applicability"]
            results[-1]["quality"]["quality_eligibility_reason"] = results[-1]["quality"]["quality_eligibility_reason"] or attempt["applicability"]["reason"]
    return results


def derive(manifest_path, spec_path, output_path=None, cache_path=None, allow_download=False, *, applicability_path=None):
    from .metrics_diagnostics import diagnostics
    from .metrics_stats import aggregate
    manifest, spec, attempts, events, provenance = ingest(manifest_path, spec_path)
    applicability = load_applicability(applicability_path, manifest_path, spec_path, attempts, provenance) if applicability_path is not None else None
    if applicability is not None and output_path is not None and Path(output_path).resolve() in {Path(item["path"]).resolve() for item in provenance}:
        raise ValueError("Metrics output must not overwrite an applicability or native input")
    sentences, turns = prepare_sentences(attempts)
    outputs, nontranslation = interpret(events, spec.get("rules", {}))
    attempts_by_id = {(row["id"], row["config"]): row for row in attempts}
    for collection in (outputs, nontranslation):
        for observation in collection:
            attempt = attempts_by_id.get((observation["raw"].get("attempt"), observation["raw"].get("config")))
            observation["capture_kind"] = attempt["kind"] if attempt else "unassigned"
            observation["capture_attempt_id"] = attempt["id"] if attempt else None
    quiet_observations = [row for row in outputs + nontranslation
                          if row["raw"].get("capture_phase") == "quiet_precondition"]
    outputs = [row for row in outputs if row["raw"].get("capture_phase") != "quiet_precondition"]
    nontranslation = [row for row in nontranslation if row["raw"].get("capture_phase") != "quiet_precondition"]
    aligner = Alignment(spec, Path(spec_path).parent, cache_path, allow_download)
    covered = coverage(manifest, attempts, events)
    for attempt in attempts:
        attempt["covered_until_ns"] = covered[attempt["clock_session"]]
    for output in outputs:
        raw = output["raw"]
        candidates = [row for row in sentences if row["scored"] and row["kind"] in ("chunk", "repeat") and row["kind"] == output["capture_kind"] and row["config"] == raw.get("config")
                      and row["clock_session"] == raw.get("clock_session") and row["start_ns"] is not None
                      and row["start_ns"] - 5_000_000_000 <= raw["t_ns"] <= (row["deadline_ns"] or row["end_ns"]) + 120_000_000_000]
        output["alignment"] = aligner.align(output, candidates, sentences)
    for row in sentences:
        timing(row, outputs, covered[row["clock_session"]])
    for turn in turns:
        members = {row["id"] for row in sentences if row["turn_id"] == turn["id"]}
        selected = [output for output in outputs if members.intersection(output["alignment"]["sentence_ids"]) and turn["deadline_ns"] is not None and output["raw"]["t_ns"] <= turn["deadline_ns"]]
        changes = [row for row in selected if row["content_changed"] is True]
        turn["lul"] = metric((max(row["raw"]["t_ns"] for row in changes) - turn["end_ns"]) / 1e9 if changes and not any(row["content_changed"] is None for row in selected) and turn["eligible"] else None,
                             None if changes and not any(row["content_changed"] is None for row in selected) and turn["eligible"] else "No supported related content change")
    segments = assemble_segments(sentences, turns, outputs, spec.get("quality_scores", {}))
    for score in spec.get("quality_scores", {}).values():
        if not score.get("provenance"):
            raise ValueError("Quality scores require provenance")
    if applicability is not None:
        exclude_inapplicable(attempts, sentences, turns, segments, outputs, applicability)
    excluded_by_reason = defaultdict(list)
    for segment in segments:
        if not segment["eligible"]:
            reasons = [segment.get("quality_eligibility_reason"), segment.get("reason")]
            if segment.get("population_eligible") is False:
                reasons.append("analysis_applicability_excluded")
            if segment.get("status") and segment["status"] not in ("done", "product_failure"):
                reasons.append(f"attempt_status:{segment['status']}")
            for reason in dict.fromkeys(reason for reason in reasons if reason):
                excluded_by_reason[reason].append(segment["id"])
            if not any(reasons):
                excluded_by_reason["ineligible_segment"].append(segment["id"])
    supplied_scores = [segment for segment in segments if segment.get("quality_score") is not None
                       and isinstance(segment["quality_score"].get("major_error"), bool)]
    report = {"schema_version": 1, "version": VERSION, "created_utc": utc_now(), "measurement_date": manifest.get("updated_wall"),
              "specification_version": spec["version"], "run": manifest["run"], "synthetic": manifest["plan"].get("synthetic", False),
              "definitions": DEFINITIONS, "provenance": provenance, "alignment_provenance": aligner.provenance,
              "application_observations": manifest.get("application_observations", []), "harness": {key: manifest["plan"].get(key) for key in ("harness_revision", "harness_sources", "frozen_rule_revision")},
              "attempts": [{key: value for key, value in attempt.items() if key not in ("reference", "callbacks")} for attempt in attempts],
              "outputs": outputs, "sentences": sentences, "turns": turns, "quality_segments": segments,
              "nontranslation_observations": nontranslation,
              "quiet_precondition_observations": quiet_observations,
              "isolated": isolated_results(attempts, outputs),
              "diagnostics": diagnostics(attempts, sentences, outputs, spec, nontranslation=nontranslation),
              "limitations": ["No actual app readiness inferred; empirical interpretation requires issue #4 evidence",
                              "OSC last update is not semantic completion", "Automatic lexical proposals are uncalibrated; full-run source correspondence requires adjudicated evidence", "No paid services are called",
                              "Prepared reference uncertainty, local-only assets and rights restrictions survive derived reports"]}
    if applicability is not None:
        report["applicability"] = applicability
    report["alignment_cache"] = {"schema_version": 1, "version": VERSION, "provenance": aligner.provenance,
                                 "links": {row["id"]: {**row["alignment"], "binding": cache_binding(row, sentences)} for row in outputs}}
    report.update(aggregate(report, spec.get("bootstrap", {})))
    report["quality_score_coverage"] = {
        "population": "All report quality segments; each aggregate separately declares its eligible/scored population",
        "total_segments": len(segments), "eligible_segments": sum(segment["eligible"] for segment in segments),
        "excluded_segments": sum(not segment["eligible"] for segment in segments),
        "supplied_major_error_scores": len(supplied_scores),
        "scored_eligible_segments": sum(segment["eligible"] for segment in supplied_scores),
        "excluded_major_error_scores": sum(not segment["eligible"] for segment in supplied_scores),
        "excluded_by_reason": dict(excluded_by_reason),
    }
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        atomic_json(Path(output_path), report)
    return report
