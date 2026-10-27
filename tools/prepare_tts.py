"""R3 OpenRouter preparation, bounded generation/accounting, and reviewed split.

No command grants approval or certifies speech. prepare is offline and never reads
credentials. Development is six CLIENT POSTs/$1; main is nine/$1.50 and requires
separate spending approval plus an adopted-pilot-method attestation. No retries,
turn fallback or provider pinning. Directions never enter the spoken transcript.
"""
from __future__ import annotations

import argparse
from array import array
from contextlib import contextmanager
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from email.message import Message
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
import wave


MODEL = "google/gemini-3.8-flash-tts"
ENDPOINT = "https://openrouter.ai/api/v1/audio/speech"
GENERATION_ENDPOINT = "https://openrouter.ai/api/v1/generation"
KEY_NAME = "VRC_BENCH_GEMINI_API_KEY"  # Owner-selected .env.local name, holding an OpenRouter key.
RATE = 24000
ATTEMPT_USD = Decimal("0.151552")
CAP_USD = Decimal("1.00")
EXPIRY = date(2026, 12, 31)
SCOPE = "six-openrouter-development-whole-dialogue-client-posts"
MAIN_SCOPE = "nine-openrouter-main-whole-dialogue-client-posts"
MAIN_CAP_USD = Decimal("1.50")
METHOD_SCOPE = "r3-adopted-whole-dialogue-pilot-method"
RATES = {"input_text": "0.50", "output_audio": "9.00"}
POLICY = {"data_collection": "deny", "zdr": True}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
GENERATION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,511}\Z")
INSTRUCTIONS = (
    "Natural informal dialogue between two attentive peers, with conversational pacing and modest contextual intonation. "
    "Avoid announcer delivery, recitation, and exaggerated acting. Read the supplied text verbatim, preserving meaningful "
    "hesitations, self-corrections, negatives, numbers, conditions, names, and turn order. Add no words or vocalizations. "
    "Do not speak labels or instructions. Take turns without overlap."
)
ACCOUNTING_FIELDS = ("total_cost", "usage", "native_tokens_prompt", "native_tokens_completion", "tokens_prompt",
                     "tokens_completion", "provider_name", "model", "upstream_id", "native_finish_reason",
                     "finish_reason", "is_byok", "request_id", "provider_responses")


def sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def save_new(path, payload):
    """Exclusive, flushed publication; interrupted files are never overwritten."""
    with Path(path).open("xb") as target:
        target.write(payload)
        target.flush()
        os.fsync(target.fileno())


def save_json(path, value):
    save_new(path, json_bytes(value))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identifier(value):
    require(isinstance(value, str) and IDENTIFIER.fullmatch(value), "Invalid local identifier")
    return value


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def phase_contract(scope):
    """Only the two owner-authorized batches, never arbitrary budget configuration."""
    if scope == SCOPE:
        return "development", 6, CAP_USD, "pilot"
    require(scope == MAIN_SCOPE, "Unsupported generation scope")
    return "main", 9, MAIN_CAP_USD, "main"


def check_ready(bundle):
    require(bundle["schema_version"] == 1, "Unsupported script schema")
    require(bundle.get("preparation_status") != "draft_pending_source_restore_and_bilingual_review",
            "Draft scripts are not TTS-ready")
    require(all(not episode.get("unresolved_source_spans") for episode in bundle["episodes"]),
            "Unresolved source spans block TTS preparation/generation")


def request_for(episode):
    require(not episode.get("unresolved_source_spans"), "Unresolved source spans block generation")
    return {"model": MODEL, "input": [{"text": turn["text"], "voice": "Puck" if turn["role"] == "A" else "Kore"}
                                     for turn in episode["turns"]],
            "instructions": INSTRUCTIONS, "response_format": "pcm",
            "provider": {**POLICY, "options": {"google-ai-studio": {"maxOutputTokens": 16384},
                                               "google-vertex": {"maxOutputTokens": 16384}}}}


