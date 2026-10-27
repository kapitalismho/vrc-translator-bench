import copy
import json
import math

import pytest

from bench.aggregation import aggregate_results


KINDS = ("P1", "P2", "P3", "P4", "T1")
LANGUAGES = ("en-zh", "ja-ko")


def population(score=100, interval=(2, 5)):
    episodes, rows = [], []
    for language in LANGUAGES:
        for kind in KINDS:
            identifier = f"{language}-{kind}"
            episodes.append({"episode_id": identifier, "language_pair": language, "kind": kind,
                             "source_case_id": f"source-{identifier}"})
            for role in ("A", "B") if kind == "T1" else ("A",):
                rows.append({"episode_id": identifier, "role": role,
                             "quality": {"status": "judged", "score": score},
                             "checkpoints": [{"checkpoint_id": f"{identifier}-{role}-meaning",
                                              "status": "met", "interval_seconds": list(interval)}]})
    return episodes, rows


def find_row(rows, identifier, role="A"):
    return next(row for row in rows if row["episode_id"] == identifier and row["role"] == role)


def test_complete_result_is_json_serializable_auditable_and_does_not_mutate_inputs():
    episodes, rows = population(80)
    original = copy.deepcopy((episodes, rows))
    result = aggregate_results(episodes, rows)
    assert json.loads(json.dumps(result, allow_nan=False)) == result
    assert (episodes, rows) == original
    assert result["schema_version"] == 1
    assert result["quality"] == {"status": "complete", "score": 80,
        "partial_contribution": 80, "planned_weight": 1, "completed_weight": 1, "missing_weight": 0}
    assert result["semantic_wait"] == {"status": "complete", "planned_weight": 1,
        "completed_weight": 1, "missing_weight": 0, "met_weight": 1, "unmet_weight": 0,
        "p50": {"status": "met", "interval_seconds": [2, 5]},
        "p90": {"status": "met", "interval_seconds": [2, 5]}}
    assert result["coverage"] == {"planned_episodes": 10, "excluded_episodes": 0,
        "required_roles": 12, "observed_roles": 12, "missing_roles": 0, "missing_cells": []}
    assert len(result["cells"]) == 10
    assert math.fsum(row["planned_weight"] for row in result["roles"]) == 1
    assert math.fsum(row["quality"]["weighted_contribution"] for row in result["roles"]) == 80
    assert all(row["source_case_id"].startswith("source-") for row in result["roles"])


def test_quality_uses_cell_episode_means_and_two_equal_t1_roles_not_role_or_packet_counts():
    episodes, rows = population()
    original = next(episode for episode in episodes if episode["episode_id"] == "en-zh-P2")
    episodes.remove(original)
    rows.remove(find_row(rows, original["episode_id"]))
    for index, score in enumerate((0, 30, 60)):
        identifier = f"p2-{index}"
        episodes.append({**original, "episode_id": identifier})
        rows.append({"episode_id": identifier, "role": "A",
            "quality": {"status": "judged", "score": score},
            "checkpoints": [{"checkpoint_id": f"meaning-{i}", "status": "met", "interval_seconds": [0, 2]}
                            for i in range(index + 1)]})
    find_row(rows, "ja-ko-T1", "A")["quality"]["score"] = 0
    find_row(rows, "ja-ko-T1", "B")["quality"]["score"] = 40
    find_row(rows, "ja-ko-T1", "B")["checkpoints"] = [
        {"checkpoint_id": f"meaning-{i}", "status": "met", "interval_seconds": [2, 5]}
        for i in range(10)]
    result = aggregate_results(episodes, rows)
    # .70*100 + .15*mean(0,30,60) + .15*mean(0,40).
    assert result["quality"]["score"] == pytest.approx(77.5)
    assert result["coverage"]["planned_episodes"] == 12
    assert result["coverage"]["required_roles"] == 14
    for index in range(3):
        role = find_row(result["roles"], f"p2-{index}")
        assert role["planned_weight"] == pytest.approx(.05)
        assert [cp["planned_weight"] for cp in role["checkpoints"]] == pytest.approx([.05 / (index + 1)] * (index + 1))
    assert find_row(result["roles"], "ja-ko-T1", "A")["planned_weight"] == .075
    assert [cp["planned_weight"] for cp in find_row(result["roles"], "ja-ko-T1", "B")["checkpoints"]] == [.0075] * 10


