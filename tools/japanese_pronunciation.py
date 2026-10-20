from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import time
from pathlib import Path
from functools import partial


ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".data" / "japanese"
MODEL = "jonatasgrosman/wav2vec2-large-xlsr-53-japanese"
REVISION = "cf031e020336460d15a417eba710bbc5bb43be9a"
FRONTEND_PACKAGES = {"pyopenjtalk-plus": "0.4.1.post9", "SudachiPy": "0.7.0", "SudachiDict-core": "20261015"}
FRONTEND_OPTIONS = {"run_marine": False, "use_vanilla": False, "use_tsqyomi": False, "use_sudachi_kanji_yomi": True, "predict_nani": False, "normalize_mode": "None", "use_read_as_pron": False, "revert_long_vowels": False, "revert_yotsugana": False}


def load_reading_frontend():
    import pyopenjtalk
    versions = {name: importlib.metadata.version(name) for name in FRONTEND_PACKAGES}
    if versions != FRONTEND_PACKAGES:
        raise ValueError(f"Reading-generation versions differ from the pinned preparation: {versions}")
    bundled = Path(pyopenjtalk.__file__).parent / "dictionary"
    if Path(os.fsdecode(pyopenjtalk.OPEN_JTALK_DICT_DIR)).resolve() != bundled.resolve():
        raise ValueError("Pinned reading generation requires the bundled dictionary; unset OPEN_JTALK_DICT_DIR overrides")
    hashes = {}
    for path in sorted(bundled.iterdir()):
        if path.is_file():
            with path.open("rb") as stream:
                hashes[path.name] = hashlib.file_digest(stream, "sha256").hexdigest()
    provenance = {"packages": versions, "options": FRONTEND_OPTIONS, "bundled_dictionary_sha256": hashes, "dictionary_override": False, "nani_policy": "Explicitly disabled to reproduce the observed original environment where optional ONNX/Nani prediction was unavailable; import warning is not suppressed."}
    return partial(pyopenjtalk.run_frontend, **FRONTEND_OPTIONS), provenance


def pronunciation_targets(surface_words: list[str], frontend, vocab: dict) -> tuple[list[str], list[tuple[int, int]]]:
    readings = []
    spans = []
    cursor = 0
    for surface in surface_words:
        features = frontend(surface)
        pronunciation = "".join(item["pron"] for item in features if item.get("pron") and item["pron"] != "*").replace("’", "")
        if not pronunciation or any(char not in vocab for char in pronunciation):
            raise ValueError(f"Pronunciation frontend/acoustic vocabulary does not cover retained surface unit {surface!r}")
        readings.append(pronunciation)
        spans.append((cursor, cursor + len(pronunciation)))
        cursor += len(pronunciation)
    return readings, spans


def audit_cached_readings(record: dict, frontend) -> int:
    vocab = {char: index for index, char in enumerate(set("".join(record["pronunciation_words"])))}
    readings, _ = pronunciation_targets(record["surface_words"], frontend, vocab)
    if readings != record["pronunciation_words"]:
        raise ValueError("Pinned reading generation does not reproduce retained acoustic pronunciation inputs")
    return len(readings)


