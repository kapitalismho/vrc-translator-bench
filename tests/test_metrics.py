from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from bench.metrics import assemble_segments, derive, prepare_sentences
from bench.metrics_alignment import Alignment, cache_binding, final_outputs, interpret
from bench.metrics_diagnostics import diagnostics
from bench.metrics_inputs import ingest, source_time, timeline
from bench.metrics_stats import clustered


ROOT = Path(__file__).resolve().parents[1]
STYLES = json.loads((ROOT / "tests/fixtures/metrics-styles.json").read_text())


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def packet(seq, seconds, text="翻訳", **extra):
    return {"address": "/chatbox/input", "args": [text, True, False], "recv_seq": seq, "t_ns": round(seconds * 1e9),
            "clock_session": "clock", "config": "APP", "direction": "D1", "attempt": 1, **extra}


def sample(root, events=None, kind="chunk", native=None):
    reference = {"reference_level": "synthetic reference", "clip_id": "clip", "sentences": [
        {"id": "s1", "speaker": "a", "start": 0, "end": 2, "text": "Hello world"},
        {"id": "s2", "speaker": "a", "start": 3, "end": 4, "text": "Good day"}],
        "turns": [{"id": "t1", "speaker": "a", "start": 0, "end": 4, "text": "Hello world. Good day."}]}
    reference_path = native or dump(root / "reference.json", reference)
    stage = {"kind": kind, "direction": "D1", "chunk": "clip", "audio_sha256": "original-audio", "sample_rate": 48000,
             "duration_seconds": 4, "speech_intervals": [[0, 2], [3, 4]]}
    trace = [{"record": "attempt_start", "clock_session": "clock"},
             {"record": "source_playback", "clock_session": "clock", "config": "APP", "attempt": 1,
              "playback_dac_start_ns": 10_000_000_000, "calibration_offset_ns": 100_000_000, "observation_end_ns": 40_000_000_000}]
    trace_path = root / "attempt.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text("\n".join(json.dumps(row) for row in trace), encoding="utf-8")
    stream_path = root / "stream.jsonl"
    stream_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in (events or [])), encoding="utf-8")
    manifest = {"run": "synthetic-test", "updated_wall": "2026-10-21T00:00:00Z", "plan": {"synthetic": True, "stages": [stage]},
                "work": [{"id": 1, "stage": 0, "profile": "APP", "kind": kind, "state": "done", "outcome": "done"}],
                "attempts": [{"id": 1, "work_id": 1, "number": 1, "state": "done", "resumed": 0, "trace": "attempt.jsonl", "end_ns": 50_000_000_000}],
                "streams": [{"path": "stream.jsonl", "sha256": hashlib.sha256(stream_path.read_bytes()).hexdigest()}]}
    spec = {"schema_version": 1, "version": "synthetic-test-v1", "rules": {"APP": STYLES["append"]},
            "alignment": {"backend": "cache"}, "bootstrap": {"iterations": 20},
            "references": {"0": {"path": str(reference_path.resolve()), "units": "samples" if native else "seconds", "session_id": "original-session",
                                  "source_group": "en", "category": "general"}}}
    return dump(root / "manifest.json", manifest), dump(root / "spec.json", spec)


def link(root, manifest, spec, entries):
    _, specification, attempts, events, _ = ingest(manifest, spec)
    sentences, _ = prepare_sentences(attempts)
    outputs, _ = interpret(events, specification["rules"])
    cache = {"schema_version": 1, "version": "hand-inspected-synthetic-v1", "provenance": ["Synthetic test correspondence, not model alignment"], "links": {}}
    for output in outputs:
        if output["id"] in entries:
            ids = entries[output["id"]]
            cache["links"][output["id"]] = {"status": "aligned" if ids else "unrelated", "sentence_ids": ids,
                                            "binding": cache_binding(output, sentences), "reason": "Explicit synthetic correspondence",
                                            "adjudication": {"decision": "confirmed", "method": "synthetic fixture ground truth",
                                                             "evidence": ["The test defines the source/output correspondence explicitly; not human or model validation"]} if ids else None}
    return dump(root / "cache.json", cache)


def test_deadline_is_inclusive_negative_lul_missing_is_null_and_raw_unchanged(tmp_path):
    events = [packet(1, 11), packet(2, 12), packet(3, 29.1), packet(4, 29.100000001)]
    manifest, spec = sample(tmp_path, events)
    cache = link(tmp_path, manifest, spec, {"clock:1": ["1:clip/s1"], "clock:2": ["1:clip/s1"], "clock:3": ["1:clip/s2"], "clock:4": ["1:clip/s2"]})
    report = derive(manifest, spec, cache_path=cache)
    one, two = report["sentences"]
    assert one["fol"]["value"] == pytest.approx(0.9)
    assert one["lul"]["value"] == pytest.approx(-0.1)
    assert two["fol"]["value"] == pytest.approx(16)
    assert two["late_output_ids"] == ["clock:4"]
    assert two["delivery_status"] == "delivered"
    assert [row["raw"] for row in report["outputs"]] == events
    missing_manifest, missing_spec = sample(tmp_path / "missing")
    absent = derive(missing_manifest, missing_spec)["sentences"][0]
    assert absent["delivery_status"] == "no_output_before_deadline"
    assert absent["fol"]["value"] is None
    assert absent["lul"]["value"] is None


def test_unknown_correspondence_retained_and_reaches_nearest_quality_segment(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 13, "unmapped")])
    report = derive(manifest, spec)
    assert report["sentences"][0]["delivery_status"] == "unknown_correspondence"
    assert report["quality_segments"][0]["unaligned_output_ids"] == ["clock:1"]
    assert report["aggregates"][0]["delivery"]["value"] == 0
    assert report["output_population"]["unaligned_output_rate"]["value"] == 1

