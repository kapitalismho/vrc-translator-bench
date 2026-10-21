from __future__ import annotations

import copy
from collections import Counter, defaultdict

from .metrics_stats import aggregate, clustered
from .quality import load_plan, status_from
from .quality_prompts import fingerprint
from .quality_sampling import disagreements, korean_packet
from .quality_store import QualityStore
from .storage import atomic_json, utc_now


def mean(values):
    return sum(values) / len(values) if values else None


def metricx_result(data, history):
    identity = fingerprint([data["source_text"], data["output_text"]])
    matches = [call for call in history if call["input_hash"] == identity]
    return matches[-1]["result"] if matches else None


def summary(rows, iterations=2000, seed=20261020, *, include_tone=True):
    eligible = [row for row in rows if row["segment"].get("eligible") is True]
    scored = [{**row["segment"], "esa": row["esa"]} for row in eligible if row.get("esa") is not None]
    esa = clustered(scored, lambda sample: mean([row["esa"]["esa_score"] for row in sample]), iterations, seed, "ESA_points_0_100")
    major = clustered(scored, lambda sample: mean([int(row["esa"]["major_error"]) for row in sample]), iterations, seed, "fraction_of_scored_segments")
    for value in (esa, major):
        value.update({"total_segments": len(rows), "eligible_segments": len(eligible), "scored_segments": len(scored), "unscored_eligible_segments": len(eligible) - len(scored)})
    return {"esa_mean": esa, "major_error_segment_rate": major,
            "supplementary_error_span_counts": dict(Counter(span["severity"] for row in scored for span in row["esa"]["spans"])),
            "span_count_limitation": "Annotations, not counts of independent real errors",
            "metricx": {"mean": mean([row["metricx"]["score"] for row in eligible if row.get("metricx") and row["metricx"].get("status") == "completed"]),
                        "eligible_segments": len(eligible), "states": dict(Counter(row["metricx"]["status"] if row.get("metricx") else "missing" for row in eligible)),
                        "role": "Supplementary QE/disagreement finder; lower score is better; no conversation context"},
            **({"tone": {field: {"mean": mean([row["tone"][field] for row in eligible if row.get("tone") and row["tone"][field] is not None]),
                                 "scored_dimensions": sum(row.get("tone") is not None and row["tone"][field] is not None for row in eligible)}
                        for field in ("politeness_register", "rudeness_risk", "naturalness")}} if include_tone else {}),
            "reference_levels": dict(Counter(str(item.get("reference_level", "unknown")) for row in rows for item in row["segment"].get("reference", []))),
            "exclusions": dict(Counter(row["segment"].get("quality_eligibility_reason") or row["segment"].get("reason") or row["segment"].get("status", "unknown") for row in rows if row["segment"].get("eligible") is not True))}


def calibration(plan, history):
    keys = set(plan["samples"]["calibration"]["keys"])
    jobs = defaultdict(list)
    for job in plan["jobs"]:
        if job["kind"] == "esa" and job["record_key"] in keys:
            jobs[job["prompt_hash"]].append(job["record_key"])
    by_model = defaultdict(dict)
    order = []
    for call in history:
        if call["state"] != "completed" or call["prompt_hash"] not in jobs:
            continue
        model = call["actual_model"]
        if model not in order:
            order.append(model)
        for key in jobs[call["prompt_hash"]]:
            by_model[model][key] = call["result"]
    comparisons = []
    if order:
        baseline = order[0]
        for model in order[1:]:
            shared = sorted(by_model[baseline].keys() & by_model[model].keys())
            deltas = [{"key": key, "esa_difference": by_model[model][key]["esa_score"] - by_model[baseline][key]["esa_score"],
                       "major_error_difference": int(by_model[model][key]["major_error"]) - int(by_model[baseline][key]["major_error"])} for key in shared]
            comparisons.append({"baseline_model": baseline, "candidate_model": model, "paired_segments": len(shared),
                                "missing_pairs": len(keys) - len(shared), "mean_esa_movement": mean([row["esa_difference"] for row in deltas]),
                                "mean_major_error_movement": mean([row["major_error_difference"] for row in deltas]), "pairs": deltas})
    return {**plan["samples"]["calibration"], "model_coverage": {model: len(values) for model, values in by_model.items()},
            "comparisons": comparisons, "limitation": "Fixed exact 100-case sample where available; movement describes these cases, not proof of judge equivalence"}


