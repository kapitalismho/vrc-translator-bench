"""Consolidated R5 checkpoint binding, recovery and frozen-input regressions.

All usage/bills are isolated synthetic inputs. Runtime integration replaces app,
collector and audio boundaries; it exercises the real Runner/Ledger/R4 consumers.
"""
from __future__ import annotations

import copy
import json
from datetime import timedelta

import pytest

from bench.cost_inputs import fingerprint, timestamp
from bench.costs import derive
from bench.storage import digest
from test_capture import make_plan, runtime
from test_costs import FIXTURES, row
from test_episode_costs import dump, example


def standalone_example(tmp_path):
    common = json.loads((FIXTURES / "synthetic-common.json").read_text(encoding="utf-8"))
    population = common["populations"][0]
    population["profile"] = "VRCS2"
    selection = population["role_results"][0]["selection"]
    selection["scope"]["profile"] = "VRCS2"
    timeline = dump(tmp_path / "timeline.json", {"episode_id": "synthetic-episode", "timeline_seconds": 20})
    bill = row(cost=".005", start="2026-10-20T12:00:01Z")
    bills = dump(tmp_path / "bills.json", [bill])
    spec = {"schema_version": 2, "synthetic": True, "revision": {"id": "initial"},
            "common_report": dump(tmp_path / "common.json", common),
            "timelines": [{"episode_id": "synthetic-episode", "artifact": timeline}],
            "windows": [{"id": "observed", "run": "synthetic-pilot", "wave": "synthetic-wave", "profile": "VRCS2",
                         "episode_id": "synthetic-episode", "pass_id": "ordinary-peer", "attempt_id": "1",
                         "kind": "P1", "roles": ["A"], "purpose": "main", "state": "done", "input_complete": True,
                         "start": "2026-10-20T12:00:00Z", "end": "2026-10-20T12:00:50Z", "replayed_seconds": 20,
                         "evidence": "Invented observed window, not app activity", "role_bindings": {"A": fingerprint(selection)}}],
            "components": [{"id": "route", "profile": "VRCS2", "provider": "openrouter", "treatment": "provider",
                            "models": ["synthetic/gemma"], "key_aliases": ["shared"], "services": ["asr", "translation"],
                            "services_evidence": "Invented all-in-one arithmetic route",
                            "coverage": {"window_ids": ["observed"], "complete": True, "evidence": "Synthetic complete bill"}}],
            "sources": [{"id": "bills", "path": bills["path"], "provider": "openrouter", "kind": "provider_export",
                         "format": "json", "permitted": True, "synthetic": True, "benchmark_only": True,
                         "selection_evidence": "Isolated invented billing record", "currency": "USD",
                         "fields": {key: key for key in bill},
                         "isolation": {"verified": True, "evidence": "Synthetic isolated input, not account proof"}}]}
    path = tmp_path / "spec.json"
    dump(path, spec)
    return path, spec, common


def bind_manifest(tmp_path, path, spec, common, manifest):
    binding = dump(tmp_path / "manifest.json", manifest)
    spec["manifests"][0].update(binding)
    for result in common["populations"][0]["role_results"]:
        result["selection"]["run_manifest"] = binding
    spec["common_report"] = dump(tmp_path / "common.json", common)
    dump(path, spec)


def save_trace(tmp_path, manifest, records, index=0):
    attempt = manifest["attempts"][index]
    trace = tmp_path / attempt["trace"]
    trace.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    attempt["checksum"] = digest(trace)


def resumed_example(tmp_path):
    path, spec, common, manifest = example(tmp_path)
    first = manifest["attempts"][0]
    records = [json.loads(line) for line in (tmp_path / first["trace"]).read_text().splitlines()]
    records[0].update(attempt=0, wall="2026-10-20T11:58:00Z")
    records[1]["attempt"] = 0
    records[-1]["source_frames"] = 10000
    records.append({**records[-1], "source_frame": 20000, "dac_t_ns": 21_000_000_000})
    prior = {**copy.deepcopy(first), "id": 0, "state": "invalid", "reason": "interrupted",
             "start_wall": "2026-10-20T11:58:00Z", "end_wall": "2026-10-20T11:59:15Z", "trace": "interrupted.jsonl"}
    first.update(number=2, resumed=True)
    manifest["attempts"].insert(0, prior)
    save_trace(tmp_path, manifest, records)
    bills = json.loads((tmp_path / "bills.json").read_text())
    bills.append(row(start="2026-10-20T11:58:01Z", cost=".007", request_id="invented-invalid", window_id="capture.attempt-0"))
    dump(tmp_path / "bills.json", bills)
    spec["components"][0]["coverage"]["window_ids"].append("capture.attempt-0")
    bind_manifest(tmp_path, path, spec, common, manifest)
    return path, spec, common, manifest


