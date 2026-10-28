"""Prepare pinned R2 IngCrowd source inputs, not an executable benchmark plan.

Only pinned local source bytes are used. References retain the original human
EAF, with separately recorded automatic source-review decisions. ASR is a
discrepancy screen, not a replacement transcript or phonetic certification.
Corpus audio/EAF/derived references stay outside the MIT code tree in .data.
"""
from __future__ import annotations

import argparse
from array import array
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import re
import sys
import time
import wave
import xml.etree.ElementTree as ET


KINDS = {"P1": 3, "P2": 9, "P3": 6}


def sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def checked_bytes(path, expected):
    payload = Path(path).read_bytes()
    if sha256(payload) != expected:
        raise ValueError(f"Pinned input checksum mismatch: {Path(path).name}")
    return payload


def annotations(payload):
    root = ET.fromstring(payload)
    times = {slot.attrib["TIME_SLOT_ID"]: int(slot.attrib["TIME_VALUE"])
             for slot in root.findall("./TIME_ORDER/TIME_SLOT")}
    result = []
    for tier in root.findall("TIER"):
        for row in tier.findall("./ANNOTATION/ALIGNABLE_ANNOTATION"):
            start, end = (times[row.attrib[key]] for key in ("TIME_SLOT_REF1", "TIME_SLOT_REF2"))
            if not 0 <= start < end:
                raise ValueError("Invalid original EAF annotation interval")
            result.append({"id": row.attrib["ANNOTATION_ID"], "speaker": tier.attrib["TIER_ID"],
                           "start_ms": start, "end_ms": end,
                           "text": row.findtext("ANNOTATION_VALUE") or ""})
    if len({row["id"] for row in result}) != len(result):
        raise ValueError("EAF annotation IDs must be unique within the dialogue")
    return sorted(result, key=lambda row: (row["start_ms"], row["end_ms"], row["id"]))


def check_selection(record):
    candidates = record["candidates"]
    if len({candidate["id"] for candidate in candidates}) != len(candidates):
        raise ValueError("Duplicate candidate ID")
    for kind, required in KINDS.items():
        if sum(c["kind"] == kind and c["project_split"] == "main" for c in candidates) != required:
            raise ValueError(f"Preserve the fixed {kind} main count")
        if sum(c["kind"] == kind and c["project_split"] == "development" for c in candidates) < 1:
            raise ValueError(f"A development {kind} candidate is required")
    if any(c["kind"] not in KINDS or c["project_split"] not in ("main", "development") for c in candidates):
        raise ValueError("Unexpected case type or split")
    groups = {split: {c["dialogue"] for c in candidates if c["project_split"] == split}
              for split in ("main", "development")}
    if groups["main"] & groups["development"]:
        raise ValueError("Whole original dialogue crosses development/main")
    # Only established equivalences belong here; absent keys never prove independence.
    for component in record["grouping"]["known_connected_dialogue_components"]:
        if groups["main"].intersection(component) and groups["development"].intersection(component):
            raise ValueError("Known connected participant component crosses development/main")
    for dialogue in groups["main"] | groups["development"]:
        intervals = sorted(c["source_samples"] for c in candidates if c["dialogue"] == dialogue)
        if any(a[1] > b[0] for a, b in zip(intervals, intervals[1:])):
            raise ValueError("Selected source intervals overlap")
    return {"main_dialogues": sorted(groups["main"]), "development_dialogues": sorted(groups["development"]),
            "whole_dialogue_intersection": [], "source_interval_overlap_pairs": [],
            "unknown_recurring_speakers_independent": False}


def signal(pcm):
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        raise ValueError("Empty decoded PCM")
    def rms_db(values):
        rms = math.sqrt(sum(value * value for value in values) / len(values)) / 32768
        return 20 * math.log10(rms) if rms else None
    return {"frames": len(samples), "peak_abs_pcm16": max(abs(x) for x in samples),
            "rms_dbfs": rms_db(samples), "first_50ms_rms_dbfs": rms_db(samples[:800]),
            "last_50ms_rms_dbfs": rms_db(samples[-800:]),
            "full_scale_samples": sum(x in (-32768, 32767) for x in samples),
            "claim": "Signal statistics only; not intelligibility or phonetic endpoint certification"}


