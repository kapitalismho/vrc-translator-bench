from __future__ import annotations

import copy
import json
import math
import re
import subprocess
import tomllib
from pathlib import Path

from . import __version__
from .adapter import redact
from .audio import wave_info
from .storage import digest


IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


def implementation_provenance():
    package = Path(__file__).resolve().parent
    root = package.parent
    identity = {"kind": "package", "revision": "unknown", "revision_reason": "not_a_harness_checkout",
                "package_version": __version__, "package_path": str(package),
                "sources": {source.name: digest(source) for source in sorted(package.glob("*.py"))}}
    project = root / "pyproject.toml"
    if not (root / ".git").exists() or not project.is_file():
        return identity
    try:
        project_name = tomllib.loads(project.read_text(encoding="utf-8")).get("project", {}).get("name")
    except (OSError, ValueError):
        identity["revision_reason"] = "unreadable_project_identity"
        return identity
    if project_name != "vrc-translator-bench":
        return identity
    identity["kind"] = "checkout"
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False)
    except OSError:
        identity["revision_reason"] = "git_unavailable"
        return identity
    if revision.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision.stdout.strip()):
        identity.update(revision=revision.stdout.strip(), revision_reason="loaded_harness_checkout")
    else:
        identity["revision_reason"] = "git_revision_unavailable"
    return identity


def _identifier(value, label):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a safe identifier")
    return value


