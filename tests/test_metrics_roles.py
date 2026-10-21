from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from bench.metrics import assemble_segments, derive
from bench.metrics_alignment import Alignment, cache_binding, final_outputs, interpret
from bench.quality import load_plan, prepare
from bench.quality_prompts import blinded_input, fingerprint
from bench.quality_report import build_report, metricx_result
from test_metrics import dump, link, packet, sample


ROOT = Path(__file__).resolve().parents[1]
RULE = {"version": "controlled-single-pair-v1", "evidence": ["Synthetic formatter boundary fixture; not app measurement"],
        "style": "unknown", "text_pattern": r"(?P<translation>[^()]*) \((?P<source>[^()]*)\)",
        "supports": {"revision": False, "erasure": False, "resend": False}, "relationships": {}}
AMBIGUOUS = "訳 (literal) (source)"


def role_fixture(root, first=AMBIGUOUS):
    manifest, spec = sample(root, [packet(1, 13, first), packet(2, 45, "Valid (World)")])
    specification = json.loads(spec.read_text())
    specification["rules"]["APP"] = RULE
    dump(spec, specification)
    dump(root / "reference.json", {"clip_id": "clip", "sentences": [
        {"id": "s1", "speaker": "a", "start": 0, "end": 31, "text": "Hello"},
        {"id": "s2", "speaker": "a", "start": 32, "end": 63, "text": "World"}],
        "turns": [{"id": "t1", "speaker": "a", "start": 0, "end": 31, "text": "Hello"},
                  {"id": "t2", "speaker": "a", "start": 32, "end": 63, "text": "World"}]})
    capture = json.loads(manifest.read_text())
    capture["plan"]["stages"][0].update(duration_seconds=63, speech_intervals=[[0, 31], [32, 63]])
    capture["attempts"][0]["end_ns"] = 100_000_000_000
    dump(manifest, capture)
    cache = link(root, manifest, spec, {"clock:2": ["1:clip/s2"]})
    return manifest, spec, cache


def test_mismatched_role_never_becomes_translated_text_or_duplicate_nulls():
    events = [packet(1, 11, AMBIGUOUS), packet(2, 12, "truncated (source"), packet(3, 13, "Valid ()"),
              packet(4, 14, " (Recognized)"), packet(5, 15, "", address="/chatbox/typing", args=[False])]
    outputs, source_only = interpret(events, {"APP": RULE})
    assert [row["output_role"] for row in outputs] == ["unresolved", "unresolved", "translation"]
    assert [row["text"] for row in outputs] == [None, None, "Valid"]
    assert [row["duplicate_observed"] for row in outputs] == [False, False, False]
    assert [row["raw"] for row in outputs] == events[:3]
    assert [row["text"] for row in final_outputs(outputs)] == ["Valid"]
    assert all(row["content_changed"] is None and row["relation"] == "unknown" for row in outputs[:2])
    assert source_only[0]["output_role"] == "source_only"
    assert source_only[0]["source_text"] == "Recognized"
    assert outputs[2]["source_text"] == ""
    assert all(row["interpretation"]["evidence"] == RULE["evidence"] for row in outputs)


def test_unknown_role_cannot_inherit_explicit_group_or_cached_translation_credit(tmp_path, monkeypatch):
    rule = {**RULE, "relationships": {"clock:2": {"relation": "revision", "parent_id": "clock:1"}}}
    outputs, _ = interpret([packet(1, 11, "Valid (Source)"), packet(2, 12, AMBIGUOUS)], {"APP": rule})
    unknown = outputs[1]
    assert unknown["relation"] == "unknown" and unknown["parent_id"] is None
    assert unknown["group_id"] == unknown["id"]
    aligner = Alignment({"alignment": {"backend": "simalign"}}, tmp_path)
    candidates = [{"id": "s1", "text": "Source", "config": "APP", "clock_session": "clock", "direction": "D1", "start_ns": 1, "end_ns": 2}]
    aligner.links[unknown["id"]] = {"status": "aligned", "sentence_ids": ["s1"], "binding": cache_binding(unknown, candidates),
                                     "adjudication": {"decision": "confirmed", "method": "synthetic", "evidence": ["fixture"]}}
    monkeypatch.setattr(aligner, "model", lambda: pytest.fail("Unresolved-role text must not reach a model"))
    result = aligner.align(unknown, candidates, candidates)
    assert result["status"] == "unknown" and result["sentence_ids"] == []
    assert result["candidate_ids"] == ["s1"]
    assert result["reason"] == "unresolved_output_role"
    assert result["cached_correspondence_rejected"] is True