def test_orphan_output_without_captured_attempt_never_gets_playback_link(tmp_path):
    event = packet(1, 13, clock_session="manual-probe", attempt=None)
    manifest, spec = sample(tmp_path, [event, packet(2, 14, clock_session="manual-probe", attempt=None), packet(3, 15, clock_session="manual-probe", attempt=None)])
    specification = json.loads(spec.read_text())
    specification["rules"]["APP"] = {**STYLES["pagination"], "relationships": {"manual-probe:1": {"relation": "new"}, "manual-probe:2": {"relation": "pagination", "parent_id": "manual-probe:1"}}}
    dump(spec, specification)
    report = derive(manifest, spec)
    output = report["outputs"][0]
    assert output["alignment"]["status"] == "unknown"
    assert output["alignment"]["sentence_ids"] == []
    assert output["quality_segment_id"].startswith("orphan:manual-probe")
    assert report["output_population"]["orphans"] == 3
    assert report["sentences"][0]["delivery_status"] == "no_output_before_deadline"


def test_no_typing_final_marker_and_explicit_styles_not_prefix_heuristics():
    events = [packet(1, 1, "short"), packet(2, 2, "short longer"), packet(3, 3, "", address="/chatbox/typing", args=[False])]
    page, _ = interpret(events, {"APP": STYLES["pagination"]})
    assert [row["relation"] for row in page] == ["new", "pagination"]
    assert len(final_outputs(page)) == 2
    revision, _ = interpret(events, {"APP": STYLES["revision"]})
    assert [row["text"] for row in final_outputs(revision)] == ["short longer"]
    unknown_rule = {**STYLES["pagination"], "relationships": {}}
    unknown, _ = interpret(events, {"APP": unknown_rule})
    assert [row["relation"] for row in unknown] == ["unknown", "unknown"]
    resumed, _ = interpret([events[0], packet(1, 4, "short", clock_session="next")], {"APP": STYLES["append"]})
    assert not resumed[-1]["duplicate_observed"]


def test_cache_rejects_changed_raw_source_and_rule_version(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 13)])
    cache = link(tmp_path, manifest, spec, {"clock:1": ["1:clip/s1"]})
    specification = json.loads(spec.read_text())
    specification["rules"]["APP"] = {**STYLES["append"], "version": "changed"}
    dump(spec, specification)
    with pytest.raises(ValueError, match="Stale alignment cache"):
        derive(manifest, spec, cache_path=cache)


def test_clock_cable_mapping_uses_callback_frame_not_origin_extrapolation():
    playback = {"calibration_offset_ns": 100_000_000, "playback_dac_start_ns": 0}
    callbacks = [{"dac_t_ns": 5_000_000_000, "source_frame": 48000, "source_frames": 48000}]
    assert source_time(playback, callbacks, 1.5, 48000) == 5_600_000_000
    assert source_time(playback, callbacks, 0.5, 48000) is None
    assert source_time({**playback, "calibration_offset_ns": None}, callbacks, 1.5, 48000) is None


def test_isolated_uses_window_without_alignment_and_keeps_carryover(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 11), packet(2, 24.1), packet(3, 24.100000001)], kind="isolated")
    report = derive(manifest, spec)
    result = report["isolated"][0]
    assert result["output_ids"] == ["clock:1", "clock:2"]
    assert result["late_carryover_ids"] == ["clock:3"]
    assert result["first_from_end"]["value"] == pytest.approx(-3.1)
    assert result["quality"]["association"] == "window_only_no_alignment"
    assert all(row["alignment"]["sentence_ids"] == [] for row in report["outputs"])


def test_real_english_sample_filters_punctuation_and_keeps_uncertain_turns(tmp_path):
    isolated = timeline({"path": str(ROOT / "corpus/english/timelines/isolated-01.json"), "units": "samples", "session_id": "TS3007a", "source_group": "en"}, tmp_path)
    assert sum(row["scored"] for row in isolated["sentences"]) == 1
    assert any(row["eligibility_reason"] == "partial_reference" for row in isolated["sentences"])
    main = timeline({"path": str(ROOT / "corpus/english/timelines/main.json"), "metadata_path": str(ROOT / "corpus/english/manifest.json"), "units": "samples", "source_group": "en"}, tmp_path)
    first = next(row for row in main["sentences"] if row["scored"])
    assert first["start"] == 0.25
    assert first["turn_id"] is None
    assert len(first["candidate_turn_ids"]) == 2
    assert first["eligibility_reason"] == "ambiguous_containing_turn"
    assert sum(row["partial"] and row["scored"] for row in main["sentences"]) == 3


def test_real_chinese_bundle_is_not_double_offset_and_context_not_source_time(tmp_path):
    refs = timeline({"path": str(ROOT / "corpus/chinese/manifest.json"), "pointer": "/bundles/main/chunks", "units": "seconds", "source_group": "zh"}, tmp_path)
    row = next(row for row in refs["sentences"] if row["chunk_id"] == "zh-general-02")
    assert row["start"] == 200.25
    assert row["session_id"]
    assert row["original_id"] is None
    assert row["generated_id"] is True


