from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from bench.metrics_batch import compose
from bench.metrics_stats import aggregate
from test_metrics import dump
from test_metrics_stats_repairs import report, segment, source, turn


ROOT = Path(__file__).resolve().parents[1]


def metrics(run, config, values=(2, 6), *, direction="D1", category="general", status="done"):
    sentences, segments, turns = [], [], []
    for index, value in enumerate(values, 1):
        sentence = source(f"{index}:sentence", run=run, config=config, direction=direction, category=category,
                          reference_id=f"clip-{index}/source", text=f"Source {index}", attempt_id=index,
                          session_id=f"original-{index}", status=status,
                          outcome="failed" if status == "product_failure" else "done",
                          delivery_status="no_output_before_deadline" if value is None else "delivered",
                          fol={"value": value}, lul={"value": value})
        quality = segment(sentence, f"{index}:quality")
        quality.update(shared_id=f"audio:{direction}:clip-{index}:0:2",
                       reference=[{"sentence_id": sentence["id"], "text": sentence["text"]}],
                       quality_score={"major_error": config == "LEFT", "provenance": ["Synthetic arithmetic fixture only"]})
        sentences.append(sentence)
        segments.append(quality)
        turns.append(turn(sentence, value))
    result = {"schema_version": 1, "version": "issue5-v1", "run": run, "synthetic": True,
              **report(sentences, turns, segments)}
    result.update(aggregate(result, {"iterations": 20, "seed": 7}))
    return result


def comparison(result, label="all_shared", left="LEFT", right="RIGHT"):
    pair = next(row for row in result["paired"] if row["left"] == left and row["right"] == right)
    return pair["comparisons"][label]


def test_cross_wave_pairs_scope_colliding_attempts_and_preserve_original_reports(tmp_path):
    left = metrics("wave-one", "LEFT", (2, 6))
    right = metrics("wave-two", "RIGHT", (10, 18))
    before = copy.deepcopy([left, right])
    paths = [dump(tmp_path / "left.json", left), dump(tmp_path / "right.json", right)]
    result = compose(paths, tmp_path / "batch.json", iterations=40, seed=7)
    assert [item["report"] for item in result["reports"]] == before == [left, right]
    assert all(item["report"]["paired"] == [] for item in result["reports"])
    paired = comparison(result)
    assert paired["delivery_difference"]["value"] == 0
    assert paired["major_error_difference"]["value"] == 1
    for name in ("fol_difference", "lul_difference"):
        assert paired[name]["value"] == -10
        assert paired[name]["observations"] == 2
        assert paired[name]["original_sessions"] == 2
        assert paired[name]["session_values"] == [{"session_id": "original-1", "value": -8}, {"session_id": "original-2", "value": -12}]
        assert paired[name]["confidence_interval_95"] == [-12, -8]
    assert result["paired"][0]["shared_segments"] == [row["shared_id"] for row in left["quality_segments"]]
    assert [row["attempt_id"] for row in result["pairing_population"]] == [1, 2, 1, 2]
    assert [item["run"] for item in result["reports"]] == ["wave-one", "wave-two"]
    assert result["reports"][0]["input_sha256"] == hashlib.sha256(paths[0].read_bytes()).hexdigest()
    assert json.loads((tmp_path / "batch.json").read_text(encoding="utf-8")) == result


def test_attempt_scoping_also_separates_configs_within_one_report(tmp_path):
    left, right = metrics("one-run", "LEFT", (2,)), metrics("one-run", "RIGHT", (10,))
    for field in ("sentences", "quality_segments"):
        left[field].extend(right[field])
    result = compose([dump(tmp_path / "same-run.json", left)], iterations=20)
    assert comparison(result)["fol_difference"]["value"] == -8
    assert comparison(result)["fol_difference"]["original_sessions"] == 1
    assert comparison(result)["fol_difference"]["confidence_interval_95"] is None


