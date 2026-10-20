from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from bench.metrics import derive
from bench.metrics_alignment import interpret
from bench.metrics_diagnostics import source_cer
from test_metrics import dump, link, packet, sample


ROOT = Path(__file__).resolve().parents[1]
RULE = {"version": "source-exposure-test-v1", "evidence": ["Controlled synthetic source and translation fields"],
        "style": "append", "text_pattern": r"(?P<source>[^|]*)\|(?P<translation>.+)", "supports": {}}


def exposed(texts, links=None, relationships=None):
    rule = {**RULE, "relationships": relationships or {}}
    outputs, _ = interpret([packet(i, 11 + i, text + "|translation") for i, text in enumerate(texts, 1)], {"APP": rule})
    for output in outputs:
        output["alignment"] = {"status": "aligned", "sentence_ids": (links or {}).get(output["id"], ["s1"])}
    return outputs


def refs(*texts):
    return [{"id": f"s{i}", "start": i, "text": text} for i, text in enumerate(texts or ("Hello world",), 1)]


def coverage(**ranges):
    return {output_id: {"provenance": ["Controlled fragment-to-reference correspondence"],
                        "source_coverage": [{"sentence_id": sentence_id, "start": start, "end": end}
                                            for sentence_id, start, end in spans]}
            for output_id, spans in ranges.items()}


def split_evidence():
    return coverage(**{"clock:1": [("s1", 0, 6)], "clock:2": [("s1", 6, 11)]})


def test_explicit_split_source_coverage_is_reconstructed_once_without_segmentation_penalty():
    result = source_cer(refs(), exposed(["Hello ", "world"]), split_evidence())
    assert result["value"] == 0
    assert result["denominator"] == 11
    assert result["evidence"][0]["edits"] == 0
    assert result["evidence"][0]["source_text"] == "Hello world"
    assert result["evidence"][0]["reconstruction_output_ids"] == ["clock:1", "clock:2"]


def test_fragment_transcription_errors_are_not_fabricated_as_zero():
    result = source_cer(refs(), exposed(["Hallo ", "world!"]), split_evidence())
    assert result["value"] == pytest.approx(2 / 11)
    assert result["denominator"] == 11
    assert result["evidence"][0]["edits"] == 2


@pytest.mark.parametrize("texts", [["Hello ", "world"], ["Hello world", "Hello world"], ["Hello", "Hello world"]])
def test_sentence_links_and_append_style_do_not_prove_fragments_or_snapshots(texts):
    result = source_cer(refs(), exposed(texts), {})
    assert result["value"] is None
    assert result["denominator"] is None
    assert "distinguish fragments from snapshots" in result["reason"]
    assert [row["source_text"] for row in result["evidence"][0]["observations"]] == texts


@pytest.mark.parametrize(("ranges", "reason"), [
    ([("s1", 7, 11)], "gap or overlap"),
    ([("s1", 5, 11)], "gap or overlap"),
    ([("s1", 6, 10)], "full reference coverage"),
    ([("s1", 6, 12)], "within reference bounds"),
    ([("s1", -1, 11)], "within reference bounds"),
    ([("s1", 6.0, 11)], "integer half-open"),
    ([("s1", True, 11)], "integer half-open"),
    ([("s1", 6, 6)], "within reference bounds"),
    ([("other", 6, 11)], "linked sentence IDs"),
])
def test_invalid_fragment_ranges_reduce_cer_to_na_with_evidence(ranges, reason):
    evidence = split_evidence()
    evidence["clock:2"]["source_coverage"] = [{"sentence_id": sid, "start": start, "end": end} for sid, start, end in ranges]
    result = source_cer(refs(), exposed(["Hello ", "world"]), evidence)
    assert result["value"] is None
    assert reason in result["reason"]
    assert result["evidence"][0]["observations"][1]["diagnostic_evidence"] == evidence["clock:2"]


def test_explicit_source_coverage_requires_existing_outer_provenance():
    evidence = split_evidence()
    evidence["clock:1"].pop("provenance")
    with pytest.raises(ValueError, match="requires provenance"):
        source_cer(refs(), exposed(["Hello ", "world"]), evidence)


