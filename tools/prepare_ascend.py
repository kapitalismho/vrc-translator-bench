"""Prepare the fixed R2 ASCEND source candidates from retained local bytes.

Offline only: no models, providers, downloads, app imports or audio devices.
References come from pinned split-local CSV rows, never embedded transcripts.
This records intact files and unresolved gates, not frozen benchmark episodes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import wave


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
    main = {speaker for group in reservations["main_reserved_original_groups"] for speaker in group}
    development = {speaker for group in reservations["development_reserved_original_groups"] for speaker in group}
    if main & development:
        raise ValueError("Main/development connected original-speaker reservations overlap")
    candidates = record["candidates"]
    expected = {("train", "01254", "main"), ("train", "00412", "main"),
                ("train", "07714", "main"), ("test", "00002", "development")}
    actual = {(c["upstream_split"], c["upstream_id"], c["project_split"]) for c in candidates}
    if len(candidates) != 4 or actual != expected:
        raise ValueError("Preserve the four preselected P1 split-local identities")
    for candidate in candidates:
        selected = set(candidate["reserved_original_speakers"])
        group_key = "main_reserved_original_groups" if candidate["project_split"] == "main" else "development_reserved_original_groups"
        allowed_groups = [set(group) for group in reservations[group_key]]
        if candidate["original_speaker_id"] not in selected or selected not in allowed_groups:
            raise ValueError("Candidate does not preserve its connected-speaker reservation")
    if len({c["archive_member"] for c in candidates}) != 4:
        raise ValueError("Selected whole source intervals must not duplicate")
    return {"main_reserved_original_speakers": sorted(main),
            "development_reserved_original_speakers": sorted(development),
            "known_intersection": [], "unknown_participation_certified_absent": False}


def reference_row(tables, candidate):
    rows = tables[candidate["upstream_split"]]
    index = int(candidate["upstream_id"])
    if candidate["upstream_id"] != f"{index:05}" or not 0 <= index < len(rows):
        raise ValueError("Invalid split-local five-digit source ID")
    row = rows[index]
    if row["file_name"] != candidate["archive_member"]:
        raise ValueError("CSV row identity disagrees with selected archive member")
    if int(row["original_speaker_id"]) != candidate["original_speaker_id"]:
        raise ValueError("Original speaker identity disagrees with CSV")
    text = row["transcription"].encode("utf-8")
    if sha256(text) != candidate["reference_utf8_sha256"]:
        raise ValueError("Released reference text checksum mismatch")
    return row, text


def decode_wave(payload, frames, expected_pcm):
    with wave.open(io.BytesIO(payload), "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) != (1, 2, 16000, "NONE"):
            raise ValueError("Source must remain mono 16 kHz PCM16")
        if source.getnframes() != frames:
            raise ValueError("Actual source frame count differs from pinned evidence")
        pcm = source.readframes(frames)
    if len(pcm) != frames * 2 or sha256(pcm) != expected_pcm:
        raise ValueError("Decoded PCM differs from pinned evidence")
    return pcm


def materialize(catalogue, cache, evidence_path, findings_path, output):
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
    if record["split_reservations"] != evidence["p1_ancestry"]:
        raise ValueError("Preserve the pinned researcher's complete connected-speaker reservations")
    # Hash the complete retained archive without allocating a second archive buffer.
    archive = cache / "waves.tar.bz2"
    if archive.stat().st_size != record["source_archive"]["bytes"] or file_sha256(archive) != record["source_archive"]["sha256"]:
        raise ValueError("Retained original archive checksum mismatch")
    metadata = {name: checked_bytes(cache / name, spec["sha256"])
                for name, spec in record["source_metadata"].items()}
    tables = {name.removesuffix("_metadata.csv"): list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))
              for name, payload in metadata.items()}
    ancillary = {name: checked_bytes(cache / name, digest)
                 for name, digest in record["ancillary_sha256"].items()}
    inputs = []
    for candidate in record["candidates"] + record["unclassified_candidates"]:
        row, text = reference_row(tables, candidate)
        payload = checked_bytes(cache / candidate["archive_member"], candidate["source_wav_sha256"])
        pcm = decode_wave(payload, candidate["source_frames"], candidate["decoded_pcm16le_sha256"])
        inputs.append((candidate, row, text, payload, pcm))
    representatives = evidence["representatives"]
    if len(representatives) != 247 or len({r["archive_member"] for r in representatives}) != 247:
        raise ValueError("Preserve all 247 distinct retained research representatives")
    # Validate every retained representative before creating any output.
    for representative in representatives:
        payload = checked_bytes(cache / representative["archive_member"], representative["wav_sha256"])
        decode_wave(payload, representative["frames"], representative["decoded_pcm16le_sha256"])
    output.mkdir(parents=True)
    for folder in ("audio", "decoded", "references", "provenance", "research-waves"):
        (output / folder).mkdir()
    (output / "provenance" / "research-machine-evidence.json").write_bytes(evidence_bytes)
    (output / "provenance" / "research-findings.json").write_bytes(findings_bytes)
    shutil.copyfile(catalogue, output / "provenance" / "catalogue.json")
    for name, payload in {**metadata, **ancillary}.items():
        (output / "provenance" / name).write_bytes(payload)
    for representative in representatives:
        shutil.copyfile(cache / representative["archive_member"], output / "research-waves" / Path(representative["archive_member"]).name)
    episodes = []
    for candidate, row, text, payload, pcm in inputs:
        identity = candidate["id"]
        (output / "audio" / (identity + ".wav")).write_bytes(payload)
        (output / "decoded" / (identity + ".s16le")).write_bytes(pcm)
        (output / "references" / (identity + ".txt")).write_bytes(text)
        p1 = candidate.get("kind") == "P1"
        local_reference = {"source_csv_row_1based_including_header": int(candidate["upstream_id"]) + 2,
                           "source_csv_row": row, "released_human_transcript": row["transcription"],
                           "reference_utf8_sha256": sha256(text),
                           "audible_transcript_certified": False}
        if p1:
            local_reference.update({"translation_targets": [{"language": "en", "text": row["transcription"],
                                                              "scope": "entire released transcript"}],
                                    "chinese_context_from_released_transcript": [],
                                    "other_audible_content_status": "not certified absent",
                                    "semantic_checkpoint_candidates": [candidate["checkpoint_candidate"]]})
        save_json(output / "references" / (identity + ".json"), local_reference)
        episodes.append({**candidate, "status": "materialized_not_frozen" if p1 else "unclassified_no_count_credit",
                         "audio_path": f"audio/{identity}.wav", "decoded_path": f"decoded/{identity}.s16le",
                         "reference_path": f"references/{identity}.json",
                         "playback_wav_sha256": sha256(payload), "playback_pcm16le_sha256": sha256(pcm),
                         "mapping": {"source_samples": [0, candidate["source_frames"]],
                                     "playback_samples": [0, candidate["source_frames"]],
                                     "source_sample_rate": 16000, "playback_sample_rate": 16000,
                                     "sample_rate_ratio": [1, 1], "gain_linear": 1,
                                     "added_silence_samples": 0, "time_compression": False,
                                     "conversion": "none; original WAV copied byte-for-byte"},
                         "speech_intervals": None, "certified_speech_end_sample": None,
                         "other_speaker_leakage_review": "pending acoustic review"})
    report = {"status": "source_materialized_production_freeze_blocked", "dataset": record["dataset"],
              "revision": record["revision"], "archive": {"retained_path": str(archive.resolve()),
              **record["source_archive"], "newly_verified_cached_archive_hash": True},
              "research_evidence_sha256": sha256(evidence_bytes), "grouping": grouping,
              "preserved_research_representatives": 247, "candidates": episodes,
              "cell_accounting": record["cell_accounting"], "blocker_evidence": record["blocker_evidence"],
              "review_level": record["review_level"], "freeze_gates": record["freeze_gates"],
              "checks": {"all_cached_representative_wav_and_pcm_hashes": "passed",
                         "selected_split_local_csv_identity_and_reference_hashes": "passed",
                         "original_archive_hash_and_metadata_hashes": "passed",
                         "known_connected_speaker_reservations_disjoint": "passed",
                         "source_to_playback_sample_mapping": "identity; exact native clock",
                         "listening": "not performed", "independent_ASR": "not performed by this tool",
                         "speech_endpoint_alignment": "not performed", "provider_or_app_calls": "none"}}
    save_json(output / "preparation-report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", default="corpus/r2/ascend.json")
    parser.add_argument("--cache", required=True)
    parser.add_argument("--evidence", default=".data/r2/ascend/research-machine-evidence.json")
    parser.add_argument("--findings", default=".data/r2/ascend/research-findings.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = materialize(args.catalogue, args.cache, args.evidence, args.findings, args.output)
    print(json.dumps({"status": report["status"], "selected_files": len(report["candidates"]),
                      "preserved_research_representatives": report["preserved_research_representatives"],
                      "report": str(Path(args.output) / "preparation-report.json")}))


if __name__ == "__main__":
    main()
