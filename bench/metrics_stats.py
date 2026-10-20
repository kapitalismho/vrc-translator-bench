from __future__ import annotations

import random
from collections import Counter, defaultdict
from itertools import combinations

from .metrics_inputs import metric


def quantile(values, probability):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * probability
    low = int(position)
    return values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (position - low)


def clustered(rows, function, iterations, seed, unit):
    sessions = sorted({row["session_id"] for row in rows if row.get("session_id")})
    value = function(rows)
    session_values = [{"session_id": session, "value": function([row for row in rows if row["session_id"] == session])} for session in sessions]
    interval = None
    reason = None
    if len(sessions) < 2:
        reason = "Fewer than two original sessions; show session values, no bootstrap interval"
    elif value is None:
        reason = "No measurable observations"
    else:
        rng = random.Random(seed)
        clusters = {session: [row for row in rows if row["session_id"] == session] for session in sessions}
        samples = []
        for _ in range(iterations):
            sample = [row for session in rng.choices(sessions, k=len(sessions)) for row in clusters[session]]
            estimate = function(sample)
            if estimate is not None:
                samples.append(estimate)
        interval = [quantile(samples, 0.025), quantile(samples, 0.975)] if samples else None
    return metric(value, None if value is not None else "No measurable observations", unit,
                  confidence_interval_95=interval, uncertainty_reason=reason, original_sessions=len(sessions),
                  session_values=session_values, observations=len(rows), bootstrap_iterations=iterations, seed=seed)


def eligible(rows):
    return [row for row in rows if row["eligible"]]


def rate(rows, key, accepted):
    values = eligible(rows)
    return sum(row[key] in accepted for row in values) / len(values) if values else None


def summary(rows, iterations, seed):
    values = eligible(rows)
    results = {"reference_sentences": len(rows), "eligible_sentences": len(values),
               "denominator_coverage": dict(Counter(row.get("eligibility_reason") or "eligible" for row in rows)),
               "delivery_status_counts": dict(Counter(row["delivery_status"] for row in rows)),
               "delivery": clustered(rows, lambda sample: rate(sample, "delivery_status", {"delivered"}), iterations, seed, "fraction_of_eligible_sentences")}
    unknown = sum(row["delivery_status"] in ("unknown_correspondence", "incomplete_observation") for row in values)
    results["delivery"]["unresolved_sentences"] = unknown
    results["delivery"]["correspondence_bounds"] = [results["delivery"]["value"], (sum(row["delivery_status"] == "delivered" for row in values) + unknown) / len(values)] if values else None
    for name in ("fol", "lul"):
        for probability in (0.5, 0.9):
            results[f"{name}_p{int(probability * 100)}"] = clustered(rows, lambda sample, name=name, probability=probability: quantile([row[name]["value"] for row in eligible(sample) if row[name]["value"] is not None], probability), iterations, seed, "seconds")
    results["fol_by_duration"] = {}
    for duration in ("below_2s", "2_to_5s", "above_5s"):
        selected = [row for row in rows if row["duration_bin"] == duration]
        results["fol_by_duration"][duration] = {f"p{int(p * 100)}": clustered(selected, lambda sample, p=p: quantile([row["fol"]["value"] for row in eligible(sample) if row["fol"]["value"] is not None], p), iterations, seed, "seconds") for p in (0.5, 0.9)}
    return results