def validate_bundle(bundle, parents_path, catalogue_path, source_cache, split="development"):
    """Primary manifest/catalogue/CSV ancestry check, not semantic certification.

    Original reference digests remain identities only: absent historical JSON/ASR
    bodies are neither recreated nor claimed verified by this R3 derivation.
    """
    require(split in ("development", "main"), "Unsupported preparation split")
    check_ready(bundle)
    parent_bytes, catalogue_bytes = Path(parents_path).read_bytes(), Path(catalogue_path).read_bytes()
    require(bundle["parent_manifest_sha256"] == sha256(parent_bytes), "Parent manifest checksum mismatch")
    manifest, catalogue = json.loads(parent_bytes), json.loads(catalogue_bytes)
    require(manifest["catalogue_sha256"] == sha256(catalogue_bytes), "Frozen catalogue checksum mismatch")
    require(manifest["root_dataset"] == catalogue["dataset"] and manifest["root_revision"] == catalogue["revision"]
            and manifest["source_license"] == catalogue["license"], "Parent catalogue root identity mismatch")
    metadata, tables = {}, {}
    for name, spec in catalogue["source_metadata"].items():
        require(name in ("train_metadata.csv", "test_metadata.csv", "validation_metadata.csv"), "Unexpected source CSV name")
        payload = (Path(source_cache) / name).read_bytes()
        require(len(payload) == spec["bytes"] and sha256(payload) == spec["sha256"], "Pinned source CSV checksum mismatch")
        metadata[name] = spec["sha256"]
        tables[name.removesuffix("_metadata.csv")] = list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))
    parents = {p["id"]: p for p in manifest["parents"]}
    candidates = {c["id"]: c for c in catalogue["candidates"] if c["kind"] == "T1"}
    require(len(parents) == len(manifest["parents"]), "Duplicate parent identity")
    episodes, seen, identities, used_keys, source_records = {}, set(), set(), set(), []
    for episode in bundle["episodes"]:
        identity, parent_id = identifier(episode["id"]), episode["parent_id"]
        require(identity not in identities and parent_id not in seen, "Duplicate episode or parent")
        identities.add(identity)
        seen.add(parent_id)
        require(parent_id in parents and parent_id in candidates, "Foreign parent")
        parent, candidate = parents[parent_id], candidates[parent_id]
        for field in ("source_case_id", "dependency_group_id", "project_split"):
            require(episode[field] == parent[field] == candidate[field], "Parent identity or split mismatch")
        require(episode["project_split"] == split, "Mixed or wrong preparation split")
        require(episode["parent_reference_sha256"] == parent["reference_sha256"], "Expected reference identity mismatch")
        require(parent["roles"] == candidate["roles"] and set(parent["roles"]) == {"A", "B"}
                and len(set(parent["roles"].values())) == 2, "Invalid fixed parent roles")
        mapping, clips = parent["source_to_playback"], candidate["clips"]
        require(len(mapping) == len(clips) and mapping, "Missing parent source membership")
        runs, source_ids, entries = [], set(), []
        for entry, clip in zip(mapping, clips):
            role, annotation, key = entry["role"], entry["annotation_L"], entry["natural_source_key"]
            require(role in ("A", "B") and type(annotation) is int and annotation > 0
                    and annotation not in source_ids and key not in used_keys, "Invalid or duplicate source membership")
            require((key, annotation, role, entry["original_person"]) ==
                    (clip["natural_source_key"], clip["annotation_L"], clip["logical_role"], clip["original_speaker_id"])
                    and entry["original_person"] == parent["roles"][role], "Source person/order/membership mismatch")
            source_split, source_id = clip["upstream_split"], clip["upstream_id"]
            index = int(source_id)
            require(source_id == f"{index:05}" and 0 <= index < len(tables[source_split]), "Invalid split-local source row")
            row = tables[source_split][index]
            require(key == f"{catalogue['dataset']}@{catalogue['revision']}/{source_split}/{source_id}", "Source revision mismatch")
            require(row["file_name"] == clip["archive_member"] and int(row["original_speaker_id"]) == entry["original_person"],
                    "Original source file/person mismatch")
            require(sha256(row["transcription"].encode("utf-8")) == clip["reference_utf8_sha256"], "Original source text checksum mismatch")
            source_ids.add(annotation)
            used_keys.add(key)
            entries.append({"annotation_L": annotation, "role": role, "original_person": entry["original_person"],
                            "natural_source_key": key, "source_file": clip["archive_member"],
                            "reference_utf8_sha256": clip["reference_utf8_sha256"]})
            if runs and runs[-1][0] == role:
                runs[-1][1].append(annotation)
            else:
                runs.append((role, [annotation]))
        turns = episode["turns"]
        require(len(turns) == len(runs) and {r[0] for r in runs} == {"A", "B"}, "Missing complete source runs")
        turn_ids = set()
        for turn, (role, annotations) in zip(turns, runs):
            turn_id = identifier(turn["id"])
            require(turn_id not in turn_ids, "Duplicate turn identity")
            turn_ids.add(turn_id)
            require(turn["role"] == role and isinstance(turn["source_annotation_Ls"], list)
                    and all(type(value) is int for value in turn["source_annotation_Ls"])
                    and turn["source_annotation_Ls"] == annotations,
                    "Turns must preserve ordered complete same-speaker source runs")
            require(nonempty(turn["text"]) and "|reaction|" not in turn["text"], "Invalid dialogue text or overlap directive")
            notes = turn["adaptation_notes"]
            require(isinstance(notes, str) or (isinstance(notes, list) and all(isinstance(n, str) for n in notes)),
                    "Adaptation notes must be text or a text list")
        episodes[parent_id] = episode
        source_records.append({"parent_id": parent_id, "expected_parent_reference_sha256": parent["reference_sha256"],
                               "original_reference_body_verified": False, "source_entries": entries})
    development = [p["id"] for p in manifest["parents"] if p["project_split"] == "development"]
    require(len(development) == 4, "Frozen manifest needs four development parents")
    selected = [p["id"] for p in manifest["parents"] if p["project_split"] == split]
    require(len(selected) == (4 if split == "development" else 9) and set(selected) == episodes.keys(),
            "Preparation requires the exact complete selected split")
    require(manifest["development_additional_take_parent_ids"] == [development[0], development[2]],
            "Additional takes must remain development parents 1 and 3")
    provenance = {"schema_version": 1, "parent_manifest_sha256": sha256(parent_bytes), "catalogue_sha256": sha256(catalogue_bytes),
                  "source_metadata_sha256": metadata, "parents": source_records, "development_parent_ids": development,
                  "original_reference_bodies_verified": False, "original_r2_handoff_complete": False,
                  "limitation": "Source-linked R3 derivation only; original reference/curation/ASR bodies are not recreated or verified. Shape does not certify JA/KO semantics."}
    return episodes, selected, provenance


