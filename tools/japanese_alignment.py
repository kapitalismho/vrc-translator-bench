from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".data" / "japanese"
MODEL = "Qwen/Qwen3-ForcedAligner-0.6B"
REVISION = "c7cbfc2048c462b0d63a45797104fc9db3ad62b7"
DEFAULT_MODEL = ROOT / ".data" / "chinese" / "models" / "models--Qwen--Qwen3-ForcedAligner-0.6B" / "snapshots" / REVISION


def raw_word_predictions(items: list[dict], expected: list[str], duration: float, required: set[int]) -> list[dict]:
    if [item["text"] for item in items] != expected:
        raise ValueError("Dedicated aligner changed/dropped retained Reazon surface words")
    predictions = []
    for index, item in enumerate(items):
        start, end = float(item["start"]), float(item["end"])
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start <= end <= duration + 0.02):
            raise ValueError(f"Invalid raw forced-aligner interval at unit{index}: {start}-{end}; no interpolation permitted")
        end = min(duration, end)
        if index in required and not start < end:
            raise ValueError(f"Required surface word has no positive raw acoustic interval at unit{index}")
        predictions.append({"text": item["text"], "start": start, "end": end})
    return predictions


def prediction_unit_index(reference: dict, word: dict, record: dict) -> int:
    stored = word.get("alignment_prediction_index")
    block_words = [item for item in reference["words"] if item["block"] == word["block"]]
    position = next(index for index, item in enumerate(block_words) if item["id"] == word["id"])
    width = len(record["surface_words"])
    starts = [index for index in range(len(block_words) - width + 1) if index <= position < index + width and [item["text"] for item in block_words[index:index + width]] == record["surface_words"]]
    if len(starts) != 1:
        raise ValueError("Cannot recover a unique actual lexical-context prediction ordinal")
    index = position - starts[0]
    if stored is not None and stored != index:
        raise ValueError("Stored prediction ordinal differs from its actual lexical-context unit")
    return index


def configure_surface_processor(processor, words: list[str]) -> None:
    processor.fix_timestamp = lambda predictions: predictions.tolist()
    processor.tokenize_japanese = lambda _: list(words)


