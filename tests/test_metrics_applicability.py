from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from bench.metrics import derive
from bench.metrics_batch import compose
from bench.metrics_stats import aggregate, paired_comparisons
from bench.quality import prepare, score_metricx
from bench.quality_report import build_report
from bench.quality_store import QualityStore
from test_metrics import dump, link, packet, sample
from test_metrics_batch import comparison, metrics


ROOT = Path(__file__).resolve().parents[1]


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def applicability(root, manifest, spec, **selector):
    evidence = dump(root / "route-evidence.json", {"events": ["Index success", "Index503", "rebuild", "Gemma401"],
                                                 "limits": "Synthetic fixture; no successful fallback or billing claim"})
    return dump(root / "applicability.json", {
        "schema_version": 1, "version": "analysis-applicability-v1", "population": "Index-primary",
        "manifest_sha256": checksum(manifest), "spec_sha256": checksum(spec),
        "exclusions": [{"run": "synthetic-test", "config": "APP", "direction": "D1", "attempt_id": 1, "stage": 0,
                        "reason": "mixed_runtime_route", "evidence": [{"path": evidence.name, "sha256": checksum(evidence)}],
                        **selector}]})


def test_batch_population_gate_is_not_only_quality_eligibility(tmp_path):
    left, right = metrics("left", "LEFT"), metrics("right", "RIGHT", (10, 18))
    excluded = left["quality_segments"][1]
    excluded.update(population_eligible=False, eligible=False,
                    applicability={"population": "Index-primary", "reason": "mixed_runtime_route"})
    result = compose([dump(tmp_path / "left.json", left), dump(tmp_path / "right.json", right)], iterations=20)
    assert len(result["pairing_population"]) == 3
    assert comparison(result)["fol_difference"]["value"] == -8
    assert comparison(result)["delivery_difference"]["observations"] == 1
    assert result["reports"][0]["report"] == left


def test_mixed_attempt_preserves_raw_collection_and_failures_but_excludes_credit(tmp_path):
    events = [packet(1, 11)]
    manifest, spec = sample(tmp_path, events)
    capture = json.loads(manifest.read_text())
    capture["attempts"][0]["reason"] = "Retained incidents: Index503 and Gemma401; cause and billing unknown"
    dump(manifest, capture)
    specification = json.loads(spec.read_text())
    specification["quality_scores"] = {"1:clip:quality-1": {"major_error": False, "provenance": ["Unobserved synthetic supplied score"]}}
    dump(spec, specification)
    cache = link(tmp_path, manifest, spec, {"clock:1": ["1:clip/s1"]})
    plain = derive(manifest, spec, cache_path=cache)
    decision = applicability(tmp_path, manifest, spec)
    before = {path: path.read_bytes() for path in (manifest, spec, tmp_path / "stream.jsonl", tmp_path / "attempt.jsonl")}
    result = derive(manifest, spec, cache_path=cache, applicability_path=decision)
    assert all(path.read_bytes() == raw for path, raw in before.items())
    assert [row["raw"] for row in result["outputs"]] == [row["raw"] for row in plain["outputs"]]
    assert [row["alignment"] for row in result["outputs"]] == [row["alignment"] for row in plain["outputs"]]
    assert result["outputs"][0]["applicability"]["exclusion_kind"] == "direct"
    assert result["outputs"][0]["population_eligible"] is False
    assert result["provenance"][:2] == plain["provenance"][:2]
    assert result["attempts"][0]["state"] == "done"
    assert result["attempts"][0]["reason"] == capture["attempts"][0]["reason"]
    assert result["sentences"][0]["delivery_status"] == "delivered"
    assert result["sentences"][0]["fol"] == plain["sentences"][0]["fol"]
    assert all(not row["eligible"] and not row["population_eligible"] for row in result["sentences"] + result["turns"])
    segment = result["quality_segments"][0]
    assert segment["reference_eligible"] and not segment["eligible"] and not segment["population_eligible"]
    assert segment["quality_eligibility_reason"] == "analysis_applicability_excluded"
    assert segment["reference"] == plain["quality_segments"][0]["reference"]
    assert segment["quality_score"] == plain["quality_segments"][0]["quality_score"]
    assert result["quality_score_coverage"]["excluded_major_error_scores"] == 1
    population = result["aggregates"][0]
    assert population["reference_sentences"] == 2 and population["eligible_sentences"] == 0
    assert population["applicability_excluded_sentences"] == 2
    assert population["applicability_excluded_turns"] == 1
    for name in ("delivery", "fol_p50", "lul_p50", "turn_lul_p50", "first_attempt_product_failure_rate"):
        assert population[name]["value"] is None
    assert population["first_attempt_product_failure_rate"]["statuses"] == {"done": 1}
    assert population["first_attempt_product_failure_rate"]["applicability_excluded_attempts"] == 1
    assert result["applicability"]["excluded_counts"] == {"attempts": 1, "sentences": 2, "turns": 1, "quality_segments": 1}
    assert result["applicability"]["sha256"] == checksum(decision)
    assert result["output_population"] == plain["output_population"]
    assert aggregate(result, {"iterations": 20})["aggregates"] == result["aggregates"]