def prepare(scripts, parents, source_cache, output, catalogue=None, split="development"):
    catalogue = catalogue or Path(__file__).resolve().parents[1] / "corpus/r2/ascend.json"
    scripts_bytes = Path(scripts).read_bytes()
    bundle = json.loads(scripts_bytes)
    episodes, selected, provenance = validate_bundle(bundle, parents, catalogue, source_cache, split)
    scope = SCOPE if split == "development" else MAIN_SCOPE
    _, count, cap, prefix = phase_contract(scope)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "requests").mkdir()
    save_new(output / "scripts.json", scripts_bytes)
    provenance_bytes = json_bytes(provenance)
    save_new(output / "source-validation.json", provenance_bytes)
    requests = []
    for episode in episodes.values():
        payload = json_bytes(request_for(episode))
        path = "requests/" + episode["id"] + ".json"
        save_new(output / path, payload)
        requests.append({"episode_id": episode["id"], "parent_id": episode["parent_id"],
                         "source_case_id": episode["source_case_id"], "dependency_group_id": episode["dependency_group_id"],
                         "parent_reference_sha256": episode["parent_reference_sha256"],
                         "project_split": episode["project_split"], "path": path, "sha256": sha256(payload)})
    sequence = selected + [selected[0], selected[2]] if split == "development" else selected
    calls = [{"id": f"{prefix}-{i:02}", "episode_id": episodes[parent_id]["id"], "take": 2 if i > 4 and split == "development" else 1}
             for i, parent_id in enumerate(sequence, 1)]
    plan = {"schema_version": 1, "run_id": uuid.uuid4().hex, "scope": scope, "model": MODEL, "api": ENDPOINT,
            "api_docs": ["https://openrouter.ai/docs/api/api-reference/tts/create-speech",
                         "https://openrouter.ai/docs/guides/overview/multimodal/tts",
                         "https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation"],
            "transport": "Python stdlib urllib, no client retries/proxy/redirect",
            "scripts_sha256": sha256(scripts_bytes), "source_validation_sha256": sha256(provenance_bytes),
            "parent_manifest_sha256": bundle["parent_manifest_sha256"], "requests": requests, "calls": calls,
            "max_client_posts": count, "client_post_reservation_usd": str(ATTEMPT_USD), "api_cap_usd": str(cap),
            ("six_client_posts_estimate_usd" if split == "development" else "nine_client_posts_estimate_usd"): str(ATTEMPT_USD * count),
            "rates_usd_per_million": RATES,
            "rates_valid_through": EXPIRY.isoformat(), "provider_policy": POLICY,
            "budget_limitations": "Conditional current-rate token estimate, not observed cap enforcement or a bound on router upstream attempts. Stop on rate/limit changes; no automatic refill.",
            "documented_token_limits": {"input": 8192, "output": 16384, "effective_enforcement_observed": False},
            "roles": {"A": {"voice": "Puck", "language": "ja", "channel": "peer"},
                      "B": {"voice": "Kore", "language": "ko", "channel": "self"}},
            "status": "prepared_not_authorized_not_audio_reviewed",
            "unknown_costs": ["cash_paid", "credit_applied", "purchase_fees", "taxes_fx", "human_review", "editing"],
            "privacy_limit": "ZDR/data-collection filters are requested, not a provider pin or independently certified universal retention policy.",
            "limits": "Source shape and cost arithmetic are not content/speaker certification; main requires adopted pilot method evidence."}
    if split == "main":
        plan.update({"main_parent_ids": selected, "pilot_development_parent_ids": provenance["development_parent_ids"],
                     "instructions_sha256": sha256(INSTRUCTIONS.encode("utf-8"))})
    save_json(output / "plan.json", plan)
    return {"plan_sha256": sha256((output / "plan.json").read_bytes()), "planned_client_posts": len(calls), "status": plan["status"]}


