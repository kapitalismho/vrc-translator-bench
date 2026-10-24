from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from bench.metrics import derive
from bench.metrics_batch import compose
from bench.quality import prepare
from bench.quality_report import build_report
from test_metrics import dump, link, packet, sample
from test_metrics_applicability import applicability


ROOT = Path(__file__).resolve().parents[1]


def trace(root, identity, origin, clock="clock", config="APP"):
    rows = [json.loads(line) for line in (root / "attempt.jsonl").read_text().splitlines()]
    for row in rows:
        row["clock_session"] = clock
        if row["record"] == "source_playback":
            row.update(attempt=identity, config=config, playback_dac_start_ns=origin)
    path = root / f"attempt-{identity}.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return path.name


def cross_attempt_capture(root, *, alignment="aligned", trusted=False):
    events = [packet(1, 15, "mixed capture output", attempt=2),
              packet(3, 42, "clean origin carryover", attempt=1)]
    if trusted:
        events.append(packet(2, 12, "trusted earlier output", attempt=1))
    manifest, spec = sample(root, events)
    capture, specification = json.loads(manifest.read_text()), json.loads(spec.read_text())
    reference = json.loads((root / "reference.json").read_text())
    for identity, origin in ((2, 20_000_000_000), (3, 40_000_000_000)):
        native = {**reference, "clip_id": f"clip-{identity}"}
        native_path = dump(root / f"reference-{identity}.json", native)
        capture["plan"]["stages"].append({**capture["plan"]["stages"][0], "audio_sha256": f"audio-{identity}"})
        capture["work"].append({"id": identity, "stage": identity - 1, "profile": "APP", "kind": "chunk", "state": "done", "outcome": "done"})
        capture["attempts"].append({"id": identity, "work_id": identity, "number": 1, "state": "done", "resumed": 0,
                                    "trace": trace(root, identity, origin), "end_ns": 70_000_000_000})
        specification["references"][str(identity - 1)] = {**specification["references"]["0"], "path": str(native_path.resolve())}
    capture["attempts"][0]["end_ns"] = 70_000_000_000
    dump(manifest, capture)
    dump(spec, specification)
    entries = {"clock:3": ["3:clip-3/s1"]}
    if alignment in ("aligned", "unrelated"):
        entries["clock:1"] = ["1:clip/s1"] if alignment == "aligned" else []
    if trusted:
        entries["clock:2"] = ["1:clip/s1"]
    cache = link(root, manifest, spec, entries)
    decision = applicability(root, manifest, spec, attempt_id=2, stage=1)
    return manifest, spec, cache, decision


def category(report):
    return next(row for row in report["aggregates"] if row["view"] == "category")


@pytest.mark.parametrize("alignment,trusted", [("aligned", False), ("aligned", True), ("unknown", False), ("unrelated", False)])
def test_direct_mixed_origin_excludes_dependencies_not_clean_origins(tmp_path, alignment, trusted):
    manifest, spec, cache, decision = cross_attempt_capture(tmp_path, alignment=alignment, trusted=trusted)
    plain = derive(manifest, spec, cache_path=cache)
    report = derive(manifest, spec, cache_path=cache, applicability_path=decision)
    original = {row["id"]: row for row in plain["outputs"]}
    outputs = {row["id"]: row for row in report["outputs"]}
    for identity, output in outputs.items():
        assert output["raw"] == original[identity]["raw"]
        assert output["alignment"] == original[identity]["alignment"]
        assert output["text"] == original[identity]["text"]
    assert outputs["clock:1"]["population_eligible"] is False
    assert outputs["clock:1"]["applicability"]["exclusion_kind"] == "direct"
    assert outputs["clock:1"]["applicability"]["attempt_id"] == 2
    assert outputs["clock:3"].get("population_eligible", True) is True
    if trusted:
        assert outputs["clock:2"].get("population_eligible", True) is True
    dependent = next(row for row in report["sentences"] if row["id"] == "1:clip/s1")
    assert dependent["eligible"] is False
    assert dependent["applicability"]["exclusion_kind"] == "dependent"
    assert dependent["applicability"]["dependent_output_ids"] == ["clock:1"]
    assert dependent["applicability"]["origin_exclusions"][0]["evidence"] == outputs["clock:1"]["applicability"]["evidence"]
    assert dependent["delivery_status"] == plain["sentences"][0]["delivery_status"]
    assert dependent["fol"] == plain["sentences"][0]["fol"]  # no missing-output rewrite or favorable re-timing
    if alignment == "aligned":
        assert dependent["delivery_status"] == "delivered"
    else:
        assert outputs["clock:1"]["quality_segment_id"] == report["quality_segments"][0]["id"]
    assert report["turns"][0]["eligible"] is False
    assert report["quality_segments"][0]["eligible"] is False
    assert report["attempts"][0]["applicability"]["exclusion_kind"] == "dependent"
    assert report["attempts"][0]["state"] == "done"
    assert report["attempts"][1]["applicability"]["exclusion_kind"] == "direct"
    clean = next(row for row in report["sentences"] if row["id"] == "3:clip-3/s1")
    assert clean["eligible"] and clean["delivery_status"] == "delivered"
    result = category(report)
    assert result["delivery"]["value"] == (1 / 3 if alignment == "aligned" else 1 / 2)
    assert result["fol_p50"]["value"] == pytest.approx(1.9)
    assert result["lul_p50"]["value"] == pytest.approx(-0.1)
    assert result["turn_lul_p50"]["value"] == pytest.approx(-2.1)
    assert result["unaligned_output_rate"]["denominator"] == 1
    assert result["first_attempt_product_failure_rate"]["denominator"] == 1
    assert report["applicability"]["direct_excluded_counts"]["attempts"] == 1
    assert report["applicability"]["dependent_excluded_counts"]["attempts"] == 1
    assert report["applicability"]["excluded_output_ids"] == ["clock:1"]
    assert report["output_population"] == plain["output_population"]
    queue = tmp_path / "queue"
    plan = prepare([dump(tmp_path / "report.json", report)], queue, skip_tone=True, skip_korean_review=True)
    real_jobs = [job for job in plan["jobs"] if not job["sanity"]]
    clean_record = next(row for row in plan["records"] if row["segment"]["attempt_id"] == 3)
    assert [job["record_key"] for job in real_jobs] == [clean_record["key"]]
    joined = build_report(queue)["joined_metrics_reports"][0]
    assert category(joined)["delivery"] == result["delivery"]
    assert category(joined)["unaligned_output_rate"] == result["unaligned_output_rate"]
    assert category(joined)["esa_mean"]["eligible_segments"] == 1
    batch = compose(quality_report_paths=[dump(tmp_path / "joined.json", {"joined_metrics_reports": [joined]})], iterations=20)
    assert [row["attempt_id"] for row in batch["pairing_population"]] == [3]
    assert {row["attempt_id"] for row in batch["pairing_exclusions"]} == {1, 2}


