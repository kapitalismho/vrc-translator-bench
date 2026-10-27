"""Synthetic checks only; no IngCrowd expressive content is embedded here."""
from copy import deepcopy
import json

import pytest

from tools.prepare_ingcrowd import (
    annotations,
    check_selection,
    deduplicate_window_tokens,
    materialize,
    reference,
    review_windows,
)


EAF = b"""<ANNOTATION_DOCUMENT><TIME_ORDER>
<TIME_SLOT TIME_SLOT_ID="t1" TIME_VALUE="10"/>
<TIME_SLOT TIME_SLOT_ID="t2" TIME_VALUE="100"/>
<TIME_SLOT TIME_SLOT_ID="t3" TIME_VALUE="50"/>
<TIME_SLOT TIME_SLOT_ID="t4" TIME_VALUE="70"/>
</TIME_ORDER><TIER TIER_ID="speaker_1"><ANNOTATION>
<ALIGNABLE_ANNOTATION ANNOTATION_ID="a9" TIME_SLOT_REF1="t1" TIME_SLOT_REF2="t2">
<ANNOTATION_VALUE>synthetic question</ANNOTATION_VALUE>
</ALIGNABLE_ANNOTATION></ANNOTATION></TIER><TIER TIER_ID="speaker_2"><ANNOTATION>
<ALIGNABLE_ANNOTATION ANNOTATION_ID="a1" TIME_SLOT_REF1="t3" TIME_SLOT_REF2="t4">
<ANNOTATION_VALUE>synthetic response &lt;?&gt;</ANNOTATION_VALUE>
</ALIGNABLE_ANNOTATION></ANNOTATION></TIER></ANNOTATION_DOCUMENT>"""


def selected():
    return {"id": "synthetic", "source_samples": [80, 1760], "annotation_ids": ["a9", "a1"],
            "checkpoints": [{"evidence_annotation_ids": ["a9"], "concept": "synthetic question",
                             "allowed_paraphrases": ["equivalent question"], "must_preserve": ["question"]}]}


def catalogue():
    candidates = []
    for kind, count in (("P1", 3), ("P2", 9), ("P3", 6)):
        for index in range(count):
            start = len(candidates) * 100
            candidates.append({"id": f"{kind}-{index}", "kind": kind, "project_split": "main",
                               "dialogue": "01", "source_samples": [start, start + 100]})
        candidates.append({"id": f"{kind}-dev", "kind": kind, "project_split": "development",
                           "dialogue": "10", "source_samples": [len(candidates) * 100, len(candidates) * 100 + 100]})
    return {"candidates": candidates, "grouping": {"known_connected_dialogue_components": [["01"], ["10"]]}}


def test_human_eaf_preserves_overlapping_second_speaker_and_original_sample_clock():
    bound = reference(selected(), annotations(EAF))
    assert [row["id"] for row in bound["annotations"]] == ["a9", "a1"]
    assert bound["annotations"][0]["playback_samples"] == [80, 1520]
    assert bound["annotations"][1]["playback_samples"] == [720, 1040]
    assert bound["annotations"][1]["uncertain_marker_present"] is True
    assert bound["checkpoints"][0]["eaf_evidence_end_playback_sample"] == 1520
    assert bound["checkpoints"][0]["original_quotes"][0]["text"] == "synthetic question"
    assert bound["checkpoints"][0]["observation_offsets_seconds"] == [0, 2, 5, 10, 15]
    assert bound["checkpoints"][0]["certified_acoustic_end_sample"] is None


def test_partial_annotation_and_omitted_mixed_speaker_are_rejected():
    candidate = selected()
    candidate["source_samples"][1] = 1500
    with pytest.raises(ValueError, match="cuts an original EAF"):
        reference(candidate, annotations(EAF))
    candidate = selected()
    candidate["annotation_ids"] = ["a9"]
    with pytest.raises(ValueError, match="another audible speaker"):
        reference(candidate, annotations(EAF))


def test_adjacent_source_intervals_and_unresolved_recurring_identity_are_not_automatic_rejection():
    grouping = check_selection(catalogue())
    assert grouping["whole_dialogue_intersection"] == []
    assert grouping["unknown_recurring_speakers_independent"] is False


