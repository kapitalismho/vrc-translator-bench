from __future__ import annotations

import copy

from bench.metrics import derive
from bench.quality import prepare, score
from bench.quality_report import build_report
from test_metrics import link, packet, sample
from test_quality import Judge, dump


def test_join_replaces_unobserved_supplied_scores_without_losing_timing_or_exclusions(tmp_path):
    manifest, spec = sample(tmp_path / "capture", [packet(1, 11, "안녕하세요")])
    cache = link(tmp_path, manifest, spec, {"clock:1": ["1:clip/s1"]})
    original = derive(manifest, spec, cache_path=cache)
    original["quality_segments"][0]["quality_score"] = {"major_error": False, "esa_score": 100, "provenance": ["Synthetic externally supplied arithmetic, not observed judge result"]}
    original["quality_segments"][0]["eligible"] = False
    original["quality_segments"][0]["quality_eligibility_reason"] = "unresolved_merged_output_allocation"
    queue = tmp_path / "queue"
    prepare([dump(tmp_path / "report.json", original)], queue)
    result = build_report(queue)
    joined = result["joined_metrics_reports"][0]
    assert joined["sentences"] == original["sentences"]
    assert joined["outputs"] == original["outputs"]
    assert joined["aggregates"][0]["delivery"] == original["aggregates"][0]["delivery"]
    assert joined["aggregates"][0]["major_error_segment_rate"]["value"] is None
    assert joined["aggregates"][0]["esa_mean"]["value"] is None
    assert joined["quality_segments"][0]["quality_score"] is None
    assert joined["quality_segments"][0]["previous_supplied_quality_score"]["esa_score"] == 100
    assert joined["quality_score_coverage"]["excluded_by_reason"] == {"unresolved_merged_output_allocation": [original["quality_segments"][0]["id"]]}


def test_join_esa_population_uses_same_primary_attempts_as_major_rate(tmp_path):
    manifest, spec = sample(tmp_path / "capture", [packet(1, 11, "안녕하세요")])
    cache = link(tmp_path, manifest, spec, {"clock:1": ["1:clip/s1"]})
    original = derive(manifest, spec, cache_path=cache)
    extra_sentences = copy.deepcopy(original["sentences"])
    for sentence in extra_sentences:
        sentence.update({"id": sentence["id"] + "-retry", "attempt_id": 2, "attempt_number": 2})
    original["sentences"].extend(extra_sentences)
    extra_segment = copy.deepcopy(original["quality_segments"][0])
    extra_segment.update({"id": "retry-quality", "attempt_id": 2, "attempt_number": 2, "final_output": [{"text": "다른 출력"}]})
    original["quality_segments"].append(extra_segment)
    extra_attempt = copy.deepcopy(original["attempts"][0])
    extra_attempt.update({"id": 2, "number": 2})
    original["attempts"].append(extra_attempt)
    queue = tmp_path / "queue"
    prepare([dump(tmp_path / "report.json", original)], queue)
    score(queue, Judge(), "synthetic-v1")
    report = build_report(queue)
    population = report["joined_metrics_reports"][0]["aggregates"][0]
    assert population["major_error_segment_rate"]["scored_segments"] == 1
    assert population["esa_mean"]["scored_segments"] == 1
    assert population["esa_mean"]["observations"] == 1
    assert report["quality_populations"][0]["esa_mean"]["scored_segments"] == 2
    assert report["joined_metrics_reports"][0]["quality_score_coverage"]["scored_eligible_segments"] == 2


def test_isolated_exact_window_join_and_out_of_window_text_stays_unscored(tmp_path):
    for label, events, should_score in (
        ("exact", [packet(1, 11, "안녕하세요")], True),
        ("late-extra", [packet(1, 11, "안녕하세요"), packet(2, 27, "늦은 추가 문장")], False),
    ):
        case = tmp_path / label
        manifest, spec = sample(case / "capture", events, kind="isolated")
        original = derive(manifest, spec)
        original["isolated"][0]["quality"]["quality_score"] = {"esa_score": 100, "major_error": False, "provenance": ["Unobserved synthetic supplied score"]}
        queue = case / "queue"
        prepare([dump(case / "report.json", original)], queue)
        score(queue, Judge(), "synthetic-v1")
        report = build_report(queue)
        isolated = report["joined_metrics_reports"][0]["isolated"][0]
        quality = isolated["quality"]
        assert quality["previous_supplied_quality_score"]["esa_score"] == 100
        assert isolated["output_ids"] == original["isolated"][0]["output_ids"]
        assert isolated["late_carryover_ids"] == original["isolated"][0]["late_carryover_ids"]
        assert quality["association"] == "window_only_no_alignment"
        assert (quality["quality_score"] is not None) is should_score
        assert report["records"][0]["esa"] is not None
        if should_score:
            assert quality["quality_score"]["esa_score"] == 20
            assert quality["quality_score_reason"] is None
        else:
            assert quality["quality_score_reason"] == "no_exact_window_matching_quality_segment"
            assert quality["tone_score"] is None and quality["metricx_score"] is None
