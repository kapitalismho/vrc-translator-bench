import copy
import json
from pathlib import Path
import wave

import pytest

from tools.prepare_read_controls import checked_bytes, check_groups, materialize, reference_row, save_wave, sha256


def candidate(text="Unmodified reference."):
    return {"filename": "123.wav", "sentence_id": 1980, "source_frames": 16000,
            "raw_text_utf8_sha256": sha256(text.encode("utf-8"))}


def test_reference_binding_uses_filename_and_sentence_id_not_row_order():
    selected = candidate()
    payload = b"151\tother.wav\tOther.\tother\to t h e r\t8000\t1\n1980\t123.wav\tUnmodified reference.\tunmodified reference\tu n\t16000\t0\n"
    result = reference_row(payload, selected)
    assert result["row_1based"] == 2
    assert result["text_utf8"] == b"Unmodified reference."
    assert result["raw_text"] != result["normalized_text"]
    assert result["row_sha256"] == sha256(payload.splitlines()[1])
    with pytest.raises(ValueError, match="sentence ID/sample count"):
        reference_row(payload.replace(b"1980\t123", b"1914\t123"), selected)
    with pytest.raises(ValueError, match="exactly one TSV row"):
        reference_row(payload + payload.splitlines()[1] + b"\n", selected)
    with pytest.raises(ValueError, match="raw text checksum"):
        reference_row(payload.replace(b"Unmodified", b"Modified"), selected)


def test_sentence_groups_reject_cross_language_development_overlap():
    record = json.loads((Path(__file__).parents[1] / "corpus/r2/read-controls.json").read_text(encoding="utf-8"))
    chosen = copy.deepcopy(record["fleurs"]["candidates"])
    tables = {language + "-" + split: str(identity).encode() + b"\tfile.wav\ttext\tnormal\tchars\t1\t0\n"
              for language in ("en_us", "ja_jp") for split, identity in (("train", 151), ("dev", 500), ("test", 1980))}
    result = check_groups(chosen, tables)
    assert result["main_original_text_groups"] == 3
    assert result["main_recordings"] == 6
    assert result["development_recordings"] == 2
    chosen[-1]["sentence_id"] = 1980
    with pytest.raises(ValueError, match="ancestry overlaps across languages"):
        check_groups(chosen, tables)


def test_original_upstream_sentence_overlap_is_rejected():
    record = json.loads((Path(__file__).parents[1] / "corpus/r2/read-controls.json").read_text(encoding="utf-8"))
    tables = {language + "-" + split: b"1980\tfile.wav\ttext\tnormal\tchars\t1\t0\n"
              for language in ("en_us", "ja_jp") for split in ("train", "dev", "test")}
    with pytest.raises(ValueError, match="Upstream split sentence IDs overlap"):
        check_groups(record["fleurs"]["candidates"], tables)


def test_checksum_failure_keeps_source_and_existing_output_untouched(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"unchanged bytes")
    with pytest.raises(ValueError, match="checksum mismatch"):
        checked_bytes(source, "0" * 64)
    assert source.read_bytes() == b"unchanged bytes"
    catalogue = tmp_path / "catalogue.json"
    catalogue.write_text("{}")
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "evidence.json"
    sentinel.write_bytes(b"existing evidence")
    with pytest.raises(ValueError, match="never overwrite"):
        materialize(catalogue, tmp_path, source, output)
    assert sentinel.read_bytes() == b"existing evidence"


def test_c1_wav_wrap_preserves_every_pcm_sample_and_gap(tmp_path):
    pcm = b"\x00\x00" * 50 + b"\xff\x7f\x00\x80" + b"\x00\x00" * 70
    path = tmp_path / "control.wav"
    save_wave(path, pcm)
    with wave.open(str(path), "rb") as source:
        assert (source.getnchannels(), source.getsampwidth(), source.getframerate()) == (1, 2, 48000)
        assert source.getnframes() == 122
        assert source.readframes(source.getnframes()) == pcm


def test_public_catalogue_has_no_audio_text_or_freeze_claim():
    catalogue = Path(__file__).parents[1] / "corpus/r2/read-controls.json"
    record = json.loads(catalogue.read_text(encoding="utf-8"))
    assert record["status"] == "preselected_preparation_not_production_frozen"
    assert record["public_example_preselection"]["publication_granted"] is False
    assert {c["sentence_id"] for c in record["fleurs"]["candidates"] if c["project_split"] == "main"} == {1980, 1914, 1771}
    assert record["c1"]["excluded_parent_samples"] == [5760000, 8640000]
    assert all(0 <= c["parent_samples"][0] < c["parent_samples"][1] <= 5760000 for c in record["c1"]["candidates"])
    assert record["c1"]["quality_credit"] is None and record["c1"]["meaning_wait_credit"] is None
    assert all("raw_text" not in c and "transcript" not in c for c in record["fleurs"]["candidates"])
