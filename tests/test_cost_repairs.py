"""Behavioral protections for accepted checkpoint findings F1-F9."""
from __future__ import annotations

import copy
import json

import pytest

from bench.costs import derive
from test_costs import provider_spec, report, row, specification


def second_consumer(spec, *, key="second-key", model="synthetic/gemma", start="2026-10-20T12:02:00Z"):
    window = {**spec["windows"][0], "id": "second-window", "profile": "VRCS2", "start": start,
              "end": "2026-10-20T12:02:20Z" if start.endswith("12:02:00Z") else "2026-10-20T12:00:20Z"}
    component = copy.deepcopy(spec["components"][0])
    component.update(id="VRCS2.translation", profile="VRCS2", key_aliases=[key], models=[model],
                     coverage={"window_ids": [window["id"]], "complete": True, "evidence": "Synthetic second consumer"})
    spec["windows"].append(window)
    spec["components"].append(component)
    return component


def test_f1_same_source_identity_ignores_inspection_wording(tmp_path):
    spec = provider_spec(tmp_path, [row(request_id=None)])
    spec["sources"].append({**copy.deepcopy(spec["sources"][0]), "id": "new-inspection",
                            "selection_evidence": "Different human-inspection wording", "synthetic": False})
    result = report(tmp_path, spec)
    assert len(result["records"]) == 1
    assert result["components"][0]["cost"] == .003
    assert result["components"][0]["provider_records"] == 1
    assert len(result["records"][0]["source_rows"]) == 2


@pytest.mark.parametrize("same_file", [False, True])
def test_f1_mixed_identified_and_anonymous_copies_cannot_add(tmp_path, same_file):
    spec = provider_spec(tmp_path, [row()])
    other = copy.deepcopy(spec["sources"][0])
    other["id"] = "anonymous-export"
    if same_file:
        other["fields"].pop("request_id")
    else:
        path = tmp_path / "anonymous.json"
        path.write_text(json.dumps([row(request_id=None)]), encoding="utf-8")
        other["path"] = str(path)
    spec["sources"].append(other)
    result = report(tmp_path, spec)
    assert result["components"][0]["cost"] == (.003 if same_file else None)
    assert len(result["records"]) == (1 if same_file else 2)
    if not same_file:
        assert all("Possible duplicate" in item["exclusion"] for item in result["records"])


def test_f1_distinct_identified_requests_remain_legitimate_even_when_other_fields_match(tmp_path):
    spec = provider_spec(tmp_path, [row()])
    path = tmp_path / "second.json"
    path.write_text(json.dumps([row(request_id="actually-distinct")]), encoding="utf-8")
    spec["sources"].append({**copy.deepcopy(spec["sources"][0]), "id": "second", "path": str(path)})
    result = report(tmp_path, spec)
    assert result["components"][0]["cost"] == pytest.approx(.006)
    assert len(result["records"]) == 2
    assert all(not item.get("exclusion") for item in result["records"])


def test_r1_distinct_nested_json_arrays_keep_distinct_identified_calls(tmp_path):
    spec = provider_spec(tmp_path, [])
    path = tmp_path / "nested-export.json"
    path.write_text(json.dumps({"exports": {"page_a": [row(request_id="distinct-a")],
                                          "page_b": [row(request_id="distinct-b")]}}), encoding="utf-8")
    source = spec["sources"][0]
    source.update(path=str(path), records_path=["exports", "page_a"])
    spec["sources"].append({**copy.deepcopy(source), "id": "page-b", "records_path": ["exports", "page_b"]})
    result = report(tmp_path, spec)
    assert len(result["records"]) == 2
    assert len({item["request_hash"] for item in result["records"]}) == 2
    assert all(not item.get("exclusion") for item in result["records"])
    assert result["components"][0]["provider_records"] == 2
    assert result["components"][0]["cost"] == pytest.approx(.006)