@pytest.mark.parametrize("change,match", [
    ("manifest", "manifest.*binding"), ("spec", "spec.*binding"), ("evidence", "evidence.*checksum"),
    ("attempt_id", "exactly one"), ("stage", "exactly one"), ("config", "exactly one"),
    ("direction", "exactly one"), ("run", "exactly one"), ("duplicate", "Duplicate"),
    ("ambiguous", "exactly one"), ("missing_selector", "selector"), ("empty_evidence", "evidence"),
])
def test_applicability_rejects_stale_or_ambiguous_inputs(tmp_path, change, match):
    manifest, spec = sample(tmp_path)
    decision = applicability(tmp_path, manifest, spec)
    document = json.loads(decision.read_text())
    if change in ("manifest", "spec"):
        path = manifest if change == "manifest" else spec
        path.write_text(path.read_text() + "\n", encoding="utf-8")
    elif change == "evidence":
        (tmp_path / "route-evidence.json").write_text("changed", encoding="utf-8")
    elif change == "duplicate":
        document["exclusions"].append(copy.deepcopy(document["exclusions"][0]))
    elif change == "ambiguous":
        capture = json.loads(manifest.read_text())
        capture["attempts"].append(copy.deepcopy(capture["attempts"][0]))
        dump(manifest, capture)
        document["manifest_sha256"] = checksum(manifest)
    elif change == "missing_selector":
        del document["exclusions"][0]["stage"]
    elif change == "empty_evidence":
        document["exclusions"][0]["evidence"] = []
    else:
        document["exclusions"][0][change] = 99 if change in ("attempt_id", "stage") else "nonexistent"
    dump(decision, document)
    with pytest.raises(ValueError, match=match):
        derive(manifest, spec, applicability_path=decision)


def test_quality_admission_join_and_frozen_resume_keep_exclusion(tmp_path):
    manifest, spec = sample(tmp_path / "capture", [packet(1, 11)])
    decision = applicability(tmp_path / "capture", manifest, spec)
    result = derive(manifest, spec, applicability_path=decision)
    path = dump(tmp_path / "metrics.json", result)
    queue = tmp_path / "queue"
    plan = prepare([path], queue, skip_tone=True, skip_korean_review=True)
    assert len(plan["records"]) == 1
    assert all(job["sanity"] for job in plan["jobs"])
    assert prepare([path], queue, skip_tone=True, skip_korean_review=True) == plan
    updated = json.loads(decision.read_text())
    updated["exclusions"][0]["reason"] = "Revised bound decision"
    dump(decision, updated)
    revised = dump(tmp_path / "revised-metrics.json", derive(manifest, spec, applicability_path=decision))
    with pytest.raises(ValueError, match="different inputs"):
        prepare([revised], queue, skip_tone=True, skip_korean_review=True)

    class RecordingMetric:
        def __init__(self):
            self.inputs = []

        def cache_identity(self):
            return {"model": "synthetic-no-inference"}

        def score(self, source, output):
            self.inputs.append((source, output))
            return {"status": "completed", "score": 1, "provenance": {}, "input_tokens": None, "raw": {}}

    runtime = RecordingMetric()
    store = QualityStore(queue)
    try:
        score_metricx(plan, store, runtime)
    finally:
        store.close()
    assert len(runtime.inputs) == len(plan["jobs"])
    joined = build_report(queue)["joined_metrics_reports"][0]
    assert joined["applicability"] == result["applicability"]
    assert joined["sentences"] == result["sentences"]
    assert joined["aggregates"][0]["delivery"]["value"] is None
    assert joined["aggregates"][0]["esa_mean"]["eligible_segments"] == 0
    assert joined["quality_segments"][0]["metricx_score"] is None
    assert compose(quality_report_paths=[dump(tmp_path / "quality.json", {"joined_metrics_reports": [joined]})], iterations=20)["pairing_population"] == []


