from __future__ import annotations

import copy
import json
import re
import subprocess
from pathlib import Path

from .adapter import redact
from .audio import wave_info
from .storage import digest


IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


def load_plan(path, run_id):
    path = Path(path).resolve()
    original = json.loads(path.read_text(encoding="utf-8"))
    plan = copy.deepcopy(original)
    if not IDENTIFIER.fullmatch(run_id):
        raise ValueError("Run ID must be a safe identifier")
    for key in ("frozen_rule_revision", "price_table_version", "profiles", "stages", "output_check"):
        if key not in plan:
            raise ValueError(f"Run plan requires {key}")
    if redact(plan) != plan:
        raise ValueError("Run plan must contain key aliases, never credential fields")
    synthetic = plan.get("synthetic", False)
    def audio(stage):
        filename = (path.parent / stage["audio"]).resolve()
        info = wave_info(filename)
        stage.update({"audio": str(filename), "audio_sha256": digest(filename), **info})
        tail = stage.get("tail_seconds", 10 if stage.get("kind") == "isolated" else 15)
        if not isinstance(tail, (int, float)) or tail < 0:
            raise ValueError("Observation tail must be nonnegative")
        stage["tail_seconds"] = tail
        intervals = stage.get("speech_intervals", [])
        previous = 0
        for start, end in intervals:
            if not 0 <= previous <= start < end <= info["duration_seconds"]:
                raise ValueError("Speech intervals must be ordered, nonoverlapping playback seconds")
            previous = end
        if stage.get("kind") in ("chunk", "repeat", "isolated") and not intervals:
            raise ValueError("Speech work requires explicit speech_intervals, not inferred from silence")
    audio(plan["output_check"])
    profiles = {}
    endpoints = {}
    for profile in plan["profiles"]:
        identity = profile["id"]
        if not IDENTIFIER.fullmatch(identity) or identity in profiles:
            raise ValueError("Profiles need unique safe IDs")
        if not isinstance(profile.get("adapter"), list) or not profile["adapter"] or not all(isinstance(arg, str) for arg in profile["adapter"]):
            raise ValueError("Adapter must be a nonempty argument vector")
        profile.setdefault("metadata", {})
        profile.setdefault("key_aliases", [])
        expected = profile.get("expected_state", {})
        for key in ("microphone", "voice_output", "osc_host", "osc_port"):
            if key not in expected:
                raise ValueError(f"Profile {identity} expected_state requires {key}")
        if "CABLE Output" not in expected["microphone"] or expected["voice_output"] is not False:
            raise ValueError("Profiles must capture CABLE Output with voice_output false")
        osc = profile["osc"]
        if osc["host"] != "127.0.0.1" or not 1 <= osc["port"] <= 65535:
            raise ValueError("OSC sinks must use an explicit local UDP port")
        if expected["osc_host"] != osc["host"] or expected["osc_port"] != osc["port"]:
            raise ValueError("Expected state must match the OSC sink")
        endpoint = (osc["host"], osc["port"])
        endpoints.setdefault(endpoint, []).append(profile)
        profiles[identity] = profile
    if not profiles:
        raise ValueError("At least one profile is required")
    for group in endpoints.values():
        if len(group) > 1:
            ports = [profile["osc"].get("source_port") for profile in group]
            if None in ports or len(set(ports)) != len(ports):
                raise ValueError("Shared destination ports require distinct pinned source ports")
    expanded = []
    prepared = set()
    directions = {}
    for index, stage in enumerate(plan["stages"]):
        if stage["kind"] not in ("chunk", "isolated", "nonspeech", "repeat"):
            raise ValueError("Input stages must be chunk, isolated, nonspeech or repeat")
        if not stage["profiles"] or len(set(stage["profiles"])) != len(stage["profiles"]) or set(stage["profiles"]) - profiles.keys():
            raise ValueError("Stages must name unique existing profiles")
        stage.setdefault("chunk", f"chunk-{index + 1}")
        if not IDENTIFIER.fullmatch(stage["chunk"]):
            raise ValueError("Chunk IDs must be safe identifiers")
        stage["wave"]
        stage["direction"]
        audio(stage)
        common = {key: stage[key] for key in ("wave", "direction", "chunk")}
        new = [profile for profile in stage["profiles"] if profile not in prepared]
        changed = [profile for profile in stage["profiles"] if directions.get(profile) != stage["direction"]]
        if new:
            expanded.append({**common, "kind": "setup", "profiles": new})
            prepared.update(new)
        if changed:
            expanded.append({**common, "kind": "direction", "profiles": changed})
            for profile in changed:
                directions[profile] = stage["direction"]
            expanded.append({**plan["output_check"], **common, "kind": "output_check", "profiles": changed})
        expanded.append(stage)
    if not expanded:
        raise ValueError("At least one source stage is required")
    calibration = plan.get("calibration")
    if calibration:
        calibration_path = (path.parent / calibration).resolve()
        record = json.loads(calibration_path.read_text(encoding="utf-8"))
        if record.get("status") != "measured" or not isinstance(record.get("offset_ns"), int):
            raise ValueError("Calibration must be an actual measured cable record")
        evidence = calibration_path.parent / record["raw_evidence"]["path"]
        if digest(evidence) != record["raw_evidence"]["sha256"]:
            raise ValueError("Calibration evidence checksum does not match")
        plan["calibration"] = {**record, "record_path": str(calibration_path), "record_sha256": digest(calibration_path)}
    else:
        plan["calibration"] = {"status": "absent", "offset_ns": None, "reason": "not_measured"}
    if not synthetic and plan["calibration"]["status"] != "measured":
        raise ValueError("Real runs require bench calibrate; an absent offset is not zero")
    revision = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    plan.update({"run_id": run_id, "schema_version": 1, "stages": expanded,
                 "harness_revision": revision.stdout.strip() if revision.returncode == 0 else "unknown",
                 "harness_sources": {source.name: digest(source) for source in sorted(Path(__file__).parent.glob("*.py"))},
                 "input_plan_sha256": digest(path), "input_plan": str(path)})
    return plan


def verify_audio(stage):
    if "audio" in stage and digest(stage["audio"]) != stage["audio_sha256"]:
        raise ValueError("Frozen playback audio changed; use a new run")
