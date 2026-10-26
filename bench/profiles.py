from __future__ import annotations

import json
import socket
from pathlib import Path


PROTOCOL = "native-output-v1"
WAVES = {
    "W1": ("PP4", "KIKI2", "VRCLT1", "VRCT3"),
    "W2": ("VRCT1", "PP1", "VRCS2", "KIKI1"),
    "W3": ("VRCT2", "VRCLT2", "PP2"),
    "W4": ("VRCS1", "PP3", "VRCLS1"),
}
PROFILE_IDS = frozenset(identity for members in WAVES.values() for identity in members)
SCOPES = ("ordinary/en-zh", "ordinary/ja-ko", "t1/en-zh/A", "t1/en-zh/B", "t1/ja-ko/A", "t1/ja-ko/B")
SELF_SPLIT = frozenset(("VRCLT1", "VRCLT2", "KIKI1", "KIKI2"))
MODELS = {
    "PP1": ("Gemini 3.5 Transcribe", "Gemma 4 mixed 26B/31B / OpenRouter"),
    "PP2": ("Gemini 3.5 Transcribe", "GPT 6 Luna / Sign in with ChatGPT"),
    "PP3": ("Gemini 3.5 Transcribe", "Index Translator"),
    "PP4": ("CPU-auto-selected local ASR", "Index Translator"),
    "VRCT1": ("Google Web Speech", "m2m100_418m"),
    "VRCT2": ("Whisper base", "Google Translate"),
    "VRCT3": ("Google Web Speech", "Gemma 4 26B / OpenRouter"),
    "VRCS1": ("Qwen3-ASR 0.6B", "Gemma 4 26B / OpenRouter"),
    "VRCS2": ("Gemini 3.5 Transcribe", "Gemma 4 26B / OpenRouter"),
    "VRCLS1": ("Developer server", "Developer server"),
    "KIKI1": ("Microsoft Bing", "Google Translate"),
    "KIKI2": ("All-in-one", "Gemini Live Translate 3.5"),
    "VRCLT1": ("All-in-one with source transcription", "Gemini Live Translate 3.5"),
    "VRCLT2": ("All-in-one", "Qwen 3.8 LiveTranslate"),
}
CPU_LOCAL = {"PP4": "asr", "VRCT1": "translation", "VRCT2": "asr", "VRCS1": "asr"}
ENDPOINTS = {
    "PuriPuly": {"transport": "cli", "path": "events follow --topic translation --include-translations", "channels": {"peer": "peer", "self": "self"}},
    "VRCT": {"transport": "websocket", "host": "127.0.0.1", "path": "/", "channels": {"peer": "RECEIVED", "self": "SENT"}},
    "VRCS": {"transport": "websocket", "host": "127.0.0.1", "path": "/v1/events", "channels": {"peer": "speaker", "self": "microphone"}, "event": "translation.completed"},
    "VRCLT": {"transport": "osc", "host": "127.0.0.1", "path": "/chatbox/input", "channels": {"self": "self"}, "cross_check": "%LOCALAPPDATA%/vrclt/logs/vrclt.log:FINAL"},
    "kikitan": {"transport": "osc", "host": "127.0.0.1", "path": "/microphone/translated", "channels": {"self": "self"}, "related": ["/microphone/recognized", "/microphone/final"]},
    "VRCLS": {"transport": "file", "path": "%APPDATA%/VRCLS/logs/vrcls-*.log", "channels": {"peer": "Desktop", "self": "Mic"}},
}


def _family(identity):
    if identity.startswith("PP"):
        return "PuriPuly"
    if identity.startswith("KIKI"):
        return "kikitan"
    return identity.rstrip("0123456789")


def _condition(identity):
    channel = "self" if identity in SELF_SPLIT else "peer"
    return {
        "ordinary_input": channel,
        "ordinary_directions": ["en->zh", "ja->ko"],
        "t1_mode": "split_self" if identity in SELF_SPLIT else "simultaneous",
        "roles": {"A": channel, "B": "self"},
        "t1_directions": {"A": ["en->zh", "ja->ko"], "B": ["zh->en", "ko->ja"]},
        "vrchat": "excluded",
    }


