import copy
import io
import json
from pathlib import Path
import wave

import pytest

from tools.prepare_ascend import (
    REQUIRED, assemble, check_reservations, checked_bytes, checkpoint_map,
    connected_groups, decode_wave, materialize, reference_row, reference_spans, sha256, timeline,
)


@pytest.fixture
def catalogue():
    return json.loads((Path(__file__).resolve().parents[1] / "corpus/r2/ascend.json").read_text(encoding="utf-8"))


def clip(L, start, frames, role="A", person=17, language="en"):
    return {"annotation_L": L, "nominal_filename_start_sample_not_common_clock": start,
            "source_frames": frames, "logical_role": role, "original_speaker_id": person,
            "source_language_label": language, "natural_source_key": f"synthetic/{L}"}


def test_full_cells_preserve_connected_people_and_pre_result_choices(catalogue):
    result = check_reservations(catalogue)
    assert result["main_reserved_original_speakers"] == [1, 2, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 24, 26]
    assert result["development_reserved_original_speakers"] == [17, 18]
    assert result["known_intersection"] == []
    assert result["unknown_participation_certified_absent"] is False
    assert catalogue["split_reservations"]["filename_original_aliases"] == {"22": 1, "23": 2, "25": 9}
    for kind, (main, development) in REQUIRED.items():
        assert sum(c["kind"] == kind and c["project_split"] == "main" for c in catalogue["candidates"]) == main
        assert sum(c["kind"] == kind and c["project_split"] == "development" for c in catalogue["candidates"]) == development
        assert catalogue["pre_result_selection"]["repeat_episode_by_kind"][kind] in {c["id"] for c in catalogue["candidates"] if c["kind"] == kind and c["project_split"] == "main"}
    assert len(catalogue["cell_accounting"]["T1"]["reviewed_parent_ids_pending_acceptance"]) == 13
    assert set(catalogue["cell_accounting"]["T1"]["accepted_parent_ids"]) <= set(catalogue["cell_accounting"]["T1"]["reviewed_parent_ids_pending_acceptance"])


@pytest.mark.parametrize("mutation", ["overlap", "omit_partner", "wrong_split", "duplicate_interval", "language_routing", "missing_quantity", "lost_p1", "clock_reset", "part_change", "direction", "dependency"])
def test_changed_identity_group_role_or_quantity_is_rejected(catalogue, mutation):
    record = copy.deepcopy(catalogue)
    if mutation == "overlap":
        record["split_reservations"]["development_reserved_original_groups"][0].append(13)
    elif mutation == "omit_partner":
        record["candidates"][1]["reserved_original_speakers"] = [21]
    elif mutation == "wrong_split":
        record["candidates"][0]["clips"][0]["upstream_split"] = "test"
    elif mutation == "duplicate_interval":
        record["candidates"][1]["clips"][0]["archive_member"] = record["candidates"][0]["clips"][0]["archive_member"]
    elif mutation == "language_routing":
        candidate = next(c for c in record["candidates"] if c["kind"] == "T1")
        first = candidate["clips"][0]
        first["logical_role"] = "B" if first["logical_role"] == "A" else "A"
    elif mutation == "missing_quantity":
        record["candidates"].pop()
    elif mutation in ("clock_reset", "part_change"):
        candidate = next(c for c in record["candidates"] if c["kind"] == "T1")
        first = candidate["clips"][0]
        later = next(c for c in candidate["clips"][1:] if c["original_speaker_id"] == first["original_speaker_id"])
        if mutation == "clock_reset":
            later["nominal_filename_start_sample_not_common_clock"] = first["nominal_filename_start_sample_not_common_clock"] - 1
        else:
            later["filename_part"] = "a different recording part"
    elif mutation == "direction":
        candidate = next(c for c in record["candidates"] if c["kind"] == "T1")
        candidate["directions"]["A"]["source_language"] = "zh"
    elif mutation == "dependency":
        record["candidates"][0]["dependency_group_id"] = "independent-new-speaker"
    else:
        c = record["candidates"][0]["clips"][0]
        c.update(upstream_id="00000", natural_source_key=f"{record['dataset']}@{record['revision']}/train/00000")
    with pytest.raises(ValueError):
        check_reservations(record)