@pytest.mark.parametrize("text,expected", [(AMBIGUOUS, "unknown_correspondence"), (" (Hello)", "no_output_before_deadline")])
def test_unknown_role_is_not_missing_or_known_source_only(tmp_path, text, expected):
    manifest, spec = sample(tmp_path, [packet(1, 13, text)])
    specification = json.loads(spec.read_text())
    specification["rules"]["APP"] = RULE
    dump(spec, specification)
    result = derive(manifest, spec)
    assert result["sentences"][0]["delivery_status"] == expected
    assert result["sentences"][0]["fol"]["value"] is None
    assert result["quality_segments"][0]["final_output"] == []
    assert result["output_population"]["observed_translation_outputs"] == 0
    if text == AMBIGUOUS:
        assert result["sentences"][0]["unknown_candidate_ids"] == ["clock:1"]
        assert result["output_population"]["unresolved_output_ids"] == ["clock:1"]
        assert result["quality_segments"][0]["eligible"] is False
        assert result["quality_segments"][0]["quality_eligibility_reason"] == "unresolved_output_role"
    else:
        assert result["quality_segments"][0]["eligible"] is True
        assert result["nontranslation_observations"][0]["output_role"] == "source_only"


def test_all_candidate_segments_are_unscorable_even_with_supplied_scores(tmp_path):
    manifest, spec, _ = role_fixture(tmp_path, "Valid (Hello)")
    events = [packet(1, 45, AMBIGUOUS)]
    stream = tmp_path / "stream.jsonl"
    stream.write_text("\n".join(json.dumps(row) for row in events), encoding="utf-8")
    capture = json.loads(manifest.read_text())
    capture["streams"][0].pop("sha256")
    dump(manifest, capture)
    specification = json.loads(spec.read_text())
    specification["quality_scores"] = {f"1:clip:quality-{i}": {"major_error": False, "provenance": ["Synthetic supplied stale score"]} for i in (1, 2)}
    dump(spec, specification)
    result = derive(manifest, spec)
    assert len(result["outputs"][0]["alignment"]["candidate_ids"]) == 2
    assert len(result["quality_segments"]) == 2
    assert all(row["unresolved_output_ids"] == ["clock:1"] and not row["eligible"] for row in result["quality_segments"])
    assert all(row["quality_eligibility_reason"] == "unresolved_output_role" for row in result["quality_segments"])
    assert result["aggregates"][0]["major_error_segment_rate"]["scored_segments"] == 0
    assert result["diagnostics"]["attempts"][0]["source_cer"]["value"] is None
    assert result["output_population"]["unaligned_output_rate"]["denominator"] == 0
    assert result["output_population"]["output_role_counts"] == {"unresolved": 1}


def test_quality_inputs_are_unavailable_not_omissions_and_valid_jobs_survive(tmp_path):
    manifest, spec, cache = role_fixture(tmp_path / "inputs")
    result = derive(manifest, spec, cache_path=cache)
    unknown, valid = result["quality_segments"]
    with pytest.raises(ValueError, match="unresolved_output_role"):
        blinded_input(unknown)
    assert blinded_input(valid)["output_text"] == "Valid"
    path = dump(tmp_path / "metrics.json", result)
    plan = prepare([path], tmp_path / "queue", skip_tone=True, skip_korean_review=True)
    unavailable = next(row for row in plan["records"] if row["segment"]["id"] == unknown["id"])
    assert unavailable["input"] is None
    assert unavailable["input_unavailable_reason"] == "unresolved_output_role"
    assert all(job["record_key"] != unavailable["key"] for job in plan["jobs"])
    assert len([job for job in plan["jobs"] if not job["sanity"]]) == 1
    assert metricx_result(None, [{"input_hash": "unrelated", "result": {"status": "completed", "score": 1}}]) is None
    joined = build_report(tmp_path / "queue")
    assert joined["records"][0]["input"] is None
    assert all(row["esa"] is None and row["metricx"] is None for row in joined["records"])
    assert joined["joined_metrics_reports"][0]["quality_score_coverage"]["excluded_by_reason"] == {"unresolved_output_role": [unknown["id"]]}