def test_known_participant_link_or_reused_dialogue_cannot_cross_split():
    record = catalogue()
    record["grouping"]["known_connected_dialogue_components"] = [["01", "10"]]
    with pytest.raises(ValueError, match="Known connected participant"):
        check_selection(record)
    record = catalogue()
    next(c for c in record["candidates"] if c["project_split"] == "development")["dialogue"] = "01"
    with pytest.raises(ValueError, match="Whole original dialogue"):
        check_selection(record)


def test_overlap_and_count_shortfall_cannot_be_hidden_by_weight_redistribution():
    record = catalogue()
    main = [c for c in record["candidates"] if c["project_split"] == "main"]
    main[1]["source_samples"] = deepcopy(main[0]["source_samples"])
    with pytest.raises(ValueError, match="source intervals overlap"):
        check_selection(record)
    record = catalogue()
    record["candidates"].pop(0)
    with pytest.raises(ValueError, match="fixed P1 main count"):
        check_selection(record)


def test_diagnostic_views_cover_same_source_with_bounded_overlap_and_no_replay_edit():
    windows = review_windows(45 * 16000)
    assert windows == [(0, 320000), (288000, 608000), (576000, 720000)]
    assert all(end - start <= 20 * 16000 for start, end in windows)
    assert all(left[1] - right[0] == 2 * 16000 for left, right in zip(windows, windows[1:]))
    assert review_windows(4 * 16000) == [(0, 4 * 16000)]


def test_overlap_deduplication_is_comparison_only_and_keeps_original_offsets():
    windows = [
        {"playback_samples": [0, 320000], "tokens": ["first", "overlap"], "timestamps": [1.0, 19.2]},
        {"playback_samples": [288000, 608000], "tokens": ["overlap", "next"], "timestamps": [1.2, 5.0]},
    ]
    original = deepcopy(windows)
    tokens = deduplicate_window_tokens(windows)
    assert [row["token"] for row in tokens] == ["first", "overlap", "next"]
    assert tokens[1]["approximate_playback_sample"] == round(19.2 * 16000)
    assert tokens[1]["window_index"] == 1
    assert windows == original


def test_source_acceptance_retains_unknown_marker_and_all_surrounding_targets():
    candidate = selected()
    candidate["source_review"] = {
        "status": "accepted",
        "annotation_notes": {"a1": {"uncertainty_scope": "original_marker_only",
                                     "decision": "Retain the unknown fragment, not an exemption of the response"}},
    }
    bound = reference(candidate, annotations(EAF))
    assert bound["status"] == "source_accepted"
    assert bound["annotations"][1]["text"] == "synthetic response <?>"
    assert bound["annotations"][1]["scope"] == "translation_and_context"
    assert bound["checkpoints"][0]["must_preserve"] == ["question"]
    assert bound["checkpoints"][0]["eaf_evidence_end_playback_sample"] == 1520
    assert "fixed source-reviewed" in bound["checkpoints"][0]["timing_status"]
    assert bound["checkpoints"][0]["certified_acoustic_end_sample"] is None


@pytest.mark.parametrize("notes", [
    {"a1": {"uncertainty_scope": "entire_annotation"}},
    {"a9": {"uncertainty_scope": "original_marker_only"}},
])
def test_acceptance_cannot_hide_annotation_or_invent_original_uncertainty(notes):
    candidate = selected()
    candidate["source_review"] = {"status": "accepted", "annotation_notes": notes}
    with pytest.raises(ValueError, match="Only an original uncertainty marker"):
        reference(candidate, annotations(EAF))


def test_review_note_must_name_an_included_original_annotation():
    candidate = selected()
    candidate["source_review"] = {"status": "accepted", "annotation_notes": {"outside": {"decision": "invalid"}}}
    with pytest.raises(ValueError, match="bind selected original annotations"):
        reference(candidate, annotations(EAF))


def test_full_source_acceptance_cannot_skip_a_case_decision(tmp_path):
    record = catalogue()
    record["source_acceptance"] = {"status": "accepted"}
    path = tmp_path / "catalogue.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    output = tmp_path / "prepared"
    with pytest.raises(ValueError, match="every selected case"):
        materialize(path, tmp_path, output)
    assert not output.exists()
