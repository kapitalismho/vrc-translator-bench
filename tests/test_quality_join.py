from __future__ import annotations

import copy
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event, get_ident

import pytest

import bench.quality_report as quality_report
from bench.metrics import derive
from bench.quality import prepare, score
from bench.quality_report import build_report
from bench.quality_store import QualityStore
from test_metrics import link, packet, sample
from test_quality import Judge, Metric, dump, input_report


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


@pytest.mark.parametrize("boundary", ["history", "cached"])
@pytest.mark.parametrize("model", [None, "synthetic-v1"])
def test_report_keeps_one_snapshot_while_scoring_commits(tmp_path, monkeypatch, boundary, model):
    root = tmp_path / "queue"
    plan = prepare([input_report(tmp_path / "input.json")], root)
    with ThreadPoolExecutor(max_workers=1) as executor:
        ready = Event()
        release = Event()

        def writer():
            ready.set()
            assert release.wait(10), "Report never reached the controlled read boundary"
            return score(root, Judge(), "synthetic-v1", metricx=Metric(), measurements_ended=True)

        store = QualityStore(root)
        store.set("active_model", "synthetic-v1")
        store.close()
        future = executor.submit(writer)
        assert ready.wait(10)
        original = getattr(QualityStore, boundary)
        triggered = False
        reader_thread = get_ident()

        def read_then_commit(self, *args, **kwargs):
            nonlocal triggered
            value = original(self, *args, **kwargs)
            if not triggered and get_ident() == reader_thread:
                triggered = True
                release.set()
                completed = future.result(timeout=10)
                assert completed["completed_for_model"] == len(plan["jobs"])
                assert completed["metricx_calls"]
            return value

        try:
            with monkeypatch.context() as patch:
                patch.setattr(QualityStore, boundary, read_then_commit)
                current = build_report(root, model=model)
        finally:
            release.set()
        assert triggered
        assert current["selected_actual_model"] == "synthetic-v1"
        assert current["scoring_models_observed"] == []
        assert current["calibration"]["model_coverage"] == {}
        assert all(row["esa"] is None and row["tone"] is None and row["metricx"] is None for row in current["records"])
        assert all(row["status"] == "missing" for row in current["sanity"])
        assert current["execution"]["completed_for_model"] == 0
        assert current["execution"]["calls"] == []
        assert current["execution"]["metricx_calls"] == []
        assert current["joined_metrics_reports"][0]["quality_segments"][0]["quality_score"] is None

    following = build_report(root, model=model)
    assert following["plan_binding"] == current["plan_binding"] == plan["binding"]
    assert following["scoring_models_observed"] == ["synthetic-v1"]
    assert following["calibration"]["model_coverage"] == {"synthetic-v1": len(plan["samples"]["calibration"]["keys"])}
    assert all(row["esa"] is not None and row["tone"] is not None and row["metricx"]["status"] == "completed" for row in following["records"])
    assert all(row["status"] == "completed" for row in following["sanity"])
    assert following["execution"]["completed_for_model"] == len(plan["jobs"])
    assert following["execution"]["calls"]
    assert following["execution"]["metricx_calls"]
    assert all("raw" not in call and call["raw_artifact"]["id"] == call["id"] for call in following["execution"]["calls"])
    assert following["joined_metrics_reports"][0]["quality_segments"][0]["quality_score"]["esa_score"] == 20


def test_report_closes_snapshot_after_output_error(tmp_path, monkeypatch):
    root = tmp_path / "queue"
    prepare([input_report(tmp_path / "input.json")], root)
    stores = []
    original = quality_report.atomic_json

    def fail_output(path, result):
        raise OSError("controlled output failure")

    def open_store(root):
        store = QualityStore(root)
        stores.append(store)
        return store

    monkeypatch.setattr(quality_report, "QualityStore", open_store)
    monkeypatch.setattr(quality_report, "atomic_json", fail_output)
    with pytest.raises(OSError, match="controlled output failure"):
        build_report(root, output=tmp_path / "failed.json")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        stores[0].db.execute("SELECT 1")
    completed = score(root, Judge(), "synthetic-v1")
    monkeypatch.setattr(quality_report, "atomic_json", original)
    following = build_report(root, output=tmp_path / "report.json")
    assert following["execution"]["completed_for_model"] == completed["jobs"]
    assert (tmp_path / "report.json").is_file()
