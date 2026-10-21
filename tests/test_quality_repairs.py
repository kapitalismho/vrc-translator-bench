from __future__ import annotations

import json
import subprocess
import sys

import pytest

from bench.quality import prepare, score, status
from bench.quality_prompts import parse_result
from bench.quality_report import build_report
from bench.quality_store import QualityStore
from test_quality import ROOT, Judge, Metric, input_report, segment


@pytest.mark.parametrize("pause", ["quota", "model_identity_changed"])
def test_metricx_only_preserves_judge_pause_until_explicit_recovery(tmp_path, pause):
    root = tmp_path / "quality-queue"
    prepare([input_report(tmp_path / "quality-input.json")], root)
    first_judge = Judge(mode="quota") if pause == "quota" else Judge("returned-v2")
    first = score(root, first_judge, "synthetic-v1")
    assert first["paused"] == pause
    metric = Metric()
    supplementary_judge = Judge()
    supplementary = score(root, supplementary_judge, "synthetic-v1", metricx=metric,
                          metricx_only=True, measurements_ended=True)
    assert metric.calls
    assert all(call["state"] == "completed" for call in supplementary["metricx_calls"])
    assert supplementary_judge.requests == []
    assert supplementary["paused"] == pause
    ordinary = Judge()
    blocked = score(root, ordinary, "synthetic-v1")
    assert blocked["paused"] == pause
    assert ordinary.requests == []
    assert blocked["calls"] == first["calls"]
    resumed_model = "synthetic-v1" if pause == "quota" else "returned-v2"
    recovered = score(root, Judge(resumed_model), resumed_model, retry_unresolved=True)
    assert recovered["completed_for_model"] == recovered["jobs"]
    assert recovered["paused"] is None
    assert recovered["calls"][0] == first["calls"][0]


def test_changed_model_cached_bad_sanity_requires_investigation_or_limitation(tmp_path):
    root = tmp_path / "quality-queue"
    prepare([input_report(tmp_path / "quality-input.json")], root)
    changed = score(root, Judge("returned-v2", score_value=99), "requested-v1")
    assert changed["paused"] == "model_identity_changed"
    assert changed["calls"][0]["result"]["esa_score"] == 99
    ordinary = Judge("returned-v2")
    blocked = score(root, ordinary, "returned-v2")
    assert blocked["paused"] == "sanity_investigation_required"
    assert ordinary.requests == []
    assert blocked["sanity_investigation"]["model"] == "returned-v2"
    assert blocked["calls"] == changed["calls"]
    permitted = score(root, ordinary, "returned-v2", sanity_limitation="Controlled explicit limitation for retained bad sanity")
    assert permitted["completed_for_model"] == permitted["jobs"]
    assert permitted["calls"][0] == changed["calls"][0]


@pytest.mark.parametrize("score_value,major_error,requires_investigation", [(99, True, True), (20, False, True), (20, True, False)])
def test_cached_sanity_reconstructs_guard_after_result_commit_gap(tmp_path, score_value, major_error, requires_investigation):
    root = tmp_path / "quality-queue"
    plan = prepare([input_report(tmp_path / "quality-input.json")], root)
    job = plan["jobs"][0]
    producer = Judge(score_value=score_value)
    envelope = producer.call(job["prompt"], 1)
    if not major_error:
        envelope["content"]["spans"] = []
    result = parse_result("esa", envelope["content"], job["input"])
    store = QualityStore(root)
    try:
        call = store.start(job, "synthetic-v1", producer.provenance)
        store.raw(call, envelope)
        store.finish(call, "completed", envelope, result)
        assert store.get("sanity_investigation") is None
        assert store.get("last_pause") is None
    finally:
        store.close()
    judge = Judge()
    resumed = score(root, judge, "synthetic-v1")
    if requires_investigation:
        assert resumed["paused"] == "sanity_investigation_required"
        assert judge.requests == []
        assert resumed["sanity_investigation"]["call"] == call
        assert len(resumed["calls"]) == 1
    else:
        assert resumed["paused"] is None
        assert resumed["completed_for_model"] == resumed["jobs"]
        assert judge.requests
    assert status(root)["calls"][0]["result"] == result