def load_key(env_file):
    """Parse only the exact owner-selected literal assignment; never source dotenv."""
    values = []
    for line in Path(env_file).read_text(encoding="utf-8-sig").splitlines():
        match = re.fullmatch(r"\s*(?:export\s+)?" + KEY_NAME + r"\s*=(.*)", line)
        if match:
            value = match[1].strip()
            if value[:1] in ("'", '"'):
                require(len(value) >= 2 and value[-1] == value[0], "Invalid literal key assignment")
                value = value[1:-1]
            values.append(value)
    require(len(values) == 1 and nonempty(values[0]), "Exactly one literal dedicated key assignment is required")
    key = values[0]
    require(not any(c.isspace() for c in key) and not any(c in key for c in "$`%\\\"'"),
            "Key must be literal, without expansion, execution or escapes")
    return key


@contextmanager
def run_lock(run):
    lock = Path(run) / ".generate.lock"
    try:
        with lock.open("xb") as target:
            target.write(b"Exclusive R3 operation lock; do not automatically reclaim.\n")
            target.flush()
            os.fsync(target.fileno())
    except FileExistsError:
        raise ValueError("Run is locked; uncertain attempts require manual investigation") from None
    try:
        yield
    finally:
        lock.unlink()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_once(request):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        response = opener.open(request, timeout=180)
    except urllib.error.HTTPError as failure:
        response = failure
    with response:
        # Never enumerate/log response headers or authorization-bearing request objects.
        headers = {name: response.headers.get(name) for name in ("Content-Type", "X-Generation-Id")
                   if response.headers.get(name) is not None}
        try:
            return response.status, headers, response.read(), True
        except http.client.IncompleteRead as failure:
            return response.status, headers, failure.partial, False
        except Exception:
            # Headers are already evidence even when no body bytes are available.
            # Never invent partial bytes from a timeout or log its exception text.
            return response.status, headers, b"", False


def post_once(payload, key):
    return open_once(urllib.request.Request(ENDPOINT, data=payload, method="POST",
                     headers={"Content-Type": "application/json", "Authorization": "Bearer " + key}))


def get_generation_once(generation_id, key):
    url = GENERATION_ENDPOINT + "?" + urllib.parse.urlencode({"id": generation_id})
    return open_once(urllib.request.Request(url, method="GET", headers={"Authorization": "Bearer " + key}))


def safe_response(payload, key):
    for secret in (key.encode("utf-8"), json.dumps(key)[1:-1].encode("utf-8")):
        payload = payload.replace(secret, b"[REDACTED]")
    return payload


def response_metadata(status, headers, complete, key):
    return {"http_status": status, "body_complete": complete,
            "headers": {name: safe_response(headers[name].encode("utf-8"), key).decode("utf-8")
                        for name in ("Content-Type", "X-Generation-Id") if name in headers}}


def generation_id_from(metadata):
    value = metadata["headers"].get("X-Generation-Id")
    return value if isinstance(value, str) and GENERATION_ID.fullmatch(value) else None


def inspect_pcm(body, content_type):
    message = Message()
    message["Content-Type"] = content_type or ""
    params = message.get_params() or []
    require(message.get_content_type() == "audio/pcm" and len(params) == 3
            and dict(params[1:]) == {"rate": "24000", "channels": "1"}, "Expected mono 24000 Hz PCM Content-Type")
    require(body and len(body) % 2 == 0 and not body.startswith(b"RIFF"), "Empty, odd/truncated, or RIFF-mislabeled PCM")
    return {"status": "generated_pending_actual_audio_review", "pcm16le_sha256": sha256(body),
            "sample_rate": RATE, "frames": len(body) // 2, "audio_seconds": len(body) / (2 * RATE),
            "completion_limit": "HTTP/PCM validity supplies no dialogue-completion, fidelity, speaker or timestamp proof."}


