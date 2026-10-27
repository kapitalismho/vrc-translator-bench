"""Frozen-plan aggregation for one profile and measurement condition.

``aggregate_results(episodes, role_results)`` returns schema version 1. ``quality``
contains a complete score or null and an explicitly unnormalised partial
contribution. ``semantic_wait`` contains independent p50/p90 status/intervals;
unknown weight makes both incomplete, whereas known unmet weight stays in the
CDF denominator. ``cells`` and ``roles`` expose the same contributions for audit.
All weights are fractions of the full two-language, five-type planned population.
Callers must group profiles/conditions before calling this function.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from fractions import Fraction


_LANGUAGE_PAIRS = ("en-zh", "ja-ko")
_TYPE_WEIGHTS = {"P1": Fraction(1, 10), "P2": Fraction(3, 10),
                 "P3": Fraction(2, 10), "P4": Fraction(1, 10), "T1": Fraction(3, 10)}


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be finite and numeric")
    try:
        value = float(value)
    except OverflowError as exc:
        raise ValueError(f"{label} must be finite and numeric") from exc
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite and numeric")
    return value


def _quality(value):
    if value is None:
        return {"status": "missing_quality", "score": None, "score_source": None}
    if not isinstance(value, Mapping):
        raise ValueError("quality must be an object")
    status = _text(value.get("status"), "quality.status")
    score = value.get("score")
    if score is not None:
        score = _number(score, "quality.score")
        if not 0 <= score <= 100:
            raise ValueError("quality.score must be between 0 and 100")
    if status == "no_output":
        if score not in (None, 0):
            raise ValueError("no_output quality must be zero or null")
        return {"status": status, "score": 0.0, "score_source": "protocol"}
    if status != "judged" and score is not None:
        raise ValueError("Unavailable quality cannot carry a score")
    return {"status": status, "score": score,
            "score_source": "judge" if status == "judged" and score is not None else None}


def _checkpoints(values, planned_ids=None):
    if values is None:
        values = []
    if not isinstance(values, (list, tuple)):
        raise ValueError("checkpoints must be a list")
    seen = set()
    result = []
    for value in values:
        if not isinstance(value, Mapping):
            raise ValueError("Each checkpoint must be an object")
        identifier = _text(value.get("checkpoint_id"), "checkpoint_id")
        if identifier in seen:
            raise ValueError(f"Duplicate checkpoint_id: {identifier}")
        seen.add(identifier)
        status = value.get("status")
        if status not in ("met", "unmet", "unknown"):
            raise ValueError("Checkpoint status must be met, unmet or unknown")
        interval = value.get("interval_seconds")
        if interval is not None:
            if not isinstance(interval, (list, tuple)) or len(interval) != 2:
                raise ValueError("interval_seconds must contain lower and upper bounds")
            lower, upper = (_number(bound, "interval_seconds") for bound in interval)
            if not 0 <= lower <= upper <= 15:
                raise ValueError("Checkpoint intervals must satisfy 0 <= lower <= upper <= 15")
            if status != "met":
                raise ValueError("Only met checkpoints can carry an interval")
            interval = [lower, upper]
        result.append({"checkpoint_id": identifier, "status": status,
                       "interval_seconds": interval})
    if planned_ids is not None:
        by_id = {checkpoint["checkpoint_id"]: checkpoint for checkpoint in result}
        unexpected = by_id.keys() - set(planned_ids)
        if unexpected:
            raise ValueError(f"Unplanned checkpoint IDs: {', '.join(sorted(unexpected))}")
        result = [by_id.get(identifier, {"checkpoint_id": identifier, "status": "unknown",
                                        "interval_seconds": None}) for identifier in planned_ids]
    return result


def _quantile(samples, target, unknown_weight):
    if unknown_weight:
        return {"status": "incomplete", "interval_seconds": None}
    if sum((weight for _, weight in samples), Fraction()) < target:
        return {"status": "unmet", "interval_seconds": None}
    bounds = []
    for index in (0, 1):
        cumulative = Fraction()
        for interval, weight in sorted(samples, key=lambda sample: sample[0][index]):
            cumulative += weight
            if cumulative >= target:
                bounds.append(interval[index])
                break
    return {"status": "met", "interval_seconds": bounds}


def _summaries(planned_weight, quality_parts, samples, unmet_weight, unknown_weight):
    completed_quality = sum((weight for weight, _ in quality_parts), Fraction())
    contribution = math.fsum(float(weight) * score for weight, score in quality_parts)
    complete_quality = completed_quality == planned_weight
    met_weight = sum((weight for _, weight in samples), Fraction())
    return (
        {"status": "complete" if complete_quality else "incomplete",
         "score": contribution / float(planned_weight) if complete_quality else None,
         "partial_contribution": contribution,
         "planned_weight": float(planned_weight), "completed_weight": float(completed_quality),
         "missing_weight": float(planned_weight - completed_quality)},
        {"status": "incomplete" if unknown_weight else "complete",
         "planned_weight": float(planned_weight),
         "completed_weight": float(met_weight + unmet_weight),
         "missing_weight": float(unknown_weight), "met_weight": float(met_weight),
         "unmet_weight": float(unmet_weight),
         "p50": _quantile(samples, planned_weight / 2, unknown_weight),
         "p90": _quantile(samples, planned_weight * Fraction(9, 10), unknown_weight)},
    )


def aggregate_results(episodes, role_results):
    """Aggregate explicit planned episodes, including unmeasured episodes.

    Episodes require episode_id, language_pair (en-zh/ja-ko), and kind
    (P1/P2/P3/P4/T1/C1); source_case_id is optional audit metadata. Ordinary
    episodes require A, T1 requires A/B. Role rows contain episode_id, role,
    quality {status, score}, and checkpoints [{checkpoint_id, status,
    interval_seconds}]. Missing quality/checkpoints remain incomplete. A met
    checkpoint with no interval is unknown timing, not a fabricated point.
    Optional episode checkpoint_ids maps A/B to frozen checkpoint ID lists.
    With this mapping, unexpected IDs are rejected and omitted IDs become unknown
    with their original equal weight. Without it, the supplied full checkpoint
    list declares the planned scope; callers must retain unknown placeholders.

    Malformed, duplicate, unplanned, or contradictory records raise ValueError.
    An absent language/type cell reserves its full design weight. Controls are
    retained in excluded_controls, never scored. Input objects are not mutated.
    Interval quantiles are lower/upper weighted-CDF bounds, not midpoints.
    Exact rational weights avoid rounding across CDF threshold boundaries.
    """
    if not isinstance(episodes, (list, tuple)) or not isinstance(role_results, (list, tuple)):
        raise ValueError("episodes and role_results must be explicit lists")
    planned = {}
    grouped = {(language, kind): [] for language in _LANGUAGE_PAIRS for kind in _TYPE_WEIGHTS}
    controls = []
    for episode in episodes:
        if not isinstance(episode, Mapping):
            raise ValueError("Each planned episode must be an object")
        identifier = _text(episode.get("episode_id"), "episode_id")
        if identifier in planned:
            raise ValueError(f"Duplicate planned episode_id: {identifier}")
        language, kind = episode.get("language_pair"), episode.get("kind")
        if language not in _LANGUAGE_PAIRS or kind not in (*_TYPE_WEIGHTS, "C1"):
            raise ValueError("Unsupported planned language_pair or kind")
        metadata = {"episode_id": identifier, "language_pair": language, "kind": kind}
        if "source_case_id" in episode:
            metadata["source_case_id"] = _text(episode["source_case_id"], "source_case_id")
        if "checkpoint_ids" in episode:
            scope = episode["checkpoint_ids"]
            allowed_roles = ("A", "B") if kind == "T1" else ("A",)
            if not isinstance(scope, Mapping) or any(role not in allowed_roles for role in scope):
                raise ValueError("checkpoint_ids must map required roles to planned ID lists")
            frozen_ids = {}
            for role, identifiers in scope.items():
                if not isinstance(identifiers, (list, tuple)):
                    raise ValueError("Each checkpoint_ids role must contain a list")
                identifiers = [_text(value, "planned checkpoint_id") for value in identifiers]
                if len(set(identifiers)) != len(identifiers):
                    raise ValueError("Duplicate planned checkpoint_id within a role")
                frozen_ids[role] = identifiers
            metadata["checkpoint_ids"] = frozen_ids
        planned[identifier] = metadata
        if kind == "C1":
            controls.append(metadata)
        else:
            grouped[language, kind].append(metadata)

    observed = {}
    for row in role_results:
        if not isinstance(row, Mapping):
            raise ValueError("Each role result must be an object")
        identifier = _text(row.get("episode_id"), "episode_id")
        if identifier not in planned:
            raise ValueError(f"Unplanned episode_id: {identifier}")
        role = row.get("role")
        if role not in (("A", "B") if planned[identifier]["kind"] == "T1" else ("A",)):
            raise ValueError("Only T1 accepts role B; ordinary episodes require A")
        key = identifier, role
        if key in observed:
            raise ValueError(f"Duplicate role result: {identifier}/{role}")
        scope = planned[identifier].get("checkpoint_ids")
        observed[key] = {"quality": _quality(row.get("quality")),
                         "checkpoints": _checkpoints(row.get("checkpoints"),
                                                     scope.get(role, []) if scope is not None else None)}

    cells, roles = [], []
    all_quality, all_samples = [], []
    all_unmet, all_unknown = Fraction(), Fraction()
    missing_cells = []
    required_roles = missing_roles = 0
    for (language, kind), members in grouped.items():
        cell_weight = _TYPE_WEIGHTS[kind] / 2
        parts, samples = [], []
        unmet, unknown = Fraction(), Fraction()
        if not members:
            unknown = cell_weight
            missing_cells.append({"language_pair": language, "kind": kind,
                                  "planned_weight": float(cell_weight)})
        for episode in members:
            role_names = ("A", "B") if kind == "T1" else ("A",)
            weight = cell_weight / len(members) / len(role_names)
            for role in role_names:
                required_roles += 1
                row = observed.get((episode["episode_id"], role))
                if row is None:
                    missing_roles += 1
                quality = dict(row["quality"]) if row else {
                    "status": "missing_role", "score": None, "score_source": None}
                score = quality["score"]
                quality["weighted_contribution"] = float(weight) * score if score is not None else None
                if score is not None:
                    parts.append((weight, score))
                scope = episode.get("checkpoint_ids")
                checkpoints = row["checkpoints"] if row else _checkpoints(
                    [], scope.get(role, []) if scope is not None else None)
                checkpoint_details = []
                role_met = role_unmet = role_unknown = Fraction()
                for checkpoint in checkpoints:
                    checkpoint_weight = weight / len(checkpoints)
                    checkpoint_details.append({**checkpoint, "planned_weight": float(checkpoint_weight)})
                    if checkpoint["status"] == "met" and checkpoint["interval_seconds"] is not None:
                        samples.append((checkpoint["interval_seconds"], checkpoint_weight))
                        role_met += checkpoint_weight
                    elif checkpoint["status"] == "unmet":
                        role_unmet += checkpoint_weight
                    else:
                        role_unknown += checkpoint_weight
                if not checkpoints:
                    role_unknown = weight
                unmet += role_unmet
                unknown += role_unknown
                roles.append({**episode, "role": role, "planned_weight": float(weight),
                              "observed": row is not None, "quality": quality,
                              "semantic_wait": {
                                  "status": "incomplete" if role_unknown else "complete",
                                  "met_weight": float(role_met), "unmet_weight": float(role_unmet),
                                  "missing_weight": float(role_unknown),
                                  "reason": "missing_role" if row is None else
                                            "missing_checkpoints" if not checkpoints else None},
                              "checkpoints": checkpoint_details})
        quality, wait = _summaries(cell_weight, parts, samples, unmet, unknown)
        cells.append({"language_pair": language, "kind": kind,
                      "planned_episodes": len(members), "quality": quality, "semantic_wait": wait})
        all_quality.extend(parts)
        all_samples.extend(samples)
        all_unmet += unmet
        all_unknown += unknown

    quality, wait = _summaries(Fraction(1), all_quality, all_samples, all_unmet, all_unknown)
    return {"schema_version": 1, "quality": quality, "semantic_wait": wait,
            "coverage": {"planned_episodes": len(planned) - len(controls),
                         "excluded_episodes": len(controls), "required_roles": required_roles,
                         "observed_roles": required_roles - missing_roles, "missing_roles": missing_roles,
                         "missing_cells": missing_cells},
            "cells": cells, "roles": roles,
            "excluded_controls": [{**episode, "planned_weight": 0.0,
                                   "role_results": [{"role": "A", **observed[episode["episode_id"], "A"]}]
                                   if (episode["episode_id"], "A") in observed else []}
                                  for episode in controls]}