def test_quantiles_pool_weighted_cdf_not_means_of_language_or_episode_quantiles():
    episodes, rows = population()
    for row in rows:
        row["checkpoints"][0]["interval_seconds"] = [0, 0] if row["episode_id"].startswith("en-zh") else [10, 15]
    result = aggregate_results(episodes, rows)
    assert result["semantic_wait"]["p50"] == {"status": "met", "interval_seconds": [0, 0]}
    assert result["semantic_wait"]["p90"] == {"status": "met", "interval_seconds": [10, 15]}


def test_overlapping_intervals_return_cdf_bound_envelope_not_a_midpoint_or_one_arbitrary_sample():
    episodes, rows = population()
    for row in rows:
        row["checkpoints"][0]["interval_seconds"] = [0, 10] if row["episode_id"].startswith("en-zh") else [2, 5]
    wait = aggregate_results(episodes, rows)["semantic_wait"]
    assert wait["p50"] == {"status": "met", "interval_seconds": [0, 5]}
    assert wait["p90"] == {"status": "met", "interval_seconds": [2, 10]}


def test_known_unmet_weight_keeps_denominator_and_p50_and_p90_are_independent():
    episodes, rows = population()
    for role in ("A", "B"):
        find_row(rows, "en-zh-T1", role)["checkpoints"][0].update(status="unmet", interval_seconds=None)
    result = aggregate_results(episodes, rows)
    assert result["quality"]["status"] == "complete"
    wait = result["semantic_wait"]
    assert wait["status"] == "complete"
    assert wait["completed_weight"] == 1
    assert wait["unmet_weight"] == .15
    assert wait["p50"] == {"status": "met", "interval_seconds": [2, 5]}
    assert wait["p90"] == {"status": "unmet", "interval_seconds": None}
    for row in rows:
        row["checkpoints"][0].update(status="unmet", interval_seconds=None)
    wait = aggregate_results(episodes, rows)["semantic_wait"]
    assert wait["p50"] == wait["p90"] == {"status": "unmet", "interval_seconds": None}
    assert wait["met_weight"] == 0
    assert wait["unmet_weight"] == 1


def test_exact_p90_boundary_with_thirds_is_met_without_promoting_weight_below_threshold():
    episodes, rows = population()
    # Exactly .10 unmet; splitting every role into thirds must not shift .90.
    for row in rows:
        row["checkpoints"] = [{"checkpoint_id": str(i), "status": "met", "interval_seconds": [5, 10]}
                              for i in range(3)]
    for checkpoint in find_row(rows, "ja-ko-P3")["checkpoints"]:
        checkpoint.update(status="unmet", interval_seconds=None)
    wait = aggregate_results(episodes, rows)["semantic_wait"]
    assert wait["met_weight"] == .9
    assert wait["p90"] == {"status": "met", "interval_seconds": [5, 10]}
    find_row(rows, "ja-ko-P1")["checkpoints"][0].update(status="unmet", interval_seconds=None)
    assert aggregate_results(episodes, rows)["semantic_wait"]["p90"] == {"status": "unmet", "interval_seconds": None}


@pytest.mark.parametrize("score", [None, 0])
def test_no_output_zero_is_protocol_value_not_a_judge_response(score):
    episodes, rows = population()
    row = find_row(rows, "en-zh-P1")
    row["quality"] = {"status": "no_output", "score": score}
    row["checkpoints"][0].update(status="unmet", interval_seconds=None)
    result = aggregate_results(episodes, rows)
    assert result["quality"]["score"] == 95
    detail = find_row(result["roles"], "en-zh-P1")
    assert detail["quality"] == {"status": "no_output", "score": 0,
                                "score_source": "protocol", "weighted_contribution": 0}
    assert result["semantic_wait"]["completed_weight"] == 1
    assert result["semantic_wait"]["unmet_weight"] == .05