def test_failure_unknown_and_quality_eligibility_are_not_success_filtered(tmp_path):
    left = metrics("failure-wave", "LEFT", (None, 6), status="product_failure")
    right = metrics("success-wave", "RIGHT", (10, 18))
    # Output-specific quality eligibility may differ for the same source.
    right["quality_segments"][1]["eligible"] = False
    right["quality_segments"][1]["quality_eligibility_reason"] = "unresolved_merged_output_allocation"
    left["sentences"][0]["delivery_status"] = "unknown_correspondence"
    result = compose([dump(tmp_path / "left.json", left), dump(tmp_path / "right.json", right)], iterations=20)
    all_shared = comparison(result)
    assert all_shared["delivery_difference"]["value"] == -0.5
    assert all_shared["delivery_difference"]["observations"] == 2
    assert all_shared["fol_difference"]["value"] == -12
    assert all_shared["fol_difference"]["observations"] == 1
    assert all_shared["major_error_difference"]["value"] == 1
    assert all_shared["major_error_difference"]["observations"] == 1
    assert comparison(result, "common_success_only_supplemental")["delivery_difference"]["observations"] == 0
    assert all(row["status"] == "product_failure" for row in result["pairing_population"][:2])
    assert result["reports"][0]["report"]["sentences"][0]["delivery_status"] == "unknown_correspondence"


def test_partial_shared_coverage_does_not_invent_matches(tmp_path):
    left, right = metrics("left", "LEFT"), metrics("right", "RIGHT", (10,))
    result = compose([dump(tmp_path / "left.json", left), dump(tmp_path / "right.json", right)], iterations=20)
    assert len(result["pairing_population"]) == 3
    assert result["paired"][0]["shared_segments"] == [left["quality_segments"][0]["shared_id"]]
    assert comparison(result)["delivery_difference"]["observations"] == 1
    assert comparison(result)["fol_difference"]["value"] == -8


@pytest.mark.parametrize("field,value", [("direction", "D3"), ("category", "stress")])
def test_different_direction_or_category_is_not_paired(tmp_path, field, value):
    left, right = metrics("left", "LEFT"), metrics("right", "RIGHT", **{field: value})
    result = compose([dump(tmp_path / "left.json", left), dump(tmp_path / "right.json", right)], iterations=20)
    assert result["paired"] == []


@pytest.mark.parametrize("same_report", [True, False])
def test_any_duplicate_eligible_population_rejects_including_successful_retry(tmp_path, same_report):
    failed = metrics("failed-run", "LEFT", (None,), status="product_failure")
    retry = metrics("retry-run", "LEFT", (1,))
    if same_report:
        for sentence in retry["sentences"]:
            sentence.update(run="failed-run", id="retry:sentence", attempt_id=2, attempt_number=2)
        retry["quality_segments"][0].update(id="retry:quality", attempt_id=2, attempt_number=2,
                                             reference=[{"sentence_id": "retry:sentence", "text": "Source 1"}])
        failed["sentences"].extend(retry["sentences"])
        failed["quality_segments"].extend(retry["quality_segments"])
        paths = [dump(tmp_path / "failure-and-retry.json", failed)]
    else:
        paths = [dump(tmp_path / "failure.json", failed), dump(tmp_path / "retry.json", retry)]
    with pytest.raises(ValueError, match="Duplicate reference-eligible chunk/shared population") as error:
        compose(paths, iterations=20)
    assert "run=failed-run" in str(error.value)
    assert "attempt=1" in str(error.value)
    assert "attempt=2" in str(error.value) if same_report else "run=retry-run" in str(error.value)
    assert "no retry is selected automatically" in str(error.value)


@pytest.mark.parametrize("field", ["text", "session_id", "reference_id"])
def test_shared_source_conflicts_reject_without_comparing_generated_ids(tmp_path, field):
    left, right = metrics("left", "LEFT", (2,)), metrics("right", "RIGHT", (10,))
    right["sentences"][0][field] = "different source"
    if field == "text":
        right["quality_segments"][0]["reference"][0]["text"] = "different source"
    if field == "session_id":
        right["quality_segments"][0]["session_id"] = "different source"
    with pytest.raises(ValueError, match="Incompatible shared source identity/text/session"):
        compose([dump(tmp_path / "left.json", left), dump(tmp_path / "right.json", right)], iterations=20)