def test_context_has_two_earlier_turns_including_non_target_speakers():
    sentences = [{"id": "1:c/s", "attempt_id": 1, "chunk_id": "c", "session_id": "original", "category": "general", "scored": True,
                  "start": 10, "end": 41, "audio_sha256": "audio", "direction": "D1", "config": "APP", "clock_session": "clock", "casual": False,
                  "kind": "chunk", "status": "done", "eligible": True, "resumed": False, "start_ns": 10, "end_ns": 41,
                  "speaker": "target", "text": "target", "uncertainty": "reference uncertainty", "reference_level": "human", "attempt_number": 1}]
    turns = [{"id": str(i), "attempt_id": 1, "session_id": "original", "start": i, "end": i + 1, "speaker": "other", "text": str(i)} for i in range(3)]
    segment = assemble_segments(sentences, turns, [], {})[0]
    assert [row["turn_id"] for row in segment["context"]] == ["1", "2"]
    assert all(not row["scored"] and row["speaker"] == "other" for row in segment["context"])


def test_supported_diagnostics_calculate_erasure_boundary_and_source_cer(tmp_path):
    events = [packet(1, 12, "Hello world|abc"), packet(2, 13, "Hello world|ax")]
    manifest, spec = sample(tmp_path, events)
    specification = json.loads(spec.read_text())
    specification["rules"]["APP"] = {**STYLES["revision"], "text_pattern": r"(?P<source>[^|]+)\|(?P<translation>.+)"}
    specification["evidence"] = {"clock:2": {"provenance": ["synthetic boundary"], "clock_session": "clock", "boundary": {"identifiable": True,
        "source_boundary_ns": 12_000_000_000, "sentence_end_ns": 12_100_000_000, "endpoint_ns": 12_300_000_000,
        "expected_source_unit_ids": ["w1", "w2"], "delivered_source_unit_ids": ["w1", "w1"]}}}
    dump(spec, specification)
    cache = link(tmp_path, manifest, spec, {"clock:1": ["1:clip/s1"], "clock:2": ["1:clip/s1"]})
    report = derive(manifest, spec, cache_path=cache)
    diag = report["diagnostics"]["attempts"][0]
    assert diag["source_cer"]["value"] == 0
    assert diag["erasure"][0]["characters_erased"]["value"] == 2
    assert diag["endpoint_cut_tradeoff"][0]["endpoint_delay"]["value"] == 1
    assert diag["endpoint_cut_tradeoff"][0]["mid_sentence_cut"]["value"] is True
    assert diag["endpoint_cut_tradeoff"][0]["boundary_loss"]["value"] == 1
    assert diag["endpoint_cut_tradeoff"][0]["boundary_duplication"]["value"] == 1


def test_nonspeech_counts_actual_two_intervals_not_hourly(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 10.1), packet(2, 130.1), packet(3, 190.1)], kind="nonspeech")
    report = derive(manifest, spec)
    assert [row["count"]["value"] for row in report["diagnostics"]["nonspeech"]] == [1, 1]
    assert report["diagnostics"]["puripuly_internal"]["status"] == "N/A"


def test_cluster_bootstrap_keeps_original_sessions_and_small_n_visible():
    rows = [{"session_id": "one", "value": value} for value in range(20)]
    result = clustered(rows, lambda sample: sum(row["value"] for row in sample) / len(sample), 40, 7, "seconds")
    assert result["original_sessions"] == 1
    assert result["confidence_interval_95"] is None
    second = rows + [{"session_id": "two", "value": 100}]
    assert clustered(second, lambda sample: sum(row["value"] for row in sample) / len(sample), 40, 7, "seconds") == clustered(second, lambda sample: sum(row["value"] for row in sample) / len(sample), 40, 7, "seconds")


def test_cli_runs_from_this_checkout_and_rejects_stale_stream(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 13)])
    output = tmp_path / "report.json"
    import os
    cache = link(tmp_path, manifest, spec, {"clock:1": ["1:clip/s1"]})
    relative_cache = os.path.relpath(cache, ROOT)
    process = subprocess.run([sys.executable, "-m", "bench.cli", "metrics", "--manifest", str(manifest), "--spec", str(spec), "--alignment-cache", relative_cache, "--output", str(output)], cwd=ROOT, capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    assert json.loads(output.read_text())["version"] == "issue5-v1"
    (tmp_path / "stream.jsonl").write_text("{}", encoding="utf-8")
    failed = subprocess.run([sys.executable, "-m", "bench.cli", "metrics", "--manifest", str(manifest), "--spec", str(spec), "--output", str(output)], cwd=ROOT, capture_output=True, text=True)
    assert failed.returncode == 2
    assert "checksum mismatch" in failed.stderr


def test_late_only_and_known_unrelated_output_are_not_unknown_delivery(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 29.2), packet(2, 15, "unrelated")])
    cache = link(tmp_path, manifest, spec, {"clock:1": ["1:clip/s1"], "clock:2": []})
    report = derive(manifest, spec, cache_path=cache)
    assert report["sentences"][0]["delivery_status"] == "no_output_before_deadline"
    assert report["sentences"][0]["late_output_ids"] == ["clock:1"]
    assert report["sentences"][0]["fol"]["value"] is None
    assert len(report["outputs"]) == 2
    assert report["output_population"]["unaligned_output_rate"]["value"] == 0.5
    assert report["output_population"]["alignment_status_counts"] == {"aligned": 1, "unrelated": 1}


def test_cached_correspondence_can_recover_earlier_direction_not_capture_context(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 13, direction="D2", attempt=999, chunk="later")])
    cache = link(tmp_path, manifest, spec, {"clock:1": ["1:clip/s1"]})
    report = derive(manifest, spec, cache_path=cache)
    assert report["sentences"][0]["delivery_status"] == "delivered"
    assert report["outputs"][0]["raw"]["direction"] == "D2"
    assert report["aggregates"][0]["unaligned_output_rate"]["denominator"] == 1