def retry_capture(root, *, first_state="done", retry=True):
    events = [packet(3, 12, "counterpart A", config="OTHER", attempt=3, clock_session="clock-3"),
              packet(4, 12, "clean B", attempt=4, clock_session="clock-4"),
              packet(5, 12, "counterpart B", config="OTHER", attempt=5, clock_session="clock-5")]
    if retry:
        events.append(packet(2, 12, "successful retry A", attempt=2, clock_session="clock-2"))
    manifest, spec = sample(root, events)
    capture, specification = json.loads(manifest.read_text()), json.loads(spec.read_text())
    capture["attempts"][0].update(state=first_state, outcome="failed" if first_state == "product_failure" else first_state)
    specification["rules"]["OTHER"] = copy.deepcopy(specification["rules"]["APP"])
    independent = json.loads((root / "reference.json").read_text())
    independent["clip_id"] = "independent"
    native = dump(root / "independent-reference.json", independent)
    capture["plan"]["stages"].append({**capture["plan"]["stages"][0], "audio_sha256": "independent-audio"})
    specification["references"]["1"] = {**specification["references"]["0"], "path": str(native.resolve())}
    for identity, work_id, stage, config, number in ((2, 1, 0, "APP", 2), (3, 2, 0, "OTHER", 1),
                                                     (4, 3, 1, "APP", 1), (5, 4, 1, "OTHER", 1)):
        if identity == 2 and not retry:
            continue
        if work_id != 1:
            capture["work"].append({"id": work_id, "stage": stage, "profile": config, "kind": "chunk", "state": "done", "outcome": "done"})
        capture["attempts"].append({"id": identity, "work_id": work_id, "number": number, "state": "done", "outcome": "done", "resumed": 0,
                                    "trace": trace(root, identity, 10_000_000_000, f"clock-{identity}", config), "end_ns": 50_000_000_000})
    dump(manifest, capture)
    dump(spec, specification)
    entries = {f"clock-{identity}:{identity}": [f"{identity}:{'clip' if identity < 4 else 'independent'}/s1"]
               for identity in (2, 3, 4, 5) if identity != 2 or retry}
    cache = link(root, manifest, spec, entries)
    return manifest, spec, cache, applicability(root, manifest, spec)


