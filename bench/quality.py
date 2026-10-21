from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from pathlib import Path

from .activity import exclusive_activity
from .metrics_alignment import require_current_extraction
from .quality_prompts import SUPPORTED_VERSIONS, VERSION, blinded_input, fingerprint, parse_result, prompt, sanity_segments
from .quality_sampling import freeze_samples, interleaved
from .quality_store import QualityStore
from .storage import RunLock, atomic_json, digest, utc_now


def load_plan(root):
    path = Path(root) / "quality-plan.json"
    plan = json.loads(path.read_text(encoding="utf-8"))
    if plan.get("version") not in SUPPORTED_VERSIONS or plan.get("binding") != fingerprint({key: value for key, value in plan.items() if key != "binding"}):
        raise ValueError("Frozen quality plan version/binding mismatch; prepare a new root for changed inputs/prompts")
    for item in plan["reports"]:
        require_current_extraction(item["report"].get("outputs", []))
    for record in plan["records"]:
        if record["input"] is None and record["segment"].get("eligible") is True:
            raise ValueError("Frozen quality plan has an eligible record with unavailable input; prepare a new queue")
    for job in plan["jobs"]:
        if job["prompt"].get("version") != plan["version"] or job.get("prompt_hash") != fingerprint(job["prompt"]):
            raise ValueError("Frozen quality job prompt version/hash mismatch")
    return plan


def make_job(kind, data, record_key, sanity=None):
    request = prompt(kind, data)
    return {"id": fingerprint([kind, record_key]), "kind": kind, "record_key": record_key, "input": data,
            "input_hash": fingerprint(data), "prompt": request, "prompt_hash": fingerprint(request), "sanity": sanity}


def prepare(reports, root, seed=20261020, *, skip_tone=False, skip_korean_review=False):
    root = Path(root)
    evaluation_scope = {"tone": not skip_tone, "korean_review": not skip_korean_review}
    root.mkdir(parents=True, exist_ok=True)
    with RunLock(root):
        if (root / "quality-plan.json").exists():
            plan = load_plan(root)
            if plan.get("evaluation_scope", {"tone": True, "korean_review": True}) != evaluation_scope:
                raise ValueError("Quality root already frozen with different evaluation scope; use a new root")
            if plan["version"] != VERSION:
                raise ValueError("Quality root uses an older frozen prompt version; use a new root for current prompts")
            expected = sorted(digest(path) for path in reports)
            if sorted(item["sha256"] for item in plan["reports"]) != expected or plan["samples"]["seed"] != seed:
                raise ValueError("Quality root already frozen with different inputs/seed; use a new root")
            return plan
        records, originals = [], []
        seen = set()
        for path in reports:
            path = Path(path)
            checksum = digest(path)
            if checksum in seen:
                raise ValueError("Duplicate metrics report input")
            seen.add(checksum)
            report = json.loads(path.read_text(encoding="utf-8"))
            if report.get("schema_version") != 1 or not isinstance(report.get("quality_segments"), list):
                raise ValueError("Expected issue5 metrics report with quality_segments")
            require_current_extraction(report.get("outputs", []))
            originals.append({"sha256": checksum, "path": str(path.resolve()), "report": report})
            ids = set()
            for segment in report["quality_segments"]:
                if segment["id"] in ids:
                    raise ValueError("Duplicate quality segment identity within metrics report")
                ids.add(segment["id"])
                unavailable = bool(segment.get("unresolved_output_ids"))
                if unavailable and segment.get("eligible") is True:
                    raise ValueError("unresolved_output_role quality segment must be ineligible; rederive metrics")
                data = None if unavailable else blinded_input(segment)
                if segment.get("eligible") is True and not data["source_text"].strip():
                    raise ValueError("Eligible quality segment has no reference text")
                key = fingerprint([checksum, segment["id"]])
                records.append({"key": key, "report_sha256": checksum, "segment": segment, "input": data,
                                **({"input_unavailable_reason": "unresolved_output_role"} if unavailable else {})})
        if not records:
            raise ValueError("No quality segments in input reports")
        samples = freeze_samples(records, seed, include_tone=not skip_tone)
        jobs = [make_job("esa", blinded_input(segment), segment["id"], segment["id"]) for segment in sanity_segments()]
        tone_keys = {key for sample in samples.get("tone", {}).values() for key in sample["keys"]}
        for record in interleaved([row for row in records if row["segment"].get("eligible") is True], seed):
            jobs.append(make_job("esa", record["input"], record["key"]))
            if record["key"] in tone_keys:
                jobs.append(make_job("tone", record["input"], record["key"]))
        plan = {"schema_version": 1, "version": VERSION, "created_utc": utc_now(), "reports": originals,
                "records": records, "samples": samples, "jobs": jobs,
                "evaluation_scope": evaluation_scope,
                "synthetic": all(item["report"].get("synthetic") is True for item in originals),
                "limitations": ["Contextual approximately 30-second GEMBA-ESA adaptation, not unchanged standard ESA",
                                "Automatic judgments do not establish human-verified semantic accuracy",
                                "Error-span counts are supplementary annotations, not independent real-error counts",
                                "Japanese-source references remain automatic/exploratory and derived speech content local-only",
                                "PP2 belongs to the planned GPT judge model family; metadata is retained only outside judge prompts"]}
        plan["binding"] = fingerprint(plan)
        atomic_json(root / "quality-plan.json", plan)
        store = QualityStore(root)
        store.close()
        return plan