@pytest.mark.parametrize("change", [{"run": "different-capture"}, {"attempt_id": "999"},
                                    {"run": "different-capture", "attempt_id": "999"}])
def test_r5_f1_copied_fingerprint_cannot_override_frozen_scope(tmp_path, change):
    path, spec, _ = standalone_example(tmp_path)
    spec["windows"][0].update(change)
    dump(path, spec)
    with pytest.raises(ValueError, match="contradicts common report selection scope"):
        derive(path, tmp_path / "cost.json")
    assert not (tmp_path / "cost.json").exists()


@pytest.mark.parametrize("missing", ["run", "profile", "episode", "pass_id", "attempt"])
def test_r5_f1_missing_essential_scope_is_pending_even_with_exact_fingerprint(tmp_path, missing):
    path, spec, common = standalone_example(tmp_path)
    selection = common["populations"][0]["role_results"][0]["selection"]
    del selection["scope"][missing]
    spec["common_report"] = dump(tmp_path / "common.json", common)
    spec["windows"][0]["role_bindings"]["A"] = fingerprint(selection)
    dump(path, spec)
    result = derive(path, tmp_path / "cost.json")
    population = result["populations"][0]
    assert population["status"] == "pending"
    assert population["cost"] is population["per_input_hour"] is None
    assert population["full_main_input_observed"] is False
    assert result["components"][0]["cost"] == .005  # The observed bill is not discarded.


def test_r5_f1_matching_standalone_scope_retains_complete_accounting(tmp_path):
    path, _, _ = standalone_example(tmp_path)
    population = derive(path, tmp_path / "cost.json")["populations"][0]
    assert population["status"] == "complete"
    assert population["cost"] == .005 and population["per_input_hour"] == .9


def test_r5_f2_invalid_gapped_history_retains_cost_without_blocking_healthy_resume(tmp_path):
    path, _, _, _ = resumed_example(tmp_path)
    result = derive(path, tmp_path / "cost.json")
    population = result["populations"][0]
    assert population["status"] == "complete"
    assert population["cost"] == .03 and population["per_input_hour"] == 1.8
    assert population["logical_episode_seconds"] == 60 and population["physical_replay_seconds"] == 120
    invalid = next(window for window in result["windows"] if window["attempt_id"] == "0")
    assert invalid["input_complete"] is False
    assert invalid["replayed_seconds"] is invalid["input_end"] is None
    assert invalid["role_replayed_seconds"] == {"A": None}
    assert "Uncertain source callback" in result["attempts"][0]["window_reason"]
    group = next(group for group in result["ledger_groups"] if group["purpose"] == "harness_invalid")
    assert group["physical_replay_seconds"] is None
    assert group["components"][0]["cost"] == .007
    assert result["attempts"][1]["resumed"] is True


@pytest.mark.parametrize("problem", ["same_count_gap", "overlap", "status", "missing_status", "dac_order", "first_dac"])
def test_bad_selected_callback_mapping_is_scoped_pending_not_complete(tmp_path, problem):
    path, spec, common, manifest = example(tmp_path)
    records = [json.loads(line) for line in (tmp_path / "attempt-1.jsonl").read_text().splitlines()]
    callback = records.pop()
    if problem == "same_count_gap":
        records += [{**callback, "source_frame": first, "source_frames": 20000, "dac_t_ns": dac}
                    for first, dac in ((0, 1_000_000_000), (30000, 21_000_000_000), (40000, 41_000_000_000))]
    elif problem in ("overlap", "dac_order"):
        records += [{**callback, "source_frames": 30000},
                    {**callback, "source_frame": 29000 if problem == "overlap" else 30000,
                     "source_frames": 30000, "dac_t_ns": 0 if problem == "dac_order" else 31_000_000_000}]
    else:
        if problem == "status":
            callback["status"] = "underflow"
        elif problem == "missing_status":
            del callback["status"]
        else:
            callback["dac_t_ns"] += 1
        records.append(callback)
    save_trace(tmp_path, manifest, records)
    bind_manifest(tmp_path, path, spec, common, manifest)
    result = derive(path, tmp_path / "cost.json")
    population = result["populations"][0]
    assert population["status"] == "pending" and population["full_main_input_observed"] is False
    assert population["cost"] is population["per_input_hour"] is None
    assert population["physical_replay_seconds"] is population["submitted_role_timeline_seconds"] is None
    assert population["known_numeric_subtotal"] == .03
    assert result["windows"][0]["callback_integrity"] == {"A": False}


@pytest.mark.parametrize("problem,match", [("source", "Playback source differs"), ("role", "Playback clock/role differs"),
                                          ("anchor", "Trace anchor contradicts"), ("checksum", "checksum differs")])