def _seconds(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and nonnegative")
    return value


def _calibration(base, route, synthetic):
    filename = route.get("calibration")
    if not filename:
        if not synthetic:
            raise ValueError("Every real route requires measured calibration; an absent offset is not zero")
        return {"status": "absent", "offset_ns": None, "reason": "synthetic_not_measured"}
    filename = (base / filename).resolve()
    record = json.loads(filename.read_text(encoding="utf-8"))
    if record.get("status") != "measured" or type(record.get("offset_ns")) is not int:
        raise ValueError("Route calibration must be measured")
    evidence = filename.parent / record["raw_evidence"]["path"]
    if digest(evidence) != record["raw_evidence"]["sha256"]:
        raise ValueError("Calibration evidence checksum does not match")
    for side, field in (("output", "output_device"), ("input", "input_device")):
        observed = record["devices"][side]
        if str(route[field]) not in (str(observed[0]), observed[1]["name"]):
            raise ValueError(f"Route {field} does not match calibration")
    return {**record, "record_path": str(filename), "record_sha256": digest(filename)}


def load_plan(path, run_id):
    path = Path(path).resolve()
    plan = copy.deepcopy(json.loads(path.read_text(encoding="utf-8")))
    _identifier(run_id, "Run ID")
    if plan.get("schema_version") != 2 or "stages" in plan:
        raise ValueError("Run plan requires episode schema_version 2; legacy stages are not executable")
    for key in ("frozen_rule_revision", "price_table_version", "profiles", "episodes"):
        if key not in plan:
            raise ValueError(f"Run plan requires {key}")
    if redact(plan) != plan:
        raise ValueError("Run plan must contain key aliases, never credential fields")
    synthetic = plan.get("synthetic", False)
    if type(synthetic) is not bool:
        raise ValueError("synthetic must be boolean")
    scope = plan.get("execution_scope", {})
    if scope.get("kind") not in ("main", "pilot", "synthetic"):
        raise ValueError("execution_scope must explicitly declare main, pilot or synthetic")
    if synthetic != (scope["kind"] == "synthetic"):
        raise ValueError("Only synthetic plans may use synthetic execution_scope")
    if scope["kind"] == "pilot" and not scope.get("reason"):
        raise ValueError("Pilot subsets require an explicit reason; they do not establish wave admission")
    catalog = None
    canonical_profiles = {}
    if not synthetic:
        filename = Path(__file__).resolve().parent.parent / "profiles" / "catalog.json"
        canonical_catalog = json.loads(filename.read_text(encoding="utf-8"))
        canonical_profiles = {profile["id"]: profile for profile in canonical_catalog["profiles"]}
        plan["profile_catalog"] = {"path": str(filename), "sha256": digest(filename)}
        if scope["kind"] == "main":
            catalog = canonical_catalog
            plan["wave_catalog"] = {**plan["profile_catalog"], "waves": catalog["waves"]}
    profiles = {}
    for profile in plan["profiles"]:
        identity = _identifier(profile["id"], "Profile ID")
        if identity in profiles:
            raise ValueError("Profiles need unique IDs")
        if not isinstance(profile.get("adapter"), list) or not profile["adapter"] or not all(isinstance(arg, str) for arg in profile["adapter"]):
            raise ValueError("Adapter must be a nonempty argument vector")
        family = profile.get("collector", {}).get("family")
        if family not in ("puripuly", "vrct", "vrcs", "vrclt", "kikitan", "vrcls"):
            raise ValueError("Profile requires a native collector family")
        canonical = canonical_profiles.get(identity)
        if canonical is not None and family != canonical["application"].lower():
            raise ValueError(f"Canonical profile {identity} requires collector.family={canonical['application'].lower()}")
        condition = (canonical["native_protocol"]["condition"] if canonical is not None else {
            "ordinary_input": "self" if family in {"vrclt", "kikitan"} else "peer",
            "t1_mode": "split_self" if family in {"vrclt", "kikitan"} else "simultaneous",
            "roles": {"A": "self", "B": "self"} if family in {"vrclt", "kikitan"} else {"A": "peer", "B": "self"}})
        if "condition" in profile and profile["condition"] != condition:
            raise ValueError(f"Profile {identity} cannot override its approved measurement condition")
        profile["condition"] = copy.deepcopy(condition)
        if not isinstance(profile.get("expected_state"), dict) or profile["expected_state"].get("voice_output") is not False:
            raise ValueError("Profiles require explicit expected_state with voice_output false")
        if not profile.get("routes") or set(profile["routes"]) - {"self", "peer"}:
            raise ValueError("Profile routes must name physical self/peer channels")
        for route in profile["routes"].values():
            for field in ("output_device", "input_device"):
                if route.get(field) is None or route[field] == "":
                    raise ValueError(f"Every route requires explicit {field}; no default-device fallback")
            route["calibration"] = _calibration(path.parent, route, synthetic)
        profiles[identity] = profile
    if not profiles:
        raise ValueError("At least one profile is required")
    if catalog and set(profiles) - {name for wave in catalog["waves"] for name in wave["profiles"]}:
        raise ValueError("Main scope profiles must belong to the preserved catalog waves")
    passes, rounds = [], []
    episode_ids = set()
    for episode in plan["episodes"]:
        identity = _identifier(episode["episode_id"], "Episode ID")
        if identity in episode_ids:
            raise ValueError("Episodes need unique IDs")
        episode_ids.add(identity)
        kind = episode["kind"]
        if kind not in ("P1", "P2", "P3", "P4", "T1", "C1"):
            raise ValueError("Episode kind must be P1/P2/P3/P4/T1/C1")
        _identifier(episode["wave"], "Wave")
        if episode["language_pair"] not in ("en-zh", "ja-ko"):
            raise ValueError("Episode language_pair must be en-zh or ja-ko")
        names = episode["profiles"]
        if not names or len(set(names)) != len(names) or set(names) - profiles.keys():
            raise ValueError("Episodes must name unique existing profiles")
        if catalog:
            membership = next((wave["profiles"] for wave in catalog["waves"] if wave["id"] == episode["wave"]), None)
            if membership is None or set(names) != set(membership):
                raise ValueError("Main episode must preserve exact catalog wave membership")
        roles = episode["roles"]
        if set(roles) != ({"A", "B"} if kind == "T1" else {"A"}):
            raise ValueError("T1 requires fixed A/B roles; ordinary episodes require A")
        languages = episode["language_pair"].split("-")
        for role, source in roles.items():
            expected_languages = languages if role == "A" else languages[::-1]
            if [source.get("source_language"), source.get("target_language")] != expected_languages:
                raise ValueError("Role languages must preserve the approved fixed directions")
            filename = (path.parent / source["audio"]).resolve()
            source.update(audio=str(filename), audio_sha256=digest(filename), **wave_info(filename))
            previous = 0
            intervals = source.get("speech_intervals", [])
            for start, end in intervals:
                _seconds(start, "Speech start")
                _seconds(end, "Speech end")
                if not previous <= start < end <= source["duration_seconds"]:
                    raise ValueError("Speech intervals must be ordered within the common timeline")
                previous = end
            if kind != "C1" and not intervals:
                raise ValueError("Speech roles require explicit speech_intervals")
            if kind == "C1" and intervals:
                raise ValueError("C1 cannot declare input speech")
        if len({(source["sample_rate"], source["frames"]) for source in roles.values()}) != 1:
            raise ValueError("Role WAVs must share sample rate, length and original common timeline")
        common_last = max((end for source in roles.values() for _, end in source.get("speech_intervals", [])), default=roles["A"]["duration_seconds"])
        quiet = {}
        if "quiet_seconds" in episode or "quiet_max_wait_seconds" in episode:
            if kind != "C1" or not all(key in episode for key in ("quiet_seconds", "quiet_max_wait_seconds")):
                raise ValueError("quiet gating requires both fields on C1")
            quiet = {key: _seconds(episode[key], key) for key in ("quiet_seconds", "quiet_max_wait_seconds")}
            if quiet["quiet_max_wait_seconds"] < quiet["quiet_seconds"]:
                raise ValueError("quiet_max_wait_seconds must be at least quiet_seconds")
        groups = {}
        for name in names:
            condition = profiles[name]["condition"]
            bindings = ([("A", {"self": "A"}), ("B", {"self": "B"})] if kind == "T1" and condition["t1_mode"] == "split_self"
                        else [("simultaneous", {channel: role for role, channel in condition["roles"].items()})] if kind == "T1"
                        else [("ordinary-" + condition["ordinary_input"], {condition["ordinary_input"]: "A"})])
            for pass_id, channels in bindings:
                if set(channels) - profiles[name]["routes"].keys():
                    raise ValueError(f"{name} lacks the required physical routes")
                groups.setdefault(pass_id, {"profiles": [], "channels": channels})["profiles"].append(name)
        first_round, second_round = [], []
        for pass_id, group in groups.items():
            bindings = {channel: {"role": role, "source_language": roles[role]["source_language"],
                                  "target_language": roles[role]["target_language"]} for channel, role in group["channels"].items()}
            (second_round if pass_id == "B" else first_round).append(len(passes))
            passes.append({"episode_id": identity, "pass_id": pass_id, "kind": kind, "wave": episode["wave"],
                           "language_pair": episode["language_pair"], "profiles": group["profiles"],
                           "roles": bindings, "duration_seconds": roles["A"]["duration_seconds"],
                           "common_last_speech_seconds": common_last, "tail_seconds": 15, **quiet})
        rounds.append({"episode_id": identity, "wave": episode["wave"], "pass_indices": first_round})
        if second_round:
            rounds.append({"episode_id": identity, "wave": episode["wave"], "pass_indices": second_round})
    if not passes:
        raise ValueError("At least one episode is required")
    if catalog and set(profiles) != {name for episode in plan["episodes"] for name in episode["profiles"]}:
        raise ValueError("Main scope must schedule every declared profile")
    implementation = implementation_provenance()
    plan.update(run_id=run_id, passes=passes, rounds=rounds, harness_revision=implementation["revision"],
                harness_sources=implementation["sources"], harness_implementation=implementation,
                input_plan_sha256=digest(path), input_plan=str(path))
    return plan


def verify_audio(episode):
    for source in episode["roles"].values():
        if digest(source["audio"]) != source["audio_sha256"]:
            raise ValueError("Frozen playback audio changed; use a new run")
