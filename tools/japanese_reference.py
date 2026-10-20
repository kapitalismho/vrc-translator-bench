from __future__ import annotations

import json
import math
import subprocess
import time
from pathlib import Path


def ctc_align(log_probs, targets: list[int], blank: int = 0) -> list[dict]:
    import numpy as np
    if not targets:
        return []
    if any(token == blank for token in targets):
        raise ValueError("Blank is not a transcript token")
    frames, _ = log_probs.shape
    minimum = len(targets) + sum(a == b for a, b in zip(targets, targets[1:]))
    if frames < minimum:
        raise ValueError("Not enough acoustic frames for transcript")
    states = np.full(2 * len(targets) + 1, blank, dtype=np.int32)
    states[1::2] = targets
    can_skip = np.zeros(len(states), dtype=bool)
    can_skip[3::2] = states[3::2] != states[1:-2:2]
    previous = np.full(len(states), -np.inf)
    previous[0] = log_probs[0, blank]
    previous[1] = log_probs[0, targets[0]]
    trace = np.zeros((frames, len(states)), dtype=np.uint8)
    for frame in range(1, frames):
        advance = np.concatenate(([-np.inf], previous[:-1]))
        skip = np.concatenate(([-np.inf, -np.inf], previous[:-2]))
        skip[~can_skip] = -np.inf
        choices = np.stack((previous, advance, skip))
        trace[frame] = choices.argmax(axis=0)
        previous = choices.max(axis=0) + log_probs[frame, states]
    state = len(states) - 1 if previous[-1] >= previous[-2] else len(states) - 2
    if not np.isfinite(previous[state]):
        raise ValueError("No complete CTC alignment path")
    path = np.empty(frames, dtype=np.int32)
    for frame in range(frames - 1, -1, -1):
        path[frame] = state
        state -= int(trace[frame, state])
    aligned = []
    for index, token in enumerate(targets):
        hits = np.flatnonzero(path == 2 * index + 1)
        if not len(hits):
            raise ValueError("CTC path omitted a transcript token")
        aligned.append({"start_frame": int(hits[0]), "end_frame": int(hits[-1] + 1), "mean_probability": float(np.exp(log_probs[hits, token]).mean())})
    return aligned


def align_characters(log_probs, text: str, vocab: dict) -> tuple[list[dict], set[int]]:
    import numpy as np
    wildcard = log_probs.shape[1]
    unsupported = {index for index, char in enumerate(text) if char not in vocab and char != " "}
    targets = [vocab["|"] if char == " " else vocab.get(char, wildcard) for char in text]
    if unsupported:
        wildcard_scores = log_probs[:, 1:].max(axis=1, keepdims=True)
        log_probs = np.concatenate((log_probs, wildcard_scores), axis=1)
    return ctc_align(log_probs, targets), unsupported


def lexical_words(text: str, tagger) -> list[dict]:
    words = []
    cursor = 0
    for token in tagger(text):
        start = text.find(token.surface, cursor)
        if start < 0 or text[cursor:start].strip():
            raise ValueError("Lexical tokenizer changed recognized text")
        words.append({"text": token.surface, "char_start": start, "char_end": start + len(token.surface)})
        cursor = start + len(token.surface)
    if text[cursor:].strip():
        raise ValueError("Lexical tokenizer dropped recognized text")
    return words


def punctuate(words: list[dict]) -> list[dict]:
    sentences = []
    current = []
    for index, word in enumerate(words):
        current.append(word)
        following = words[index + 1] if index + 1 < len(words) else None
        gap = following["start"] - word["end"] if following and following["start"] is not None and word["end"] is not None else 0
        if following is None or gap >= 0.6 or following["speaker"] != word["speaker"] or following["block"] != word["block"]:
            sentences.append({"text": "".join(item["text"] for item in current) + "。", "start": current[0]["start"], "end": current[-1]["end"], "speaker": current[0]["speaker"], "punctuation": "automatic_acoustic_heuristic_not_syntax_verified", "word_ids": [item["id"] for item in current]})
            current = []
    return sentences


def speaker_at(start: float, end: float, turns: list[dict]) -> tuple[str, bool]:
    totals = {}
    for turn in turns:
        overlap = max(0.0, min(end, turn["end"]) - max(start, turn["start"]))
        if overlap:
            totals[turn["speaker"]] = totals.get(turn["speaker"], 0.0) + overlap
    if not totals:
        return "unknown", False
    return max(totals, key=totals.get), len(totals) > 1


def merge_speaker_turns(segments: list[dict]) -> list[dict]:
    turns = []
    for segment in segments:
        if turns and turns[-1]["speaker"] == segment["speaker"]:
            turns[-1]["end"] = max(turns[-1]["end"], segment["end"])
        else:
            turns.append(dict(segment))
    return turns


