from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from bench.metrics import derive
from test_metrics import dump, packet, sample


ROOT = Path(__file__).resolve().parents[1]


def quiet_fixture(root, status="timeout", evidence="stream"):
    wait = packet(1, 9, "delayed earlier speech", capture_phase="quiet_precondition",
                  output_classification="unresolved_carryover",
                  source_candidate_provenance=[{"attempt": 99, "chunk": "earlier"}])
    events = [wait, packet(2, 10.1, "at nonspeech start", capture_phase="nonspeech"),
              packet(3, 130.1, "at background start", capture_phase="nonspeech"),
              packet(4, 190.1, "outside interval", capture_phase="nonspeech")]
    manifest, spec = sample(root, events, kind="nonspeech")
    data = json.loads(manifest.read_text())
    data["plan"]["stages"][0].update(duration_seconds=180, quiet_seconds=15, quiet_max_wait_seconds=120)
    gate = {"record": "nonspeech_quiet_wait", "phase": "end", "status": status,
            "stage": 0, "wave": "W1", "direction": "D1", "chunk": "clip", "clock_session": "clock",
            "attempts": {"APP": 1}, "start_ns": 0, "end_ns": 10_000_000_000, "t_ns": 10_000_000_000,
            "quiet_seconds": 15, "quiet_max_wait_seconds": 120, "waited_seconds": 10,
            "timed_out": status == "timeout",
            "quiet_precondition_met": status == "achieved", "unresolved_carryover": status != "achieved",
            "profiles": {"APP": {"last_output_ns": 9_000_000_000, "achieved_quiet_seconds": 1,
                                   "quiet_precondition_met": status == "achieved", "active": True}}}
    if evidence == "stream":
        stream = root / "stream.jsonl"
        with stream.open("a", encoding="utf-8") as target:
            target.write("\n" + json.dumps(gate))
        data["streams"][0].pop("sha256")
    elif evidence == "ledger":
        data["records"] = [{"kind": "nonspeech_quiet_wait", "detail": json.dumps(gate)}]
    elif evidence == "playback":
        trace = root / "attempt.jsonl"
        rows = [json.loads(line) for line in trace.read_text().splitlines()]
        rows[1].update(quiet_precondition_met=False, unresolved_carryover=True)
        trace.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    dump(manifest, data)
    specification = json.loads(spec.read_text())
    specification.pop("references")
    dump(spec, specification)
    return manifest, spec, gate, wait


@pytest.mark.parametrize("evidence", ["stream", "ledger", "playback"])
def test_timeout_preserves_raw_playback_counts_but_not_clean_attribution(tmp_path, evidence):
    manifest, spec, gate, wait = quiet_fixture(tmp_path, evidence=evidence)
    report = derive(manifest, spec)
    assert [row["id"] for row in report["outputs"]] == ["clock:2", "clock:3", "clock:4"]
    assert report["output_population"]["unaligned_output_rate"]["denominator"] == 3
    assert report["quiet_precondition_observations"][0]["raw"] == wait
    intervals = report["diagnostics"]["nonspeech"]
    assert [row["count"]["value"] for row in intervals] == [1, 1]
    assert [row["output_ids"] for row in intervals] == [["clock:2"], ["clock:3"]]
    assert all(row["clean_nonspeech_count"]["value"] is None for row in intervals)
    assert all("carryover" in row["clean_nonspeech_count"]["reason"] for row in intervals)
    assert all(row["quiet_precondition_met"] is False and row["unresolved_carryover"] is True for row in intervals)
    if evidence != "playback":
        assert intervals[0]["nonspeech_quiet_wait"] == gate
    assert all(not row["eligible"] for row in report["quality_segments"])
    assert all("clock:1" not in row["output_ids"] for row in report["quality_segments"])


def test_achieved_gate_keeps_wait_separate_and_reports_observed_clean_counts(tmp_path):
    manifest, spec, gate, _ = quiet_fixture(tmp_path, status="achieved")
    report = derive(manifest, spec)
    assert [row["clean_nonspeech_count"]["value"] for row in report["diagnostics"]["nonspeech"]] == [1, 1]
    assert report["attempts"][0]["nonspeech_quiet_wait"] == gate
    assert "clock:1" not in report["alignment_cache"]["links"]


def test_historical_no_gate_keeps_observed_semantics_without_inventing_quiet(tmp_path):
    manifest, spec = sample(tmp_path, [packet(1, 11)], kind="nonspeech")
    report = derive(manifest, spec)
    interval = report["diagnostics"]["nonspeech"][0]
    assert interval["count"]["value"] == 1
    assert interval["quiet_precondition_met"] is None
    assert interval["unresolved_carryover"] is None
    assert interval["nonspeech_quiet_wait"] is None
    assert interval["clean_nonspeech_count"]["value"] is None
    assert report["quiet_precondition_observations"] == []
    assert report["output_population"]["unaligned_output_rate"]["denominator"] == 1


def test_actual_cli_quiet_timeout_report(tmp_path):
    manifest, spec, gate, wait = quiet_fixture(tmp_path)
    output = tmp_path / "report.json"
    result = subprocess.run([sys.executable, "-m", "bench.cli", "metrics", "--manifest", str(manifest),
                             "--spec", str(spec), "--output", str(output)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["quiet_precondition_observations"][0]["raw"] == wait
    assert report["output_population"]["unaligned_output_rate"]["denominator"] == 3
    assert [row["count"]["value"] for row in report["diagnostics"]["nonspeech"]] == [1, 1]
    assert all(row["clean_nonspeech_count"]["value"] is None for row in report["diagnostics"]["nonspeech"])
    assert report["attempts"][0]["nonspeech_quiet_wait"] == gate


def test_wait_output_with_prior_speech_capture_identity_never_enters_measured_population(tmp_path):
    wait = packet(1, 13, "delayed speech", capture_phase="quiet_precondition",
                  output_classification="unresolved_carryover")
    manifest, spec = sample(tmp_path, [wait])
    report = derive(manifest, spec)
    assert report["outputs"] == []
    assert report["output_population"]["unaligned_output_rate"]["denominator"] == 0
    assert all(row["unaligned_output_ids"] == [] for row in report["quality_segments"])
    assert all(row["delivery_status"] == "no_output_before_deadline" for row in report["sentences"])
    assert report["quiet_precondition_observations"][0]["raw"] == wait