def test_missing_t1_role_does_not_double_episodes_or_renormalize_other_role():
    episodes, rows = population()
    rows.remove(find_row(rows, "ja-ko-T1", "B"))
    result = aggregate_results(episodes, rows)
    assert result["quality"]["score"] is None
    assert result["quality"]["status"] == "incomplete"
    assert result["quality"]["partial_contribution"] == pytest.approx(92.5)
    assert result["quality"]["completed_weight"] == .925
    assert result["quality"]["missing_weight"] == .075
    assert result["semantic_wait"]["missing_weight"] == .075
    assert result["semantic_wait"]["p50"] == result["semantic_wait"]["p90"] == {
        "status": "incomplete", "interval_seconds": None}
    assert result["coverage"]["planned_episodes"] == 10
    assert result["coverage"]["required_roles"] == 12
    assert result["coverage"]["missing_roles"] == 1
    detail = find_row(result["roles"], "ja-ko-T1", "B")
    assert detail["planned_weight"] == .075
    assert detail["quality"]["status"] == "missing_role"
    assert detail["semantic_wait"]["reason"] == "missing_role"


def test_unmeasured_episode_retains_its_frozen_cell_denominator():
    episodes, rows = population()
    episodes.append({"episode_id": "unmeasured", "language_pair": "en-zh", "kind": "P2"})
    result = aggregate_results(episodes, rows)
    assert result["quality"]["partial_contribution"] == pytest.approx(92.5)
    assert result["quality"]["missing_weight"] == .075
    assert find_row(result["roles"], "en-zh-P2")["planned_weight"] == .075
    assert find_row(result["roles"], "unmeasured")["quality"]["score"] is None


def test_missing_whole_cell_reserves_known_design_weight_instead_of_redistributing_it():
    episodes, rows = population()
    episodes = [episode for episode in episodes if episode["episode_id"] != "en-zh-P2"]
    rows = [row for row in rows if row["episode_id"] != "en-zh-P2"]
    result = aggregate_results(episodes, rows)
    assert result["coverage"]["missing_cells"] == [{"language_pair": "en-zh", "kind": "P2", "planned_weight": .15}]
    assert result["quality"]["partial_contribution"] == 85
    assert result["quality"]["missing_weight"] == .15
    assert result["quality"]["score"] is None
    assert result["semantic_wait"]["missing_weight"] == .15
    assert result["semantic_wait"]["p90"]["status"] == "incomplete"
    assert len(result["cells"]) == 10


def test_empty_planned_population_is_not_complete_or_zero_quality():
    result = aggregate_results([], [])
    assert result["quality"]["status"] == "incomplete"
    assert result["quality"]["score"] is None
    assert result["quality"]["partial_contribution"] == 0
    assert result["quality"]["missing_weight"] == 1
    assert result["semantic_wait"]["missing_weight"] == 1
    assert len(result["coverage"]["missing_cells"]) == 10


@pytest.mark.parametrize("checkpoints", [None, [], [{"checkpoint_id": "unobserved", "status": "unknown", "interval_seconds": None}],
    [{"checkpoint_id": "no-clock", "status": "met", "interval_seconds": None}]])
def test_missing_unknown_or_unclocked_checkpoints_do_not_corrupt_complete_quality(checkpoints):
    episodes, rows = population()
    row = find_row(rows, "en-zh-P1")
    row["checkpoints"] = checkpoints
    result = aggregate_results(episodes, rows)
    assert result["quality"]["score"] == 100
    assert result["semantic_wait"]["status"] == "incomplete"
    assert result["semantic_wait"]["missing_weight"] == .05
    assert result["semantic_wait"]["unmet_weight"] == 0
    assert result["semantic_wait"]["p50"]["interval_seconds"] is None