def test_whole_source_cer_keeps_real_errors_and_counts_disjoint_sentences_once():
    outputs = exposed(["Hallo world", "Good day"], {"clock:1": ["s1"], "clock:2": ["s2"]})
    result = source_cer(refs("Hello world", "Good day"), outputs, {})
    assert result["value"] == pytest.approx(1 / 19)
    assert result["denominator"] == 19


def test_explicit_revision_uses_final_source_not_stale_snapshot():
    outputs = exposed(["Hallo world", "Hello world"], relationships={
        "clock:2": {"relation": "revision", "parent_id": "clock:1"}})
    result = source_cer(refs(), outputs, {})
    assert result["value"] == 0
    assert result["denominator"] == 11
    assert result["evidence"][0]["output_ids"] == ["clock:2"]


def test_merged_source_uses_reference_order_without_inventing_sentence_separator():
    outputs = exposed(["Hello worldGood day"], {"clock:1": ["s2", "s1"]})
    result = source_cer(refs("Hello world", "Good day"), outputs, {})
    assert result["value"] == 0
    assert result["denominator"] == 19
    assert result["evidence"][0]["sentence_ids"] == ["s1", "s2"]


def test_merged_and_split_source_can_reconstruct_supported_contiguous_coverage():
    outputs = exposed(["Hello worldGood ", "day"], {"clock:1": ["s1", "s2"], "clock:2": ["s2"]})
    evidence = coverage(**{"clock:1": [("s1", 0, 11), ("s2", 0, 5)], "clock:2": [("s2", 5, 8)]})
    result = source_cer(refs("Hello world", "Good day"), outputs, evidence)
    assert result["value"] == 0
    assert result["denominator"] == 19


def test_interleaved_merged_coverage_is_not_blindly_concatenated():
    outputs = exposed(["Helloworld", " "], {"clock:1": ["s1"], "clock:2": ["s1"]})
    evidence = coverage(**{"clock:1": [("s1", 0, 5), ("s1", 6, 11)], "clock:2": [("s1", 5, 6)]})
    result = source_cer(refs(), outputs, evidence)
    assert result["value"] is None
    assert "within-source-text offsets" in result["reason"]


@pytest.mark.parametrize("ranges", [[], {}, "0:11", [None]])
def test_malformed_coverage_shape_is_na_and_retained(ranges):
    evidence = split_evidence()
    evidence["clock:1"]["source_coverage"] = ranges
    result = source_cer(refs(), exposed(["Hello ", "world"]), evidence)
    assert result["value"] is None
    assert "reference sentence ranges" in result["reason"]
    assert result["evidence"][0]["observations"][0]["source_coverage"] == ranges


def test_merged_and_split_messages_without_fragment_coverage_stay_ambiguous():
    outputs = exposed(["Hello worldGood ", "day"], {"clock:1": ["s1", "s2"], "clock:2": ["s2"]})
    result = source_cer(refs("Hello world", "Good day"), outputs, {})
    assert result["value"] is None
    assert result["denominator"] is None
    assert result["evidence"][0]["sentence_ids"] == ["s1", "s2"]


def test_out_of_order_message_ranges_and_cross_attempt_merges_are_not_scored():
    outputs = exposed(["Hello world"], {"clock:1": ["s1"]})
    evidence = coverage(**{"clock:1": [("s1", 6, 11), ("s1", 0, 6)]})
    assert "reference sentence and character order" in source_cer(refs(), outputs, evidence)["reason"]
    outputs[0]["alignment"]["sentence_ids"].append("outside-attempt")
    result = source_cer(refs(), outputs, {})
    assert result["value"] is None
    assert "outside this attempt" in result["reason"]


def test_unicode_coverage_offsets_count_code_points_including_whitespace():
    outputs = exposed(["안녕 ", "🌍"])
    evidence = coverage(**{"clock:1": [("s1", 0, 3)], "clock:2": [("s1", 3, 4)]})
    result = source_cer(refs("안녕 🌍"), outputs, evidence)
    assert result["value"] == 0
    assert result["denominator"] == 4