@pytest.mark.parametrize("first,unresolved,source_only", [
    (AMBIGUOUS, True, False), (" (Hello)", False, True), ("Valid (Hello)", False, False)])
def test_untimed_capture_quality_is_unavailable_only_with_unresolved_role_in_actual_cli(tmp_path, first, unresolved, source_only):
    root = tmp_path / "inputs"
    manifest, spec, _ = role_fixture(root, first)
    trace = [json.loads(line) for line in (root / "attempt.jsonl").read_text().splitlines()]
    next(row for row in trace if row["record"] == "source_playback")["calibration_offset_ns"] = None
    (root / "attempt.jsonl").write_text("\n".join(json.dumps(row) for row in trace), encoding="utf-8")
    output, queue, joined = tmp_path / "metrics.json", tmp_path / "queue", tmp_path / "joined.json"
    commands = [["metrics", "--manifest", manifest, "--spec", spec, "--output", output],
                ["quality", "prepare", "--report", output, "--root", queue, "--skip-tone", "--skip-korean-review"],
                ["quality", "report", "--root", queue, "--output", joined]]
    for command in commands:
        process = subprocess.run([sys.executable, "-B", "-m", "bench.cli", *map(str, command)], cwd=ROOT,
                                 capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert process.returncode == 0, process.stderr
    metrics = json.loads(output.read_text(encoding="utf-8"))
    plan = json.loads((queue / "quality-plan.json").read_text(encoding="utf-8"))
    report = json.loads(joined.read_text(encoding="utf-8"))
    reference = [row for row in metrics["quality_segments"] if row["reference"]]
    assert len(reference) == 2
    assert all(row["start_ns"] is None and row["end_ns"] is None and row["final_output"] == [] for row in reference)
    assert all(row["reference_eligible"] and not row["timing_eligible"] for row in reference)
    assert all(row["delivery_status"] == "N/A" and row["eligibility_reason"] == "source_timing_unavailable"
               for row in metrics["sentences"])
    assert all(row["alignment"]["candidate_ids"] == [] and row["source_quality_segment_ids"] == [] for row in metrics["outputs"])
    assert "cache" not in metrics["alignment_provenance"]
    assert metrics["nontranslation_observations"][0]["output_role"] == "source_only" if source_only else not metrics["nontranslation_observations"]
    non_sanity = [job for job in plan["jobs"] if not job["sanity"]]
    if unresolved:
        unknown = metrics["outputs"][0]
        assert unknown["id"] == "clock:1" and unknown["raw"]["args"][0] == first and unknown["text"] is None
        assert unknown["untimed_capture_quality_segment_ids"] == [row["id"] for row in reference]
        assert unknown["quality_segment_id"].startswith("orphan:")
        assert set(unknown["unresolved_quality_segment_ids"]) == {row["id"] for row in metrics["quality_segments"]}
        assert all(not row["eligible"] and row["quality_eligibility_reason"] == "unresolved_output_role"
                   and row["unresolved_output_ids"] == ["clock:1"] for row in metrics["quality_segments"])
        assert non_sanity == []
        for record in [*plan["records"], *report["records"]]:
            assert record["input"] is None
            assert record["input_unavailable_reason"] == record["segment"]["quality_eligibility_reason"] == "unresolved_output_role"
        expected = [row["id"] for row in metrics["quality_segments"]]
        assert metrics["quality_score_coverage"]["excluded_by_reason"]["unresolved_output_role"] == expected
        assert report["joined_metrics_reports"][0]["quality_score_coverage"]["excluded_by_reason"] == {"unresolved_output_role": expected}
    else:
        assert all(row["eligible"] and row["quality_eligibility_reason"] is None and not row["unresolved_output_ids"] for row in reference)
        assert len(non_sanity) == 2
        assert all(record["input"] is not None and "input_unavailable_reason" not in record for record in plan["records"])
        assert all(job["input"]["output_text"] == "" for job in non_sanity)
    assert report["execution"]["calls"] == report["execution"]["metricx_calls"] == []


def test_untimed_role_exclusion_stays_within_exact_capture_population(tmp_path):
    manifest, spec, _ = role_fixture(tmp_path)
    trace = [json.loads(line) for line in (tmp_path / "attempt.jsonl").read_text().splitlines()]
    next(row for row in trace if row["record"] == "source_playback")["calibration_offset_ns"] = None
    (tmp_path / "attempt.jsonl").write_text("\n".join(json.dumps(row) for row in trace), encoding="utf-8")
    metrics = derive(manifest, spec)
    neighbors = []
    for field, value in (("attempt_id", 2), ("config", "OTHER"), ("clock_session", "other-clock"), ("direction", "D2"), ("kind", "repeat")):
        row = {**metrics["sentences"][0], "id": f"neighbor-{field}", "chunk_id": f"neighbor-{field}", field: value}
        neighbors.append(row)
    unknown = copy.deepcopy(metrics["outputs"][0])
    segments = assemble_segments([*metrics["sentences"], *neighbors], metrics["turns"], [unknown], {})
    affected = [row for row in segments if row["reference"] and not row["id"].startswith("1:neighbor-") and row["attempt_id"] == 1]
    untouched = [row for row in segments if row["reference"] and row not in affected]
    assert len(affected) == 2 and len(untouched) == 5
    assert unknown["untimed_capture_quality_segment_ids"] == [row["id"] for row in affected]
    assert all(not row["eligible"] and row["unresolved_output_ids"] == ["clock:1"] for row in affected)
    assert all(row["eligible"] and row["unresolved_output_ids"] == [] and row["quality_eligibility_reason"] is None for row in untouched)


@pytest.mark.parametrize("unknown_first", [True, False])
def test_role_reason_survives_cross_segment_exclusion_and_quality_report(tmp_path, unknown_first):
    root = tmp_path / "inputs"
    manifest, spec, _ = role_fixture(root)
    texts = [AMBIGUOUS, "Valid (Hello World)"] if unknown_first else ["Valid (Hello World)", AMBIGUOUS]
    events = [packet(index, seconds, text) for index, (seconds, text) in enumerate(zip((45, 70), texts), 1)]
    stream = root / "stream.jsonl"
    stream.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in events), encoding="utf-8")
    capture = json.loads(manifest.read_text())
    capture["streams"][0].pop("sha256")
    dump(manifest, capture)
    unknown_id, known_id = ("clock:1", "clock:2") if unknown_first else ("clock:2", "clock:1")
    cache = link(root, manifest, spec, {known_id: ["1:clip/s1", "1:clip/s2"]})
    metrics = derive(manifest, spec, cache_path=cache)
    segment_ids = [row["id"] for row in metrics["quality_segments"]]
    assert len(segment_ids) == 2
    assert sum(len(row["final_output"]) for row in metrics["quality_segments"]) == 1
    for segment in metrics["quality_segments"]:
        assert segment["eligible"] is False
        assert segment["unresolved_output_ids"] == [unknown_id]
        assert segment["quality_eligibility_reason"] == "unresolved_output_role"
        assert segment["source_linked_output_ids"] == segment["cross_segment_output_ids"] == [known_id]
        assert segment["cross_segment_group_ids"] == [known_id]
        assert segment["reconstruction_status"] == "N/A_unresolved_output_role"
    expected = {"unresolved_output_role": segment_ids}
    assert metrics["quality_score_coverage"]["excluded_by_reason"] == expected
    plan = prepare([dump(tmp_path / "metrics.json", metrics)], tmp_path / "queue",
                   skip_tone=True, skip_korean_review=True)
    assert not [job for job in plan["jobs"] if not job["sanity"]]
    joined = build_report(tmp_path / "queue")
    for record in [*plan["records"], *joined["records"]]:
        assert record["input"] is None
        assert record["input_unavailable_reason"] == record["segment"]["quality_eligibility_reason"] == "unresolved_output_role"
        assert record["segment"]["cross_segment_output_ids"] == [known_id]
    assert joined["joined_metrics_reports"][0]["quality_score_coverage"]["excluded_by_reason"] == expected
    assert all(row["exclusions"] == {"unresolved_output_role": 2} for row in joined["quality_populations"])
    assert joined["execution"]["calls"] == joined["execution"]["metricx_calls"] == []