def acoustic_stats(words: list[dict], turns: list[dict], speech_segments: list[dict]) -> dict:
    aligned = [word for word in words if word["start"] is not None]
    gaps = [b["start"] - a["end"] for a, b in zip(aligned, aligned[1:]) if a["speaker"] == b["speaker"] and a["block"] == b["block"]]
    fast_changes = sum(0 <= b["start"] - a["end"] <= 0.3 and a["speaker"] != b["speaker"] for a, b in zip(turns, turns[1:]))
    overlap = 0.0
    for index, a in enumerate(speech_segments):
        for b in speech_segments[index + 1:]:
            if b["start"] >= a["end"]:
                break
            if a["speaker"] != b["speaker"]:
                overlap += max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
    return {
        "estimated_speakers": len({turn["speaker"] for turn in turns}),
        "estimated_turns": len(turns), "estimated_fast_speaker_changes_le_300ms": fast_changes,
        "estimated_pairwise_overlap_seconds": round(overlap, 3),
        "overlap_basis": "Raw estimated speech-segment intersections, excluding silence inside coalesced turn spans.",
        "speaker_count_basis": "Anonymous acoustic cluster count, not verified participants; substantial over-/under-clustering remains possible.",
        "aligned_same_speaker_word_gap_ge_300ms": sum(gap >= 0.3 for gap in gaps),
        "short_estimated_turns_le_1s": sum(turn["end"] - turn["start"] <= 1 for turn in turns),
        "lexical_filler_candidates": sum(word["text"] in {"えー", "ええ", "あの", "えっと", "うん", "はい"} for word in words),
        "confirmed_mid_sentence_pauses": None, "confirmed_pre_predicate_pauses": None,
        "confirmed_backchannels": None, "confirmed_trailing_fillers": None,
        "confirmed_continuing_across_sentences": None,
        "interpretation": "Acoustic/lexical proxies only, not human stress labels. CTC blank gaps can include silence or uncertain alignment; pairwise overlap is model-estimated, not verified.",
    }


