"""Materialize the preselected R2 FLEURS/C1 candidates from pinned local bytes.

Offline only: no providers, app imports, discovery, downloads or audio devices.
The output is deliberately not an executable/frozen benchmark plan. See the
catalogue's freeze gates; file boundaries are not certified speech boundaries.
"""
from __future__ import annotations

import argparse
from array import array
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import wave


def sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def checked_bytes(path, expected):
    payload = Path(path).read_bytes()
    if sha256(payload) != expected:
        raise ValueError(f"Pinned source checksum mismatch: {Path(path).name}")
    return payload


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_wave(path, pcm, sample_rate=48000):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm)


def reference_row(payload, candidate):
    matches = []
    for number, line in enumerate(payload.splitlines(), 1):
        fields = line.decode("utf-8").split("\t")
        if len(fields) != 7:
            raise ValueError("FLEURS TSV must have seven columns and no header")
        if fields[1] == candidate["filename"]:
            matches.append((number, line, fields))
    if len(matches) != 1:
        raise ValueError("Selected recording needs exactly one TSV row")
    number, line, fields = matches[0]
    if int(fields[0]) != candidate["sentence_id"] or int(fields[5]) != candidate["source_frames"]:
        raise ValueError("Selected TSV sentence ID/sample count disagrees with catalogue")
    text = fields[2].encode("utf-8")
    if sha256(text) != candidate["raw_text_utf8_sha256"]:
        raise ValueError("Selected raw text checksum disagrees with catalogue")
    return {"row_1based": number, "row_sha256": sha256(line), "raw_text": fields[2],
            "normalized_text": fields[3], "gender": fields[6], "text_utf8": text}


def check_groups(candidates, tables):
    groups = {usage: {c["sentence_id"] for c in candidates if c["project_split"] == usage}
              for usage in ("main", "development")}
    if groups["main"] & groups["development"]:
        raise ValueError("Development/main sentence ancestry overlaps across languages")
    if groups != {"main": {1980, 1914, 1771}, "development": {151}}:
        raise ValueError("Preserve the preselected original sentence groups")
    for language in ("en_us", "ja_jp"):
        chosen = [c for c in candidates if c["language"] == language]
        if len(chosen) != 4 or {c["sentence_id"] for c in chosen} != groups["main"] | groups["development"]:
            raise ValueError("Each input language needs three main and one development recording")
        ids = {split: {int(line.split(b"\t", 1)[0]) for line in tables[f"{language}-{split}"].splitlines()}
               for split in ("train", "dev", "test")}
        if any(ids[a] & ids[b] for a, b in (("train", "dev"), ("train", "test"), ("dev", "test"))):
            raise ValueError("Upstream split sentence IDs overlap")
    return {"main_sentence_ids": sorted(groups["main"]), "development_sentence_ids": sorted(groups["development"]),
            "main_original_text_groups": 3, "main_recordings": 6, "development_recordings": 2,
            "main_development_sentence_intersection": [], "speaker_identity": "unavailable; not independently certified"}


def decode(ffmpeg, path, sample_rate, codec, raw_format):
    command = [str(ffmpeg), "-v", "error", "-i", str(path), "-f", raw_format,
               "-acodec", codec, "-ac", "1", "-ar", str(sample_rate), "pipe:1"]
    result = subprocess.run(command, capture_output=True, check=True)
    return result.stdout, command


def signal_summary(pcm):
    samples = array("f")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples or not all(math.isfinite(x) for x in samples):
        raise ValueError("Decoded source must contain finite float32 samples")
    rms = math.sqrt(sum(x * x for x in samples) / len(samples))
    return {"frames": len(samples), "peak_abs": max(abs(x) for x in samples), "rms": rms,
            "rms_dbfs": 20 * math.log10(rms) if rms else None,
            "full_scale_samples": sum(abs(x) >= 1 for x in samples),
            "first_100ms_rms": math.sqrt(sum(x*x for x in samples[:1600]) / min(1600, len(samples))),
            "last_100ms_rms": math.sqrt(sum(x*x for x in samples[-1600:]) / min(1600, len(samples))),
            "boundary_claim": "Signal statistics only, not speech endpoints or intelligibility certification"}