def test_revision_of_earlier_fragment_preserves_later_page_for_source_cer():
    outputs = exposed(["Hallo ", "world", "Hello "], relationships={
        "clock:2": {"relation": "pagination", "parent_id": "clock:1"},
        "clock:3": {"relation": "revision", "parent_id": "clock:1"}})
    evidence = coverage(**{"clock:3": [("s1", 0, 6)], "clock:2": [("s1", 6, 11)]})
    result = source_cer(refs(), outputs, evidence)
    assert result["value"] == 0
    assert result["denominator"] == 11
    assert result["evidence"][0]["reconstruction_output_ids"] == ["clock:3", "clock:2"]


def test_ambiguous_component_prevents_misleading_partial_aggregate_but_keeps_supported_evidence():
    outputs = exposed(["Hello ", "world", "Good day"], {"clock:1": ["s1"], "clock:2": ["s1"], "clock:3": ["s2"]})
    result = source_cer(refs("Hello world", "Good day"), outputs, {})
    assert result["value"] is None
    assert result["denominator"] is None
    assert result["supported_reference_characters"] == 8
    assert result["supported_edits"] == 0
    assert [row["status"] for row in result["evidence"]] == ["N/A", "available"]


def composition_inputs(root, explicit=True):
    manifest, spec = sample(root, [packet(1, 12, "Hello |one"), packet(2, 13, "world|two")])
    specification = json.loads(spec.read_text())
    specification["rules"]["APP"] = copy.deepcopy(RULE)
    if explicit:
        specification["evidence"] = coverage(**{"clock:1": [("1:clip/s1", 0, 6)], "clock:2": [("1:clip/s1", 6, 11)]})
    dump(spec, specification)
    cache = link(root, manifest, spec, {"clock:1": ["1:clip/s1"], "clock:2": ["1:clip/s1"]})
    return manifest, spec, cache


def test_diagnostics_composition_preserves_split_counts_but_removes_cer_split_penalty(tmp_path):
    manifest, spec, cache = composition_inputs(tmp_path)
    report = derive(manifest, spec, cache_path=cache)
    diagnostic = report["diagnostics"]["attempts"][0]
    assert diagnostic["sentence_splits"]["value"] == 1
    assert diagnostic["source_cer"]["value"] == 0
    assert diagnostic["source_cer"]["denominator"] == 11
    assert [row["source_text"] for row in report["outputs"]] == ["Hello ", "world"]
    assert report["quality_segments"][0]["output_ids"] == ["clock:1", "clock:2"]


@pytest.mark.parametrize("explicit", [True, False])
def test_actual_metrics_cli_preserves_supported_or_ambiguous_source_reconstruction(tmp_path, explicit):
    manifest, spec, cache = composition_inputs(tmp_path, explicit)
    output = tmp_path / "report.json"
    process = subprocess.run([sys.executable, "-m", "bench.cli", "metrics", "--manifest", str(manifest), "--spec", str(spec),
                              "--alignment-cache", str(cache), "--output", str(output)],
                             cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["outputs"] == 2
    result = json.loads(output.read_text())["diagnostics"]["attempts"][0]["source_cer"]
    assert result["value"] == (0 if explicit else None)
    assert result["denominator"] == (11 if explicit else None)
    if not explicit:
        assert "distinguish fragments from snapshots" in result["reason"]


def test_source_only_observation_without_source_correspondence_remains_cer_na(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 12, "Hello world|")])
    specification = json.loads(spec.read_text())
    specification["rules"]["APP"] = {**RULE, "text_pattern": r"(?P<source>[^|]*)\|(?P<translation>.*)"}
    dump(spec, specification)
    report = derive(manifest, spec)
    assert report["diagnostics"]["attempts"][0]["source_cer"]["value"] is None
    assert report["nontranslation_observations"][0]["source_text"] == "Hello world"
