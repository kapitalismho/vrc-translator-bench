import hashlib
import json

import pytest

from tools.export_pilot_evidence import export, redact_paths


def test_redaction_retains_numeric_timing_and_field_provenance():
    changes = []
    original = {"audio": "C:/private/repo/audio.wav", "t_ns": 987654321, "args": ["Okay.\nわかりました。", True, False]}
    result = redact_paths(original, [("C:/private/repo", "[LOCAL_REPOSITORY]")], changes)
    assert result == {**original, "audio": "[LOCAL_REPOSITORY]/audio.wav"}
    assert changes == ["/audio"]
    assert original["audio"] == "C:/private/repo/audio.wav"


def test_export_preserves_raw_stream_bytes_and_original_hashes(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    raw = b'{"record":"audio_callback","dac_t_ns":123456789,"source_frame":0}\n'
    (run / "stream-session.jsonl").write_bytes(raw)
    original_manifest = {"streams": [{"path": "stream-session.jsonl", "sha256": hashlib.sha256(raw).hexdigest()}],
                         "attempts": [], "plan": {"audio": str(tmp_path / "private.wav")}}
    manifest_bytes = json.dumps(original_manifest).encode()
    (run / "manifest.json").write_bytes(manifest_bytes)
    output = tmp_path / "public"
    provenance = export(run, output, tmp_path)
    assert (run / "manifest.json").read_bytes() == manifest_bytes
    assert (output / "stream-session.jsonl").read_bytes() == raw
    stream = next(item for item in provenance["files"] if item["name"] == "stream-session.jsonl")
    assert stream["byte_identical"] is True
    assert stream["original_sha256"] == stream["export_sha256"] == hashlib.sha256(raw).hexdigest()
    derived = json.loads((output / "manifest.json").read_text())
    assert derived["plan"]["audio"].startswith("[LOCAL_REPOSITORY]")
    assert "not authoritative" in derived["derived_export_notice"]
    with pytest.raises(ValueError, match="never overwrite"):
        export(run, output, tmp_path)


def test_export_redacts_serialized_json_without_changing_literal_text(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "synthetic-user"))
    run = tmp_path / "run"
    run.mkdir()
    package = str(tmp_path / "package")
    detail = json.dumps({"implementation": {"package_path": package}, "t_ns": 987654321,
                         "nested": json.dumps({"path": package}), "text": "Okay.\nわかりました。"})
    literal = 'Not JSON: {"unfinished": ' + package
    unchanged = '  { "text": "literal \\\\ escape", "number": 42 }  '
    manifest = {"streams": [], "attempts": [],
                "records": [{"detail": detail}, {"detail": literal}, {"detail": unchanged}],
                "plain_path": package}
    original = json.dumps(manifest).encode()
    (run / "manifest.json").write_bytes(original)
    output = tmp_path / "public"
    provenance = export(run, output, tmp_path)
    derived = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    parsed_detail = json.loads(derived["records"][0]["detail"])
    expected_path = package.replace(str(tmp_path), "[LOCAL_REPOSITORY]")
    assert parsed_detail == {"implementation": {"package_path": expected_path}, "t_ns": 987654321,
                             "nested": json.dumps({"path": expected_path}, separators=(",", ":")),
                             "text": "Okay.\nわかりました。"}
    assert derived["records"][1]["detail"] == literal.replace(str(tmp_path), "[LOCAL_REPOSITORY]")
    assert derived["records"][2]["detail"] == unchanged
    assert derived["plain_path"] == expected_path
    assert (run / "manifest.json").read_bytes() == original
    assert provenance["files"][0]["original_sha256"] == hashlib.sha256(original).hexdigest()
    assert provenance["files"][0]["export_sha256"] == hashlib.sha256((output / "manifest.json").read_bytes()).hexdigest()
    assert provenance["files"][0]["redacted_json_pointers"] == [
        "/records/0/detail", "/records/1/detail", "/plain_path"]


def test_redaction_handles_escaped_windows_paths_in_serialized_json():
    private = r"C:\private\repo"
    original = json.dumps({"implementation": {"package_path": private + r"\bench"}})
    changes = []
    result = redact_paths(original, [(private, "[LOCAL_REPOSITORY]")], changes, "/detail")
    assert json.loads(result) == {"implementation": {"package_path": r"[LOCAL_REPOSITORY]\bench"}}
    assert changes == ["/detail"]
