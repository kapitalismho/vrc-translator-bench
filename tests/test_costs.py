from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from bench.cost_inputs import fingerprint, timestamp
from bench.costs import derive
from bench.storage import digest

FIXTURES = Path(__file__).parent / "fixtures" / "costs"


def specification(name="synthetic-spec.json"):
    spec = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    for section in ("sources", "manifests", "evidence_files"):
        for source in spec.get(section, []):
            source["path"] = str((FIXTURES / source["path"]).resolve())
            if "export_provenance" in source:
                source["export_provenance"] = str((FIXTURES / source["export_provenance"]).resolve())
    for summary in spec.get("consumption_summaries", []):
        summary["artifact"]["path"] = str((FIXTURES / summary["artifact"]["path"]).resolve())
    if "common_report" in spec:
        spec["common_report"]["path"] = str((FIXTURES / spec["common_report"]["path"]).resolve())
    for timeline in spec.get("timelines", []):
        timeline["artifact"]["path"] = str((FIXTURES / timeline["artifact"]["path"]).resolve())
    return spec


def report(tmp_path, spec):
    directory = tmp_path / f"reconciliation-{len(list(tmp_path.glob('reconciliation-*')))}"
    directory.mkdir()
    if spec.get("mode") != "historical_evidence_only":
        # Low-level ingestion cases vary profiles/windows. Keep a truthful,
        # incomplete synthetic common report for that test's selected input.
        common = json.loads((FIXTURES / "synthetic-common.json").read_text(encoding="utf-8"))
        profiles = sorted({window["profile"] for window in spec.get("windows", [])})
        common["populations"] = []
        for profile in profiles:
            windows = [window for window in spec["windows"] if window["profile"] == profile]
            window = windows[0]
            selection = {"history": {"path": str(FIXTURES / "synthetic-history.json"),
                                     "sha256": digest(FIXTURES / "synthetic-history.json")},
                         "scope": {"episode": window["episode_id"], "profile": profile,
                                   "run": window["run"], "pass_id": window["pass_id"], "attempt": window["attempt_id"]}}
            window["role_bindings"] = {"A": fingerprint(selection)}
            common["populations"].append({"profile": profile, "measurement_condition": "peer/simultaneous",
                                          "condition": {"ordinary_input": "peer", "t1_mode": "simultaneous",
                                                        "roles": {"A": "peer", "B": "self"}},
                                          "role_results": [{"episode_id": window["episode_id"], "role": "A",
                                                            "selection": selection, "quality": {"status": "unknown", "score": None},
                                                            "checkpoints": []}]})
        common_path = directory / "common.json"
        common_path.write_text(json.dumps(common), encoding="utf-8")
        spec["common_report"] = {"path": str(common_path), "sha256": digest(common_path)}
    spec_path = directory / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    return derive(spec_path, directory / "report.json")


def provider_spec(tmp_path, rows, *, provider="openrouter", granularity="request", isolation=True):
    path = tmp_path / "export.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    spec = specification()
    spec["components"] = [spec["components"][0]]
    spec["sources"] = [{"id": "export", "path": str(path), "provider": provider, "kind": "provider_export",
                        "format": "json", "permitted": True, "synthetic": True, "granularity": granularity,
                        "benchmark_only": True, "selection_evidence": "Synthetic selected benchmark-owned rows",
                        "currency": "USD", "fields": {key: key for key in ("start", "end", "model", "key_alias", "cost", "request_id")},
                        "isolation": {"verified": isolation, "evidence": "synthetic account only"}}]
    spec["components"][0]["provider"] = provider
    if provider == "qwen":
        spec["windows"][0]["profile"] = spec["components"][0]["profile"] = "VRCLT2"
    return spec


def row(**changes):
    value = {"start": "2026-10-20T12:00:00Z", "end": "2026-10-20T12:05:00Z", "model": "synthetic/gemma",
             "key_alias": "shared", "cost": "0.003", "request_id": "synthetic-request"}
    return {**value, **changes}