def test_partial_checkpoint_weight_is_preserved_without_publishing_complete_quantile():
    episodes, rows = population()
    find_row(rows, "en-zh-P2")["checkpoints"].append({
        "checkpoint_id": "not-judged", "status": "unknown", "interval_seconds": None})
    result = aggregate_results(episodes, rows)
    assert result["semantic_wait"]["met_weight"] == .925
    assert result["semantic_wait"]["missing_weight"] == .075
    assert result["semantic_wait"]["p90"]["status"] == "incomplete"
    detail = find_row(result["roles"], "en-zh-P2")
    assert [cp["planned_weight"] for cp in detail["checkpoints"]] == [.075, .075]


@pytest.mark.parametrize("quality", [None, {"status": "judged", "score": None},
    {"status": "harness_invalid", "score": None}, {"status": "unsupported", "score": None},
    {"status": "unresolved_judge", "score": None}])
def test_unavailable_quality_is_not_zero_and_does_not_hide_completed_time(quality):
    episodes, rows = population()
    find_row(rows, "en-zh-P1")["quality"] = quality
    result = aggregate_results(episodes, rows)
    assert result["quality"]["status"] == "incomplete"
    assert result["quality"]["score"] is None
    assert result["quality"]["partial_contribution"] == 95
    assert result["quality"]["missing_weight"] == .05
    assert result["semantic_wait"]["status"] == "complete"
    detail = find_row(result["roles"], "en-zh-P1")["quality"]
    assert detail["status"] == (quality["status"] if quality else "missing_quality")
    assert detail["score_source"] is None
    assert detail["weighted_contribution"] is None


def test_control_is_retained_but_never_quality100_or_time0_and_never_completes_missing_cells():
    episodes, rows = population(80)
    control = {"episode_id": "silence", "language_pair": "ja-ko", "kind": "C1"}
    control_row = {"episode_id": "silence", "role": "A", "quality": {"status": "no_output", "score": None}, "checkpoints": []}
    before = aggregate_results(episodes, rows)
    result = aggregate_results(episodes + [control], rows + [control_row])
    assert result["quality"] == before["quality"]
    assert result["semantic_wait"] == before["semantic_wait"]
    assert result["coverage"]["planned_episodes"] == 10
    assert result["coverage"]["excluded_episodes"] == 1
    assert result["excluded_controls"][0]["planned_weight"] == 0
    assert result["excluded_controls"][0]["role_results"][0]["quality"]["status"] == "no_output"
    only_control = aggregate_results([control], [control_row])
    assert only_control["quality"]["status"] == "incomplete"
    assert only_control["semantic_wait"]["missing_weight"] == 1


@pytest.mark.parametrize("score", [True, "80", float("nan"), float("inf"), -1, 101, 10**1000])
def test_rejects_invalid_quality_numbers(score):
    episodes, rows = population()
    rows[0]["quality"]["score"] = score
    with pytest.raises(ValueError):
        aggregate_results(episodes, rows)


@pytest.mark.parametrize("interval", [[-1, 2], [5, 2], [10, 16], [0, float("nan")],
    [0, float("inf")], [False, 2], [0, "2"], [0], [0, 1, 2], "0,2"])
def test_rejects_impossible_or_nonfinite_checkpoint_intervals(interval):
    episodes, rows = population()
    rows[0]["checkpoints"][0]["interval_seconds"] = interval
    with pytest.raises(ValueError):
        aggregate_results(episodes, rows)


@pytest.mark.parametrize("change", ["episode_duplicate", "role_duplicate", "checkpoint_duplicate",
    "unplanned", "ordinary_b", "bad_role", "language", "kind", "checkpoint_status", "unmet_interval",
    "unknown_interval", "no_output_nonzero", "unavailable_score", "empty_id", "empty_checkpoint_id"])
