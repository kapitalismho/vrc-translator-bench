from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import subprocess
import tarfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DATA_REVISION = "c9674490249665d658f527e2684848377108d82c"
ASR_REVISION = "291488c8151be24d7da4bf7af26e533fad96e407"
ALIGN_REVISION = "cf031e020336460d15a417eba710bbc5bb43be9a"
DATA_BASE = f"https://huggingface.co/datasets/espnet/yodas2/resolve/{DATA_REVISION}/data/ja000"
ASR_BASE = f"https://huggingface.co/reazon-research/reazonspeech-k2-v2/resolve/{ASR_REVISION}"
ALIGN_BASE = f"https://huggingface.co/jonatasgrosman/wav2vec2-large-xlsr-53-japanese/resolve/{ALIGN_REVISION}"
ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".data" / "japanese"
RIGHTS = {
    "release_cleared": False,
    "status": "NOT_RELEASE_CLEARED_LOCAL_ONLY",
    "dataset_declared_license": "CC-BY-3.0",
    "original_video_url": None,
    "original_creator": None,
    "video_specific_license_evidence": None,
    "reason": "YODAS2 pseudonymous IDs are not original video IDs; original attribution and video-specific rights unresolved. Do not decode mappings or publish derived speech assets.",
    "evidence_urls": [
        f"https://huggingface.co/datasets/espnet/yodas2/blob/{DATA_REVISION}/README.md",
        "https://huggingface.co/datasets/espnet/yodas2/discussions/2",
        "https://huggingface.co/datasets/espnet/yodas2/discussions/6",
        "https://creativecommons.org/licenses/by/3.0/",
    ],
}


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fetch(url: str, path: Path, expected: str | None = None) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    if not path.exists():
        partial = path.with_suffix(path.suffix + ".part")
        with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as out:
            shutil.copyfileobj(response, out, 1024 * 1024)
        partial.replace(path)
    actual = digest(path)
    if expected is not None and actual != expected:
        raise ValueError(f"Checksum mismatch: {path.name}: {actual}")
    return {"url": url, "path": str(path.relative_to(ROOT)), "sha256": actual, "bytes": path.stat().st_size, "elapsed_seconds": round(time.time() - started, 3)}


def acquire(with_alignment: bool = False) -> None:
    jobs = [
        (f"{DATA_BASE}/audio/00000000.tar.gz", LOCAL / "source.tar.gz", "f557b807d448d4ef5383174076892f41b457eaebeff540b5e5b8ee6605ed79f5"),
        (f"{DATA_BASE}/text/00000000.json", LOCAL / "captions.json", None),
        (f"{DATA_BASE}/duration/00000000.txt", LOCAL / "durations.txt", None),
    ]
    for name in ("encoder-epoch-99-avg-1.int8.onnx", "decoder-epoch-99-avg-1.onnx", "joiner-epoch-99-avg-1.int8.onnx", "tokens.txt", "README.md"):
        jobs.append((f"{ASR_BASE}/{name}", LOCAL / "models" / "reazon" / name, None))
    jobs.extend([
        ("https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2", LOCAL / "models" / "segmentation.tar.bz2", None),
        ("https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx", LOCAL / "models" / "embedding.onnx", None),
    ])
    if with_alignment:
        for name in ("pytorch_model.bin", "config.json", "preprocessor_config.json", "special_tokens_map.json", "vocab.json", "README.md"):
            jobs.append((f"{ALIGN_BASE}/{name}", LOCAL / "models" / "alignment" / name, None))
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda job: fetch(*job), jobs))
    save(LOCAL / "acquisition.json", {"rights": RIGHTS, "downloads": results})
    with tarfile.open(LOCAL / "models" / "segmentation.tar.bz2") as archive:
        for member in archive:
            if member.isfile() and Path(member.name).name in {"model.int8.onnx", "LICENSE", "README.md"}:
                target = LOCAL / "models" / "segmentation" / Path(member.name).name
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open("wb") as out:
                    shutil.copyfileobj(source, out)
    print(json.dumps(results, ensure_ascii=False), flush=True)


