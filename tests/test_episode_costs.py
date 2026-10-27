"""Offline episode/report binding and immutable later-evidence regressions."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from bench.cost_inputs import fingerprint
from bench.costs import derive
from bench.storage import digest
from test_costs import FIXTURES, row, specification


def dump(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return {"path": str(path), "sha256": digest(path)}


def example(tmp_path, profile="VRCLT2", simultaneous=False):
    """A retained synthetic R1-shaped capture plus an incomplete R4 report.

    No judge score, app opportunity/admission or provider activity is asserted.
    Charges are invented arithmetic records, not empirical billing.
    """
    condition = {"ordinary_input": "peer" if simultaneous else "self",
                 "t1_mode": "simultaneous" if simultaneous else "split_self",
                 "roles": {"A": "peer", "B": "self"} if simultaneous else {"A": "self", "B": "self"}}
    bindings = [("simultaneous", {"peer": {"role": "A"}, "self": {"role": "B"}})] if simultaneous else [
        ("A", {"self": {"role": "A"}}), ("B", {"self": {"role": "B"}})]
    episode = {"episode_id": "conversation", "kind": "T1", "language_pair": "en-zh", "wave": "wave",
               "roles": {role: {"sample_rate": 1000, "frames": 60000, "audio_sha256": "synthetic-audio-" + role}
                         for role in ("A", "B")}}
    manifest = {"schema_version": 2, "run": "synthetic-capture", "plan": {"execution_scope": {"kind": "synthetic"},
                "episodes": [episode], "passes": [], "profiles": [{"id": profile, "condition": condition}]},
                "work": [], "attempts": [], "streams": []}
    for index, (pass_id, channels) in enumerate(bindings, 1):
        minute = (index - 1) * 2
        start_ns = 1_000_000_000
        records = [{"record": "attempt_start", "wall": f"2026-10-20T12:{minute:02}:00Z", "t_ns": start_ns,
                    "clock_session": "synthetic-clock", "run": manifest["run"], "profile": profile,
                    "episode_id": "conversation", "pass_id": pass_id, "attempt": index}]
        for channel, binding in channels.items():
            role = binding["role"]
            records += [{"record": "source_playback", "profile": profile, "episode_id": "conversation",
                         "pass_id": pass_id, "attempt": index, "role": role, "input_channel": channel,
                         "clock_session": "synthetic-clock", "playback_dac_start_ns": start_ns,
                         "actual_dac_observed": False, "audio_sha256": "synthetic-audio-" + role},
                        {"record": "audio_callback", "input_channel": channel, "source_frame": 0,
                         "source_frames": 60000, "dac_t_ns": start_ns}]
        trace = tmp_path / f"attempt-{index}.jsonl"
        trace.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
        manifest["plan"]["passes"].append({"episode_id": "conversation", "pass_id": pass_id, "wave": "wave",
                                             "profiles": [profile], "roles": channels})
        manifest["work"].append({"id": index, "profile": profile, "episode_id": "conversation",
                                  "pass_id": pass_id, "kind": "T1", "outcome": "unknown_no_output"})
        manifest["attempts"].append({"id": index, "work_id": index, "number": 1, "resumed": False, "state": "done",
                                      "start_wall": f"2026-10-20T12:{minute:02}:00Z",
                                      "end_wall": f"2026-10-20T12:{minute + 1:02}:15Z", "end_ns": 76_000_000_000,
                                      "trace": trace.name, "checksum": digest(trace), "reason": None,
                                      "detail": {"observation_end_ns": 76_000_000_000}})
    manifest_binding = dump(tmp_path / "manifest.json", manifest)
    common = {"schema_version": 1, "kind": "episode_quality", "report_version": "r4-episode-quality-v1",
              "status": "incomplete", "protocol_revision": "synthetic-offline-cost-counterexample",
              "synthetic_judgments": True, "planned_episodes": [{key: episode[key] for key in ("episode_id", "kind", "language_pair")}],
              "populations": [{"profile": profile,
                  "measurement_condition": "peer/simultaneous" if simultaneous else "self/split", "condition": condition,
                  "cost_binding_id": "existing-r4-population-binding", "role_results": []}]}
    for role in ("A", "B"):
        aid = 1 if simultaneous or role == "A" else 2
        selection = {"run_manifest": manifest_binding, "attempt_id": aid,
                     "pass_id": "simultaneous" if simultaneous else role}
        common["populations"][0]["role_results"].append({"episode_id": "conversation", "role": role,
            "selection": selection, "cost_binding_id": "existing-r4-role-" + role,
            "quality": {"status": "unknown", "score": None}, "checkpoints": []})
    common_binding = dump(tmp_path / "common.json", common)
    provider = "qwen" if profile == "VRCLT2" else "openrouter"
    bills = [row(start="2026-10-20T12:00:01Z", cost=".01", request_id="invented-a", window_id="capture.attempt-1"),
             row(start="2026-10-20T12:00:02Z" if simultaneous else "2026-10-20T12:02:01Z", cost=".02",
                 request_id="invented-b", window_id="capture.attempt-1" if simultaneous else "capture.attempt-2")]
    dump(tmp_path / "bills.json", bills)
    spec = {"schema_version": 2, "synthetic": True, "revision": {"id": "observed-example"}, "common_report": common_binding,
            "manifests": [{"id": "capture", **manifest_binding, "purpose": "main"}],
            "components": [{"id": profile + ".route", "profile": profile, "provider": provider, "treatment": "provider",
                            "models": ["synthetic/gemma"], "key_aliases": ["shared"], "services": ["asr", "translation"],
                            "services_evidence": "Invented all-in-one arithmetic route, not a real model price",
                            "coverage": {"window_ids": ["capture.attempt-" + str(i) for i in range(1, len(bindings) + 1)],
                                         "complete": True, "evidence": "Complete synthetic bills for both passes"}}],
            "sources": [{"id": "invented-bills", "path": str(tmp_path / "bills.json"), "kind": "provider_export",
                         "provider": provider, "format": "json", "permitted": True, "synthetic": True,
                         "benchmark_only": True, "selection_evidence": "Invented selected records; no account activity",
                         "currency": "USD", "fields": {key: key for key in (*bills[0].keys(), "product_retry")},
                         "isolation": {"verified": True, "evidence": "Synthetic isolated fixture, not account proof"}}]}
    path = tmp_path / "cost-spec.json"
    dump(path, spec)
    return path, spec, common, manifest


@pytest.mark.parametrize("profile", ["VRCLT1", "VRCLT2", "KIKI1", "KIKI2"])
def test_split_both_passes_billed_original_timeline_once(tmp_path, profile):
    path, spec, common, manifest = example(tmp_path, profile)
    result = derive(path, tmp_path / "cost.json")
    population = result["populations"][0]
    assert result["version"] == "r5-cost-evidence-v1"
    assert result["common_report"]["sha256"] == digest(tmp_path / "common.json")
    assert population["cost_binding_id"] == "existing-r4-population-binding"
    assert population["cost"] == pytest.approx(.03)
    assert population["logical_episode_seconds"] == 60
    assert population["physical_replay_seconds"] == 120
    assert population["per_input_hour"] == pytest.approx(1.8)
    assert [row["pass_id"] for row in population["role_bindings"]] == ["A", "B"]
    assert common["status"] == "incomplete"  # Cost completeness is not quality/admission.


def test_simultaneous_roles_share_one_pass_and_one_timeline(tmp_path):
    path, _, _, _ = example(tmp_path, "VRCS2", simultaneous=True)
    population = derive(path, tmp_path / "cost.json")["populations"][0]
    assert population["cost"] == .03 and population["per_input_hour"] == 1.8
    assert population["logical_episode_seconds"] == population["physical_replay_seconds"] == 60
    assert population["submitted_role_timeline_seconds"] == 120
    assert len(population["pass_costs"]) == 1


def test_pending_later_revision_is_idempotent_and_cannot_mutate_quality_or_prior(tmp_path):
    path, spec, _, _ = example(tmp_path)
    original = (tmp_path / "common.json").read_bytes()
    frozen_hash = digest(tmp_path / "common.json")
    pending = copy.deepcopy(spec)
    pending["revision"]["id"] = "pending"
    pending["sources"] = []
    dump(path, pending)
    pending_path = tmp_path / "pending.json"
    first = derive(path, pending_path)
    assert first["populations"][0]["cost"] is None
    assert first["populations"][0]["status"] == "pending"
    assert derive(path, pending_path) == first
    frozen_pending = pending_path.read_bytes()
    spec["revision"] = {"id": "owner-evidence-2", "previous": {"path": str(pending_path), "sha256": digest(pending_path)}}
    dump(path, spec)
    later_path = tmp_path / "later.json"
    later = derive(path, later_path)
    assert later["populations"][0]["cost"] == .03
    assert later["revision"]["previous"]["id"] == "pending"
    assert later["revision"]["evidence_sha256"] != first["revision"]["evidence_sha256"]
    assert digest(tmp_path / "common.json") == frozen_hash
    assert (tmp_path / "common.json").read_bytes() == original
    assert pending_path.read_bytes() == frozen_pending
    assert derive(path, later_path) == later
    with pytest.raises(ValueError, match="overwrite"):
        derive(path, pending_path)
    spec["revision"]["id"] = "third"
    dump(path, spec)
    with pytest.raises(ValueError, match="immutable"):
        derive(path, later_path)


def test_incomplete_components_and_subscriptions_keep_known_subtotals(tmp_path):
    path, spec, _, _ = example(tmp_path, "KIKI1")
    component = spec["components"][0]
    component["services"] = ["translation"]
    dump(path, spec)
    result = derive(path, tmp_path / "missing-asr.json")
    population = result["populations"][0]
    assert population["known_numeric_subtotal"] == .03
    assert population["missing_services"] == ["asr"]
    assert population["cost"] is population["per_input_hour"] is None
    component["treatment"] = "subscription"
    dump(path, spec)
    result = derive(path, tmp_path / "subscription.json")
    assert result["components"][0]["status"] == "subscription"
    assert result["components"][0]["cost"] is None
    assert result["populations"][0]["per_input_hour"] is None


def test_coarse_ambiguous_amount_not_divided_among_passes(tmp_path):
    path, spec, _, _ = example(tmp_path)
    spec["sources"][0]["granularity"] = "hour"
    spec["sources"][0]["fields"].pop("window_id")
    spec["sources"][0]["scope"] = {"run": "synthetic-capture", "wave": "wave"}
    spec["sources"][0]["scope_evidence"] = "Synthetic whole wave"
    dump(tmp_path / "bills.json", [row(start="2026-10-20T12:00:00Z", end="2026-10-20T13:00:00Z", cost=".03")])
    dump(path, spec)
    result = derive(path, tmp_path / "coarse.json")
    assert result["coarse_costs"][0]["cost"] == .03
    assert len(result["records"][0]["attribution"]["candidates"]) == 2
    assert result["populations"][0]["cost"] is None
    assert result["populations"][0]["per_input_hour"] is None


def test_product_billed_retry_in_tail_is_included_but_other_purposes_are_separate(tmp_path):
    path, spec, _, _ = example(tmp_path)
    bills = json.loads((tmp_path / "bills.json").read_text())
    bills.append(row(start="2026-10-20T12:01:10Z", cost=".005", request_id="product-retry",
                     window_id="capture.attempt-1", product_retry=True))
    spec["windows"] = []
    for index, (purpose, state) in enumerate([("repeat", "done"), ("preparation", "done"),
                                              ("main", "invalid"), ("harness_retry", "done")], 4):
        minute = index * 2
        wid = purpose + "-" + state
        spec["windows"].append({"id": wid, "run": "other-run", "wave": "wave", "profile": "VRCLT2",
            "episode_id": "conversation", "pass_id": "A", "attempt_id": str(index), "roles": ["A"], "kind": "T1",
            "purpose": purpose, "state": state, "replayed_seconds": 12, "input_complete": False,
            "start": f"2026-10-20T12:{minute:02}:00Z", "end": f"2026-10-20T12:{minute:02}:27Z", "evidence": "Synthetic extra purpose"})
        bills.append(row(start=f"2026-10-20T12:{minute:02}:01Z", cost="1", request_id=wid, window_id=wid))
        spec["components"][0]["coverage"]["window_ids"].append(wid)
    dump(tmp_path / "bills.json", bills)
    dump(path, spec)
    result = derive(path, tmp_path / "cost.json")
    assert result["populations"][0]["cost"] == .035
    assert result["populations"][0]["per_input_hour"] == 2.1
    assert result["populations"][0]["logical_episode_seconds"] == 60
    assert result["profiles"][0]["cost"] == 4.035  # Audit ledger, not public selected-main total.
    assert {group["purpose"] for group in result["ledger_groups"]} == {"main", "repeat", "preparation", "harness_retry", "harness_invalid"}
    assert sum(record["product_retry"] is True for record in result["records"]) == 1


@pytest.mark.parametrize("partial", [True, False])
def test_partial_and_invalid_observed_input_never_rank_as_full_episode(tmp_path, partial):
    path, spec, common, manifest = example(tmp_path)
    if partial:
        trace = tmp_path / "attempt-1.jsonl"
        records = [json.loads(line) for line in trace.read_text().splitlines()]
        records[-1]["source_frames"] = 17000
        trace.write_text("".join(json.dumps(record) + "\n" for record in records))
        manifest["attempts"][0]["checksum"] = digest(trace)
    else:
        manifest["attempts"][0]["state"] = "invalid"
    mb = dump(tmp_path / "manifest.json", manifest)
    spec["manifests"][0].update(mb)
    for role in common["populations"][0]["role_results"]:
        role["selection"]["run_manifest"] = mb
    spec["common_report"] = dump(tmp_path / "common.json", common)
    dump(path, spec)
    result = derive(path, tmp_path / "cost.json")
    population = result["populations"][0]
    assert population["logical_episode_seconds"] == 60
    assert population["physical_replay_seconds"] == (77 if partial else 120)
    assert population["cost"] is population["per_input_hour"] is None
    assert population["known_numeric_subtotal"] == .03
    assert population["full_main_input_observed"] is False


def test_later_revision_cannot_rebind_changed_frozen_report(tmp_path):
    path, spec, common, _ = example(tmp_path)
    first_path = tmp_path / "first.json"
    derive(path, first_path)
    spec["revision"] = {"id": "changed", "previous": {"path": str(first_path), "sha256": digest(first_path)}}
    common["status"] = "changed-quality-is-not-a-cost-update"
    spec["common_report"] = dump(tmp_path / "changed-common.json", common)
    dump(path, spec)
    with pytest.raises(ValueError, match="same immutable common report"):
        derive(path, tmp_path / "later.json")


@pytest.mark.parametrize("target", ["common.json", "manifest.json", "attempt-1.jsonl", "bills.json", "cost-spec.json"])
@pytest.mark.parametrize("temporary", [False, True])
def test_new_bound_inputs_and_temporary_siblings_are_protected(tmp_path, target, temporary):
    path, _, _, _ = example(tmp_path)
    source = tmp_path / target
    before = source.read_bytes()
    output = source.with_name("output.json") if temporary else source
    if temporary:
        os.link(source, output.with_name(output.name + ".tmp"))
    with pytest.raises(ValueError, match="overwrite"):
        derive(path, output)
    assert source.read_bytes() == before


def test_legacy_cost_spec_cannot_execute_new_normalization(tmp_path):
    path = tmp_path / "legacy.json"
    dump(path, {"version": 1})
    with pytest.raises(ValueError, match="schema_version 2"):
        derive(path, tmp_path / "result.json")


def test_historical_evidence_is_exercisable_without_invented_common_identity(tmp_path):
    spec = specification("real-missing-spec.json")
    path = tmp_path / "historical.json"
    dump(path, spec)
    result = derive(path, tmp_path / "historical-cost.json")
    assert result["common_report"] is None and result["populations"] == []
    assert [row["replayed_seconds"] for row in result["attempts"]] == [None, None, 10, 40]
    assert all(row["cost"] is None for row in result["profiles"])
    assert sum(row["known_subtotal"] for row in result["consumption_summaries"]) == pytest.approx(.2595575)
    assert [row["unknown_calls"] for row in result["consumption_summaries"]] == [["pilot-01"], ["main-09"]]
    assert all(row["total"] is None for row in result["consumption_summaries"])
    assert all("not_native_export" in row["amount_basis"] for row in result["consumption_summaries"])


def test_supported_cli_returns_revision_and_actual_arithmetic(tmp_path):
    path, _, _, _ = example(tmp_path, "KIKI2")
    output = tmp_path / "cli-cost.json"
    process = subprocess.run([sys.executable, "-m", "bench.cli", "costs", "--spec", str(path), "--output", str(output)],
                             text=True, capture_output=True, check=False)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["revision"] == "observed-example"
    assert json.loads(output.read_text())["populations"][0]["per_input_hour"] == 1.8


def test_production_tts_and_judge_components_never_enter_app_numerator(tmp_path):
    path, spec, _, _ = example(tmp_path)
    bills = json.loads((tmp_path / "bills.json").read_text())
    spec["windows"] = []
    for index, ledger in enumerate(("production", "tts", "judge"), 4):
        wid = "aux-" + ledger
        spec["windows"].append({"id": wid, "run": "producer-run", "wave": "production", "profile": "producer",
            "ledger": ledger, "purpose": "preparation", "state": "done", "start": "2026-10-20T14:00:00Z",
            "end": "2026-10-20T14:01:00Z", "evidence": "Isolated invented production records"})
        spec["components"].append({"id": wid, "profile": "producer", "provider": "qwen", "ledger": ledger,
            "treatment": "provider", "coverage": {"window_ids": [wid], "complete": True, "evidence": "Invented auxiliary bill"}})
        bills.append(row(start="2026-10-20T14:00:01Z", cost="1", request_id=wid, window_id=wid))
    dump(tmp_path / "bills.json", bills)
    dump(path, spec)
    result = derive(path, tmp_path / "cost.json")
    assert result["populations"][0]["cost"] == .03
    assert result["populations"][0]["per_input_hour"] == 1.8
    assert {component["ledger"] for component in result["auxiliary_components"]} == {"production", "tts", "judge"}
    assert [component["cost"] for component in result["auxiliary_components"]] == [1, 1, 1]
    assert [profile["profile"] for profile in result["profiles"]] == ["VRCLT2"]
    assert all(group["components"] for group in result["ledger_groups"])


def test_retained_consumption_summary_cannot_be_relabelled_as_app_billing(tmp_path):
    spec = specification("real-missing-spec.json")
    spec["consumption_summaries"][0]["ledger"] = "evaluation"
    path = tmp_path / "summary.json"
    dump(path, spec)
    with pytest.raises(ValueError, match="cannot enter evaluation"):
        derive(path, tmp_path / "cost.json")


def test_frozen_report_hash_is_enforced_before_any_output(tmp_path):
    path, _, _, _ = example(tmp_path)
    (tmp_path / "common.json").write_text("{}")
    with pytest.raises(ValueError, match="checksum"):
        derive(path, tmp_path / "cost.json")
    assert not (tmp_path / "cost.json").exists()


def test_cost_publication_does_not_copy_private_r4_paths(tmp_path):
    path, _, _, _ = example(tmp_path)
    result = derive(path, tmp_path / "cost.json")
    serialized = json.dumps(result)
    assert str(tmp_path) not in serialized
    assert '"run_manifest":' not in serialized  # The harmless provenance kind may say run_manifest.
    assert '"invented-a"' not in serialized and '"invented-b"' not in serialized


@pytest.mark.parametrize("name", ["kind", "language_pair"])
def test_frozen_episode_metadata_cannot_disagree_with_common_population(tmp_path, name):
    path, spec, common, _ = example(tmp_path)
    common["planned_episodes"][0][name] = "P1" if name == "kind" else "ja-ko"
    spec["common_report"] = dump(tmp_path / "changed-common.json", common)
    dump(path, spec)
    with pytest.raises(ValueError, match="contradicts common report"):
        derive(path, tmp_path / "cost.json")


def test_real_r4_report_is_consumed_without_judge_dispatch_or_quality_mutation(tmp_path):
    from bench.quality import evaluate
    from test_episode_quality import spec_fixture

    quality_path, quality_spec = spec_fixture(tmp_path)
    quality_spec["populations"][0]["condition"] = {
        "ordinary_input": "peer", "t1_mode": "simultaneous", "roles": {"A": "peer", "B": "self"}}
    selection = quality_spec["populations"][0]["roles"][0]["selection"]
    selection["scope"]["pass_id"] = "ordinary-peer"
    dump(quality_path, quality_spec)
    quality_path_out = tmp_path / "r4-report.json"
    report = evaluate(quality_path, quality_path_out)
    frozen = quality_path_out.read_bytes()
    assert report["schema_version"] == 1 and report["report_version"] == "r4-episode-quality-v1"
    assert report["calls"] == []  # Offline quality remains incomplete, never paid.
    timeline = dump(tmp_path / "timeline.json", {"episode_id": "ep", "timeline_seconds": 20})
    spec = {"schema_version": 2, "revision": {"id": "from-real-r4-interface"},
            "common_report": {"path": str(quality_path_out), "sha256": digest(quality_path_out)},
            "timelines": [{"episode_id": "ep", "artifact": timeline}],
            "windows": [{"id": "observed", "run": "synthetic", "wave": "synthetic", "profile": "TEST",
                "episode_id": "ep", "pass_id": "ordinary-peer", "attempt_id": "1", "roles": ["A"], "kind": "P1",
                "state": "done", "purpose": "main", "input_complete": True, "replayed_seconds": 20,
                "start": "2026-10-20T12:00:00Z", "end": "2026-10-20T12:00:35Z",
                "evidence": "Invented observed input, no billing evidence", "role_bindings": {"A": fingerprint(selection)}}],
            "components": [{"id": "unknown-route", "profile": "TEST", "provider": "unknown", "treatment": "unknown",
                "services": ["asr", "translation"], "services_evidence": "Unpriced all-in-one fixture",
                "coverage": {"window_ids": ["observed"], "complete": False}}]}
    path = tmp_path / "cost-spec.json"
    dump(path, spec)
    costs = derive(path, tmp_path / "cost.json")
    assert costs["populations"][0]["logical_episode_seconds"] == 20
    assert costs["populations"][0]["cost"] is None
    assert quality_path_out.read_bytes() == frozen


@pytest.mark.parametrize("spec_path", [
    "split-example/spec.json", "split-example/pending-spec.json", "split-example/incomplete-spec.json",
    "split-example/coarse-spec.json", "subscription-example/spec.json", "synthetic-spec.json",
])
def test_retained_cli_inputs_bind_exact_bytes(tmp_path, spec_path):
    result = derive(FIXTURES / spec_path, tmp_path / "cost.json")
    assert result["common_report"] is not None
    assert result["populations"][0]["logical_episode_seconds"] in (20, 60)
    if spec_path == "split-example/spec.json":
        assert result["populations"][0]["cost"] == .03
        assert result["populations"][0]["per_input_hour"] == 1.8


def test_incomplete_r4_condition_is_retained_pending_not_reinvented(tmp_path):
    path, spec, common, _ = example(tmp_path)
    common["populations"][0]["condition"] = {"label": "unresolved"}
    spec["common_report"] = dump(tmp_path / "unresolved-common.json", common)
    dump(path, spec)
    result = derive(path, tmp_path / "cost.json")
    assert result["populations"][0]["cost"] is None
    assert result["populations"][0]["known_numeric_subtotal"] == .03
    assert "structured measurement condition missing" in result["populations"][0]["reason"]
