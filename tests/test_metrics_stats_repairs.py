from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from bench.metrics import assemble_segments, derive, timing
from bench.metrics_stats import aggregate
from test_metrics import dump, packet, sample


ROOT = Path(__file__).resolve().parents[1]


def source(identity, **changes):
    row = {"id": identity, "reference_id": identity, "turn_id": f"turn:{identity}", "attempt_id": 1,
           "attempt_number": 1, "run": "controlled", "config": "APP", "direction": "D1", "clock_session": "clock",
           "audio_sha256": "audio", "kind": "chunk", "status": "done", "outcome": "done", "resumed": False,
           "category": "general", "casual": True, "session_id": "original-a", "eligible": True,
           "eligibility_reason": None, "delivery_status": "delivered", "duration_bin": "2_to_5s",
           "start": 0, "end": 2, "fol": {"value": 10}, "lul": {"value": 10}}
    return {**row, **changes}


def turn(sentence, value, **changes):
    return {**sentence, "id": sentence["turn_id"], "lul": {"value": value, "reason": None if value is not None else "No supported related content change"}, **changes}


def segment(sentence, identity):
    reference_eligible = sentence["status"] in ("done", "product_failure") and sentence.get("outcome") != "N/A"
    return {**sentence, "id": identity, "shared_id": None, "reference_eligible": reference_eligible, "eligible": reference_eligible,
            "reference": [{"sentence_id": sentence["id"]}], "quality_score": None}


def output(identity, assigned, linked=(), **raw):
    return {"id": identity, "quality_segment_id": assigned, "alignment": {"status": "aligned" if linked else "unknown", "sentence_ids": list(linked)},
            "raw": {"config": "APP", "direction": "D1", "clock_session": "clock", "attempt": 1, **raw}}


def report(sentences, turns=(), segments=(), outputs=()):
    attempts = [{"id": identity, "work_id": identity, "number": 1, "state": "done", "outcome": "done"} for identity in {row["attempt_id"] for row in sentences}]
    return {"sentences": sentences, "turns": list(turns), "quality_segments": list(segments), "outputs": list(outputs), "attempts": attempts}


def view(result, category="general", casual=False, config="APP", direction="D1"):
    return next(row for row in result["aggregates"] if (row["config"], row["direction"], row["category"], row["view"]) == (config, direction, category, "casual_only" if casual else "category"))


def test_output_rates_use_distinct_source_populations_and_keep_delayed_attribution():
    casual = source("casual")
    general = source("general", casual=False)
    stress = source("stress", category="stress", casual=False)
    check = source("check", kind="output_check")
    segments = [segment(row, f"q:{row['id']}") for row in (casual, general, stress, check)]
    outputs = [output("delayed", "q:casual", [casual["id"]], direction="D2", attempt=999),
               output("casual-unknown", "q:casual"),
               output("general-unknown", "q:general"), output("stress-unknown", "q:stress"),
               output("orphan", "orphan:clock:APP"), output("check", "q:check")]
    result = aggregate(report([casual, general, stress], segments=segments, outputs=outputs), {"iterations": 40})
    for category, casual_only, denominator, value in (("general", False, 3, 2 / 3), ("general", True, 2, 0.5), ("stress", False, 1, 1)):
        rate = view(result, category, casual_only)["unaligned_output_rate"]
        assert rate["denominator"] == denominator
        assert rate["value"] == value
        assert rate["population_attribution"]["unassigned_capture_output_ids"] == ["orphan"]
    assert view(result)["unaligned_output_rate"]["population_attribution"]["selection_basis_counts"] == {"linked_source": 1, "assigned_quality_segment": 2}
    assert result["output_population"]["unaligned_output_rate"]["denominator"] == 6
    assert result["output_population"]["unaligned_output_rate"]["value"] == 5 / 6
    assert result["output_population"]["unassigned_output_ids"] == ["orphan"]


@pytest.mark.parametrize("raw", [{"clock_session": "other-clock"}, {"config": "OTHER"}])
def test_link_recovery_never_crosses_configuration_or_clock(raw):
    sentence = source("s")
    result = aggregate(report([sentence], segments=[segment(sentence, "q")], outputs=[output("bad-link", "q", ["s"], **raw)]), {"iterations": 10})
    assert view(result)["unaligned_output_rate"]["denominator"] == 0
    assert result["output_population"]["observed_translation_outputs"] == 1
    assert result["output_population"]["unassigned_output_ids"] == ["bad-link"]