def test_isolated_unknown_role_retains_activity_without_translation_response_or_score(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 13, AMBIGUOUS)], kind="isolated")
    specification = json.loads(spec.read_text())
    specification["rules"]["APP"] = RULE
    dump(spec, specification)
    result = derive(manifest, spec)
    isolated = result["isolated"][0]
    assert isolated["status"] == "unknown_output_role"
    assert isolated["raw_activity_ids"] == ["clock:1"]
    assert isolated["unresolved_output_ids"] == ["clock:1"]
    assert isolated["output_ids"] == []
    assert isolated["first_from_start"]["value"] is None
    assert isolated["quality"]["eligible"] is False
    assert isolated["quality"]["quality_eligibility_reason"] == "unresolved_output_role"
    assert isolated["quality"]["unresolved_output_ids"] == ["clock:1"]
    with pytest.raises(ValueError, match="unresolved_output_role"):
        blinded_input({"direction": "D1", **isolated["quality"]})


def test_nonspeech_counts_unknown_activity_separately_from_known_translation(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 11, AMBIGUOUS), packet(2, 12, "Valid (Source)"), packet(3, 13, " (Source)")], kind="nonspeech")
    specification = json.loads(spec.read_text())
    specification["rules"]["APP"] = RULE
    dump(spec, specification)
    result = derive(manifest, spec)
    interval = result["diagnostics"]["nonspeech"][0]
    assert interval["raw_activity_count"]["value"] == 3
    assert interval["known_translation_count"]["value"] == 1
    assert interval["unresolved_output_ids"] == ["clock:1"]
    assert interval["source_only_output_ids"] == ["clock:3"]
    assert interval["count"]["value"] == 2


