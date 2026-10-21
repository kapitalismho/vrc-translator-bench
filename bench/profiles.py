from __future__ import annotations

import json
import socket
from pathlib import Path


PROFILE_IDS = frozenset(("PP1", "PP2", "PP3", "PP4", "VRCT1", "VRCT2", "VRCT3", "VRCS1", "VRCS2", "VRCLS1", "KIKI1", "KIKI2", "VRCLT1", "VRCLT2"))
DIRECTIONS = {"D1": ("en", "ja"), "D2": ("en", "zh"), "D3": ("zh", "ko"), "D4": ("ja", "ko"), "D5": ("zh", "ja"), "D6": ("ja", "en")}


def inspect_catalog(path, *, check_ports=False):
    path = Path(path).resolve()
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if catalog.get("schema_version") != 1:
        raise ValueError("Unsupported profile catalogue schema")
    profiles = {}
    required = ("application", "finding", "reason", "planned", "observed", "directions", "control", "microphone", "osc", "tts", "updates", "access", "cpu_local", "procedure", "evidence", "osc_example")
    for profile in catalog["profiles"]:
        identity = profile["id"]
        if identity not in PROFILE_IDS or identity in profiles:
            raise ValueError(f"Unexpected or duplicate profile: {identity}")
        for field in required:
            if field not in profile:
                raise ValueError(f"{identity} requires {field}")
        if profile["finding"] not in ("ready", "unsupported", "blocked") or not profile["reason"]:
            raise ValueError(f"{identity} needs an explicit finding and reason")
        if profile["cpu_local"] not in (None, "asr", "translation"):
            raise ValueError(f"{identity} has an unknown CPU-local workload")
        if set(profile["directions"]) != set(DIRECTIONS):
            raise ValueError(f"{identity} must account for all six directions")
        if any(value not in ("verified", "source_supported", "unsupported", "unverified") for value in profile["directions"].values()):
            raise ValueError(f"{identity} has an unknown direction finding")
        for name in (profile["procedure"], *profile["evidence"]):
            if not (path.parent / name).is_file():
                raise ValueError(f"{identity} evidence/procedure does not exist: {name}")
        osc = profile["osc"]
        if osc["host"] != "127.0.0.1":
            raise ValueError(f"{identity} must send to loopback")
        for key in ("send_port", "receive_port"):
            port = osc[key]
            if port is not None and (type(port) is not int or not 1 <= port <= 65535):
                raise ValueError(f"{identity} has an invalid {key}")
        if osc["send_port"] is None:
            raise ValueError(f"{identity} needs an assigned capture port")
        if profile["finding"] == "ready":
            observed = profile["observed"]
            if not all(observed.get(key) for key in ("version", "asr", "translation", "provider_route", "state_evidence")):
                raise ValueError(f"{identity} cannot be ready without observed route/state")
            if profile["microphone"].get("verified") is not True or profile["tts"].get("verified_off_injection") is not True:
                raise ValueError(f"{identity} cannot be ready without verified audio routing")
            example = profile["osc_example"]
            if not example or example.get("kind") != "audio_to_osc" or not example.get("no_vrchat"):
                raise ValueError(f"{identity} requires an actual no-VRChat audio-to-OSC example")
            for name in (observed["state_evidence"], example["path"]):
                if not (path.parent / name).is_file():
                    raise ValueError(f"{identity} missing readiness evidence: {name}")
            if not any(value == "verified" for value in profile["directions"].values()):
                raise ValueError(f"{identity} has no verified direction")
        profiles[identity] = profile
    if profiles.keys() != PROFILE_IDS:
        raise ValueError(f"Missing parent profiles: {sorted(PROFILE_IDS - profiles.keys())}")
    assigned = set()
    wave_ids = set()
    for wave in catalog["waves"]:
        if wave["id"] in wave_ids:
            raise ValueError("Duplicate wave ID")
        wave_ids.add(wave["id"])
        members = wave["profiles"]
        if not members or len(members) != len(set(members)) or set(members) - profiles.keys():
            raise ValueError(f"{wave['id']} has invalid membership")
        if assigned.intersection(members):
            raise ValueError("A profile occurs in more than one wave")
        assigned.update(members)
        selected = [profiles[identity] for identity in members]
        apps = [profile["application"] for profile in selected]
        if len(apps) != len(set(apps)):
            raise ValueError(f"{wave['id']} runs multiple configurations of one app")
        if sum(profile["cpu_local"] is not None for profile in selected) > 1:
            raise ValueError(f"{wave['id']} runs competing CPU-local workloads")
        ports = []
        quota_scopes = []
        for profile in selected:
            ports.extend(port for port in (profile["osc"]["send_port"], profile["osc"]["receive_port"]) if port is not None)
            scope = profile["access"].get("exclusive_quota_scope")
            if scope:
                quota_scopes.append(scope)
        if len(ports) != len(set(ports)):
            raise ValueError(f"{wave['id']} has conflicting OSC ports")
        if len(quota_scopes) != len(set(quota_scopes)):
            raise ValueError(f"{wave['id']} has a shared exclusive quota scope")
    if assigned != PROFILE_IDS:
        raise ValueError("Wave plan must account for every parent profile")
    port_observations = []
    if check_ports:
        sockets = []
        try:
            for port in sorted({port for profile in profiles.values() for port in (profile["osc"]["send_port"], profile["osc"]["receive_port"]) if port is not None}):
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sockets.append(sock)
                if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                try:
                    sock.bind(("127.0.0.1", port))
                    port_observations.append({"port": port, "available": True})
                except OSError as error:
                    port_observations.append({"port": port, "available": False, "error": error.errno})
        finally:
            for sock in sockets:
                sock.close()
    findings = [{"id": identity, "finding": profile["finding"], "reason": profile["reason"]} for identity, profile in profiles.items()]
    ready = [row["id"] for row in findings if row["finding"] == "ready"]
    return {"catalog": str(path), "status": "ready" if len(ready) == len(PROFILE_IDS) and all(row["available"] for row in port_observations) else "blocked",
            "ready_profiles": ready, "findings": findings, "waves": catalog["waves"], "port_observations": port_observations,
            "limits": catalog["limitations"], "port_check_scope": "instantaneous loopback UDP bind only; not future reservation or app readiness"}