def test_exported_cache_replays_and_same_version_changed_rule_is_rejected(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 13)])
    cache = link(tmp_path, manifest, spec, {"clock:1": ["1:clip/s1"]})
    report_path = tmp_path / "first-report.json"
    first = derive(manifest, spec, report_path, cache)
    second = derive(manifest, spec, cache_path=report_path)
    assert second["sentences"][0]["fol"] == first["sentences"][0]["fol"]
    specification = json.loads(spec.read_text())
    specification["rules"]["APP"]["uncertainty"] = "changed interpretation, same version"
    dump(spec, specification)
    with pytest.raises(ValueError, match="Stale alignment cache"):
        derive(manifest, spec, cache_path=report_path)


def test_failed_first_attempt_and_resumed_retry_stay_distinct(tmp_path):
    manifest, spec = sample(tmp_path)
    data = json.loads(manifest.read_text())
    data["attempts"][0]["state"] = "invalid"
    data["attempts"][0]["reason"] = "interrupted"
    retry = {**data["attempts"][0], "id": 2, "number": 2, "state": "done", "reason": None, "resumed": 1, "trace": "retry.jsonl"}
    trace = [json.loads(line) for line in (tmp_path / "attempt.jsonl").read_text().splitlines()]
    for row in trace:
        row["clock_session"] = "resume"
        if row["record"] == "source_playback":
            row["attempt"] = 2
    (tmp_path / "retry.jsonl").write_text("\n".join(json.dumps(row) for row in trace), encoding="utf-8")
    data["attempts"].append(retry)
    dump(manifest, data)
    report = derive(manifest, spec)
    assert [row["state"] for row in report["attempts"]] == ["invalid", "done"]
    assert report["aggregates"][0]["first_attempt_product_failure_rate"]["statuses"] == {"invalid": 1}
    assert report["aggregates"][0]["first_attempt_product_failure_rate"]["denominator"] == 0
    assert report["resume_sensitivity"][0]["with_resumed"]["eligible_sentences"] == 2
    assert report["resume_sensitivity"][0]["without_resumed"]["eligible_sentences"] == 0


def test_paired_shared_segments_include_failure_and_keep_session_cluster(tmp_path):
    from bench.metrics_stats import aggregate
    manifest, spec = sample(tmp_path, [packet(1, 13), packet(2, 14)])
    cache = link(tmp_path, manifest, spec, {"clock:1": ["1:clip/s1"], "clock:2": ["1:clip/s2"]})
    report = derive(manifest, spec, cache_path=cache)
    report["quality_segments"][0]["quality_score"] = {"major_error": False, "provenance": ["synthetic"]}
    other = copy.deepcopy(report["quality_segments"][0])
    other.update({"id": "2:clip:quality-2", "attempt_id": 2, "config": "OTHER", "status": "product_failure", "quality_score": {"major_error": True, "provenance": ["synthetic"]}})
    report["quality_segments"].append(other)
    for source in list(report["sentences"]):
        row = copy.deepcopy(source)
        row.update({"id": row["id"].replace("1:", "2:", 1), "attempt_id": 2, "config": "OTHER", "status": "product_failure"})
        if row["original_id"] == "s2":
            row.update({"delivery_status": "no_output_before_deadline", "fol": {"value": None}, "lul": {"value": None}})
        report["sentences"].append(row)
    report["attempts"].append({**report["attempts"][0], "id": 2, "work_id": 2, "config": "OTHER", "state": "product_failure"})
    results = aggregate(report, {"iterations": 20})
    paired = results["paired"][0]
    assert paired["comparisons"]["all_shared"]["delivery_difference"]["value"] == 0.5
    assert paired["comparisons"]["all_shared"]["major_error_difference"]["value"] == -1
    assert paired["comparisons"]["all_shared"]["fol_difference"]["original_sessions"] == 1
    assert paired["comparisons"]["common_success_only_supplemental"]["delivery_difference"]["value"] is None
    other_result = next(row for row in results["aggregates"] if row["config"] == "OTHER")
    assert other_result["first_attempt_product_failure_rate"]["value"] == 1
    assert other_result["major_error_segment_rate"]["value"] == 1


def test_unknown_diagnostics_do_not_invent_zero_splits_or_semantic_confidence(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 13)])
    report = derive(manifest, spec)
    diag = report["diagnostics"]["attempts"][0]
    assert diag["sentence_splits"]["value"] is None
    assert diag["source_cer"]["value"] is None
    assert diag["revisions"]["value"] is None
    specification = json.loads(spec.read_text())
    specification["alignment"] = {"backend": "simalign", "model_path": "not-a-pinned-snapshot", "model_revision": "bad"}
    dump(spec, specification)
    unavailable = derive(manifest, spec)
    assert unavailable["outputs"][0]["alignment"]["status"] == "unknown"
    assert "SimAlign unavailable" in unavailable["outputs"][0]["alignment"]["reason"]