def test_rejects_duplicate_unplanned_and_contradictory_records(change):
    episodes, rows = population()
    if change == "episode_duplicate":
        episodes.append(copy.deepcopy(episodes[0]))
    elif change == "role_duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif change == "checkpoint_duplicate":
        rows[0]["checkpoints"].append(copy.deepcopy(rows[0]["checkpoints"][0]))
    elif change == "unplanned":
        rows[0]["episode_id"] = "not-in-plan"
    elif change == "ordinary_b":
        rows[0]["role"] = "B"
    elif change == "bad_role":
        rows[0]["role"] = "self"
    elif change == "language":
        episodes[0]["language_pair"] = "zh-en"
    elif change == "kind":
        episodes[0]["kind"] = "P5"
    elif change == "checkpoint_status":
        rows[0]["checkpoints"][0]["status"] = "invalid"
    elif change in ("unmet_interval", "unknown_interval"):
        rows[0]["checkpoints"][0]["status"] = change.split("_")[0]
    elif change == "no_output_nonzero":
        rows[0]["quality"] = {"status": "no_output", "score": 50}
    elif change == "unavailable_score":
        rows[0]["quality"] = {"status": "harness_invalid", "score": 0}
    elif change == "empty_id":
        episodes[0]["episode_id"] = ""
    elif change == "empty_checkpoint_id":
        rows[0]["checkpoints"][0]["checkpoint_id"] = ""
    with pytest.raises(ValueError):
        aggregate_results(episodes, rows)


def test_frozen_checkpoint_scope_fills_omitted_ids_without_redistributing_their_weight():
    episodes, rows = population()
    episode = next(episode for episode in episodes if episode["episode_id"] == "en-zh-P2")
    measured_id = find_row(rows, "en-zh-P2")["checkpoints"][0]["checkpoint_id"]
    episode["checkpoint_ids"] = {"A": [measured_id, "missing-meaning"]}
    result = aggregate_results(episodes, rows)
    detail = find_row(result["roles"], "en-zh-P2")
    assert detail["checkpoints"] == [
        {"checkpoint_id": measured_id, "status": "met", "interval_seconds": [2, 5], "planned_weight": .075},
        {"checkpoint_id": "missing-meaning", "status": "unknown", "interval_seconds": None, "planned_weight": .075}]
    assert detail["checkpoint_ids"] == episode["checkpoint_ids"]
    assert result["semantic_wait"]["met_weight"] == .925
    assert result["semantic_wait"]["missing_weight"] == .075
    assert result["semantic_wait"]["p90"]["status"] == "incomplete"
    assert result["quality"]["score"] == 100


def test_frozen_checkpoint_scope_preserves_all_missing_t1_role_placeholders():
    episodes, rows = population()
    episode = next(episode for episode in episodes if episode["episode_id"] == "ja-ko-T1")
    measured_id = find_row(rows, "ja-ko-T1", "A")["checkpoints"][0]["checkpoint_id"]
    episode["checkpoint_ids"] = {"A": [measured_id], "B": ["b1", "b2", "b3"]}
    rows.remove(find_row(rows, "ja-ko-T1", "B"))
    result = aggregate_results(episodes, rows)
    detail = find_row(result["roles"], "ja-ko-T1", "B")
    assert len(detail["checkpoints"]) == 3
    assert [cp["planned_weight"] for cp in detail["checkpoints"]] == [.025] * 3
    assert all(cp["status"] == "unknown" for cp in detail["checkpoints"])
    assert detail["semantic_wait"]["missing_weight"] == .075
    assert detail["semantic_wait"]["reason"] == "missing_role"
    assert result["quality"]["missing_weight"] == .075


@pytest.mark.parametrize("scope", [{"A": []}, {}, {"A": ["different-id"]}, {"B": ["wrong-role"]},
    {"A": ["duplicate", "duplicate"]}, {"A": [""]}, {"A": "not-a-list"}, None])
def test_rejects_unexpected_or_invalid_frozen_checkpoint_ids(scope):
    episodes, rows = population()
    episodes[0]["checkpoint_ids"] = scope
    with pytest.raises(ValueError):
        aggregate_results(episodes, rows)