def test_references_come_from_exact_split_local_row_and_pinned_text():
    text = "synthetic reference only"
    row = {"file_name": "waves/ses1_spk17_L1_1.000_0.100.wav", "original_speaker_id": "17", "transcription": text}
    selected = {"upstream_split": "test", "upstream_id": "00000", "archive_member": row["file_name"],
                "original_speaker_id": 17, "annotation_L": 1,
                "nominal_filename_start_sample_not_common_clock": 16000, "reference_utf8_sha256": sha256(text.encode())}
    assert reference_row({"test": [row]}, selected) == (row, text.encode())
    with pytest.raises(ValueError, match="checksum"):
        reference_row({"test": [{**row, "transcription": "changed synthetic text"}]}, selected)
    with pytest.raises(ValueError, match="identity"):
        reference_row({"test": [{**row, "file_name": "waves/different.wav"}]}, selected)
    with pytest.raises(ValueError, match="five-digit"):
        reference_row({"test": [row]}, {**selected, "upstream_id": "0"})
    with pytest.raises(ValueError, match="Filename-local"):
        reference_row({"test": [row]}, {**selected, "nominal_filename_start_sample_not_common_clock": 16001})


def test_decode_preserves_sample_clock_and_rejects_wrong_frames_or_hash():
    pcm = b"\x00\x00\x01\x00\xff\xff"
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(pcm)
    assert decode_wave(buffer.getvalue(), 3, sha256(pcm)) == pcm
    with pytest.raises(ValueError, match="frame count"):
        decode_wave(buffer.getvalue(), 2, sha256(pcm))
    with pytest.raises(ValueError, match="Decoded PCM"):
        decode_wave(buffer.getvalue(), 3, sha256(b"wrong"))


def test_conditional_offset_uses_actual_frames_and_preserves_own_clock():
    clips = [clip(1, 100, 11), clip(2, 90, 7, "B", 18), clip(3, 140, 5)]
    result = timeline(clips, "T1")
    assert result["conditional_offset_bounds_samples"] == [21, 43]
    assert result["relative_offset_B_samples"] == 32
    assert result["positions"] == [0, 22, 40]
    assert result["frames"] == 45
    assert result["historical_synchrony_claimed"] is False
    assert all(not g["original_audio_or_historical_silence_recovered"] for g in result["gaps"])


@pytest.mark.parametrize("clips, reason", [
    ([clip(1, 0, 10), clip(2, 3, 20, "B", 18), clip(3, 15, 5)], "constraints conflict"),
    ([clip(1, 100, 10), clip(2, 20, 5, "B", 18)], "does not bound"),
    ([clip(1, 100, 10), clip(2, 90, 5)], "overlap or reset"),
])
def test_explicit_fallback_is_declared_and_never_hides_missing_gaps(clips, reason):
    result = timeline(clips, "T1", gap_samples=3)
    assert result["method"] == "explicit_paced_dialogue"
    assert reason in result["fallback_reason"]
    assert result["positions"][1] == clips[0]["source_frames"] + 3
    assert all(g["samples"] == 3 and g["origin"] == "experimenter_fixed_gap" for g in result["gaps"])
    assert result["relative_offset_B_samples"] is None


def test_same_person_continuation_preserves_internal_and_filename_gaps():
    result = timeline([clip(1, 100, 11), clip(2, 115, 8)], "P3")
    assert result["method"] == "same_speaker_filename_continuation"
    assert result["positions"] == [0, 15]
    assert result["gaps"][0]["samples"] == 4
    assert result["frames"] == 23
    reset = timeline([clip(1, 100, 11), clip(2, 10, 8)], "P3", 4)
    assert reset["method"] == "explicit_paced_continuation"
    assert reset["positions"] == [0, 15]
    with pytest.raises(ValueError, match="nonnegative"):
        timeline([clip(1, 0, 1)], "P3", -1)


