from __future__ import annotations

from collections import Counter

from .metrics_alignment import final_outputs, is_translation
from .metrics_inputs import metric, source_time


def edit_distance(left, right):
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def erased(left, right):
    previous = [0] * (len(right) + 1)
    for a in left:
        current = [0]
        for j, b in enumerate(right, 1):
            current.append(previous[j - 1] + 1 if a == b else max(previous[j], current[-1]))
        previous = current
    return len(left) - previous[-1]


def union_duration(intervals):
    end, total = None, 0
    for start, stop in sorted(intervals):
        if end is None or start > end:
            total += stop - start
        elif stop > end:
            total += stop - end
        end = max(end, stop) if end is not None else stop
    return total


def source_cer(refs, outputs, evidence):
    references = {row["id"]: row for row in refs}
    reference_order = {row["id"]: i for i, row in enumerate(sorted(refs, key=lambda row: (row["start"], row["id"])))}
    observations = []
    owners = {}
    for output in final_outputs(outputs):
        if output["source_text"] is None:
            continue
        sentence_ids = set(output["alignment"]["sentence_ids"])
        if not sentence_ids.intersection(references):
            continue
        supplied = evidence.get(output["id"], {})
        record = {"output_id": output["id"], "source_text": output["source_text"],
                  "sentence_ids": sorted(sentence_ids), "source_coverage": supplied.get("source_coverage"),
                  "diagnostic_evidence": supplied, "interpretation": output["interpretation"]}
        observations.append(record)
        for sentence_id in sentence_ids:
            owners.setdefault(sentence_id, []).append(len(observations) - 1)
    pending = set(range(len(observations)))
    reconstructions = []
    while pending:
        todo = [min(pending)]
        component = set()
        sentence_ids = set()
        while todo:
            index = todo.pop()
            if index in component:
                continue
            component.add(index)
            pending.discard(index)
            for sentence_id in observations[index]["sentence_ids"]:
                if sentence_id in sentence_ids:
                    continue
                sentence_ids.add(sentence_id)
                todo.extend(owner for owner in owners[sentence_id] if owner not in component)
        records = [observations[index] for index in sorted(component)]
        reason = None
        spans = []
        if not sentence_ids.issubset(references):
            reason = "Source message also covers reference sentences outside this attempt's scored population"
        else:
            for record in records:
                coverage = record["source_coverage"]
                if coverage is None and len(records) == 1:
                    coverage = [{"sentence_id": sentence_id, "start": 0, "end": len(references[sentence_id]["text"])}
                                for sentence_id in sorted(sentence_ids, key=reference_order.get)]
                if not isinstance(coverage, list) or not coverage:
                    reason = ("Multiple source messages share reference coverage; explicit source_coverage is required to distinguish fragments from snapshots"
                              if coverage is None else "source_coverage must be a nonempty list of reference sentence ranges")
                    break
                if record["source_coverage"] is not None and not record["diagnostic_evidence"].get("provenance"):
                    raise ValueError("Diagnostic evidence requires provenance")
                local = []
                for span in coverage:
                    if not isinstance(span, dict):
                        reason = "source_coverage entries must be reference sentence ranges"
                        break
                    sentence_id, start, end = span.get("sentence_id"), span.get("start"), span.get("end")
                    if (sentence_id not in record["sentence_ids"] or sentence_id not in references
                            or type(start) is not int or type(end) is not int
                            or not 0 <= start < end <= len(references[sentence_id]["text"])):
                        reason = "source_coverage requires linked sentence IDs and integer half-open Unicode ranges within reference bounds"
                        break
                    local.append((reference_order[sentence_id], start, end, record["output_id"]))
                if reason:
                    break
                if local != sorted(local):
                    reason = "Source message coverage must follow reference sentence and character order"
                    break
                spans.extend(local)
        ordered_ids = []
        if not reason:
            positions = {reference_order[sentence_id]: 0 for sentence_id in sentence_ids}
            for sentence_index, start, end, output_id in sorted(spans):
                if start != positions[sentence_index]:
                    reason = "Source coverage has a gap or overlap; each reference character must be covered exactly once"
                    break
                positions[sentence_index] = end
                if not ordered_ids or ordered_ids[-1] != output_id:
                    if output_id in ordered_ids:
                        reason = "Interleaved merged source coverage cannot be reconstructed without within-source-text offsets"
                        break
                    ordered_ids.append(output_id)
            if not reason and any(positions[reference_order[sentence_id]] != len(references[sentence_id]["text"]) for sentence_id in sentence_ids):
                reason = "Source coverage is incomplete; full reference coverage is required"
        reconstruction = {"output_ids": [record["output_id"] for record in records],
                          "sentence_ids": sorted(sentence_ids, key=lambda value: reference_order.get(value, len(reference_order))),
                          "observations": records, "status": "N/A" if reason else "available", "reason": reason}
        if not reason:
            by_id = {record["output_id"]: record for record in records}
            reference = "".join(references[sentence_id]["text"] for sentence_id in reconstruction["sentence_ids"])
            source = "".join(by_id[output_id]["source_text"] for output_id in ordered_ids)
            reconstruction.update({"reconstruction_output_ids": ordered_ids, "source_text": source,
                                   "edits": edit_distance(reference, source), "reference_characters": len(reference)})
        reconstructions.append(reconstruction)
    unresolved = [row for row in reconstructions if row["status"] == "N/A"]
    denominator = sum(row.get("reference_characters", 0) for row in reconstructions)
    edits = sum(row.get("edits", 0) for row in reconstructions)
    return metric(edits / denominator if denominator and not unresolved else None,
                  "Source reconstruction unresolved: " + "; ".join(dict.fromkeys(row["reason"] for row in unresolved)) if unresolved
                  else None if denominator else "App source text and determinable source correspondence required",
                  "edits/reference_character", denominator=None if unresolved else denominator, evidence=reconstructions,
                  supported_reference_characters=denominator, supported_edits=edits,
                  normalization="none; Unicode code points including whitespace and punctuation",
                  guidance="Japanese automatic-reference CER is guidance, not validated accuracy")