def test_mixed_casual_assignment_is_disclosed_not_copied_into_casual_rate():
    casual, ordinary = source("casual"), source("ordinary", casual=False)
    mixed = {**segment(ordinary, "mixed"), "reference": [{"sentence_id": "casual"}, {"sentence_id": "ordinary"}]}
    result = aggregate(report([casual, ordinary], segments=[mixed], outputs=[output("unknown", "mixed")]), {"iterations": 10})
    assert view(result)["unaligned_output_rate"]["denominator"] == 1
    assert view(result, casual=True)["unaligned_output_rate"]["denominator"] == 0
    assert view(result, casual=True)["unaligned_output_rate"]["population_attribution"]["excluded_ambiguous_output_ids"] == ["unknown"]
    assert result["output_population"]["ambiguous_population_output_ids"] == ["unknown"]


def test_output_linked_to_multiple_populations_discloses_nonexclusive_attribution():
    general, stress = source("general"), source("stress", category="stress", casual=False)
    result = aggregate(report([general, stress], segments=[segment(general, "q")], outputs=[output("shared", "q", ["general", "stress"])]), {"iterations": 10})
    for category in ("general", "stress"):
        rate = view(result, category)["unaligned_output_rate"]
        assert rate["denominator"] == 1
        assert rate["population_attribution"]["ambiguous_output_ids"] == ["shared"]
    assert result["output_population"]["observed_translation_outputs"] == 1
    assert result["output_population"]["ambiguous_population_output_ids"] == ["shared"]


def test_turn_quantiles_cluster_original_sessions_and_preserve_failure_and_na_coverage():
    a = source("a")
    b = source("b", attempt_id=2, session_id="original-b", resumed=True)
    failed = source("failure", attempt_id=3, status="product_failure", delivery_status="no_output_before_deadline")
    invalid = source("invalid", attempt_id=4, eligible=False, eligibility_reason="operational_invalid", status="invalid")
    sentences = [a, b, failed, invalid]
    turns = [turn(a, -2), turn(b, 6), turn(failed, None), turn(invalid, 100)]
    result = aggregate(report(sentences, turns), {"iterations": 100, "seed": 7})
    result_view = view(result)
    assert result_view["lul_p50"]["value"] == 10
    assert result_view["turn_lul_p50"]["value"] == 2
    assert result_view["turn_lul_p90"]["value"] == pytest.approx(5.2)
    assert result_view["reference_turns"] == 4
    assert result_view["eligible_turns"] == 3
    assert result_view["measurable_turns"] == 2
    assert result_view["turn_denominator_coverage"] == {"eligible": 3, "operational_invalid": 1}
    assert result_view["turn_lul_unavailable_reasons"] == {"No supported related content change": 1}
    estimate = result_view["turn_lul_p50"]
    assert estimate["original_sessions"] == 2
    assert estimate["session_values"] == [{"session_id": "original-a", "value": -2}, {"session_id": "original-b", "value": 6}]
    assert estimate["confidence_interval_95"] == [-2, 6]
    sensitivity = next(row for row in result["resume_sensitivity"] if row["view"] == "category")
    assert sensitivity["with_resumed"]["turn_lul_p50"]["value"] == 2
    assert sensitivity["without_resumed"]["turn_lul_p90"]["value"] == -2
    assert sensitivity["without_resumed"]["turn_lul_p50"]["confidence_interval_95"] is None


@pytest.mark.parametrize("field,value", [("category", "stress"), ("config", "OTHER"), ("direction", "D2"), ("casual", False)])
def test_turn_population_views_follow_source_metadata(field, value):
    one, two = source("one"), source("two", **{field: value})
    result = aggregate(report([one, two], [turn(one, 1), turn(two, 9)]), {"iterations": 20})
    selected = view(result, casual=field == "casual")
    assert selected["turn_lul_p50"]["value"] == 1
    assert selected["eligible_turns"] == 1


def test_repeat_and_shared_baseline_have_turn_latency_not_sentence_substitutes():
    baseline = source("s")
    unrelated = source("outside", attempt_id=2)
    repeated = source("repeat-s", reference_id="s", kind="repeat", attempt_id=3)
    result = aggregate(report([baseline, unrelated, repeated], [turn(baseline, -1), turn(unrelated, 50), turn(repeated, 3)]), {"iterations": 20})
    assert result["repeats"][0]["turn_lul_p50"]["value"] == 3
    assert result["repeats"][0]["turn_lul_p90"]["confidence_interval_95"] is None
    variation = result["repeat_variation"][0]
    assert variation["baseline_shared_subset"]["turn_lul_p50"]["value"] == -1
    assert variation["repeat_attempts"][0]["turn_lul_p50"] == 3
    assert variation["repeat_attempts"][0]["turn_lul_p90"] == 3