def join_isolated(report, index, *, include_tone=True):
    for isolated in report.get("isolated", []):
        quality = isolated.get("quality")
        if not isinstance(quality, dict):
            isolated["quality_scoring"] = {"status": "missing", "reason": "isolated_reference_window_unavailable"}
            continue
        quality["previous_supplied_quality_score"] = quality.get("quality_score")
        quality["quality_score"] = None
        if include_tone:
            quality["tone_score"] = None
        else:
            quality.pop("tone_score", None)
            quality.pop("tone_provenance", None)
        quality["metricx_score"] = None
        matches = [row for row in index.values() if row["segment"].get("kind") == "isolated"
                   and row["segment"].get("attempt_id") == isolated.get("attempt_id") and row["segment"].get("eligible") is True
                   and [item["text"] for item in row["segment"]["reference"]] == [item["text"] for item in quality.get("reference", [])]
                   and [(item.get("output_id"), item["text"]) for item in row["segment"]["final_output"]]
                   == [(item.get("output_id"), item["text"]) for item in quality.get("final_output", [])]]
        if len(matches) != 1:
            quality["quality_score_reason"] = "no_exact_window_matching_quality_segment"
            continue
        row = matches[0]
        quality["quality_record_key"] = row["key"]
        quality["quality_score"] = {**row["esa"], "provenance": row["esa_provenance"]} if row["esa"] is not None else None
        quality["quality_score_reason"] = None if row["esa"] is not None else "matching_window_segment_has_no_completed_judgment"
        if include_tone:
            quality["tone_score"] = row["tone"]
            quality["tone_provenance"] = row["tone_provenance"]
        quality["metricx_score"] = row["metricx"]
        quality["score_association"] = "Exact source texts and ordered final output IDs/texts match same-attempt window-only input; no alignment credit"