def test_hand_reconciled_selected_output(tmp_path):
    result = report(tmp_path, specification())
    translation, asr = result["components"]
    assert translation["cost"] == pytest.approx(.005)
    assert translation["internal_usage"]["calls"] == 2
    assert translation["all_bound_internal_usage"]["logical_requests"] == 2
    assert translation["internal_usage"]["input_tokens"]["known"] == 1500
    assert translation["internal_usage"]["cached_tokens"]["known"] == 200
    assert translation["internal_usage"]["output_tokens"]["known"] == 500
    assert translation["internal_usage"]["reasoning_tokens"]["known"] == 50
    assert translation["internal_calculation"]["known_subtotal"] == pytest.approx(.00235)
    assert translation["reconciliation"]["difference_provider_minus_internal"] == pytest.approx(.00265)
    assert asr["internal_usage"]["audio_seconds"]["known"] == 10
    assert asr["cost"] is None
    assert asr["calculated_cost"] == pytest.approx(.001)
    assert asr["amount_basis"] == "usage_times_dated_price_not_billing"
    assert result["profiles"][0]["cost"] is None
    assert result["profiles"][0]["calculated_cost"] == pytest.approx(.006)
    assert result["populations"][0]["per_input_hour"] is None
    assert result["populations"][0]["calculated_per_input_hour"] == pytest.approx(1.08)
    serialized = json.dumps(result)
    for private in ("DO_NOT_COPY_THIS", "PRIVATE_UNRELATED", "private/unrelated", "unrelated-account-record", str(tmp_path), "synthetic-1", "successful_bytes"):
        assert private not in serialized
    assert result["unmatched_record_count"] == 1  # One logical start precedes the playback window.
    assert next(item for item in result["provenance"] if item["id"] == "openrouter-synthetic")["private_filtered_row_count"] == 1
    assert all("sha256" in item for item in result["provenance"])
    assert result["price_tables"][0]["date"] == "2026-10-20"
    assert result["components"][0]["coverage"]["claim_type"].startswith("operator_supplied")


@pytest.mark.parametrize(("start", "expected"), [
    ("2026-10-20T12:00:00Z", "attributed"),
    ("2026-10-20T21:00:50+09:00", "attributed"),
    ("2026-10-20T12:00:50.000001Z", "unknown"),
    ("2026-10-20T11:59:59.999999Z", "unknown"),
])
def test_inclusive_start_grace_and_timezone(tmp_path, start, expected):
    result = report(tmp_path, provider_spec(tmp_path, [row(start=start)]))
    assert (result["records"][0]["attribution"]["status"] if result["records"] else None) == expected
    assert result["components"][0]["cost"] == (.003 if expected == "attributed" else None)


def test_completion_cannot_replace_missing_request_start(tmp_path):
    result = report(tmp_path, provider_spec(tmp_path, [row(start=None, end="2026-10-20T12:00:03Z")]))
    assert result["records"][0]["attribution"]["status"] == "unknown"
    assert "START" in result["records"][0]["attribution"]["reason"]
    assert result["components"][0]["cost"] is None


def test_shared_pp1_vrcs2_ambiguity_never_subtracts_internal_estimate(tmp_path):
    spec = specification()
    other = copy.deepcopy(spec["windows"][0])
    other.update(id="other", profile="VRCS2")
    spec["windows"].append(other)
    component = copy.deepcopy(spec["components"][0])
    component.update(id="VRCS2.translation", profile="VRCS2", coverage={"window_ids": ["other"], "complete": True, "evidence": "synthetic"})
    spec["components"].append(component)
    result = report(tmp_path, spec)
    exports = [item for item in result["records"] if item["kind"] == "provider_export"]
    assert len(exports) == 2
    assert all(item["attribution"]["status"] == "ambiguous" and len(item["attribution"]["candidates"]) == 2 for item in exports)
    assert result["components"][0]["cost"] is None
    assert result["components"][0]["internal_calculation"]["known_subtotal"] == pytest.approx(.00235)
    assert result["components"][2]["cost"] is None
    assert result["components"][0]["reconciliation"]["difference_provider_minus_internal"] is None