def save_wave(path, pcm):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(pcm)


def reference(candidate, rows):
    start, end = candidate["source_samples"]
    selected = [row for row in rows if row["start_ms"] * 16 < end and row["end_ms"] * 16 > start]
    if not selected or any(row["start_ms"] * 16 < start or row["end_ms"] * 16 > end for row in selected):
        raise ValueError("A crop cuts an original EAF annotation")
    if [row["id"] for row in selected] != candidate["annotation_ids"]:
        raise ValueError("Candidate annotations changed, including another audible speaker")
    mapped = [{**row, "source_samples": [row["start_ms"] * 16, row["end_ms"] * 16],
               "playback_samples": [row["start_ms"] * 16 - start, row["end_ms"] * 16 - start],
               "logical_role": "A", "language": "ja", "scope": "translation_and_context",
               "uncertain_marker_present": "<?>" in row["text"]} for row in selected]
    by_id = {row["id"]: row for row in mapped}
    review = candidate.get("source_review", {})
    notes = review.get("annotation_notes", {})
    if set(notes) - set(by_id):
        raise ValueError("Source review notes must bind selected original annotations")
    for identity, note in notes.items():
        uncertainty = note.get("uncertainty_scope")
        if uncertainty is not None:
            if uncertainty != "original_marker_only" or "<?>" not in by_id[identity]["text"]:
                raise ValueError("Only an original uncertainty marker may lack a lexical target")
        by_id[identity]["source_review_note"] = note
    accepted = review.get("status") == "accepted"
    checkpoints = []
    for index, checkpoint in enumerate(candidate["checkpoints"], 1):
        evidence = [by_id[identity] for identity in checkpoint["evidence_annotation_ids"]]
        utterance_end = max(row["playback_samples"][1] for row in evidence)
        checkpoints.append({**checkpoint, "id": f"{candidate['id']}-cp{index:02}",
                            "original_quotes": [{"annotation_id": row["id"], "text": row["text"]} for row in evidence],
                            "eaf_evidence_end_playback_sample": utterance_end,
                            "eaf_evidence_end_seconds": utterance_end / 16000,
                            "observation_offsets_seconds": [0, 2, 5, 10, 15],
                            "certified_acoustic_end_sample": None,
                            "timing_status": "fixed source-reviewed EAF evidence end; approximate acoustic endpoint, not phonetic calibration"
                            if accepted else "provisional EAF utterance end; acoustic review pending"})
    bound = {"id": candidate["id"], "status": "source_accepted" if accepted else "candidate_not_frozen",
             "reference_origin": "original_human_eaf",
             "scope": "All annotated lexical Japanese from both mixed-input speakers is translation target and context; laughter is nonlexical. Original uncertainty markers do not license invented words or exemption of surrounding lexical content.",
             "speaker_labels": "EAF-local labels only; no cross-dialogue identity or globally verified individual-track mapping",
             "annotations": mapped, "checkpoints": checkpoints,
             "uncertain_content_policy": "Preserve literal <?> and <la>; only the original unknown fragment lacks a required lexical output, never the surrounding annotation or a stated number/condition",
             "review_level": "original human EAF plus recorded source semantics, waveform and independent ASR screening; no actual listening or exact phonetic certification"}
    if review:
        bound["source_review"] = review
    return bound