def test_japanese_style_ids_scope_reused_words_and_keep_automatic_uncertainty(tmp_path):
    path = dump(tmp_path / "ja-synthetic.json", {"reference_level": "automatic exploratory", "speaker_uncertainty": "estimated anonymous",
        "words": [{"id": 0, "chunk_id": "a", "start": 0, "end": 1, "speaker": "s", "text": "x"}, {"id": 0, "chunk_id": "b", "start": 2, "end": 3, "speaker": "s", "text": "y"}],
        "sentences": [{"chunk_id": "a", "source_id": "same-video", "start": 0, "end": 1, "speaker": "s", "word_ids": [0], "text": "x"},
                      {"chunk_id": "b", "source_id": "same-video", "start": 2, "end": 3, "speaker": "s", "word_ids": [0], "text": "y"}],
        "turns": [{"chunk_id": "a", "source_id": "same-video", "start": 0.1, "end": 1, "speaker": "s"},
                  {"chunk_id": "b", "source_id": "same-video", "start": 2, "end": 3, "speaker": "s"}]})
    refs = timeline({"path": str(path), "units": "seconds", "source_group": "ja"}, tmp_path)
    assert [row["session_id"] for row in refs["sentences"]] == ["same-video", "same-video"]
    assert len({row["id"] for row in refs["sentences"]}) == 2
    assert refs["sentences"][0]["eligibility_reason"] == "ambiguous_containing_turn"
    assert refs["sentences"][0]["uncertainty"] == "estimated anonymous"
    assert refs["sentences"][0]["casual"] is None


def test_japanese_boundary_long_speech_common_and_internal_signals_calculate(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 40, direction="D4"), packet(2, 50, "unknown", direction="D4"), packet(3, 100, direction="D4")])
    data = json.loads(manifest.read_text())
    data["plan"]["stages"][0].update({"direction": "D4", "duration_seconds": 80, "speech_intervals": [[0, 80]]})
    data["attempts"][0]["end_ns"] = 120_000_000_000
    dump(manifest, data)
    reference = json.loads((tmp_path / "reference.json").read_text())
    reference["sentences"][0].update({"start": 0, "end": 40})
    reference["sentences"][1].update({"start": 45, "end": 80})
    reference["turns"][0]["end"] = 80
    dump(tmp_path / "reference.json", reference)
    specification = json.loads(spec.read_text())
    specification["references"]["0"]["source_group"] = "ja"
    specification["common_clips"] = [{"chunk_id": "clip", "start": 0, "end": 80, "provenance": "synthetic frozen clip"}]
    specification["evidence"] = {"clock:1": {"provenance": ["synthetic predicate/cut"], "clock_session": "clock",
        "boundary": {"identifiable": True, "source_boundary_ns": 35_000_000_000, "sentence_end_ns": 50_100_000_000,
                     "speaker_crossing": True, "predicate_end_ns": 45_000_000_000}}}
    specification["puripuly_internal"] = [{"provenance": ["synthetic app-local events"], "clock_session": "app-clock",
        "speech_end_ns": 1_000_000_000, "endpoint_ns": 1_200_000_000, "asr_start_ns": 1_200_000_000, "asr_end_ns": 1_500_000_000,
        "queued_ns": 1_500_000_000, "generation_start_ns": 1_600_000_000, "first_token_ns": 1_800_000_000,
        "generation_end_ns": 2_000_000_000, "output_ns": 2_100_000_000}]
    dump(spec, specification)
    cache = link(tmp_path, manifest, spec, {"clock:1": ["1:clip/s1"], "clock:3": ["1:clip/s2"]})
    report = derive(manifest, spec, cache_path=cache)
    diag = report["diagnostics"]["attempts"][0]
    assert diag["endpoint_cut_tradeoff"][0]["japanese_speaker_boundary_crossing"]["value"] is True
    assert diag["endpoint_cut_tradeoff"][0]["japanese_pre_predicate_cut"]["value"] is True
    assert diag["long_speech_accumulation"][0]["last_minus_first_lul"]["value"] == pytest.approx(20)
    assert len(report["diagnostics"]["common_clips"][0]["timelines"]) == 3
    internal = report["diagnostics"]["puripuly_internal"]["records"][0]["decomposition"]
    assert {name: row["value"] for name, row in internal.items()} == {"endpoint": 0.2, "asr": 0.3, "queue": 0.1, "first_token": 0.2, "generation": 0.4, "output": 0.1}


def test_repeats_categories_and_unknown_casual_are_not_pooled_as_recordings(tmp_path):
    from bench.metrics_stats import aggregate
    manifest, spec = sample(tmp_path)
    report = derive(manifest, spec)
    for row in report["sentences"]:
        row["casual"] = True
    repeat = copy.deepcopy(report["sentences"][0])
    repeat.update({"id": "2:clip/s1", "attempt_id": 2, "kind": "repeat"})
    report["sentences"].append(repeat)
    stress = copy.deepcopy(report["sentences"][0])
    stress.update({"id": "3:clip/s1", "reference_id": "stress/s1", "attempt_id": 3, "category": "stress", "casual": None})
    report["sentences"].append(stress)
    result = aggregate(report, {"iterations": 20})
    assert {(row["category"], row["view"]) for row in result["aggregates"]} == {("general", "category"), ("general", "casual_only"), ("stress", "category")}
    assert result["repeat_variation"][0]["baseline_shared_subset"]["reference_sentences"] == 1
    assert result["repeats"][0]["delivery"]["original_sessions"] == 1
    assert next(row for row in result["aggregates"] if row["view"] == "category" and row["category"] == "general")["reference_sentences"] == 2