def test_equal_role_buffers_preserve_code_switches_repeats_and_source_pcm():
    clips = [clip(1, 100, 2, "A", 17, "zh"), clip(2, 103, 3, "A", 17, "en"),
             clip(3, 109, 2, "B", 18, "en"), clip(4, 112, 1, "A", 17, "mixed")]
    policy = {"paced_gap_samples": 2, "relative_offset_B_samples": 0}
    candidate = {"kind": "T1", "roles": {"A": 17, "B": 18}, "clips": clips, "timing_policy": policy,
                 "timeline": timeline(clips, "T1", 2, 0)}
    pcm = {c["natural_source_key"]: bytes([i + 1, 0]) * c["source_frames"] for i, c in enumerate(clips)}
    mapping, roles, mixed = assemble(candidate, pcm)
    assert len(roles["A"]) == len(roles["B"]) == len(mixed) == mapping["frames"] * 2
    for c, start in zip(clips, mapping["positions"]):
        end = start + c["source_frames"]
        assert roles[c["logical_role"]][start * 2:end * 2] == pcm[c["natural_source_key"]]
        other = "B" if c["logical_role"] == "A" else "A"
        assert roles[other][start * 2:end * 2] == bytes(c["source_frames"] * 2)
        assert mixed[start * 2:end * 2] == pcm[c["natural_source_key"]]
    assert roles["A"][4:6] == b"\0\0"
    candidate["timeline"]["positions"][0] += 1
    with pytest.raises(ValueError, match="no longer reproduce"):
        assemble(candidate, pcm)


def test_target_and_context_spans_preserve_exact_source_coordinates():
    text = "I like 学会独立 and AI"
    spans = reference_spans(text)
    assert {s["language"] for s in spans} == {"en", "zh"}
    assert all(text[s["source_characters"][0]:s["source_characters"][1]] == s["text"] for s in spans)
    assert next(s for s in spans if s["language"] == "zh")["text"] == "学会独立"


def test_alias_people_link_across_filename_pairs_sessions_and_upstream_splits():
    def row(speaker, person, session):
        return {"file_name": f"waves/ses{session}_spk{speaker}_L{speaker}_0.0_1.0.wav",
                "original_speaker_id": str(person)}
    tables = {"train": [row(1, 1, 1), row(2, 2, 1), row(21, 21, 2), row(22, 1, 2)],
              "test": [row(23, 2, 3), row(24, 24, 3), row(17, 17, 1), row(18, 18, 1)]}
    assert connected_groups(tables) == [[1, 2, 21, 24], [17, 18]]


def test_checkpoint_maps_to_actual_clip_and_never_future_context_or_wrong_role():
    clips = [clip(1, 100, 10), clip(2, 120, 8, "B", 18), clip(3, 140, 5)]
    candidate = {"kind": "T1", "clips": clips}
    mapping = timeline(clips, "T1", relative_offset=0)
    texts = {1: "Will you wait? 已经是中文背景", 2: "我会等候。already English", 3: "Later."}
    definitions = [{"id": "a", "role": "A", "end_L": 1, "evidence_Ls": [1],
                    "required_concepts": ["request to wait"], "allowed_paraphrase_concepts": ["ask the listener to wait"],
                    "source_evidence_end_sample_proposal": 7,
                    "scored_translation_evidence": [{"annotation_L": 1, "source_characters": [0, 14]}],
                    "unscored_context_constraints": []},
                   {"id": "b", "role": "B", "end_L": 2, "evidence_Ls": [1, 2],
                    "required_concepts": ["will wait"], "allowed_paraphrase_concepts": ["agree to wait"],
                    "source_evidence_end_sample_proposal": 6,
                    "scored_translation_evidence": [{"annotation_L": 2, "source_characters": [0, 4]}],
                    "unscored_context_constraints": []}]
    result = checkpoint_map(candidate, definitions, mapping, texts)
    assert [c["playback_evidence_end_sample_proposal"] for c in result] == [7, 26]
    assert all(c["observation_offsets_seconds"] == [0, 2, 5, 10, 15] for c in result)
    assert not any(c["certified_phonetic_endpoint"] for c in result)
    assert [c["scored_translation_evidence"][0]["language"] for c in result] == ["en", "zh"]
    for mutation in ({"end_L": 99}, {"role": "B"}, {"evidence_Ls": [1, 3]},
                     {"source_evidence_end_sample_proposal": 11},
                     {"scored_translation_evidence": [{"annotation_L": 2, "source_characters": [0, 4]}]}):
        with pytest.raises(ValueError):
            checkpoint_map(candidate, [{**definitions[0], **mutation}, definitions[1]], mapping, texts)
    with pytest.raises(ValueError, match="Both T1"):
        checkpoint_map(candidate, definitions[:1], mapping, texts)