def _file(base, name, identity):
    if not isinstance(name, str) or not name or not (base / name).is_file():
        raise ValueError(f"{identity} missing evidence/procedure: {name}")
    return base / name


def _endpoint(native, identity):
    endpoint = native["endpoint"]
    family = _family(identity)
    expected = ENDPOINTS[family]
    network = expected["transport"] in ("osc", "websocket")
    if set(endpoint) != set(expected) | ({"port"} if network else set()) or any(endpoint.get(key) != value for key, value in expected.items()):
        raise ValueError(f"{identity} has an unexpected native endpoint/channel")
    if network:
        port = endpoint["port"]
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError(f"{identity} has an invalid native port")
        if family == "kikitan" and port != 7272:
            raise ValueError(f"{identity} user-data native port must be 7272, not chatbox OSC")
        return ("udp" if expected["transport"] == "osc" else "tcp", port)
    return None


def _early_feasibility(base, profile, native):
    identity = profile["id"]
    early = native["early_feasibility"]
    if not isinstance(early, dict) or set(early) != {"confirmed", "blockers", "unverified"}:
        raise ValueError(f"{identity} needs separate confirmation/blocker/unverified states")
    confirmed = early["confirmed"]
    unverified = early["unverified"]
    if not isinstance(confirmed, list) or not isinstance(unverified, list) or any(not isinstance(scope, str) for scope in unverified):
        raise ValueError(f"{identity} needs explicit confirmation/unverified scope lists")
    scopes = list(unverified)
    for confirmation in confirmed:
        if not isinstance(confirmation, dict) or set(confirmation) != {"scope", "evidence"} or confirmation["scope"] not in SCOPES:
            raise ValueError(f"{identity} has an unknown confirmation scope/state")
        scope = confirmation["scope"]
        evidence = json.loads(_file(base, confirmation["evidence"], identity).read_text(encoding="utf-8"))
        bindings = {"protocol": PROTOCOL, "profile": identity, "scope": scope,
                    "condition": native["condition"], "endpoint": native["endpoint"],
                    "models": {key: profile["planned"][key] for key in ("asr", "translation")},
                    "kind": "input_to_native_translation"}
        if "peer_asr" in native:
            bindings["peer_asr"] = native["peer_asr"]
        if any(evidence.get(key) != value for key, value in bindings.items()):
            raise ValueError(f"{identity} confirmation lacks matching native evidence bindings")
        if not all(isinstance(evidence.get(key), str) and evidence[key].strip() for key in ("app_version", "instance", "translated_text")):
            raise ValueError(f"{identity} confirmation requires actual translation/build/instance evidence")
        for key in ("input_evidence", "raw_evidence", "clock_evidence"):
            _file(base, evidence.get(key), identity)
        if _family(identity) == "VRCT":
            if evidence.get("ocr_disabled") is not True or evidence.get("external_text_disabled") is not True:
                raise ValueError(f"{identity} confirmation requires OCR/external-text disabled proof")
            _file(base, evidence.get("ocr_evidence"), identity)
        scopes.append(scope)
    if len(scopes) != len(SCOPES) or set(scopes) != set(SCOPES):
        raise ValueError(f"{identity} must account for each native condition scope exactly once")
    blockers = early["blockers"]
    if not isinstance(blockers, list) or any(not isinstance(row, dict) or row.get("scope") not in (*SCOPES, "all") or not isinstance(row.get("reason"), str) or not row["reason"].strip() for row in blockers):
        raise ValueError(f"{identity} needs scoped prerequisite blockers with reasons")
    for row in blockers:
        if any(row["scope"] in ("all", confirmation["scope"]) for confirmation in confirmed):
            raise ValueError(f"{identity} cannot confirm scope with an unresolved blocker")
    return early