def check_measurements(capture_roots):
    checked = []
    for root in capture_roots:
        root = Path(root).resolve()
        checked.append(str(root))
        candidates = [root / "ledger.sqlite"] if (root / "ledger.sqlite").is_file() else sorted(root.glob("*/ledger.sqlite"))
        for path in candidates:
            try:
                db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)
                try:
                    count = db.execute("SELECT count(*) FROM attempts WHERE state='running'").fetchone()[0]
                finally:
                    db.close()
            except sqlite3.Error as error:
                raise ValueError(f"Cannot establish measurement state at {path}: {error}") from error
            if count:
                raise ValueError(f"Known capture measurement is running at {path}; judging prohibited")
    return {"checked_capture_roots": checked, "checked_utc": utc_now(),
            "limitation": "Read-only ledger observation plus operator acknowledgement; not a global external-process detector or race-free shared capture lock"}


def bad_sanity(result):
    return result["esa_score"] > 50 or not result["major_error"]


def score(root, transport, model, limit=None, retry_unresolved=False, calibration_only=False,
          measurements_ended=False, capture_roots=(), metricx=None, metricx_only=False, sanity_limitation=None):
    if not isinstance(model, str) or not model.strip():
        raise ValueError("An exposed actual model identity is required for cache selection")
    root = Path(root)
    with RunLock(root), exclusive_activity():
        plan = load_plan(root)
        if (not transport.synthetic or metricx is not None) and not measurements_ended:
            raise ValueError("Real judging and MetricX require --measurements-ended operator acknowledgement")
        if transport.synthetic and not plan["synthetic"]:
            raise ValueError("Controlled synthetic transport is prohibited on non-synthetic metrics reports")
        observation = check_measurements(capture_roots)
        observation["operator_measurements_ended"] = measurements_ended
        store = QualityStore(root)
        try:
            store.recover()
            if not metricx_only or store.get("active_model") is None:
                store.set("active_model", model)
            store.set("measurement_guard", observation)
            store.set("transport", transport.provenance)
            if not metricx_only and sanity_limitation:
                store.set("sanity_limitation", {"model": model, "explanation": sanity_limitation})
            limitation = store.get("sanity_limitation")
            accepted_sanity_limitation = isinstance(limitation, dict) and limitation.get("model") == model
            if not metricx_only:
                for job in plan["jobs"]:
                    cached = store.cached(job, model) if job["sanity"] else None
                    if cached and bad_sanity(cached["result"]):
                        store.set("sanity_investigation", {"call": cached["id"], "model": model,
                                  "reason": "Obvious bad output not given low ESA and a major span; investigate prompt/input before further judging"})
                        break
            latest = store.latest_call() if not metricx_only else None
            if latest and latest["state"] == "completed" and latest["expected_model"] == model and latest["actual_model"] != model:
                store.set("last_pause", "model_identity_changed")
            if not metricx_only and store.get("last_pause") in ("quota", "unavailable", "unresolved", "missing_actual_model_identity") and not retry_unresolved:
                return status_from(plan, store)
            if not metricx_only and store.get("last_pause") == "model_identity_changed":
                if latest and latest["actual_model"] != model:
                    return status_from(plan, store)
            investigation = store.get("sanity_investigation")
            if not metricx_only and investigation and investigation.get("model") == model and not accepted_sanity_limitation:
                store.set("last_pause", "sanity_investigation_required")
                return status_from(plan, store)
            completed = 0
            paused = None
            eligible = set(plan["samples"]["calibration"]["keys"]) if calibration_only else None
            if not metricx_only:
                for job in plan["jobs"]:
                    if eligible is not None and not job["sanity"] and (job["kind"] != "esa" or job["record_key"] not in eligible):
                        continue
                    if store.cached(job, model):
                        continue
                    if store.has_attempt(job, model) and not retry_unresolved:
                        continue
                    if limit is not None and completed >= limit:
                        break
                    call = store.start(job, model, transport.provenance)
                    envelope = {}
                    try:
                        envelope = transport.call(job["prompt"], call)
                        store.raw(call, envelope)
                        if not isinstance(envelope, dict):
                            raise ValueError("Judge transport returned no response object")
                        state = envelope.get("status", "completed")
                        if state != "completed":
                            if state not in ("quota", "unresolved", "failed", "unavailable"):
                                raise ValueError("Unknown judge transport response status")
                            store.finish(call, state, envelope, reason=envelope.get("reason") or "Missing successful judge response")
                            if state in ("quota", "unavailable", "unresolved"):
                                paused = state
                                break
                            completed += 1
                            continue
                        actual = envelope.get("actual_model")
                        if not isinstance(actual, str) or not actual.strip() or not envelope.get("model_identity_evidence"):
                            store.finish(call, "unresolved", envelope, reason="Returned actual model identity not exposed; requested name is not cache evidence")
                            paused = "missing_actual_model_identity"
                            break
                        result = parse_result(job["kind"], envelope.get("content"), job["input"], prompt_version=job["prompt"]["version"])
                        store.finish(call, "completed", envelope, result)
                        completed += 1
                        failed_sanity = job["sanity"] and bad_sanity(result)
                        if failed_sanity:
                            store.set("sanity_investigation", {"call": call, "model": actual, "reason": "Obvious bad output not given low ESA and a major span; investigate prompt/input before further judging"})
                        if actual != model:
                            paused = "model_identity_changed"
                            break
                        if failed_sanity and not accepted_sanity_limitation:
                            paused = "sanity_investigation_required"
                            break
                    except (OSError, ValueError, TypeError, KeyError) as error:
                        store.finish(call, "failed", envelope if isinstance(envelope, dict) else {}, reason=str(error))
                        completed += 1
            if metricx is not None and paused is None:
                outcomes = score_metricx(plan, store, metricx, eligible, limit, retry_unresolved)
                store.set("last_metricx_outcomes", outcomes)
            if not metricx_only:
                store.set("last_pause", paused)
            return status_from(plan, store)
        finally:
            store.close()