@pytest.mark.parametrize("first_state", ["done", "product_failure", "invalid"])
@pytest.mark.parametrize("retry", [False, True])
def test_pairing_uses_retained_terminal_before_exclusion_and_checks_duplicates(tmp_path, first_state, retry):
    manifest, spec, cache, decision = retry_capture(tmp_path, first_state=first_state, retry=retry)
    plain = derive(manifest, spec, cache_path=cache)
    report = derive(manifest, spec, cache_path=cache, applicability_path=decision)
    clean_shared = next(row["shared_id"] for row in report["quality_segments"] if row["attempt_id"] == 4)
    shared = report["paired"][0]["shared_segments"]
    assert clean_shared in shared
    assert len(shared) == (2 if first_state == "invalid" and retry else 1)
    assert report["paired"][0]["comparisons"]["all_shared"]["delivery_difference"]["observations"] == len(shared)
    if first_state != "invalid":
        # The first completed/product-failed source has no output. Its later
        # successful retry must not replace this negative observation, even
        # without an applicability file.
        assert plain["paired"][0]["comparisons"]["all_shared"]["delivery_difference"]["value"] == -0.25
    queue = tmp_path / "queue"
    prepare([dump(tmp_path / "report.json", report)], queue, skip_tone=True, skip_korean_review=True)
    joined = build_report(queue)["joined_metrics_reports"][0]
    assert joined["paired"] == report["paired"]
    for label, document, joined_input in (("raw", report, False), ("joined", joined, True)):
        path = dump(tmp_path / f"{label}.json", {"joined_metrics_reports": [document]} if joined_input else document)
        arguments = {"quality_report_paths": [path]} if joined_input else {"report_paths": [path]}
        if retry and first_state != "invalid":
            with pytest.raises(ValueError, match="Duplicate reference-eligible chunk/shared population"):
                compose(iterations=20, **arguments)
        else:
            batch = compose(iterations=20, **arguments)
            assert batch["paired"][0]["shared_segments"] == shared
            assert 1 not in [row["attempt_id"] for row in batch["pairing_population"] if row["config"] == "APP"]
            assert (2 in [row["attempt_id"] for row in batch["pairing_population"] if row["config"] == "APP"]) == (retry and first_state == "invalid")


def test_duplicate_excluded_population_across_reports_still_rejects(tmp_path):
    manifest, spec, cache, decision = retry_capture(tmp_path / "capture", retry=False)
    first = derive(manifest, spec, cache_path=cache, applicability_path=decision)
    other = copy.deepcopy(first)
    other["run"] = "distinct-retained-run"
    for sentence in other["sentences"]:
        sentence["run"] = other["run"]
    with pytest.raises(ValueError, match="Duplicate reference-eligible chunk/shared population"):
        compose([dump(tmp_path / "first.json", first), dump(tmp_path / "other.json", other)], iterations=20)


def test_actual_cli_keeps_cross_attempt_uncertainty_and_rejects_retry_batch(tmp_path):
    assert Path(sys.modules["bench.metrics"].__file__).resolve() == ROOT / "bench/metrics.py"
    manifest, spec, cache, decision = cross_attempt_capture(tmp_path / "cross", trusted=True)
    output = tmp_path / "cross-report.json"
    process = subprocess.run([sys.executable, "-B", "-m", "bench.cli", "metrics", "--manifest", str(manifest), "--spec", str(spec),
                              "--alignment-cache", str(cache), "--applicability", str(decision), "--output", str(output)],
                             cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert process.returncode == 0, process.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["outputs"][0]["population_eligible"] is False
    assert report["sentences"][0]["applicability"]["exclusion_kind"] == "dependent"
    assert category(report)["unaligned_output_rate"]["denominator"] == 1
    manifest, spec, cache, decision = retry_capture(tmp_path / "retry")
    retry_report = dump(tmp_path / "retry-report.json", derive(manifest, spec, cache_path=cache, applicability_path=decision))
    destination = tmp_path / "must-not-exist.json"
    rejected = subprocess.run([sys.executable, "-B", "-m", "bench.cli", "metrics-batch", "--report", str(retry_report), "--output", str(destination)],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert rejected.returncode == 2
    assert "Duplicate reference-eligible chunk/shared population" in rejected.stderr
    assert not destination.exists()


def test_in_report_duplicate_primary_is_checked_before_analysis_gate(tmp_path):
    from bench.metrics_stats import paired_comparisons

    manifest, spec, cache, decision = retry_capture(tmp_path, retry=False)
    report = derive(manifest, spec, cache_path=cache, applicability_path=decision)
    duplicate = copy.deepcopy(report["quality_segments"][0])
    duplicate["id"] = "duplicate-excluded-primary"
    with pytest.raises(ValueError, match="Duplicate reference-eligible retained-primary"):
        paired_comparisons(report["sentences"], report["quality_segments"] + [duplicate], 20, 7)


def test_existing_isolated_window_cannot_credit_a_directly_mixed_origin(tmp_path):
    manifest, spec, cache, _ = cross_attempt_capture(tmp_path, alignment="unrelated")
    capture = json.loads(manifest.read_text())
    capture["work"][0]["kind"] = "isolated"
    capture["plan"]["stages"][0]["kind"] = "isolated"
    dump(manifest, capture)
    decision = applicability(tmp_path, manifest, spec, attempt_id=2, stage=1)
    plain = derive(manifest, spec, cache_path=cache)
    report = derive(manifest, spec, cache_path=cache, applicability_path=decision)
    result = report["isolated"][0]
    assert result["status"] == plain["isolated"][0]["status"] == "response"
    assert result["first_from_start"] == plain["isolated"][0]["first_from_start"]
    assert result["output_ids"] == plain["isolated"][0]["output_ids"] == ["clock:1"]
    assert not result["measurement_eligible"] and not result["quality"]["eligible"]
    assert result["applicability"]["exclusion_kind"] == "dependent"
    assert report["attempts"][0]["applicability"]["dependent_output_ids"] == ["clock:1"]
    assert report["quality_segments"][0]["eligible"] is False
    assert report["outputs"][1].get("population_eligible", True) is True