def test_adjacent_grace_overlap_is_not_first_match(tmp_path):
    spec = provider_spec(tmp_path, [row(start="2026-10-20T12:00:20Z")])
    other = copy.deepcopy(spec["windows"][0])
    other.update(id="adjacent", start="2026-10-20T12:00:20Z", end="2026-10-20T12:00:40Z", kind="output_check")
    spec["windows"].append(other)
    result = report(tmp_path, spec)
    assert result["records"][0]["attribution"]["status"] == "ambiguous"
    assert result["components"][0]["cost"] is None


@pytest.mark.parametrize("isolation", [False, True])
def test_qwen_coarse_bucket_never_invents_chunk_amount(tmp_path, isolation):
    spec = provider_spec(tmp_path, [row(start="2026-10-20T12:00:00Z", end="2026-10-20T13:00:00Z")], provider="qwen", granularity="hour", isolation=isolation)
    spec["sources"][0]["scope"] = {"run": "synthetic-pilot", "wave": "synthetic-wave"}
    spec["sources"][0]["scope_evidence"] = "Synthetic bucket known to belong to this wave"
    result = report(tmp_path, spec)
    assert result["records"][0]["attribution"]["status"] == "coarse"
    assert result["records"][0]["attribution"]["window_id"] is None
    assert result["components"][0]["cost"] is None
    assert result["coarse_costs"][0]["cost"] == (.003 if isolation else None)
    assert result["coarse_costs"][0]["mixed_workload_possible"] is not isolation


def test_qwen_planned_only_consumer_not_account_isolation(tmp_path):
    result = report(tmp_path, provider_spec(tmp_path, [row()], provider="qwen", isolation=False))
    assert result["records"][0]["attribution"]["status"] == "conditional"
    assert "sole consumer" in result["records"][0]["attribution"]["reason"]
    assert result["components"][0]["cost"] is None


def test_duplicate_request_and_duplicate_sources_count_once(tmp_path):
    spec = specification()
    spec["sources"].append({**copy.deepcopy(spec["sources"][0]), "id": "export-copy"})
    spec["sources"].append({**copy.deepcopy(spec["sources"][1]), "id": "log-copy"})
    result = report(tmp_path, spec)
    assert result["components"][0]["provider_records"] == 2
    assert result["components"][0]["internal_usage"]["calls"] == 2
    assert result["components"][0]["cost"] == pytest.approx(.005)
    assert len(next(item for item in result["records"] if item["kind"] == "provider_export")["sources"]) == 2


def test_conflicting_duplicate_excludes_both_amounts(tmp_path):
    result = report(tmp_path, provider_spec(tmp_path, [row(), row(cost="8")]))
    assert len(result["records"]) == 2
    assert {item["cost"] for item in result["records"]} == {.003, 8}
    assert all("Conflicting" in item["exclusion"] and item["conflicting_record_ids"] for item in result["records"])
    assert result["components"][0]["cost"] is None
    assert result["components"][0]["known_subtotal"] is None


def test_aggregate_detail_overlap_is_not_additive(tmp_path):
    spec = provider_spec(tmp_path, [row()])
    path = tmp_path / "bucket.json"
    path.write_text(json.dumps([row(start="2026-10-20T12:00:00Z", end="2026-10-20T13:00:00Z", cost=".01", request_id="bucket")]), encoding="utf-8")
    spec["sources"].append({**copy.deepcopy(spec["sources"][0]), "id": "bucket", "path": str(path), "granularity": "hour", "scope": {"run": "synthetic-pilot", "wave": "synthetic-wave"}, "scope_evidence": "Synthetic wave-scoped export"})
    result = report(tmp_path, spec)
    detail = next(item for item in result["records"] if item["granularity"] == "request")
    assert "aggregate" in detail["exclusion"]
    assert result["coarse_costs"][0]["cost"] == .01
    assert result["components"][0]["cost"] is None
    assert result["components"][0]["known_subtotal"] is None