def controlled_fixture(root):
    manifest, spec = sample(root, [packet(1, 13, "general", direction="D2", attempt=999), packet(2, 45, "ordinary"), packet(3, 77, "stress")])
    capture = json.loads(manifest.read_text())
    capture["plan"]["stages"][0].update(duration_seconds=68, speech_intervals=[[0, 2], [3, 4], [32, 34], [35, 36], [64, 66], [67, 68]])
    capture["attempts"][0]["end_ns"] = 110_000_000_000
    dump(manifest, capture)
    trace_path = root / "attempt.jsonl"
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    trace[1]["observation_end_ns"] = 110_000_000_000
    trace_path.write_text("\n".join(json.dumps(row) for row in trace), encoding="utf-8")
    specification = json.loads(spec.read_text())
    reference = {"chunks": []}
    for name, start, casual, category in (("casual", 0, True, "general"), ("ordinary", 32, False, "general"), ("stress", 64, False, "stress")):
        reference["chunks"].append({"clip_id": name, "category": category, "casual": casual,
            "sentences": [{"id": "s1", "speaker": "a", "start": start, "end": start + 2, "text": "Hello"},
                          {"id": "s2", "speaker": "a", "start": start + 3, "end": start + 4, "text": "World"}],
            "turns": [{"id": "t", "speaker": "a", "start": start, "end": start + 4, "text": "Hello world"}]})
    dump(root / "reference.json", reference)
    specification["references"]["0"].pop("category")
    specification["references"]["0"]["source_group"] = "synthetic"
    dump(spec, specification)
    initial = derive(manifest, spec)
    cache = copy.deepcopy(initial["alignment_cache"])
    cache["provenance"] = ["Explicit synthetic links for statistics repair, not a model accuracy claim"]
    cache["links"]["clock:1"].update(status="aligned", sentence_ids=["1:casual/s1"], reason="Inspected controlled correspondence")
    cache["links"]["clock:2"].update(status="aligned", sentence_ids=["1:ordinary/s1"], reason="Inspected controlled correspondence")
    for sequence, chunk in ((1, 0), (2, 1)):
        cache["links"][f"clock:{sequence}"]["adjudication"] = {
            "decision": "confirmed", "method": "synthetic_fixture_ground_truth",
            "evidence": [f"reference.json#/chunks/{chunk}/sentences/0", f"stream.jsonl#recv_seq={sequence}"]}
    return manifest, spec, dump(root / "cache.json", cache)