class SurfaceAligner:
    def __init__(self, model_path: Path, threads: int):
        cache = LOCAL / "alignment-repair" / "runtime-cache"
        cache.mkdir(parents=True, exist_ok=True)
        for name in ("HF_HOME", "TORCH_HOME", "NUMBA_CACHE_DIR", "TEMP", "TMP"):
            os.environ[name] = str(cache / name.lower())
            Path(os.environ[name]).mkdir(parents=True, exist_ok=True)
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        os.environ["DO_NOT_TRACK"] = "1"
        import torch
        from qwen_asr import Qwen3ForcedAligner
        torch.set_num_threads(threads)
        self.torch = torch
        self.model = Qwen3ForcedAligner.from_pretrained(str(model_path), dtype=torch.float32, device_map="cpu", attn_implementation="eager")
        with (model_path / "model.safetensors").open("rb") as weights:
            self.model_weights_sha256 = hashlib.file_digest(weights, "sha256").hexdigest()

    def align(self, source: Path, source_sha256: str, source_start: float, source_end: float, words: list[str], required: set[int]) -> tuple[list[dict], str]:
        from prepare_japanese import load, save
        start_sample, end_sample = round(source_start * 16000), round(source_end * 16000)
        duration = (end_sample - start_sample) / 16000
        inputs = {"model": MODEL, "revision": REVISION, "source_audio_sha256": source_sha256, "source_start_sample_16k": start_sample, "source_end_sample_16k": end_sample, "surface_words": words, "language": "Japanese", "timestamp_interpolation": False}
        fingerprint = hashlib.sha256(json.dumps(inputs, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        destination = LOCAL / "alignment-repair" / "predictions" / f"{fingerprint}.json"
        if destination.exists():
            record = load(destination)
            predictions = raw_word_predictions(record["raw_predictions"], words, duration, required)
            return predictions, str(destination.relative_to(ROOT))
        import numpy as np
        command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-ss", str(start_sample / 16000), "-i", str(source), "-t", str(duration), "-ar", "16000", "-ac", "1", "-f", "f32le", "pipe:1"]
        samples = np.frombuffer(subprocess.run(command, check=True, capture_output=True).stdout, dtype="<f4").copy()
        if abs(len(samples) - (end_sample - start_sample)) > 1:
            raise ValueError("Forced-aligner acoustic input does not match source interval")
        configure_surface_processor(self.model.aligner_processor, words)
        started = time.time()
        with self.torch.inference_mode():
            result = list(self.model.align(audio=(samples, 16000), text="".join(words), language="Japanese")[0])
        raw = [{"text": item.text, "start": float(item.start_time), "end": float(item.end_time)} for item in result]
        record = {**inputs, "fingerprint": fingerprint, "acoustic_input_samples": len(samples), "acoustic_input_pcm_sha256": hashlib.sha256(samples.tobytes()).hexdigest(), "raw_predictions": raw, "runtime_seconds": time.time() - started, "unit_policy": "Unchanged existing Fugashi/UniDic surface words requested directly as dedicated model timestamp units; no replacement ASR text or duration division.", "source_file_path": str(source.relative_to(ROOT)), "source_file_sha256": source_sha256}
        try:
            predictions = raw_word_predictions(raw, words, duration, required)
        except ValueError as error:
            record.update({"accepted": False, "rejection": str(error)})
            save(destination, record)
            raise
        record["accepted"] = True
        save(destination, record)
        return predictions, str(destination.relative_to(ROOT))


def context_requests(words: list[dict], required: set[int], block: dict) -> list[dict]:
    groups = []
    for index in sorted(required):
        if groups and index == groups[-1][-1] + 1:
            groups[-1].append(index)
        else:
            groups.append([index])
    requests = []
    for group in groups:
        first, last = max(0, group[0] - 1), min(len(words) - 1, group[-1] + 1)
        anchors = [word for word in words[first:last + 1] if word["start"] is not None and word["end"] is not None]
        start = block["start"] if group[0] == 0 else max(block["start"], min((word["start"] for word in anchors), default=block["start"]) - 0.25)
        end = block["end"] if group[-1] == len(words) - 1 else min(block["end"], max((word["end"] for word in anchors), default=block["end"]) + 0.25)
        if not start < end:
            raise ValueError("No genuine acoustic context interval for retained untimed words")
        requests.append({"first": first, "last": last, "required": group, "start": start, "end": end})
    return requests


def covering_predictions(engine, source: Path, source_hash: str, reference: dict, block: dict, words: list[dict], required: set[int], rejections: list[dict]) -> dict:
    try:
        predictions, evidence = engine.align(source, source_hash, reference["source_start"] + block["start"], reference["source_start"] + block["end"], [word["text"] for word in words], required)
        return {index: {"start": block["start"] + predictions[index]["start"], "end": block["start"] + predictions[index]["end"], "evidence": evidence, "prediction_index": index, "context": "whole_reazon_block"} for index in required}
    except (ValueError, RuntimeError) as error:
        rejections.append({"source_id": reference["source_id"], "block": block["id"], "reason": str(error), "resolution": "New genuine forced-alignment requests over retained word groups plus adjacent numeric acoustic anchors; primary raw rejection is not repaired/interpolated."})
    repaired = {}
    for request in context_requests(words, required, block):
        first, last = request["first"], request["last"]
        relative_required = {index - first for index in request["required"]}
        predictions, evidence = engine.align(source, source_hash, reference["source_start"] + request["start"], reference["source_start"] + request["end"], [word["text"] for word in words[first:last + 1]], relative_required)
        for index in request["required"]:
            prediction = predictions[index - first]
            repaired[index] = {"start": request["start"] + prediction["start"], "end": request["start"] + prediction["end"], "evidence": evidence, "prediction_index": index - first, "context": "bounded_retained_word_group_with_adjacent_acoustic_anchors"}
    return repaired


def align_references(args) -> None:
    from prepare_japanese import digest, load, save, source_path
    from japanese_reference import acoustic_stats, merge_speaker_turns, punctuate, speaker_at
    import shutil
    baseline_manifest = LOCAL / "alignment-repair" / "baseline" / "corpus-japanese-local-preparation.json"
    if not baseline_manifest.exists():
        baseline_manifest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "corpus" / "japanese" / "local-preparation.json", baseline_manifest)
    previous_report = LOCAL / "alignment-repair" / "report.json"
    prior_model = load(previous_report) if previous_report.exists() else {}
    if previous_report.exists() and not args.smoke:
        history = LOCAL / "alignment-repair" / "attempts" / f"{time.time_ns()}.json"
        history.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(previous_report, history)
    selection = load(LOCAL / "selection.json")
    references = []
    for chunk in selection["chunks"]:
        if args.chunks and chunk["id"] not in args.chunks:
            continue
        references.append(("references", chunk["id"], LOCAL / "references" / f"{chunk['id']}.json"))
        producer = LOCAL / "source-references" / f"{chunk['id']}.json"
        if producer.exists() and not args.smoke:
            references.append(("source-references", chunk["id"], producer))
    engine = None
    source_hashes = {}
    observations = []
    retained = []
    failures = []
    primary_rejections = []
    for folder, chunk_id, path in references:
        reference = load(path)
        retained.extend({"folder": folder, "chunk_id": chunk_id, "block": word["block"], "word_id": word["id"], "word_text": word["text"], "start": word["start"], "end": word["end"], "prediction_path": word["alignment_prediction_path"], "context": word.get("alignment_context", "whole_reazon_block")} for word in reference["words"] if word.get("timing_status") == "dedicated_forced_aligner_raw_surface_word")
        previous_words = [word["text"] for word in reference["words"]]
        missing = [word for word in reference["words"] if word["start"] is None or word["end"] is None]
        blocks = sorted({word["block"] for word in missing})
        if args.blocks:
            blocks = [block for block in blocks if block in args.blocks]
        if not blocks:
            continue
        baseline = LOCAL / "alignment-repair" / "baseline" / folder / path.name
        if not baseline.exists():
            save(baseline, reference)
        source = source_path(reference["source_id"])
        if str(source) not in source_hashes:
            source_hashes[str(source)] = digest(source)
        for block_id in blocks:
            block = next(block for block in reference["blocks"] if block["id"] == block_id)
            block_words = [word for word in reference["words"] if word["block"] == block_id]
            required = {index for index, word in enumerate(block_words) if word["start"] is None or word["end"] is None}
            if engine is None:
                engine = SurfaceAligner(args.model_dir, args.threads)
            try:
                predictions = covering_predictions(engine, source, source_hashes[str(source)], reference, block, block_words, required, primary_rejections)
            except (ValueError, RuntimeError) as error:
                failures.append({"folder": folder, "chunk_id": chunk_id, "block": block_id, "error": str(error)})
                continue
            for index in sorted(required):
                word = block_words[index]
                prediction = predictions[index]
                start, end = prediction["start"], prediction["end"]
                speaker, ambiguous = speaker_at(start, end, reference.get("diarization_segments", reference["turns"]))
                word.update({"start": start, "end": end, "timing_status": "dedicated_forced_aligner_raw_surface_word", "timing_method": "Raw Japanese dedicated forced-aligner surface-word prediction; timestamp repair/interpolation disabled; not replacement ASR.", "alignment_model": MODEL, "alignment_model_revision": REVISION, "alignment_prediction_path": prediction["evidence"], "alignment_prediction_index": prediction["prediction_index"], "alignment_context": prediction["context"], "speaker": speaker, "speaker_ambiguous": ambiguous or speaker == "unknown"})
                observations.append({"folder": folder, "chunk_id": chunk_id, "block": block_id, "word_id": word["id"], "word_text": word["text"], "start": start, "end": end, "prediction_path": prediction["evidence"], "context": prediction["context"]})
            block["covering_alignment"] = {"model": MODEL, "revision": REVISION, "prediction_paths": sorted({predictions[index]["evidence"] for index in required}), "repaired_word_ids": [block_words[index]["id"] for index in sorted(required)]}
        if [word["text"] for word in reference["words"]] != previous_words:
            raise ValueError("Alignment repair changed retained Reazon lexical content")
        if not args.smoke:
            reference["sentences"] = punctuate(reference["words"])
            reference["models"]["covering_alignment"] = {"model": MODEL, "revision": REVISION, "timestamp_interpolation": False, "reference_asr_unchanged": True}
            reference["timing_method"] += " Dedicated multilingual forced alignment supplies raw surface-word intervals for the CTC-OOV words; Reazon lexical text is unchanged."
            segments = reference.get("diarization_segments", reference["turns"])
            reference["turns"] = merge_speaker_turns(segments)
            reference["stats"] = acoustic_stats(reference["words"], reference["turns"], segments)
            save(path, reference)
    report = {"failed_candidate": "d39f6e8692e213c3521fc6b40a9e252fe4293c4f", "accepted_findings": ["F1", "F2"], "mode": "smoke" if args.smoke else "apply", "model": MODEL, "revision": REVISION, "model_directory": str(args.model_dir.relative_to(ROOT)), "model_weights_sha256": engine.model_weights_sha256 if engine is not None else prior_model.get("model_weights_sha256"), "model_read_only": True, "timestamp_interpolation": False, "reference_asr": "reazon-research/reazonspeech-k2-v2 unchanged", "observations": retained + observations, "newly_aligned_words": len(observations), "reused_aligned_words": len(retained), "primary_rejections": primary_rejections, "failures": failures, "listening_performed": False, "release_cleared": False}
    destination = LOCAL / "alignment-repair" / (f"smoke-{time.time_ns()}.json" if args.smoke else "report.json")
    save(destination, report)
    print(json.dumps({"report": str(destination.relative_to(ROOT)), "aligned_words": len(observations), "failures": failures}, ensure_ascii=False), flush=True)
    if failures:
        raise RuntimeError(f"{len(failures)} genuine forced-alignment requests failed; raw failures retained, no fabricated timing")


def main() -> None:
    parser = argparse.ArgumentParser(description="Complete Japanese CTC-OOV timing using unchanged Reazon surface words and a dedicated acoustic forced aligner.")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--chunks", nargs="+")
    parser.add_argument("--blocks", type=int, nargs="+")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    args.model_dir = args.model_dir.resolve()
    if args.threads < 1:
        parser.error("--threads must be positive")
    align_references(args)


if __name__ == "__main__":
    main()