def test_unaligned_page_stays_nearest_instead_of_inheriting_parent_source_segment(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 20), packet(2, 70, "unmapped page")])
    reference = json.loads((tmp_path / "reference.json").read_text())
    reference["sentences"][0]["end"] = 31
    reference["sentences"][1].update({"start": 32, "end": 63})
    reference["turns"][0]["end"] = 63
    dump(tmp_path / "reference.json", reference)
    specification = json.loads(spec.read_text())
    specification["rules"]["APP"] = STYLES["pagination"]
    dump(spec, specification)
    cache = link(tmp_path, manifest, spec, {"clock:1": ["1:clip/s1"]})
    report = derive(manifest, spec, cache_path=cache)
    assert report["outputs"][0]["quality_segment_id"] != report["outputs"][1]["quality_segment_id"]
    assert report["quality_segments"][1]["unaligned_output_ids"] == ["clock:2"]
    assert report["quality_segments"][0]["cross_segment_group_ids"] == ["clock:1"]
    assert report["quality_segments"][0]["reconstruction_status"] == "unknown_observed_order_only"
    assert report["outputs"][1]["source_quality_segment_ids"] == []
    assert [segment["source_linked_output_ids"] for segment in report["quality_segments"]] == [["clock:1"], []]
    assert all(segment["eligible"] and segment["cross_segment_output_ids"] == [] for segment in report["quality_segments"])


def test_page_revisions_replace_explicit_parent_slots_and_keep_other_pages():
    rule = {**STYLES["pagination"], "relationships": {
        "clock:1": {"relation": "new"},
        "clock:2": {"relation": "pagination", "parent_id": "clock:1"},
        "clock:3": {"relation": "revision", "parent_id": "clock:1"},
        "clock:4": {"relation": "revision", "parent_id": "clock:3"},
        "clock:5": {"relation": "revision", "parent_id": "clock:2"},
        "clock:6": {"relation": "resend", "parent_id": "clock:4"},
        "clock:7": {"relation": "revision", "parent_id": "clock:6"}}}
    events = [packet(index, index, text) for index, text in enumerate(("page A", "page B", "corrected A", "A again", "corrected B", "A again", "final A"), 1)]
    outputs, nontranslation = interpret(events, {"APP": rule})
    assert nontranslation == []
    assert [(row["id"], row["text"]) for row in final_outputs(outputs)] == [("clock:7", "final A"), ("clock:5", "corrected B")]


def test_resend_capability_does_not_identify_equal_text_utterances():
    rule = {**STYLES["append"], "supports": {"resend": True},
            "relationships": {"clock:3": {"relation": "resend", "parent_id": "clock:2"}}}
    outputs, _ = interpret([packet(1, 11, "yes"), packet(2, 20, "yes"), packet(3, 21, "yes")], {"APP": rule})
    assert [row["relation"] for row in outputs] == ["new", "new", "resend"]
    assert [row["content_changed"] for row in outputs] == [True, True, False]
    assert [row["duplicate_observed"] for row in outputs] == [False, True, True]
    assert [row["id"] for row in final_outputs(outputs)] == ["clock:1", "clock:2"]


@pytest.mark.parametrize("translation", ["", "   "])
def test_source_only_extraction_is_retained_outside_translation_population(tmp_path, translation):
    event = packet(1, 13, f"Hello world|{translation}")
    manifest, spec = sample(tmp_path, [event])
    specification = json.loads(spec.read_text())
    specification["rules"]["APP"] = {**STYLES["append"], "text_pattern": r"(?P<source>[^|]+)\|(?P<translation>.*)"}
    dump(spec, specification)
    report = derive(manifest, spec)
    assert report["outputs"] == []
    assert report["nontranslation_observations"][0]["raw"] == event
    assert report["nontranslation_observations"][0]["source_text"] == "Hello world"
    assert report["nontranslation_observations"][0]["reason"] == "empty_extracted_translation"
    assert report["output_population"]["observed_translation_outputs"] == 0
    assert all(row["delivery_status"] == "no_output_before_deadline" for row in report["sentences"])
    assert all(row["output_ids"] == [] for row in report["quality_segments"])


def test_model_proposal_cache_needs_explicit_inspection_and_keeps_proposal_history(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 13)])
    report = derive(manifest, spec)
    entry = report["alignment_cache"]["links"]["clock:1"]
    entry.update({"method": "simalign", "proposal_status": "requires_adjudication", "proposed_sentence_ids": ["1:clip/s1"],
                  "token_links": [[0, 0]], "source_tokens": ["Hello"], "source_owners": ["1:clip/s1"], "target_tokens": ["翻訳"],
                  "rejected_support": [], "reason": "Synthetic proposal-policy fixture; not actual model execution"})
    cache = dump(tmp_path / "proposal-cache.json", report["alignment_cache"])
    provisional = derive(manifest, spec, cache_path=cache)
    assert provisional["sentences"][0]["delivery_status"] == "unknown_correspondence"
    assert provisional["sentences"][0]["fol"]["value"] is None
    entry.update({"status": "aligned", "sentence_ids": ["1:clip/s1"]})
    dump(cache, report["alignment_cache"])
    with pytest.raises(ValueError, match="requires explicit adjudication"):
        derive(manifest, spec, cache_path=cache)
    entry["adjudication"] = {"decision": "confirmed", "method": "bounded synthetic fixture inspection",
                             "evidence": ["This fixture explicitly assigns packet 1 to sentence s1; it does not validate the model"]}
    dump(cache, report["alignment_cache"])
    confirmed = derive(manifest, spec, cache_path=cache)
    assert confirmed["sentences"][0]["delivery_status"] == "delivered"
    assert confirmed["sentences"][0]["fol"]["value"] == pytest.approx(2.9)
    assert confirmed["outputs"][0]["alignment"]["token_links"] == [[0, 0]]
    assert confirmed["outputs"][0]["alignment"]["proposal_status"] == "requires_adjudication"
    assert confirmed["outputs"][0]["alignment"]["adjudication"] == entry["adjudication"]