def inspect_catalog(path, *, check_ports=False):
    """Inspect native R1 feasibility; historical fields never confer admission."""
    path = Path(path).resolve()
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if catalog.get("schema_version") != 2 or catalog.get("current_protocol") != PROTOCOL:
        raise ValueError("Unsupported native profile catalogue schema/protocol")
    profiles = {}
    endpoints = {}
    findings = []
    for profile in catalog["profiles"]:
        identity = profile["id"]
        if identity not in PROFILE_IDS or identity in profiles:
            raise ValueError(f"Unexpected or duplicate profile: {identity}")
        family = _family(identity)
        if profile["application"] != family:
            raise ValueError(f"{identity} has an unexpected application family")
        if tuple(profile["planned"].get(key) for key in ("asr", "translation")) != MODELS[identity]:
            raise ValueError(f"{identity} changes the planned model comparison")
        for name in (profile["procedure"], *profile["evidence"]):
            _file(path.parent, name, identity)
        native = profile["native_protocol"]
        if native["condition"] != _condition(identity):
            raise ValueError(f"{identity} has an unexpected native condition/role/direction")
        if family == "PuriPuly" and native.get("peer_asr") != ("local_cpu_auto" if identity == "PP4" else "gemini_transcribe"):
            raise ValueError(f"{identity} needs its separately planned peer ASR")
        endpoints[identity] = _endpoint(native, identity)
        early = _early_feasibility(path.parent, profile, native)
        admission = native["final_admission"]
        if admission != {"owner": "R6", "quality": "pending_r6", "time": "pending_r6"}:
            raise ValueError(f"{identity} final quality/time admission must remain separate and pending R6")
        profiles[identity] = profile
        findings.append({"id": identity, "application": family, "models": profile["planned"],
                         **native, "historical": {"finding": profile["finding"], "reason": profile["reason"]}})
    if profiles.keys() != PROFILE_IDS:
        raise ValueError(f"Missing parent profiles: {sorted(PROFILE_IDS - profiles.keys())}")
    seen = set()
    for wave in catalog["waves"]:
        wave_id = wave["id"]
        if wave_id in seen or wave_id not in WAVES or wave["profiles"] != list(WAVES[wave_id]):
            raise ValueError("Fixed W1-W4 concurrency membership must be preserved")
        seen.add(wave_id)
        selected = [profiles[identity] for identity in wave["profiles"]]
        if sum(profile["cpu_local"] is not None for profile in selected) > 1:
            raise ValueError(f"{wave_id} runs competing CPU-local workloads")
        addresses = [endpoints[profile["id"]] for profile in selected if endpoints[profile["id"]] is not None]
        if len(addresses) != len(set(addresses)):
            raise ValueError(f"{wave_id} has conflicting native ports")
        quotas = [profile["access"].get("exclusive_quota_scope") for profile in selected if profile["access"].get("exclusive_quota_scope")]
        if len(quotas) != len(set(quotas)):
            raise ValueError(f"{wave_id} has a shared exclusive quota scope")
    if seen != WAVES.keys():
        raise ValueError("Fixed W1-W4 concurrency membership must be preserved")
    for identity, profile in profiles.items():
        if profile["cpu_local"] != CPU_LOCAL.get(identity):
            raise ValueError(f"{identity} changes its CPU-local model workload")
    observations = []
    if check_ports:
        for transport, port in sorted({endpoint for endpoint in endpoints.values() if endpoint is not None}):
            kind = socket.SOCK_DGRAM if transport == "udp" else socket.SOCK_STREAM
            with socket.socket(socket.AF_INET, kind) as sock:
                if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                row = {"transport": transport, "host": "127.0.0.1", "port": port}
                try:
                    sock.bind(("127.0.0.1", port))
                    row["available"] = True
                except OSError as error:
                    row.update(available=False, error=error.errno)
                observations.append(row)
    count = sum(len(row["early_feasibility"]["confirmed"]) for row in findings)
    status = "unverified" if count == 0 else "early_confirmed" if count == len(PROFILE_IDS) * len(SCOPES) else "partially_confirmed"
    return {"catalog": str(path), "scope": PROTOCOL, "new_protocol_status": status,
            "final_admission": {"owner": "R6", "quality": "pending_r6", "time": "pending_r6"},
            "findings": findings, "waves": catalog["waves"], "port_observations": observations,
            "limits": catalog["native_limitations"],
            "port_check_scope": "Instantaneous loopback TCP/UDP bind only; occupied app listeners may be expected. Not authentication, input/output proof, reservation or admission."}
