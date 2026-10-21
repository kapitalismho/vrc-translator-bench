from __future__ import annotations

from collections import defaultdict

from .quality_prompts import fingerprint


def ordered(rows, seed, namespace):
    return sorted(rows, key=lambda row: fingerprint([seed, namespace, row["key"]]))


def freeze_samples(records, seed, *, include_tone=True):
    eligible = [row for row in records if row["segment"].get("eligible") is True]
    calibration = [row["key"] for row in ordered(eligible, seed, "calibration")[:100]]
    samples = {"seed": seed, "calibration": {"requested": 100, "keys": calibration, "shortfall": 100 - len(calibration)},
               "policy": "Frozen exact input/output cases, reused across judge models; deterministic hash sampling without replacement."}
    if include_tone:
        by_config = {row["segment"]["config"]: [] for row in records}
        for row in eligible:
            by_config[row["segment"]["config"]].append(row)
        tone = {config: [row["key"] for row in ordered(rows, seed, "tone:" + config)[:30]] for config, rows in sorted(by_config.items())}
        samples["tone"] = {config: {"requested": 30, "keys": keys, "shortfall": 30 - len(keys)} for config, keys in tone.items()}
        samples["policy"] += " Tone: 30 per configuration across eligible directions/categories. These are working choices, not owner-mandated strata."
    return samples


def interleaved(records, seed):
    groups = defaultdict(list)
    for row in records:
        groups[row["segment"].get("shared_id", row["key"])].append(row)
    result = []
    for group in sorted(groups, key=lambda key: fingerprint([seed, "source-order", key])):
        result.extend(ordered(groups[group], seed, "configuration-order:" + group))
    return result


def disagreements(rows):
    available = [row for row in rows if row.get("esa") is not None and row.get("metricx") is not None
                 and row["metricx"].get("status") == "completed" and row["metricx"].get("score") is not None]
    groups = defaultdict(list)
    for row in available:
        groups[(row["segment"].get("direction"), row["segment"].get("category"))].append(row)
    result = []
    for group, members in sorted(groups.items()):
        esa = [100 - row["esa"]["esa_score"] for row in members]
        metricx = [row["metricx"]["score"] for row in members]

        def percentile(value, population):
            return (sum(item < value for item in population) + (sum(item == value for item in population) - 1) / 2) / (len(population) - 1) if len(population) > 1 else 0.5

        for row, e, m in zip(members, esa, metricx):
            erank, mrank = percentile(e, esa), percentile(m, metricx)
            result.append({"key": row["key"], "config": row["segment"]["config"], "direction": group[0], "category": group[1],
                           "esa_score": row["esa"]["esa_score"], "metricx_score": m, "esa_error_percentile": erank,
                           "metricx_error_percentile": mrank, "disagreement": abs(erank - mrank), "comparison_population": len(members)})
    return sorted(result, key=lambda row: (-row["disagreement"], row["key"]))


def korean_packet(rows, disagreement, seed, human_notes=None):
    pool = [row for row in rows if row["segment"].get("direction") in ("D3", "D4") and row["segment"].get("eligible") is True]
    ranks = {row["key"]: row for row in disagreement}
    selected = set()
    selection = []
    coverage = {}
    for stratum in ("random", "disagreement"):
        candidates = [row for row in pool if row["key"] not in selected and (stratum == "random" or row["key"] in ranks)]
        candidates = ordered(candidates, seed, "korean:" + stratum) if stratum == "random" else sorted(candidates, key=lambda row: (-ranks[row["key"]]["disagreement"], fingerprint([seed, row["key"]])))
        pp2 = [row for row in candidates if row["segment"]["config"] == "PP2"]
        others = [row for row in candidates if row["segment"]["config"] != "PP2"]
        chosen = pp2[:25] + others[:25]
        spare = [row for row in candidates if row not in chosen]
        chosen += spare[:50 - len(chosen)]
        counts = {"PP2": sum(row["segment"]["config"] == "PP2" for row in chosen), "other": sum(row["segment"]["config"] != "PP2" for row in chosen)}
        coverage[stratum] = {"requested": 50, "selected": len(chosen), "shortfall": 50 - len(chosen), "family_counts": counts,
                             "family_target": {"PP2": 25, "other": 25},
                             "balance_shortfall": {family: max(0, 25 - count) for family, count in counts.items()}}
        for row in chosen:
            selected.add(row["key"])
            segment = row["segment"]
            selection.append({"key": row["key"], "stratum": stratum, "config": segment["config"], "direction": segment["direction"],
                              "reference_levels": sorted({str(item.get("reference_level", "unknown")) for item in segment["reference"]}),
                              "context": segment.get("context", []), "reference": segment["reference"], "final_output": segment["final_output"],
                              "esa": row.get("esa"), "metricx": row.get("metricx"), "disagreement": ranks.get(row["key"])})
    if human_notes is None:
        notes = {"performed": False, "notes": [], "reason": "No owner review observations supplied"}
    else:
        if not isinstance(human_notes, dict) or type(human_notes.get("performed")) is not bool or not isinstance(human_notes.get("notes"), list):
            raise ValueError("Human notes require performed boolean and notes array")
        for note in human_notes["notes"]:
            if not isinstance(note, dict) or note.get("key") not in selected or not isinstance(note.get("note"), str) or not note["note"].strip():
                raise ValueError("Human note must identify a selected review key and nonempty note")
        if human_notes["notes"] and human_notes["performed"] is not True:
            raise ValueError("Unperformed review cannot contain observations")
        notes = human_notes
    return {"schema_version": 1, "requested": 100, "selected": len(selection), "shortfall": 100 - len(selection), "coverage": coverage,
            "selection_policy": "50 random, then 50 largest within-direction/category rank disagreements without overlap; 25 PP2 and 25 other-family cases per stratum where available, fill remaining capacity and disclose imbalance. D3/D4 eligible only. Frozen seed, not proof of representativeness.",
            "review_scope": "Reference-only Korean target fluency, tone and obvious Korean problems. Owner review does not verify Chinese/Japanese semantics. Automatic scores are not changed by notes.",
            "automatic_limitations": "ESA sees earlier reference context; MetricX does not. Agreement is not truth; disagreement does not prove model-family bias. D4 references are automatic/exploratory and local-only.",
            "segments": selection, "human_review": notes}