def test_native_chinese_non_target_turns_supply_nonempty_joined_quality_context(tmp_path):
    refs = timeline({"path": str(ROOT / "corpus/chinese/manifest.json"), "pointer": "/bundles/main/chunks",
                     "units": "seconds", "source_group": "zh"}, tmp_path)
    non_target = [row for row in refs["turns"] if not row["scored"]]
    assert non_target
    assert all(row["text"].strip() and row["text_provenance"] == "native_context_joined_by_source_segment_ids" for row in non_target)
    manifest, spec = sample(tmp_path)
    attempts = ingest(manifest, spec)[2]
    attempts[0]["reference"] = refs
    sentences, turns = prepare_sentences(attempts)
    segments = assemble_segments(sentences, turns, [], {})
    assert segments
    assert all(row["text"].strip() for segment in segments for row in segment["context"])
    assert any(row.get("speaker") != segment["reference"][0]["speaker"] for segment in segments for row in segment["context"])


def test_aligned_pages_follow_their_source_segments_not_first_group_segment(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 20, "page A"), packet(2, 70, "page B")])
    reference = json.loads((tmp_path / "reference.json").read_text())
    reference["sentences"][0]["end"] = 31
    reference["sentences"][1].update({"start": 32, "end": 63})
    reference["turns"][0]["end"] = 63
    dump(tmp_path / "reference.json", reference)
    specification = json.loads(spec.read_text())
    specification["rules"]["APP"] = STYLES["pagination"]
    dump(spec, specification)
    cache = link(tmp_path, manifest, spec, {"clock:1": ["1:clip/s1"], "clock:2": ["1:clip/s2"]})
    report = derive(manifest, spec, cache_path=cache)
    assert [row["output_ids"] for row in report["quality_segments"]] == [["clock:1"], ["clock:2"]]
    assert [row["final_output"][0]["text"] for row in report["quality_segments"]] == ["page A", "page B"]
    assert all(row["cross_segment_group_ids"] == ["clock:1"] and row["reconstruction_status"] == "unknown_observed_order_only" for row in report["quality_segments"])
    assert [row["source_linked_output_ids"] for row in report["quality_segments"]] == [["clock:1"], ["clock:2"]]
    assert all(row["eligible"] and row["reference_eligible"] and row["cross_segment_output_ids"] == [] for row in report["quality_segments"])
    assert [row["source_quality_segment_ids"] for row in report["outputs"]] == [[report["quality_segments"][0]["id"]], [report["quality_segments"][1]["id"]]]


@pytest.mark.parametrize("test_kind", ["output_check", "isolated", "nonspeech"])
def test_reference_free_test_output_cannot_enter_continuous_quality(tmp_path, test_kind):
    manifest, spec = sample(tmp_path, [packet(1, 5, "other-test", attempt=2), packet(2, 11, "continuous")])
    data = json.loads(manifest.read_text())
    data["plan"]["stages"].append({**data["plan"]["stages"][0], "kind": test_kind})
    data["work"].append({"id": 2, "stage": 1, "profile": "APP", "kind": test_kind, "state": "done", "outcome": "done"})
    data["attempts"].append({**data["attempts"][0], "id": 2, "work_id": 2})
    dump(manifest, data)
    cache = link(tmp_path, manifest, spec, {"clock:2": ["1:clip/s1"]})
    report = derive(manifest, spec, cache_path=cache)
    continuous = next(row for row in report["quality_segments"] if not row["id"].startswith("orphan:"))
    orphan = next(row for row in report["quality_segments"] if row["id"].startswith("orphan:"))
    assert continuous["output_ids"] == ["clock:2"]
    assert continuous["unaligned_output_ids"] == []
    assert orphan["output_ids"] == ["clock:1"] and orphan["kind"] == test_kind
    assert not orphan["reference_eligible"]
    assert report["outputs"][0]["alignment"]["candidate_ids"] == []
    assert report["sentences"][1]["delivery_status"] == "no_output_before_deadline"
    assert report["aggregates"][0]["unaligned_output_rate"]["denominator"] == 1


def test_confirmed_delayed_translation_can_override_capture_test_population(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 13, "delayed continuous", attempt=2, direction="D2")])
    data = json.loads(manifest.read_text())
    data["plan"]["stages"].append({**data["plan"]["stages"][0], "kind": "output_check", "direction": "D2"})
    data["work"].append({"id": 2, "stage": 1, "profile": "APP", "kind": "output_check", "state": "done", "outcome": "done"})
    data["attempts"].append({**data["attempts"][0], "id": 2, "work_id": 2})
    dump(manifest, data)
    cache = link(tmp_path, manifest, spec, {"clock:1": ["1:clip/s1"]})
    report = derive(manifest, spec, cache_path=cache)
    assert report["outputs"][0]["capture_kind"] == "output_check"
    assert report["sentences"][0]["delivery_status"] == "delivered"
    assert report["outputs"][0]["quality_segment_id"] == report["quality_segments"][0]["id"]
    assert report["quality_segments"][0]["kind"] == "chunk"


def test_inspected_correspondence_preserves_negative_fol_with_reference_uncertainty(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 9.8)])
    specification = json.loads(spec.read_text())
    specification["references"]["0"]["uncertainty"] = "Synthetic reference-onset uncertainty; not a timing-accuracy claim"
    dump(spec, specification)
    cache = link(tmp_path, manifest, spec, {"clock:1": ["1:clip/s1"]})
    report = derive(manifest, spec, cache_path=cache)
    assert report["sentences"][0]["delivery_status"] == "delivered"
    assert report["sentences"][0]["fol"]["value"] == pytest.approx(-0.3)
    assert "reference-onset uncertainty" in report["sentences"][0]["uncertainty"]