def checked_run(run):
    plan_bytes = (run / "plan.json").read_bytes()
    plan = json.loads(plan_bytes)
    split, count, cap, prefix = phase_contract(plan["scope"])
    require(plan["api"] == ENDPOINT and plan["model"] == MODEL
            and plan["max_client_posts"] == count and plan["api_cap_usd"] == str(cap)
            and plan["client_post_reservation_usd"] == str(ATTEMPT_USD) and plan["rates_valid_through"] == EXPIRY.isoformat()
            and plan["rates_usd_per_million"] == RATES and plan["provider_policy"] == POLICY, "Unsupported generation plan")
    scripts_bytes = (run / "scripts.json").read_bytes()
    require(sha256(scripts_bytes) == plan["scripts_sha256"], "Frozen script bytes changed")
    require(sha256((run / "source-validation.json").read_bytes()) == plan["source_validation_sha256"], "Frozen source evidence changed")
    bundle = json.loads(scripts_bytes)
    check_ready(bundle)
    episodes = {episode["id"]: episode for episode in bundle["episodes"]}
    requests = {}
    for entry in plan["requests"]:
        expected_path = "requests/" + identifier(entry["episode_id"]) + ".json"
        require(entry["path"] == expected_path, "Invalid frozen request path")
        payload = (run / expected_path).read_bytes()
        require(sha256(payload) == entry["sha256"] and payload == json_bytes(request_for(episodes[entry["episode_id"]])),
                "Frozen request bytes changed")
        requests[entry["episode_id"]] = payload
    calls = plan["calls"]
    require(len(calls) == count and [c["id"] for c in calls] == [f"{prefix}-{i:02}" for i in range(1, count + 1)],
            "Invalid fixed batch sequence")
    if split == "development":
        require([c["episode_id"] for c in calls[4:]] == [calls[0]["episode_id"], calls[2]["episode_id"]]
                and len({c["episode_id"] for c in calls[:4]}) == 4, "Invalid development repeat sequence")
    else:
        require(len(episodes) == len(bundle["episodes"]) == len(requests) == len(plan["requests"]) == 9
                and set(c["episode_id"] for c in calls) == episodes.keys() == requests.keys()
                and all(c["take"] == 1 for c in calls), "Main requires nine distinct one-take requests")
        require([episodes[c["episode_id"]]["parent_id"] for c in calls] == plan["main_parent_ids"]
                and len(set(plan["main_parent_ids"])) == 9, "Invalid exact main parent sequence")
        require(len(plan["pilot_development_parent_ids"]) == len(set(plan["pilot_development_parent_ids"])) == 4
                and plan["instructions_sha256"] == sha256(INSTRUCTIONS.encode("utf-8")), "Invalid pilot method identities")
    require(all(episodes[c["episode_id"]]["project_split"] == split for c in calls), "Wrong generation split")
    return plan, sha256(plan_bytes), requests


