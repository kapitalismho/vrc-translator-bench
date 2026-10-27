from __future__ import annotations

import copy
import json
from decimal import Decimal

import pytest

from bench.cost_inputs import normalize
from bench.costs import calculate
from bench.storage import digest
from test_costs import FIXTURES, provider_spec, report, row, specification


def test_token_containment_and_distinct_reasoning_price(tmp_path):
    spec = specification()
    spec["price_tables"][0]["rates"]["reasoning"] = 4
    result = report(tmp_path, spec)
    calculation = result["components"][0]["internal_calculation"]
    assert calculation["known_subtotal"] == pytest.approx(.00245)
    assert calculation["records"][0]["billed_units"] == {"input": 800, "cached": 200, "output": 250, "reasoning": 50}


def test_contained_details_without_discount_are_charged_once(tmp_path):
    spec = specification()
    spec["price_tables"][0]["rates"].pop("cached")
    result = report(tmp_path, spec)
    calculation = result["components"][0]["internal_calculation"]
    assert calculation["known_subtotal"] == pytest.approx(.0025)
    assert calculation["records"][0]["billed_units"] == {"input": 1000, "output": 300}


def test_noncontained_categories_are_additive_once(tmp_path):
    spec = specification()
    spec["price_tables"][0].update(input_includes_cached=False, output_includes_reasoning=False)
    result = report(tmp_path, spec)
    assert result["components"][0]["internal_calculation"]["known_subtotal"] == pytest.approx(.00265)


@pytest.mark.parametrize("change,expected", [
    ({"input_tokens": 100, "cached_tokens": 200}, "containment"),
    ({"reasoning_tokens": None}, "Missing token"),
    ({"model": None}, "dated model"),
    ({"start": "2026-10-21T00:00:00Z"}, "dated model"),
])
def test_unpriceable_usage_stays_unknown(change, expected):
    spec = specification()
    selected = {"model": "synthetic/gemma", "start": "2026-10-20T12:00:00Z", "input_tokens": 1000,
                "cached_tokens": 200, "output_tokens": 300, "reasoning_tokens": 50, **change}
    usage = normalize(selected, spec["sources"][1], 1)
    result = calculate(usage, spec["price_tables"])
    assert result["value"] is None
    assert expected in result["reason"]


def test_no_replay_duration_substitution_for_asr():
    spec = specification()
    usage = {"provider": "gemini", "model": "synthetic/transcribe", "start": "2026-10-20T12:00:00Z",
             "audio_seconds": None, "replay_seconds": Decimal(20)}
    result = calculate(usage, spec["price_tables"])
    assert result["value"] is None
    assert "replay duration" in result["reason"]


def test_no_request_id_dedup_only_repeated_source_rows(tmp_path):
    spec = provider_spec(tmp_path, [row(request_id=None), row(request_id=None)])
    spec["sources"].append({**copy.deepcopy(spec["sources"][0]), "id": "repeated-source"})
    result = report(tmp_path, spec)
    assert result["components"][0]["provider_records"] == 2
    assert result["components"][0]["cost"] == pytest.approx(.006)


def test_process_session_namespace_keeps_counter_reuse(tmp_path):
    spec = specification()
    second_log = tmp_path / "second-process.log"
    second_log.write_text((FIXTURES / "pp.log").read_text(encoding="utf-8").replace("pid=42", "pid=43"), encoding="utf-8")
    spec["sources"].append({**copy.deepcopy(spec["sources"][1]), "id": "other-session", "session": "second-process-session",
                            "process_id": 43, "path": str(second_log)})
    result = report(tmp_path, spec)
    assert result["components"][0]["all_bound_internal_usage"]["calls"] == 4
    assert result["components"][0]["all_bound_internal_usage"]["logical_requests"] == 4


def test_wrong_process_logs_are_not_ingested(tmp_path):
    spec = specification()
    spec["sources"][1]["process_id"] = 100
    result = report(tmp_path, spec)
    assert result["components"][0]["internal_usage"]["calls"] == 0
    assert result["components"][0]["reconciliation"]["difference_provider_minus_internal"] is None


def test_missing_currency_is_not_assumed_usd(tmp_path):
    spec = provider_spec(tmp_path, [row()])
    spec["sources"][0].pop("currency")
    result = report(tmp_path, spec)
    assert result["components"][0]["cost"] is None
    assert result["components"][0]["known_subtotal"] is None