@pytest.mark.parametrize("attempt_status", ["done", "invalid"])
def test_one_confirmed_merge_crossing_quality_cut_is_linked_everywhere_but_scored_nowhere(tmp_path, attempt_status):
    event = packet(1, 74.1, "translation of A and B")
    manifest, spec = sample(tmp_path, [event])
    reference = json.loads((tmp_path / "reference.json").read_text())
    reference["sentences"][0]["end"] = 31
    reference["sentences"][1].update({"start": 32, "end": 63})
    reference["turns"][0]["end"] = 63
    dump(tmp_path / "reference.json", reference)
    data = json.loads(manifest.read_text())
    data["attempts"][0].update({"state": attempt_status, "reason": "interrupted" if attempt_status == "invalid" else None, "end_ns": 110_000_000_000})
    dump(manifest, data)
    specification = json.loads(spec.read_text())
    specification["quality_scores"] = {
        "1:clip:quality-1": {"major_error": False, "provenance": ["Synthetic supplied score for testing exclusion; not a judge run"]},
        "1:clip:quality-2": {"major_error": True, "provenance": ["Synthetic supplied score for testing exclusion; not a judge run"]}}
    dump(spec, specification)
    cache = link(tmp_path, manifest, spec, {"clock:1": ["1:clip/s1", "1:clip/s2"]})
    report = derive(manifest, spec, cache_path=cache)
    segments = report["quality_segments"]
    segment_ids = [segment["id"] for segment in segments]
    assert len(report["outputs"]) == 1 and report["outputs"][0]["raw"] == event
    assert report["outputs"][0]["source_quality_segment_ids"] == segment_ids
    assert report["outputs"][0]["quality_segment_id"] == segment_ids[1]
    assert [segment["output_ids"] for segment in segments] == [[], ["clock:1"]]
    assert sum(len(segment["final_output"]) for segment in segments) == 1
    assert all(segment["source_linked_output_ids"] == ["clock:1"] and segment["cross_segment_output_ids"] == ["clock:1"] for segment in segments)
    assert all(segment["cross_segment_group_ids"] == ["clock:1"] for segment in segments)
    assert all(not segment["eligible"] and segment["quality_eligibility_reason"] == "unresolved_merged_output_allocation"
               and segment["reconstruction_status"] == "N/A_unresolved_merged_output_allocation" for segment in segments)
    assert all(segment["status"] == attempt_status for segment in segments)
    assert all(segment["reference_eligible"] == (attempt_status == "done") for segment in segments)
    assert all(segment["quality_score"] == specification["quality_scores"][segment["id"]] for segment in segments)
    coverage = report["quality_score_coverage"]
    assert coverage["total_segments"] == coverage["excluded_segments"] == coverage["supplied_major_error_scores"] == coverage["excluded_major_error_scores"] == 2
    assert coverage["eligible_segments"] == coverage["scored_eligible_segments"] == 0
    assert coverage["excluded_by_reason"]["unresolved_merged_output_allocation"] == segment_ids
    rate = report["aggregates"][0]["major_error_segment_rate"]
    assert rate["value"] is None and rate["eligible_segments"] == rate["scored_segments"] == 0
    assert report["output_population"]["observed_translation_outputs"] == 1
    if attempt_status == "done":
        assert all(sentence["delivery_status"] == "delivered" for sentence in report["sentences"])
        assert [sentence["fol"]["value"] for sentence in report["sentences"]] == [64.0, 32.0]
        assert [sentence["lul"]["value"] for sentence in report["sentences"]] == [33.0, 1.0]
        assert report["aggregates"][0]["delivery"]["value"] == 1
    else:
        assert report["attempts"][0]["reason"] == "interrupted"
        assert all(sentence["delivery_status"] == "N/A" and sentence["fol"]["reason"] == "operational_invalid" for sentence in report["sentences"])
        assert coverage["excluded_by_reason"]["attempt_status:invalid"] == segment_ids


def test_confirmed_multi_sentence_merge_inside_one_quality_segment_remains_scorable(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 15, "one translation of both short sentences")])
    specification = json.loads(spec.read_text())
    score = {"major_error": True, "provenance": ["Synthetic supplied score for testing a valid denominator; not a judge run"]}
    specification["quality_scores"] = {"1:clip:quality-1": score}
    dump(spec, specification)
    cache = link(tmp_path, manifest, spec, {"clock:1": ["1:clip/s1", "1:clip/s2"]})
    report = derive(manifest, spec, cache_path=cache)
    segment = report["quality_segments"][0]
    assert len(report["quality_segments"]) == 1
    assert report["outputs"][0]["source_quality_segment_ids"] == [segment["id"]]
    assert segment["source_linked_output_ids"] == segment["output_ids"] == ["clock:1"]
    assert segment["eligible"] and segment["reference_eligible"] and segment["quality_eligibility_reason"] is None
    assert segment["cross_segment_output_ids"] == segment["cross_segment_group_ids"] == []
    assert segment["reconstruction_status"] == "estimated_under_versioned_rules"
    assert segment["quality_score"] == score
    assert all(sentence["delivery_status"] == "delivered" for sentence in report["sentences"])
    rate = report["aggregates"][0]["major_error_segment_rate"]
    assert rate["value"] == rate["eligible_segments"] == rate["scored_segments"] == 1
    assert report["quality_score_coverage"]["eligible_segments"] == report["quality_score_coverage"]["scored_eligible_segments"] == 1
    assert report["quality_score_coverage"]["excluded_by_reason"] == {}
