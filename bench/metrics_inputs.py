from __future__ import annotations

import json
import math
from pathlib import Path
from .storage import digest


VERSION = "issue5-v1"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fingerprint(path):
    return digest(path)


def resolve(base, path):
    value = Path(path)
    return value if value.is_absolute() else Path(base) / value


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def metric(value=None, reason=None, unit="seconds", **evidence):
    return {"value": value, "unit": unit, "reason": reason, **evidence}


def read_rows(path):
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def timeline(spec, base):
    path = resolve(base, spec["path"])
    data = load_json(path)
    for part in spec.get("pointer", "").strip("/").split("/") if spec.get("pointer") else []:
        data = data[int(part)] if isinstance(data, list) else data[part.replace("~1", "/").replace("~0", "~")]
    units = spec["units"]
    if units not in ("samples", "seconds"):
        raise ValueError("Timeline units must explicitly be samples or seconds")
    scale = number(spec.get("sample_rate", 48000), "sample_rate") if units == "samples" else 1
    if scale <= 0:
        raise ValueError("sample_rate must be positive")
    clips = {item.get("clip_id", item.get("id")): item for item in spec.get("clips", [])}
    if spec.get("metadata_path"):
        metadata = load_json(resolve(base, spec["metadata_path"]))
        entries = metadata.get("assets", metadata.get("chunks", []))
        clips.update({item.get("clip_id", item.get("id")): {**item, "session_id": item.get("session", item.get("source_id")),
                                                         "casual": item.get("casual_chat", None)} for item in entries})
    containers = data if isinstance(data, list) else data.get("chunks", [data])
    result = {"sentences": [], "turns": [], "intervals": data.get("intervals", []) if isinstance(data, dict) else [],
              "path": str(path), "sha256": fingerprint(path), "reference_level": spec.get("reference_level", data.get("reference_level", "unknown") if isinstance(data, dict) else "unknown")}
    offset = number(spec.get("offset_seconds", 0), "offset_seconds")
    for container in containers:
        context_by_id = {row["id"]: row for row in container.get("context", [])}
        for kind in ("turns", "sentences"):
            for index, row in enumerate(container.get(kind, [])):
                chunk = row.get("clip_id", row.get("chunk_id", container.get("clip_id", container.get("chunk_id", container.get("id", spec.get("chunk_id", "clip"))))))
                info = {**container, **spec, **clips.get(chunk, {})}
                start = number(row.get("playback_start", row.get("start")), "reference start") / scale - offset
                end = number(row.get("playback_end", row.get("end")), "reference end") / scale - offset
                if end < start:
                    raise ValueError("Reference end precedes start")
                if end < spec.get("window_start_seconds", 0) or start > spec.get("window_end_seconds", float("inf")):
                    continue
                native_id = row.get("id", row.get("sentence_id", row.get("turn_id")))
                identity = str(native_id) if native_id is not None else f"{kind}-{index}"
                session = info.get("session_id", info.get("session", row.get("source_id", info.get("source_id"))))
                if not session:
                    raise ValueError(f"Original session_id required for {chunk}/{identity}")
                words = container.get("words_and_events", container.get("words", []))
                lexical = [word for word in words if word.get("id") in row.get("word_ids", []) and word.get("clip_id", word.get("chunk_id", chunk)) == chunk
                           and not word.get("punctuation", False) and word.get("kind", "w") == "w" and word.get("scored", word.get("score", True))]
                scored = row.get("scored", row.get("score", True))
                if "words_and_events" in container:
                    scored = scored and bool(lexical)
                casual = info.get("casual", info.get("casual_chat"))
                if spec.get("source_group") == "en":
                    topics = container.get("topics", [])
                    casual = any(any("top.14" in tag for tag in topic.get("types", []))
                                 and any(a / scale <= start + offset and end + offset <= b / scale for a, b in topic.get("playback_parts", [])) for topic in topics)
                text_provenance = "native_reference_text"
                if kind == "turns" and not row.get("text"):
                    segment_ids = row.get("source_segment_ids", [])
                    context_segments = [context_by_id[identity] for identity in segment_ids if identity in context_by_id]
                    if segment_ids and len(context_segments) == len(segment_ids) and all(item.get("text", "").strip() for item in context_segments):
                        text = " ".join(item["text"] for item in context_segments)
                        text_provenance = "native_context_joined_by_source_segment_ids"
                    else:
                        row_words = [word for word in words if word.get("clip_id", word.get("chunk_id", chunk)) == chunk and word.get("speaker") == row.get("speaker")
                                     and number(word.get("playback_start", word.get("start")), "word start") / scale >= start + offset
                                     and number(word.get("playback_end", word.get("end")), "word end") / scale <= end + offset]
                        text = " ".join(word.get("text", "") for word in row_words)
                        text_provenance = "contained_reference_words" if text.strip() else "unavailable"
                else:
                    text = row.get("text", "")
                earlier = []
                source_start = row.get("source_start")
                for context in sorted(container.get("context", []), key=lambda item: item["source_start"]):
                    if source_start is None or context["source_end"] > source_start:
                        continue
                    if earlier and earlier[-1]["speaker"] == context["speaker"]:
                        earlier[-1]["text"] += " " + context.get("text", "")
                        earlier[-1]["source_end"] = max(earlier[-1]["source_end"], context["source_end"])
                        earlier[-1]["source_segment_ids"].append(context["id"])
                    else:
                        earlier.append({"speaker": context["speaker"], "text": context.get("text", ""), "source_start": context["source_start"],
                                        "source_end": context["source_end"], "source_segment_ids": [context["id"]], "scored": False,
                                        "coordinate_units": units, "provenance": "source-onset label-change grouping of native unscored context; no invented playback time"})
                result[kind].append({"id": f"{chunk}/{identity}", "original_id": native_id, "generated_id": native_id is None,
                                     "chunk_id": chunk, "session_id": session, "start": start, "end": end,
                                     "timebase": "playback seconds", "native_coordinate_units": units, "offset_seconds": offset,
                                     "speaker": row.get("speaker"), "text": text, "scored": scored,
                                     "text_provenance": text_provenance,
                                     "partial": row.get("partial", False), "category": info.get("category", "unknown"),
                                     "earlier_source_turns": earlier[-2:],
                                     "casual": casual, "source_group": info.get("source_group", "unknown"),
                                     "reference_level": container.get("reference_level", result["reference_level"]), "reference_evidence": row,
                                     "uncertainty": info.get("uncertainty", container.get("speaker_uncertainty", container.get("word_timing_uncertainty", "not independently verified")))})
    if len({row["id"] for row in result["sentences"]}) != len(result["sentences"]):
        raise ValueError("Duplicate reference sentence identity; include native chunk_id")
    for sentence in result["sentences"]:
        candidates = [turn for turn in result["turns"] if turn["chunk_id"] == sentence["chunk_id"] and turn["speaker"] == sentence["speaker"]
                      and (set(turn["reference_evidence"].get("word_ids", [])).intersection(sentence["reference_evidence"].get("word_ids", []))
                           or turn["start"] < sentence["end"] and sentence["start"] < turn["end"])]
        containing = [turn for turn in candidates if turn["start"] <= sentence["start"] and turn["end"] >= sentence["end"]]
        sentence["candidate_turn_ids"] = [turn["id"] for turn in candidates]
        sentence["turn_id"] = containing[0]["id"] if len(candidates) == len(containing) == 1 else None
        sentence["eligibility_reason"] = "partial_reference" if sentence["partial"] else "unscored_or_nonlexical_reference" if not sentence["scored"] else "ambiguous_containing_turn" if sentence["turn_id"] is None else None
    return result