def checked_pilot_method(plan, approval, receipt_path):
    """Check a bound review attestation, not proof that its factual claims are true."""
    require(receipt_path is not None, "Main generation requires adopted pilot method evidence")
    payload = Path(receipt_path).read_bytes()
    require(sha256(payload) == approval["pilot_method_receipt_sha256"], "Pilot method receipt checksum mismatch")
    receipt = json.loads(payload)
    require(receipt["schema_version"] == 1 and receipt["scope"] == METHOD_SCOPE
            and receipt["parent_manifest_sha256"] == plan["parent_manifest_sha256"]
            and receipt["model"] == MODEL and receipt["voices"] == {"A": "Puck", "B": "Kore"}
            and receipt["instructions_sha256"] == plan["instructions_sha256"]
            and receipt["development_parent_ids"] == plan["pilot_development_parent_ids"],
            "Foreign or incompatible pilot method evidence")
    require(isinstance(receipt.get("pilot_plan_sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", receipt["pilot_plan_sha256"]), "Pilot plan identity is required")
    require(all(receipt.get(flag) is True for flag in
                ("actual_ja_ko_quality_review_approved", "actual_role_boundary_verification_approved", "method_adopted")),
            "Pilot quality and actual role-boundary review must precede method adoption")
    require(all(nonempty(receipt.get(field)) for field in ("reviewer", "reviewed_at", "evidence")),
            "Pilot method reviewer evidence is required")
    return payload


def check_run_directory(run, approval):
    directory = approval.get("run_directory")
    require(nonempty(directory) and Path(directory).is_absolute()
            and Path(directory).resolve() == run.resolve(), "Approval binds one canonical run directory")


def accounting_cost(value):
    if value is None:
        return None
    require(type(value) in (int, float, str), "Invalid retained accounting cost")
    try:
        cost = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Invalid retained accounting cost") from None
    require(cost.is_finite() and cost >= 0, "Invalid retained accounting cost")
    return cost


def check_retained_budget(attempts, consumed, cap):
    exposure, known_total = Decimal(0), Decimal(0)
    for call_id in consumed:
        reconciliation = attempts / call_id / "reconciliation"
        cost = None
        if reconciliation.exists():
            # An interrupted/malformed accounting record needs investigation, not
            # a silent replacement with zero. Ordinary missing usage remains null.
            record = json.loads((reconciliation / "result.json").read_bytes())
            require(record["status"] in ("accounting_recorded", "accounting_unknown"), "Invalid retained accounting status")
            cost = accounting_cost(record["api_consumption_usd"])
            reported = accounting_cost(record["metadata"]["total_cost"])
            require(cost == reported, "Retained accounting costs disagree")
            if cost is not None:
                require(cost < cap, "Known consumption exhausts approved phase cap")
                require(cost <= ATTEMPT_USD, "Recorded cost contradicts documented client-POST reservation")
                known_total += cost
        # Reconciled small/zero costs never refund reserved allowance or slots.
        exposure += ATTEMPT_USD if cost is None else max(ATTEMPT_USD, cost)
    require(known_total < cap and exposure + ATTEMPT_USD <= cap, "Consumption/reservations exhaust approved phase cap")


def generate(run, approval_path, call_id, env_file, pilot_method=None):
    run = Path(run)
    with run_lock(run):
        plan, plan_hash, requests = checked_run(run)
        split, count, cap, _ = phase_contract(plan["scope"])
        approval_bytes = Path(approval_path).read_bytes()
        approval = json.loads(approval_bytes)
        check_run_directory(run, approval)
        require(approval["schema_version"] == 1 and approval["plan_sha256"] == plan_hash, "Approval must bind exact plan bytes")
        require(approval["scope"] == plan["scope"] and approval["max_client_posts"] == count and approval["api_cap_usd"] == str(cap)
                and approval["api"] == ENDPOINT and approval["model"] == MODEL
                and approval["rates_usd_per_million"] == RATES and approval["provider_policy"] == POLICY, "Approval route/rates/policy/scope mismatch")
        require(all(approval.get(flag) is True for flag in ("setup_confirmed", "terms_and_rights_confirmed", "scripts_approved")),
                "Explicit owner confirmations are required")
        require(all(nonempty(approval.get(f)) for f in ("owner", "approved_at", "approval_source", "approval_evidence")),
                "Record explicit owner confirmation source and faithful scope; never record a key")
        require(datetime.now(timezone.utc).date() <= date.fromisoformat(approval["expires_on"]) <= EXPIRY,
                "Approval or current-rate budget has expired")
        method_bytes = checked_pilot_method(plan, approval, pilot_method) if split == "main" else None
        attempts = run / "attempts"
        attempts.mkdir(exist_ok=True)
        calls = plan["calls"]
        consumed = {p.name for p in attempts.iterdir()}
        require(consumed == {c["id"] for c in calls[:len(consumed)]}, "Unrecognized attempt state; stop for investigation")
        require(len(consumed) < count, "Phase client-POST allowance exhausted")
        check_retained_budget(attempts, consumed, cap)
        call = calls[len(consumed)]
        require(call_id == call["id"], "Submit only the next planned client POST; retries are not authorized")
        require(not Path(env_file).resolve().is_relative_to(run.resolve()), "Selected secret file must stay outside run outputs")
        key = load_key(env_file)
        require(key not in json.dumps(approval, ensure_ascii=False), "Approval must be secret-free")
        require(method_bytes is None or key not in method_bytes.decode("utf-8"), "Pilot method receipt must be secret-free")
        attempt = attempts / call_id
        attempt.mkdir()  # Existence alone consumes this client-POST slot after interruption.
        save_new(attempt / "approval.json", approval_bytes)
        reservation = {"category": "pilot" if split == "development" else "production", "call": call, "plan_sha256": plan_hash,
                       "request_sha256": sha256(requests[call["episode_id"]]), "approval_sha256": sha256(approval_bytes),
                       "reserved_at": datetime.now(timezone.utc).isoformat(), "reserved_usd": str(ATTEMPT_USD),
                       "status": "reserved_outcome_unknown", "client_post_allowance_consumed": True,
                       "upstream_attempt_count": None}
        if method_bytes is not None:
            save_new(attempt / "pilot-method.json", method_bytes)
            reservation["pilot_method_receipt_sha256"] = sha256(method_bytes)
        save_json(attempt / "reservation.json", reservation)
        result = {"status": "uncertain_transport_or_local_failure", "generation_id": None, "usage": None,
                  "api_consumption_usd": None, "billing_status": "unknown_pending_reconciliation", "adopted": False}
        try:
            status, headers, body, complete = post_once(requests[call["episode_id"]], key)
            metadata = response_metadata(status, headers, complete, key)
            save_json(attempt / "response-metadata.json", metadata)
            result.update({"http_status": status, "generation_id": generation_id_from(metadata)})
            if 200 <= status < 300 and headers.get("Content-Type", "").lower().startswith("audio/"):
                # PCM stays byte-identical; never redact/alter it into a different take.
                require(key.encode("utf-8") not in body, "Credential echo cannot be retained as audio")
                save_new(attempt / "audio.pcm", body)
                result["raw_audio_sha256"] = sha256(body)
                result["raw_audio_bytes"] = len(body)
                try:
                    require(complete, "Incomplete HTTP audio body")
                    inspected = inspect_pcm(body, headers.get("Content-Type"))
                    wav = encode_wave(body)
                    save_new(attempt / "audio.wav", wav)
                    result.update(inspected)
                    result["wav_sha256"] = sha256(wav)
                except ValueError:
                    result["status"] = "failed_response_retained"
            else:
                save_new(attempt / "response.safe.bin", safe_response(body, key))
                result["status"] = "failed_response_retained"
        except Exception:
            # No provider exception messages, authorization headers or secret paths.
            result["status"] = "uncertain_transport_or_local_failure"
        finally:
            save_json(attempt / "result.json", result)
        return {"call_id": call_id, "status": result["status"], "client_post_allowance_consumed": True,
                "reserved_client_posts": len(consumed) + 1}


def reconcile(run, call_id, env_file):
    """One explicit accounting GET per retained attempt, never polling or refund."""
    run = Path(run)
    identifier(call_id)
    with run_lock(run):
        plan, plan_hash, _ = checked_run(run)
        require(call_id in {c["id"] for c in plan["calls"]}, "Foreign generation call")
        attempt = run / "attempts" / call_id
        reservation = json.loads((attempt / "reservation.json").read_bytes())
        require(reservation["plan_sha256"] == plan_hash, "Reservation plan mismatch")
        approval = json.loads((attempt / "approval.json").read_bytes())
        check_run_directory(run, approval)
        generated = json.loads((attempt / "result.json").read_bytes())
        metadata = json.loads((attempt / "response-metadata.json").read_bytes())
        generation_id = generation_id_from(metadata)
        require(generation_id and generated["generation_id"] == generation_id, "No safe recorded generation ID to reconcile")
        output = attempt / "reconciliation"
        require(not output.exists(), "Accounting lookup already attempted; no polling/retry")
        require(not Path(env_file).resolve().is_relative_to(run.resolve()), "Selected secret file must stay outside run outputs")
        key = load_key(env_file)
        output.mkdir()
        save_json(output / "reservation.json", {"generation_id": generation_id, "plan_sha256": plan_hash,
                  "requested_at": datetime.now(timezone.utc).isoformat(), "scope": "one-non-generative-accounting-GET"})
        result = {"status": "accounting_unknown", "generation_id": generation_id,
                  "metadata": {field: None for field in ACCOUNTING_FIELDS}, "api_consumption_usd": None,
                  "billing_status": "unknown_pending_reconciliation", "client_post_allowance_changed": False}
        try:
            status, headers, body, complete = get_generation_once(generation_id, key)
            save_json(output / "response-metadata.json", response_metadata(status, headers, complete, key))
            body = safe_response(body, key)
            save_new(output / "response.safe.json", body)
            require(200 <= status < 300 and complete, "Accounting HTTP request failed/incomplete")
            data = json.loads(body)["data"]
            require(isinstance(data, dict) and data.get("id", generation_id) == generation_id, "Accounting identity mismatch")
            result["metadata"] = {field: data.get(field) for field in ACCOUNTING_FIELDS}
            cost = data.get("total_cost")
            if cost is not None:
                accounting_cost(cost)
                result["api_consumption_usd"] = cost
                result["billing_status"] = "reported_model_consumption_not_cash_or_credit_proof"
            result["status"] = "accounting_recorded"
        except Exception:
            result["status"] = "accounting_unknown"
        finally:
            save_json(output / "result.json", result)
        return {"call_id": call_id, "status": result["status"], "api_consumption_usd": result["api_consumption_usd"],
                "client_post_allowance_changed": False}


def encode_wave(pcm):
    target = io.BytesIO()
    with wave.open(target, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes(pcm)
    return target.getvalue()


def decode_wave(payload):
    try:
        with wave.open(io.BytesIO(payload), "rb") as source:
            require((source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype())
                    == (1, 2, RATE, "NONE"), "Audio must be mono PCM16 WAV at 24000 Hz")
            frames = source.getnframes()
            pcm = source.readframes(frames + 1)
    except (wave.Error, EOFError) as failure:
        raise ValueError("Malformed WAV") from failure
    require(frames > 0 and len(pcm) == frames * 2, "Empty or truncated WAV")
    require(len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WAVE"
            and int.from_bytes(payload[4:8], "little") + 8 == len(payload), "Truncated or inconsistent RIFF size")
    return pcm


def samples(pcm):
    values = array("h", pcm)
    if sys.byteorder != "little":
        values.byteswap()
    return values


def split(wav_path, review_path, output):
    wav, review_bytes = Path(wav_path).read_bytes(), Path(review_path).read_bytes()
    review = json.loads(review_bytes)
    require(review["schema_version"] == 1 and review["wav_sha256"] == sha256(wav), "Review must bind exact WAV bytes")
    require(review.get("actual_audio_reviewed") is True
            and all(nonempty(review.get(f)) for f in ("reviewer", "reviewed_at", "evidence", "silence_policy")),
            "Explicit actual-audio review evidence and silence policy are required")
    pcm = decode_wave(wav)
    frames, cursor = len(pcm) // 2, 0
    roles = {"A": bytearray(len(pcm)), "B": bytearray(len(pcm))}
    seen = set()
    for interval in review["intervals"]:
        start, end, role = interval["start_sample"], interval["end_sample"], interval["role"]
        require(type(start) is int and type(end) is int and start == cursor and start < end <= frames
                and role in roles, "Reviewed intervals must be nonoverlapping integer ranges covering all samples")
        roles[role][start * 2:end * 2] = pcm[start * 2:end * 2]
        seen.add(role)
        cursor = end
    require(cursor == frames and seen == {"A", "B"}, "Reviewed intervals must cover entire WAV and both roles")
    require(all(a + b == original for a, b, original in zip(samples(roles["A"]), samples(roles["B"]), samples(pcm))),
            "Role PCM sum does not reconstruct original")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    save_new(output / "original.wav", wav)
    save_new(output / "review.json", review_bytes)
    assets = {}
    for role, buffer in roles.items():
        payload = encode_wave(buffer)
        save_new(output / (role + ".wav"), payload)
        assets[role] = {"path": role + ".wav", "wav_sha256": sha256(payload),
                        "pcm16le_sha256": sha256(buffer), "frames": frames,
                        "channel": "peer" if role == "A" else "self"}
    report = {"schema_version": 1, "status": "split_not_adopted", "adopted": False,
              "original_wav_sha256": sha256(wav), "original_pcm16le_sha256": sha256(pcm),
              "review_sha256": sha256(review_bytes), "sample_rate": RATE, "frames": frames,
              "intervals": review["intervals"], "silence_policy": review["silence_policy"], "assets": assets,
              "clock": "actual generated audio sample positions, not parent timing",
              "reconstruction": "exact PCM arithmetic passed; NOT speaker/content certification",
              "actual_audio_review": "reviewer assertion recorded, not independently certified by this tool"}
    save_json(output / "timeline.json", report)
    return {"status": report["status"], "frames": frames, "pcm_reconstruction": "passed"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preparation = commands.add_parser("prepare", help="Offline immutable source-linked requests; no credentials/network")
    for name in ("scripts", "parents", "source-cache", "output"):
        preparation.add_argument("--" + name, required=True)
    preparation.add_argument("--catalogue", default=str(Path(__file__).resolve().parents[1] / "corpus/r2/ascend.json"))
    preparation.add_argument("--split", choices=("development", "main"), default="development")
    generation = commands.add_parser("generate", help="One explicitly approved phase call, never retry")
    for name in ("run", "approval", "call", "env-file"):
        generation.add_argument("--" + name, required=True)
    generation.add_argument("--pilot-method", help="Main-only adopted method receipt, hash-bound by main approval")
    accounting = commands.add_parser("reconcile", help="One explicit non-generative accounting GET; no polling/refill")
    for name in ("run", "call", "env-file"):
        accounting.add_argument("--" + name, required=True)
    splitting = commands.add_parser("split", help="Apply recorded actual-audio boundaries without adopting")
    for name in ("wav", "review", "output"):
        splitting.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare(args.scripts, args.parents, args.source_cache, args.output, args.catalogue, args.split)
        elif args.command == "generate":
            result = generate(args.run, args.approval, args.call, args.env_file, args.pilot_method)
        elif args.command == "reconcile":
            result = reconcile(args.run, args.call, args.env_file)
        else:
            result = split(args.wav, args.review, args.output)
    except (ValueError, OSError, KeyError, TypeError):
        print("R3 operation blocked or failed; no automatic retry was made. Inspect retained state and required inputs/authorization.", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return int((args.command == "generate" and result["status"] != "generated_pending_actual_audio_review")
               or (args.command == "reconcile" and result["status"] != "accounting_recorded"))


if __name__ == "__main__":
    raise SystemExit(main())