@pytest.fixture
def mixed_checkpoint_source():
    text = "I come from Korea. 这段中文已经说明两台设备都用overseas和top只是词"
    clips = [clip(1, 0, 100)]
    candidate = {"kind": "P2", "clips": clips}
    definition = {"id": "origin", "role": "A", "end_L": 1, "evidence_Ls": [1],
                  "required_concepts": ["speaker origin"], "allowed_paraphrase_concepts": ["comes from Korea"],
                  "source_evidence_end_sample_proposal": 100,
                  "scored_translation_evidence": [{"annotation_L": 1, "source_characters": [0, 18]}],
                  "unscored_context_constraints": [
                      {"meaning": "Both devices are used; this is already-Chinese input context",
                       "evidence_Ls": [1]}]}
    return candidate, definition, timeline(clips, "P1"), {1: text}


def test_context_output_is_not_required_and_cannot_supply_translation_credit(mixed_checkpoint_source):
    candidate, definition, mapping, texts = mixed_checkpoint_source
    result = checkpoint_map(candidate, [definition], mapping, texts)[0]
    evidence = result["scored_translation_evidence"]
    assert all(e["language"] == "en" for e in evidence)
    assert all(e["source_characters"][1] <= texts[1].index("这") for e in evidence)
    assert not any("\u3400" <= character <= "\u9fff" for e in evidence for character in e["text"])
    assert result["unscored_context_constraints"][0]["required_in_output"] is False
    assert result["unscored_context_constraints"][0]["translation_credit"] is False
    # This checks evidence projection, not a mock translation judge: semantic
    # entailment of required concepts still needs curated source review.
    assert "only to the scored translation evidence" in result["output_scope"]


@pytest.mark.parametrize("scope", ["chinese_only", "mixed_with_loanwords", "empty", "punctuation_only"])
def test_chinese_passthrough_and_loanwords_do_not_certify_a_chinese_proposition(mixed_checkpoint_source, scope):
    candidate, definition, mapping, texts = mixed_checkpoint_source
    text = texts[1]
    if scope == "empty":
        definition["scored_translation_evidence"] = []
    else:
        start, end = {
            "chinese_only": (text.index("这"), text.index("overseas")),
            "mixed_with_loanwords": (text.index("这"), len(text)),
            "punctuation_only": (text.index("."), text.index(".") + 1),
        }[scope]
        definition["scored_translation_evidence"][0]["source_characters"] = [start, end]
    with pytest.raises(ValueError, match="translation evidence|translation-target spans"):
        checkpoint_map(candidate, [definition], mapping, texts)


def test_reverse_t1_cannot_use_already_english_context_as_chinese_translation_evidence():
    clips = [clip(1, 0, 10), clip(2, 20, 10, "B", 18)]
    texts = {1: "Please wait.", 2: "我会等候 English context"}
    definitions = [
        {"id": "a", "role": "A", "end_L": 1, "evidence_Ls": [1],
         "required_concepts": ["wait request"], "allowed_paraphrase_concepts": ["please wait"],
         "source_evidence_end_sample_proposal": 10,
         "scored_translation_evidence": [{"annotation_L": 1, "source_characters": [0, 12]}],
         "unscored_context_constraints": []},
        {"id": "b", "role": "B", "end_L": 2, "evidence_Ls": [1, 2],
         "required_concepts": ["wait agreement"], "allowed_paraphrase_concepts": ["will wait"],
         "source_evidence_end_sample_proposal": 10,
         "scored_translation_evidence": [{"annotation_L": 2, "source_characters": [5, len(texts[2])]}],
         "unscored_context_constraints": []},
    ]
    with pytest.raises(ValueError, match="translation-target spans"):
        checkpoint_map({"kind": "T1", "clips": clips}, definitions, timeline(clips, "T1", relative_offset=0), texts)


def test_released_unknown_tokens_are_never_certified_english_targets():
    spans = reference_spans("maybe [UNK] 可是 no")
    assert next(s for s in spans if s["text"] == "[UNK]")["language"] == "unknown"


def test_changed_source_bytes_and_existing_output_are_not_overwritten(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"actual synthetic bytes")
    with pytest.raises(ValueError, match="checksum"):
        checked_bytes(source, sha256(b"different"))
    output = tmp_path / "prepared"
    output.mkdir()
    sentinel = output / "keep"
    sentinel.write_bytes(b"unchanged")
    with pytest.raises(ValueError, match="never overwrite"):
        materialize("missing-catalogue", "missing-cache", "missing-evidence", "missing-findings", output)
    assert sentinel.read_bytes() == b"unchanged"