def inspect() -> None:
    records = load(LOCAL / "captions.json")
    if isinstance(records, dict):
        print(json.dumps({"keys": list(records)[:10]}, ensure_ascii=False))
        return
    for record in records:
        texts = list(record["text"].values())
        print(json.dumps({"id": record["audio_id"], "caption_count": len(texts), "first": texts[:3], "sample": texts[len(texts) // 2:len(texts) // 2 + 2]}, ensure_ascii=False), flush=True)


def extract(ids: set[str]) -> None:
    found = set()
    with tarfile.open(LOCAL / "source.tar.gz", "r|gz") as archive:
        for member in archive:
            source_id = Path(member.name).stem
            if member.isfile() and source_id in ids:
                target = LOCAL / "sources" / Path(member.name).name
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open("wb") as out:
                    shutil.copyfileobj(source, out)
                found.add(source_id)
                print(json.dumps({"source_id": source_id, "path": str(target.relative_to(ROOT)), "bytes": target.stat().st_size, "sha256": digest(target)}), flush=True)
    if found != ids:
        raise ValueError(f"Missing source IDs: {sorted(ids - found)}")


def source_path(source_id: str) -> Path:
    paths = list((LOCAL / "sources").glob(f"{source_id}.*"))
    if len(paths) != 1:
        raise ValueError(f"Expected one extracted file for {source_id}, got {paths}")
    return paths[0]


def cut_audio(source: Path, output: Path, start: float, end: float) -> dict:
    if not 0 <= start < end:
        raise ValueError("Invalid source interval")
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source), "-ss", str(start), "-t", str(end - start),
        "-af", "loudnorm=I=-23:TP=-2:LRA=7:linear=false", "-ar", "48000",
        "-ac", "1", "-c:a", "pcm_s16le", str(output),
    ]
    subprocess.run(command, check=True)
    import soundfile as sf
    info = sf.info(output)
    if info.samplerate != 48000 or info.channels != 1 or abs(info.duration - (end - start)) > 1 / 48000:
        raise ValueError(f"Unexpected rendered audio format/duration: {info}")
    return {"path": str(output.relative_to(ROOT)), "sha256": digest(output), "duration_seconds": info.duration, "sample_rate": info.samplerate, "channels": info.channels, "normalization": "FFmpeg loudnorm -23 LUFS / -2 dBTP / LRA 7, dynamic, PCM16", "rights": RIGHTS}


def assemble(chunks: list[dict], output: Path, gap: float = 2.0) -> list[dict]:
    import numpy as np
    import soundfile as sf
    if gap < 0:
        raise ValueError("Negative interchunk gap")
    mapping = []
    cursor = 0
    output.parent.mkdir(parents=True, exist_ok=True)
    with sf.SoundFile(output, mode="w", samplerate=48000, channels=1, subtype="PCM_16") as out:
        for index, chunk in enumerate(chunks):
            if index:
                out.write(np.zeros(round(gap * 48000), dtype=np.float32))
                cursor += round(gap * 48000)
            audio, rate = sf.read(ROOT / chunk["audio"]["path"], dtype="float32")
            if rate != 48000 or audio.ndim != 1:
                raise ValueError("Only normalized 48k mono chunks can be assembled")
            start = cursor / 48000
            out.write(audio)
            cursor += len(audio)
            mapping.append({"chunk_id": chunk["id"], "source_id": chunk["source_id"], "source_start": chunk["source_start"], "source_end": chunk["source_end"], "playback_start": start, "playback_end": cursor / 48000, "operation": "crop_only_no_silence_compression", "rights": RIGHTS})
    return mapping


def select() -> None:
    seed = 20261020
    pool_a = [("Yr7rGfescvQ", start, start + 180) for start in (67.75, 250.0, 450.0, 650.0, 850.0)]
    pool_b = [("YvBXxjwqeTy", start, start + 240) for start in (25.0, 285.0, 545.0)]
    rng = random.Random(seed)
    general = rng.sample(pool_a, 4) + rng.sample(pool_b, 2)
    rng.shuffle(general)
    chunks = []
    for index, (source_id, start, end) in enumerate(general):
        chunks.append({"id": f"ja-general-{index + 1:02}", "split": "main", "category": "general", "topic": "bonsai_work_discussion", "input_tags": ["mixed_speaker_candidate", "instructional_discussion"], "source_id": source_id, "source_start": start, "source_end": end})
    for index, start in enumerate((0.0, 220.0, 440.0)):
        chunks.append({"id": f"ja-stress-{index + 1:02}", "split": "main", "category": "stress", "topic": "exercise_instruction_responses", "input_tags": ["mixed_speaker_candidate", "fast_response_candidate", "backchannel_candidate"], "source_id": "YIIDry4AVKA", "source_start": start, "source_end": start + 200.0})
    chunks.append({"id": "ja-dev-01", "split": "dev", "category": "development", "topic": "bonsai_work_discussion", "input_tags": ["mixed_speaker_candidate"], "source_id": "Yr7rGfescvQ", "source_start": 1200.0, "source_end": 1500.0})
    chunks.append({"id": "ja-heldout-reserve", "split": "heldout_reserve", "category": "isolated_candidate_pool", "topic": "bonsai_work_discussion", "input_tags": ["mixed_speaker_candidate"], "source_id": "Yr7rGfescvQ", "source_start": 1550.0, "source_end": 2260.0})
    selection = {
        "rights": RIGHTS, "seed": seed, "directions": ["D4", "D6"],
        "state": "LOCAL_CANDIDATES_NOT_FROZEN",
        "rules": {
            "candidate_pool": "Pinned ja000 shard 00000000; first/middle caption samples inspected from all 73 records, with additional selected-record excerpts; only three selected conversational/response candidates extracted for preparation.",
            "general": "Casual chat prioritized before work/discussion. Zero verified casual-chat windows in inspected shard. Provisional bonsai work/discussion pool: five 180s windows from Yr7rGfescvQ and three 240s windows from YvBXxjwqeTy. Fixed-seed sampling selects four and two respectively, then shuffles; no app results used.",
            "eligibility": "Japanese-language real speech, multiple acoustic speakers and conversational interaction. Acoustic/ASR evidence only; no listening was available. Suitability is NOT established by dataset language tag or captions alone.",
            "stress": "Predeclared three 200s exercise-response candidate windows, separate from general. Count acoustic pauses, short responses, speaker changes and overlap estimates; do not assert human stress labels or equal semantic counts.",
            "isolation": "No main/dev/reserve source-time overlap. Heldout extraction must further reject estimated overlap/other-speaker intrusion; isolation remains automatic, not human verified.",
        },
        "casual_chat_seconds_confirmed": 0,
        "general_candidate_pool": [{"source_id": sid, "source_start": start, "source_end": end} for sid, start, end in pool_a + pool_b],
        "general_candidate_seconds": 1200, "stress_candidate_seconds": 600,
        "development_candidate_seconds": 300,
        "elapsed_budget": {"main": 1800, "general": 1200, "stress": 600, "general_assigned_gap_seconds": 12, "stress_assigned_gap_seconds": 4, "final_general_source_seconds": 1188, "final_stress_source_seconds": 596, "state": "source_reference_generation_then_word_safe_crop"},
        "listening_performed": False, "chunks": chunks,
        "curation_adjustments": [{"source_id": "Yr7rGfescvQ", "old_source_interval": [35.71, 215.71], "replacement_source_interval": [67.75, 247.75], "reason": "Exclude an introductory region with sparse speech captions and sparse ASR recovery. Actual 30s Reazon probes from the old start produced only 10-16 characters; supplementary captions identify sustained discussion after 67.75s. This is pre-freeze source curation, not tuning on app benchmark outputs; no listening claimed."}],
        "common_clip_shortlist": [{"chunk_id": "ja-general-01", "chunk_start": 30, "chunk_end": 60}, {"chunk_id": "ja-stress-01", "chunk_start": 20, "chunk_end": 50}],
        "blockers": ["Original-video attribution/rights unresolved: no Japanese release.", "No listening/content inspection tool: mixed-speaker estimates do not prove 30m suitable Japanese conversation.", "PP4 actual ASR not resolved; reference independence must be checked before freeze."],
    }
    save(LOCAL / "selection.json", selection)
    print(json.dumps({"chunks": len(chunks), "candidate_source_seconds_before_budget": 1800, "main_elapsed_budget_seconds": 1800, "dev_seconds": 300, "heldout_reserve_seconds": 710, "state": selection["state"]}), flush=True)


def render(only: set[str] | None = None) -> None:
    selection = load(LOCAL / "selection.json")
    for chunk in selection["chunks"]:
        if only is not None and chunk["id"] not in only:
            continue
        chunk["audio"] = cut_audio(source_path(chunk["source_id"]), LOCAL / "chunks" / f"{chunk['id']}.wav", chunk["source_start"], chunk["source_end"])
        print(json.dumps({"chunk_id": chunk["id"], **chunk["audio"]}), flush=True)
    save(LOCAL / "selection.json", selection)


def reference(only: set[str] | None, limit: float | None, threads: int) -> None:
    import os
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HOME"] = str(LOCAL / "hf-cache")
    from japanese_reference import ReferenceEngine
    engine = ReferenceEngine(LOCAL / "models", threads)
    selection = load(LOCAL / "selection.json")
    for chunk in selection["chunks"]:
        if only is not None and chunk["id"] not in only:
            continue
        path = ROOT / chunk["audio"]["path"]
        folder = "probes" if limit is not None else "references"
        name = f"{chunk['id']}-{time.time_ns()}" if limit is not None else chunk["id"]
        destination = LOCAL / folder / f"{name}.json"
        result = engine.run(path, limit)
        result.update({"rights": RIGHTS, "source_id": chunk["source_id"], "source_start": chunk["source_start"], "source_end": chunk["source_end"], "audio_sha256": digest(path)})
        save(destination, result)
        print(json.dumps({"reference": str(destination.relative_to(ROOT)), "words": len(result["words"]), "aligned_words": sum(word["start"] is not None for word in result["words"]), "stats": result["stats"], "runtime": result["runtime"]}), flush=True)


def complete_alignment(aligner_python: Path, pronunciation_python: Path, model_dir: Path, threads: int) -> None:
    report_path = LOCAL / "alignment-repair" / "report.json"
    previous_mtime = report_path.stat().st_mtime_ns if report_path.exists() else None
    command = [str(aligner_python), "-B", "-X", "utf8", str(ROOT / "tools" / "japanese_alignment.py"), "--model-dir", str(model_dir), "--threads", str(threads)]
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode:
        if not report_path.exists() or report_path.stat().st_mtime_ns == previous_mtime or not load(report_path).get("failures"):
            raise subprocess.CalledProcessError(result.returncode, command)
        print("Raw dedicated predictions rejected and retained; completing only unresolved words with genuine pronunciation CTC.", flush=True)
    subprocess.run([str(pronunciation_python), "-B", "-X", "utf8", str(ROOT / "tools" / "japanese_pronunciation.py"), "--threads", str(threads)], cwd=ROOT, check=True)
    from japanese_alignment import prediction_unit_index
    prediction_records = {}
    inventory = []
    for chunk in load(LOCAL / "selection.json")["chunks"]:
        paths = [LOCAL / "references" / f"{chunk['id']}.json"]
        producer = LOCAL / "source-references" / f"{chunk['id']}.json"
        if producer.exists():
            paths.append(producer)
        for path in paths:
            ref = load(path)
            for word in ref["words"]:
                if word.get("timing_status") in {"dedicated_forced_aligner_raw_surface_word", "ctc_forced_aligned_dictionary_pronunciation"}:
                    evidence_path = word["alignment_prediction_path"]
                    if evidence_path not in prediction_records:
                        prediction_records[evidence_path] = load(ROOT / evidence_path)
                    word["alignment_prediction_index"] = prediction_unit_index(ref, word, prediction_records[evidence_path])
            inventory.append(timing_inventory(str(path.relative_to(ROOT)), ref, ref["audio_duration_seconds"]))
            ref["timing_method"] = "Initial Japanese Wav2Vec2 CTC constrained-Viterbi character occupancy supplies supported lexical-word spans; those intervals remain unchanged. Initial CTC-OOV words use genuine raw dedicated surface-word predictions or, after rejected raw predictions, vocabulary-covered dictionary-pronunciation CTC character occupancy as recorded per word. No replacement ASR, word deletion, interpolation, duration division or token-point interval substitution. Dictionary pronunciations, especially names, and all automatic acoustic estimates remain uncertain; no human validation."
            save(path, ref)
    completion = {"failed_candidate": "d39f6e8692e213c3521fc6b40a9e252fe4293c4f", "reference_asr_unchanged": True, "timestamp_interpolation": False, "timing_inventory": inventory, "unresolved_missing_word_bounds": 0, "unresolved_missing_sentence_bounds": 0, "dedicated_report": str(report_path.relative_to(ROOT)), "pronunciation_report": ".data/japanese/alignment-repair/pronunciation-report.json", "rejected_attempt_history": ".data/japanese/alignment-repair/attempts", "listening_performed": False, "release_cleared": False}
    save(LOCAL / "alignment-repair" / "completion.json", completion)
    print(json.dumps({"complete_alignment_inventory_assets": len(inventory), "missing_word_bounds": 0, "missing_sentence_bounds": 0}), flush=True)


def apply_elapsed_budget() -> None:
    from japanese_budget import RATE, choose_trim_plan, crop_units
    from japanese_reference import acoustic_stats, merge_speaker_turns, punctuate
    selection = load(LOCAL / "selection.json")
    if selection.get("elapsed_budget", {}).get("state") == "applied":
        return
    plans = []
    for category, target_seconds in (("general", 1188), ("stress", 596)):
        chunks = [chunk for chunk in selection["chunks"] if chunk["split"] == "main" and chunk["category"] == category]
        references = []
        for chunk in chunks:
            producer_path = LOCAL / "source-references" / f"{chunk['id']}.json"
            if not producer_path.exists():
                save(producer_path, load(LOCAL / "references" / f"{chunk['id']}.json"))
            references.append(load(producer_path))
        original_seconds = sum(round(ref["audio_duration_seconds"] * RATE) for ref in references) / RATE
        crop_plans = choose_trim_plan(references, original_seconds - target_seconds)
        plans.extend(zip(chunks, references, crop_plans))
    for chunk, producer, plan in plans:
        producer_path = LOCAL / "source-references" / f"{chunk['id']}.json"
        source_start = producer["source_start"] + plan["start_sample"] / RATE
        source_end = producer["source_start"] + plan["end_sample"] / RATE
        chunk.update({
            "producer_source_start": producer["source_start"], "producer_source_end": producer["source_end"],
            "source_reference_path": str(producer_path.relative_to(ROOT)), "source_reference_sha256": digest(producer_path),
            "source_start": source_start, "source_end": source_end,
            "budget_trim": {**plan, "sample_rate": RATE, "boundary_basis": "outside aligned words, estimated voice segments and untimed ASR blocks with 20ms guard; unchanged endpoints permitted"},
        })
        if plan["trim_samples"]:
            chunk["audio"] = cut_audio(source_path(chunk["source_id"]), LOCAL / "chunks" / f"{chunk['id']}.wav", source_start, source_end)
            units = crop_units(producer, plan["start_sample"], plan["end_sample"])
            turns = merge_speaker_turns(units["diarization_segments"])
            ref = {
                **producer, **units, "turns": turns, "sentences": punctuate(units["words"]),
                "stats": acoustic_stats(units["words"], turns, units["diarization_segments"]),
                "audio_duration_seconds": chunk["audio"]["duration_seconds"], "audio_sha256": chunk["audio"]["sha256"],
                "source_start": source_start, "source_end": source_end,
                "source_reference_path": str(producer_path.relative_to(ROOT)), "source_reference_sha256": chunk["source_reference_sha256"],
                "reference_transform": "Source-relative crop/remap only; unchanged ASR/CTC inference reused. Audio re-cropped and normalized without retiming or inserting within-chunk silence.",
                "runtime": {**producer["runtime"], "measured_source_audio_seconds": producer["audio_duration_seconds"], "inference_reused_after_crop": True},
            }
            save(LOCAL / "references" / f"{chunk['id']}.json", ref)
        print(json.dumps({"elapsed_budget_chunk": chunk["id"], "source_start": source_start, "source_end": source_end, "trim_seconds": plan["trim_seconds"], "side": plan["side"]}), flush=True)
    selection["elapsed_budget"] = {
        "state": "applied", "main": 1800, "general": 1200, "stress": 600,
        "general_source_seconds": 1188, "stress_source_seconds": 596,
        "general_assigned_gap_seconds": 12, "stress_assigned_gap_seconds": 4,
        "accounting": "Five internal general gaps plus general-to-stress gap assigned to general; two internal stress gaps assigned to stress. Source audio totals1784s plus16s separators.",
        "word_boundary_basis": "Estimated acoustic silence plus aligned-word/untimed-block exclusion, not human listening.",
        "producer_references": ".data/japanese/source-references",
    }
    save(LOCAL / "selection.json", selection)


def playback_references() -> None:
    from japanese_reference import acoustic_stats, merge_speaker_turns
    apply_elapsed_budget()
    selection = load(LOCAL / "selection.json")
    for chunk in selection["chunks"]:
        path = LOCAL / "references" / f"{chunk['id']}.json"
        ref = load(path)
        if chunk.get("source_reference_path"):
            producer_sha256 = digest(ROOT / chunk["source_reference_path"])
            chunk["source_reference_sha256"] = producer_sha256
            ref["source_reference_sha256"] = producer_sha256
        if "diarization_segments" not in ref:
            ref["diarization_segments"] = ref["turns"]
        ref["turns"] = merge_speaker_turns(ref["diarization_segments"])
        ref["turn_definition"] = "Consecutive same-label diarization segments coalesced across their preserved pauses; a new turn follows an estimated speaker-label change. Overlapping estimated speakers remain visible."
        ref["stats"] = acoustic_stats(ref["words"], ref["turns"], ref["diarization_segments"])
        save(path, ref)
    save(LOCAL / "selection.json", selection)
    for split in ("main", "dev"):
        chunks = [chunk for chunk in selection["chunks"] if chunk["split"] == split]
        audio_path = LOCAL / "playback" / f"ja-{split}.wav"
        mapping = {"rights": RIGHTS, "directions": ["D4", "D6"], "gap_seconds": 2, "mapping": assemble(chunks, audio_path), "audio_sha256": digest(audio_path), "elapsed_budget": selection["elapsed_budget"]}
        save(LOCAL / "playback" / f"ja-{split}-mapping.json", mapping)
        combined = {"rights": RIGHTS, "directions": ["D4", "D6"], "reference_level": "automatic_exploratory", "listening_performed": False, "speaker_uncertainty": "Anonymous estimated clusters can substantially split/merge real voices; labels are chunk-local, not verified identities.", "word_timing_uncertainty": "Supported CTC acoustic intervals plus raw dedicated surface-word/pronunciation forced alignment for CTC-OOV words; automatic, not human verified; no interpolated timing.", "audio_sha256": mapping["audio_sha256"], "mapping": mapping["mapping"], "words": [], "sentences": [], "turns": []}
        for cut in mapping["mapping"]:
            reference_path = LOCAL / "references" / f"{cut['chunk_id']}.json"
            ref = load(reference_path)
            for kind in ("words", "sentences", "turns"):
                for item in ref[kind]:
                    entry = {**item, "chunk_id": cut["chunk_id"], "source_id": cut["source_id"]}
                    for key in ("start", "end"):
                        value = item[key]
                        entry[f"source_{key}"] = None if value is None else cut["source_start"] + value
                        entry[key] = None if value is None else cut["playback_start"] + value
                    combined[kind].append(entry)
        save(LOCAL / "playback" / f"ja-{split}-reference.json", combined)
        print(json.dumps({"split": split, "words": len(combined["words"]), "sentences": len(combined["sentences"]), "turns": len(combined["turns"])}), flush=True)


def isolated_candidates(ref: dict) -> list[dict]:
    candidates = []
    untimed_blocks = {word["block"] for word in ref["words"] if word["start"] is None or word["end"] is None}
    for segment in ref["diarization_segments"]:
        start = max(0.0, segment["start"] - 0.08)
        end = min(ref["audio_duration_seconds"], segment["end"] + 0.08)
        if segment["speaker"] == "unknown" or not 0.4 <= end - start <= 18:
            continue
        if any(other["speaker"] != segment["speaker"] and other["start"] < end and other["end"] > start for other in ref["diarization_segments"]):
            continue
        if any(block["id"] in untimed_blocks and block["start"] < end and block["end"] > start for block in ref["blocks"]):
            continue
        intersecting = [(index, word) for index, word in enumerate(ref["words"]) if word["start"] is not None and word["start"] < end and word["end"] > start]
        if any(word["start"] < start or word["end"] > end for _, word in intersecting):
            continue
        word_ids = [index for index, _ in intersecting]
        words = [ref["words"][index] for index in word_ids]
        if not words or any(word["speaker_ambiguous"] or word["speaker"] != segment["speaker"] for word in words):
            continue
        paused = any(b["start"] - a["end"] >= 0.3 for a, b in zip(words, words[1:]))
        tags = []
        if end - start <= 3:
            tags.append("short")
        if end - start >= 6:
            tags.append("long")
        if paused:
            tags.append("internally_paused")
        candidates.append({"start": start, "end": end, "speaker": segment["speaker"], "tags": tags, "word_ids": word_ids})
    return candidates


def heldout() -> None:
    from japanese_reference import punctuate
    selection = load(LOCAL / "selection.json")
    reserve = next(chunk for chunk in selection["chunks"] if chunk["split"] == "heldout_reserve")
    ref = load(LOCAL / "references" / f"{reserve['id']}.json")
    pool = isolated_candidates(ref)
    rng = random.Random(selection["seed"])
    rng.shuffle(pool)
    chosen = []
    for category in ("internally_paused", "long", "short", None):
        count = 5 if category else 20 - len(chosen)
        for candidate in pool:
            if count <= 0:
                break
            if category is not None and category not in candidate["tags"]:
                continue
            if any(candidate["start"] < other["end"] and candidate["end"] > other["start"] for other in chosen):
                continue
            chosen.append(candidate)
            count -= 1
    if len(chosen) != 20:
        raise ValueError(f"Need20 complete-word isolated utterances; selected {len(chosen)} from {len(pool)} candidates")
    if any(not any(category in candidate["tags"] for candidate in chosen) for category in ("short", "long", "internally_paused")):
        raise ValueError("Isolated selection must retain short, long and internally-paused coverage")
    entries = []
    baseline = LOCAL / "alignment-repair" / "baseline" / "heldout"
    old_index = LOCAL / "heldout" / "index.json"
    if old_index.exists() and not (baseline / "index.json").exists():
        baseline.mkdir(parents=True, exist_ok=True)
        for old in load(old_index)["entries"]:
            shutil.copyfile(ROOT / old["audio"]["path"], baseline / f"{old['id']}.wav")
            shutil.copyfile(LOCAL / "heldout" / f"{old['id']}.json", baseline / f"{old['id']}.json")
        shutil.copyfile(old_index, baseline / "index.json")
    source = source_path(reserve["source_id"])
    for index, candidate in enumerate(chosen):
        clip_id = f"ja-isolated-{index + 1:02}"
        start = reserve["source_start"] + candidate["start"]
        end = reserve["source_start"] + candidate["end"]
        audio = cut_audio(source, LOCAL / "heldout" / f"{clip_id}.wav", start, end)
        words = []
        for word_id in candidate["word_ids"]:
            word = ref["words"][word_id]
            words.append({**word, "origin_word_id": word["id"], "id": len(words), "source_start": reserve["source_start"] + word["start"], "source_end": reserve["source_start"] + word["end"], "start": word["start"] - candidate["start"], "end": word["end"] - candidate["start"]})
        turns = []
        for turn in ref["turns"]:
            a = max(candidate["start"], turn["start"])
            b = min(candidate["end"], turn["end"])
            if a < b:
                turns.append({**turn, "start": a - candidate["start"], "end": b - candidate["start"], "source_start": reserve["source_start"] + a, "source_end": reserve["source_start"] + b})
        sentences = punctuate(words)
        for sentence in sentences:
            sentence["source_start"] = start + sentence["start"]
            sentence["source_end"] = start + sentence["end"]
        entry = {"id": clip_id, "directions": ["D6"], "rights": RIGHTS, "source_id": reserve["source_id"], "source_start": start, "source_end": end, "playback_start": 0, "playback_end": audio["duration_seconds"], "audio": audio, "category_tags": candidate["tags"], "isolation": "automatic_single_estimated_speaker_no_estimated_intrusion_not_listened", "reference_level": "automatic_exploratory", "words": words, "sentences": sentences, "turns": turns, "operation": "source_crop_no_silence_compression"}
        save(LOCAL / "heldout" / f"{clip_id}.json", entry)
        entries.append({key: entry[key] for key in ("id", "rights", "source_id", "source_start", "source_end", "audio", "category_tags", "isolation")})
    save(LOCAL / "heldout" / "index.json", {"rights": RIGHTS, "requested_count": 20, "prepared_count": len(entries), "pool_count": len(pool), "entries": entries})
    print(json.dumps({"heldout_candidate_count": len(entries), "pool_count": len(pool), "category_counts": {category: sum(category in entry["category_tags"] for entry in entries) for category in ("short", "long", "internally_paused")}}), flush=True)


def public_metadata(selection: dict, summaries: dict) -> dict:
    return {
        "schema_version": 1, "language": "ja", "directions": ["D4", "D6"],
        "rights": RIGHTS, "state": selection["state"], "publication": "NO_AUDIO_OR_DERIVED_SPEECH_PUBLICATION",
        "reference_level": "automatic_exploratory", "source_dataset": "espnet/yodas2", "source_revision": DATA_REVISION,
        "released_artifact_location": None, "same_audio_direction_pair": ["D4", "D6"],
        "local_acceptance_scope": "Local audio/reference/checksum/rights-and-unresolved-record preparation only. This is not release clearance; no Hugging Face or Git publication of derived speech.",
        "dataset_attribution": {"title": "YODAS: Youtube-Oriented Dataset for Audio and Speech / YODAS2 long-form packaging", "publisher": "ESPnet", "authors": ["Xinjian Li", "Shinnosuke Takamichi", "Takaaki Saeki", "William Chen", "Sayaka Shiota", "Shinji Watanabe"], "citation": "ASRU 2023, pp. 1-8", "paper_url": "https://arxiv.org/abs/2406.00899", "license_url": "https://creativecommons.org/licenses/by/3.0/", "warning": "Dataset attribution is not selected-video attribution or release clearance."},
        "curation_adjustments": selection["curation_adjustments"],
        "seed": selection["seed"], "selection_rules": selection["rules"],
        "general_candidate_pool": selection["general_candidate_pool"],
        "general_candidate_seconds": selection["general_candidate_seconds"], "stress_candidate_seconds": selection["stress_candidate_seconds"],
        "general_elapsed_seconds": 1200, "stress_elapsed_seconds": 600,
        "general_source_seconds": round(sum(chunk["source_end"] - chunk["source_start"] for chunk in selection["chunks"] if chunk["split"] == "main" and chunk["category"] == "general"), 9),
        "stress_source_seconds": round(sum(chunk["source_end"] - chunk["source_start"] for chunk in selection["chunks"] if chunk["split"] == "main" and chunk["category"] == "stress"), 9),
        "elapsed_budget": selection["elapsed_budget"],
        "development_candidate_seconds": selection["development_candidate_seconds"], "casual_chat_seconds_confirmed": 0,
        "caption_tag_casual_chat_fraction_of_general_candidates": 0.0, "actual_casual_chat_fraction": None, "listening_performed": False,
        "chunks": [{"rights": RIGHTS, **{key: chunk[key] for key in ("id", "split", "category", "topic", "input_tags", "source_id", "source_start", "source_end", "audio", "producer_source_start", "producer_source_end", "source_reference_path", "source_reference_sha256", "budget_trim") if key in chunk}} for chunk in selection["chunks"]],
        "common_clip_shortlist": selection["common_clip_shortlist"],
        "local_artifact_pointers": {"selection": ".data/japanese/selection.json", "references": ".data/japanese/references", "playback": ".data/japanese/playback", "main_audio": ".data/japanese/playback/ja-main.wav", "dev_audio": ".data/japanese/playback/ja-dev.wav", "main_timeline": ".data/japanese/playback/ja-main-reference.json", "dev_timeline": ".data/japanese/playback/ja-dev-reference.json", "heldout": ".data/japanese/heldout/index.json", "runtime_checks": ".data/japanese/checks.json"},
        "sources": [{"pseudo_session_id": sid, "original_video_url": None, "original_creator": None, "video_specific_license_evidence": None, "dataset_audio_url": f"{DATA_BASE}/audio/00000000.tar.gz", "dataset_caption_url": f"{DATA_BASE}/text/00000000.json", "rights": RIGHTS} for sid in sorted({chunk["source_id"] for chunk in selection["chunks"]})],
        "reference_execution": {
            "decoder": "modified_beam_search", "max_active_paths": 4,
            "inference_padding_seconds_each_end": 0.9, "asr_window_seconds": [6, 8],
            "device": "cpu", "default_threads": 2,
            "captions_used_as_reference": False, "word_intervals_from_rnnt_token_points": False,
        },
        "models": {
            "asr": {"id": "reazon-research/reazonspeech-k2-v2", "revision": ASR_REVISION, "license": "Apache-2.0", "precision": "int8_encoder_joiner_fp32_decoder"},
            "alignment": {"id": "jonatasgrosman/wav2vec2-large-xlsr-53-japanese", "revision": ALIGN_REVISION, "license": "Apache-2.0"},
            "covering_alignment": {"id": "Qwen/Qwen3-ForcedAligner-0.6B", "revision": "c7cbfc2048c462b0d63a45797104fc9db3ad62b7", "license": "Apache-2.0", "purpose": "Dedicated acoustic timestamps for unchanged Reazon surface words, not replacement ASR", "timestamp_interpolation": False},
            "covering_pronunciation": {"acoustic_model": "jonatasgrosman/wav2vec2-large-xlsr-53-japanese", "revision": ALIGN_REVISION, "frontend": "pyopenjtalk-plus", "frontend_version": "0.4.1.post9", "purpose": "Genuine CTC pronunciation paths only after raw dedicated predictions are rejected; surface words unchanged", "timestamp_interpolation": False},
            "speakers": {
                "segmentation": "sherpa-onnx-pyannote-segmentation-3-0 int8",
                "segmentation_license": "MIT, CNRS 2022, shipped LICENSE",
                "embedding": "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx",
                "embedding_terms": "upstream 3D-Speaker Apache-2.0; exported file asset-specific evidence not independently established",
                "clustering_threshold": 0.75, "num_clusters": "estimated",
                "min_duration_on": 0.3, "min_duration_off": 0.5,
                "uncertainty": "Labels can merge different speakers or split one voice. Counts and overlap are automatic estimates, not participant identities.",
            },
            "device": "cpu",
        },
        "process": {"audio": "Crop, FFmpeg dynamic loudnorm I=-23 TP=-2 LRA=7, 48k mono PCM16, 2s interchunk gaps, no speech synthesis or long-gap compression", "word_timing": "Supported CTC character-occupancy intervals retained; CTC-OOV surface words completed by raw dedicated forced alignment or vocabulary-covered dictionary-pronunciation CTC after rejected raw predictions. No word deletion, replacement ASR, interpolation, duration division or RNNT token-point interval substitutes.", "punctuation": "Insert punctuation only at acoustic/estimated speaker/ASR-window boundaries; no word rewriting; sentence-like units not syntactically verified", "captions": "Supplementary candidate selection only, never copied into references or public metadata", "independence": "ReazonSpeech differs from explicitly planned evaluated ASRs, but PP4 CPU-auto ASR remains unresolved; dedicated Qwen forced alignment is timing only, not evaluated-ASR replacement text; no claim of disjoint training data"},
        "summaries": summaries, "blockers": selection["blockers"],
    }


def assert_metadata_only(value: object) -> None:
    forbidden = {"text", "transcript", "words", "sentences", "turns", "blocks", "diarization_segments", "asr_tokens", "asr_token_points", "alignment_model_greedy_diagnostic", "word_text", "surface_words", "surface_word", "pronunciation_words", "pronunciation", "raw_predictions", "observations"}
    if isinstance(value, dict):
        if forbidden.intersection(value):
            raise ValueError("Refusing to export derived Japanese speech/timeline content")
        for item in value.values():
            assert_metadata_only(item)
    elif isinstance(value, list):
        for item in value:
            assert_metadata_only(item)


def export_metadata() -> None:
    selection = load(LOCAL / "selection.json")
    summaries = {}
    for chunk in selection["chunks"]:
        path = LOCAL / "references" / f"{chunk['id']}.json"
        if path.exists():
            ref = load(path)
            summaries[chunk["id"]] = {"word_count": len(ref["words"]), "aligned_word_count": sum(word["start"] is not None for word in ref["words"]), "reference_sha256": digest(path), "stats": ref["stats"], "runtime": ref["runtime"]}
    value = public_metadata(selection, summaries)
    acquisition = load(LOCAL / "acquisition.json")
    value["acquisition"] = acquisition
    heldout_path = LOCAL / "heldout" / "index.json"
    if heldout_path.exists():
        value["heldout"] = load(heldout_path)
        for entry in value["heldout"]["entries"]:
            reference_path = LOCAL / "heldout" / f"{entry['id']}.json"
            entry["local_reference_path"] = str(reference_path.relative_to(ROOT))
            entry["reference_sha256"] = digest(reference_path)
        value["heldout"]["index_sha256"] = digest(heldout_path)
    import soundfile as sf
    for source in value["sources"]:
        path = source_path(source["pseudo_session_id"])
        info = sf.info(path)
        source.update({"local_source_path": str(path.relative_to(ROOT)), "source_sha256": digest(path), "source_duration_seconds": info.duration, "source_sample_rate": info.samplerate, "source_channels": info.channels})
    value["eligible_conversation_seconds_confirmed"] = None
    value["eligibility_status"] = "AUTOMATIC_SOURCE_CANDIDATES_NOT_LISTENED"
    value["playback_assets"] = {}
    for split in ("main", "dev"):
        folder = LOCAL / "playback"
        audio_path = folder / f"ja-{split}.wav"
        mapping_path = folder / f"ja-{split}-mapping.json"
        timeline_path = folder / f"ja-{split}-reference.json"
        mapping = load(mapping_path)
        value["playback_assets"][split] = {
            "rights": RIGHTS, "directions": ["D4", "D6"],
            "local_audio_path": str(audio_path.relative_to(ROOT)), "audio_sha256": mapping["audio_sha256"],
            "duration_seconds": sf.info(audio_path).duration,
            "local_mapping_path": str(mapping_path.relative_to(ROOT)), "mapping_sha256": digest(mapping_path),
            "local_timeline_path": str(timeline_path.relative_to(ROOT)), "timeline_sha256": digest(timeline_path),
        }
    checks_path = LOCAL / "checks.json"
    if not checks_path.exists():
        raise ValueError("Run complete Japanese artifact checks before exporting metadata")
    checks = load(checks_path)
    if not checks.get("timing_inventory") or any(item["missing_words_bounds"] or item["missing_sentences_bounds"] for item in checks["timing_inventory"]):
        raise ValueError("Complete word/sentence timing inventory is required for metadata export")
    if len(checks.get("heldout_intersection_audit", [])) != 20:
        raise ValueError("Full isolated-word intersection audit is required for metadata export")
    value["practical_checks"] = checks
    completion_path = LOCAL / "alignment-repair" / "completion.json"
    if completion_path.exists():
        completion = load(completion_path)
        value["alignment_completion"] = {"local_record_path": str(completion_path.relative_to(ROOT)), "record_sha256": digest(completion_path), "missing_word_bounds": completion["unresolved_missing_word_bounds"], "missing_sentence_bounds": completion["unresolved_missing_sentence_bounds"], "reference_asr_unchanged": True, "timestamp_interpolation": False, "raw_attempts_local_directory": ".data/japanese/alignment-repair"}
        dedicated = load(ROOT / completion["dedicated_report"])
        value["models"]["covering_alignment"]["weights_sha256"] = dedicated["model_weights_sha256"]
        pronunciation = load(ROOT / completion["pronunciation_report"])
        value["models"]["covering_pronunciation"]["frontend_version"] = pronunciation["frontend_version"]
        value["models"]["covering_pronunciation"]["frontend_provenance"] = pronunciation["frontend_provenance"]
        value["process"]["alignment_uncertainty"] = "Automatic surface/pronunciation alignment only; dictionary readings may be contextually wrong, especially names. Some paths have very low acoustic likelihood; scores are retained locally but are not calibrated accuracy. Raw units may overlap or share intervals and multiple backends may disagree; no human timing or listening claim."
    assert_metadata_only(value)
    save(ROOT / "corpus" / "japanese" / "local-preparation.json", value)
    print(json.dumps({"metadata": "corpus/japanese/local-preparation.json", "derived_speech_exported": False, "release_cleared": False}), flush=True)


def timing_inventory(label: str, reference: dict, duration: float) -> dict:
    import math
    counts = {"asset": label}
    for kind in ("words", "sentences"):
        records = reference[kind]
        missing = sum(item["start"] is None or item["end"] is None or not math.isfinite(item["start"]) or not math.isfinite(item["end"]) for item in records)
        counts[f"{kind}_count"] = len(records)
        counts[f"missing_{kind}_bounds"] = missing
        if missing:
            raise ValueError(f"Final reference missing/nonfinite {kind} bounds: {label}: {missing}")
        if any(not 0 <= item["start"] < item["end"] <= duration + 1 / 48000 for item in records):
            raise ValueError(f"Final reference {kind} interval outside audio: {label}")
    return counts


def audit_isolated_reference(entry: dict, artifact: dict, reserve: dict) -> dict:
    start = entry["source_start"] - reserve["source_start"]
    end = entry["source_end"] - reserve["source_start"]
    intersecting = [(index, word) for index, word in enumerate(reserve["words"]) if word["start"] is not None and word["start"] < end and word["end"] > start]
    crossing = [index for index, word in intersecting if word["start"] < start - 1e-9 or word["end"] > end + 1e-9]
    if crossing:
        raise ValueError(f"Isolated crop crosses aligned word boundaries: {entry['id']}: {crossing}")
    expected_ids = [index for index, _ in intersecting]
    if [word["origin_word_id"] for word in artifact["words"]] != expected_ids:
        raise ValueError(f"Isolated reference omits or adds intersecting source words: {entry['id']}")
    speakers = {word["speaker"] for _, word in intersecting}
    if len(speakers) != 1 or "unknown" in speakers:
        raise ValueError("Isolated reference lacks a single estimated speaker")
    speaker = next(iter(speakers))
    if any(segment["speaker"] != speaker and segment["start"] < end and segment["end"] > start for segment in reserve["diarization_segments"]):
        raise ValueError("Isolated reference contains estimated other-speaker intrusion")
    untimed = {word["block"] for word in reserve["words"] if word["start"] is None or word["end"] is None}
    if any(block["id"] in untimed and block["start"] < end and block["end"] > start for block in reserve["blocks"]):
        raise ValueError("Isolated reference intersects an untimed ASR block")
    for (_, source), word in zip(intersecting, artifact["words"]):
        if word["text"] != source["text"]:
            raise ValueError("Isolated reference changed source lexical text")
        for key in ("start", "end"):
            absolute = reserve["source_start"] + source[key]
            if abs(word[f"source_{key}"] - absolute) > 1e-8 or abs(word[key] - (absolute - entry["source_start"])) > 1e-8:
                raise ValueError("Isolated word source/playback mapping mismatch")
    return {"id": entry["id"], "intersecting_source_word_count": len(intersecting), "emitted_word_count": len(artifact["words"]), "boundary_crossings": 0, "all_intersections_retained": True}


def audit_baseline_lexical(reference: dict, baseline: dict) -> dict:
    if [word["text"] for word in reference["words"]] != [word["text"] for word in baseline["words"]]:
        raise ValueError("Repair changed failed-candidate Reazon lexical units")
    if [(block["id"], block["text"]) for block in reference["blocks"]] != [(block["id"], block["text"]) for block in baseline["blocks"]]:
        raise ValueError("Repair changed failed-candidate Reazon ASR blocks")
    retained = 0
    for current, previous in zip(reference["words"], baseline["words"]):
        if previous["start"] is not None and previous["end"] is not None:
            if (current["start"], current["end"]) != (previous["start"], previous["end"]):
                raise ValueError("Repair changed previously supported acoustic intervals")
            retained += 1
    return {"lexical_word_count": len(reference["words"]), "asr_block_count": len(reference["blocks"]), "previously_supported_intervals_unchanged": retained}


def audit_covering_alignment(reference: dict, source_sha256: str, evidence_loader=load) -> dict:
    if __package__:
        from .japanese_alignment import prediction_unit_index, raw_word_predictions
    else:
        from japanese_alignment import prediction_unit_index, raw_word_predictions
    evidence = {}
    counts = {"dedicated_surface_words": 0, "pronunciation_ctc_words": 0}
    for word in reference["words"]:
        status = word.get("timing_status")
        if status not in {"dedicated_forced_aligner_raw_surface_word", "ctc_forced_aligned_dictionary_pronunciation"}:
            continue
        path = word["alignment_prediction_path"]
        if path not in evidence:
            evidence[path] = evidence_loader(ROOT / path)
        record = evidence[path]
        recorded_source = record.get("source_audio_sha256", record.get("source_sha256"))
        if recorded_source != source_sha256 or record["model"] != word["alignment_model"] or record["revision"] != word["alignment_model_revision"]:
            raise ValueError("Covering alignment source/model provenance mismatch")
        duration = (record["source_end_sample_16k"] - record["source_start_sample_16k"]) / 16000
        if abs(record["acoustic_input_samples"] / 16000 - duration) > 1 / 16000 or record["timestamp_interpolation"]:
            raise ValueError("Covering alignment acoustic sample interval mismatch")
        if status == "dedicated_forced_aligner_raw_surface_word":
            if not record["accepted"]:
                raise ValueError("Rejected raw prediction used as final timing")
            predictions = raw_word_predictions(record["raw_predictions"], record["surface_words"], duration, set())
            counts["dedicated_surface_words"] += 1
        else:
            if len(record["ctc_pronunciation_character_frames"]) != len("".join(record["pronunciation_words"])):
                raise ValueError("Pronunciation alignment lacks complete acoustic character occupancy")
            predictions = record["predictions"]
            counts["pronunciation_ctc_words"] += 1
        offset = record["source_start_sample_16k"] / 16000 - reference["source_start"]
        prediction = predictions[prediction_unit_index(reference, word, record)]
        if prediction["text"] != word["text"] or abs(word["start"] - (offset + prediction["start"])) > 1 / 16000 or abs(word["end"] - (offset + prediction["end"])) > 1 / 16000:
            raise ValueError(f"Repaired word timing does not match its genuine acoustic prediction: source={reference.get('source_id')} word_id={word.get('id')} evidence={path}")
    return {**counts, "prediction_files_checked": len(evidence), "source_hash_matches": True, "raw_prediction_mapping_matches": True}


def check_artifacts() -> None:
    import numpy as np
    import soundfile as sf
    started = time.time()
    selection = load(LOCAL / "selection.json")
    checks = []
    inventory = []
    baseline_checks = []
    alignment_checks = []
    source_hashes = {}
    for index, chunk in enumerate(selection["chunks"]):
        for other in selection["chunks"][index + 1:]:
            if chunk["source_id"] == other["source_id"] and chunk["source_start"] < other["source_end"] and chunk["source_end"] > other["source_start"]:
                raise ValueError("Source overlap across selected cuts")
        path = ROOT / chunk["audio"]["path"]
        info = sf.info(path)
        if info.samplerate != 48000 or info.channels != 1 or abs(info.duration - (chunk["source_end"] - chunk["source_start"])) > 1 / 48000:
            raise ValueError(f"Audio format/duration mismatch: {chunk['id']}")
        if digest(path) != chunk["audio"]["sha256"]:
            raise ValueError(f"Audio checksum mismatch: {chunk['id']}")
        ref = load(LOCAL / "references" / f"{chunk['id']}.json")
        if ref["source_id"] not in source_hashes:
            source_hashes[ref["source_id"]] = digest(source_path(ref["source_id"]))
        alignment_checks.append({"asset": chunk["id"], **audit_covering_alignment(ref, source_hashes[ref["source_id"]])})
        baseline_path = LOCAL / "alignment-repair" / "baseline" / "references" / f"{chunk['id']}.json"
        if baseline_path.exists():
            baseline_checks.append({"asset": chunk["id"], **audit_baseline_lexical(ref, load(baseline_path))})
        if ref["audio_sha256"] != chunk["audio"]["sha256"]:
            raise ValueError("References belong to different audio")
        inventory.append(timing_inventory(chunk["id"], ref, info.duration))
        if chunk.get("source_reference_path"):
            producer = load(ROOT / chunk["source_reference_path"])
            inventory.append(timing_inventory(f"producer/{chunk['id']}", producer, producer["audio_duration_seconds"]))
            alignment_checks.append({"asset": f"producer/{chunk['id']}", **audit_covering_alignment(producer, source_hashes[ref["source_id"]])})
            producer_baseline = LOCAL / "alignment-repair" / "baseline" / "source-references" / f"{chunk['id']}.json"
            if producer_baseline.exists():
                baseline_checks.append({"asset": f"producer/{chunk['id']}", **audit_baseline_lexical(producer, load(producer_baseline))})
        for block in ref["blocks"]:
            recognized = "".join(word["text"] for word in ref["words"] if word["block"] == block["id"])
            if recognized != "".join(block["text"].split()):
                raise ValueError("Word segmentation rewrote ASR text")
        restored = "".join(sentence["text"][:-1] for sentence in ref["sentences"])
        if restored != "".join(word["text"] for word in ref["words"]):
            raise ValueError("Punctuation restoration rewrote words")
        checks.append({"chunk_id": chunk["id"], "audio_duration_seconds": info.duration, "word_count": len(ref["words"]), "aligned_word_count": sum(word["start"] is not None for word in ref["words"]), "audio_checksum_matches": True, "word_bounds_valid": True, "recognized_words_preserved": True})
    bundles = []
    for split in ("main", "dev"):
        mapping = load(LOCAL / "playback" / f"ja-{split}-mapping.json")
        path = LOCAL / "playback" / f"ja-{split}.wav"
        audio, rate = sf.read(path, dtype="float32")
        if rate != 48000 or audio.ndim != 1 or digest(path) != mapping["audio_sha256"]:
            raise ValueError("Playback checksum/format mismatch")
        previous = 0
        for index, entry in enumerate(mapping["mapping"]):
            start = round(entry["playback_start"] * rate)
            end = round(entry["playback_end"] * rate)
            if index and (start - previous != 2 * rate or np.any(audio[previous:start])):
                raise ValueError("Interchunk gap is not exactly 2s zero samples")
            original, _ = sf.read(LOCAL / "chunks" / f"{entry['chunk_id']}.wav", dtype="float32")
            if not np.array_equal(audio[start:end], original):
                raise ValueError("Assembly changed source chunk samples")
            previous = end
        if previous != len(audio):
            raise ValueError("Unmapped playback samples")
        combined = load(LOCAL / "playback" / f"ja-{split}-reference.json")
        if combined["audio_sha256"] != mapping["audio_sha256"]:
            raise ValueError("Playback references target different audio")
        inventory.append(timing_inventory(f"playback/{split}", combined, len(audio) / rate))
        for entry in mapping["mapping"]:
            local_ref = load(LOCAL / "references" / f"{entry['chunk_id']}.json")
            for kind in ("words", "sentences", "turns"):
                mapped = [item for item in combined[kind] if item["chunk_id"] == entry["chunk_id"]]
                if len(mapped) != len(local_ref[kind]):
                    raise ValueError("Playback timeline omitted units")
                for a, b in zip(mapped, local_ref[kind]):
                    for key in ("start", "end"):
                        if b[key] is not None and (abs(a[key] - b[key] - entry["playback_start"]) > 1e-8 or abs(a[f"source_{key}"] - b[key] - entry["source_start"]) > 1e-8):
                            raise ValueError("Source-to-playback time mismatch")
        expected_seconds = 1800 if split == "main" else 300
        if len(audio) != expected_seconds * rate:
            raise ValueError(f"{split} elapsed playback must be exactly {expected_seconds}s including separators")
        if split == "main":
            categories = {chunk["id"]: chunk["category"] for chunk in selection["chunks"]}
            stress_start = min(entry["playback_start"] for entry in mapping["mapping"] if categories[entry["chunk_id"]] == "stress")
            if round(stress_start * rate) != 1200 * rate:
                raise ValueError("General assigned-separator budget must end at exactly1200s")
            for category, seconds in (("general", 1188), ("stress", 596)):
                samples = sum(round(chunk["audio"]["duration_seconds"] * rate) for chunk in selection["chunks"] if chunk["split"] == "main" and chunk["category"] == category)
                if samples != seconds * rate:
                    raise ValueError(f"{category} source budget must be exactly {seconds}s")
        bundles.append({"split": split, "duration_seconds": len(audio) / rate, "sha256": mapping["audio_sha256"], "exact_sample_assembly": True, "source_to_playback_units_checked": True, "zero_gap_seconds": 2})
    heldout_index = load(LOCAL / "heldout" / "index.json")
    reserve_chunk = next(chunk for chunk in selection["chunks"] if chunk["split"] == "heldout_reserve")
    reserve = load(LOCAL / "references" / f"{reserve_chunk['id']}.json")
    heldout_audit = []
    for entry in heldout_index["entries"]:
        artifact = load(LOCAL / "heldout" / f"{entry['id']}.json")
        if digest(ROOT / entry["audio"]["path"]) != entry["audio"]["sha256"]:
            raise ValueError("Heldout checksum mismatch")
        if any(word["start"] < 0 or word["end"] > entry["audio"]["duration_seconds"] + 1 / 48000 for word in artifact["words"]):
            raise ValueError("Heldout word outside clip")
        inventory.append(timing_inventory(f"heldout/{entry['id']}", artifact, entry["audio"]["duration_seconds"]))
        heldout_audit.append(audit_isolated_reference(entry, artifact, reserve))
        for chunk in selection["chunks"]:
            if chunk["split"] != "heldout_reserve" and chunk["source_id"] == entry["source_id"] and chunk["source_start"] < entry["source_end"] and chunk["source_end"] > entry["source_start"]:
                raise ValueError("Heldout leaked into main or dev")
    environment = subprocess.run([str(LOCAL / "venv" / "Scripts" / "python.exe"), "-m", "pip", "freeze"], check=True, capture_output=True, text=True).stdout.splitlines()
    save(LOCAL / "environment.json", {"python": subprocess.run([str(LOCAL / "venv" / "Scripts" / "python.exe"), "--version"], check=True, capture_output=True, text=True).stdout.strip(), "packages": environment})
    result = {"rights": RIGHTS, "started_unix": started, "ended_unix": time.time(), "chunks": checks, "bundles": bundles, "heldout_count": heldout_index["prepared_count"], "heldout_source_disjoint": True, "heldout_intersection_audit": heldout_audit, "timing_inventory": inventory, "listening_performed": False, "limits": ["Checks establish data consistency, not human reference accuracy, semantic stress labels, actual conversation suitability, or release eligibility."]}
    result["failed_candidate_lexical_preservation"] = baseline_checks
    result["covering_alignment_audit"] = alignment_checks
    save(LOCAL / "checks.json", result)
    print(json.dumps(result), flush=True)

def main() -> None:
    parser = argparse.ArgumentParser(description="Local-only Japanese preparation. No upload/publication commands; unresolved speech remains in .data/japanese.")
    sub = parser.add_subparsers(dest="command", required=True)
    acquire_parser = sub.add_parser("acquire")
    acquire_parser.add_argument("--with-alignment", action="store_true")
    sub.add_parser("inspect")
    extract_parser = sub.add_parser("extract")
    extract_parser.add_argument("ids", nargs="+")
    sub.add_parser("select")
    render_parser = sub.add_parser("render")
    render_parser.add_argument("--only", nargs="+")
    ref_parser = sub.add_parser("reference")
    ref_parser.add_argument("--only", nargs="+")
    ref_parser.add_argument("--limit", type=float)
    ref_parser.add_argument("--threads", type=int, default=2)
    complete_parser = sub.add_parser("complete-alignment", description="Complete initial CTC-OOV times without replacement ASR. Default: reuse the existing Chinese Qwen environment/weights read-only. Fresh setup: create a Python3.12 CPU env under .data/japanese, install torch==2.14.1+cpu, qwen-asr==0.0.6 (transformers==4.57.6, accelerate==1.12.0), and download Qwen/Qwen3-ForcedAligner-0.6B at revision c7cbfc2048c462b0d63a45797104fc9db3ad62b7 into .data/japanese/models/covering-alignment; supply both overrides below. No runtime model/network downloads.")
    complete_parser.add_argument("--aligner-python", type=Path, default=ROOT / ".data" / "chinese" / "venv" / "Scripts" / "python.exe", help="CPU Qwen environment Python; fresh example .data/japanese/aligner-venv/Scripts/python.exe. qwen-asr==0.0.6 and its pinned dependencies are required.")
    complete_parser.add_argument("--pronunciation-python", type=Path, default=LOCAL / "venv" / "Scripts" / "python.exe", help="Japanese Reazon/CTC env with pyopenjtalk-plus==0.4.1.post9, SudachiPy==0.7.0, SudachiDict-core==20261015. Bundled dictionary only; unset OPEN_JTALK_DICT_DIR overrides. Nani prediction is explicitly disabled to reproduce the original optional-ONNX-unavailable behavior.")
    from japanese_alignment import DEFAULT_MODEL
    complete_parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL, help="Existing local pinned dedicated-aligner snapshot. Fresh example .data/japanese/models/covering-alignment; acquire with hf download Qwen/Qwen3-ForcedAligner-0.6B --revision c7cbfc2048c462b0d63a45797104fc9db3ad62b7 --local-dir .data/japanese/models/covering-alignment. This is only the dedicated model, never a full YODAS config.")
    complete_parser.add_argument("--threads", type=int, default=2)
    sub.add_parser("playback-references")
    sub.add_parser("heldout")
    sub.add_parser("export-metadata")
    sub.add_parser("check")
    args = parser.parse_args()
    if args.command == "acquire":
        acquire(args.with_alignment)
    elif args.command == "inspect":
        inspect()
    elif args.command == "extract":
        extract(set(args.ids))
    elif args.command == "select":
        select()
    elif args.command == "render":
        render(set(args.only) if args.only else None)
    elif args.command == "reference":
        if args.limit is not None and args.limit <= 0:
            parser.error("--limit must be positive")
        if args.threads < 1:
            parser.error("--threads must be positive")
        reference(set(args.only) if args.only else None, args.limit, args.threads)
    elif args.command == "complete-alignment":
        if args.threads < 1:
            parser.error("--threads must be positive")
        complete_alignment(args.aligner_python.resolve(), args.pronunciation_python.resolve(), args.model_dir.resolve(), args.threads)
    elif args.command == "playback-references":
        playback_references()
    elif args.command == "heldout":
        heldout()
    elif args.command == "export-metadata":
        export_metadata()
    elif args.command == "check":
        check_artifacts()


if __name__ == "__main__":
    main()