class ReferenceEngine:
    def __init__(self, model_root: Path, threads: int = 2):
        import fugashi
        import sherpa_onnx
        import torch
        from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
        torch.set_num_threads(threads)
        self.torch = torch
        self.tagger = fugashi.Tagger()
        base = model_root / "reazon"
        self.asr = sherpa_onnx.OfflineRecognizer.from_transducer(
            tokens=str(base / "tokens.txt"), encoder=str(base / "encoder-epoch-99-avg-1.int8.onnx"),
            decoder=str(base / "decoder-epoch-99-avg-1.onnx"), joiner=str(base / "joiner-epoch-99-avg-1.int8.onnx"),
            num_threads=threads, sample_rate=16000, feature_dim=80, decoding_method="modified_beam_search", max_active_paths=4, provider="cpu",
        )
        config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(model_root / "segmentation" / "model.int8.onnx")), num_threads=threads, provider="cpu",
            ),
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(model_root / "embedding.onnx"), num_threads=threads, provider="cpu"),
            clustering=sherpa_onnx.FastClusteringConfig(num_clusters=-1, threshold=0.75), min_duration_on=0.3, min_duration_off=0.5,
        )
        if not config.validate():
            raise ValueError("Invalid CPU diarization configuration")
        self.diarization = sherpa_onnx.OfflineSpeakerDiarization(config)
        align = model_root / "alignment"
        self.processor = Wav2Vec2Processor.from_pretrained(align, local_files_only=True)
        self.model = Wav2Vec2ForCTC.from_pretrained(align, local_files_only=True, use_safetensors=False).eval()
        self.vocab = self.processor.tokenizer.get_vocab()

    def run(self, path: Path, duration_limit: float | None = None) -> dict:
        import numpy as np
        started = time.time()
        command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(path)]
        if duration_limit is not None:
            command.extend(["-t", str(duration_limit)])
        command.extend(["-ar", "16000", "-ac", "1", "-f", "f32le", "pipe:1"])
        audio = np.frombuffer(subprocess.run(command, check=True, capture_output=True).stdout, dtype="<f4").copy()
        diarization_started = time.time()
        segments = self.diarization.process(audio).sort_by_start_time()
        turns = [{"start": float(seg.start), "end": float(seg.end), "speaker": f"speaker_{seg.speaker:02}", "status": "estimated_anonymous_chunk_local"} for seg in segments]
        diarization_seconds = time.time() - diarization_started
        blocks = []
        words = []
        cursor = 0
        while cursor < len(audio):
            end = min(len(audio), cursor + 8 * 16000)
            if end < len(audio):
                candidates = np.arange(cursor + 6 * 16000, end, 1600)
                energies = [float(np.mean(audio[p:p + 1600] ** 2)) for p in candidates]
                end = int(candidates[int(np.argmin(energies))]) + 800
            clip = audio[cursor:end]
            offset = cursor / 16000
            padded = np.pad(clip, (14400, 14400))
            stream = self.asr.create_stream()
            stream.accept_waveform(16000, padded)
            self.asr.decode_stream(stream)
            text = stream.result.text
            block_id = len(blocks)
            block = {"id": block_id, "start": offset, "end": end / 16000, "text": text, "asr_tokens": list(stream.result.tokens), "asr_token_points": [offset + float(t) - 0.9 for t in stream.result.timestamps], "asr_token_points_are_not_word_intervals": True}
            lexical = lexical_words(text, self.tagger)
            unsupported = {index for index, char in enumerate(text) if char not in self.vocab and char != " "}
            char_times = None
            if text:
                inputs = self.processor(clip, sampling_rate=16000, return_tensors="pt", padding=False)
                with self.torch.inference_mode():
                    logits = self.model(inputs.input_values, attention_mask=inputs.get("attention_mask")).logits[0]
                    probabilities = self.torch.log_softmax(logits, dim=-1).numpy()
                block["alignment_model_greedy_diagnostic"] = self.processor.decode(logits.argmax(dim=-1))
                aligned, unsupported = align_characters(probabilities, text, self.vocab)
                char_times = []
                stride = math.prod(self.model.config.conv_stride) / 16000
                receptive = 1
                jump = 1
                for kernel, conv_stride in zip(self.model.config.conv_kernel, self.model.config.conv_stride):
                    receptive += (kernel - 1) * jump
                    jump *= conv_stride
                half_receptive = receptive / 16000 / 2
                for item in aligned:
                    char_times.append({"start": offset + max(0.0, item["start_frame"] * stride + half_receptive - stride / 2), "end": offset + min(len(clip) / 16000, (item["end_frame"] - 1) * stride + half_receptive + stride / 2), "score": item["mean_probability"]})
                block["alignment_status"] = "ctc_viterbi_with_unsupported_wildcards" if unsupported else "ctc_viterbi_complete"
                block["unsupported_characters"] = sorted({text[index] for index in unsupported})
            else:
                block["alignment_status"] = "no_asr_text"
            for item in lexical:
                word_unsupported = any(index in unsupported for index in range(item["char_start"], item["char_end"]))
                if char_times is None or word_unsupported:
                    start_time = end_time = score = None
                    speaker, uncertain = "unknown", True
                else:
                    first = char_times[item["char_start"]]
                    last = char_times[item["char_end"] - 1]
                    start_time, end_time = first["start"], last["end"]
                    score = float(np.mean([char["score"] for char in char_times[item["char_start"]:item["char_end"]]]))
                    speaker, uncertain = speaker_at(start_time, end_time, turns)
                words.append({**item, "id": len(words), "block": block_id, "start": start_time, "end": end_time, "alignment_mean_character_probability": score, "speaker": speaker, "speaker_ambiguous": uncertain, "timing_status": "unavailable_unsupported_characters" if word_unsupported else block["alignment_status"]})
            blocks.append(block)
            print(json.dumps({"reference_audio": path.name, "block": block_id, "through_seconds": round(end / 16000, 3), "recognized_characters": len(text), "alignment_status": block["alignment_status"]}), flush=True)
            cursor = end
        return {
            "reference_level": "automatic_exploratory_not_human_validated",
            "audio_duration_seconds": len(audio) / 16000,
            "asr_decoding": "modified_beam_search, max_active_paths=4",
            "models": {"asr": "reazon-research/reazonspeech-k2-v2", "alignment": "jonatasgrosman/wav2vec2-large-xlsr-53-japanese", "speakers": "pyannote-segmentation-3.0 int8 + 3D-Speaker ERes2Net embeddings, threshold=0.75, min_on=0.3s/min_off=0.5s, unknown cluster count", "word_segmentation": "fugashi + unidic-lite"},
            "timing_method": "CTC constrained Viterbi path over independent Japanese Wav2Vec2 acoustic frames; lexical word spans are min/max aligned character occupancy. 20ms stride and convolution receptive-field centers; blanks excluded at word edges. OOV character targets use max-nonblank acoustic wildcard scores to preserve surrounding constraints; words containing OOV characters keep null times. Remaining supported words retain alignment uncertainty; no token-point interpolation.",
            "asr_windowing": "6-8s contiguous windows, boundary at lowest 100ms RMS in last 2s, no source samples dropped; official Reazon 0.9s leading/trailing inference padding. Subtract 0.9s from diagnostic token points, which may still lie outside actual audio and are not word times. Window-edge recognition errors remain possible.",
            "speaker_label_scope": "Within this chunk only; labels do not establish cross-chunk identity. Dominant overlapping estimated turn assigned to each aligned word; multiple overlapping speakers marked ambiguous.",
            "punctuation_method": "Only insert 。 at acoustic gap >=600ms, estimated speaker change, ASR block end or final word. Recognized lexical content is never rewritten. These are exploratory acoustic sentence-like units, not verified linguistic sentence boundaries.",
            "listening_performed": False, "blocks": blocks, "words": words, "sentences": punctuate(words), "turns": turns,
            "stats": acoustic_stats(words, turns, turns),
            "runtime": {"started_unix": started, "ended_unix": time.time(), "elapsed_seconds": round(time.time() - started, 3), "diarization_seconds": round(diarization_seconds, 3), "device": "cpu"},
        }