def test_wrong_frozen_trace_identity_is_rejected(tmp_path, problem, match):
    path, spec, common, manifest = example(tmp_path)
    records = [json.loads(line) for line in (tmp_path / "attempt-1.jsonl").read_text().splitlines()]
    if problem == "source":
        records[1]["audio_sha256"] = "another-frozen-audio"
    elif problem == "role":
        records[1]["role"] = "B"
    elif problem == "anchor":
        records[0]["run"] = "different-capture"
    save_trace(tmp_path, manifest, records)
    if problem == "checksum":
        manifest["attempts"][0]["checksum"] = "0" * 64
    bind_manifest(tmp_path, path, spec, common, manifest)
    with pytest.raises(ValueError, match=match):
        derive(path, tmp_path / "cost.json")


def test_correct_pass_name_does_not_authorize_wrong_physical_channel(tmp_path):
    path, spec, common, manifest = example(tmp_path, "VRCS2", simultaneous=True)
    manifest["plan"]["passes"][0]["roles"] = {"self": {"role": "A"}, "peer": {"role": "B"}}
    records = [json.loads(line) for line in (tmp_path / "attempt-1.jsonl").read_text().splitlines()]
    for record in records:
        if "input_channel" in record:
            record["input_channel"] = "self" if record["input_channel"] == "peer" else "peer"
    save_trace(tmp_path, manifest, records)
    bind_manifest(tmp_path, path, spec, common, manifest)
    with pytest.raises(ValueError, match="physical role/channel routing"):
        derive(path, tmp_path / "cost.json")


@pytest.mark.parametrize("kind", ["pilot", "preparation"])
def test_frozen_nonmain_execution_cannot_be_promoted_by_cost_spec(tmp_path, kind):
    path, spec, common, manifest = example(tmp_path)
    manifest["plan"]["execution_scope"]["kind"] = kind
    bind_manifest(tmp_path, path, spec, common, manifest)
    with pytest.raises(ValueError, match="pilot/preparation cannot be promoted"):
        derive(path, tmp_path / "cost.json")
    spec["manifests"][0]["purpose"] = "preparation"
    dump(path, spec)
    population = derive(path, tmp_path / "preparation-cost.json")["populations"][0]
    assert population["cost"] is None and population["known_numeric_subtotal"] == .03


@pytest.mark.parametrize("change", ["duration", "timeline_hash", "physical_duration", "observation_bounds", "window_identity"])
def test_r5_f3_billing_revision_cannot_replace_known_standalone_timing_basis(tmp_path, change):
    path, spec, _ = standalone_example(tmp_path)
    first_path = tmp_path / "first.json"
    first = derive(path, first_path)
    frozen_common = digest(tmp_path / "common.json")
    spec["revision"] = {"id": "later", "previous": {"path": str(first_path), "sha256": digest(first_path)}}
    if change in ("duration", "timeline_hash"):
        spec["timelines"][0]["artifact"] = dump(tmp_path / "new-timeline.json", {
            "episode_id": "synthetic-episode", "timeline_seconds": 40 if change == "duration" else 20,
            "evidence": "Different experimental timeline, not a bill update"})
        if change == "duration":
            spec["windows"][0]["replayed_seconds"] = 40
    elif change == "physical_duration":
        spec["windows"][0]["replayed_seconds"] = 19
    elif change == "observation_bounds":
        spec["windows"][0]["end"] = "2026-10-20T12:00:51Z"
    else:
        spec["windows"][0]["id"] = "replacement-window"
        spec["components"][0]["coverage"]["window_ids"] = ["replacement-window"]
    dump(path, spec)
    with pytest.raises(ValueError, match="cannot change frozen"):
        derive(path, tmp_path / "later.json")
    assert first["populations"][0]["per_input_hour"] == .9
    assert digest(tmp_path / "common.json") == frozen_common
    assert not (tmp_path / "later.json").exists()


def test_r5_f3_missing_bill_can_arrive_idempotently_with_frozen_inputs_unchanged(tmp_path):
    path, spec, _ = standalone_example(tmp_path)
    supplied = copy.deepcopy(spec["sources"])
    spec["sources"] = []
    dump(path, spec)
    hashes = {name: digest(tmp_path / name) for name in ("common.json", "timeline.json")}
    pending_path = tmp_path / "pending.json"
    pending = derive(path, pending_path)
    assert pending["populations"][0]["status"] == "pending"
    prior_hash = digest(pending_path)
    spec["sources"] = supplied
    spec["revision"] = {"id": "bill-arrived", "previous": {"path": str(pending_path), "sha256": prior_hash}}
    dump(path, spec)
    output = tmp_path / "later.json"
    later = derive(path, output)
    assert later["populations"][0]["status"] == "complete"
    assert later["populations"][0]["per_input_hour"] == .9
    assert later["windows"] == pending["windows"]
    assert derive(path, output) == later
    assert digest(pending_path) == prior_hash
    assert {name: digest(tmp_path / name) for name in hashes} == hashes