def test_legacy_explicit_mismatch_requires_rederive_and_does_not_mutate_queue(tmp_path):
    manifest, spec = sample(tmp_path / "inputs", [packet(1, 13, "Valid")])
    result = derive(manifest, spec)
    good = dump(tmp_path / "good.json", result)
    queue = tmp_path / "queue"
    plan = prepare([good], queue, skip_tone=True, skip_korean_review=True)
    old = copy.deepcopy(result)
    old["outputs"][0]["extraction"] = "pattern_mismatch_unknown_translation"
    with pytest.raises(ValueError, match="rederive"):
        prepare([dump(tmp_path / "legacy.json", old)], tmp_path / "new-queue", skip_tone=True, skip_korean_review=True)
    plan["reports"][0]["report"] = old
    plan["binding"] = fingerprint({key: value for key, value in plan.items() if key != "binding"})
    frozen = dump(queue / "quality-plan.json", plan)
    before = frozen.read_bytes()
    with pytest.raises(ValueError, match="rederive"):
        load_plan(queue)
    assert frozen.read_bytes() == before


def test_actual_cli_metrics_prepare_report_with_ambiguous_and_valid_rows(tmp_path):
    manifest, spec, cache = role_fixture(tmp_path / "inputs")
    output, queue, joined = tmp_path / "metrics.json", tmp_path / "queue", tmp_path / "joined.json"
    commands = [["metrics", "--manifest", manifest, "--spec", spec, "--alignment-cache", cache, "--output", output],
                ["quality", "prepare", "--report", output, "--root", queue, "--skip-tone", "--skip-korean-review"],
                ["quality", "report", "--root", queue, "--output", joined]]
    for command in commands:
        process = subprocess.run([sys.executable, "-B", "-m", "bench.cli", *map(str, command)], cwd=ROOT,
                                 capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert process.returncode == 0, process.stderr
    metrics = json.loads(output.read_text(encoding="utf-8"))
    plan = json.loads((queue / "quality-plan.json").read_text(encoding="utf-8"))
    report = json.loads(joined.read_text(encoding="utf-8"))
    assert [row["delivery_status"] for row in metrics["sentences"]] == ["unknown_correspondence", "delivered"]
    assert [row["eligible"] for row in metrics["quality_segments"]] == [False, True]
    assert len([job for job in plan["jobs"] if not job["sanity"]]) == 1
    assert plan["records"][0]["input"] is None
    assert AMBIGUOUS not in json.dumps(plan["jobs"], ensure_ascii=False)
    assert report["records"][0]["input"] is None
    assert report["execution"]["calls"] == report["execution"]["metricx_calls"] == []


def test_common_timeline_keeps_raw_payload_separate_from_unknown_translation(tmp_path):
    manifest, spec, cache = role_fixture(tmp_path)
    specification = json.loads(spec.read_text())
    specification["common_clips"] = [{"chunk_id": "clip"}]
    dump(spec, specification)
    result = derive(manifest, spec, cache_path=cache)
    timeline = result["diagnostics"]["common_clips"][0]["timelines"]
    assert [row["raw_text"] for row in timeline] == [AMBIGUOUS, "Valid (World)"]
    assert [row["text"] for row in timeline] == [None, "Valid"]
    assert [row["output_role"] for row in timeline] == ["unresolved", "translation"]
    assert timeline[0]["alignment"]["sentence_ids"] == []


def test_known_and_unknown_isolated_activity_does_not_erase_valid_translation(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 11, "Valid (Source)"), packet(2, 13, AMBIGUOUS)], kind="isolated")
    specification = json.loads(spec.read_text())
    specification["rules"]["APP"] = RULE
    dump(spec, specification)
    result = derive(manifest, spec)
    isolated = result["isolated"][0]
    assert isolated["status"] == "response"
    assert isolated["output_ids"] == ["clock:1"]
    assert isolated["raw_activity_ids"] == ["clock:1", "clock:2"]
    assert isolated["unresolved_output_ids"] == ["clock:2"]
    assert isolated["first_from_start"]["value"] is not None
    assert isolated["last_content_change_from_end"]["value"] is None
    assert isolated["quality"]["eligible"] is False
    assert [row["text"] for row in isolated["quality"]["final_output"]] == ["Valid"]