def source_time(playback, callbacks, seconds, rate):
    correction = playback.get("calibration_offset_ns")
    if correction is None:
        return None
    frame = seconds * rate
    candidates = [row for row in callbacks if "dac_t_ns" in row and row["source_frame"] <= frame <= row["source_frame"] + row["source_frames"]]
    if candidates:
        row = max(candidates, key=lambda item: item["source_frame"])
        return row["dac_t_ns"] + round((frame - row["source_frame"]) / rate * 1e9) + correction
    if playback.get("synthetic"):
        return playback["playback_dac_start_ns"] + round(seconds * 1e9) + correction
    return None


def ingest(manifest_path, specification_path):
    manifest_path, specification_path = Path(manifest_path), Path(specification_path)
    manifest, spec = load_json(manifest_path), load_json(specification_path)
    if spec.get("schema_version") != 1 or not spec.get("version"):
        raise ValueError("Metrics specification requires schema_version=1 and version")
    root, base = manifest_path.parent, specification_path.parent
    records = []
    provenance = [{"path": str(manifest_path), "sha256": fingerprint(manifest_path)},
                  {"path": str(specification_path), "sha256": fingerprint(specification_path)}]
    for stream in manifest.get("streams", []):
        path = resolve(root, stream["path"])
        checksum = fingerprint(path)
        if stream.get("sha256") and checksum != stream["sha256"]:
            raise ValueError(f"Continuous stream checksum mismatch: {path}")
        provenance.append({"path": str(path), "sha256": checksum})
        records.extend(read_rows(path))
    work = {row["id"]: row for row in manifest["work"]}
    attempts = []
    for attempt in manifest["attempts"]:
        item = {**work[attempt["work_id"]], **attempt}
        stage = manifest["plan"]["stages"][item["stage"]]
        item.update({"config": item["profile"], "direction": stage.get("direction"), "stage_data": stage,
                     "run": manifest["run"], "synthetic": manifest["plan"].get("synthetic", False)})
        path = resolve(root, attempt["trace"])
        trace = list(read_rows(path)) if path.exists() else []
        if path.exists():
            checksum = fingerprint(path)
            if attempt.get("checksum") and checksum != attempt["checksum"]:
                raise ValueError(f"Attempt checksum mismatch: {path}")
            provenance.append({"path": str(path), "sha256": checksum})
        start = next((row for row in trace if row.get("record") == "attempt_start"), {})
        item["clock_session"] = start.get("clock_session")
        playback = next((row for row in trace if row.get("record") == "source_playback"), None)
        if playback is None:
            playback = next((row for row in records if row.get("record") == "source_playback" and row.get("attempt") == item["id"] and row.get("config") == item["config"]), None)
        item["playback"] = playback
        item["callbacks"] = [row for row in records if row.get("record") == "audio_callback"
                             and row.get("clock_session") == item["clock_session"]
                             and row.get("attempts", {}).get(item["config"]) == item["id"]]
        if not item["callbacks"]:
            item["callbacks"] = [row for row in trace if row.get("record") == "audio_callback"]
        reference = spec.get("references", {}).get(str(item["stage"]))
        item["isolated_quality_score"] = spec.get("isolated_quality_scores", {}).get(str(item["id"]))
        item["reference"] = timeline(reference, base) if reference else {"sentences": [], "turns": [], "intervals": []}
        if reference:
            provenance.append({"path": item["reference"]["path"], "sha256": item["reference"]["sha256"]})
            if reference.get("metadata_path"):
                metadata_path = resolve(base, reference["metadata_path"])
                provenance.append({"path": str(metadata_path), "sha256": fingerprint(metadata_path)})
        if playback:
            item["clock_session"] = playback["clock_session"]
            playback = {**playback, "synthetic": item["synthetic"]}
            item["playback"] = playback
            for kind in ("sentences", "turns"):
                for row in item["reference"][kind]:
                    row["start_ns"] = source_time(playback, item["callbacks"], row["start"], stage.get("sample_rate", 48000))
                    row["end_ns"] = source_time(playback, item["callbacks"], row["end"], stage.get("sample_rate", 48000))
        attempts.append(item)
    events = [row for row in records if "address" in row and "recv_seq" in row]
    keys = [(row.get("clock_session"), row["recv_seq"]) for row in events]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate OSC identity within clock session")
    return manifest, spec, attempts, events, provenance