def test_overlap_between_buckets_retains_unknown_union(tmp_path):
    spec = provider_spec(tmp_path, [row(end="2026-10-20T13:00:00Z"), row(request_id="second", end="2026-10-20T14:00:00Z")], granularity="hour")
    spec["sources"][0]["scope"] = {"run": "synthetic-pilot", "wave": "synthetic-wave"}
    result = report(tmp_path, spec)
    assert len(result["coarse_costs"]) == 2
    assert all(item["cost"] is None for item in result["coarse_costs"])
    assert all("Overlapping" in item["exclusion"] for item in result["records"])


def test_partial_provider_coverage_and_missing_asr_never_complete_total(tmp_path):
    spec = specification()
    spec["components"][0]["coverage"]["complete"] = False
    spec["sources"] = spec["sources"][:2]
    result = report(tmp_path, spec)
    assert result["components"][0]["known_subtotal"] == .005
    assert result["components"][0]["cost"] is None
    assert result["components"][1]["cost"] is None
    assert result["profiles"][0]["cost"] is None
    assert result["populations"][0]["per_input_hour"] is None


def test_subscription_equivalent_is_not_actual_and_gemini_stays_separate(tmp_path):
    spec = specification()
    spec["windows"][0]["profile"] = "PP2"
    for component in spec["components"]:
        component["profile"] = "PP2"
    spec["components"][0]["treatment"] = "subscription"
    spec["components"][0]["provider"] = "chatgpt"
    spec["sources"][1]["provider"] = "chatgpt"
    log = tmp_path / "subscription.log"
    log.write_text((FIXTURES / "pp.log").read_text(encoding="utf-8").replace("provider=openrouter", "provider=chatgpt"), encoding="utf-8")
    spec["sources"][1]["path"] = str(log)
    spec["price_tables"][0]["provider"] = "chatgpt"
    result = report(tmp_path, spec)
    subscription, asr = result["components"]
    assert subscription["cost"] is None
    assert subscription["known_subtotal"] is None
    assert subscription["status"] == "subscription"
    assert subscription["supplementary_api_equivalent"]["known_subtotal"] == pytest.approx(.00235)
    assert asr["cost"] is None
    assert asr["calculated_cost"] == pytest.approx(.001)
    assert result["profiles"][0]["cost"] is None
    assert result["profiles"][0]["known_numeric_subtotal"] is None
    assert result["profiles"][0]["calculated_subtotal"] == pytest.approx(.001)


@pytest.mark.parametrize("eligible", [False, True])
def test_free_requires_observed_eligible_coverage_and_keeps_limit_timing(tmp_path, eligible):
    spec = provider_spec(tmp_path, [])
    spec["windows"][0]["profile"] = "PP3"
    component = spec["components"][0]
    component.update(profile="PP3", provider="index", treatment="free", access={
        "observed_eligible": eligible, "window_ids": ["pilot-chunk"], "evidence": "synthetic eligibility observation",
        "quota": {"unit": "requests", "observed_limit": 3}, "limit_status": "reached", "scope_start": "2026-10-20T12:00:00Z", "reached_at": "2026-10-20T12:02:30Z"})
    result = report(tmp_path, spec)
    assert result["components"][0]["cost"] == (0 if eligible else None)
    assert result["components"][0]["access"]["minutes_to_limit"] == 2.5
    assert result["components"][0]["access"]["quota"]["observed_limit"] == 3