def build_report(root, output=None, review_output=None, human_notes=None, model=None):
    plan = load_plan(root)
    scope = plan.get("evaluation_scope", {"tone": True, "korean_review": True})
    if not scope["korean_review"] and (review_output is not None or human_notes is not None):
        raise ValueError("--review-output and --human-notes are unavailable: Korean review disabled in frozen evaluation scope")
    store = QualityStore(root)
    try:
        # Keep history, cached judgments, and execution status on one WAL snapshot.
        store.db.execute("BEGIN")
        selected_model = model or store.get("active_model")
        calls = store.history(include_raw=False)
        mxhistory = store.metricx_history()
        jobs = {(job["record_key"], job["kind"]): job for job in plan["jobs"]}
        rows = []
        for record in plan["records"]:
            values = {}
            for kind in (("esa", "tone") if scope["tone"] else ("esa",)):
                job = jobs.get((record["key"], kind))
                call = store.cached(job, selected_model) if job and selected_model else None
                values[kind] = call["result"] if call else None
                values[kind + "_provenance"] = {key: call[key] for key in ("id", "actual_model", "started_utc", "ended_utc", "response_date", "prompt_hash", "input_hash", "transport")} if call else None
            values["metricx"] = metricx_result(record["input"], mxhistory)
            rows.append({**record, **values, "judge_family_overlap": record["segment"].get("config") == "PP2"})
        disagreement = disagreements(rows)
        packet = korean_packet(rows, disagreement, plan["samples"]["seed"], human_notes) if scope["korean_review"] else None
        by_report = defaultdict(list)
        for row in rows:
            by_report[row["report_sha256"]].append(row)
        joined = []
        for item in plan["reports"]:
            report = copy.deepcopy(item["report"])
            index = {row["segment"]["id"]: row for row in by_report[item["sha256"]]}
            for segment in report["quality_segments"]:
                row = index[segment["id"]]
                segment["previous_supplied_quality_score"] = segment.get("quality_score")
                segment["quality_score"] = ({**row["esa"], "provenance": row["esa_provenance"]} if row["esa"] is not None else None)
                if scope["tone"]:
                    segment["tone_score"] = row["tone"]
                    segment["tone_provenance"] = row["tone_provenance"]
                else:
                    segment.pop("tone_score", None)
                    segment.pop("tone_provenance", None)
                segment["metricx_score"] = row["metricx"]
                segment["quality_record_key"] = row["key"]
                segment["judge_family_overlap"] = row["judge_family_overlap"]
            join_isolated(report, index, include_tone=scope["tone"])
            if report.get("sentences") is not None and report.get("outputs") is not None and report.get("attempts") is not None:
                original_aggregate = next(iter(report.get("aggregates", [])), {})
                options = {key: original_aggregate.get("major_error_segment_rate", {}).get(field, default) for key, field, default in
                           (("iterations", "bootstrap_iterations", 2000), ("seed", "seed", 20261020))}
                report.update(aggregate(report, options))
                primary_numbers = {}
                for sentence in report["sentences"]:
                    identity = tuple(sentence[key] for key in ("run", "config", "direction", "audio_sha256", "reference_id", "kind"))
                    if sentence["status"] in ("done", "product_failure") and sentence["outcome"] != "N/A":
                        primary_numbers[identity] = min(primary_numbers.get(identity, sentence["attempt_number"]), sentence["attempt_number"])
                primary = [sentence for sentence in report["sentences"] if sentence["kind"] == "chunk"
                           and sentence["attempt_number"] == primary_numbers.get(tuple(sentence[key] for key in ("run", "config", "direction", "audio_sha256", "reference_id", "kind")), sentence["attempt_number"])]
                for population in report["aggregates"]:
                    attempt_ids = {sentence["attempt_id"] for sentence in primary if sentence["config"] == population["config"] and sentence["direction"] == population["direction"] and sentence["category"] == population["category"]}
                    selected = [row for row in index.values() if row["segment"].get("attempt_id") in attempt_ids and row["segment"].get("kind") == "chunk" and row["segment"].get("config") == population["config"] and row["segment"].get("direction") == population["direction"] and row["segment"].get("category") == population["category"] and (population["view"] != "casual_only" or row["segment"].get("casual") is True)]
                    quality = summary(selected, options["iterations"], options["seed"], include_tone=scope["tone"])
                    population["esa_mean"] = quality["esa_mean"]
                    population["quality_supplementary"] = {key: value for key, value in quality.items() if key not in ("esa_mean", "major_error_segment_rate")}
            report["previous_supplied_quality_score_coverage"] = report.get("quality_score_coverage")
            report["quality_score_coverage"] = {"total_segments": len(index), "reference_eligible_segments": sum(row["segment"].get("reference_eligible", False) for row in index.values()),
                                                "population": "All report quality segments; each aggregate separately declares its eligible/scored population",
                                                "supplied_major_error_scores": sum(row["esa"] is not None for row in index.values()),
                                                "excluded_major_error_scores": sum(row["esa"] is not None and row["segment"].get("eligible") is not True for row in index.values()),
                                                "eligible_segments": sum(row["segment"].get("eligible") is True for row in index.values()),
                                                "excluded_segments": sum(row["segment"].get("eligible") is not True for row in index.values()),
                                                "scored_eligible_segments": sum(row["esa"] is not None and row["segment"].get("eligible") is True for row in index.values()),
                                                "unscored_eligible_segments": sum(row["esa"] is None and row["segment"].get("eligible") is True for row in index.values()),
                                                "excluded_by_reason": {reason: [row["segment"]["id"] for row in index.values() if row["segment"].get("eligible") is not True and (row["segment"].get("quality_eligibility_reason") or row["segment"].get("reason") or "ineligible") == reason] for reason in {row["segment"].get("quality_eligibility_reason") or row["segment"].get("reason") or "ineligible" for row in index.values() if row["segment"].get("eligible") is not True}}}
            report["quality_provenance"] = {"plan_binding": plan["binding"], "selected_actual_model": selected_model, "source_report_sha256": item["sha256"]}
            joined.append(report)
        grouped = defaultdict(list)
        for row in rows:
            segment = row["segment"]
            grouped[(segment.get("config"), segment.get("direction"), segment.get("category"), segment.get("kind"), "category")].append(row)
            if segment.get("casual") is True:
                grouped[(segment.get("config"), segment.get("direction"), segment.get("category"), segment.get("kind"), "casual_only")].append(row)
        sanity = []
        for job in plan["jobs"]:
            if job["sanity"]:
                call = store.cached(job, selected_model) if selected_model else None
                attempts = [attempt for attempt in calls if attempt["prompt_hash"] == job["prompt_hash"] and attempt["expected_model"] == selected_model]
                sanity.append({"case": job["sanity"], "input": job["input"], "esa": call["result"] if call else None,
                               "call_id": call["id"] if call else None, "metricx": metricx_result(job["input"], mxhistory),
                               "status": "completed" if call else "missing", "attempt_ids": [attempt["id"] for attempt in attempts],
                               "reason": None if call else attempts[-1]["reason"] if attempts else "No completed judgment for selected actual model",
                               "obvious_failure": call["result"]["esa_score"] > 50 or not call["result"]["major_error"] if call else None})
        result = {"schema_version": 1, "version": plan["version"], "created_utc": utc_now(), "synthetic": plan["synthetic"],
                  "plan_binding": plan["binding"], "selected_actual_model": selected_model, "evaluation_scope": scope,
                  "scoring_models_observed": sorted({call["actual_model"] for call in calls if call["actual_model"]}),
                  "mixed_version_scoring": len({row["esa_provenance"]["actual_model"] for row in rows if row["esa_provenance"]}) > 1,
                  "limitations": plan["limitations"] + ["The shared OS activity lock excludes cooperating capture/scoring commands; root observations and operator acknowledgement do not detect unmanaged external measurements", "No single overall quality/latency/cost score is produced", "Raw transcripts and Japanese-derived speech content remain local; inspect before publication"],
                  "working_choices": {"prompt_version": plan["version"], "samples": plan["samples"], "sanity_rule": "Pause if an obvious bad-output ESA exceeds 50 or has no major span; working investigation trigger, not evaluator validation", "disagreement": "Absolute midrank-percentile difference of ESA error (100-score) and MetricX score within direction/category; no scale-equivalence claim", "order": "Seeded source-group order and randomized configurations within shared source segments; each call independent"},
                  "records": rows, "joined_metrics_reports": joined,
                  "quality_populations": [{"config": key[0], "direction": key[1], "category": key[2], "kind": key[3], "view": key[4],
                                           "attempt_policy": "All retained quality input attempts, not additional independent recordings", **summary(members, include_tone=scope["tone"])} for key, members in sorted(grouped.items(), key=lambda item: str(item[0]))],
                  "disagreements": disagreement, "calibration": calibration(plan, calls), "sanity": sanity,
                  "execution": status_from(plan, store, include_raw=False)}
        if scope["korean_review"]:
            result["korean_review"] = packet
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            atomic_json(output, result)
        if review_output:
            review_output.parent.mkdir(parents=True, exist_ok=True)
            atomic_json(review_output, packet)
        return result
    finally:
        store.close()