def aggregate(report, options):
    iterations, seed = options.get("iterations", 2000), options.get("seed", 20261020)
    if not isinstance(iterations, int) or iterations < 1:
        raise ValueError("Bootstrap iterations must be a positive integer")
    sentences = report["sentences"]
    primary_numbers = {}
    for row in sentences:
        key = (row["run"], row["config"], row["direction"], row["audio_sha256"], row["reference_id"], row["kind"])
        if row["status"] in ("done", "product_failure") and row["outcome"] != "N/A":
            primary_numbers[key] = min(primary_numbers.get(key, row["attempt_number"]), row["attempt_number"])
    primary = [row for row in sentences if row["kind"] == "chunk" and row["attempt_number"] == primary_numbers.get((row["run"], row["config"], row["direction"], row["audio_sha256"], row["reference_id"], row["kind"]), row["attempt_number"])]
    grouped = defaultdict(list)
    for row in primary:
        grouped[(row["config"], row["direction"], row["category"], "category")].append(row)
        if row["casual"] is True:
            grouped[(row["config"], row["direction"], row["category"], "casual_only")].append(row)
    aggregates = []
    for key, rows in sorted(grouped.items()):
        config, direction, category, view = key
        result = {"config": config, "direction": direction, "category": category, "view": view, **summary(rows, iterations, seed)}
        attempt_ids = {row["attempt_id"] for row in rows}
        source_ids = {item["id"] for item in rows}
        selected_outputs = [row for row in report["outputs"] if row["raw"].get("config") == config
                            and (row["raw"].get("direction") == direction and row["raw"].get("attempt") in attempt_ids or source_ids.intersection(row["alignment"]["sentence_ids"]))]
        result["unaligned_output_rate"] = metric(sum(not row["alignment"]["sentence_ids"] for row in selected_outputs) / len(selected_outputs) if selected_outputs else None,
                                                None if selected_outputs else "No observed translation output in this capture/source population", "fraction_of_observed_translation_outputs", denominator=len(selected_outputs))
        segments = [row for row in report["quality_segments"] if row.get("attempt_id") in attempt_ids and row["category"] == category and (view != "casual_only" or row["casual"] is True)]
        scored = [row for row in segments if row["eligible"] and row.get("quality_score") is not None and isinstance(row["quality_score"].get("major_error"), bool)]
        result["major_error_segment_rate"] = clustered(scored, lambda sample: sum(row["quality_score"]["major_error"] for row in sample) / len(sample) if sample else None, iterations, seed, "fraction_of_scored_segments")
        result["major_error_segment_rate"]["eligible_segments"] = sum(row["eligible"] for row in segments)
        result["major_error_segment_rate"]["scored_segments"] = len(scored)
        work_ids = {row["work_id"] for row in report["attempts"] if row["id"] in attempt_ids}
        attempts = [row for row in report["attempts"] if row["work_id"] in work_ids and row["number"] == 1]
        denominator = [row for row in attempts if row["state"] in ("done", "product_failure") and row.get("outcome") != "N/A"]
        result["first_attempt_product_failure_rate"] = metric(sum(row["state"] == "product_failure" for row in denominator) / len(denominator) if denominator else None,
                                                            None if denominator else "No eligible first attempts", "fraction_of_eligible_first_attempts", denominator=len(denominator),
                                                            statuses=dict(Counter(row["state"] for row in attempts)))
        aggregates.append(result)
    paired = []
    indexed = defaultdict(dict)
    for row in report["quality_segments"]:
        if row.get("shared_id") and row.get("eligible") and row.get("kind") == "chunk":
            indexed[(row["direction"], row["category"], row["config"])][row["shared_id"]] = row
    for direction, category in sorted({(key[0], key[1]) for key in indexed}):
        configs = sorted(key[2] for key in indexed if key[:2] == (direction, category))
        for left, right in combinations(configs, 2):
            a, b = indexed[(direction, category, left)], indexed[(direction, category, right)]
            shared = sorted(a.keys() & b.keys())
            points = []
            for identity in shared:
                one, two = a[identity], b[identity]
                s1 = [row for row in sentences if row["attempt_id"] == one["attempt_id"] and one["start"] <= row["start"] and row["end"] <= one["end"]]
                s2 = [row for row in sentences if row["attempt_id"] == two["attempt_id"] and two["start"] <= row["start"] and row["end"] <= two["end"]]
                v1, v2 = rate(s1, "delivery_status", {"delivered"}), rate(s2, "delivery_status", {"delivered"})
                points.append({"session_id": one["session_id"], "shared_id": identity, "delivery_difference": v1 - v2 if v1 is not None and v2 is not None else None,
                               "common_success": one["status"] == two["status"] == "done",
                               "major_error_difference": int(one["quality_score"]["major_error"]) - int(two["quality_score"]["major_error"]) if one.get("quality_score") and two.get("quality_score") and isinstance(one["quality_score"].get("major_error"), bool) and isinstance(two["quality_score"].get("major_error"), bool) else None})
                for name in ("fol", "lul"):
                    left_value = quantile([row[name]["value"] for row in eligible(s1) if row[name]["value"] is not None], 0.5)
                    right_value = quantile([row[name]["value"] for row in eligible(s2) if row[name]["value"] is not None], 0.5)
                    points[-1][f"{name}_difference"] = left_value - right_value if left_value is not None and right_value is not None else None
            comparisons = {}
            for label, values in (("all_shared", points), ("common_success_only_supplemental", [row for row in points if row["common_success"]])):
                comparisons[label] = {name: clustered([row for row in values if row[name] is not None], lambda sample, name=name: sum(row[name] for row in sample) / len(sample) if sample else None, iterations, seed, "left_minus_right_seconds" if name in ("fol_difference", "lul_difference") else "left_minus_right_fraction") for name in ("delivery_difference", "major_error_difference", "fol_difference", "lul_difference")}
            paired.append({"direction": direction, "category": category, "left": left, "right": right, "shared_segments": shared, "comparisons": comparisons})
    repeat_groups = defaultdict(list)
    for row in sentences:
        if row["kind"] == "repeat":
            repeat_groups[(row["config"], row["direction"], row["run"], row["attempt_id"])].append(row)
    repeats = [{"config": key[0], "direction": key[1], "run": key[2], "attempt_id": key[3], **summary(rows, iterations, seed)} for key, rows in repeat_groups.items()]
    repeat_variation = []
    for config, direction in sorted({(row["config"], row["direction"]) for row in repeats}):
        observed = [row for row in repeats if row["config"] == config and row["direction"] == direction]
        reference_ids = {row["reference_id"] for row in sentences if row["config"] == config and row["direction"] == direction and row["kind"] == "repeat"}
        baseline = [row for row in primary if row["config"] == config and row["direction"] == direction and row["reference_id"] in reference_ids]
        repeat_variation.append({"config": config, "direction": direction, "baseline_shared_subset": summary(baseline, iterations, seed),
                                 "repeat_attempts": [{"run": row["run"], "attempt_id": row["attempt_id"], "delivery": row["delivery"]["value"],
                                                      "fol_p50": row["fol_p50"]["value"], "lul_p50": row["lul_p50"]["value"]} for row in observed],
                                 "delivery_range": [min(row["delivery"]["value"] for row in observed if row["delivery"]["value"] is not None),
                                                    max(row["delivery"]["value"] for row in observed if row["delivery"]["value"] is not None)] if any(row["delivery"]["value"] is not None for row in observed) else None,
                                 "independence": "Repeated original audio is observed run variation, not additional independent recordings"})
    sensitivity = [{"config": key[0], "direction": key[1], "category": key[2], "view": key[3],
                    "with_resumed": summary(rows, iterations, seed), "without_resumed": summary([row for row in rows if not row["resumed"]], iterations, seed)} for key, rows in grouped.items()]
    output_count = len(report["outputs"])
    return {"aggregates": aggregates, "paired": paired, "repeats": repeats, "repeat_variation": repeat_variation, "resume_sensitivity": sensitivity,
            "output_population": {"observed_translation_outputs": output_count,
                                  "alignment_status_counts": dict(Counter(row["alignment"]["status"] for row in report["outputs"])),
                                  "unaligned_output_rate": metric(sum(not row["alignment"]["sentence_ids"] for row in report["outputs"]) / output_count if output_count else None,
                                                                  None if output_count else "No translation output", "fraction_of_observed_translation_outputs", denominator=output_count),
                                  "orphans": sum(row["quality_segment_id"].startswith("orphan:") for row in report["outputs"])} }