def score_metricx(plan, store, runtime, selected=None, limit=None, retry_unresolved=False):
    scored = 0
    outcomes = Counter()
    inputs = [(row["key"], row["input"]) for row in plan["records"] if row["segment"].get("eligible") is True]
    inputs = [(segment["id"], blinded_input(segment)) for segment in sanity_segments()] + inputs
    for key, data in inputs:
        if selected is not None and key not in selected and not key.startswith("sanity:"):
            continue
        identity = runtime.cache_identity()
        input_hash = fingerprint([data["source_text"], data["output_text"]])
        if store.metricx_cached(input_hash, identity):
            outcomes["completed"] += 1
            continue
        if not retry_unresolved and store.has_unresolved_metricx(input_hash):
            outcomes["unresolved"] += 1
            continue
        if limit is not None and scored >= limit:
            break
        call = store.metricx_start(input_hash, identity)
        try:
            result = runtime.score(data["source_text"], data["output_text"])
            if result.get("status") not in ("completed", "oversized", "unavailable", "failed"):
                raise ValueError("Invalid MetricX terminal status")
            value = result.get("score")
            if result["status"] == "completed" and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError("Completed MetricX result requires finite numeric score")
            if result["status"] != "completed" and value is not None:
                raise ValueError("Non-completed MetricX result must retain null score")
            store.metricx_finish(call, result)
            outcomes[result["status"]] += 1
        except (OSError, ValueError, TypeError, KeyError) as error:
            store.metricx_finish(call, {"status": "failed", "score": None, "reason": str(error), "provenance": {}, "input_tokens": None, "raw": {}})
            outcomes["failed"] += 1
        scored += 1
    return dict(outcomes)


def status_from(plan, store, include_raw=True):
    model = store.get("active_model")
    calls = store.history(include_raw)
    pending = [job for job in plan["jobs"] if not model or store.cached(job, model) is None]
    completed = len(plan["jobs"]) - len(pending)
    return {"root": str(store.root), "version": plan["version"], "synthetic": plan["synthetic"], "model": model,
            "jobs": len(plan["jobs"]), "completed_for_model": completed, "pending_or_unresolved_for_model": len(plan["jobs"]) - completed,
            "blocked_for_model": sum(store.has_attempt(job, model) for job in pending) if model else 0,
            "call_states": dict(Counter(row["state"] for row in calls)), "calls": calls,
            "unresolved_calls": [row for row in calls if row["state"] in ("running", "unresolved", "quota", "unavailable", "failed")],
            "actual_models": sorted({row["actual_model"] for row in calls if row["actual_model"]}),
            "metricx_calls": store.metricx_history(), "samples": plan["samples"], "paused": store.get("last_pause"),
            "metricx_outcomes": store.get("last_metricx_outcomes", {}),
            "measurement_guard": store.get("measurement_guard"), "sanity_investigation": store.get("sanity_investigation"),
            "sanity_limitation": store.get("sanity_limitation")}


def status(root):
    plan = load_plan(root)
    store = QualityStore(root)
    try:
        return status_from(plan, store)
    finally:
        store.close()
