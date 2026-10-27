"""Pure reconstruction and offline replay; never launch apps or call providers."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from bench.history import event_sha256, reconstruct_history, source_prefix


RULE = {"id": "fixture-supported-output-v1",
        "description": "The synthetic endpoint explicitly identifies independent items and their replacement/clear operations.",
        "evidence": ["tests/test_history.py synthetic endpoint contract; not evidence about a real application"]}


def event(text="translation", *, time=1, **fields):
    return {"record": "native_output_event", "episode_id": "episode", "profile": "P",
            "attempt": 1, "pass_id": "A", "role": "A", "input_channel": "self",
            "clock_session": "session", "target_language": "zh", "native_id": None,
            "translated_text": text, "source_text": "native ASR is audit, not reference",
            "native_endpoint": "synthetic.output", "endpoint_stage": "translation_output",
            "collector_received_monotonic": time + 1,
            "event_time_interval": {"earliest_ns": time, "latest_ns": time, "clock_session": "session"},
            "clock_mapping": {"evidence": ["Synthetic common monotonic endpoint clock"]},
            "raw_evidence": {"sha256": "original-wire-hash", "allowlisted_projection": {"text": text}},
            **fields}


def interpretations(rows, operations):
    result = []
    for index, operation in enumerate(operations):
        if operation is None:
            continue
        fields = {"operation": operation} if isinstance(operation, str) else operation
        result.append({"event_index": index, "event_sha256": event_sha256(rows[index]),
                       "rule": RULE, **fields})
    return result


def reconstruct(rows, operations=None, **kwargs):
    return reconstruct_history(rows, role="A", interpretations=interpretations(rows, operations) if operations else None,
                               **kwargs)


def test_evidenced_cumulative_revisions_are_one_item_but_true_repeat_remains():
    rows = [event("A", time=1), event("A+B", time=2), event("A+B+C", time=3), event("A+B+C", time=4)]
    original = copy.deepcopy(rows)
    result = reconstruct(rows, ["append", {"operation": "replace", "replaces_event_index": 0},
                                {"operation": "replace", "replaces_event_index": 1}, "append"])
    assert result["status"] == "reconstructed"
    assert result["text"] == "A+B+C\nA+B+C"
    assert len(result["items"]) == 2
    assert [revision.get("text") for revision in result["revisions"]] == ["A", "A+B", "A+B+C", "A+B+C"]
    assert [item["native_id"] for item in result["items"]] == [None, None]
    assert result["items"][0]["derived_item_id"] == "event:0"
    assert result["text_citations"][0]["citation"]["event_index"] == 2
    for span in result["text_citations"]:
        assert result["text"][span["start"]:span["end"]] == "A+B+C"
    assert rows == original
    json.dumps(result, allow_nan=False)


def test_clear_and_delete_archive_earlier_pages_without_semantic_retraction():
    rows = [event("earlier page"), event("", time=2), event("next page", time=3), event("", time=4)]
    result = reconstruct(rows, ["append", "clear", "append", {"operation": "delete", "replaces_event_index": 2}])
    assert result["text"] == "earlier page\nnext page"
    assert [item["active"] for item in result["items"]] == [False, False]
    assert [item["page"] for item in result["items"]] == [0, 1]
    assert result["revisions"][1]["archived_item_ids"] == ["event:0"]
    assert result["revisions"][3]["archived_item_ids"] == ["event:2"]


def test_replacement_can_correct_a_known_archived_item_without_losing_audit():
    rows = [event("wrong"), event("", time=2), event("correct", time=3)]
    result = reconstruct(rows, ["append", "clear", {"operation": "replace", "replaces_event_index": 0}])
    assert result["text"] == "correct"
    assert result["items"][0]["active"] is False
    assert result["revisions"][-1]["previous_text"] == "wrong"


def test_early_snapshot_does_not_leak_later_correction_anywhere_in_json():
    rows = [event("wrong number 8", time=1), event("FUTURE SECRET number 3", time=10)]
    operations = ["append", {"operation": "replace", "replaces_event_index": 0}]
    early = reconstruct(rows, operations, cutoff_ns=5, clock_session="session")
    final = reconstruct(rows, operations)
    assert early["text"] == "wrong number 8"
    assert "FUTURE SECRET" not in json.dumps(early)
    assert final["text"] == "FUTURE SECRET number 3"
    assert len(final["revisions"]) == 2


def test_late_correction_separate_from_final_observation_horizon():
    rows = [event("wrong", time=1), event("LATE CORRECTION", time=20)]
    result = reconstruct(rows, ["append", {"operation": "replace", "replaces_event_index": 0}], horizon_ns=15)
    assert result["text"] == "wrong"
    assert len(result["late_events"]) == 1
    assert "LATE CORRECTION" not in json.dumps(result)


@pytest.mark.parametrize("field,value,scope", [
    ("role", "B", {}), ("pass_id", "B", {"pass_id": "A"}),
    ("clock_session", "different", {"clock_session": "session"}),
    ("profile", "other", {"profile": "P"}), ("episode_id", "other", {"episode": "episode"}),
    ("attempt", 2, {"attempt": 1}), ("input_channel", "peer", {"channel": "self"}),
    ("target_language", "ko", {"target_language": "zh"}),
    ("run", "other-run", {"run": "selected-run"}),
    ("wave", "other-wave", {"wave": "selected-wave"}),
])
def test_explicit_scope_never_consumes_other_role_pass_clock_or_attempt(field, value, scope):
    rows = [event("right"), event("UNSELECTED NATIVE TEXT", time=2, **{field: value})]
    result = reconstruct(rows, ["append", "append"], **scope)
    assert result["text"] == "right"
    assert "UNSELECTED NATIVE TEXT" not in json.dumps(result)
    assert len(result["excluded_events"]) == 1


@pytest.mark.parametrize("field", ["run", "wave"])
def test_ambiguous_execution_identity_cannot_merge_histories(field):
    rows = [event("first", **{field: "one"}), event("second", **{field: "two"})]
    result = reconstruct(rows, ["append", "append"])
    assert result["text"] is None
    assert result["quality_eligible"] is False
    assert "ambiguous_" + field in result["reasons"]


def test_omitted_ambiguous_attempt_cannot_silently_merge_histories():
    rows = [event("first"), event("second", attempt=2)]
    result = reconstruct(rows, ["append", "append"])
    assert result["status"] == "unknown" and result["text"] is None
    assert "ambiguous_attempt" in result["reasons"]


@pytest.mark.parametrize("missing", ["role", "input_channel", "target_language"])
def test_unknown_extraction_is_not_empty_or_protocol_no_output(missing):
    row = event()
    row[missing] = None
    result = reconstruct([row], ["append"])
    assert result["status"] == "unknown"
    assert result["text"] is None and not result["quality_eligible"]
    assert result["no_output_certified"] is False


def test_interval_crossing_cutoff_is_unknown_and_withholds_raw_text():
    row = event("BOUNDARY SECRET", event_time_interval={"earliest_ns": 4, "latest_ns": 6, "clock_session": "session"})
    result = reconstruct([row], ["append"], cutoff_ns=5, clock_session="session")
    assert result["status"] == "unknown"
    assert "interval_crosses_cutoff" in result["reasons"]
    assert "BOUNDARY SECRET" not in json.dumps(result)
    later = reconstruct([row], ["append"], cutoff_ns=6, clock_session="session")
    assert later["text"] == "BOUNDARY SECRET" and later["timing_eligible"]


def test_definitely_future_event_crossing_horizon_does_not_poison_earlier_snapshot():
    rows = [event("early", time=1), event("FUTURE", event_time_interval={"earliest_ns": 10, "latest_ns": 20,
                                                                     "clock_session": "session"})]
    result = reconstruct(rows, ["append", "append"], cutoff_ns=5, horizon_ns=15, clock_session="session")
    assert result["text"] == "early" and result["timing_eligible"]
    assert "FUTURE" not in json.dumps(result)


@pytest.mark.parametrize("mapping", [None, {}, {"evidence": []}])
def test_receipt_time_does_not_become_producer_time_but_final_quality_can_be_available(mapping):
    rows = [event("observed output", time=1, clock_mapping=mapping)]
    final = reconstruct(rows, ["append"], horizon_ns=5)
    early = reconstruct(rows, ["append"], cutoff_ns=5, clock_session="session")
    assert final["text"] == "observed output" and final["quality_eligible"]
    assert not final["timing_eligible"]
    assert early["status"] == "unknown" and "observed output" not in json.dumps(early)


def test_valid_mapping_can_recover_proven_earlier_occurrence_despite_late_receipt():
    row = event("emitted before cutoff", time=1, collector_received_monotonic=20)
    result = reconstruct([row], ["append"], cutoff_ns=5, horizon_ns=15, clock_session="session")
    assert result["text"] == "emitted before cutoff"
    assert result["events"][0]["event"]["collector_received_monotonic"] == 20


def test_mismatched_mapping_clock_is_not_an_exact_time():
    row = event("secret", event_time_interval={"earliest_ns": 1, "latest_ns": 1, "clock_session": "old"})
    result = reconstruct([row], ["append"], cutoff_ns=5, clock_session="session")
    assert not result["timing_eligible"] and result["text"] is None
    assert "secret" not in json.dumps(result)


def test_late_unmapped_receipt_is_not_backdated_to_horizon():
    row = event("late", event_time_interval=None, collector_received_monotonic=20)
    result = reconstruct([row], ["append"], horizon_ns=15)
    assert len(result["late_events"]) == 1
    assert result["text"] is None
    assert not result["no_output_certified"]


def test_empty_kikitan_final_does_not_invent_clear_or_native_identity():
    rows = [event("cumulative", native_endpoint="recognition", native_final_signal=False),
            event("cumulative", native_endpoint="recognition", native_final_signal=True),
            event("", native_endpoint="recognition", native_final_signal=False)]
    result = reconstruct(rows)
    assert result["status"] == "unknown" and result["text"] is None
    assert len(result["emissions"]) == 3 and result["revisions"] == []
    assert all(row["native_id"] is None for row in rows)
    assert not result["no_output_certified"]


def test_native_update_names_and_message_ids_are_not_generic_relation_rules():
    rows = [event("A", native_id="same-message", update_kind="append"),
            event("A+B", native_id="same-message", update_kind="replace")]
    result = reconstruct(rows)
    assert result["text"] is None and result["revisions"] == []
    assert len(result["emissions"]) == 2


def test_vrclt_mixed_display_remains_unavailable_and_final_log_is_not_spliced():
    rows = [event(None, display_text="source\ntranslation", native_endpoint="/chatbox/input",
                  endpoint_stage="self_chatbox_udp", boundary="unstructured_chatbox_text"),
            event("complete final text", native_endpoint="FINAL", endpoint_stage="final_log_crosscheck")]
    result = reconstruct(rows)
    assert result["text"] is None and result["observed_text"] == ""
    assert result["emissions"][0]["event"]["display_text"] == "source\ntranslation"
    assert result["excluded_events"][0]["reason"] == "separate_final_crosscheck"


def test_interpretation_is_checksum_bound_and_requires_semantic_provenance():
    rows = [event("output")]
    binding = interpretations(rows, ["append"])
    binding[0]["event_sha256"] = "wrong"
    with pytest.raises(ValueError, match="match the cited native event"):
        reconstruct_history(rows, role="A", interpretations=binding)
    binding = interpretations(rows, ["append"])
    binding[0]["rule"] = {"id": "convenience", "description": "no source", "evidence": []}
    with pytest.raises(ValueError, match="semantic rule provenance"):
        reconstruct_history(rows, role="A", interpretations=binding)


def test_exact_native_text_slice_and_role_binding_never_replace_text_with_reference():
    row = event(None, role=None, display_text="source|target")
    bindings = interpretations([row], [{"operation": "append", "role": "A", "text_field": "display_text",
                                      "text_span": [7, 13]}])
    result = reconstruct_history([row], role="A", interpretations=bindings)
    assert result["text"] == "target"
    assert result["events"][0]["event"]["source_text"] == "native ASR is audit, not reference"
    assert row["role"] is None and row["translated_text"] is None


def test_unknown_replacement_target_is_not_a_successful_last_packet_fallback():
    rows = [event("last packet")]
    result = reconstruct(rows, [{"operation": "replace", "replaces_event_index": 9}])
    assert result["text"] is None and "replacement_target_unknown" in result["reasons"]


def test_gap_is_unknown_not_product_no_output():
    result = reconstruct([event("", loss_or_gap="collector_disconnected")], ["append"])
    assert result["text"] is None and "native_history_gap" in result["reasons"]
    assert not result["no_output_certified"]


def puri(text, identity):
    row = event(text, native_id=identity, producer_instance="producer", transport="cli_jsonl",
                native_endpoint="translation", endpoint_stage="self_pre_overlay_chatbox_projection")
    row["raw_evidence"]["allowlisted_projection"] = {
        "topic": "translation", "channel": "self", "text": text,
        "utterance_id": identity, "instance_id": "producer"}
    return row


def test_puri_unique_scoped_ids_introduce_items_even_when_strings_repeat():
    result = reconstruct([puri("repeat", "one"), puri("repeat", "two")])
    assert result["text"] == "repeat\nrepeat"
    assert all(revision["rule"]["id"] == "puripuly-cli-translation-unique-utterance-v1"
               for revision in result["revisions"])


def test_puri_repeated_id_needs_evidence_bound_replacement_not_blanket_upsert():
    rows = [puri("first", "one"), puri("second", "one")]
    unknown = reconstruct(rows)
    assert unknown["text"] is None and len(unknown["emissions"]) == 2
    bindings = interpretations(rows, [None, {"operation": "replace", "replaces_event_index": 0}])
    result = reconstruct_history(rows, role="A", interpretations=bindings)
    assert result["text"] == "second" and len(result["items"]) == 1


def test_source_prefix_preserves_exact_reference_and_other_speaker_context_without_future_text():
    units = [{"id": "a", "role": "A", "text": "exact reference", "start_ns": 0, "end_ns": 2,
              "translation_targets": [{"text": "exact", "source_characters": [0, 5]}],
              "citations": ["corpus unit a"]},
             {"id": "b", "role": "B", "text": "other audible speaker", "start_ns": 2, "end_ns": 4,
              "context_only": True},
             {"id": "c", "role": "A", "text": "FUTURE ANSWER", "start_ns": 5, "end_ns": 10,
              "translation_targets": [{"text": "FUTURE ANSWER"}]}]
    original = copy.deepcopy(units)
    result = source_prefix(units, cutoff_ns=104, origin_ns=100, clock_session="pass-A")
    assert result["units"] == units[:2] and result["quality_eligible"]
    assert result["text"] == "exact reference\nother audible speaker"
    assert "FUTURE ANSWER" not in json.dumps(result)
    assert units == original


def test_source_prefix_early_interruption_withholds_entire_unfinished_unit():
    units = [{"id": "u", "role": "A", "text": "UNHEARD SUFFIX", "start_ns": 0, "end_ns": 10}]
    interrupted = source_prefix(units, cutoff_ns=120, origin_ns=100, clock_session="pass-B",
                                input_available_until_ns=105)
    assert interrupted["status"] == "unknown" and interrupted["units"] == []
    assert "UNHEARD SUFFIX" not in json.dumps(interrupted)
    later = source_prefix(units, cutoff_ns=110, origin_ns=100, clock_session="pass-B")
    assert later["text"] == "UNHEARD SUFFIX"


def test_source_prefix_rejects_cross_clock_units():
    result = source_prefix([{"text": "secret", "start_ns": 0, "end_ns": 1, "clock_session": "other"}],
                           cutoff_ns=2, origin_ns=0, clock_session="pass")
    assert result["status"] == "unknown" and "secret" not in json.dumps(result)


EVIDENCE = Path(__file__).resolve().parents[1] / "profiles" / "evidence" / "r1"


@pytest.mark.parametrize("filename,count,status,emissions", [
    ("pp4-en-zh-native.jsonl", 10, "reconstructed", 10),
    ("vrct2-en-zh-native.jsonl", 7, "unknown", 7),
    ("vrcs2-en-zh-native.jsonl", 22, "unknown", 7),
    ("vrclt2-en-zh-native.jsonl", 44, "unknown", 12),
    ("vrcls1-en-zh-native.jsonl", 15, "unknown", 5),
    ("kiki2-websocket-en-zh-native.jsonl", 66, "unknown", 66),
    ("kiki2-websocket-runner-en-zh-native.jsonl", 66, "unknown", 66),
])
def test_retained_real_native_files_replay_offline_without_promotion(filename, count, status, emissions):
    path = EVIDENCE / filename
    before = path.read_bytes()
    rows = [json.loads(line) for line in before.decode("utf-8").splitlines()]
    original = copy.deepcopy(rows)
    result = reconstruct_history(rows, role="A")
    assert len(rows) == count and result["status"] == status
    assert len(result["emissions"]) == emissions
    assert not result["timing_eligible"] and not result["no_output_certified"]
    assert rows == original and path.read_bytes() == before
    assert all(audit["citation"]["raw_evidence"]["sha256"] for audit in result["emissions"])
    if status == "unknown":
        assert result["text"] is None and not result["quality_eligible"]
    else:
        assert len(result["items"]) == count
    json.dumps(result, allow_nan=False)


def test_raw_attempt_trace_keeps_interpretation_indexes_stable_without_scoring_playback_records():
    rows = [{"record": "attempt_start", "attempt": "unrelated-metadata"},
            {"record": "source_playback", "source_text": "NOT A REFERENCE", "clock_session": "other"},
            event("native output")]
    result = reconstruct(rows, [None, None, "append"])
    assert result["text"] == "native output"
    assert result["items"][0]["derived_item_id"] == "event:2"
    assert len(result["excluded_events"]) == 2
    assert "NOT A REFERENCE" not in json.dumps(result)


@pytest.mark.parametrize("offset,expected", [(0, "initial"), (2, "at two"), (5, "at five"),
                                           (10, "at ten"), (15, "at fifteen")])
def test_checkpoint_offsets_use_actual_pass_origin_and_then_available_revisions(offset, expected):
    origin = 123_000_000_000
    words = ["initial", "at two", "at five", "at ten", "at fifteen"]
    rows = [event(text, time=origin + second * 1_000_000_000)
            for second, text in zip((0, 2, 5, 10, 15), words)]
    operations = ["append"] + [{"operation": "replace", "replaces_event_index": index}
                               for index in range(4)]
    result = reconstruct(rows, operations, cutoff_ns=origin + offset * 1_000_000_000,
                         clock_session="session")
    assert result["text"] == expected and result["timing_eligible"]
    assert len(result["revisions"]) == [0, 2, 5, 10, 15].index(offset) + 1


def test_horizon_requires_a_bound_clock_not_just_plausible_receipt_numbers():
    row = event("output", clock_session=None, event_time_interval=None, clock_mapping=None)
    result = reconstruct([row], ["append"], horizon_ns=10)
    assert not result["quality_eligible"]
    assert "horizon_clock_unknown" in result["reasons"]