@pytest.mark.parametrize("mapped_audio", [False, True])
def test_actual_runner_ledger_and_r4_report_remain_usable_for_costs(tmp_path, runtime, monkeypatch, mapped_audio):
    from bench.quality import evaluate
    from test_episode_quality import spec_fixture
    import bench.runner as runner_module
    from bench.audio import ClockPlayback

    if mapped_audio:
        class ControlledCallbacks(ClockPlayback):
            def start(self, scheduled_start_ns=None):
                super().start(scheduled_start_ns)
                self.records = [{"source_frame": 0, "source_frames": self.info["frames"],
                                 "dac_t_ns": self.first_dac_ns, "status": ""}]
        monkeypatch.setattr(runner_module, "ClockPlayback", ControlledCallbacks)

    _, run = runtime
    root, manifest = run(make_plan(tmp_path / "capture-input", {"TEST": "puripuly"}, kinds=("P1",), duration=2))
    quality_path, quality_spec = spec_fixture(tmp_path, events=[])
    quality_spec["episodes"][0]["episode_id"] = "e1"
    population = quality_spec["populations"][0]
    population["condition"] = {"ordinary_input": "peer", "t1_mode": "simultaneous", "roles": {"A": "peer", "B": "self"}}
    population["roles"][0]["episode_id"] = "e1"
    manifest_binding = {"path": str(root / "manifest.json"), "sha256": digest(root / "manifest.json")}
    population["roles"][0]["selection"] = {"run_manifest": manifest_binding,
                                          "attempt_id": manifest["attempts"][0]["id"], "pass_id": "ordinary-peer"}
    dump(quality_path, quality_spec)
    common_path = tmp_path / "r4.json"
    common = evaluate(quality_path, common_path)
    assert common["calls"] == []
    spec = {"schema_version": 2, "revision": {"id": "real-consumer-pending"},
            "common_report": {"path": str(common_path), "sha256": digest(common_path)},
            "manifests": [{"id": "runner", **manifest_binding, "purpose": "main"}],
            "components": [{"id": "route", "profile": "TEST", "provider": "openrouter", "treatment": "provider",
                            "models": ["synthetic/gemma"], "key_aliases": ["shared"], "services": ["asr", "translation"],
                            "services_evidence": "Synthetic all-in-one arithmetic",
                            "coverage": {"window_ids": ["runner.attempt-1"], "complete": True, "evidence": "Synthetic bill"}}]}
    path = tmp_path / "cost-spec.json"
    dump(path, spec)
    first_path = tmp_path / "pending.json"
    pending = derive(path, first_path)
    assert pending["populations"][0]["full_main_input_observed"] is mapped_audio
    bill = row(start=(timestamp(pending["windows"][0]["start"]) + timedelta(seconds=1)).isoformat(), cost=".01")
    bill_binding = dump(tmp_path / "runtime-bill.json", [bill])
    spec["sources"] = [{"id": "bill", "path": bill_binding["path"], "provider": "openrouter", "kind": "provider_export",
                        "format": "json", "permitted": True, "synthetic": True, "benchmark_only": True,
                        "selection_evidence": "Isolated synthetic bill", "currency": "USD", "fields": {key: key for key in bill},
                        "isolation": {"verified": True, "evidence": "Synthetic isolated input"}}]
    spec["revision"] = {"id": "real-consumer-bill", "previous": {"path": str(first_path), "sha256": digest(first_path)}}
    dump(path, spec)
    later = derive(path, tmp_path / "later.json")
    assert later["populations"][0]["status"] == ("complete" if mapped_audio else "pending")
    assert later["populations"][0]["logical_episode_seconds"] == 2
    assert later["populations"][0]["per_input_hour"] == (18 if mapped_audio else None)
    assert later["populations"][0]["known_numeric_subtotal"] == .01
    assert later["synthetic"] is True


def test_valid_callbacks_with_scheduled_leading_silence_remain_complete(tmp_path):
    path, spec, common, manifest = example(tmp_path)
    records = [json.loads(line) for line in (tmp_path / "attempt-1.jsonl").read_text().splitlines()]
    callback = records[-1]
    records.insert(-1, {**callback, "source_frames": 0, "dac_t_ns": 900_000_000})
    save_trace(tmp_path, manifest, records)
    bind_manifest(tmp_path, path, spec, common, manifest)
    population = derive(path, tmp_path / "cost.json")["populations"][0]
    assert population["full_main_input_observed"] is True
    assert population["cost"] == .03 and population["per_input_hour"] == 1.8