@pytest.mark.parametrize("request_id", ["same-request", None])
def test_r1_repeated_same_nested_json_record_deduplicates_despite_inspection_wording(tmp_path, request_id):
    spec = provider_spec(tmp_path, [])
    path = tmp_path / "nested-export.json"
    path.write_text(json.dumps({"exports": {"page_a": [row(request_id=request_id)]}}), encoding="utf-8")
    source = spec["sources"][0]
    source.update(path=str(path), records_path=["exports", "page_a"])
    spec["sources"].append({**copy.deepcopy(source), "id": "second-inspection",
                            "selection_evidence": "Independent second inspection, same physical record"})
    result = report(tmp_path, spec)
    assert len(result["records"]) == 1
    assert len(result["records"][0]["source_rows"]) == 2
    assert not result["records"][0].get("exclusion")
    assert result["components"][0]["provider_records"] == 1
    assert result["components"][0]["cost"] == .003


def test_f2_conflicting_alternatives_retain_every_affected_consumer(tmp_path):
    rows = [row(), row(start="2026-10-20T12:02:00Z", key_alias="second-key"),
            row(start="2026-10-20T12:02:01Z", key_alias="second-key", request_id="valid-second")]
    spec = provider_spec(tmp_path, rows)
    second_consumer(spec)
    result = report(tmp_path, spec)
    assert len(result["records"]) == 3
    alternatives = result["records"][:2]
    assert alternatives[0]["request_hash"] == alternatives[1]["request_hash"]
    assert all("Conflicting" in item["exclusion"] for item in alternatives)
    assert {item["attribution"]["component_id"] for item in alternatives} == {"PP1.translation", "VRCS2.translation"}
    first, second = result["components"]
    assert first["cost"] is None and second["cost"] is None
    assert second["known_subtotal"] == .003 and second["status"] == "partial"
    assert second["unresolved_record_ids"] == [alternatives[1]["id"]]
    assert result["records"][2]["attribution"]["status"] == "attributed"
    assert not result["records"][2].get("exclusion")


@pytest.mark.parametrize("unexpected", ["model", "upstream_provider"])
def test_f3_unexpected_actual_identity_on_known_key_is_visible_and_unresolved(tmp_path, unexpected):
    extra = row(request_id="unexpected", **{unexpected: "synthetic/unexpected"})
    spec = provider_spec(tmp_path, [row(), extra,
                                  row(key_alias="distinct-key", request_id="distinct")])
    if unexpected == "upstream_provider":
        spec["sources"][0]["fields"]["upstream_provider"] = "upstream_provider"
        spec["sources"][0]["constants"] = {"upstream_provider": "synthetic/expected"}
        spec["components"][0]["upstream_providers"] = ["synthetic/expected"]
    second_consumer(spec, key="distinct-key", start="2026-10-20T12:00:00Z")
    result = report(tmp_path, spec)
    assert len(result["records"]) == 3
    unusual = result["records"][1]
    assert unusual[unexpected] == "synthetic/unexpected"
    assert unusual["attribution"]["status"] == "unresolved_identity"
    assert {item["component_id"] for item in unusual["attribution"]["potential_candidates"]} == {"PP1.translation"}
    assert result["components"][0]["cost"] is None
    assert result["components"][0]["known_subtotal"] == .003
    assert unusual["id"] in result["components"][0]["unresolved_record_ids"]
    assert result["components"][1]["cost"] == .003  # The different known key is not poisoned.
    assert result["unmatched_record_count"] == 1


def test_f3_selected_outside_windows_remains_safe_unmatched_evidence(tmp_path):
    spec = provider_spec(tmp_path, [row(start="2026-10-21T12:00:00Z")])
    result = report(tmp_path, spec)
    assert len(result["records"]) == 1
    assert result["records"][0]["attribution"]["status"] == "unknown"
    assert result["records"][0]["cost"] == .003
    assert result["unmatched_record_count"] == 1


