"""Reproduce R2 ASCEND human speech on a declared reconstruction-v1 clock.

Offline standard-library preparation only. Whole native clips, fixed original
people, pinned released references and exact sample maps are preserved. New gaps
are reconstruction, never recovered historical silence. Source review and final
acceptance remain distinct from deterministic materialization.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tarfile
import sys
import wave


RATE = 16000
REQUIRED = {"P1": (3, 1), "P2": (9, 1), "P3": (6, 1), "T1": (9, 4)}
FILENAME = re.compile(r"waves/ses(\d+)_spk(\d+)(?:_(\d+))?_L(\d+)_([\d.]+)_([\d.]+)\.wav")


def sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def checked_bytes(path, expected):
    payload = Path(path).read_bytes()
    if sha256(payload) != expected:
        raise ValueError(f"Pinned source checksum mismatch: {Path(path).name}")
    return payload


def file_sha256(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def check_reservations(record):
    reservations = record["split_reservations"]
    groups = {split: [set(group) for group in reservations[f"{split}_reserved_original_groups"]]
              for split in ("main", "development")}
    people = {split: set().union(*values) for split, values in groups.items()}
    if people["main"] & people["development"]:
        raise ValueError("Main/development connected original-speaker reservations overlap")
    used, identities, counts, p1 = set(), set(), {}, set()
    for candidate in record["candidates"]:
        identity, kind, split = candidate["id"], candidate["kind"], candidate["project_split"]
        if identity in identities or kind not in REQUIRED or split not in groups:
            raise ValueError("Invalid or duplicate episode identity/kind/split")
        identities.add(identity)
        counts[kind, split] = counts.get((kind, split), 0) + 1
        reserved = set(candidate["reserved_original_speakers"])
        if reserved not in groups[split] or not set(candidate["roles"].values()) <= reserved:
            raise ValueError("Candidate does not preserve its complete connected-speaker reservation")
        clips = candidate["clips"]
        if not clips or len(set(candidate["roles"].values())) != len(candidate["roles"]):
            raise ValueError("An episode needs clips and distinct fixed original-person roles")
        if kind in ("P2", "T1") and set(candidate["roles"]) != {"A", "B"}:
            raise ValueError("Dialogue requires two fixed roles")
        if kind in ("P1", "P3") and set(candidate["roles"]) != {"A"}:
            raise ValueError("P1/P3 requires one original speaker")
        expected_directions = ({"A": {"input_channel": "peer", "source_language": "en", "target_language": "zh"},
                                "B": {"input_channel": "self", "source_language": "zh", "target_language": "en"}}
                               if kind == "T1" else
                               {"peer": {"source_language": "en", "target_language": "zh",
                                         "source_person_roles": list(candidate["roles"])}})
        if candidate["directions"] != expected_directions:
            raise ValueError("Preserve fixed translation directions and ordinary mixed peer input")
        expected_group = "ascend-original-people-" + "-".join(map(str, sorted(reserved)))
        if candidate["dependency_group_id"] != expected_group or candidate["source_case_id"] != identity:
            raise ValueError("Preserve root case and connected-person dependency identities")
        previous_L, local_key, previous_person_clock = -1, None, {}
        for clip in clips:
            key = clip["natural_source_key"]
            if key in used or clip["archive_member"] in used:
                raise ValueError("Credited source intervals must not duplicate across episodes/types")
            used.update((key, clip["archive_member"]))
            if key != f"{record['dataset']}@{record['revision']}/{clip['upstream_split']}/{clip['upstream_id']}":
                raise ValueError("Source key must include pinned revision and split-local ID")
            if candidate["roles"].get(clip["logical_role"]) != clip["original_speaker_id"]:
                raise ValueError("Routing must preserve original person, not language or row parity")
            if clip["annotation_L"] <= previous_L:
                raise ValueError("Preserve the reviewed local annotation order")
            previous_L = clip["annotation_L"]
            key = (clip["session_id"], (clip["filename_speaker"] - 1) // 2)
            if local_key is not None and key != local_key:
                raise ValueError("Cut at source pair/session changes; do not join unrelated rows")
            local_key = key
            person = clip["original_speaker_id"]
            clock = (clip["filename_part"], clip["nominal_filename_start_sample_not_common_clock"])
            if person in previous_person_clock:
                part, start = previous_person_clock[person]
                if part != clock[0] or start > clock[1]:
                    raise ValueError("Cut at recording part changes or same-person clock resets")
            previous_person_clock[person] = clock
        if kind == "P1":
            if len(clips) != 1:
                raise ValueError("P1 must remain one intact native file")
            p1.add((clips[0]["upstream_split"], clips[0]["upstream_id"], split))
    expected_p1 = {("train", "01254", "main"), ("train", "00412", "main"),
                   ("train", "07714", "main"), ("test", "00002", "development")}
    if p1 != expected_p1:
        raise ValueError("Preserve the four preselected P1 split-local identities")
    for kind, (main, development) in REQUIRED.items():
        if (counts.get((kind, "main"), 0), counts.get((kind, "development"), 0)) != (main, development):
            raise ValueError(f"Preserve required {kind} main/development quantities")
    return {"main_reserved_original_speakers": sorted(people["main"]),
            "development_reserved_original_speakers": sorted(people["development"]),
            "known_intersection": [], "unknown_participation_certified_absent": False}


def connected_groups(tables):
    """Conservative original-person components of the inspected filename pairs."""
    pairs = {}
    for rows in tables.values():
        for row in rows:
            match = FILENAME.fullmatch(row["file_name"])
            if not match:
                raise ValueError("Unrecognized ASCEND source filename")
            pairs.setdefault((int(match[2]) - 1) // 2, set()).add(int(row["original_speaker_id"]))
    components = []
    for people in pairs.values():
        merged = set(people)
        for old in list(components):
            if old & merged:
                merged |= old
                components.remove(old)
        components.append(merged)
    # A newly merged component can connect earlier components transitively.
    changed = True
    while changed:
        changed = False
        for i, a in enumerate(components):
            for b in components[i + 1:]:
                if a & b:
                    a |= b
                    components.remove(b)
                    changed = True
                    break
            if changed:
                break
    return sorted(sorted(group) for group in components)


def reference_row(tables, clip):
    rows = tables[clip["upstream_split"]]
    index = int(clip["upstream_id"])
    if clip["upstream_id"] != f"{index:05}" or not 0 <= index < len(rows):
        raise ValueError("Invalid split-local five-digit source ID")
    row = rows[index]
    if row["file_name"] != clip["archive_member"]:
        raise ValueError("CSV row identity disagrees with selected archive member")
    if int(row["original_speaker_id"]) != clip["original_speaker_id"]:
        raise ValueError("Original speaker identity disagrees with CSV")
    match = FILENAME.fullmatch(row["file_name"])
    if not match or int(match[4]) != clip["annotation_L"]:
        raise ValueError("Annotation identity disagrees with source filename")
    if round(Decimal(match[5]) * RATE) != clip["nominal_filename_start_sample_not_common_clock"]:
        raise ValueError("Filename-local sample position disagrees with metadata")
    text = row["transcription"].encode("utf-8")
    if sha256(text) != clip["reference_utf8_sha256"]:
        raise ValueError("Released reference text checksum mismatch")
    return row, text


def decode_wave(payload, frames, expected_pcm):
    with wave.open(io.BytesIO(payload), "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) != (1, 2, RATE, "NONE"):
            raise ValueError("Source must remain mono 16 kHz PCM16")
        if source.getnframes() != frames:
            raise ValueError("Actual source frame count differs from pinned evidence")
        pcm = source.readframes(frames)
    if len(pcm) != frames * 2 or sha256(pcm) != expected_pcm:
        raise ValueError("Decoded PCM differs from pinned evidence")
    return pcm


def timeline(clips, kind, gap_samples=4800, relative_offset=None):
    """Metadata first; an infeasible/unidentified model has an explicit fallback.

    Offsets are conditional nonoverlap constraints, not measured recorder lags.
    Every integer position uses decoded frame counts. No clipping, crossfade,
    per-turn repair or suppression of internal source samples is permitted.
    """
    if gap_samples < 0:
        raise ValueError("Reconstructed gap must be nonnegative")
    starts = [c["nominal_filename_start_sample_not_common_clock"] for c in clips]
    lower, upper, same_conflict = None, None, False
    for a, b, start_a, start_b in zip(clips, clips[1:], starts, starts[1:]):
        bound = start_a + a["source_frames"] - start_b
        if a["logical_role"] == b["logical_role"]:
            same_conflict |= bound > 0
        elif b["logical_role"] == "B":
            lower = bound if lower is None else max(lower, bound)
        else:
            upper = -bound if upper is None else min(upper, -bound)
    if kind == "P1":
        positions, method, reason = [0], "native", None
        offset = None
    elif kind == "P3" and not same_conflict:
        positions = [s - starts[0] for s in starts]
        method, reason, offset = "same_speaker_filename_continuation", None, None
    else:
        offset = relative_offset
        if offset is None and lower is not None and upper is not None and lower <= upper:
            offset = (lower + upper) // 2
        feasible = (not same_conflict and offset is not None
                    and (lower is None or offset >= lower) and (upper is None or offset <= upper))
        if feasible:
            shifted = [s + (offset if c["logical_role"] == "B" else 0) for s, c in zip(starts, clips)]
            origin = min(shifted)
            positions = [s - origin for s in shifted]
            method, reason = "metadata_relative_offset", None
        else:
            positions, cursor = [], 0
            for clip in clips:
                positions.append(cursor)
                cursor += clip["source_frames"] + gap_samples
            method = "explicit_paced_continuation" if kind == "P3" else "explicit_paced_dialogue"
            reason = ("same-person clip intervals overlap or reset" if same_conflict else
                      "conditional nonoverlap offset constraints conflict" if lower is not None and upper is not None and lower > upper else
                      "local sequence does not bound both sides of a relative offset")
            offset = None
    end = max(start + clip["source_frames"] for start, clip in zip(positions, clips))
    gaps = []
    for a, b, start_a, start_b in zip(clips, clips[1:], positions, positions[1:]):
        finish = start_a + a["source_frames"]
        if start_b < finish:
            raise ValueError("Reconstruction may not overlap or overwrite whole clips")
        gaps.append({"after_L": a["annotation_L"], "before_L": b["annotation_L"],
                     "playback_samples": [finish, start_b], "samples": start_b - finish,
                     "origin": "experimenter_fixed_gap" if method.startswith("explicit_paced") else
                               "filename_inferred_uncovered_interval_zero_filled",
                     "original_audio_or_historical_silence_recovered": False})
    return {"method": method, "positions": positions, "frames": end,
            "relative_offset_B_samples": offset, "conditional_offset_bounds_samples": [lower, upper],
            "fallback_reason": reason, "fixed_paced_gap_samples": gap_samples,
            "gaps": gaps, "clock": "new_common_playback_samples_16000Hz",
            "historical_synchrony_claimed": False}


def assemble(candidate, pcm_by_key):
    mapping = timeline(candidate["clips"], candidate["kind"],
                       candidate["timing_policy"]["paced_gap_samples"],
                       candidate["timing_policy"].get("relative_offset_B_samples"))
    if mapping != candidate["timeline"]:
        raise ValueError("Frozen reconstruction positions/policy no longer reproduce")
    buffers = {role: bytearray(mapping["frames"] * 2) for role in candidate["roles"]}
    mixed = bytearray(mapping["frames"] * 2)
    for clip, start in zip(candidate["clips"], mapping["positions"]):
        pcm = pcm_by_key[clip["natural_source_key"]]
        if len(pcm) != clip["source_frames"] * 2:
            raise ValueError("Source PCM length disagrees with source map")
        finish = (start + clip["source_frames"]) * 2
        buffers[clip["logical_role"]][start * 2:finish] = pcm
        mixed[start * 2:finish] = pcm
    return mapping, buffers, mixed


def reference_spans(text):
    """Exact source-character spans, not rewritten monolingual source sentences."""
    return [{"source_characters": [m.start(), m.end()], "text": m.group(),
             "language": "unknown" if m.group() == "[UNK]" else
                         "zh" if re.search(r"[\u3400-\u9fff]", m.group()) else "en"}
            for m in re.finditer(r"\[UNK\]|[\u3400-\u9fff]+|[A-Za-z0-9][A-Za-z0-9 '?,.\-]*", text)]


def checkpoint_map(candidate, definitions, mapping, source_texts):
    """Bind curated meanings to actual scored source spans, not context echoes.

    Membership, language, person and chronology are executable guarantees.
    Whether a concept is entailed by the cited words remains curated semantic
    review; English loanwords cannot mechanically certify a Chinese proposition.
    """
    result = []
    selected = {clip["annotation_L"]: (i, clip) for i, clip in enumerate(candidate["clips"])}
    for checkpoint in definitions:
        end_L = checkpoint["end_L"]
        if end_L not in selected:
            raise ValueError("Checkpoint evidence is outside its source episode")
        index, clip = selected[end_L]
        anchor = checkpoint["source_evidence_end_sample_proposal"]
        if (not 0 <= anchor <= clip["source_frames"] or clip["logical_role"] != checkpoint["role"]
                or not checkpoint["required_concepts"] or not checkpoint["allowed_paraphrase_concepts"]
                or any(L not in selected or L > end_L for L in checkpoint["evidence_Ls"])):
            raise ValueError("Checkpoint evidence must preserve role, meaning and past-only source scope")
        target = "zh" if candidate["kind"] == "T1" and checkpoint["role"] == "B" else "en"
        citations = checkpoint["scored_translation_evidence"]
        if not citations:
            raise ValueError("Checkpoint requires actual scored translation evidence, not context alone")
        scored = []
        for citation in citations:
            L = citation["annotation_L"]
            if L not in checkpoint["evidence_Ls"] or L not in selected or L > end_L:
                raise ValueError("Scored translation evidence must belong to past checkpoint source scope")
            _, source = selected[L]
            if source["logical_role"] != checkpoint["role"]:
                raise ValueError("Scored translation evidence must belong to the checkpoint person")
            text = source_texts[L]
            start, end = citation["source_characters"]
            spans = reference_spans(text)
            if (not 0 <= start < end <= len(text)
                    or not any(s["language"] == target and s["source_characters"][0] <= start
                               and end <= s["source_characters"][1] for s in spans)
                    or not re.search(r"[\u3400-\u9fff]" if target == "zh" else r"[A-Za-z]", text[start:end])):
                raise ValueError("Scored checkpoint evidence must be inside actual translation-target spans")
            scored.append({**citation, "natural_source_key": source["natural_source_key"],
                           "role": source["logical_role"], "language": target, "text": text[start:end]})
        constraints = []
        for constraint in checkpoint["unscored_context_constraints"]:
            if (not constraint["meaning"] or not constraint["evidence_Ls"]
                    or any(L not in selected or L > end_L for L in constraint["evidence_Ls"])):
                raise ValueError("Unscored checkpoint context must preserve past-only source scope")
            constraints.append({**constraint, "required_in_output": False, "translation_credit": False})
        result.append({**checkpoint, "scored_translation_evidence": scored,
                       "unscored_context_constraints": constraints,
                       "output_scope": "Required concepts apply only to the scored translation evidence. Context constrains interpretation but its echo is neither required nor translation credit.",
                       "natural_source_key": clip["natural_source_key"],
                       "playback_evidence_end_sample_proposal": mapping["positions"][index] + anchor,
                       "observation_offsets_seconds": [0, 2, 5, 10, 15],
                       "certified_phonetic_endpoint": False})
    if not result or (candidate["kind"] == "T1" and {cp["role"] for cp in result} != {"A", "B"}):
        raise ValueError("Both T1 roles require substantive reviewed checkpoints")
    return result


def write_wave(path, pcm):
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        output.writeframes(pcm)


def source_payloads(cache, clips):
    wanted = {clip["archive_member"]: clip for clip in clips}
    payloads = {}
    for name in list(wanted):
        if (cache / name).is_file():
            payloads[name] = (cache / name).read_bytes()
            del wanted[name]
    if wanted:
        with tarfile.open(cache / "waves.tar.bz2", "r|bz2") as archive:
            for member in archive:
                name = member.name.removeprefix("./")
                if name in wanted:
                    payloads[name] = archive.extractfile(member).read()
                    del wanted[name]
    if wanted:
        raise ValueError(f"Selected source members missing from retained archive: {sorted(wanted)}")
    return payloads


def materialize(catalogue, cache, evidence_path, findings_path, output, curation_path=None):
    catalogue, cache, evidence_path, findings_path, output = map(
        Path, (catalogue, cache, evidence_path, findings_path, output))
    if output.exists():
        raise ValueError("Use a new output directory; never overwrite evidence")
    record = json.loads(catalogue.read_text(encoding="utf-8"))
    grouping = check_reservations(record)
    evidence_bytes = checked_bytes(evidence_path, record["research_evidence"]["sha256"])
    findings_bytes = checked_bytes(findings_path, record["research_evidence"]["original_findings_sha256"])
    evidence = json.loads(evidence_bytes)
    if evidence["source_revision_legacy"] != record["revision"]:
        raise ValueError("Research and candidate source revisions disagree")
    for split in ("main", "development"):
        key = f"{split}_reserved_original_groups"
        if not set().union(*map(set, evidence["p1_ancestry"][key])) <= set().union(*map(set, record["split_reservations"][key])):
            raise ValueError("Preserve all prior connected-speaker reservations")
    curation_bytes = checked_bytes(curation_path or record["curation"]["path"], record["curation"]["sha256"])
    curation = json.loads(curation_bytes)
    archive = cache / "waves.tar.bz2"
    if archive.stat().st_size != record["source_archive"]["bytes"] or file_sha256(archive) != record["source_archive"]["sha256"]:
        raise ValueError("Retained original archive checksum mismatch")
    metadata = {name: checked_bytes(cache / name, spec["sha256"])
                for name, spec in record["source_metadata"].items()}
    tables = {name.removesuffix("_metadata.csv"): list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))
              for name, payload in metadata.items()}
    components = connected_groups(tables)
    for candidate in record["candidates"]:
        if sorted(candidate["reserved_original_speakers"]) not in components:
            raise ValueError("Reservation must include the complete metadata-connected original-person group")
    grouping["metadata_connected_original_groups"] = components
    ancillary = {name: checked_bytes(cache / name, digest) for name, digest in record["ancillary_sha256"].items()}
    clips = [clip for candidate in record["candidates"] for clip in candidate["clips"]]
    payloads = source_payloads(cache, clips)
    pcm_by_key, references = {}, {}
    for clip in clips:
        row, text = reference_row(tables, clip)
        payload = payloads[clip["archive_member"]]
        if sha256(payload) != clip["source_wav_sha256"]:
            raise ValueError("Selected source WAV checksum mismatch")
        pcm_by_key[clip["natural_source_key"]] = decode_wave(payload, clip["source_frames"], clip["decoded_pcm16le_sha256"])
        references[clip["natural_source_key"]] = row, text
    # Validate and assemble all inputs before making any output directory.
    prepared = [(c, *assemble(c, pcm_by_key)) for c in record["candidates"]]
    checkpoints_by_id = {
        c["id"]: checkpoint_map(c, curation["episodes"][c["id"]]["checkpoints"], mapping,
                                {clip["annotation_L"]: references[clip["natural_source_key"]][0]["transcription"]
                                 for clip in c["clips"]})
        for c, mapping, _, _ in prepared}
    output.mkdir(parents=True)
    for folder in ("audio", "decoded", "references", "provenance", "sources"):
        (output / folder).mkdir()
    (output / "provenance" / "research-machine-evidence.json").write_bytes(evidence_bytes)
    (output / "provenance" / "research-findings.json").write_bytes(findings_bytes)
    (output / "provenance" / "curation.json").write_bytes(curation_bytes)
    shutil.copyfile(catalogue, output / "provenance" / "catalogue.json")
    for name, payload in {**metadata, **ancillary}.items():
        (output / "provenance" / name).write_bytes(payload)
    for name, payload in payloads.items():
        (output / "sources" / Path(name).name).write_bytes(payload)
    episodes = []
    for candidate, mapping, buffers, mixed in prepared:
        identity = candidate["id"]
        playback = buffers if candidate["kind"] == "T1" else {"peer": mixed}
        assets = {}
        for role, pcm in playback.items():
            stem = f"{identity}-{role}"
            wav_path = output / "audio" / (stem + ".wav")
            if candidate["kind"] == "P1":
                wav_path.write_bytes(payloads[candidate["clips"][0]["archive_member"]])
            else:
                write_wave(wav_path, pcm)
            (output / "decoded" / (stem + ".s16le")).write_bytes(pcm)
            assets[role] = {"audio_path": f"audio/{stem}.wav", "decoded_path": f"decoded/{stem}.s16le",
                            "frames": mapping["frames"], "sample_rate": RATE,
                            "wav_sha256": file_sha256(wav_path), "pcm16le_sha256": sha256(pcm)}
        local_refs, source_maps = [], []
        for clip, start in zip(candidate["clips"], mapping["positions"]):
            row, text = references[clip["natural_source_key"]]
            role = clip["logical_role"]
            target_language = "zh" if candidate["kind"] == "T1" and role == "B" else "en"
            spans = reference_spans(row["transcription"])
            local_refs.append({"natural_source_key": clip["natural_source_key"], "annotation_L": clip["annotation_L"],
                               "original_person": clip["original_speaker_id"], "role": role,
                               "source_csv_row_1based_including_header": int(clip["upstream_id"]) + 2,
                               "source_csv_row": row, "released_human_transcript": text.decode("utf-8"),
                               "reference_utf8_sha256": sha256(text), "source_language_label": row["language"],
                               "translation_target_source_language": target_language,
                               "translation_targets": [s for s in spans if s["language"] == target_language],
                               "target_language_context_not_scored_as_translation": [s for s in spans if s["language"] != target_language],
                               "automatic_review": curation["episodes"][identity]["source_review"],
                               "reference_notes": curation["reference_notes"].get(str(clip["annotation_L"]), []),
                               "source_only_asr_observation": curation["source_observations"][str(clip["annotation_L"])]})
            source_maps.append({"natural_source_key": clip["natural_source_key"], "annotation_L": clip["annotation_L"],
                                "role": role, "original_person": clip["original_speaker_id"],
                                "source_samples": [0, clip["source_frames"]], "playback_samples": [start, start + clip["source_frames"]],
                                "pcm16le_sha256": clip["decoded_pcm16le_sha256"], "sample_rate_ratio": [1, 1],
                                "gain_linear": 1, "within_clip_pcm_and_gaps_unchanged": True})
        checkpoints = checkpoints_by_id[identity]
        reference = {"id": identity, "source_case_id": candidate["source_case_id"], "roles": candidate["roles"],
                     "dependency_group_id": candidate["dependency_group_id"], "directions": candidate["directions"],
                     "story": curation["episodes"][identity]["story"], "references": local_refs,
                     "semantic_checkpoints": checkpoints, "source_to_playback": source_maps,
                     "timeline": mapping, "review_level": record["review_level"],
                     "reference_policy": curation["reference_policy"],
                     "unscored_context_constraints": [
                         {**constraint, "required_in_output": False, "translation_credit": False,
                          "available_after_playback_sample": max(
                              m["playback_samples"][1] for m in source_maps
                              if m["annotation_L"] in constraint["evidence_Ls"])}
                         for constraint in curation["episodes"][identity]["unscored_context_constraints"]],
                     "context_rule": "Only source input through the observation point; never use future answers retrospectively."}
        save_json(output / "references" / (identity + ".json"), reference)
        episodes.append({"id": identity, "kind": candidate["kind"], "project_split": candidate["project_split"],
                         "source_case_id": candidate["source_case_id"], "roles": candidate["roles"],
                         "reserved_original_speakers": candidate["reserved_original_speakers"],
                         "dependency_group_id": candidate["dependency_group_id"], "directions": candidate["directions"],
                         "assets": assets, "reference_path": f"references/{identity}.json",
                         "reference_sha256": file_sha256(output / "references" / (identity + ".json")),
                         "source_to_playback": source_maps, "timeline": mapping,
                         "status": "materialized_reconstruction_v1_pending_director_acceptance"})
    report = {"status": "source_materialized_reconstruction_v1_pending_acceptance", "dataset": record["dataset"],
              "revision": record["revision"], "condition": "ascend-reconstruction-v1",
              "schema": "r2_source_preparation_v2", "not_executable_benchmark_plan": True,
              "downstream_plan_boundary": {
                  "ordinary_runtime_role": "One mixed WAV becomes ordinary role A, not two runtime roles",
                  "T1_runtime_roles": "Equal-length A/B WAVs retain their declared fixed directions",
                  "speech_intervals": "Not fabricated here: exact whole-source clip maps are not certified speech_intervals",
                  "remaining_runtime_ownership": "R6 binds devices, profiles, calibration and explicit speech intervals; source acceptance does not wait on app/provider access"},
              "catalogue_sha256": file_sha256(catalogue), "curation_sha256": sha256(curation_bytes),
              "archive": record["source_archive"], "research_evidence_sha256": sha256(evidence_bytes),
              "grouping": grouping, "selected_source_clips": len(clips), "candidates": episodes,
              "cell_accounting": record["cell_accounting"], "review_level": record["review_level"],
              "pre_result_selection": record["pre_result_selection"],
              "t1_parent_ids_pending_acceptance": [e["id"] for e in episodes if e["kind"] == "T1"],
              "checks": {"archive_metadata_source_and_reference_hashes": "passed",
                         "whole_clip_pcm_and_exact_integer_positions": "passed",
                         "known_connected_main_development_groups_disjoint": "passed",
                         "source_interval_reuse": "none", "provider_or_app_calls": "none",
                         "historical_clock_or_missing_audio_recovered": False}}
    parents = [{"id": e["id"], "source_case_id": e["source_case_id"],
                "project_split": e["project_split"], "roles": e["roles"],
                "reserved_original_speakers": e["reserved_original_speakers"],
                "dependency_group_id": e["dependency_group_id"], "directions": e["directions"],
                "story": curation["episodes"][e["id"]]["story"],
                "reference_path": e["reference_path"], "reference_sha256": e["reference_sha256"],
                "assets": e["assets"], "source_to_playback": e["source_to_playback"],
                "timeline": e["timeline"]} for e in episodes if e["kind"] == "T1"]
    save_json(output / "t1-parent-manifest.json",
              {"condition": "ascend-reconstruction-v1", "status": "pending_director_source_acceptance",
               "root_dataset": record["dataset"], "root_revision": record["revision"],
               "source_license": record["license"], "catalogue_sha256": file_sha256(catalogue),
               "curation_sha256": sha256(curation_bytes), "parents": parents,
               "R3_contract": "After source acceptance, preserve this exact story, original-person roles, source_case_id and reference identity. JA/KO synthesis gets its own observed timeline; this playback clock is approximate, not historical.",
               "development_additional_take_parent_ids": record["pre_result_selection"]["development_t1_additional_take_parent_ids"]})
    report["t1_parent_manifest"] = {"path": "t1-parent-manifest.json",
                                     "sha256": file_sha256(output / "t1-parent-manifest.json")}
    save_json(output / "preparation-report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", default="corpus/r2/ascend.json")
    parser.add_argument("--cache", required=True)
    parser.add_argument("--evidence", default=".data/r2/ascend/research-machine-evidence.json")
    parser.add_argument("--findings", default=".data/r2/ascend/research-findings.json")
    parser.add_argument("--curation", help="Override the pinned task-local review/checkpoint record path")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if __package__ in (None, ""):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from bench.paths import DataPathError, DataPaths
    paths = DataPaths()
    try:
        args.output = paths.output(args.output)
        for name in ("catalogue", "cache", "evidence", "findings"):
            setattr(args, name, paths.input(getattr(args, name)))
        curation = args.curation
        if curation is None:
            curation = json.loads(args.catalogue.read_text(encoding="utf-8"))["curation"]["path"]
        args.curation = paths.input(curation)
    except DataPathError as error:
        parser.error(str(error))
    report = materialize(args.catalogue, args.cache, args.evidence, args.findings, args.output, args.curation)
    print(json.dumps({"status": report["status"], "episodes": len(report["candidates"]),
                      "source_clips": report["selected_source_clips"],
                      "report": str(Path(args.output) / "preparation-report.json")}))


if __name__ == "__main__":
    main()