def test_invalid_interrupted_attempt_keeps_actual_partial_replay(tmp_path):
    trace = tmp_path / "attempt.jsonl"
    rows = [
        {"record": "attempt_start", "wall": "2026-10-20T12:00:00Z", "t_ns": 1000000000, "clock_session": "test-session"},
        {"record": "source_playback", "playback_dac_start_ns": 2000000000, "playback_end_ns": 42000000000,
         "clock_session": "test-session", "actual_dac_observed": False},
        {"record": "audio_callback", "source_frame": 0, "source_frames": 48000, "dac_t_ns": 2000000000},
        {"record": "audio_callback", "source_frame": 48000, "source_frames": 48000, "dac_t_ns": 3000000000},
    ]
    trace.write_text("\n".join(json.dumps(item) for item in rows), encoding="utf-8")
    manifest = {"run": "interrupted-source-run", "plan": {"stages": [{"wave": "test-wave", "chunk": "test-chunk", "sample_rate": 48000, "duration_seconds": 40}]},
                "work": [{"id": 1, "stage": 0, "profile": "VRCS2", "kind": "chunk", "outcome": "invalid"}],
                "attempts": [{"id": 1, "work_id": 1, "number": 1, "resumed": 0, "state": "invalid", "reason": "interrupted",
                              "start_wall": "2026-10-20T12:00:00Z", "end_wall": "2026-10-20T12:00:05Z", "trace": trace.name, "checksum": digest(trace)}]}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    spec = {"schema_version": 2, "mode": "historical_evidence_only", "revision": {"id": "interrupted"},
            "synthetic": True, "manifests": [{"id": "interrupted", "path": str(path), "populations": {"0": "development"}}],
            "components": [{"id": "VRCS2.translation", "profile": "VRCS2", "provider": "openrouter", "treatment": "provider",
                            "coverage": {"window_ids": ["interrupted.attempt-1"], "complete": False, "evidence": "Synthetic interrupted run"}}]}
    result = report(tmp_path, spec)
    assert result["attempts"][0]["run"] == "interrupted-source-run"
    assert result["attempts"][0]["state"] == "invalid" and result["attempts"][0]["reason"] == "interrupted"
    assert result["attempts"][0]["replayed_seconds"] == 2
    assert result["windows"][0]["start"] == "2026-10-20T12:00:01+00:00"
    assert result["windows"][0]["end"] == "2026-10-20T12:00:03+00:00"
    assert not result["populations"]
    assert result["components"][0]["cost"] is None


def test_missing_frozen_timeline_is_unknown_not_zero(tmp_path):
    spec = specification()
    spec["timelines"] = []
    result = report(tmp_path, spec)
    assert result["populations"][0]["logical_episode_seconds"] is None
    assert result["populations"][0]["per_input_hour"] is None
    assert result["populations"][0]["calculated_per_input_hour"] is None


def test_recognition_terminal_bytes_do_not_become_asr_usage(tmp_path):
    spec = specification()
    spec["sources"] = spec["sources"][:2]
    result = report(tmp_path, spec)
    assert result["components"][1]["cost"] is None
    assert result["components"][1]["internal_usage"]["audio_seconds"]["observed_calls"] == 0
    assert result["components"][1]["internal_usage"]["audio_seconds"]["known"] is None
    assert result["profiles"][0]["cost"] is None


def test_possible_unidentified_request_duplicates_across_different_exports_are_unknown(tmp_path):
    spec = provider_spec(tmp_path, [row(request_id=None)])
    path = tmp_path / "reformatted-export.json"
    path.write_text(json.dumps([row(request_id=None)], indent=2), encoding="utf-8")
    spec["sources"].append({**copy.deepcopy(spec["sources"][0]), "id": "different-export", "path": str(path)})
    result = report(tmp_path, spec)
    assert len(result["records"]) == 2
    assert all("Possible duplicate" in item["exclusion"] for item in result["records"])
    assert result["components"][0]["cost"] is None


def test_actual_upstream_provider_can_constrain_without_gateway_substitution(tmp_path):
    spec = provider_spec(tmp_path, [row()])
    spec["components"][0]["upstream_providers"] = ["synthetic-upstream"]
    result = report(tmp_path, spec)
    assert result["records"][0]["upstream_provider"] is None
    assert result["records"][0]["attribution"]["status"] == "conditional"
    assert result["components"][0]["cost"] is None
    spec["sources"][0]["constants"] = {"upstream_provider": "synthetic-upstream"}
    result = report(tmp_path, spec)
    assert result["components"][0]["cost"] == .003


def test_audio_interval_duration_is_independent_of_request_time(tmp_path):
    spec = specification()
    data = json.loads((FIXTURES / "submitted-audio.json").read_text(encoding="utf-8"))
    # Ten audio seconds can be submitted in an instant; wall request length is not audio length.
    data[0]["submitted_at"] = "2026-10-20T12:00:50.000001Z"
    path = tmp_path / "audio.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    spec["sources"][2]["path"] = str(path)
    result = report(tmp_path, spec)
    asr = result["components"][1]
    assert asr["all_bound_internal_usage"]["audio_seconds"]["known"] == 10
    assert asr["internal_usage"]["audio_seconds"]["known"] == 6
    # In-window calculation survives, but unmatched bound usage defeats complete coverage.
    assert asr["internal_calculation"]["known_subtotal"] == pytest.approx(.0006)
    assert asr["cost"] is None
    assert result["profiles"][0]["cost"] is None


def test_vad_bounds_cannot_be_replaced_by_request_wall_elapsed(tmp_path):
    spec = specification()
    spec["sources"][2]["fields"].pop("audio_start")
    with pytest.raises(ValueError, match="independent source-audio"):
        report(tmp_path, spec)


def test_coarse_wave_amount_needs_scope_evidence(tmp_path):
    spec = provider_spec(tmp_path, [row(end="2026-10-20T13:00:00Z")], granularity="hour")
    spec["sources"][0]["scope"] = {"run": "synthetic-pilot", "wave": "synthetic-wave"}
    result = report(tmp_path, spec)
    assert result["coarse_costs"][0]["known_export_amount"] == .003
    assert result["coarse_costs"][0]["cost"] is None


def test_synthetic_sources_cannot_be_relabelled_as_real(tmp_path):
    spec = specification()
    spec["synthetic"] = False
    result = report(tmp_path, spec)
    assert result["synthetic"] is True