def test_f4_omitted_pp_asr_blocks_profile_and_default_normalization_but_not_component(tmp_path):
    spec = specification()
    spec["components"] = spec["components"][:1]
    spec["sources"] = spec["sources"][:2]
    spec["denominators"][0]["component_ids"] = ["PP1.translation"]
    result = report(tmp_path, spec)
    assert result["components"][0]["cost"] == .005
    assert result["profiles"][0]["cost"] is None
    assert result["profiles"][0]["missing_services"] == ["asr"]
    assert "asr" in result["profiles"][0]["reason"]
    assert result["denominators"][0]["scope"] == "profile"
    assert result["denominators"][0]["cost"] is None
    assert result["denominators"][0]["per_replayed_conversation_hour"] is None
    spec["denominators"][0]["scope"] = "component"
    result = report(tmp_path, spec)
    subtotal = result["denominators"][0]
    assert subtotal["cost_kind"] == "component_subtotal" and subtotal["cost"] == .005
    assert subtotal["per_replayed_conversation_hour"] == pytest.approx(.9)
    assert result["profiles"][0]["cost"] is None


def test_f4_missing_service_inventory_never_completes_generic_profile(tmp_path):
    spec = specification()
    spec["windows"][0]["profile"] = "GENERIC"
    for component in spec["components"]:
        component["profile"] = "GENERIC"
        component.pop("services")
    result = report(tmp_path, spec)
    assert [item["cost"] for item in result["components"]] == [.005, .001]
    assert result["profiles"][0]["cost"] is None
    assert result["profiles"][0]["missing_services"] == ["asr", "translation"]
    assert len(result["profiles"][0]["inventory_issues"]) == 2


@pytest.mark.parametrize("evidenced", [False, True])
def test_f4_generic_combined_service_requires_actual_combined_evidence(tmp_path, evidenced):
    spec = provider_spec(tmp_path, [row()])
    spec["windows"][0]["profile"] = spec["components"][0]["profile"] = "ALLINONE"
    spec["components"][0]["services"] = ["translation", "asr"]
    if evidenced:
        spec["components"][0]["services_evidence"] = "Synthetic evidence of a genuinely combined route"
    result = report(tmp_path, spec)
    assert result["profiles"][0]["cost"] == (.003 if evidenced else None)
    assert result["profiles"][0]["missing_services"] == ([] if evidenced else ["asr", "translation"])


@pytest.mark.parametrize("profile,provider,services", [
    ("PP1", "openrouter", ["asr"]), ("PP1", "gemini", ["translation"]),
    ("PP2", "chatgpt", ["asr"]), ("PP2", "gemini", ["translation"]),
    ("PP1", "openrouter", ["translation", "asr"]),
])
def test_f4_known_pp_obligations_cannot_be_relabelled(tmp_path, profile, provider, services):
    spec = provider_spec(tmp_path, [])
    component = spec["components"][0]
    component.update(profile=profile, provider=provider, services=services)
    if profile == "PP2" and provider != "gemini":
        component["treatment"] = "subscription"
    spec["windows"][0]["profile"] = profile
    with pytest.raises(ValueError, match="ASR|obligations|separate"):
        report(tmp_path, spec)


def test_f4_profile_denominator_cannot_omit_declared_unknown_or_paid_component(tmp_path):
    spec = specification()
    spec["denominators"][0]["component_ids"] = ["PP1.translation"]
    result = report(tmp_path, spec)
    assert result["profiles"][0]["cost"] == .006
    assert result["denominators"][0]["cost"] is None
    assert "omitted" in result["denominators"][0]["reason"]
    spec["components"][1]["coverage"]["complete"] = False
    result = report(tmp_path, spec)
    assert result["denominators"][0]["cost"] is None


@pytest.mark.parametrize("supplied", [1, 19, 21])
def test_f5_positive_replay_denominator_contradiction_is_unknown_not_overridden(tmp_path, supplied):
    spec = specification()
    spec["denominators"][0]["replay_seconds"] = supplied
    result = report(tmp_path, spec)
    denominator = result["denominators"][0]
    assert denominator["replay_seconds"] == supplied
    assert denominator["observed_replay_seconds"] == 20
    assert denominator["replay_seconds_consistent"] is False
    assert denominator["cost"] is None
    assert denominator["per_replayed_conversation_hour"] is None
    assert denominator["per_1000_reference_sentences"] is None
    assert "contradict" in denominator["reason"]
    assert result["profiles"][0]["cost"] == .006