def test_missing_tokens_or_actual_model_stay_unknown(tmp_path):
    spec = specification()
    text = (FIXTURES / "pp.log").read_text(encoding="utf-8").replace("actual_model=synthetic/gemma", "actual_model=none").replace("cached_input_tokens=200", "cached_input_tokens=none")
    path = tmp_path / "unknown.log"
    path.write_text(text, encoding="utf-8")
    spec["sources"][1]["path"] = str(path)
    result = report(tmp_path, spec)
    internal = result["components"][0]["all_bound_internal_usage"]
    assert internal["calls"] == 2
    assert internal["cached_tokens"]["observed_calls"] == 1
    attempts = [item for item in result["records"] if item.get("event") == "attempt_end"]
    assert all(item["model"] is None and item["requested_model"] == "synthetic/requested" for item in attempts)
    assert all(item["attribution"]["status"] == "conditional" for item in attempts)
    assert result["components"][0]["reconciliation"]["difference_provider_minus_internal"] is None


def test_preserves_failed_and_cancelled_provider_attempts(tmp_path):
    spec = specification()
    text = (FIXTURES / "pp.log").read_text(encoding="utf-8").replace("status=success", "status=error", 1)
    text += "2026-10-20 21:00:04.000 [INFO] pid=42 puripuly_heart.session: [Diagnostic][LlmLatency] attempt_end request_id=1 attempt=1 provider=openrouter model=synthetic/requested actual_model=synthetic/gemma status=cancelled attempt_ms=2000 network_ms=2000 input_tokens=none output_tokens=none cached_input_tokens=none reasoning_tokens=none\n"
    path = tmp_path / "attempts.log"
    path.write_text(text, encoding="utf-8")
    spec["sources"][1]["path"] = str(path)
    result = report(tmp_path, spec)
    summary = result["components"][0]["all_bound_internal_usage"]
    assert summary["calls"] == 3 and summary["logical_requests"] == 2
    assert summary["statuses"] == {"success": 1, "error": 1, "cancelled": 1}
    assert result["components"][0]["internal_calculation"]["priced_calls"] == 2


def test_real_manifest_missing_cost_uses_actual_40s_not_60s_attempt(tmp_path):
    result = report(tmp_path, specification("real-missing-spec.json"))
    assert result["synthetic"] is False
    assert len(result["attempts"]) == 4
    assert [item["replayed_seconds"] for item in result["attempts"]] == [None, None, 10, 40]
    chunk = next(item for item in result["windows"] if item["kind"] == "chunk")
    assert (timestamp(chunk["end"]) - timestamp(chunk["start"])).total_seconds() == 40
    assert chunk["population"] == "development"
    assert "anchor" in chunk["window_basis"]
    assert chunk["clock_session"] == "5ebe4e0a8c9f40a2b48f6780ec3b49c7"
    assert all(item["cost"] is None for item in result["components"])
    assert result["profiles"][0]["cost"] is None
    assert result["common_report"] is None and result["populations"] == []
    assert result["status"] == "historical_evidence_only"
    assert result["consumption_summaries"][0]["known_subtotal"] == pytest.approx(.1151360)
    assert result["consumption_summaries"][1]["known_subtotal"] == pytest.approx(.1444215)
    assert all(row["total"] is None for row in result["consumption_summaries"])
    assert any(item["kind"] == "capture_export_provenance" for item in result["provenance"])


def test_rejects_input_overwrite_without_changing_bytes(tmp_path):
    spec = specification()
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    original = path.read_bytes()
    with pytest.raises(ValueError, match="overwrite"):
        derive(path, path)
    assert path.read_bytes() == original


@pytest.mark.parametrize("mutation,match", [
    (lambda spec: spec["windows"][0].update(start="2026-10-20T12:00:00"), "timezone"),
    (lambda spec: spec["sources"][0].update(permitted=False), "permitted"),
    (lambda spec: spec["sources"][0].pop("selection_evidence"), "selection"),
    (lambda spec: spec["sources"][1].update(timezone="local"), "UTC offset"),
    (lambda spec: spec["price_tables"][0].pop("input_includes_cached"), "containment"),
    (lambda spec: spec["components"][0].update(treatment="free"), "governing"),
])
def test_rejects_unsupported_claims(tmp_path, mutation, match):
    spec = specification()
    mutation(spec)
    with pytest.raises(ValueError, match=match):
        report(tmp_path, spec)
