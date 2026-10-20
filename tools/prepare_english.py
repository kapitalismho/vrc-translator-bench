from __future__ import annotations

import argparse
from array import array
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import urllib.request
import wave
import xml.etree.ElementTree as ET
import zipfile

RATE = 48000
NITE = "{http://nite.sourceforge.net/}"
ANNOTATIONS = "https://groups.inf.ed.ac.uk/ami/AMICorpusAnnotations/ami_public_manual_1.6.2.zip"
ANNOTATION_SHA256 = "b56e5babb2496b8795deeeda7e71178d7fbc9963f94276cf2a3f4b56ebbc9f9d"
BASE = "https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus"
ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def acquire(url, path, expected=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix(path.suffix + ".partial")
        print(f"Downloading {url}", flush=True)
        with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as out:
            shutil.copyfileobj(response, out)
        temporary.replace(path)
    digest = sha256(path)
    if expected is not None and digest != expected:
        raise ValueError(f"Checksum mismatch: {path}; remove the damaged local file before retrying")
    return digest


def tick(seconds):
    return round(float(seconds) * RATE)


def merged(intervals):
    result = []
    for a, b in sorted(intervals):
        if b <= a:
            continue
        if result and a <= result[-1][1]:
            result[-1][1] = max(result[-1][1], b)
        else:
            result.append([a, b])
    return result


def overlap(a, b, intervals):
    return sum(max(0, min(b, y) - max(a, x)) for x, y in merged(intervals))


def make_mapping(start, end, target_events, other_words, threshold=8 * RATE, keep=3 * RATE):
    events = merged((max(start, a), min(end, b)) for a, b in target_events)
    others = merged(other_words)
    removals = []
    for (_, left), (right, _) in zip(events, events[1:]):
        if right - left > threshold and overlap(left, right, others) >= RATE:
            removals.append([left + keep // 2, right - (keep - keep // 2)])
    retained = []
    cursor, playback = start, 0
    for a, b in removals + [[end, end]]:
        if a > cursor:
            retained.append({"source_start": cursor, "source_end": a, "playback_start": playback,
                             "playback_end": playback + a - cursor})
            playback += a - cursor
        cursor = b
    return retained, [{"source_start": a, "source_end": b,
                       "reason": "long_target_gap_occupied_by_other_speakers"} for a, b in removals]


def map_interval(start, end, mapping):
    result = []
    for span in mapping:
        a, b = max(start, span["source_start"]), min(end, span["source_end"])
        if a < b or (start == end and span["source_start"] <= start <= span["source_end"]):
            result.append([span["playback_start"] + a - span["source_start"],
                           span["playback_start"] + b - span["source_start"]])
            if start == end:
                break
    return result


def trim_mapping(mapping, budget, target_events):
    if not mapping or mapping[-1]["playback_end"] < budget:
        return None
    cutoff = budget
    protected = [part for a, b in target_events for part in map_interval(a, b, mapping)]
    while True:
        boundary = min((a for a, b in protected if a < cutoff < b), default=cutoff)
        if boundary == cutoff:
            break
        cutoff = boundary
    if budget - cutoff > 2 * RATE:
        return None
    retained = []
    for span in mapping:
        if span["playback_start"] >= cutoff:
            break
        count = min(span["playback_end"], cutoff) - span["playback_start"]
        retained.append({**span, "source_end": span["source_start"] + count,
                         "playback_end": span["playback_start"] + count})
    return retained, budget - cutoff


def referenced_ids(element, streams):
    result = []
    for child in element.findall(f"{NITE}child"):
        href = child.get("href", "")
        filename, fragment = href.split("#", 1)
        agent = filename.split(".")[-3]
        ids = re.findall(r"id\(([^)]+)\)", fragment)
        ordered = streams[agent]
        lookup = {w["id"]: i for i, w in enumerate(ordered)}
        lo, hi = lookup[ids[0]], lookup[ids[-1]]
        result.extend(ordered[lo:hi + 1])
    return result


def load_corpus(archive):
    corpus = {}
    with zipfile.ZipFile(archive) as z:
        resource = ET.fromstring(z.read("corpusResources/meetings.xml"))
        for meeting in resource:
            if meeting.get("type") != "scenario" or meeting.get("visibility") != "unseen":
                continue
            session = meeting.get("observation")
            streams, acts, invalid = {}, [], []
            speakers = {s.get("nxt_agent"): dict(s.attrib) for s in meeting}
            for agent in sorted(speakers):
                events = []
                for node in ET.fromstring(z.read(f"words/{session}.{agent}.words.xml")):
                    a, b = float(node.get("starttime", "nan")), float(node.get("endtime", "nan"))
                    valid = math.isfinite(a) and math.isfinite(b) and 0 <= a <= b
                    if not valid:
                        invalid.append({"id": node.get(NITE + "id"), "kind": node.tag,
                                        "raw_start": node.get("starttime"), "raw_end": node.get("endtime"),
                                        "bounded": math.isfinite(a) and math.isfinite(b),
                                        "source_start": tick(min(a, b)) if math.isfinite(a) and math.isfinite(b) else 0,
                                        "source_end": tick(max(a, b)) if math.isfinite(a) and math.isfinite(b) else 0})
                    events.append({"id": node.get(NITE + "id"), "speaker": agent, "timing_valid": valid,
                                   "source_start": tick(min(a, b)) if math.isfinite(a) and math.isfinite(b) else 0,
                                   "source_end": tick(max(a, b)) if math.isfinite(a) and math.isfinite(b) else 0,
                                   "text": node.text or "", "kind": node.tag,
                                   "punctuation": node.get("punc") == "true",
                                   "truncated": node.get("trunc") == "true",
                                   "sound_type": node.get("type")})
                streams[agent] = events
            if any(e["kind"] == "w" or not e["bounded"] for e in invalid):
                corpus[session] = {"excluded": "unbounded event or invalid lexical word times", "invalid_events": invalid}
                continue
            for agent in sorted(speakers):
                for node in ET.fromstring(z.read(f"dialogueActs/{session}.{agent}.dialog-act.xml")):
                    words = referenced_ids(node, streams)
                    lexical = [w for w in words if w["kind"] == "w" and not w["punctuation"]]
                    if not lexical:
                        continue
                    pointer = node.find(f"{NITE}pointer[@role='da-aspect']")
                    dtype = re.search(r"id\(([^)]+)\)", pointer.get("href")).group(1) if pointer is not None else None
                    act = {"id": node.get(NITE + "id"), "speaker": agent, "type": dtype,
                           "word_ids": [w["id"] for w in words],
                           "source_start": min(w["source_start"] for w in lexical),
                           "source_end": max(w["source_end"] for w in lexical)}
                    acts.append(act)
                    for word in words:
                        word["dialogue_act"] = act["id"]
            topics, chat = [], []
            for node in ET.fromstring(z.read(f"topics/{session}.topic.xml")).iter("topic"):
                words = referenced_ids(node, streams)
                if not words:
                    continue
                pointers = [p.get("href") for p in node.findall(f"{NITE}pointer")]
                record = {"id": node.get(NITE + "id"), "types": pointers,
                          "other_description": node.get("other_description"),
                          "source_start": min(w["source_start"] for w in words),
                          "source_end": max(w["source_end"] for w in words)}
                topics.append(record)
                if any("id(top.14)" in p for p in pointers):
                    chat.append([record["source_start"], record["source_end"]])
            corpus[session] = {"speakers": speakers, "streams": streams, "acts": acts,
                               "topics": topics, "chat": chat, "invalid_events": invalid,
                               "end": max(w["source_end"] for ws in streams.values() for w in ws)}
        expected = {prefix + suffix for prefix in ("ES2004", "ES2014", "IS1009", "TS3003", "TS3007") for suffix in "abcd"}
        if set(corpus) != expected:
            raise ValueError("Archive does not match the declared official scenario-only SC partition")
    return corpus


def lexical_words(data, agent):
    return [w for w in data["streams"][agent] if w["kind"] == "w" and not w["punctuation"]]


def stress_events(data, agent):
    events = []
    stream = data["streams"][agent]
    words = lexical_words(data, agent)
    by_id = {w["id"]: w for w in stream}
    for left, right in zip(words, words[1:]):
        gap = right["source_start"] - left["source_end"]
        between = [w for w in stream if left["source_end"] <= w["source_start"] <= right["source_start"] and w["punctuation"]]
        terminal = any(w["text"] in {".", "?", "!"} for w in between)
        if gap >= tick(.3) and left.get("dialogue_act") is not None and left.get("dialogue_act") == right.get("dialogue_act") and not terminal:
            events.append({"type": "internal_pause", "source_start": left["source_end"],
                           "source_end": right["source_start"], "word_ids": [left["id"], right["id"]],
                           "confidence": "alignment_candidate_not_listened"})
        if 0 <= gap <= tick(.3) and terminal:
            events.append({"type": "cross_sentence_continuation", "source_start": left["source_end"],
                           "source_end": right["source_start"], "word_ids": [left["id"], right["id"]],
                           "confidence": "punctuation_timing_heuristic_not_listened"})
    for act in data["acts"]:
        if act["speaker"] != agent:
            continue
        ws = [by_id[i] for i in act["word_ids"] if i in by_id and by_id[i]["kind"] == "w" and not by_id[i]["punctuation"]]
        if not ws:
            continue
        for kind in (["backchannel"] if act["type"] == "ami_da_1" else []) + (["trailing_filler"] if ws[-1]["text"].lower().strip(".,?!") in {"uh", "um", "er", "erm", "hmm", "mm"} else []):
            events.append({"type": kind, "source_start": act["source_start"], "source_end": act["source_end"],
                           "dialogue_act": act["id"], "confidence": "manual_dialogue_act" if kind == "backchannel" else "lexical_heuristic_not_listened"})
    return events


def candidate(data, session, agent, start, seconds):
    events = [(w["source_start"], w["source_end"]) for w in data["streams"][agent] if w["kind"] in {"w", "vocalsound", "nonword"} and not w["punctuation"]]
    if any(a < start < b for a, b in events):
        return None
    others = [(w["source_start"], w["source_end"]) for a in data["streams"] if a != agent for w in lexical_words(data, a)]
    mapping, removed = make_mapping(start, data["end"], events, others)
    trimmed = trim_mapping(mapping, tick(seconds), events)
    if trimmed is None:
        return None
    mapping, padding = trimmed
    end = mapping[-1]["source_end"]
    if any(start < e["source_end"] and e["source_start"] < end for e in data.get("invalid_events", [])):
        return None
    words = [w for w in lexical_words(data, agent) if start <= w["source_start"] and w["source_end"] <= end]
    if len(words) < 80 or any(w.get("dialogue_act") is None for w in words):
        return None
    speaker = data["speakers"][agent]
    return {"session": session, "speaker": agent, "channel": int(speaker["channel"]),
            "global_speaker": speaker["global_name"], "source_start": start, "source_end": end,
            "frames": tick(seconds), "mapping": mapping, "padding_frames": padding,
            "removed": [r for r in removed if start <= r["source_start"] < r["source_end"] <= end],
            "source_url": f"{BASE}/{session}/audio/{session}.Headset-{speaker['channel']}.wav"}


def plan(root, data_root):
    policy_path = root / "corpus/english/selection-policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    seed = policy["seed"]
    archive = data_root / "downloads/ami_public_manual_1.6.2.zip"
    acquire(ANNOTATIONS, archive, ANNOTATION_SHA256)
    corpus = load_corpus(archive)
    usable = sorted(s for s, d in corpus.items() if "excluded" not in d and s != "ES2004d")
    rng = random.Random(seed)
    rng.shuffle(usable)
    reserved = {"TS3007a"}
    used, chunks = set(reserved), []
    stress_cache = {}
    def choose(category, agent, seconds, index):
        sessions = [s for s in usable if s not in used]
        if category == "general" and any(corpus[s]["chat"] for s in sessions):
            sessions.sort(key=lambda s: not bool(corpus[s]["chat"]))
        choices = []
        for session in sessions:
            data = corpus[session]
            starts = sorted({max(0, a["source_start"] - tick(.25)) for a in data["acts"] if a["speaker"] == agent})
            rng.shuffle(starts)
            starts = starts[:80] if not data["chat"] else starts
            stress_cache[(session, agent)] = stress_events(data, agent)
            for start in starts:
                item = candidate(data, session, agent, start, seconds)
                if item is None:
                    continue
                chat_frames = sum(y - x for a, b in data["chat"] for x, y in map_interval(max(a, item["source_start"]), min(b, item["source_end"]), item["mapping"]) if max(a, item["source_start"]) <= min(b, item["source_end"]))
                events = [e for e in stress_cache[(session, agent)] if start <= e["source_start"] <= e["source_end"] <= item["source_end"]]
                item.update({"id": f"{category}-{index:02d}", "category": category,
                             "directions": ["D1", "D2"], "input_mode": "selected_headset",
                             "stress_candidate_counts": dict(Counter(e["type"] for e in events)),
                             "casual_chat_playback_frames": chat_frames})
                if category != "stress" and not data["chat"]:
                    choices.append((0, item))
                    break
                score = len(events) if category == "stress" else chat_frames
                choices.append((score, item))
            if choices and category != "stress" and (not data["chat"] or max(c[0] for c in choices) > 0):
                break
        if not choices:
            raise ValueError(f"No eligible real {category} candidate for {agent}")
        item = max(choices, key=lambda x: x[0])[1] if category == "stress" or max(c[0] for c in choices) else choices[0][1]
        used.add(item["session"])
        chunks.append(item)
    for i, agent in enumerate("ABCD", 1):
        choose("general", agent, 298, i)
    for i, agent in enumerate("AB", 1):
        choose("stress", agent, 299, i)
    for i, agent in enumerate("CD", 1):
        choose("development", agent, 149, i)
    isolated = []
    session = "TS3007a"
    data = corpus[session]
    buckets = {"short": [], "long": [], "internally_paused": []}
    isolated_stress = {agent: stress_events(data, agent) for agent in data["streams"]}
    for act in data["acts"]:
        if any(act["source_start"] < e["source_end"] and e["source_start"] < act["source_end"] for e in data.get("invalid_events", [])):
            continue
        duration = act["source_end"] - act["source_start"]
        if duration <= tick(2):
            buckets["short"].append(act)
        if duration >= tick(8):
            buckets["long"].append(act)
        if any(e["type"] == "internal_pause" and act["source_start"] <= e["source_start"] < e["source_end"] <= act["source_end"] for e in isolated_stress[act["speaker"]]):
            buckets["internally_paused"].append(act)
    chosen = set()
    for bucket, count in (("short", 7), ("long", 6), ("internally_paused", 7)):
        rng.shuffle(buckets[bucket])
        selected = [a for a in buckets[bucket] if a["id"] not in chosen][:count]
        if len(selected) != count:
            raise ValueError(f"Insufficient real isolated utterances: {bucket}")
        for act in selected:
            chosen.add(act["id"])
            agent = act["speaker"]
            start, end = act["source_start"], act["source_end"]
            speaker = data["speakers"][agent]
            isolated.append({"id": f"isolated-{len(isolated) + 1:02d}", "category": "isolated",
                             "selection_bucket": bucket, "directions": ["D1"], "session": session,
                             "input_mode": "selected_headset",
                             "speaker": agent, "channel": int(speaker["channel"]), "global_speaker": speaker["global_name"],
                             "dialogue_act": act["id"], "source_start": start, "source_end": end,
                             "frames": end - start, "padding_frames": 0, "removed": [],
                             "mapping": [{"source_start": start, "source_end": end, "playback_start": 0, "playback_end": end - start}],
                             "source_url": f"{BASE}/{session}/audio/{session}.Headset-{speaker['channel']}.wav"})
    result = {"schema_version": 1, "seed": seed, "policy_sha256": sha256(policy_path),
              "annotations": {"url": ANNOTATIONS, "sha256": ANNOTATION_SHA256,
                              "filename": archive.name, "internal_readme_release": "1.7, 16 June 2014"},
              "partition": policy["partition"], "excluded_sessions": {s: d.get("excluded") for s, d in corpus.items() if "excluded" in d} | {"ES2004d": "documented audio dropouts; excluded conservatively"},
              "chunks": chunks, "isolated": isolated,
              "scope_note": "English local data only. Development is locally held-out official test material, NOT official AMI dev. Held-out at session rather than global-speaker identity level."}
    save(root / "corpus/english/selection.json", result)
    print(json.dumps({"chunks": [(c["id"], c["session"], c["speaker"], c["source_start"] / RATE, c["source_end"] / RATE) for c in chunks], "isolated": len(isolated)}, indent=2))


def render_pcm(source, item):
    spans = []
    for span in item["mapping"]:
        length = span["source_end"] - span["source_start"]
        command = ["ffmpeg", "-v", "error", "-i", str(source), "-af",
                   f"aresample={RATE},atrim=start_sample={span['source_start']}:end_sample={span['source_end']},asetpts=PTS-STARTPTS",
                   "-ac", "1", "-ar", str(RATE), "-f", "s16le", "pipe:1"]
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if len(result.stdout) != length * 2:
            raise ValueError(f"Source ends before selected interval: {source}; expected {length}, decoded {len(result.stdout) // 2}")
        spans.append(result.stdout)
    samples = array("h")
    samples.frombytes(b"".join(spans))
    if sys.byteorder != "little":
        samples.byteswap()
    peak = max((abs(x) for x in samples), default=0)
    if peak == 0:
        raise ValueError(f"Selected clip contains only zero samples: {item['id']}")
    gain = (32767 * 10 ** (-3 / 20)) / peak
    normalized = array("h", (round(x * gain) for x in samples))
    if sys.byteorder != "little":
        normalized.byteswap()
    pcm = normalized.tobytes() + bytes(item["padding_frames"] * 2)
    if len(pcm) != item["frames"] * 2:
        raise ValueError("Rendered sample budget mismatch")
    return pcm, {"source_peak_pcm16": peak, "gain_linear": gain, "target_peak_dbfs": -3}


def write_wave(path, pcm):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(pcm)


def read_pcm(path):
    with wave.open(str(path), "rb") as src:
        if (src.getnchannels(), src.getsampwidth(), src.getframerate()) != (1, 2, RATE):
            raise ValueError(f"Wrong playback format: {path}")
        return src.readframes(src.getnframes())


def timeline(data, item):
    mapping = item["mapping"]
    events = []
    for agent, stream in data["streams"].items():
        for word in stream:
            parts = map_interval(word["source_start"], word["source_end"], mapping)
            if not parts:
                continue
            full = sum(b - a for a, b in parts) == word["source_end"] - word["source_start"]
            lexical = word["kind"] == "w" and not word["punctuation"]
            scored = agent == item["speaker"] and lexical
            if scored and not full:
                raise ValueError(f"Target word was cut: {word['id']}")
            events.append({**word, "playback_parts": parts, "playback_start": parts[0][0],
                           "playback_end": parts[-1][1], "scored": scored,
                           "fully_retained": full, "reference_role": "target" if agent == item["speaker"] else "context_only_headset_bleed_not_guaranteed_audible"})
    events.sort(key=lambda w: (w["playback_start"], w["speaker"], w["id"]))
    sentences = []
    for act in data["acts"]:
        selected = [w for w in events if w.get("dialogue_act") == act["id"] and w["kind"] == "w"]
        if not selected:
            continue
        sentences.append({**act, "playback_parts": map_interval(act["source_start"], act["source_end"], mapping),
                          "playback_start": min(w["playback_start"] for w in selected),
                          "playback_end": max(w["playback_end"] for w in selected),
                          "retained_word_ids": [w["id"] for w in selected],
                          "text": " ".join(w["text"] for w in selected),
                          "partial": len(selected) != len([i for i in act["word_ids"] if any(w["id"] == i and w["kind"] == "w" for w in data["streams"][act["speaker"]])]),
                          "scored": act["speaker"] == item["speaker"], "unit": "manual_dialogue_act_not_grammatical_sentence"})
    turns = []
    for word in [w for w in events if w["kind"] == "w" and not w["punctuation"]]:
        if not turns or turns[-1]["speaker"] != word["speaker"]:
            turns.append({"id": f"{item['id']}.turn{len(turns)}", "speaker": word["speaker"],
                          "playback_start": word["playback_start"], "playback_end": word["playback_end"], "word_ids": []})
        turns[-1]["playback_end"] = max(turns[-1]["playback_end"], word["playback_end"])
        turns[-1]["word_ids"].append(word["id"])
    event_by_id = {w["id"]: w for w in events}
    for turn in turns:
        turn["text"] = " ".join(event_by_id[i]["text"] for i in turn["word_ids"])
    stress = []
    scored_ids = {w["id"] for w in events if w["scored"]}
    for event in stress_events(data, item["speaker"]):
        if not (item["source_start"] <= event["source_start"] <= event["source_end"] <= item["source_end"]):
            continue
        if "word_ids" in event and not set(event["word_ids"]) <= scored_ids:
            continue
        parts = map_interval(event["source_start"], event["source_end"], mapping)
        if parts:
            stress.append({**event, "playback_parts": parts})
    topics = []
    for topic in data["topics"]:
        parts = map_interval(topic["source_start"], topic["source_end"], mapping)
        if parts:
            topics.append({**topic, "playback_parts": parts})
    return {"schema_version": 1, "clip_id": item["id"], "timebase": "integer frames at 48000 Hz; intervals half-open; zero-width punctuation retained", "frames": item["frames"],
            "reference_level": "human transcript/manual dialogue acts; automatically forced-aligned source word times; not independently verified",
            "source_to_playback": mapping, "removed": item["removed"],
            "padding": [{"playback_start": item["frames"] - item["padding_frames"], "playback_end": item["frames"]}] if item["padding_frames"] else [],
            "words_and_events": events, "sentences": sentences, "turns": turns, "topics": topics, "stress_candidates": stress}


def relative(path, root):
    return path.relative_to(root).as_posix()


def prepare(root, data_root):
    selection_path = root / "corpus/english/selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if selection["policy_sha256"] != sha256(root / "corpus/english/selection-policy.json"):
        raise ValueError("Selection policy changed; explicitly run plan again before preparation")
    archive = data_root / "downloads/ami_public_manual_1.6.2.zip"
    acquire(ANNOTATIONS, archive, ANNOTATION_SHA256)
    corpus = load_corpus(archive)
    records = []
    for item in selection["chunks"] + selection["isolated"]:
        source = data_root / "downloads" / item["session"] / item["source_url"].rsplit("/", 1)[1]
        source_hash = acquire(item["source_url"], source)
        audio = data_root / "audio" / (item["id"] + ".wav")
        timeline_path = root / "corpus/english/timelines" / (item["id"] + ".json")
        pcm, gain = render_pcm(source, item)
        write_wave(audio, pcm)
        reference = timeline(corpus[item["session"]], item)
        save(timeline_path, reference)
        record = {**item, "audio_path": relative(audio, root), "audio_sha256": sha256(audio),
                  "timeline_path": relative(timeline_path, root), "timeline_sha256": sha256(timeline_path),
                  "source_path": relative(source, root), "source_sha256": source_hash,
                  "normalization": gain, "scored_words": sum(w["scored"] for w in reference["words_and_events"]),
                  "stress_candidate_counts": dict(Counter(e["type"] for e in reference["stress_candidates"])),
                  "license": "CC-BY-4.0", "attribution": "AMI Project — AMI Meeting Corpus", "reference_level": reference["reference_level"]}
        records.append(record)
        print(f"Prepared {item['id']}: {item['frames'] / RATE:.3f}s; {record['scored_words']} scored words", flush=True)
    main = [r for r in records if r["category"] in {"general", "stress"}]
    dev = [r for r in records if r["category"] == "development"]
    bundles = []
    for name, items, directions in (("main", main, ["D1", "D2"]), ("development", dev, ["D1", "D2"])):
        pcm_parts, offsets, cursor = [], [], 0
        for i, record in enumerate(items):
            if i:
                pcm_parts.append(bytes(2 * RATE * 2))
                cursor += 2 * RATE
            pcm = read_pcm(root / record["audio_path"])
            offsets.append({"clip_id": record["id"], "playback_start": cursor, "playback_end": cursor + record["frames"],
                            "timeline_path": record["timeline_path"]})
            pcm_parts.append(pcm)
            cursor += record["frames"]
        path = data_root / "audio" / f"{name}.wav"
        write_wave(path, b"".join(pcm_parts))
        expected = tick(1800 if name == "main" else 300)
        if cursor != expected:
            raise ValueError(f"{name} bundle duration budget mismatch")
        bundle_timeline = {"timebase": "integer frames at 48000 Hz", "frames": cursor, "clips": offsets,
                           "separators": [{"playback_start": a["playback_end"], "playback_end": b["playback_start"]} for a, b in zip(offsets, offsets[1:])]}
        for key in ("words_and_events", "sentences", "turns", "stress_candidates", "topics"):
            joined = []
            for offset in offsets:
                source_reference = json.loads((root / offset["timeline_path"]).read_text(encoding="utf-8"))
                for unit in source_reference[key]:
                    copy = {**unit, "clip_id": offset["clip_id"]}
                    for boundary in ("playback_start", "playback_end"):
                        if boundary in copy:
                            copy[boundary] += offset["playback_start"]
                    if "playback_parts" in copy:
                        copy["playback_parts"] = [[a + offset["playback_start"], b + offset["playback_start"]] for a, b in copy["playback_parts"]]
                    joined.append(copy)
            bundle_timeline[key] = joined
        ref_path = root / "corpus/english/timelines" / f"{name}.json"
        save(ref_path, bundle_timeline)
        bundles.append({"id": name, "directions": directions, "frames": cursor,
                        "audio_path": relative(path, root), "audio_sha256": sha256(path),
                        "timeline_path": relative(ref_path, root), "timeline_sha256": sha256(ref_path), "clips": offsets})
    repeat_path = data_root / "audio/repeat.wav"
    write_wave(repeat_path, read_pcm(root / main[0]["audio_path"]) + bytes(2 * RATE * 2))
    repeat_reference = json.loads((root / main[0]["timeline_path"]).read_text(encoding="utf-8"))
    repeat_reference["frames"] = 300 * RATE
    repeat_reference["separator"] = {"playback_start": 298 * RATE, "playback_end": 300 * RATE}
    save(root / "corpus/english/timelines/repeat.json", repeat_reference)
    shortlist = [{"clip_id": r["id"], "audio_sha256": r["audio_sha256"], "session": r["session"],
                  "speaker": r["speaker"], "category": r["category"], "timeline_path": r["timeline_path"],
                  "reason": "general including genuine labelled chitchat" if r["id"] == "general-01" else "separately selected stress; inspect uncertainty before presentation"}
                 for r in records if r["id"] in {"general-01", "stress-01", "stress-02"}]
    save(root / "corpus/english/common-shortlist.json", {"status": "candidate shortlist selected before benchmark results; final common excerpt freeze remains with Director", "seed": selection["seed"], "clips": shortlist})
    with zipfile.ZipFile(archive) as z:
        license_path = root / "corpus/english/AMI-LICENCE.txt"
        license_path.write_bytes(z.read("LICENCE.txt"))
    manifest = {"schema_version": 1, "status": "prepared_local_not_published", "sample_rate": RATE, "channels": 1,
                "seed": selection["seed"], "partition": selection["partition"], "selection_sha256": sha256(selection_path),
                "direction_reuse": {"D1": "main", "D2": "main"}, "bundles": bundles, "assets": records,
                "repeat": {"audio_path": relative(repeat_path, root), "audio_sha256": sha256(repeat_path), "frames": 300 * RATE,
                           "timeline_path": "corpus/english/timelines/repeat.json", "timeline_sha256": sha256(root / "corpus/english/timelines/repeat.json"),
                           "main_frames": [0, 300 * RATE], "directions": ["D1"]},
                "duration_accounting": {"main_total_seconds": 1800, "main_chunk_seconds": 1790, "main_separator_seconds": 10,
                                        "general_chunk_seconds": 1192, "general_assigned_separator_seconds": 8, "general_total_seconds": 1200,
                                        "stress_chunk_seconds": 598, "stress_assigned_separator_seconds": 2, "stress_total_seconds": 600,
                                        "development_chunk_seconds": 298, "development_separator_seconds": 2, "development_total_seconds": 300,
                                        "isolated_count": len(selection["isolated"]), "isolated_total_seconds": sum(r["frames"] for r in records if r["category"] == "isolated") / RATE,
                                        "padding_within_main_chunks_seconds": sum(r["padding_frames"] for r in main) / RATE},
                "casual_chat": {"method": "Only original top.14 source intervals; surrounding chunk is not relabelled casual", "main_playback_seconds": sum(r.get("casual_chat_playback_frames", 0) for r in main) / RATE,
                                "main_proportion": sum(r.get("casual_chat_playback_frames", 0) for r in main) / (1800 * RATE), "eligible_session": "ES2014d", "all_sessions_are_meetings": True},
                "reference_limits": ["Human orthographic transcripts/manual dialogue acts; word times are automatic corpus forced alignment.", "Stress pauses/continuations/fillers are explicitly uncertain timing/lexical candidates; not independent listening validation.", "Other-speaker context references describe retained source time but may be inaudible on target headset. Only target lexical words are scored.", "Heldout means distinct source sessions, not distinct global participants or globally independent conversations.", "No listening or GUI presentation claimed by this program. Native source WAV is 16 kHz; 48 kHz output is upsampled.", "Final common-clip freeze and complete six-direction/release manifest belong to Director."],
                "license": {"identifier": "CC-BY-4.0", "attribution": "AMI Project — AMI Meeting Corpus", "corpus_url": "https://groups.inf.ed.ac.uk/ami/corpus/",
                            "license_url": "https://creativecommons.org/licenses/by/4.0/", "source_terms_url": "https://groups.inf.ed.ac.uk/ami/corpus/license.shtml",
                            "included_license": relative(license_path, root), "license_sha256": sha256(license_path), "annotations": selection["annotations"],
                            "modifications": "Selected participant headset excerpts; long gaps occupied by other speakers compressed by deleting middle audio; source resampled from 16 kHz to 48 kHz mono; constant peak normalization; digital silence padding and separators; reference times recomputed from retained sample mappings. No endorsement implied."}}
    save(root / "corpus/english/manifest.json", manifest)
    print(json.dumps(manifest["duration_accounting"], indent=2))


def check(root):
    manifest = json.loads((root / "corpus/english/manifest.json").read_text(encoding="utf-8"))
    checked = 0
    for record in manifest["assets"] + manifest["bundles"] + [manifest["repeat"]]:
        for key in ("audio", "timeline"):
            if sha256(root / record[key + "_path"]) != record[key + "_sha256"]:
                raise ValueError(f"Changed {key}: {record[key + '_path']}")
        pcm = read_pcm(root / record["audio_path"])
        if len(pcm) != record["frames"] * 2:
            raise ValueError(f"Wrong frame count: {record['audio_path']}")
        reference = json.loads((root / record["timeline_path"]).read_text(encoding="utf-8"))
        for key in ("words_and_events", "sentences", "turns"):
            for unit in reference[key]:
                if not 0 <= unit["playback_start"] <= unit["playback_end"] <= record["frames"]:
                    raise ValueError(f"Out of range {key}: {unit}")
                for a, b in unit.get("playback_parts", []):
                    if not 0 <= a <= b <= record["frames"]:
                        raise ValueError(f"Out of range part: {unit}")
        if "mapping" in record:
            covered_ids = {i for sentence in reference["sentences"] if sentence["scored"] for i in sentence["retained_word_ids"]}
            for word in reference["words_and_events"]:
                if map_interval(word["source_start"], word["source_end"], record["mapping"]) != word["playback_parts"]:
                    raise ValueError(f"Mapping disagreement: {word['id']}")
                if word["scored"] and (not word["fully_retained"] or word["speaker"] != record["speaker"] or word["punctuation"]):
                    raise ValueError(f"Invalid scoring eligibility: {word['id']}")
                if word["scored"] and (word.get("dialogue_act") is None or word["id"] not in covered_ids):
                    raise ValueError(f"Scored word lacks a manual dialogue-act reference: {word['id']}")
            for span in record["mapping"]:
                if span["source_end"] - span["source_start"] != span["playback_end"] - span["playback_start"]:
                    raise ValueError("A retained interval was time stretched")
        checked += 1
    main_pcm = read_pcm(root / next(b for b in manifest["bundles"] if b["id"] == "main")["audio_path"])
    repeat_pcm = read_pcm(root / manifest["repeat"]["audio_path"])
    if repeat_pcm != main_pcm[:len(repeat_pcm)]:
        raise ValueError("Repeat is not the exact five-minute main prefix")
    for bundle in manifest["bundles"]:
        pcm = read_pcm(root / bundle["audio_path"])
        for previous, following in zip(bundle["clips"], bundle["clips"][1:]):
            gap = pcm[previous["playback_end"] * 2:following["playback_start"] * 2]
            if gap != bytes(2 * RATE * 2):
                raise ValueError("Interchunk separator is not exactly two seconds of silence")
    result = {"status": "passed", "checked_audio_and_timeline_pairs": checked,
              "checks": ["SHA-256", "48 kHz mono PCM16", "exact sample budgets", "all timeline boundaries in range", "word source-to-playback mapping", "target-only complete lexical scoring", "retained intervals not stretched", "exact 5m repeat prefix", "exact zero-valued 2s separators"],
              "limits": "Does not establish transcription correctness, listening intelligibility, acoustic pause authenticity, or GUI presentation quality."}
    save(root / "corpus/english/verification.json", result)
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Acquire and prepare real local AMI English inputs; no upload or evaluated ASR.")
    parser.add_argument("command", choices=["plan", "prepare", "check"])
    parser.add_argument("--data-root", type=Path, default=ROOT / ".data/english")
    args = parser.parse_args()
    if not args.data_root.resolve().is_relative_to((ROOT / ".data").resolve()):
        parser.error("Downloads and audio must remain under repository .data")
    if args.command == "plan":
        plan(ROOT, args.data_root.resolve())
    elif args.command == "prepare":
        prepare(ROOT, args.data_root.resolve())
    else:
        check(ROOT)


if __name__ == "__main__":
    main()