def diagnostics(attempts, sentences, outputs, spec, *, nontranslation=()):
    evidence = spec.get("evidence", {})
    by_id = {row["id"]: row for row in outputs}
    rows = []
    for attempt in attempts:
        refs = [row for row in sentences if row["attempt_id"] == attempt["id"] and row["scored"]]
        ids = {row["id"] for row in refs}
        selected = [row for row in outputs if ids.intersection(row["alignment"]["sentence_ids"])]
        observed = [row for row in outputs if row["raw"].get("config") == attempt["config"] and row["raw"].get("clock_session") == attempt["clock_session"]
                    and row["raw"].get("attempt") == attempt["id"]]
        independent = [row for row in selected if row["relation"] not in ("resend", "revision")]
        split = sum(sum(ref["id"] in row["alignment"]["sentence_ids"] for row in independent) > 1 for ref in refs)
        merged = sum(len(set(row["alignment"]["sentence_ids"]) & ids) > 1 for row in independent)
        unknown = [row["id"] for row in outputs if row["alignment"]["status"] == "unknown" and ids.intersection(row["alignment"].get("candidate_ids", []))]
        speaking = union_duration(attempt["stage_data"].get("speech_intervals", []))
        boundaries = []
        revisions = []
        for output in selected:
            supplied = evidence.get(output["id"], {})
            if supplied and not supplied.get("provenance"):
                raise ValueError("Diagnostic evidence requires provenance")
            if output["relation"] == "revision":
                support = output["interpretation"]["supports"]
                parent = by_id.get(output["parent_id"])
                revisions.append({"output_id": output["id"], "characters_erased": metric(erased(parent["text"], output["text"]) if parent and support.get("erasure") else None,
                                                                                      None if parent and support.get("erasure") else "App rules do not support character erasure", "characters"),
                                  "revision_supported": bool(support.get("revision"))})
            boundary = supplied.get("boundary")
            if boundary:
                if not boundary.get("identifiable") or supplied.get("clock_session") != output["raw"].get("clock_session"):
                    boundaries.append({"output_id": output["id"], "status": "N/A", "reason": "Boundary correspondence or same-clock evidence not identifiable", "evidence": supplied})
                    continue
                source = boundary.get("source_boundary_ns")
                sentence_end = boundary.get("sentence_end_ns")
                expected = boundary.get("expected_source_unit_ids")
                delivered = boundary.get("delivered_source_unit_ids")
                loss = len(set(expected) - set(delivered)) if expected is not None and delivered is not None else boundary.get("missing_source_units")
                duplication = len(delivered) - len(set(delivered)) if delivered is not None else boundary.get("duplicated_source_units")
                boundaries.append({"output_id": output["id"], "evidence": supplied,
                                   "endpoint_delay": metric((output["raw"]["t_ns"] - source) / 1e9 if source is not None else None,
                                                            None if source is not None else "Identifiable source boundary in OSC clock required", endpoint="OSC receipt; not internal app endpoint"),
                                   "mid_sentence_cut": metric(source < sentence_end if source is not None and sentence_end is not None else None,
                                                              None if source is not None and sentence_end is not None else "Identifiable sentence boundary required", "boolean"),
                                   "boundary_loss": metric(loss, None if loss is not None else "Source-unit boundary evidence absent", "source_units"),
                                   "boundary_duplication": metric(duplication, None if duplication is not None else "Source-unit boundary evidence absent", "source_units"),
                                   "japanese_speaker_boundary_crossing": metric((len(set(boundary["source_speakers"])) > 1 if "source_speakers" in boundary else boundary.get("speaker_crossing")) if attempt["stage_data"].get("direction") in ("D4", "D6") else None,
                                                                               "Exploratory; estimated speaker evidence required" if "speaker_crossing" not in boundary and "source_speakers" not in boundary else None, "boolean"),
                                   "japanese_pre_predicate_cut": metric(source < boundary["predicate_end_ns"] if source is not None and boundary.get("predicate_end_ns") is not None else None,
                                                                        None if source is not None and boundary.get("predicate_end_ns") is not None else "Predicate-position evidence absent; exploratory", "boolean")})
        order = [min((ref["start"] for ref in refs if ref["id"] in row["alignment"]["sentence_ids"]), default=0) for row in independent]
        accumulation = []
        for start, end in attempt["stage_data"].get("speech_intervals", []):
            if end - start < spec.get("long_speech_min_seconds", 30):
                continue
            points = [{"sentence_id": ref["id"], "elapsed_speech_seconds": ref["end"] - start, "lul_seconds": ref["lul"]["value"]}
                      for ref in refs if start <= ref["start"] and ref["end"] <= end and ref.get("lul", {}).get("value") is not None]
            accumulation.append({"start": start, "end": end, "points": points,
                                 "last_minus_first_lul": metric(points[-1]["lul_seconds"] - points[0]["lul_seconds"] if len(points) > 1 else None,
                                                                None if len(points) > 1 else "At least two supported latency points required")})
        rows.append({"attempt_id": attempt["id"], "sentence_splits": metric(split if not unknown else None, None if not unknown else "Unknown source correspondence prevents complete split count", "sentences", denominator=len(refs), unknown_output_ids=unknown),
                     "message_merges": metric(merged if not unknown else None, None if not unknown else "Unknown source correspondence prevents complete merge count", "messages", denominator=len(independent), unknown_output_ids=unknown),
                     "segmentation_interpretation": "Estimated correspondence only; splitting/merging alone is neither good nor bad translation",
                     "messages_per_speaking_minute": metric(len(observed) * 60 / speaking if speaking else None, None if speaking else "Annotated speaking duration absent", "messages/minute", numerator=len(observed), denominator_seconds=speaking,
                                                            attribution="capture-context output, not asserted source correspondence"),
                     "output_role_counts": dict(Counter(row.get("output_role", "translation") for row in observed)),
                     "unresolved_output_ids": [row["id"] for row in observed if not is_translation(row)],
                     "duplicates": metric(sum(row["duplicate_observed"] for row in observed), None, "messages", denominator=len(observed)),
                     "order_changes": metric(sum(right < left for left, right in zip(order, order[1:])) if len(order) > 1 and not unknown else None, "At least two supported messages and determinate correspondence required" if len(order) < 2 or unknown else None, "adjacent_order_inversions", denominator=max(len(order) - 1, 0)),
                     "revisions": metric(sum(row["revision_supported"] for row in revisions) if any(row["interpretation"]["supports"].get("revision") for row in selected) else None,
                                         None if any(row["interpretation"]["supports"].get("revision") for row in selected) else "App rules do not support revision inference", "updates"),
                     "erasure": revisions or metric(reason="No supported revision pairs", unit="characters"),
                     "source_cer": source_cer(refs, selected, evidence),
                     "endpoint_cut_tradeoff": boundaries or metric(reason="Identifiable source boundaries and app endpoint/cut signals absent", unit="boundary_records"),
                     "boundary_loss_duplication": metric(reason="Requires explicit identifiable source-unit evidence; no lexical loss inferred from split/merge counts", unit="source_units") if not boundaries else boundaries,
                     "japanese_explorations": metric(reason="Requires supplied speaker/predicate boundary evidence; automatic references exploratory", unit="boundary_records") if not boundaries else boundaries,
                     "long_speech_accumulation": accumulation or metric(reason="No sufficiently long annotated uninterrupted speech with supported latency", unit="series")})
    nonspeech = []
    for attempt in attempts:
        if attempt["kind"] != "nonspeech":
            continue
        playback = attempt["playback"]
        intervals = spec.get("nonspeech_intervals", {}).get(str(attempt["stage"]), [{"label": "silence_keyboard_nonverbal", "start": 0, "end": 120}, {"label": "background_human_conversation", "start": 120, "end": 180}])
        for interval in intervals:
            start_ns = source_time(playback, attempt["callbacks"], interval["start"], attempt["stage_data"].get("sample_rate", 48000)) if playback else None
            end_ns = source_time(playback, attempt["callbacks"], interval["end"], attempt["stage_data"].get("sample_rate", 48000)) if playback else None
            valid = start_ns is not None and end_ns is not None
            quiet_met = attempt.get("quiet_precondition_met")
            clean_reason = ("Quiet precondition not met; unresolved carryover prevents clean nonspeech attribution"
                            if quiet_met is False else "Quiet precondition observation unavailable"
                            if quiet_met is None else "Playback/cable timing unavailable" if not valid else None)
            observed = [row for row in outputs if valid and row["raw"].get("clock_session") == attempt["clock_session"] and row["raw"].get("config") == attempt["config"]
                        and start_ns <= row["raw"]["t_ns"] < end_ns]
            source_only = [row for row in nontranslation if valid and row["raw"].get("clock_session") == attempt["clock_session"] and row["raw"].get("config") == attempt["config"]
                           and start_ns <= row["raw"]["t_ns"] < end_ns]
            selected = [row["id"] for row in observed]
            nonspeech.append({"attempt_id": attempt["id"], **interval, "count": metric(len(selected) if valid else None, None if valid else "Playback/cable timing unavailable", "observed_outputs"),
                              "raw_activity_count": metric(len(observed) + len(source_only) if valid else None, None if valid else "Playback/cable timing unavailable", "nonempty_chatbox_inputs"),
                              "known_translation_count": metric(sum(is_translation(row) for row in observed) if valid else None, None if valid else "Playback/cable timing unavailable", "known_translation_outputs"),
                              "unresolved_output_ids": [row["id"] for row in observed if not is_translation(row)],
                              "source_only_output_ids": [row["id"] for row in source_only],
                              "clean_nonspeech_count": metric(len(selected) if valid and quiet_met is True else None,
                                                              clean_reason, "observed_outputs"),
                              "quiet_precondition_met": quiet_met,
                              "unresolved_carryover": attempt.get("unresolved_carryover"),
                              "nonspeech_quiet_wait": attempt.get("nonspeech_quiet_wait"),
                              "observation_complete": bool(valid and attempt.get("covered_until_ns", 0) >= end_ns),
                              "observed_seconds": max(0, min(end_ns, attempt.get("covered_until_ns", 0)) - start_ns) / 1e9 if valid else None,
                              "output_ids": selected, "scope": "Observed interval count, never hourly extrapolation"})
    common = []
    for clip in spec.get("common_clips", []):
        refs = [row for row in sentences if row["chunk_id"] == clip["chunk_id"] and clip.get("start", float("-inf")) <= row["end"] and row["start"] <= clip.get("end", float("inf"))]
        ids = {row["id"] for row in refs}
        common.append({"selection": clip, "timelines": [{"output_id": row["id"], "t_ns": row["raw"]["t_ns"], "clock_session": row["raw"].get("clock_session"),
                                                         "text": row["text"], "raw_text": row["raw"]["args"][0], "output_role": row.get("output_role", "translation"),
                                                         "relation": row["relation"], "alignment": row["alignment"]}
                                                        for row in outputs if ids.intersection(row["alignment"]["sentence_ids"]) or any(
                                                            row["raw"].get("config") == ref["config"] and row["raw"].get("clock_session") == ref["clock_session"]
                                                            and ref["start_ns"] is not None and ref["end_ns"] is not None
                                                            and ref["start_ns"] <= row["raw"]["t_ns"] <= ref["end_ns"] + 15_000_000_000 for ref in refs)],
                       "status": "available" if refs else "N/A", "reason": None if refs else "Selected reference unavailable",
                       "association": "Known alignment or source-window temporal inclusion; unaligned correspondence remains unknown"})
    internal = spec.get("puripuly_internal", [])
    if internal and any(not row.get("provenance") or not row.get("clock_session") for row in internal):
        raise ValueError("Internal diagnostics require provenance and clock_session")
    internal_rows = []
    for row in internal:
        stages = {}
        for label, start_key, end_key in (("endpoint", "speech_end_ns", "endpoint_ns"), ("asr", "asr_start_ns", "asr_end_ns"),
                                         ("queue", "queued_ns", "generation_start_ns"), ("first_token", "generation_start_ns", "first_token_ns"),
                                         ("generation", "generation_start_ns", "generation_end_ns"), ("output", "generation_end_ns", "output_ns")):
            start, end = row.get(start_key), row.get(end_key)
            stages[label] = metric((end - start) / 1e9 if start is not None and end is not None else None, None if start is not None and end is not None else "Required internal timestamps absent")
        internal_rows.append({"provenance": row["provenance"], "clock_session": row.get("clock_session"), "decomposition": stages})
    return {"attempts": rows, "nonspeech": nonspeech, "common_clips": common,
            "puripuly_internal": {"scope": "Separate internal app signals; never cross-app OSC endpoint metrics", "records": internal_rows,
                                  "status": "available" if internal else "N/A", "reason": None if internal else "No PuriPuly internal signals supplied"}}