def test_invalid_attempts_remain_retained_but_are_not_paired(tmp_path):
    left, right = metrics("left", "LEFT", (2,)), metrics("right", "RIGHT", (10,))
    left["quality_segments"][0].update(reference_eligible=False, eligible=False, status="invalid")
    left["sentences"][0].update(eligible=False, status="invalid", outcome="N/A")
    result = compose([dump(tmp_path / "left.json", left), dump(tmp_path / "right.json", right)], iterations=20)
    assert result["paired"] == []
    assert len(result["pairing_population"]) == 1
    assert result["reports"][0]["report"] == left


def test_duplicate_files_and_raw_plus_joined_source_are_rejected(tmp_path):
    original = metrics("one-run", "LEFT")
    path = dump(tmp_path / "metrics.json", original)
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="Duplicate batch input file"):
        compose([path, path], iterations=20)
    joined = {**original, "quality_provenance": {"source_report_sha256": checksum}}
    quality = dump(tmp_path / "quality.json", {"joined_metrics_reports": [joined]})
    with pytest.raises(ValueError, match="Duplicate source metrics report"):
        compose([path], quality_report_paths=[quality], iterations=20)
    # Exporting a joined metrics envelope does not give it a new source population.
    exported = dump(tmp_path / "joined-metrics.json", joined)
    with pytest.raises(ValueError, match="Duplicate source metrics report"):
        compose([exported], quality_report_paths=[quality], iterations=20)


def test_joined_quality_cli_pairs_actual_report_files_without_scoring(tmp_path):
    originals = [metrics("left-run", "LEFT", (2,)), metrics("right-run", "RIGHT", (10,))]
    for index, original in enumerate(originals):
        source_path = dump(tmp_path / f"source-{index}.json", original)
        original["quality_provenance"] = {"source_report_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                                          "selected_actual_model": "synthetic-no-model-called"}
    quality = dump(tmp_path / "quality.json", {"joined_metrics_reports": originals})
    destination = tmp_path / "batch.json"
    process = subprocess.run([sys.executable, "-B", "-m", "bench.cli", "metrics-batch", "--quality-report", str(quality),
                              "--output", str(destination), "--iterations", "20", "--seed", "7"],
                             cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == {"report": str(destination), "version": "metrics-batch-v1", "reports": 2,
                                         "pairing_segments": 2, "paired": 1}
    result = json.loads(destination.read_text(encoding="utf-8"))
    assert comparison(result)["major_error_difference"]["value"] == 1
    assert [row["report_pointer"] for row in result["reports"]] == ["/joined_metrics_reports/0", "/joined_metrics_reports/1"]
    assert [row["report"] for row in result["reports"]] == originals


def test_cli_rejects_duplicate_population_without_writing_batch(tmp_path):
    first = dump(tmp_path / "one.json", metrics("one-run", "LEFT"))
    second = dump(tmp_path / "two.json", metrics("two-run", "LEFT"))
    destination = tmp_path / "batch.json"
    process = subprocess.run([sys.executable, "-B", "-m", "bench.cli", "metrics-batch", "--report", str(first),
                              "--report", str(second), "--output", str(destination)],
                             cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert process.returncode == 2
    assert "Duplicate reference-eligible chunk/shared population" in process.stderr
    assert not destination.exists()


def test_generated_capture_ids_can_differ_for_the_same_shared_source(tmp_path):
    left, right = metrics("left", "LEFT", (2,)), metrics("right", "RIGHT", (10,))
    right["sentences"][0].update(id="different-generated-sentence", attempt_id=41, clock_session="different-clock")
    right["quality_segments"][0].update(id="different-generated-segment", attempt_id=41, clock_session="different-clock",
                                       reference=[{"sentence_id": "different-generated-sentence", "text": "Source 1"}])
    result = compose([dump(tmp_path / "left.json", left), dump(tmp_path / "right.json", right)], iterations=20)
    assert comparison(result)["fol_difference"]["value"] == -8
    assert [row["attempt_id"] for row in result["pairing_population"]] == [1, 41]
    assert [row["session_id"] for row in result["pairing_population"]] == ["original-1", "original-1"]