class PronunciationAligner:
    def __init__(self, threads: int, frontend, frontend_provenance: dict):
        cache = LOCAL / "alignment-repair" / "pronunciation-runtime"
        cache.mkdir(parents=True, exist_ok=True)
        os.environ["HF_HOME"] = str(cache / "huggingface")
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        os.environ["DO_NOT_TRACK"] = "1"
        import torch
        from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
        torch.set_num_threads(threads)
        self.torch = torch
        self.frontend = frontend
        self.frontend_provenance = frontend_provenance
        self.frontend_version = frontend_provenance["packages"]["pyopenjtalk-plus"]
        model_path = LOCAL / "models" / "alignment"
        self.processor = Wav2Vec2Processor.from_pretrained(model_path, local_files_only=True)
        self.model, loading = Wav2Vec2ForCTC.from_pretrained(model_path, local_files_only=True, use_safetensors=False, output_loading_info=True)
        if loading.get("missing_keys") or loading.get("mismatched_keys"):
            raise ValueError("Refusing uninitialized/mismatched pronunciation aligner parameters")
        self.model.eval()
        self.vocab = self.processor.tokenizer.get_vocab()

    def align(self, source: Path, source_sha256: str, start: float, end: float, surface_words: list[str]) -> tuple[list[dict], str]:
        import numpy as np
        from prepare_japanese import load, save
        from japanese_reference import ctc_align
        readings, spans = pronunciation_targets(surface_words, self.frontend, self.vocab)
        start_sample, end_sample = round(start * 16000), round(end * 16000)
        inputs = {"model": MODEL, "revision": REVISION, "frontend": "pyopenjtalk-plus.run_frontend pron fields; nonspoken U+2019 devoicing annotation removed from the kana input view", "frontend_version": self.frontend_version, "frontend_provenance": self.frontend_provenance, "source_sha256": source_sha256, "source_start_sample_16k": start_sample, "source_end_sample_16k": end_sample, "surface_words": surface_words, "pronunciation_words": readings}
        fingerprint = hashlib.sha256(json.dumps(inputs, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        destination = LOCAL / "alignment-repair" / "pronunciation" / f"{fingerprint}.json"
        if destination.exists():
            return load(destination)["predictions"], str(destination.relative_to(ROOT))
        duration = (end_sample - start_sample) / 16000
        command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-ss", str(start_sample / 16000), "-i", str(source), "-t", str(duration), "-ar", "16000", "-ac", "1", "-f", "f32le", "pipe:1"]
        samples = np.frombuffer(subprocess.run(command, check=True, capture_output=True).stdout, dtype="<f4").copy()
        if abs(len(samples) - (end_sample - start_sample)) > 1:
            raise ValueError("Pronunciation alignment acoustic input duration mismatch")
        inputs_tensor = self.processor(samples, sampling_rate=16000, return_tensors="pt", padding=False)
        started = time.time()
        with self.torch.inference_mode():
            logits = self.model(inputs_tensor.input_values, attention_mask=inputs_tensor.get("attention_mask")).logits[0]
            probabilities = self.torch.log_softmax(logits, dim=-1).numpy()
        target = "".join(readings)
        frames = ctc_align(probabilities, [self.vocab[char] for char in target])
        stride_samples = 1
        receptive_samples = 1
        for kernel, stride in zip(self.model.config.conv_kernel, self.model.config.conv_stride):
            receptive_samples += (kernel - 1) * stride_samples
            stride_samples *= stride
        predictions = []
        for surface, pronunciation, (first, last) in zip(surface_words, readings, spans):
            a = max(0.0, (frames[first]["start_frame"] * stride_samples + receptive_samples / 2 - stride_samples / 2) / 16000)
            b = min(duration, ((frames[last - 1]["end_frame"] - 1) * stride_samples + receptive_samples / 2 + stride_samples / 2) / 16000)
            if not 0 <= a < b <= duration:
                raise ValueError("No complete positive acoustic pronunciation interval")
            predictions.append({"text": surface, "pronunciation": pronunciation, "start": a, "end": b, "mean_pronunciation_probability": float(np.mean([frame["mean_probability"] for frame in frames[first:last]]))})
        save(destination, {**inputs, "fingerprint": fingerprint, "acoustic_input_samples": len(samples), "acoustic_pcm_sha256": hashlib.sha256(samples.tobytes()).hexdigest(), "ctc_pronunciation_character_frames": frames, "predictions": predictions, "runtime_seconds": time.time() - started, "timestamp_interpolation": False, "method": "Actual monotone CTC acoustic path over dictionary pronunciations; word extents are occupied pronunciation-character frames, not divided durations or token points.", "uncertainty": "Automatic dictionary pronunciations may be contextually wrong, especially names; acoustic support scores retained, no human validation."})
        return predictions, str(destination.relative_to(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Genuine pronunciation CTC completion after rejected raw dedicated surface predictions; original Reazon words never rewritten.")
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()
    if args.threads < 1:
        parser.error("--threads must be positive")
    from prepare_japanese import digest, load, save, source_path
    from japanese_reference import acoustic_stats, merge_speaker_turns, punctuate, speaker_at
    from japanese_alignment import context_requests
    selection = load(LOCAL / "selection.json")
    frontend, frontend_provenance = load_reading_frontend()
    reading_files = set()
    reading_units = 0
    engine = None
    source_hashes = {}
    observations = []
    retained = []
    failures = []
    for chunk in selection["chunks"]:
        paths = [LOCAL / "references" / f"{chunk['id']}.json"]
        producer = LOCAL / "source-references" / f"{chunk['id']}.json"
        if producer.exists():
            paths.append(producer)
        for path in paths:
            reference = load(path)
            retained.extend({"reference_path": str(path.relative_to(ROOT)), "block": word["block"], "word_id": word["id"], "surface_word": word["text"], "start": word["start"], "end": word["end"], "prediction_path": word["alignment_prediction_path"]} for word in reference["words"] if word.get("timing_status") == "ctc_forced_aligned_dictionary_pronunciation")
            for word in reference["words"]:
                if word.get("timing_status") == "ctc_forced_aligned_dictionary_pronunciation" and word["alignment_prediction_path"] not in reading_files:
                    evidence_path = word["alignment_prediction_path"]
                    reading_units += audit_cached_readings(load(ROOT / evidence_path), frontend)
                    reading_files.add(evidence_path)
            original_text = [word["text"] for word in reference["words"]]
            missing_blocks = sorted({word["block"] for word in reference["words"] if word["start"] is None or word["end"] is None})
            if not missing_blocks:
                continue
            if engine is None:
                engine = PronunciationAligner(args.threads, frontend, frontend_provenance)
            source = source_path(reference["source_id"])
            if str(source) not in source_hashes:
                source_hashes[str(source)] = digest(source)
            for block_id in missing_blocks:
                block = next(block for block in reference["blocks"] if block["id"] == block_id)
                words = [word for word in reference["words"] if word["block"] == block_id]
                required = {index for index, word in enumerate(words) if word["start"] is None or word["end"] is None}
                for request in context_requests(words, required, block):
                    first, last = request["first"], request["last"]
                    try:
                        predictions, evidence = engine.align(source, source_hashes[str(source)], reference["source_start"] + request["start"], reference["source_start"] + request["end"], [word["text"] for word in words[first:last + 1]])
                    except (ValueError, RuntimeError) as error:
                        failures.append({"reference_path": str(path.relative_to(ROOT)), "block": block_id, "reason": str(error)})
                        continue
                    for index in request["required"]:
                        word, prediction = words[index], predictions[index - first]
                        start, end = request["start"] + prediction["start"], request["start"] + prediction["end"]
                        speaker, ambiguous = speaker_at(start, end, reference.get("diarization_segments", reference["turns"]))
                        word.update({"start": start, "end": end, "timing_status": "ctc_forced_aligned_dictionary_pronunciation", "timing_method": "Actual acoustic CTC alignment of pronunciation frontend output; no duration division/interpolation and no ASR-word replacement.", "alignment_model": MODEL, "alignment_model_revision": REVISION, "alignment_prediction_path": evidence, "alignment_prediction_index": index - first, "alignment_mean_pronunciation_probability": prediction["mean_pronunciation_probability"], "speaker": speaker, "speaker_ambiguous": ambiguous or speaker == "unknown"})
                        observations.append({"reference_path": str(path.relative_to(ROOT)), "block": block_id, "word_id": word["id"], "surface_word": word["text"], "pronunciation": prediction["pronunciation"], "start": start, "end": end, "prediction_path": evidence})
            if [word["text"] for word in reference["words"]] != original_text:
                raise ValueError("Pronunciation alignment rewrote retained Reazon words")
            reference["sentences"] = punctuate(reference["words"])
            reference["models"]["pronunciation_alignment"] = {"model": MODEL, "revision": REVISION, "frontend": "pyopenjtalk-plus", "frontend_version": engine.frontend_version, "reference_asr_unchanged": True}
            reference["timing_method"] += " Rejected dedicated raw predictions are completed by a genuine vocabulary-covered dictionary-pronunciation CTC path, with unchanged surface words."
            segments = reference.get("diarization_segments", reference["turns"])
            reference["turns"] = merge_speaker_turns(segments)
            reference["stats"] = acoustic_stats(reference["words"], reference["turns"], segments)
            save(path, reference)
    report = {"failed_candidate": "d39f6e8692e213c3521fc6b40a9e252fe4293c4f", "model": MODEL, "revision": REVISION, "frontend": "pyopenjtalk-plus", "frontend_version": importlib.metadata.version("pyopenjtalk-plus"), "frontend_provenance": frontend_provenance, "cached_reading_reproduction": {"prediction_files_checked": len(reading_files), "surface_units_checked": reading_units, "all_matched": True}, "observations": retained + observations, "newly_aligned_words": len(observations), "reused_aligned_words": len(retained), "failures": failures, "reference_asr_unchanged": True, "timestamp_interpolation": False, "listening_performed": False, "release_cleared": False}
    import shutil
    previous = LOCAL / "alignment-repair" / "pronunciation-report.json"
    if previous.exists():
        history = LOCAL / "alignment-repair" / "attempts" / f"pronunciation-{time.time_ns()}.json"
        history.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(previous, history)
    save(LOCAL / "alignment-repair" / "pronunciation-report.json", report)
    print(json.dumps({"aligned_words": len(observations), "cached_readings_verified": reading_units, "failures": failures}), flush=True)
    if failures:
        raise RuntimeError("Remaining pronunciation acoustic alignments failed; no synthetic timing supplied")


if __name__ == "__main__":
    main()