def materialize(catalogue, retained, output):
    catalogue, retained, output = map(Path, (catalogue, retained, output))
    record = json.loads(catalogue.read_text(encoding="utf-8"))
    grouping = check_selection(record)
    accepted = record.get("source_acceptance", {}).get("status") == "accepted"
    if accepted and any(c.get("source_review", {}).get("status") != "accepted" for c in record["candidates"]):
        raise ValueError("Source acceptance requires a recorded decision for every selected case")
    if output.exists():
        raise ValueError("Use a fresh output directory; do not overwrite evidence")
    checked_bytes(retained / "README.md", record["source"]["card_sha256"])
    decoded, source_rows = {}, {}
    for source in record["sources"]:
        dialogue = source["dialogue"]
        eaf = checked_bytes(retained / source["eaf_path"], source["eaf_sha256"])
        source_rows[dialogue] = annotations(eaf)
        wav_path = retained / source["wav_path"]
        checked_bytes(wav_path, source["wav_sha256"])
        with wave.open(str(wav_path), "rb") as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1, 2, 16000, "NONE"):
                raise ValueError("Expected original mono 16 kHz PCM16 WAV")
            pcm = wav.readframes(wav.getnframes())
            if len(pcm) != wav.getnframes() * 2 or wav.getnframes() != source["source_frames"]:
                raise ValueError("Original decoded sample count changed")
        if sha256(pcm) != source["decoded_s16le_sha256"]:
            raise ValueError("Original decoded PCM changed")
        decoded[dialogue] = pcm
    prepared = []
    for candidate in record["candidates"]:
        start, end = candidate["source_samples"]
        if not 0 <= start < end <= len(decoded[candidate["dialogue"]]) // 2:
            raise ValueError("Crop outside original source")
        pcm = decoded[candidate["dialogue"]][start * 2:end * 2]
        if sha256(pcm) != candidate["playback_s16le_sha256"]:
            raise ValueError("Selected playback PCM changed")
        bound = reference(candidate, source_rows[candidate["dialogue"]])
        reference_bytes = (json.dumps(bound, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if sha256(reference_bytes) != candidate["reference_json_sha256"]:
            raise ValueError("Selected reference/checkpoints changed")
        prepared.append((candidate, pcm, bound, reference_bytes))
    output.mkdir(parents=True)
    (output / "catalogue.json").write_bytes(catalogue.read_bytes())
    (output / "playback").mkdir()
    (output / "references").mkdir()
    episodes = []
    for candidate, pcm, bound, reference_bytes in prepared:
        identity = candidate["id"]
        wav_path = output / "playback" / (identity + ".wav")
        save_wave(wav_path, pcm)
        if sha256(wav_path.read_bytes()) != candidate["playback_wav_sha256"]:
            raise ValueError("Materialized WAV differs from pinned candidate")
        with wave.open(str(wav_path), "rb") as check:
            if check.readframes(check.getnframes()) != pcm:
                raise ValueError("WAV roundtrip changed selected original PCM")
        reference_path = output / "references" / (identity + ".json")
        reference_path.write_bytes(reference_bytes)
        mapped = bound["annotations"]
        gaps = []
        cursor = 0
        for row in mapped:
            left, right = row["playback_samples"]
            if left > cursor:
                gaps.append([cursor, left])
            cursor = max(cursor, right)
        if cursor < len(pcm) // 2:
            gaps.append([cursor, len(pcm) // 2])
        # Gaps are unannotated original signal, not synthesized/digital silence.
        episodes.append({"id": identity, "kind": candidate["kind"], "project_split": candidate["project_split"],
                         "dialogue": candidate["dialogue"], "status": "source_accepted" if accepted else "materialized_not_frozen",
                         "input_channel": "peer", "logical_role": "A", "speakers": ["speaker_1", "speaker_2"],
                         "source_language": "ja", "target_language": "ko", "source_track": "mixed",
                         "playback_path": f"playback/{identity}.wav", "reference_path": f"references/{identity}.json",
                         "playback_wav_sha256": sha256(wav_path.read_bytes()), "playback_s16le_sha256": sha256(pcm),
                         "reference_json_sha256": sha256(reference_bytes), "frames": len(pcm) // 2,
                         "mapping": {"source_samples": candidate["source_samples"], "playback_samples": [0, len(pcm) // 2],
                                     "source_sample_rate": 16000, "playback_sample_rate": 16000, "sample_rate_ratio": [1, 1],
                                     "gain_linear": 1, "resampling": False, "added_silence_samples": 0,
                                     "time_compression": False, "unannotated_original_signal_samples": gaps,
                                     "gap_claim": "All original samples, gaps and overlaps retained exactly; no splice or role masking"},
                         "signal": signal(pcm), "annotation_count": len(mapped),
                         "uncertain_annotations": [r["id"] for r in mapped if r["uncertain_marker_present"]],
                         "checkpoint_count": len(bound["checkpoints"]),
                         "source_review": candidate.get("source_review"),
                         "certified_acoustic_boundaries": False})
    report = {"schema_version": 1, "status": "source_accepted" if accepted else "materialized_not_frozen", "offline": True,
              "catalogue_sha256": sha256(catalogue.read_bytes()), "grouping": grouping,
              "episodes": episodes, "counts": record["counts"], "rights": record["rights"],
              "review_level": "original EAF semantic curation plus decoded mixed-WAV signal and exact-sample binding; not listening",
              "source_acceptance": record.get("source_acceptance"),
              "freeze_gates": record["freeze_gates"]}
    save_json(output / "materialization.json", report)
    return report


def normalized(text):
    # Diagnostic only: do not rewrite the human reference or conflate script variants.
    return re.sub(r"[\W_]", "", re.sub(r"<[^>]*>", "", text), flags=re.UNICODE)


def edit_distance(left, right):
    previous = list(range(len(right) + 1))
    for index, a in enumerate(left, 1):
        current = [index]
        for column, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[column] + 1, previous[column - 1] + (a != b)))
        previous = current
    return previous[-1]


def review_windows(frames):
    """Twenty-second views, two-second overlap; never alter the playback WAV."""
    windows = []
    for start in range(0, frames, 18 * 16000):
        end = min(start + 20 * 16000, frames)
        windows.append((start, end))
        if end == frames:
            break
    return windows


def deduplicate_window_tokens(windows):
    """Diagnostic ownership at overlap midpoints, using approximate ASR times."""
    retained = []
    for index, window in enumerate(windows):
        start, end = window["playback_samples"]
        lower = (windows[index - 1]["playback_samples"][1] + start) // 2 if index else start
        upper = (end + windows[index + 1]["playback_samples"][0]) // 2 if index + 1 < len(windows) else end
        if len(window["tokens"]) != len(window["timestamps"]):
            raise ValueError("Recognizer tokens and timestamps have different lengths")
        for token, timestamp in zip(window["tokens"], window["timestamps"]):
            approximate_sample = start + round(timestamp * 16000)
            if lower <= approximate_sample < upper:
                retained.append({"token": token, "approximate_playback_sample": approximate_sample,
                                 "window_index": index})
    return retained


def review_asr(prepared, model, destination):
    # Imported only in the explicitly requested offline review environment.
    import numpy as np
    import sherpa_onnx

    prepared, model, destination = map(Path, (prepared, model, destination))
    if destination.exists():
        raise ValueError("Do not overwrite independent ASR evidence")
    files = {key: model / filename for key, filename in {
        "encoder": "encoder-epoch-99-avg-1.int8.onnx", "decoder": "decoder-epoch-99-avg-1.onnx",
        "joiner": "joiner-epoch-99-avg-1.int8.onnx", "tokens": "tokens.txt"}.items()}
    recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
        **{key: str(path) for key, path in files.items()}, num_threads=2,
        sample_rate=16000, feature_dim=80, decoding_method="greedy_search", provider="cpu")
    report = json.loads((prepared / "materialization.json").read_text(encoding="utf-8"))
    results = []
    started = time.time()
    for episode in report["episodes"]:
        path = prepared / episode["playback_path"]
        checked_bytes(path, episode["playback_wav_sha256"])
        reference_payload = checked_bytes(prepared / episode["reference_path"], episode["reference_json_sha256"])
        bound = json.loads(reference_payload)
        with wave.open(str(path), "rb") as wav:
            samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32) / 32768
        windows = []
        for start, end in review_windows(len(samples)):
            stream = recognizer.create_stream()
            stream.accept_waveform(16000, samples[start:end])
            before = time.time()
            recognizer.decode_stream(stream)
            source_start = episode["mapping"]["source_samples"][0]
            intersecting = [row for row in bound["annotations"]
                            if row["playback_samples"][0] < end and row["playback_samples"][1] > start]
            windows.append({"playback_samples": [start, end],
                            "source_samples": [source_start + start, source_start + end],
                            "recognized_text": stream.result.text, "tokens": stream.result.tokens,
                            "timestamps": stream.result.timestamps,
                            "eaf_annotation_ids_intersecting": [row["id"] for row in intersecting],
                            "eaf_annotation_ids_partial_in_view": [row["id"] for row in intersecting
                                                                  if row["playback_samples"][0] < start or row["playback_samples"][1] > end],
                            "decode_started_unix": before, "decode_ended_unix": time.time()})
        retained_tokens = deduplicate_window_tokens(windows)
        text = "".join(row["token"] for row in retained_tokens).replace("▁", " ")
        human = "".join(row["text"] for row in bound["annotations"])
        truth, recognized = normalized(human), normalized(text)
        distance = edit_distance(truth, recognized)
        result = {"id": episode["id"], "wav_sha256": episode["playback_wav_sha256"],
                  "reference_json_sha256": episode["reference_json_sha256"], "recognized_text": text,
                  "windows": windows, "diagnostic_deduplicated_tokens": retained_tokens,
                  "reference_characters": len(truth), "edit_distance": distance,
                  "diagnostic_cer": distance / len(truth) if truth else None,
                  "interpretation": "Independent ASR discrepancy screen, not transcript/speech/boundary truth; overlaps and Japanese orthography affect CER"}
        results.append(result)
        print(json.dumps({"id": result["id"], "windows": len(windows),
                          "diagnostic_cer": result["diagnostic_cer"]}), flush=True)
    evidence = {"status": "independent_asr_screening_only", "engine": "sherpa_onnx",
                "engine_version": importlib.metadata.version("sherpa-onnx"), "provider": "cpu", "num_threads": 2,
                "model": "ReazonSpeech-k2-v2", "model_revision": "291488c8151be24d7da4bf7af26e533fad96e407",
                "model_file_sha256": {key: sha256(path.read_bytes()) for key, path in files.items()},
                "runtime_contract": "Retained model README supports approximately 30-second clips; each independent view is at most 20 seconds.",
                "window_seconds": 20, "overlap_seconds": 2, "playback_modified": False,
                "deduplication": "Comparison only: approximate ASR-token times assigned at overlap midpoints. Raw overlapping views and offsets retained; no transcript/reference rewriting or certified timing claim.",
                "started_unix": started, "ended_unix": time.time(), "results": results,
                "no_human_listening": True, "reference_replaced_by_asr": False}
    save_json(destination, evidence)
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="Materialize pinned candidates, without provider calls")
    prepare.add_argument("--catalogue", type=Path, default=Path("corpus/r2/ingcrowd.json"))
    prepare.add_argument("--retained", type=Path, required=True)
    prepare.add_argument("--output", type=Path, default=Path(".data/r2/ingcrowd/prepared-v1"))
    review = subparsers.add_parser("asr", help="Independent offline Reazon discrepancy screening")
    review.add_argument("--prepared", type=Path, required=True)
    review.add_argument("--model", type=Path, required=True)
    review.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    if __package__ in (None, ""):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from bench.paths import DataPathError, DataPaths
    paths = DataPaths()
    try:
        if args.command == "prepare":
            args.output = paths.output(args.output)
            args.catalogue = paths.input(args.catalogue)
            args.retained = paths.input(args.retained)
        else:
            args.report = paths.output(args.report)
            args.prepared = paths.input(args.prepared)
            args.model = paths.input(args.model)
    except DataPathError as error:
        parser.error(str(error))
    if args.command == "prepare":
        report = materialize(args.catalogue, args.retained, args.output)
        print(json.dumps({"status": report["status"], "episodes": len(report["episodes"]), "output": str(args.output)}))
    else:
        report = review_asr(args.prepared, args.model, args.report)
        print(json.dumps({"status": report["status"], "episodes": len(report["results"])}))


if __name__ == "__main__":
    main()
