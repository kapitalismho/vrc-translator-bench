from __future__ import annotations

import math


RATE = 48000


def merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged = []
    for start, end in sorted(ranges):
        if start > end:
            continue
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def safe_crop_choices(reference: dict, max_trim_samples: int) -> list[dict]:
    duration = round(reference["audio_duration_seconds"] * RATE)
    maximum = min(max_trim_samples, duration - 120 * RATE)
    if maximum < 0:
        raise ValueError("Main chunks must retain at least two minutes")
    guard = 0.02
    intervals = [(segment["start"], segment["end"]) for segment in reference.get("diarization_segments", reference["turns"])]
    intervals.extend((word["start"], word["end"]) for word in reference["words"] if word["start"] is not None)
    untimed_blocks = {word["block"] for word in reference["words"] if word["start"] is None}
    intervals.extend((block["start"], block["end"]) for block in reference["blocks"] if block["id"] in untimed_blocks)
    blocked = merge_ranges([(max(0, math.floor((start - guard) * RATE)), min(duration, math.ceil((end + guard) * RATE))) for start, end in intervals])
    gaps = []
    cursor = 0
    for start, end in blocked:
        if cursor < start:
            gaps.append((cursor, start - 1))
        cursor = max(cursor, end + 1)
    if cursor <= duration:
        gaps.append((cursor, duration))
    choices = [{"side": "none", "minimum": 0, "maximum": 0}]
    for side in ("right", "left"):
        allowed = []
        for start, end in gaps:
            if side == "right":
                minimum, maximum_here = max(1, duration - end), min(maximum, duration - start)
            else:
                minimum, maximum_here = max(1, start), min(maximum, end)
            if minimum <= maximum_here:
                allowed.append((minimum, maximum_here))
        choices.extend({"side": side, "minimum": start, "maximum": end} for start, end in merge_ranges(allowed))
    return choices


def choose_trim_plan(references: list[dict], total_trim_seconds: float) -> list[dict]:
    target = round(total_trim_seconds * RATE)
    if target < 0:
        raise ValueError("Cannot enlarge speech with a trimming budget")
    choices = [safe_crop_choices(reference, target) for reference in references]
    suffix = [[] for _ in range(len(references) + 1)]
    suffix[-1] = [(0, 0)]
    for index in range(len(references) - 1, -1, -1):
        reachable = []
        for choice in choices[index]:
            for start, end in suffix[index + 1]:
                a, b = choice["minimum"] + start, min(target, choice["maximum"] + end)
                if a <= b:
                    reachable.append((a, b))
        suffix[index] = merge_ranges(reachable)
    if not any(start <= target <= end for start, end in suffix[0]):
        raise ValueError("Exact elapsed budget cannot be met at estimated silence boundaries without cutting aligned words/voice or an untimed block")
    remaining = target
    plan = []
    for index, reference in enumerate(references):
        preferred = round(remaining / (len(references) - index))
        candidates = []
        for choice in choices[index]:
            for start, end in suffix[index + 1]:
                minimum = max(choice["minimum"], remaining - end)
                maximum = min(choice["maximum"], remaining - start)
                if minimum <= maximum:
                    amount = min(maximum, max(minimum, preferred))
                    candidates.append((abs(amount - preferred), choice["side"] == "left", amount, choice["side"]))
        if not candidates:
            raise ValueError("Internal exact-budget reconstruction failure")
        _, _, amount, side = min(candidates)
        duration = round(reference["audio_duration_seconds"] * RATE)
        left = amount if side == "left" else 0
        right = duration - amount if side == "right" else duration
        plan.append({"side": side, "trim_samples": amount, "trim_seconds": amount / RATE, "start_sample": left, "end_sample": right, "duration_samples": right - left})
        remaining -= amount
    if remaining:
        raise ValueError("Exact playback budget has an unassigned remainder")
    return plan


def crop_units(reference: dict, start_sample: int, end_sample: int) -> dict:
    left, right = start_sample / RATE, end_sample / RATE
    if not 0 <= left < right <= reference["audio_duration_seconds"] + 1e-9:
        raise ValueError("Invalid reference crop")
    blocks_by_id = {block["id"]: block for block in reference["blocks"]}
    words = []
    character_cursors = {}
    for word in reference["words"]:
        block = blocks_by_id[word["block"]]
        if word["start"] is None:
            if block["end"] <= left or block["start"] >= right:
                continue
            if block["start"] < left - 1e-9 or block["end"] > right + 1e-9:
                raise ValueError("Crop would partially retain an untimed ASR block")
            a = b = None
        else:
            if word["end"] <= left or word["start"] >= right:
                continue
            if word["start"] < left - 1e-9 or word["end"] > right + 1e-9:
                raise ValueError("Crop would cut an aligned word")
            a, b = word["start"] - left, word["end"] - left
        cursor = character_cursors.get(word["block"], 0)
        words.append({**word, "origin_word_id": word["id"], "id": len(words), "origin_char_start": word["char_start"], "origin_char_end": word["char_end"], "char_start": cursor, "char_end": cursor + len(word["text"]), "start": a, "end": b})
        character_cursors[word["block"]] = cursor + len(word["text"])
    blocks = []
    for block in reference["blocks"]:
        if block["end"] <= left or block["start"] >= right:
            continue
        blocks.append({"id": block["id"], "start": max(left, block["start"]) - left, "end": min(right, block["end"]) - left, "text": "".join(word["text"] for word in words if word["block"] == block["id"]), "alignment_status": block["alignment_status"], "source_reference_block_id": block["id"], "inference_reused": True})
    segments = []
    for segment in reference.get("diarization_segments", reference["turns"]):
        start, end = max(left, segment["start"]), min(right, segment["end"])
        if start < end:
            segments.append({**segment, "start": start - left, "end": end - left})
    return {"words": words, "blocks": blocks, "diarization_segments": segments}