def test_cli_composes_population_and_turn_report_from_this_checkout(tmp_path):
    assert Path(sys.modules["bench.metrics_stats"].__file__).resolve() == ROOT / "bench/metrics_stats.py"
    manifest, spec, cache = controlled_fixture(tmp_path)
    destination = tmp_path / "report.json"
    process = subprocess.run([sys.executable, "-B", "-m", "bench.cli", "metrics", "--manifest", str(manifest), "--spec", str(spec), "--alignment-cache", str(cache), "--output", str(destination)], cwd=ROOT, capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    result = json.loads(destination.read_text(encoding="utf-8"))
    assert view(result)["unaligned_output_rate"]["denominator"] == 2
    assert view(result, casual=True)["unaligned_output_rate"]["denominator"] == 1
    assert view(result, "stress")["unaligned_output_rate"]["value"] == 1
    casual = view(result, casual=True)
    assert casual["turn_lul_p50"]["value"] == pytest.approx(-1.1)
    assert casual["lul_p50"]["value"] == pytest.approx(0.9)
    assert casual["turn_lul_p50"]["session_values"] == [{"session_id": "original-session", "value": pytest.approx(-1.1)}]
    assert view(result, "stress")["measurable_turns"] == 0
    assert result["output_population"]["unaligned_output_rate"]["denominator"] == 3


@pytest.mark.parametrize("merged_config", ["APP", "OTHER"])
@pytest.mark.parametrize("left_status", ["done", "product_failure"])
def test_merged_quality_allocation_keeps_paired_source_timing_but_not_scores(merged_config, left_status):
    sentences, outputs = [], []
    for config, attempt, status in (("APP", 1, left_status), ("OTHER", 2, "done")):
        members = []
        for name, start, end in (("a", 0, 31), ("b", 32, 63)):
            row = source(f"{attempt}:{name}", attempt_id=attempt, config=config, status=status,
                         reference_id=name, scored=True, chunk_id="clip", speaker="speaker", text=name,
                         uncertainty="controlled synthetic reference", reference_level="synthetic",
                         start=start, end=end, start_ns=start * 1_000_000_000, end_ns=end * 1_000_000_000,
                         duration_bin="above_5s", turn_id=f"{attempt}:turn", deadline_ns=78_000_000_000)
            members.append(row)
            sentences.append(row)
        links = [[row["id"] for row in members]] if config == merged_config else [[row["id"]] for row in members]
        for index, identities in enumerate(links):
            identity = f"{config}:{index}"
            outputs.append({**output(identity, "", identities, config=config, attempt=attempt, t_ns=(64 if config == "APP" else 61) * 1_000_000_000),
                            "group_id": identity, "relation": "new", "content_changed": True,
                            "text": "controlled merged translation" if config == merged_config else "controlled separate translation"})
    for row in sentences:
        timing(row, outputs, 80_000_000_000)
    segments = assemble_segments(sentences, [], outputs, {})
    merged_segments = [row for row in segments if row["config"] == merged_config]
    assert len(merged_segments) == 2
    assert all(row["reference_eligible"] and not row["eligible"] for row in merged_segments)
    assert all(row["quality_eligibility_reason"] == "unresolved_merged_output_allocation" for row in merged_segments)
    assert all(row["cross_segment_output_ids"] == [f"{merged_config}:0"] for row in merged_segments)
    assert all(row["source_linked_output_ids"] == [f"{merged_config}:0"] for row in merged_segments)
    assert sum(len(row["final_output"]) for row in merged_segments) == 1
    for row in segments:
        row["quality_score"] = {"major_error": row["config"] == merged_config, "provenance": ["Synthetic stale score to exercise quality eligibility gate"]}
    result = aggregate(report(sentences, segments=segments, outputs=outputs), {"iterations": 20})
    pair = result["paired"][0]
    assert len(pair["shared_segments"]) == 2
    comparisons = pair["comparisons"]["all_shared"]
    for name, expected in (("delivery_difference", 0), ("fol_difference", 3), ("lul_difference", 3)):
        assert comparisons[name]["value"] == expected
        assert comparisons[name]["observations"] == 2
        assert comparisons[name]["session_values"] == [{"session_id": "original-a", "value": expected}]
    assert comparisons["major_error_difference"]["value"] is None
    assert comparisons["major_error_difference"]["observations"] == 0
    supplemental = pair["comparisons"]["common_success_only_supplemental"]
    assert supplemental["delivery_difference"]["observations"] == (2 if left_status == "done" else 0)
    gated = view(result, config=merged_config)["major_error_segment_rate"]
    assert gated["eligible_segments"] == 0 and gated["scored_segments"] == 0
    assert gated["value"] is None
    other = view(result, config="OTHER" if merged_config == "APP" else "APP")["major_error_segment_rate"]
    assert other["eligible_segments"] == 2 and other["scored_segments"] == 2


@pytest.mark.parametrize("status,outcome,reference_eligible", [
    ("done", "done", True), ("product_failure", "failed", True),
    ("invalid", "invalid", False), ("done", "N/A", False)])
def test_paired_reference_eligibility_preserves_terminal_failure_policy(status, outcome, reference_eligible):
    left = source("left", status=status, outcome=outcome, eligible=reference_eligible)
    right = source("right", attempt_id=2, config="OTHER")
    segments = [segment(left, "left-q"), segment(right, "right-q")]
    for index, row in enumerate(segments):
        row.update(shared_id="shared", quality_score={"major_error": index == 0, "provenance": ["synthetic score"]})
    result = aggregate(report([left, right], segments=segments), {"iterations": 20})
    if not reference_eligible:
        assert result["paired"] == []
        return
    comparisons = result["paired"][0]["comparisons"]
    assert comparisons["all_shared"]["delivery_difference"]["value"] == 0
    assert comparisons["all_shared"]["major_error_difference"]["value"] == 1
    assert comparisons["common_success_only_supplemental"]["delivery_difference"]["observations"] == (1 if status == "done" else 0)


def test_paired_unknown_source_timing_stays_unmeasurable_without_dropping_quality_pair():
    left = source("left", eligible=False, eligibility_reason="ambiguous_containing_turn",
                  delivery_status="N/A", fol={"value": None}, lul={"value": None})
    right = source("right", attempt_id=2, config="OTHER")
    segments = [segment(left, "left-q"), segment(right, "right-q")]
    for index, row in enumerate(segments):
        row.update(shared_id="shared", quality_score={"major_error": index == 0, "provenance": ["synthetic score"]})
    assert all(row["reference_eligible"] for row in segments)
    result = aggregate(report([left, right], segments=segments), {"iterations": 20})
    assert result["paired"][0]["shared_segments"] == ["shared"]
    comparisons = result["paired"][0]["comparisons"]["all_shared"]
    for name in ("delivery_difference", "fol_difference", "lul_difference"):
        assert comparisons[name]["value"] is None
        assert comparisons[name]["observations"] == 0
    assert comparisons["major_error_difference"]["value"] == 1