@pytest.mark.parametrize("prior_pause", [None, "quota"])
@pytest.mark.parametrize("score_value", [99, 20])
def test_changed_model_commit_gap_blocks_old_request_then_checks_actual_model_sanity(tmp_path, prior_pause, score_value):
    root = tmp_path / "quality-queue"
    plan = prepare([input_report(tmp_path / "quality-input.json")], root)
    prior_calls = []
    if prior_pause:
        paused = score(root, Judge(mode=prior_pause), "requested-v1")
        assert paused["paused"] == prior_pause
        prior_calls = paused["calls"]
    job = plan["jobs"][0]
    producer = Judge("returned-v2", score_value=score_value)
    envelope = producer.call(job["prompt"], 1)
    result = parse_result("esa", envelope["content"], job["input"])
    store = QualityStore(root)
    try:
        call = store.start(job, "requested-v1", producer.provenance)
        store.raw(call, envelope)
        store.finish(call, "completed", envelope, result)
        assert store.get("last_pause") == prior_pause
        assert store.get("sanity_investigation") is None
    finally:
        store.close()
    requested = Judge("requested-v1")
    unchanged = score(root, requested, "requested-v1", retry_unresolved=True)
    assert unchanged["paused"] == "model_identity_changed"
    assert requested.requests == []
    assert len(unchanged["calls"]) == len(prior_calls) + 1
    assert unchanged["calls"][:len(prior_calls)] == prior_calls
    actual = Judge("returned-v2")
    changed = score(root, actual, "returned-v2", retry_unresolved=True)
    if score_value > 50:
        assert changed["paused"] == "sanity_investigation_required"
        assert actual.requests == []
        assert changed["sanity_investigation"]["call"] == call
        assert changed["calls"] == unchanged["calls"]
        wrong_limitation = score(root, requested, "requested-v1", retry_unresolved=True,
                                 sanity_limitation="Not applicable to returned-v2")
        assert wrong_limitation["paused"] == "model_identity_changed"
        assert requested.requests == []
        still_blocked = score(root, actual, "returned-v2", retry_unresolved=True)
        assert still_blocked["paused"] == "sanity_investigation_required"
        assert actual.requests == []
        changed = score(root, actual, "returned-v2", retry_unresolved=True,
                        sanity_limitation="Controlled explicit limitation for returned-v2 bad sanity")
    assert changed["paused"] is None
    assert changed["completed_for_model"] == changed["jobs"]
    assert actual.requests
    assert changed["calls"][:len(unchanged["calls"])] == unchanged["calls"]


class MovementJudge(Judge):
    def call(self, prompt, call_id):
        response = super().call(prompt, call_id)
        if isinstance(response.get("content"), dict) and "esa_score" in response["content"]:
            data = json.loads(prompt["messages"][1]["content"])
            if data["output_text"].endswith(" 0"):
                response["content"].update(esa_score=30, spans=[])
        return response


def test_calibration_counts_every_frozen_case_when_identical_prompts_share_cache(tmp_path):
    root = tmp_path / "quality-queue"
    inputs = [segment(0, "PP2"), segment(0, "OTHER"), segment(1, "THIRD")]
    plan = prepare([input_report(tmp_path / "quality-input.json", inputs)], root)
    assert len(plan["samples"]["calibration"]["keys"]) == 3
    first_judge = Judge("baseline-model")
    first = score(root, first_judge, "baseline-model")
    assert first["completed_for_model"] == first["jobs"] == 9
    assert len(first_judge.requests) == 7
    candidate_judge = MovementJudge("candidate-model")
    second = score(root, candidate_judge, "candidate-model", calibration_only=True)
    assert second["completed_for_model"] == 6
    assert len(candidate_judge.requests) == 5
    report = build_report(root)
    calibration = report["calibration"]
    assert calibration["model_coverage"] == {"baseline-model": 3, "candidate-model": 3}
    comparison = calibration["comparisons"][0]
    assert comparison["paired_segments"] == 3
    assert comparison["missing_pairs"] == 0
    assert comparison["mean_esa_movement"] == pytest.approx(20 / 3)
    assert comparison["mean_major_error_movement"] == pytest.approx(-2 / 3)
    assert sorted(pair["esa_difference"] for pair in comparison["pairs"]) == [0, 10, 10]
    assert {pair["key"] for pair in comparison["pairs"]} == set(plan["samples"]["calibration"]["keys"])


@pytest.mark.parametrize("metricx_state,exit_code", [("completed", 0), ("unavailable", 2), ("failed", 2), ("oversized", 2)])
def test_metricx_only_cli_exit_uses_local_outcomes_and_preserves_judge_pause(tmp_path, metricx_state, exit_code):
    root = tmp_path / "quality-queue"
    prepare([input_report(tmp_path / "quality-input.json")], root)
    first = score(root, Judge(mode="quota"), "synthetic-v1")
    command = [sys.executable, str(ROOT / "tests/fixtures/quality_repair_cli.py"), "--controlled-metricx-status", metricx_state,
               "quality", "score", "--root", str(root), "--metricx-only", "--measurements-ended"]
    observed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert observed.returncode == exit_code, observed.stderr + observed.stdout
    result = json.loads(observed.stdout)
    assert result["paused"] == "quota"
    assert result["metricx_outcomes"] == {metricx_state: 4}
    retained = status(root)
    assert retained["paused"] == "quota"
    assert retained["calls"] == first["calls"]
    assert all(call["state"] == metricx_state for call in retained["metricx_calls"])