def control_pcm(parent, expected):
    checked_bytes(parent, expected["historical_parent_sha256"])
    with wave.open(str(parent), "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getnframes()) != (1, 2, 48000, 8640000):
            raise ValueError("Historical C1 parent format changed")
        pcm = source.readframes(source.getnframes())
    if sha256(pcm) != expected["historical_parent_pcm_sha256"]:
        raise ValueError("Historical C1 decoded PCM changed")
    if any(pcm[:2880000 * 2]):
        raise ValueError("Selected silence is not exact digital zero")
    for segment in expected["source_to_parent"]:
        start, end = segment["parent_samples"]
        if sha256(pcm[start * 2:end * 2]) != segment["parent_pcm_sha256"]:
            raise ValueError("Historical nonverbal segment mapping changed")
    for start, end in expected["exact_zero_parent_gaps"]:
        if any(pcm[start * 2:end * 2]):
            raise ValueError("Historical nonverbal zero gap changed")
    return pcm


def load_source_acceptance(path, catalogue):
    """Bind the local audible references and reviewed sample positions, not app admission."""
    path = Path(path)
    review = json.loads(checked_bytes(path, catalogue["source_acceptance"]["sha256"]).decode("utf-8"))
    if review.get("status") != "source_accepted_automatic" or review.get("review_level") != "automatic_not_human":
        raise ValueError("Source acceptance must declare its actual automatic review level")
    candidates = {item["id"]: item for item in catalogue["fleurs"]["candidates"]}
    if len(review["p4"]) != len(candidates) or {item["id"] for item in review["p4"]} != candidates.keys():
        raise ValueError("Source acceptance must cover every selected P4 exactly once")
    references = {}
    for item in review["p4"]:
        if item.get("status") != "source_accepted_automatic":
            raise ValueError("Every P4 must have a closed source-acceptance decision")
        candidate = candidates[item["id"]]
        if (item["source_wav_sha256"], item["upstream_reference_sha256"]) != (
                candidate["source_wav_sha256"], candidate["raw_text_utf8_sha256"]):
            raise ValueError("Reviewed reference belongs to different source bytes")
        end = item["speech_end_source_sample"]
        checkpoint = item["checkpoint"]
        if type(end) is not int or not 0 < end <= candidate["source_frames"]:
            raise ValueError("Reviewed speech end must be an actual source sample position")
        if (end != candidate["reviewed_speech_end_source_sample"] or
                item["audible_reference_sha256"] != candidate["audible_reference_utf8_sha256"]):
            raise ValueError("Public source metadata disagrees with the pinned acceptance evidence")
        if (checkpoint["evidence_end_source_sample"] != end or
                checkpoint["reference_utf8_sha256"] != item["audible_reference_sha256"] or
                not checkpoint.get("required_meaning")):
            raise ValueError("Checkpoint must bind the audible reference, meaning and reviewed end")
        if item["audible_reference_sha256"] != item["upstream_reference_sha256"] and not item.get("reference_change"):
            raise ValueError("Audible-reference corrections require an explicit source-review reason")
        reference_path = (path.parent / item["audible_reference_path"]).resolve()
        if not reference_path.is_relative_to(path.parent.resolve()):
            raise ValueError("Reviewed references must stay inside the local acceptance directory")
        payload = checked_bytes(reference_path, item["audible_reference_sha256"])
        payload.decode("utf-8")
        references[item["id"]] = payload
    controls = {item["id"]: item for item in catalogue["c1"]["candidates"]}
    if len(review["c1"]) != len(controls) or {item["id"] for item in review["c1"]} != controls.keys():
        raise ValueError("Source acceptance must cover both C1 controls exactly once")
    for item in review["c1"]:
        if item.get("status") != "source_accepted_automatic":
            raise ValueError("Both C1 controls must have closed source-acceptance decisions")
        if (item["parent_sha256"] != catalogue["c1"]["historical_parent_sha256"] or
                item["parent_samples"] != controls[item["id"]]["parent_samples"] or
                item.get("quality_credit") is not None or item.get("meaning_wait_credit") is not None):
            raise ValueError("C1 acceptance must preserve the parent interval and no-credit contract")
    return review, references


def materialize(catalogue, retained, historical_control, output, ffmpeg="ffmpeg", acceptance=None):
    catalogue, retained, historical_control, output = map(Path, (catalogue, retained, historical_control, output))
    record = json.loads(catalogue.read_text(encoding="utf-8"))
    if output.exists():
        raise ValueError("Use a new output directory; never overwrite existing evidence")
    fleurs = record["fleurs"]
    # Check every immutable input before writing any output.
    tables = {key: checked_bytes(retained / (key + ".tsv"), digest)
              for key, digest in fleurs["split_tsv_sha256"].items()}
    card = checked_bytes(retained / "FLEURS-README.md", fleurs["card_sha256"])
    if acceptance is None and record.get("source_acceptance"):
        acceptance = catalogue.parent / record["source_acceptance"]["path"]
    reviewed, audible_references = load_source_acceptance(acceptance, record) if acceptance else (None, {})
    reviewed_p4 = {item["id"]: item for item in reviewed["p4"]} if reviewed else {}
    reviewed_c1 = {item["id"]: item for item in reviewed["c1"]} if reviewed else {}
    grouping = check_groups(fleurs["candidates"], tables)
    inputs = []
    for candidate in fleurs["candidates"]:
        key = candidate["language"] + "-" + candidate["upstream_split"]
        source = retained / (key + "-" + candidate["filename"])
        checked_bytes(source, candidate["source_wav_sha256"])
        inputs.append((candidate, source, reference_row(tables[key], candidate)))
    parent_pcm = control_pcm(historical_control, record["c1"])
    for source in record["c1"]["sources"]:
        checked_bytes(historical_control.parent / "sources" / source["filename"], source["sha256"])
    for item in reviewed_c1.values():
        start, end = item["parent_samples"]
        if sha256(parent_pcm[start * 2:end * 2]) != item["pcm_sha256"]:
            raise ValueError("Reviewed C1 PCM no longer matches its parent")
    ffmpeg = shutil.which(str(ffmpeg)) or str(ffmpeg)
    version = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    output.mkdir(parents=True)
    for folder in ("sources", "references", "decoded", "playback", "controls", "provenance"):
        (output / folder).mkdir()
    for key, payload in tables.items():
        (output / "provenance" / (key + ".tsv")).write_bytes(payload)
    (output / "provenance" / "FLEURS-README.md").write_bytes(card)
    save_json(output / "provenance" / "catalogue.json", record)
    episodes = []
    for candidate, source, reference in inputs:
        identity = candidate["id"]
        destination = output / "sources" / (identity + ".wav")
        shutil.copyfile(source, destination)
        native, native_command = decode(ffmpeg, destination, 16000, "pcm_f32le", "f32le")
        playback, playback_command = decode(ffmpeg, destination, 48000, "pcm_s16le", "s16le")
        if sha256(native) != candidate["decoded_f32le_sha256"] or len(native) != candidate["source_frames"] * 4:
            raise ValueError("Decoded native PCM differs from pinned evidence")
        if sha256(playback) != candidate["playback_s16le_sha256"] or len(playback) != candidate["source_frames"] * 3 * 2:
            raise ValueError("Playback PCM differs from pinned conversion evidence")
        (output / "decoded" / (identity + ".f32le")).write_bytes(native)
        upstream_path = output / "references" / (identity + ".upstream.txt")
        upstream_text = reference.pop("text_utf8")
        upstream_path.write_bytes(upstream_text)
        audible_text = audible_references.get(identity, upstream_text)
        text_path = output / "references" / (identity + ".txt")
        text_path.write_bytes(audible_text)
        reference["upstream_raw_text"] = reference["raw_text"]
        reference["upstream_normalized_text"] = reference.pop("normalized_text")
        reference["raw_text"] = audible_text.decode("utf-8")
        decision = reviewed_p4.get(identity)
        speech_end = decision["speech_end_source_sample"] / 16000 if decision else None
        playback_path = output / "playback" / (identity + ".wav")
        save_wave(playback_path, playback)
        episodes.append({**candidate, "kind": "P4", "status": "source_accepted_automatic" if decision else "materialized_not_frozen", "logical_role": "A",
                         "source_language": candidate["language"][:2],
                         "target_language": "zh" if candidate["language"] == "en_us" else "ko",
                         "source_url": f"https://huggingface.co/datasets/google/fleurs/resolve/{fleurs['revision']}/data/{candidate['language']}/audio/{candidate['upstream_split']}.tar.gz",
                         "archive_member": candidate["upstream_split"] + "/" + candidate["filename"],
                         "source_path": destination.relative_to(output).as_posix(),
                         "reference_path": text_path.relative_to(output).as_posix(), "reference": reference,
                         "upstream_reference_path": upstream_path.relative_to(output).as_posix(),
                         "upstream_raw_text_utf8_sha256": candidate["raw_text_utf8_sha256"],
                         "raw_text_utf8_sha256": sha256(audible_text),
                         "decoded_path": f"decoded/{identity}.f32le", "signal": signal_summary(native),
                         "playback_path": playback_path.relative_to(output).as_posix(), "playback_wav_sha256": sha256(playback_path.read_bytes()),
                         "mapping": {"source_samples": [0, candidate["source_frames"]],
                                     "playback_samples": [0, candidate["source_frames"] * 3], "sample_rate_ratio": [3, 1],
                                     "gain_linear": 1, "added_silence_samples": 0, "time_compression": False},
                         "decode_command": native_command, "playback_command": playback_command,
                         "speech_intervals": [[0, speech_end]] if decision else None,
                         "speech_interval_start_policy": "Conservative role-A buffer starts at file origin; leading silence retained, not a phonetic onset claim",
                         "reviewed_speech_end_source_sample": decision["speech_end_source_sample"] if decision else None,
                         "reviewed_checkpoint_end_playback_sample": decision["speech_end_source_sample"] * 3 if decision else None,
                         "checkpoint": decision["checkpoint"] if decision else None,
                         "reference_change": decision.get("reference_change") if decision else None,
                         "source_acceptance_status": "source_accepted_automatic" if decision else "pending_review",
                         "endpoint_status": "Reviewed automatic preparation coordinate, not calibrated exact phonetic timing" if decision
                                            else "pending content/alignment review; entire file retained, not assumed all speech"})
    controls = []
    for candidate in record["c1"]["candidates"]:
        start, end = candidate["parent_samples"]
        if not 0 <= start < end <= 5760000:
            raise ValueError("C1 must exclude the historical AMI speech region")
        pcm = parent_pcm[start * 2:end * 2]
        if candidate.get("expected_pcm_sha256") and sha256(pcm) != candidate["expected_pcm_sha256"]:
            raise ValueError("C1 selected PCM checksum changed")
        path = output / "controls" / (candidate["id"] + ".wav")
        save_wave(path, pcm)
        reference_path = output / "references" / (candidate["id"] + ".txt")
        reference_path.write_bytes(b"")
        source_mapping = [{**segment, "playback_samples": [segment["parent_samples"][0] - start,
                                                          segment["parent_samples"][1] - start]}
                          for segment in record["c1"]["source_to_parent"]
                          if start <= segment["parent_samples"][0] < segment["parent_samples"][1] <= end]
        controls.append({**candidate, "kind": "C1", "path": path.relative_to(output).as_posix(),
                         "wav_sha256": sha256(path.read_bytes()), "pcm_sha256": sha256(pcm), "frames": end - start,
                         "parent_sha256": record["c1"]["historical_parent_sha256"],
                         "mapping": {"parent_samples": [start, end], "playback_samples": [0, end-start], "gain_linear": 1,
                                     "conversion": "none; exact PCM16 sample crop", "time_compression": False},
                         "recorded_source_mapping": source_mapping,
                         "reference_path": reference_path.relative_to(output).as_posix(), "reference_utf8_sha256": sha256(b""),
                         "speech_intervals": [], "quality_credit": None, "meaning_wait_credit": None,
                         "source_acceptance_status": "source_accepted_automatic" if candidate["id"] in reviewed_c1 else "pending_review",
                         "status": "source_accepted_automatic" if candidate["id"] in reviewed_c1
                                   else "exact_zero_candidate" if not any(pcm) else "pending_incidental_speech_review"})
    report = {"schema_version": 1, "status": "source_accepted_automatic" if reviewed else "materialized_not_frozen", "offline": True,
              "catalogue_sha256": sha256(catalogue.read_bytes()), "ffmpeg": version,
              "historical_parent": str(historical_control.resolve()), "historical_parent_preserved": True,
              "grouping": grouping, "p4": episodes, "c1": controls,
              "review_level": reviewed["review_level"] if reviewed else "signal_and_source_binding_only; no listening, ASR or endpoint acceptance in this command",
              "source_acceptance": {"path": str(Path(acceptance).resolve()), "sha256": record["source_acceptance"]["sha256"]} if reviewed else None,
              "production_frozen": False, "r6_runtime_admitted": False,
              "freeze_gates": record["freeze_gates"]}
    save_json(output / "materialization.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", type=Path, default=Path("corpus/r2/read-controls.json"))
    parser.add_argument("--retained", type=Path, required=True, help="Pinned source research directory; read-only")
    parser.add_argument("--historical-control", type=Path, required=True, help="Unchanged historical nonspeech.wav; read-only")
    parser.add_argument("--output", type=Path, default=Path(".data/r2/read-controls/accepted-v2"))
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--acceptance", type=Path, help="Pinned local source review; otherwise use the catalogue-relative acceptance path")
    args = parser.parse_args()
    report = materialize(args.catalogue, args.retained, args.historical_control, args.output, args.ffmpeg, args.acceptance)
    print(json.dumps({"status": report["status"], "p4": len(report["p4"]), "c1": len(report["c1"]),
                      "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