def test_actual_metrics_cli_applies_bound_decision_without_inference(tmp_path):
    assert Path(sys.modules["bench.metrics"].__file__).resolve() == ROOT / "bench/metrics.py"
    manifest, spec = sample(tmp_path, [packet(1, 11)])
    decision = applicability(tmp_path, manifest, spec)
    output = tmp_path / "derived.json"
    process = subprocess.run([sys.executable, "-B", "-m", "bench.cli", "metrics", "--manifest", str(manifest),
                              "--spec", str(spec), "--applicability", str(decision), "--output", str(output)],
                             cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert process.returncode == 0, process.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["applicability"]["excluded_counts"]["sentences"] == 2
    assert report["aggregates"][0]["delivery"]["value"] is None
    assert report["outputs"][0]["raw"] == packet(1, 11)


@pytest.mark.parametrize("exclude_repeat", [False, True])
def test_exact_native_scope_preserves_clean_resume_failure_and_repeat_populations(tmp_path, exclude_repeat):
    manifest, spec = sample(tmp_path)
    capture = json.loads(manifest.read_text())
    specification = json.loads(spec.read_text())
    # One mixed primary, an independent clean failure/resume, a repeat of the
    # mixed source, and a successful retry of that primary. No inference occurs.
    for identity, kind, work_id, stage, number, state in (
        (2, "chunk", 2, 1, 1, "product_failure"),
        (3, "repeat", 3, 2, 1, "done"),
        (4, "chunk", 1, 0, 2, "done"),
    ):
        if work_id != 1:
            capture["plan"]["stages"].append({**capture["plan"]["stages"][0], "kind": kind,
                                              "audio_sha256": "clean-audio" if kind == "chunk" else "original-audio"})
            capture["work"].append({"id": work_id, "stage": stage, "profile": "APP", "kind": kind,
                                    "state": state, "outcome": "failed" if state == "product_failure" else "done"})
            specification["references"][str(stage)] = copy.deepcopy(specification["references"]["0"])
            if kind == "chunk":
                clean_reference = json.loads((tmp_path / "reference.json").read_text())
                clean_reference["clip_id"] = "independent-clean-clip"
                clean_path = dump(tmp_path / "clean-reference.json", clean_reference)
                specification["references"][str(stage)]["path"] = str(clean_path.resolve())
        trace_path = tmp_path / f"attempt-{identity}.jsonl"
        trace = [json.loads(line) for line in (tmp_path / "attempt.jsonl").read_text().splitlines()]
        for row in trace:
            row["clock_session"] = f"clock-{identity}"
            if row.get("record") == "source_playback":
                row["attempt"] = identity
        trace_path.write_text("\n".join(json.dumps(row) for row in trace), encoding="utf-8")
        capture["attempts"].append({"id": identity, "work_id": work_id, "number": number, "state": state,
                                    "resumed": int(identity == 2), "trace": trace_path.name, "end_ns": 50_000_000_000})
    dump(manifest, capture)
    dump(spec, specification)
    decision = applicability(tmp_path, manifest, spec)
    if exclude_repeat:
        document = json.loads(decision.read_text())
        document["exclusions"].append({**document["exclusions"][0], "attempt_id": 3, "stage": 2})
        dump(decision, document)
    result = derive(manifest, spec, applicability_path=decision)
    population = result["aggregates"][0]
    assert population["reference_sentences"] == 4  # mixed first + clean; no retry promotion
    assert population["eligible_sentences"] == 2
    assert population["delivery"]["value"] == 0
    assert population["first_attempt_product_failure_rate"]["value"] == 1
    assert population["first_attempt_product_failure_rate"]["denominator"] == 1
    assert population["first_attempt_product_failure_rate"]["statuses"] == {"done": 1, "product_failure": 1}
    assert population["sentences_applicability_reasons"] == {"mixed_runtime_route": 2}
    sensitivity = result["resume_sensitivity"][0]
    assert sensitivity["with_resumed"]["eligible_sentences"] == 2
    assert sensitivity["without_resumed"]["eligible_sentences"] == 0
    assert sensitivity["without_resumed"]["delivery"]["value"] is None
    assert result["repeats"][0]["eligible_sentences"] == (0 if exclude_repeat else 2)
    assert result["repeat_variation"][0]["baseline_shared_subset"]["eligible_sentences"] == 0
    assert all(row["eligible"] for row in result["sentences"] if row["attempt_id"] in (2, 4))
    assert result["attempts"][1]["state"] == "product_failure"
    # Rejoining reuses exactly the same retained primary selector and gates.
    queue = tmp_path / "queue"
    prepare([dump(tmp_path / "report.json", result)], queue, skip_tone=True, skip_korean_review=True)
    joined = build_report(queue)["joined_metrics_reports"][0]
    assert joined["aggregates"][0]["delivery"] == population["delivery"]
    assert joined["aggregates"][0]["first_attempt_product_failure_rate"] == population["first_attempt_product_failure_rate"]
    assert joined["aggregates"][0]["esa_mean"]["eligible_segments"] == 1
    assert joined["resume_sensitivity"] == result["resume_sensitivity"]
    assert joined["repeats"] == result["repeats"]


def test_output_cannot_overwrite_bound_native_or_analysis_inputs(tmp_path):
    manifest, spec = sample(tmp_path)
    decision = applicability(tmp_path, manifest, spec)
    for path in (manifest, spec, decision, tmp_path / "route-evidence.json", tmp_path / "attempt.jsonl"):
        before = path.read_bytes()
        with pytest.raises(ValueError, match="must not overwrite"):
            derive(manifest, spec, output_path=path, applicability_path=decision)
        assert path.read_bytes() == before


def test_in_report_pairs_keep_only_the_applicable_shared_subset():
    left, right = metrics("left", "LEFT"), metrics("right", "RIGHT", (10, 18))
    left["quality_segments"][1].update(population_eligible=False, eligible=False)
    # Native attempts are globally unique within a report; the helper creates
    # independent reports, so make that identity boundary explicit here.
    for report in (left, right):
        for collection in ("sentences", "quality_segments"):
            for row in report[collection]:
                row["attempt_id"] = (report["run"], row["attempt_id"])
    paired = paired_comparisons(left["sentences"] + right["sentences"],
                                left["quality_segments"] + right["quality_segments"], 20, 7)
    assert len(paired[0]["shared_segments"]) == 1
    assert paired[0]["comparisons"]["all_shared"]["fol_difference"]["value"] == -8
    assert paired[0]["comparisons"]["all_shared"]["major_error_difference"]["observations"] == 1


def test_missing_evidence_and_reference_free_selectors_are_rejected(tmp_path):
    manifest, spec = sample(tmp_path)
    decision = applicability(tmp_path, manifest, spec)
    document = json.loads(decision.read_text())
    document["exclusions"][0]["evidence"][0]["path"] = "absent-evidence.json"
    dump(decision, document)
    with pytest.raises(FileNotFoundError):
        derive(manifest, spec, applicability_path=decision)
    isolated_manifest, isolated_spec = sample(tmp_path / "isolated", kind="isolated")
    isolated_decision = applicability(tmp_path / "isolated", isolated_manifest, isolated_spec)
    with pytest.raises(ValueError, match="reference-bearing chunk or repeat"):
        derive(isolated_manifest, isolated_spec, applicability_path=isolated_decision)
