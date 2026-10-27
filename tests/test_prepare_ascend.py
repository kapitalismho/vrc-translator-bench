import copy
import io
import json
from pathlib import Path
import wave

import pytest

from tools.prepare_ascend import (
    check_reservations, checked_bytes, decode_wave, materialize, reference_row, sha256,
)


@pytest.fixture
def catalogue():
    return json.loads((Path(__file__).resolve().parents[1] / "corpus/r2/ascend.json").read_text(encoding="utf-8"))


def test_fixed_p1_reservations_are_disjoint_without_certifying_unknowns(catalogue):
    result = check_reservations(catalogue)
    assert result["main_reserved_original_speakers"] == [1, 2, 7, 8, 13, 14, 21, 24]
    assert result["development_reserved_original_speakers"] == [17, 18]
    assert result["known_intersection"] == []
    assert result["unknown_participation_certified_absent"] is False
    assert catalogue["split_reservations"]["filename_original_aliases"] == {"22": 1, "23": 2, "25": 9}
    assert catalogue["cell_accounting"]["T1"]["accepted_parent_ids"] == []
    assert catalogue["cell_accounting"]["T1"]["unmet_development"] == 4


@pytest.mark.parametrize("mutation", ["overlap", "omit_partner", "wrong_split", "duplicate_interval"])
def test_changed_identity_or_connected_group_is_rejected(catalogue, mutation):
    record = copy.deepcopy(catalogue)
    if mutation == "overlap":
        record["split_reservations"]["development_reserved_original_groups"][0].append(13)
    elif mutation == "omit_partner":
        record["candidates"][1]["reserved_original_speakers"] = [21]
    elif mutation == "wrong_split":
        record["candidates"][0]["upstream_split"] = "test"
    else:
        record["candidates"][1]["archive_member"] = record["candidates"][0]["archive_member"]
    with pytest.raises(ValueError):
        check_reservations(record)


def test_references_come_from_exact_split_local_row_and_pinned_text():
    text = "synthetic reference only"
    row = {"file_name": "waves/synthetic.wav", "original_speaker_id": "17", "transcription": text}
    candidate = {"upstream_split": "test", "upstream_id": "00000", "archive_member": row["file_name"],
                 "original_speaker_id": 17, "reference_utf8_sha256": sha256(text.encode())}
    assert reference_row({"test": [row]}, candidate) == (row, text.encode())
    with pytest.raises(ValueError, match="checksum"):
        reference_row({"test": [{**row, "transcription": "changed synthetic text"}]}, candidate)
    with pytest.raises(ValueError, match="identity"):
        reference_row({"test": [{**row, "file_name": "waves/different.wav"}]}, candidate)
    with pytest.raises(ValueError, match="five-digit"):
        reference_row({"test": [row]}, {**candidate, "upstream_id": "0"})


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