def test_f5_native_callback_duration_wins_over_wall_tail_and_remains_explicit(tmp_path):
    spec = specification("real-missing-spec.json")
    result = report(tmp_path, spec)
    assert result["denominators"][0]["observed_replay_seconds"] == 40
    assert result["denominators"][0]["replay_seconds_consistent"] is True
    spec["denominators"][0]["replay_seconds"] = 60
    result = report(tmp_path, spec)
    assert result["denominators"][0]["replay_seconds_consistent"] is False
    assert result["denominators"][0]["cost"] is None


def test_f5_mixed_population_profile_names_exact_observed_subset(tmp_path):
    spec = specification()
    other = {**spec["windows"][0], "id": "repeat", "population": "repeat", "start": "2026-10-20T12:02:00Z", "end": "2026-10-20T12:02:10Z"}
    spec["windows"].append(other)
    for component in spec["components"]:
        component["coverage"]["window_ids"].append("repeat")
    spec["denominators"][0].update(window_ids=["pilot-chunk", "repeat"], replay_seconds=30,
                                   population="Explicit synthetic development plus repeat")
    result = report(tmp_path, spec)
    denominator = result["denominators"][0]
    assert denominator["observed_replay_seconds"] == 30
    assert denominator["replay_seconds_consistent"] is True
    assert denominator["window_populations"] == ["development", "repeat"] and denominator["mixed_populations"] is True
    assert denominator["cost"] == .006


@pytest.mark.parametrize("artifact", ["setup", "direction", "resume_setup", "stream", "diagnostic", "extra", "audio", "override", "ledger"])
@pytest.mark.parametrize("temporary_target", [False, True])
def test_f6_protects_all_manifest_linked_raw_artifacts_without_parsing(tmp_path, artifact, temporary_target):
    target = tmp_path / ("raw.json.tmp" if temporary_target else "raw.bin")
    original = b"PRIVATE raw payload deliberately not JSON and never needed by cost processing"
    target.write_bytes(original)
    manifest = {"run": "test-run", "plan": {"stages": [{"kind": "setup", "wave": "test-wave"}]},
                "work": [], "attempts": [], "streams": [], "records": []}
    source = {"id": "capture", "path": str(tmp_path / "manifest.json")}
    if artifact in ("setup", "direction", "resume_setup", "override"):
        kind = artifact if artifact != "override" else "setup"
        manifest["work"] = [{"id": 1, "stage": 0, "profile": "GENERIC", "kind": kind}]
        manifest["attempts"] = [{"id": 1, "work_id": 1, "number": 1, "resumed": 0, "state": "done", "reason": None,
                                 "start_wall": "2026-10-20T12:00:00Z", "end_wall": "2026-10-20T12:00:01Z", "trace": target.name}]
        if artifact == "override":
            manifest["attempts"][0]["trace"] = "unavailable-native.jsonl"
            source["traces"] = {"1": target.name}
    elif artifact == "stream":
        manifest["streams"] = [{"path": target.name}]
    elif artifact == "diagnostic":
        manifest["records"] = [{"kind": "diagnostic_artifact", "detail": json.dumps({"path": target.name})}]
    elif artifact == "extra":
        manifest["records"] = [{"kind": "other_artifact", "detail": json.dumps({"attachments": [{"capture_file": target.name}]})}]
    elif artifact == "audio":
        manifest["plan"]["stages"][0]["audio"] = str(target)
    else:
        manifest["ledger"] = str(target)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    spec = {"version": 1, "manifests": [source], "components": [
        {"id": "unknown", "profile": "GENERIC", "services": ["translation", "asr"], "services_evidence": "Synthetic combined route",
         "provider": "unknown", "treatment": "unknown"}]}
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    output = target.with_name(target.name[:-4]) if temporary_target else target
    with pytest.raises(ValueError, match="overwrite"):
        derive(spec_path, output)
    assert target.read_bytes() == original
    assert manifest_path.read_text(encoding="utf-8") == json.dumps(manifest)