def test_legacy_mismatch_cannot_reenter_batch_pairs(tmp_path):
    from bench.metrics_batch import compose

    manifest, spec = sample(tmp_path / "inputs", [packet(1, 13, "Valid")])
    result = derive(manifest, spec)
    result["outputs"][0]["extraction"] = "pattern_mismatch_unknown_translation"
    with pytest.raises(ValueError, match="rederive"):
        compose([dump(tmp_path / "legacy.json", result)])


@pytest.mark.parametrize("relation", ["revision", "pagination", "resend"])
def test_known_translation_cannot_group_under_an_unresolved_role_parent(relation):
    rule = {**RULE, "relationships": {"clock:2": {"relation": relation, "parent_id": "clock:1"}}}
    with pytest.raises(ValueError, match="translated output"):
        interpret([packet(1, 11, AMBIGUOUS), packet(2, 12, "Valid (Source)")], {"APP": rule})


def test_historical_source_only_records_keep_honest_role_coverage(tmp_path):
    from bench.metrics_stats import aggregate

    manifest, spec = sample(tmp_path, [packet(1, 13, " (Hello)")])
    specification = json.loads(spec.read_text())
    specification["rules"]["APP"] = RULE
    dump(spec, specification)
    result = derive(manifest, spec)
    result["nontranslation_observations"][0].pop("output_role")
    rebuilt = aggregate(result, {"iterations": 20})
    assert rebuilt["output_population"]["observed_translation_outputs"] == 0
    assert rebuilt["output_population"]["output_role_counts"] == {"source_only": 1}