@pytest.mark.parametrize("charge,expected", [("0.003", None), ("0", 0)])
def test_f7_provider_charge_cannot_be_erased_by_free_eligibility(tmp_path, charge, expected):
    spec = provider_spec(tmp_path, [row(cost=charge)])
    spec["windows"][0]["profile"] = "GENERIC"
    component = spec["components"][0]
    component.update(profile="GENERIC", services=["translation", "asr"], services_evidence="Synthetic combined route",
                     treatment="free", access={"observed_eligible": True, "window_ids": ["pilot-chunk"], "evidence": "Synthetic free assertion"})
    result = report(tmp_path, spec)
    assert result["components"][0]["cost"] == expected
    assert result["profiles"][0]["cost"] == expected
    assert result["records"][0]["cost"] == float(charge)
    if charge != "0":
        assert result["components"][0]["status"] == "unknown"
        assert result["components"][0]["access_conflict_record_ids"] == [result["records"][0]["id"]]
        assert "contradict" in result["components"][0]["reason"]


@pytest.mark.parametrize("evidence", [True, ""])
def test_f4_combined_service_evidence_requires_an_explanation_not_a_flag(tmp_path, evidence):
    spec = provider_spec(tmp_path, [row()])
    component = spec["components"][0]
    component.update(profile="GENERIC", services=["translation", "asr"], services_evidence=evidence)
    spec["windows"][0]["profile"] = "GENERIC"
    with pytest.raises(ValueError, match="explanation"):
        report(tmp_path, spec)


@pytest.mark.parametrize("asr_complete", [True, False])
def test_f8_profile_retains_partial_actual_subtotals_without_normalizing(tmp_path, asr_complete):
    spec = specification()
    spec["components"][0]["coverage"]["complete"] = False
    spec["components"][1]["coverage"]["complete"] = asr_complete
    result = report(tmp_path, spec)
    translation, asr = result["components"]
    assert translation["known_subtotal"] == pytest.approx(.005)
    assert translation["cost"] is None
    assert asr["known_subtotal"] == pytest.approx(.001)
    assert asr["cost"] == (.001 if asr_complete else None)
    profile = result["profiles"][0]
    assert profile["known_numeric_subtotal"] == pytest.approx(.006)
    assert profile["cost"] is None
    denominator = result["denominators"][0]
    assert denominator["cost"] is None
    assert denominator["per_replayed_conversation_hour"] is None
    assert denominator["per_1000_reference_sentences"] is None


@pytest.mark.parametrize("known_zero", [False, True])
def test_f8_profile_distinguishes_unknown_from_evidenced_zero(tmp_path, known_zero):
    spec = provider_spec(tmp_path, [row(cost="0" if known_zero else None)])
    spec["components"][0]["coverage"]["complete"] = False
    result = report(tmp_path, spec)
    assert result["components"][0]["known_subtotal"] == (0 if known_zero else None)
    assert result["profiles"][0]["known_numeric_subtotal"] == (0 if known_zero else None)
    assert result["profiles"][0]["cost"] is None


@pytest.mark.parametrize("currency", ["CNY", "USD", None])
@pytest.mark.parametrize("isolation", [True, False])
def test_f9_coarse_export_retains_native_currency_without_conversion(tmp_path, currency, isolation):
    spec = provider_spec(tmp_path, [row()], provider="qwen", granularity="hour", isolation=isolation)
    source = spec["sources"][0]
    source["currency"] = currency
    source["scope"] = {"run": "synthetic-pilot", "wave": "synthetic-wave"}
    source["scope_evidence"] = "Synthetic bucket belongs to this wave"
    result = report(tmp_path, spec)
    coarse = result["coarse_costs"][0]
    assert coarse["known_export_amount"] == pytest.approx(.003)
    assert coarse["currency"] == currency
    assert coarse["cost"] == (.003 if currency == "USD" and isolation else None)
    assert coarse["mixed_workload_possible"] is not isolation
    assert result["components"][0]["cost"] is None
    assert result["components"][0]["known_subtotal"] is None
    assert result["profiles"][0]["cost"] is None
    assert result["profiles"][0]["known_numeric_subtotal"] is None
