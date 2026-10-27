from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

import bench.quality as quality
from bench.history import event_sha256
from bench.quality import StageJudge, evaluate, judge_role
from bench.quality_prompts import identity, validate
from bench.quality_store import QualityStore
from bench.storage import digest

DATA = {"source_language": "en", "target_language": "zh", "source": "Do not buy 12 tickets.",
        "output": "不要买十二张票。", "context": []}
BINDINGS = {"native_endpoint": "task-owned-translation", "endpoint_stage": "translation_output",
            "source_binding": "task-owned-small-text", "native_semantics": "single complete output"}


class ControlledTransport:
    def __init__(self, outputs=None, model="gpt-6-astra", status="completed"):
        self.outputs = outputs or {}
        self.model, self.status = model, status
        self.requests = []
        self.provenance = {"kind": "synthetic-command", "synthetic": True, "route": "controlled synthetic"}

    def call(self, request, call):
        self.requests.append(request)
        stage = request["stage"]
        data = json.loads(request["messages"][1]["content"].split("Untrusted episode data (JSON):\n", 1)[1])
        if callable(self.outputs):
            content = self.outputs(stage, data)
        else:
            content = self.outputs.get(stage, {"errors": []} if stage == "errors" else {"score": 96.5} if stage == "score" else {
                "status": "met", "evidence": [{"side": "output", "text": data["output"], "occurrence": 1}],
                "reversal": False, "correction": False, "reason": "Controlled affirmative fixture, not semantic validation"})
        return {"status": self.status, "actual_model": self.model,
                "model_identity_evidence": {"synthetic": True, "source": "controlled response"},
                "content": content, "raw": {"controlled": True, "call_id": call}}


def install(monkeypatch, transport):
    monkeypatch.setattr(quality, "load_transport", lambda path: transport)


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return {"path": path.name, "sha256": digest(path)}


def event(text="不要买十二张票。", seconds=1, **extra):
    return {"record": "native_output_event", "profile": "TEST", "episode_id": "ep", "attempt": 1,
            "pass_id": "A", "input_channel": "peer", "role": "A", "target_language": "zh",
            "clock_session": "clock", "native_endpoint": "task-owned-output", "endpoint_stage": "translation_output",
            "translated_text": text, "collector_received_monotonic": round(seconds * 1e9),
            "event_time_interval": {"earliest_ns": round(seconds * 1e9), "latest_ns": round(seconds * 1e9), "clock_session": "clock"},
            "clock_mapping": {"evidence": ["controlled exact local clock"]},
            "raw_evidence": {"sha256": "task-owned-raw", "profile": "SECRET_PROFILE", "price": 4, "model": "SECRET_MODEL"}, **extra}


def interpretation(events, index, operation="append", target=None):
    result = {"event_index": index, "event_sha256": event_sha256(events[index]), "operation": operation,
              "rule": {"id": "controlled-semantic-operation", "description": "Fixture-author established native operation",
                       "evidence": ["task-owned deterministic history fixture"]}}
    if target is not None:
        result["replaces_event_index"] = target
    return result


def spec_fixture(tmp_path, *, events=None, outcome=None, clock=True, units=None, kind="P1", interpretations=None):
    events = [event()] if events is None else events
    units = units or [{"id": "u1", "role": "A", "text": DATA["source"], "start_ns": 0,
                       "end_ns": 1_000_000_000, "citations": ["task-owned original text"],
                       "uncertainty": {"review": "controlled exact source"}}]
    cps = [{"id": "cpA", "role": "A", "evidence_end_seconds": 1,
            "required_concepts": ["Do not buy twelve tickets"], "allowed_paraphrase_concepts": ["equivalent meaning"]}]
    if kind == "T1":
        cps.append({"id": "cpB", "role": "B", "evidence_end_seconds": 1,
                    "required_concepts": ["Acknowledge"], "allowed_paraphrase_concepts": ["equivalent meaning"]})
    reference = {"id": "ep", "source_units": units, "semantic_checkpoints": cps}
    reference_binding = dump(tmp_path / "reference.json", reference)
    history_binding = dump(tmp_path / "history.json", events)
    selection = {"history": history_binding,
                 "scope": {"episode": "ep", "profile": "TEST", "attempt": 1, "pass_id": "A", "channel": "peer"},
                 "interpretations": interpretations if interpretations is not None else [interpretation(events, i) for i in range(len(events))],
                 "outcome": outcome or {"state": "done", "role_outcomes": {"A": {"status": "output_observed"}}}}
    if clock:
        selection["clock"] = {"origin_ns": 0, "horizon_ns": 16_000_000_000, "clock_session": "clock",
                              "evidence": ["controlled exact input origin and complete horizon"]}
    spec = {"schema_version": 1, "protocol_revision": "task-owned-r4", "measurements_ended": True,
            "expected_model": "gpt-6-astra", "judge_kind": "synthetic-command",
            "episodes": [{"episode_id": "ep", "source_case_id": "ep", "language_pair": "en-zh", "kind": kind,
                          "reference": reference_binding, "cost_binding_id": "logical-input-ep"}],
            "populations": [{"profile": "TEST", "measurement_condition": "peer/simultaneous",
                             "roles": [{"episode_id": "ep", "role": "A", "selection": selection}]}]}
    path = tmp_path / "spec.json"
    dump(path, spec)
    return path, spec


def save_run(path, spec, manifest, records):
    trace = path.parent / manifest["attempts"][0]["trace"]
    trace.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
    manifest["attempts"][0]["checksum"] = digest(trace)
    spec["populations"][0]["roles"][0]["selection"]["run_manifest"] = dump(path.parent / "manifest.json", manifest)
    dump(path, spec)


def run_fixture(tmp_path, *, events=None, dac_seconds=(10, 10.5, 11, 11.5)):
    events = [] if events is None else events
    path, spec = spec_fixture(tmp_path, events=events, clock=False)
    source = {"record": "source_playback", "profile": "TEST", "episode_id": "ep", "attempt": 1, "pass_id": "A",
              "role": "A", "input_channel": "peer", "clock_session": "clock", "actual_dac_observed": True,
              "audio_sha256": "controlled-source-audio", "playback_dac_start_ns": 10_000_000_000,
              "input_origin_ns": 10_250_000_000,
              "calibration": {"status": "measured", "offset_ns": 250_000_000, "record_sha256": "controlled-calibration",
                              "raw_evidence": {"path": "controlled-calibration.npz", "sha256": "controlled-probe"}}}
    callbacks = [{"record": "audio_callback", "input_channel": "peer", "source_frame": i * 500,
                  "source_frames": 500, "dac_t_ns": round(seconds * 1e9), "status": ""}
                 for i, seconds in enumerate(dac_seconds)]
    common_end = round((dac_seconds[-1] + 0.5) * 1e9)
    horizon = common_end + 250_000_000 + 15_000_000_000
    records = [{"record": "attempt_start"}, source, *callbacks,
               {"record": "role_horizon", "input_channel": "peer", "common_last_speech_seconds": 2,
                "common_speech_end_dac_ns": common_end, "calibration_offset_ns": 250_000_000,
                "role_horizon_ns": horizon, "synthetic": False}, *events]
    detail = {"opportunity_established": True, "continuity_established": {"app": True, "input": True, "collector": True},
              "synthetic": False, "role_outcomes": {"A": {"status": "output_observed" if events else "product_no_output"}},
              "output_windows_ns": {"peer": [10_250_000_000, horizon]}, "common_last_speech_seconds": 2,
              "role_horizons_ns": {"peer": horizon}, "observation_deadline_ns": horizon,
              "observation_end_ns": horizon + 5_000_000_000,
              "playback": {"peer": {"complete": True, "end_ns": common_end}}}
    manifest = {"schema_version": 2, "plan": {"episodes": [{"episode_id": "ep", "roles": {"A": {
                    "audio_sha256": "controlled-source-audio", "sample_rate": 1000, "frames": 2000}}}],
                "profiles": [{"id": "TEST", "routes": {"peer": {"calibration": copy.deepcopy(source["calibration"])}}}],
                "passes": [{"episode_id": "ep", "pass_id": "A", "profiles": ["TEST"], "common_last_speech_seconds": 2}]},
                "work": [{"id": 1, "profile": "TEST", "episode_id": "ep", "pass_id": "A",
                          "outcome": "output_observed" if events else "product_no_output"}],
                "attempts": [{"id": 1, "work_id": 1, "state": "done", "reason": None, "trace": "attempt.jsonl",
                              "detail": detail}], "streams": []}
    spec["populations"][0]["roles"][0]["selection"] = {
        "run_manifest": {}, "attempt_id": 1, "pass_id": "A",
        "interpretations": [interpretation(records, i) for i, row in enumerate(records) if row.get("record") == "native_output_event"]}
    save_run(path, spec, manifest, records)
    return path, spec, manifest, records


def role_result(report):
    return report["populations"][0]["role_results"][0]


@pytest.mark.parametrize("field", ["run", "wave"])
def test_standalone_execution_identity_selects_output_without_losing_cost_binding(tmp_path, field):
    rows = [event("不要买十二张票。", run="selected-run", wave="selected-wave"),
            event("UNRELATED OUTPUT", run="selected-run", wave="selected-wave")]
    rows[1][field] = "another-execution"
    path, spec = spec_fixture(tmp_path, events=rows)
    selection = spec["populations"][0]["roles"][0]["selection"]
    selection["scope"].update(run="selected-run", wave="selected-wave")
    dump(path, spec)
    history_bytes = (tmp_path / "history.json").read_bytes()

    report = evaluate(path, tmp_path / "result.json")

    result = role_result(report)
    assert result["history"]["text"] == "不要买十二张票。"
    assert result["history"]["excluded_events"][0]["reason"] == "scope_" + field
    assert result["provenance"]["selection"]["scope"] == selection["scope"]
    assert (tmp_path / "history.json").read_bytes() == history_bytes


def test_two_stages_are_fresh_and_retain_durable_inputs_raw_results(monkeypatch, tmp_path):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    report = judge_role(DATA, store_path=tmp_path / "store", transport_path="controlled", measurements_ended=True, bindings=BINDINGS)
    assert report["status"] == "complete"
    assert report["quality"]["score"] == 96.5
    assert [r["stage"] for r in transport.requests] == ["errors", "score"]
    assert all(len(r["messages"]) == 2 for r in transport.requests)
    assert '"errors":[]' in transport.requests[1]["messages"][1]["content"]
    store = QualityStore(tmp_path / "store")
    try:
        calls = store.history()
        assert [c["state"] for c in calls] == ["completed", "completed"]
        assert all(c["raw"]["raw"]["controlled"] for c in calls)
        assert calls[0]["input_hash"] != calls[1]["input_hash"]
        for call in calls:
            job = store.get("r4_job:" + call["prompt_hash"])
            assert job["inputs"]["data"] == DATA
            assert job["inputs"]["bindings"] == BINDINGS
            assert identity(call["result"]) == report["quality"][call["job"].split(":")[0] + "_stage"]["result_hash"]
    finally:
        store.close()


@pytest.mark.parametrize("output,category,score", [
    ("十二张票不要买。", None, 98), ("不要买十二张票。", None, 77.125), ("买票。", "accuracy/omission", 30),
    ("买十二张票。", "accuracy/mistranslation", 20), ("不要买二十张票。", "accuracy/mistranslation", 25),
    ("Do not buy 12 tickets.", "accuracy/untranslated text", 15),
])
def test_controlled_contrast_results_preserved_not_claimed_semantic_discrimination(monkeypatch, tmp_path, output, category, score):
    data = {**DATA, "output": output}
    errors = [] if category is None else [{"category": category, "severity": "major",
        "quote": {"side": "source" if category == "accuracy/omission" else "output",
                  "text": DATA["source"] if category == "accuracy/omission" else output, "occurrence": 1},
        "explanation": "Controlled expected category; not a real model discrimination claim"}]
    transport = ControlledTransport({"errors": {"errors": errors}, "score": {"score": score}})
    install(monkeypatch, transport)
    report = judge_role(data, store_path=tmp_path / "store", transport_path="controlled", measurements_ended=True)
    assert report["quality"]["score"] == score
    assert report["quality"]["errors_stage"]["result"]["errors"] == errors
    assert report["quality"]["score_source"] == "controlled_synthetic"


@pytest.mark.parametrize("text,occurrence", [("not present", 1), ("不要", 2), ("不要", True), ("", 1)])
def test_invalid_exact_quote_or_occurrence_stops_score_without_repair(monkeypatch, tmp_path, text, occurrence):
    errors = {"errors": [{"category": "accuracy/mistranslation", "severity": "major",
        "quote": {"side": "output", "text": text, "occurrence": occurrence}, "explanation": "controlled invalid quote"}]}
    transport = ControlledTransport({"errors": errors})
    install(monkeypatch, transport)
    report = judge_role(DATA, store_path=tmp_path / "store", transport_path="controlled", measurements_ended=True)
    assert report["quality"]["status"] == "invalid_response"
    assert report["quality"]["score"] is None
    assert len(transport.requests) == 1
    assert report["quality"]["score_stage"] is None


def test_quote_occurrences_are_exact_nonoverlapping_and_not_normalized():
    data = {**DATA, "output": "票 票 票"}
    value = {"errors": [{"category": "accuracy/addition", "severity": "minor",
             "quote": {"side": "output", "text": "票", "occurrence": 3}, "explanation": "third exact occurrence"}]}
    assert validate("errors", value, data) == value
    with pytest.raises(ValueError, match="not repaired"):
        validate("errors", value, {**data, "output": "票 票"})


def test_cache_separates_stage_context_native_semantics_endpoint_model_and_errors(monkeypatch, tmp_path):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    with StageJudge(tmp_path / "store", transport_path="controlled", measurements_ended=True) as executor:
        first = executor.run("errors", DATA, bindings=BINDINGS)
        same = executor.run("errors", DATA, bindings=BINDINGS)
        assert same["cached"] and same["call_id"] == first["call_id"]
        changed = [executor.run("errors", {**DATA, "context": ["changed audible source"]}, bindings=BINDINGS),
                   executor.run("errors", {**DATA, "output": "different output"}, bindings=BINDINGS),
                   executor.run("errors", DATA, bindings={**BINDINGS, "native_semantics": "changed replacement"}),
                   executor.run("errors", DATA, bindings={**BINDINGS, "endpoint_stage": "other-stage"}),
                   executor.run("score", DATA, bindings=BINDINGS, errors={"errors": []}),
                   executor.run("score", DATA, bindings=BINDINGS, errors={"errors": [{"different": "validated upstream result"}]})]
        assert len({first["prompt_hash"], *(r["prompt_hash"] for r in changed)}) == 7
    count = len(transport.requests)
    offline = judge_role(DATA, store_path=tmp_path / "store", judge_kind="synthetic-command", bindings=BINDINGS)
    assert offline["quality"]["errors_stage"]["cached"]
    assert len(transport.requests) == count
    other_model = judge_role(DATA, store_path=tmp_path / "store", expected_model="gpt-6-astra-2026-10-27",
                             judge_kind="synthetic-command", bindings=BINDINGS)
    assert other_model["quality"]["status"] == "not_judged"


@pytest.mark.parametrize("state", ["unresolved", "quota", "failed"])
def test_uncertain_and_failed_calls_retained_never_redispatched(monkeypatch, tmp_path, state):
    transport = ControlledTransport(status=state)
    install(monkeypatch, transport)
    for _ in range(2):
        report = judge_role(DATA, store_path=tmp_path / "store", transport_path="controlled", measurements_ended=True)
        assert report["quality"]["status"] == state
    assert len(transport.requests) == 1
    assert len(report["calls"]) == 1


def test_running_call_recovery_and_model_mismatch_block_further_dispatch(monkeypatch, tmp_path):
    transport = ControlledTransport(model="different-model")
    install(monkeypatch, transport)
    with StageJudge(tmp_path / "store", transport_path="controlled", measurements_ended=True) as executor:
        mismatch = executor.run("errors", DATA, bindings=BINDINGS)
        assert mismatch["status"] == "model_mismatch"
        blocked = executor.run("errors", {**DATA, "source": "changed"}, bindings=BINDINGS)
        assert blocked["status"] == "blocked"
        job = {"id": "running-control", "input_hash": "x", "prompt_hash": "y"}
        executor.store.start(job, "gpt-6-astra", {"synthetic": True})
    with StageJudge(tmp_path / "store") as executor:
        assert executor.store.history()[-1]["state"] == "unresolved"
    assert len(transport.requests) == 1


def test_dispatch_requires_measurements_ended_and_activity_lock(monkeypatch, tmp_path):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    with pytest.raises(ValueError, match="measurements_ended"):
        judge_role(DATA, store_path=tmp_path / "store", transport_path="controlled")
    from bench.activity import exclusive_activity
    with exclusive_activity():
        with pytest.raises(ValueError, match="active"):
            judge_role(DATA, store_path=tmp_path / "store", transport_path="controlled", measurements_ended=True)
    assert transport.requests == []


def test_historical_store_not_adopted(tmp_path):
    old = QualityStore(tmp_path / "store")
    old.start({"id": "legacy", "input_hash": "x", "prompt_hash": "y"}, "old", {})
    old.close()
    with pytest.raises(ValueError, match="Historical"):
        with StageJudge(tmp_path / "store"):
            pass


def test_no_provider_evaluate_preserves_planned_roles_weights_and_conditions(tmp_path):
    path, spec = spec_fixture(tmp_path, kind="T1")
    spec["populations"].append({"profile": "OTHER", "measurement_condition": "self/split", "roles": []})
    dump(path, spec)
    report = evaluate(path, tmp_path / "report.json")
    assert report["status"] == "incomplete"
    assert report["kind"] == "episode_quality"
    assert report["calls"] == []
    assert report["planned_episodes"][0]["checkpoint_ids"] == {"A": ["cpA"], "B": ["cpB"]}
    assert report["planned_episodes"][0]["cost_binding_id"] == "logical-input-ep"
    roles = report["populations"][0]["role_results"]
    assert roles[1]["quality"]["status"] == "missing_attempt"
    assert roles[1]["checkpoints"][0]["status"] == "unknown"
    assert len(report["populations"]) == 2
    assert report["populations"][0]["aggregate"]["quality"]["missing_weight"] == 1


@pytest.mark.parametrize("proven,expected", [(True, "no_output"), (False, "unknown")])
def test_no_output_is_protocol_zero_only_with_complete_opportunity(tmp_path, proven, expected):
    outcome = {"state": "done", "role_outcomes": {"A": {"status": "product_no_output"}},
               "opportunity": {"input_complete": proven, "app_opportunity": True, "observation_complete": True}}
    path, _ = spec_fixture(tmp_path, events=[], outcome=outcome)
    report = evaluate(path, tmp_path / "report.json")
    role = role_result(report)
    assert role["quality"]["status"] == expected
    assert role["quality"]["score"] == (0 if proven else None)
    assert role["checkpoints"][0]["status"] == ("unmet" if proven else "unknown")
    assert report["calls"] == []
    if proven:
        assert role["quality"]["score_source"] == "protocol"
        assert role["quality"]["errors_stage"] is None


def test_early_harness_interruption_invalid_not_zero_or_judged(monkeypatch, tmp_path):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    path, _ = spec_fixture(tmp_path, outcome={"state": "invalid", "reason": "early stop", "opportunity_established": False})
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    assert role_result(report)["quality"]["status"] == "invalid"
    assert role_result(report)["quality"]["score"] is None
    assert transport.requests == []


def test_checkpoint_prefixes_no_future_or_metadata_leak_and_fresh_calls(monkeypatch, tmp_path):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    units = [{"id": "u1", "role": "A", "text": DATA["source"], "start_ns": 0, "end_ns": 1_000_000_000,
              "citations": [{"source": "SECRET_PROFILE"}], "uncertainty": {"content": "original marker retained"}},
             {"id": "u2", "role": "B", "text": "FUTURE_ANSWER", "start_ns": 3_000_000_000, "end_ns": 4_000_000_000,
              "citations": ["original other speaker"], "context_only": True}]
    path, _ = spec_fixture(tmp_path, units=units)
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    calls = [r for r in transport.requests if r["stage"] == "checkpoint"]
    assert len(calls) == 5
    first = calls[0]["messages"][1]["content"]
    assert "FUTURE_ANSWER" not in first
    assert "SECRET_PROFILE" not in first and "SECRET_MODEL" not in first
    later = calls[-1]["messages"][1]["content"]
    assert "FUTURE_ANSWER" in later and '"scored":false' in later
    assert "original marker retained" in first
    cp = role_result(report)["checkpoints"][0]
    assert cp["first_met"] == [0, 0]
    assert [o["offset_seconds"] for o in cp["observations"]] == [0, 2, 5, 10, 15]


def test_quality_survives_unmapped_producer_clock_but_wait_unknown(monkeypatch, tmp_path):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    rows = [event(event_time_interval=None, clock_mapping=None)]
    path, _ = spec_fixture(tmp_path, events=rows)
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    assert role_result(report)["quality"]["status"] == "judged"
    assert role_result(report)["checkpoints"][0]["status"] == "unknown"
    assert [r["stage"] for r in transport.requests] == ["errors", "score"]


def test_wrong_revision_preserves_first_met_clear_is_not_reversal(monkeypatch, tmp_path):
    rows = [event(seconds=1), event("买十二张票。", seconds=4), event("不要买十二张票。", seconds=8), event("", seconds=12)]
    rules = [interpretation(rows, 0), interpretation(rows, 1, "replace", 0),
             interpretation(rows, 2, "replace", 1), interpretation(rows, 3, "clear")]
    def decisions(stage, data):
        if stage == "errors":
            return {"errors": []}
        if stage == "score":
            return {"score": 99}
        wrong = data["output"] == "买十二张票。"
        operations = [r["operation"] for r in data["output_history"]]
        return {"status": "unmet" if wrong else "met", "evidence": [] if wrong else [
            {"side": "output", "text": data["output"], "occurrence": 1}], "reversal": wrong or operations[-1] == "clear",
            "correction": not wrong and operations[-1] == "replace", "reason": "Controlled revision decision"}
    transport = ControlledTransport(decisions)
    install(monkeypatch, transport)
    path, _ = spec_fixture(tmp_path, events=rows, interpretations=rules)
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    cp = role_result(report)["checkpoints"][0]
    assert cp["first_met"] == [0, 0]
    assert cp["status"] == "met"
    assert cp["later_reversals_seconds"] == [5]
    assert cp["later_corrections_seconds"] == [10]
    assert cp["observations"][-1]["status"] == "met"
    assert cp["observations"][-1]["reversal"] is False
    assert cp["observations"][-1]["judgment"]["result"]["reversal"] is True


def test_checksum_and_unknown_reference_fail_closed(tmp_path):
    path, spec = spec_fixture(tmp_path)
    spec["episodes"][0]["reference"]["sha256"] = "wrong"
    dump(path, spec)
    with pytest.raises(ValueError, match="checksum"):
        evaluate(path, tmp_path / "report.json")
    spec["episodes"][0]["reference"] = dump(tmp_path / "reference.json", {"id": "ep", "turns": [{"text": "script is not gold"}]})
    dump(path, spec)
    with pytest.raises(ValueError, match="scripts are not reviewed"):
        evaluate(path, tmp_path / "report.json")


def test_controlled_command_api_smoke_and_fresh_process_cached_replay(tmp_path):
    command = """import json,sys
request=json.load(sys.stdin)
stage=request['prompt']['stage']
value={'errors':[]} if stage=='errors' else {'score':93.75}
print(json.dumps({'status':'completed','actual_model':'gpt-6-astra','model_identity_evidence':{'synthetic':True},'content':value,'raw':{'controlled':True}}))
"""
    transport = tmp_path / "transport.json"
    dump(transport, {"kind": "synthetic-command", "command": [sys.executable, "-B", "-c", command]})
    store = tmp_path / "store"
    first = judge_role(DATA, store_path=store, transport_path=transport, measurements_ended=True, bindings=BINDINGS)
    assert first["quality"]["score"] == 93.75
    replay = """import json,sys
from bench.quality import judge_role
report=judge_role(json.loads(sys.argv[2]),store_path=sys.argv[1],judge_kind='synthetic-command',bindings=json.loads(sys.argv[3]))
print(json.dumps(report))
"""
    result = subprocess.run([sys.executable, "-B", "-c", replay, str(store), json.dumps(DATA), json.dumps(BINDINGS)],
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    second = json.loads(result.stdout)
    assert second["quality"]["score"] == 93.75
    assert len(second["calls"]) == 2
    assert second["quality"]["errors_stage"]["cached"] and second["quality"]["score_stage"]["cached"]


def test_actual_ascend_generator_shape_keeps_both_ordinary_speakers(monkeypatch, tmp_path):
    from tools.prepare_ascend import reference_spans
    transport = ControlledTransport()
    install(monkeypatch, transport)
    path, spec = spec_fixture(tmp_path, kind="P2")
    texts = ["Do not buy twelve tickets. 中文背景", "I will buy no tickets."]
    rows = [{"natural_source_key": f"original-{index}", "role": role, "original_person": 10 + index,
             "released_human_transcript": text, "reference_utf8_sha256": identity(text),
             "translation_targets": [span for span in reference_spans(text) if span["language"] == "en"],
             "reference_notes": ["Retained source uncertainty, not an invented lexical target"]}
            for index, (role, text) in enumerate(zip(("A", "B"), texts))]
    reference = {"id": "ep", "references": rows,
                 "source_to_playback": [{"natural_source_key": row["natural_source_key"],
                                         "playback_samples": [index * 16000, (index + 1) * 16000]}
                                        for index, row in enumerate(rows)],
                 "semantic_checkpoints": [{"id": "cpB", "role": "B", "required_concepts": ["buy no tickets"],
                                          "allowed_paraphrase_concepts": ["equivalent meaning"],
                                          "playback_evidence_end_sample_proposal": 32000,
                                          "observation_offsets_seconds": [0, 2, 5, 10, 15]}]}
    spec["episodes"][0]["reference"] = dump(tmp_path / "reference.json", reference)
    spec["populations"][0]["roles"][0]["selection"]["clock"]["horizon_ns"] = 17_000_000_000
    dump(path, spec)
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    data = json.loads(transport.requests[0]["messages"][1]["content"].split("Untrusted episode data (JSON):\n", 1)[1])
    assert texts[1] in data["source"]
    assert "中文背景" not in data["source"]
    assert data["context"][1]["original_person"] == 11
    assert all(row["scored"] for row in data["context"])
    assert report["planned_episodes"][0]["checkpoint_ids"] == {"A": ["cpB"]}


def test_late_native_evidence_does_not_invalidate_earlier_cached_stages(monkeypatch, tmp_path):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    path, spec = spec_fixture(tmp_path)
    first = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    assert len(first["calls"]) == 7
    rows = [event(), event("LATE_OUTPUT_NOT_AVAILABLE", seconds=20)]
    selection = spec["populations"][0]["roles"][0]["selection"]
    selection["history"] = dump(tmp_path / "history.json", rows)
    selection["interpretations"].append(interpretation(rows, 1))
    dump(path, spec)
    second = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    assert len(second["calls"]) == 7
    assert len(transport.requests) == 7
    assert role_result(second)["quality"]["errors_stage"]["cached"]
    assert all(o["judgment"]["cached"] for o in role_result(second)["checkpoints"][0]["observations"])
    assert role_result(second)["history"]["late_events"]


def test_run_manifest_selection_binds_attempt_trace_and_complete_no_output(tmp_path):
    path, _, _, _ = run_fixture(tmp_path)
    report = evaluate(path, tmp_path / "report.json")
    assert role_result(report)["quality"]["status"] == "no_output"
    assert role_result(report)["checkpoints"][0]["status"] == "unmet"
    assert role_result(report)["provenance"]["selection"]["attempt_id"] == 1
    assert report["calls"] == []


def test_clock_interval_crossing_and_final_unknown_keep_earlier_semantic_success(monkeypatch, tmp_path):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    rows = [event(), event("unrelated unresolved output", seconds=12)]
    path, spec = spec_fixture(tmp_path, events=rows, interpretations=[interpretation(rows, 0)])
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    assert role_result(report)["quality"]["status"] == "unknown_output"
    assert role_result(report)["checkpoints"][0]["first_met"] == [0, 0]
    assert role_result(report)["checkpoints"][0]["status"] == "met"
    assert all(request["stage"] == "checkpoint" for request in transport.requests)
    rows = [event(seconds=3, event_time_interval={"earliest_ns": 2_500_000_000, "latest_ns": 3_500_000_000,
                                                "clock_session": "clock"})]
    selection = spec["populations"][0]["roles"][0]["selection"]
    selection["history"] = dump(tmp_path / "history.json", rows)
    selection["interpretations"] = [interpretation(rows, 0)]
    dump(path, spec)
    report = evaluate(path, tmp_path / "clock-report.json", transport_path="controlled")
    cp = role_result(report)["checkpoints"][0]
    assert cp["observations"][1]["status"] == "unknown"
    assert cp["first_met"] == [0, 5]


@pytest.mark.parametrize("state,expected", [("unsupported", "unsupported"), ("unknown", "unknown")])
def test_unsupported_and_unknown_are_not_no_output(monkeypatch, tmp_path, state, expected):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    path, _ = spec_fixture(tmp_path, events=[], outcome={"state": state, "reason": "explicit recorded reason"})
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    assert role_result(report)["quality"]["status"] == expected
    assert role_result(report)["quality"]["score"] is None
    assert report["calls"] == []


def test_unknown_reference_cannot_turn_no_output_into_protocol_zero(tmp_path):
    path, spec = spec_fixture(tmp_path, events=[], outcome={"state": "done",
        "role_outcomes": {"A": {"status": "product_no_output"}},
        "opportunity": {"input_complete": True, "app_opportunity": True, "observation_complete": True}})
    reference = json.loads((tmp_path / "reference.json").read_text(encoding="utf-8"))
    reference["quality_eligible"] = False
    spec["episodes"][0]["reference"] = dump(tmp_path / "reference.json", reference)
    dump(path, spec)
    report = evaluate(path, tmp_path / "report.json")
    assert role_result(report)["quality"]["status"] == "unknown_reference"
    assert role_result(report)["quality"]["score"] is None


def test_actual_controlled_evaluate_cli_smoke_preserves_partial_report_and_cache(tmp_path):
    path, _ = spec_fixture(tmp_path)
    script = """import json,sys
r=json.load(sys.stdin)['prompt']
data=json.loads(r['messages'][1]['content'].split('Untrusted episode data (JSON):\\n',1)[1])
value=({'errors':[]} if r['stage']=='errors' else {'score':94} if r['stage']=='score' else
       {'status':'met','evidence':[{'side':'output','text':data['output'],'occurrence':1}],
        'reversal':False,'correction':False,'reason':'controlled synthetic decision'})
print(json.dumps({'status':'completed','actual_model':'gpt-6-astra','model_identity_evidence':{'synthetic':True},'content':value,'raw':{'controlled':True}}))
"""
    transport = tmp_path / "transport.json"
    dump(transport, {"kind": "synthetic-command", "command": [sys.executable, "-B", "-c", script]})
    output = tmp_path / "report.json"
    command = [sys.executable, "-B", "-m", "bench.cli", "quality", "--spec", str(path), "--output", str(output)]
    result = subprocess.run(command + ["--transport", str(transport)], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 2, result.stdout + result.stderr
    assert json.loads(result.stdout)["status"] == "incomplete"
    report = json.loads(output.read_text(encoding="utf-8"))
    assert role_result(report)["quality"]["score"] == 94
    assert role_result(report)["checkpoints"][0]["first_met"] == [0, 0]
    assert len(report["calls"]) == 7
    replay = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert replay.returncode == 2, replay.stdout + replay.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert len(report["calls"]) == 7
    assert role_result(report)["quality"]["errors_stage"]["cached"]


@pytest.mark.parametrize("artifact", ["spec", "reference", "history", "manifest", "trace", "stream", "interpretations", "transport"])
@pytest.mark.parametrize("temporary", [False, True])
def test_report_and_atomic_temporary_cannot_overwrite_consumed_artifacts(monkeypatch, tmp_path, artifact, temporary):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    if artifact in ("manifest", "trace", "stream"):
        path, spec, manifest, records = run_fixture(tmp_path)
    else:
        path, spec = spec_fixture(tmp_path)
    selection = spec["populations"][0]["roles"][0]["selection"]
    target = tmp_path / ("immutable.json.tmp" if temporary else "immutable.json")
    transport_path = tmp_path / "transport.json"
    transport_value = {"kind": "synthetic-command", "command": [sys.executable, "-c", "raise SystemExit(1)"]}
    dump(transport_path, transport_value)
    if artifact == "reference":
        spec["episodes"][0]["reference"] = dump(target, json.loads((tmp_path / "reference.json").read_text(encoding="utf-8")))
    elif artifact == "history":
        selection["history"] = dump(target, [event()])
    elif artifact == "interpretations":
        selection["interpretations"] = dump(target, selection["interpretations"])
    elif artifact == "transport":
        dump(target, transport_value)
        transport_path = target
    elif artifact in ("manifest", "trace", "stream"):
        if artifact == "trace":
            binding = dump(target, records)
            manifest["attempts"][0].update(trace=binding["path"], checksum=binding["sha256"])
        elif artifact == "stream":
            manifest["streams"] = [dump(target, [])]
        selection["run_manifest"] = dump(target if artifact == "manifest" else tmp_path / "manifest.json", manifest)
    if artifact == "spec":
        path = target
    dump(path, spec)
    originals = {file: file.read_bytes() for file in tmp_path.iterdir() if file.is_file()}
    output = tmp_path / "immutable.json"
    with pytest.raises(ValueError, match="must not overwrite an immutable input"):
        evaluate(path, output, transport_path=transport_path)
    assert {file: file.read_bytes() for file in originals} == originals
    assert not Path(str(output) + ".store").exists()
    assert transport.requests == []


@pytest.mark.parametrize("temporary", [False, True])
def test_output_guard_preserves_hardlinked_input_bytes(tmp_path, temporary):
    path, _ = spec_fixture(tmp_path)
    original = tmp_path / "reference.json"
    before = original.read_bytes()
    output = tmp_path / "alias.json"
    alias = output.with_name(output.name + ".tmp") if temporary else output
    alias.hardlink_to(original)
    with pytest.raises(ValueError, match="immutable input"):
        evaluate(path, output)
    assert original.read_bytes() == before and alias.read_bytes() == before
    assert not Path(str(output) + ".store").exists()


@pytest.mark.parametrize("extra", [
    {"translated_texts": ["非空翻译"]}, {"translated_texts": [""] + [None]},
    {"translated_texts": "unresolved native extraction"}, {"translated_text": None},
    {"loss_or_gap": {"reason": "collector dropped records"}},
    {"event_time_interval": {"earliest_ns": 2, "latest_ns": 1, "clock_session": "clock"}},
    {"clock_mapping": None}, {"role": None}, {"target_language": None}, {"clock_session": "another-clock"},
])
def test_empty_primary_text_cannot_certify_ambiguous_native_evidence_as_zero(monkeypatch, tmp_path, extra):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    rows = [event("", **extra)]
    path, _ = spec_fixture(tmp_path, events=rows, outcome={"state": "done",
        "role_outcomes": {"A": {"status": "product_no_output"}},
        "opportunity": {"input_complete": True, "app_opportunity": True, "observation_complete": True}})
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    result = role_result(report)
    assert result["quality"]["status"] == "unknown_output" and result["quality"]["score"] is None
    assert result["checkpoints"][0]["status"] == "unknown"
    assert report["calls"] == [] and transport.requests == []


def test_explicitly_empty_native_output_remains_protocol_zero_without_judging(monkeypatch, tmp_path):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    path, _ = spec_fixture(tmp_path, events=[event("", translated_texts=[])], outcome={"state": "done",
        "role_outcomes": {"A": {"status": "product_no_output"}},
        "opportunity": {"input_complete": True, "app_opportunity": True, "observation_complete": True}})
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    assert role_result(report)["quality"]["score"] == 0
    assert role_result(report)["quality"]["score_source"] == "protocol"
    assert role_result(report)["checkpoints"][0]["status"] == "unmet"
    assert report["calls"] == [] and transport.requests == []


@pytest.mark.parametrize("problem", ["missing", "gap", "overlap", "status", "rate", "calibration", "hash", "horizon"])
def test_manifest_unverified_source_mapping_never_becomes_protocol_zero(tmp_path, problem):
    path, spec, manifest, records = run_fixture(tmp_path)
    if problem == "missing":
        records[:] = [row for row in records if row.get("record") != "audio_callback"]
    elif problem in ("gap", "overlap"):
        records[3]["source_frame"] += 100 if problem == "gap" else -100
    elif problem == "status":
        records[3]["status"] = "underflow"
    elif problem == "rate":
        manifest["plan"]["episodes"][0]["roles"]["A"]["sample_rate"] = None
    elif problem == "calibration":
        records[1]["calibration"]["status"] = "unmeasured"
    elif problem == "hash":
        records[1]["audio_sha256"] = "another-wave"
    else:
        manifest["attempts"][0]["detail"]["role_horizons_ns"]["peer"] -= 1_000_000_000
    save_run(path, spec, manifest, records)
    report = evaluate(path, tmp_path / "report.json")
    result = role_result(report)
    assert result["quality"]["status"] == "unknown" and result["quality"]["score"] is None
    assert result["checkpoints"][0]["status"] == "unknown"
    assert result["provenance"]["source_clock_status"]["A"]["status"] == "unknown"
    assert report["calls"] == []


def test_callback_gap_contradicts_playback_complete_and_positive_output(monkeypatch, tmp_path):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    path, spec, manifest, records = run_fixture(tmp_path, events=[event(seconds=11)])
    records[3]["source_frame"] += 100
    save_run(path, spec, manifest, records)
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    result = role_result(report)
    assert result["outcome"]["playback"]["peer"]["complete"] is True
    assert result["quality"]["status"] == "unknown" and result["quality"]["score"] is None
    assert result["provenance"]["input_error"]
    assert result["checkpoints"][0]["status"] == "unknown"
    assert report["calls"] == [] and transport.requests == []


def test_origin_alone_keeps_quality_separate_and_retains_profile_horizon(monkeypatch, tmp_path):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    path, spec, manifest, records = run_fixture(tmp_path, events=[event(seconds=11), event("LATE", seconds=29)])
    # The terminal collector stopped at32.25, but classification ends at27.25.
    records[:] = [row for row in records if row.get("record") != "audio_callback"]
    selection = spec["populations"][0]["roles"][0]["selection"]
    selection["interpretations"] = [interpretation(records, i) for i, row in enumerate(records) if row.get("record") == "native_output_event"]
    save_run(path, spec, manifest, records)
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    result = role_result(report)
    assert result["quality"]["status"] == "judged" and result["quality"]["score"] == 96.5
    assert result["checkpoints"][0]["status"] == "unknown"
    assert result["provenance"]["source_clock_kind"] == "unavailable"
    assert result["history"]["horizon_ns"] == 27_250_000_000
    assert result["history"]["text"] == DATA["output"] and result["history"]["late_events"]
    assert [request["stage"] for request in transport.requests] == ["errors", "score"]


def test_callback_local_mapping_calibration_and_past_only_source_drive_checkpoints(monkeypatch, tmp_path):
    def decisions(stage, data):
        if stage == "errors":
            return {"errors": []}
        if stage == "score":
            return {"score": 77.125}
        return {"status": "met" if data["output"] else "unmet",
                "evidence": [{"side": "output", "text": data["output"], "occurrence": 1}] if data["output"] else [],
                "reason": "Controlled source-time fixture", "reversal": False, "correction": False}
    transport = ControlledTransport(decisions)
    install(monkeypatch, transport)
    path, spec, manifest, records = run_fixture(tmp_path, events=[event(seconds=12.8)], dac_seconds=(10, 10.5, 12, 12.5))
    reference = json.loads((tmp_path / "reference.json").read_text(encoding="utf-8"))
    reference["source_units"][0]["end_ns"] = 1_250_000_000
    reference["source_units"].append({"id": "future", "role": "A", "text": "FUTURE_CONTEXT", "start_ns": 1_500_000_000,
                                       "end_ns": 2_000_000_000, "context_only": True, "citations": ["controlled later source"]})
    reference["semantic_checkpoints"][0]["evidence_end_seconds"] = 1.25
    spec["episodes"][0]["reference"] = dump(tmp_path / "reference.json", reference)
    save_run(path, spec, manifest, records)
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    result = role_result(report)
    cp = result["checkpoints"][0]
    assert result["quality"]["score"] == 77.125
    assert cp["first_met"] == [0, 2]
    assert cp["observations"][0]["source_evidence_end_ns"] == 12_500_000_000
    assert [row["cutoff_ns"] for row in cp["observations"]] == [12_500_000_000, 14_500_000_000, 17_500_000_000, 22_500_000_000, 27_500_000_000]
    requests = [request for request in transport.requests if request["stage"] == "checkpoint"]
    assert len(requests) == 5
    assert "FUTURE_CONTEXT" not in requests[0]["messages"][1]["content"]
    assert "FUTURE_CONTEXT" in requests[1]["messages"][1]["content"]
    assert result["provenance"]["source_clock_kind"] == "runner_callbacks"


def test_common_pass_horizon_not_active_role_speech_end_controls_no_output_wait(tmp_path):
    path, spec, manifest, records = run_fixture(tmp_path)
    # Role A's only source unit ends at1s; original common final speech is2s.
    report = evaluate(path, tmp_path / "report.json")
    result = role_result(report)
    assert result["quality"]["score"] == 0
    assert result["history"]["horizon_ns"] == 27_250_000_000
    assert result["checkpoints"][0]["observations"][-1]["cutoff_ns"] == 26_250_000_000
    assert result["checkpoints"][0]["status"] == "unmet" and report["calls"] == []


def test_manifest_rejects_linear_clock_override_while_standalone_remains_explicit(tmp_path):
    path, spec, manifest, records = run_fixture(tmp_path)
    clock = {"origin_ns": 0, "horizon_ns": 16_000_000_000, "clock_session": "clock",
             "evidence": ["Controlled standalone linear-clock proof"]}
    spec["populations"][0]["roles"][0]["selection"]["clock"] = clock
    save_run(path, spec, manifest, records)
    with pytest.raises(ValueError, match="explicit linear clocks require standalone"):
        evaluate(path, tmp_path / "report.json")
    path, _ = spec_fixture(tmp_path)
    report = evaluate(path, tmp_path / "standalone.json")
    assert role_result(report)["provenance"]["source_clock_kind"] == "standalone_linear"


@pytest.mark.parametrize("scope", [{"channel": "self"}, {"clock_session": "another-session"}])
def test_manifest_scope_cannot_redirect_verified_source_clock(tmp_path, scope):
    path, spec, manifest, records = run_fixture(tmp_path)
    spec["populations"][0]["roles"][0]["selection"]["scope"] = scope
    save_run(path, spec, manifest, records)
    with pytest.raises(ValueError, match="source channel or clock session"):
        evaluate(path, tmp_path / "report.json")


@pytest.mark.parametrize("gap", [False, True])
def test_unmeasured_clock_does_not_hide_input_gap_or_discard_valid_final_quality(monkeypatch, tmp_path, gap):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    path, spec, manifest, records = run_fixture(tmp_path, events=[event(seconds=11)])
    records[1]["calibration"]["status"] = "unmeasured"
    if gap:
        records[3]["source_frame"] += 100
    save_run(path, spec, manifest, records)
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    result = role_result(report)
    assert result["quality"]["status"] == ("unknown" if gap else "judged")
    assert result["quality"]["score"] == (None if gap else 96.5)
    assert result["checkpoints"][0]["status"] == "unknown"
    assert len(report["calls"]) == (0 if gap else 2)


def test_role_unsupported_remains_separate_from_callback_evidence_gap(tmp_path):
    path, spec, manifest, records = run_fixture(tmp_path)
    records[3]["source_frame"] += 100
    manifest["attempts"][0]["detail"]["role_outcomes"]["A"]["status"] = "unsupported"
    save_run(path, spec, manifest, records)
    result = role_result(evaluate(path, tmp_path / "report.json"))
    assert result["quality"]["status"] == "unsupported" and result["quality"]["score"] is None
    assert result["provenance"]["input_error"]


def test_scheduling_silence_is_not_source_frames_and_does_not_break_valid_clock(tmp_path):
    path, spec, manifest, records = run_fixture(tmp_path)
    records.insert(2, {"record": "audio_callback", "input_channel": "peer", "source_frame": 0,
                       "source_frames": 0, "dac_t_ns": 10_000_000_001, "scheduled_silence_frames": 500, "status": ""})
    save_run(path, spec, manifest, records)
    result = role_result(evaluate(path, tmp_path / "report.json"))
    assert result["quality"]["score"] == 0
    assert result["checkpoints"][0]["observations"][0]["cutoff_ns"] == 11_250_000_000
    assert len(result["provenance"]["source_clocks"]["A"]["callbacks"]) == 4


@pytest.mark.parametrize("mismatch", ["route_calibration", "frozen_common_horizon"])
def test_manifest_clock_requires_frozen_route_and_common_pass_binding(tmp_path, mismatch):
    path, spec, manifest, records = run_fixture(tmp_path)
    if mismatch == "route_calibration":
        manifest["plan"]["profiles"][0]["routes"]["peer"]["calibration"]["record_sha256"] = "another-calibration"
    else:
        manifest["plan"]["passes"][0]["common_last_speech_seconds"] = 1
    save_run(path, spec, manifest, records)
    result = role_result(evaluate(path, tmp_path / "report.json"))
    assert result["quality"]["status"] == "unknown" and result["quality"]["score"] is None
    assert result["checkpoints"][0]["status"] == "unknown"


def condition_fixture(tmp_path, profile="KIKI2", *, kind="P1", manifest_selection=False):
    self_only = profile.startswith(("KIKI", "VRCLT"))
    channel = "self" if self_only else "peer"
    label = "self/split" if self_only else "peer/simultaneous"
    pass_id = ("A" if self_only else "simultaneous") if kind == "T1" else "ordinary-" + channel
    if manifest_selection:
        path, spec, manifest, records = run_fixture(tmp_path)
        for record in records:
            if "profile" in record:
                record["profile"] = profile
            if "pass_id" in record:
                record["pass_id"] = pass_id
            if "input_channel" in record:
                record["input_channel"] = channel
        plan_profile = manifest["plan"]["profiles"][0]
        plan_profile["id"] = profile
        plan_profile["routes"] = {channel: plan_profile["routes"]["peer"]}
        catalog = json.loads((Path(quality.__file__).resolve().parent.parent / "profiles" / "catalog.json").read_text(encoding="utf-8"))
        canonical = next((row for row in catalog["profiles"] if row["id"] == profile), None)
        plan_profile["condition"] = copy.deepcopy(canonical["native_protocol"]["condition"]) if canonical else {
            "ordinary_input": "peer", "t1_mode": "simultaneous", "roles": {"A": "peer", "B": "self"}}
        manifest["work"][0].update(profile=profile, pass_id=pass_id)
        manifest["plan"]["passes"][0].update(profiles=[profile], pass_id=pass_id, roles={channel: {"role": "A"}})
        detail = manifest["attempts"][0]["detail"]
        for field in ("output_windows_ns", "role_horizons_ns", "playback"):
            detail[field] = {channel: detail[field]["peer"]}
        selection = spec["populations"][0]["roles"][0]["selection"]
        selection["pass_id"] = pass_id
    else:
        path, spec = spec_fixture(tmp_path, events=[], kind=kind, outcome={"state": "done",
            "role_outcomes": {"A": {"status": "product_no_output"}},
            "opportunity": {"input_complete": True, "app_opportunity": True, "observation_complete": True}})
        selection = spec["populations"][0]["roles"][0]["selection"]
        selection["scope"].update(profile=profile, channel=channel, pass_id=pass_id)
        manifest, records = None, None
    spec["populations"][0].update(profile=profile, measurement_condition=label)
    if manifest_selection:
        save_run(path, spec, manifest, records)
    else:
        dump(path, spec)
    return path, spec, manifest, records


@pytest.mark.parametrize("profile", ["KIKI1", "KIKI2", "VRCLT1", "VRCLT2"])
def test_canonical_self_profiles_cannot_be_labelled_peer_simultaneous(tmp_path, profile):
    path, spec, _, _ = condition_fixture(tmp_path, profile)
    spec["populations"][0]["measurement_condition"] = "peer/simultaneous"
    dump(path, spec)
    with pytest.raises(ValueError, match="measurement_condition must be 'self/split'"):
        evaluate(path, tmp_path / "report.json")
    assert not (tmp_path / "report.json.store").exists()


@pytest.mark.parametrize("profile", ["KIKI1", "KIKI2", "VRCLT1", "VRCLT2"])
def test_canonical_self_condition_is_structured_auditable_and_retains_valid_no_output(tmp_path, profile):
    path, _, _, _ = condition_fixture(tmp_path, profile)
    report = evaluate(path, tmp_path / "report.json")
    population = report["populations"][0]
    assert population["measurement_condition"] == "self/split"
    assert population["condition"]["ordinary_input"] == "self"
    assert population["condition"]["t1_mode"] == "split_self"
    assert population["condition"]["roles"] == {"A": "self", "B": "self"}
    assert population["condition_evidence"][0]["source"] == "profile_catalog"
    assert population["condition_evidence"][0]["sha256"]
    assert role_result(report)["condition"] == population["condition"]
    assert role_result(report)["quality"]["score"] == 0 and report["calls"] == []


@pytest.mark.parametrize("scope", [{"channel": "peer"}, {"pass_id": "simultaneous"}, {"profile": "TEST"}])
def test_canonical_split_scope_cannot_contradict_channel_pass_or_profile(tmp_path, scope):
    path, spec, _, _ = condition_fixture(tmp_path, kind="T1")
    spec["populations"][0]["roles"][0]["selection"]["scope"].update(scope)
    dump(path, spec)
    with pytest.raises(ValueError, match="contradicts the authoritative measurement condition"):
        evaluate(path, tmp_path / "report.json")


@pytest.mark.parametrize("native", [
    {"role": "A", "input_channel": "peer"},
    {"role": None, "input_channel": "peer"},
    {"role": "B", "input_channel": "self"},
])
def test_canonical_split_native_routing_cannot_be_hidden_by_scope(tmp_path, native):
    path, spec, _, _ = condition_fixture(tmp_path, kind="T1")
    rows = [event("", profile="KIKI2", pass_id="A", **native)]
    selection = spec["populations"][0]["roles"][0]["selection"]
    selection["history"] = dump(tmp_path / "history.json", rows)
    selection["interpretations"] = [interpretation(rows, 0)]
    dump(path, spec)
    with pytest.raises(ValueError, match="Native role/channel evidence contradicts"):
        evaluate(path, tmp_path / "report.json")


def test_canonical_peer_profile_keeps_simultaneous_role_mapping(tmp_path):
    path, _, _, _ = condition_fixture(tmp_path, "PP4", kind="T1")
    report = evaluate(path, tmp_path / "report.json")
    population = report["populations"][0]
    assert population["condition"]["t1_mode"] == "simultaneous"
    assert population["condition"]["roles"] == {"A": "peer", "B": "self"}
    assert role_result(report)["quality"]["score"] == 0
    assert population["role_results"][1]["quality"]["status"] == "missing_attempt"


def test_canonical_manifest_condition_and_physical_self_pass_are_retained(tmp_path):
    path, _, _, _ = condition_fixture(tmp_path, manifest_selection=True)
    report = evaluate(path, tmp_path / "report.json")
    result = role_result(report)
    assert result["quality"]["score"] == 0
    assert result["provenance"]["source_clock_kind"] == "runner_callbacks"
    assert result["history"]["scope"]["input_channel"] == "self"
    assert result["history"]["scope"]["pass_id"] == "ordinary-self"
    assert {row["source"] for row in result["condition_evidence"]} == {"profile_catalog", "run_manifest"}
    assert report["populations"][0]["condition"]["t1_mode"] == "split_self"


@pytest.mark.parametrize("contradiction", ["profile_condition", "pass_roles"])
def test_canonical_manifest_cannot_override_approved_condition_or_role_route(tmp_path, contradiction):
    path, spec, manifest, records = condition_fixture(tmp_path, manifest_selection=True)
    if contradiction == "profile_condition":
        manifest["plan"]["profiles"][0]["condition"] = {
            "ordinary_input": "peer", "t1_mode": "simultaneous", "roles": {"A": "peer", "B": "self"}}
    else:
        manifest["plan"]["passes"][0]["roles"] = {"peer": {"role": "A"}}
    save_run(path, spec, manifest, records)
    with pytest.raises(ValueError, match="contradict"):
        evaluate(path, tmp_path / "report.json")


def test_custom_manifest_condition_is_authoritative_without_catalog_profile(tmp_path):
    path, _, _, _ = condition_fixture(tmp_path, "CUSTOM", manifest_selection=True)
    report = evaluate(path, tmp_path / "report.json")
    population = report["populations"][0]
    assert population["condition"]["ordinary_input"] == "peer"
    assert population["condition"]["t1_mode"] == "simultaneous"
    assert [row["source"] for row in population["condition_evidence"]] == ["run_manifest"]
    assert role_result(report)["quality"]["score"] == 0


def test_custom_explicit_condition_remains_available(tmp_path):
    path, spec = spec_fixture(tmp_path, events=[], kind="T1")
    population = spec["populations"][0]
    population.update(measurement_condition="self/split", condition={
        "ordinary_input": "self", "t1_mode": "split_self", "roles": {"A": "self", "B": "self"}})
    population["roles"][0]["selection"]["scope"].update(channel="self", pass_id="A")
    dump(path, spec)
    report = evaluate(path, tmp_path / "report.json")
    assert report["populations"][0]["condition"] == population["condition"]
    assert report["populations"][0]["condition_evidence"] == [{"source": "explicit_population"}]
    assert role_result(report)["quality"]["score"] is None and report["calls"] == []


@pytest.mark.parametrize("temporary", [False, True])
def test_consumed_profile_catalog_is_protected_from_report_writes(monkeypatch, tmp_path, temporary):
    path, _ = spec_fixture(tmp_path)
    checkout = tmp_path / "controlled-checkout"
    catalog = checkout / "profiles" / ("catalog.json.tmp" if temporary else "catalog.json")
    catalog.parent.mkdir(parents=True)
    if temporary:
        # Keep the lookup name fixed while exercising the atomic temporary alias.
        catalog = catalog.with_name("catalog.json")
    dump(catalog, {"profiles": []})
    monkeypatch.setattr(quality, "__file__", str(checkout / "bench" / "quality.py"))
    output = catalog
    if temporary:
        output = catalog.with_name("result.json")
        output.with_name(output.name + ".tmp").hardlink_to(catalog)
    before = catalog.read_bytes()
    with pytest.raises(ValueError, match="immutable input"):
        evaluate(path, output)
    assert catalog.read_bytes() == before


def test_correct_emission_replaced_between_observations_remains_citable(monkeypatch, tmp_path):
    correct, wrong = DATA["output"], "买十二张票。"
    rows = [event(correct, seconds=1.25), event(wrong, seconds=2)]
    rules = [interpretation(rows, 0), interpretation(rows, 1, "replace", 0)]
    def decisions(stage, data):
        if stage == "errors":
            assert data["output"] == wrong
            return {"errors": []}
        if stage == "score":
            assert data["output"] == wrong
            return {"score": 33}
        matches = [row for row in data["output_history"] if row.get("text") == correct]
        return {"status": "met" if matches else "unmet",
                "evidence": [{"side": "history", "history_index": matches[0]["index"],
                              "text": correct, "occurrence": 1}] if matches else [],
                "reversal": bool(matches and data["output"] == wrong), "correction": False,
                "reason": "Controlled earlier emission and contradictory replacement"}
    transport = ControlledTransport(decisions)
    install(monkeypatch, transport)
    path, _ = spec_fixture(tmp_path, events=rows, interpretations=rules)
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    result = role_result(report)
    cp = result["checkpoints"][0]
    assert result["quality"]["score"] == 33 and result["history"]["text"] == wrong
    assert [row["text"] for row in result["history"]["revisions"]] == [correct, wrong]
    assert cp["observations"][0]["status"] == "unmet"
    assert cp["status"] == "met" and cp["first_met"] == [0, 2]
    assert cp["later_reversals_seconds"] == [2]
    assert cp["observations"][1]["evidence"] == [{"side": "history", "history_index": 0, "text": correct, "occurrence": 1}]
    citation = cp["observations"][1]["native_history_citations"][0]
    assert citation["index"] == 0
    assert citation["citation"]["event_index"] == 0
    assert citation["citation"]["event_sha256"] == event_sha256(rows[0])
    assert all(row["judgment"]["status"] == "completed" for row in cp["observations"])


@pytest.mark.parametrize("evidence", [
    {"side": "history", "history_index": 1, "text": DATA["output"], "occurrence": 1},
    {"side": "history", "history_index": 0, "text": "不要买12张票。", "occurrence": 1},
    {"side": "history", "history_index": 0, "text": DATA["output"], "occurrence": 2},
    {"side": "history", "history_index": True, "text": DATA["output"], "occurrence": 1},
    {"side": "history", "history_index": -1, "text": DATA["output"], "occurrence": 1},
    {"side": "history", "history_index": 2, "text": "FUTURE_UNAVAILABLE_EMISSION", "occurrence": 1},
])
def test_checkpoint_historical_citations_reject_wrong_nonexact_or_unavailable_evidence(monkeypatch, tmp_path, evidence):
    rows = [event(seconds=1.25), event("买十二张票。", seconds=2), event("FUTURE_UNAVAILABLE_EMISSION", seconds=20)]
    rules = [interpretation(rows, 0), interpretation(rows, 1, "replace", 0), interpretation(rows, 2)]
    def decisions(stage, data):
        if stage == "errors":
            return {"errors": []}
        if stage == "score":
            return {"score": 33}
        assert "FUTURE_UNAVAILABLE_EMISSION" not in json.dumps(data, ensure_ascii=False)
        return {"status": "met" if data["output_history"] else "unmet",
                "evidence": [evidence] if data["output_history"] else [],
                "reversal": False, "correction": False, "reason": "Controlled forged historical quote"}
    transport = ControlledTransport(decisions)
    install(monkeypatch, transport)
    path, _ = spec_fixture(tmp_path, events=rows, interpretations=rules)
    result = role_result(evaluate(path, tmp_path / "report.json", transport_path="controlled"))
    cp = result["checkpoints"][0]
    assert result["quality"]["score"] == 33
    assert cp["status"] == "unknown" and cp["first_met"] is None
    assert all(row["judgment"]["status"] == "invalid_response" for row in cp["observations"][1:])


@pytest.mark.parametrize("operation", ["clear", "delete", "ignore"])
def test_checkpoint_history_quote_requires_emitted_text_not_presentation_operation(operation):
    data = {**DATA, "output_history": [{"index": 0, "operation": operation, "text": DATA["output"]}]}
    value = {"status": "met", "evidence": [{"side": "history", "history_index": 0, "text": DATA["output"], "occurrence": 1}],
             "reversal": False, "correction": False, "reason": "Cannot cite a non-emission"}
    with pytest.raises(ValueError, match="admitted emission"):
        validate("checkpoint", value, data)


def test_historical_quote_extension_is_checkpoint_only_and_preserves_surviving_output_quotes():
    historical = {"side": "history", "history_index": 0, "text": DATA["output"], "occurrence": 1}
    data = {**DATA, "output_history": [{"index": 0, "operation": "append", "text": DATA["output"]}]}
    value = {"status": "met", "evidence": [historical], "reversal": False, "correction": False, "reason": "Earlier output"}
    assert validate("checkpoint", value, data) == value
    current = {**value, "evidence": [{"side": "output", "text": DATA["output"], "occurrence": 1}]}
    assert validate("checkpoint", current, data) == current
    with pytest.raises(ValueError, match="invalid object schema"):
        validate("errors", {"errors": [{"category": "accuracy/mistranslation", "severity": "major",
            "quote": historical, "explanation": "History is not an error-stage quote side"}]}, data)


@pytest.mark.parametrize("available_ns", [500_000_000, 1_000_000_000, 1_500_000_000])
@pytest.mark.parametrize("no_output", [False, True])
def test_standalone_partial_input_overrides_complete_opportunity_for_final_quality(monkeypatch, tmp_path, available_ns, no_output):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    path, spec = spec_fixture(tmp_path, events=[] if no_output else [event()], outcome={"state": "done",
        "role_outcomes": {"A": {"status": "product_no_output" if no_output else "output_observed"}},
        "opportunity": {"input_complete": True, "app_opportunity": True, "observation_complete": True}})
    spec["populations"][0]["roles"][0]["selection"]["clock"]["input_available_until_ns"] = available_ns
    dump(path, spec)
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    result = role_result(report)
    if available_ns < 1_000_000_000:
        assert result["quality"]["status"] == "unknown_input" and result["quality"]["score"] is None
        assert result["checkpoints"][0]["status"] == "unknown"
        assert report["calls"] == [] and transport.requests == []
    else:
        assert result["quality"]["status"] == ("no_output" if no_output else "judged")
        assert result["quality"]["score"] == (0 if no_output else 96.5)
        assert result["checkpoints"][0]["status"] == ("unmet" if no_output else "met")
        assert len(report["calls"]) == (0 if no_output else 7)


def test_partial_input_retains_valid_earlier_checkpoint_without_judging_unheard_final_source(monkeypatch, tmp_path):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    units = [{"id": "early", "role": "A", "text": DATA["source"], "start_ns": 0, "end_ns": 1_000_000_000,
              "citations": ["Controlled heard source"]},
             {"id": "late", "role": "A", "text": "UNHEARD_LATER_SOURCE", "start_ns": 3_000_000_000,
              "end_ns": 4_000_000_000, "citations": ["Controlled unplayed source"]}]
    path, spec = spec_fixture(tmp_path, units=units)
    selection = spec["populations"][0]["roles"][0]["selection"]
    selection["clock"]["input_available_until_ns"] = 2_500_000_000
    reference = json.loads((tmp_path / "reference.json").read_text(encoding="utf-8"))
    reference["semantic_checkpoints"].append({"id": "late", "role": "A", "evidence_end_seconds": 4,
                                               "required_concepts": ["Unheard later meaning"]})
    spec["episodes"][0]["reference"] = dump(tmp_path / "reference.json", reference)
    dump(path, spec)
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    result = role_result(report)
    assert result["quality"]["status"] == "unknown_input" and result["quality"]["score"] is None
    assert result["checkpoints"][0]["status"] == "met" and result["checkpoints"][0]["first_met"] == [0, 0]
    assert result["checkpoints"][1]["status"] == "unknown"
    assert len(transport.requests) == 5 and all(row["stage"] == "checkpoint" for row in transport.requests)
    assert all("UNHEARD_LATER_SOURCE" not in row["messages"][1]["content"] for row in transport.requests)


def test_partial_input_preserves_explicit_harness_invalid_state(monkeypatch, tmp_path):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    path, spec = spec_fixture(tmp_path, outcome={"state": "invalid", "harness_interrupted": True})
    spec["populations"][0]["roles"][0]["selection"]["clock"]["input_available_until_ns"] = 500_000_000
    dump(path, spec)
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    assert role_result(report)["quality"]["status"] == "invalid"
    assert role_result(report)["checkpoints"][0]["status"] == "unknown"
    assert report["calls"] == [] and transport.requests == []


def test_actual_ingcrowd_annotation_speakers_survive_blinded_scored_context(monkeypatch, tmp_path):
    from tools.prepare_ingcrowd import annotations, reference
    payload = b'''<ANNOTATION_DOCUMENT><TIME_ORDER>
<TIME_SLOT TIME_SLOT_ID="t0" TIME_VALUE="0"/><TIME_SLOT TIME_SLOT_ID="t1" TIME_VALUE="500"/>
<TIME_SLOT TIME_SLOT_ID="t2" TIME_VALUE="1000"/></TIME_ORDER>
<TIER TIER_ID="speaker-one"><ANNOTATION><ALIGNABLE_ANNOTATION ANNOTATION_ID="a1" TIME_SLOT_REF1="t0" TIME_SLOT_REF2="t1">
<ANNOTATION_VALUE>first speaker text</ANNOTATION_VALUE></ALIGNABLE_ANNOTATION></ANNOTATION></TIER>
<TIER TIER_ID="speaker-two"><ANNOTATION><ALIGNABLE_ANNOTATION ANNOTATION_ID="a2" TIME_SLOT_REF1="t1" TIME_SLOT_REF2="t2">
<ANNOTATION_VALUE>second speaker text</ANNOTATION_VALUE></ALIGNABLE_ANNOTATION></ANNOTATION></TIER></ANNOTATION_DOCUMENT>'''
    bound = reference({"id": "ep", "source_samples": [0, 16000], "annotation_ids": ["a1", "a2"],
        "checkpoints": [{"evidence_annotation_ids": ["a1", "a2"], "required_concepts": ["Both audible speakers"]}],
        "source_review": {"status": "accepted"}}, annotations(payload))
    transport = ControlledTransport()
    install(monkeypatch, transport)
    path, spec = spec_fixture(tmp_path, events=[event("두 사람의 번역", target_language="ko")])
    spec["episodes"][0].update(language_pair="ja-ko", reference=dump(tmp_path / "reference.json", bound))
    dump(path, spec)
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    assert role_result(report)["quality"]["score"] == 96.5
    for request in transport.requests:
        data = json.loads(request["messages"][1]["content"].split("Untrusted episode data (JSON):\n", 1)[1])
        assert data["source"] == "first speaker text\nsecond speaker text"
        assert [row["original_person"] for row in data["context"]] == ["speaker-one", "speaker-two"]
        assert all(row["original_person_scope"] == "dialogue_local" for row in data["context"])
        assert all(row["role"] == "A" and row["scored"] is True for row in data["context"])


def runwide_gap(seconds=2, **extra):
    ns = round(seconds * 1e9)
    return {"record": "native_collector_evidence", "run": "controlled-run", "clock_session": "clock",
            "profile": "TEST", "config": "TEST", "kind": "gap", "loss_or_gap": "collector_disconnected",
            "generation": 1, "failure_kind": "transport_disconnect",
            "collector_received_monotonic": ns, "t_ns": ns, **extra}


def scoped_attempt_fixture(tmp_path, *, stream=None, no_output=False):
    path, spec, manifest, records = run_fixture(tmp_path, events=[] if no_output else [event(seconds=11.25)])
    records[0].update(t_ns=5_000_000_000, profile="TEST", episode_id="ep", attempt=1, pass_id="A",
                      clock_session="clock", run="controlled-run")
    records.append({"record": "attempt_end", "t_ns": 34_000_000_000, "state": "done"})
    manifest["run"] = "controlled-run"
    manifest["attempts"][0].update(start_ns=4_900_000_000, end_ns=34_100_000_000)
    if stream is not None:
        manifest["streams"] = [dump(tmp_path / "run-stream.json", stream)]
    save_run(path, spec, manifest, records)
    return path, spec, manifest, records


@pytest.mark.parametrize("seconds", [2, 40])
@pytest.mark.parametrize("no_output", [False, True])
def test_disjoint_runwide_diagnostic_does_not_contaminate_selected_attempt(monkeypatch, tmp_path, seconds, no_output):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    gap = runwide_gap(seconds)
    path, _, _, _ = scoped_attempt_fixture(tmp_path, stream=[gap], no_output=no_output)
    before = (tmp_path / "run-stream.json").read_bytes()
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    result = role_result(report)
    assert result["quality"]["score"] == (0 if no_output else 96.5)
    assert result["checkpoints"][0]["status"] == ("unmet" if no_output else "met")
    assert len(report["calls"]) == (0 if no_output else 7)
    assert result["provenance"]["attempt_bounds"]["start_ns"] == 5_000_000_000
    assert result["provenance"]["attempt_bounds"]["end_ns"] == 34_000_000_000
    excluded, = result["provenance"]["excluded_stream_diagnostics"]
    assert excluded["event"] == gap
    assert excluded["origin"]["record_index"] == 0
    assert excluded["origin"]["artifact"]["sha256"] == digest(tmp_path / "run-stream.json")
    assert any(row["citation"]["event_sha256"] == event_sha256(gap) and "selected_attempt" in row["reason"]
               for row in result["history"]["excluded_events"])
    assert (tmp_path / "run-stream.json").read_bytes() == before


@pytest.mark.parametrize("gap", [
    runwide_gap(5), runwide_gap(6.5), runwide_gap(11),
    runwide_gap(2, event_time_interval={"earliest_ns": 4_000_000_000, "latest_ns": 6_000_000_000, "clock_session": "clock"},
                clock_mapping={"evidence": ["Controlled interval crossing selected start"]}),
    runwide_gap(2, event_time_interval={"earliest_ns": 2_000_000_000, "latest_ns": 5_000_000_000, "clock_session": "clock"},
                clock_mapping={"evidence": ["Controlled interval ending exactly at selected start"]}),
])
def test_preparation_equal_start_and_overlapping_gaps_remain_unknown(monkeypatch, tmp_path, gap):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    path, _, _, _ = scoped_attempt_fixture(tmp_path, stream=[gap])
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    result = role_result(report)
    assert result["quality"]["status"] == "unknown_output" and result["quality"]["score"] is None
    assert "native_history_gap" in result["history"]["reasons"]
    assert result["provenance"]["excluded_stream_diagnostics"] == []
    assert report["calls"] == [] and transport.requests == []


def test_gap_at_selected_attempt_end_remains_available_to_existing_horizon_rules(monkeypatch, tmp_path):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    gap = runwide_gap(34)
    path, _, _, _ = scoped_attempt_fixture(tmp_path, stream=[gap])
    result = role_result(evaluate(path, tmp_path / "report.json", transport_path="controlled"))
    assert result["provenance"]["excluded_stream_diagnostics"] == []
    assert any(row["citation"]["event_sha256"] == event_sha256(gap) for row in result["history"]["late_events"])
    assert result["quality"]["score"] == 96.5
    assert result["checkpoints"][0]["status"] == "unknown"


@pytest.mark.parametrize("problem", [
    "missing_start", "duplicate_start", "missing_end", "duplicate_end", "reversed_bounds",
    "missing_session", "wrong_start_profile", "wrong_start_attempt", "wrong_start_run",
    "ledger_start_conflict", "ledger_end_conflict", "wrong_terminal_state",
])
def test_missing_or_ambiguous_attempt_bounds_do_not_guess_diagnostic_scope(tmp_path, problem):
    path, spec, manifest, records = scoped_attempt_fixture(tmp_path, stream=[runwide_gap()])
    if problem == "missing_start":
        records[0].pop("t_ns")
    elif problem == "duplicate_start":
        records.insert(1, dict(records[0]))
    elif problem == "missing_end":
        records.pop()
    elif problem == "duplicate_end":
        records.append(dict(records[-1]))
    elif problem == "reversed_bounds":
        records[-1]["t_ns"] = 4_000_000_000
    elif problem == "missing_session":
        records[0].pop("clock_session")
    elif problem == "wrong_start_profile":
        records[0]["profile"] = "OTHER"
    elif problem == "wrong_start_attempt":
        records[0]["attempt"] = 99
    elif problem == "wrong_start_run":
        records[0]["run"] = "OTHER-RUN"
    elif problem == "ledger_start_conflict":
        manifest["attempts"][0]["start_ns"] = 6_000_000_000
    elif problem == "ledger_end_conflict":
        manifest["attempts"][0]["end_ns"] = 33_000_000_000
    else:
        records[-1]["state"] = "invalid"
    spec["populations"][0]["roles"][0]["selection"]["interpretations"] = [
        interpretation(records, index) for index, row in enumerate(records) if row.get("record") == "native_output_event"]
    save_run(path, spec, manifest, records)
    result = role_result(evaluate(path, tmp_path / "report.json"))
    assert result["provenance"]["attempt_bounds"]["status"] == "unknown"
    assert result["provenance"]["excluded_stream_diagnostics"] == []
    assert result["quality"]["status"] == "unknown_output" and result["quality"]["score"] is None
    assert "native_history_gap" in result["history"]["reasons"]


@pytest.mark.parametrize("extra", [
    {"clock_session": None}, {"collector_received_monotonic": None}, {"t_ns": 6_000_000_000},
    {"t_ns": True}, {"start_ns": 4_000_000_000, "end_ns": 6_000_000_000},
    {"loss_or_gap": {"start_ns": 4_000_000_000, "end_ns": 6_000_000_000}},
    {"clock_mapping": {"evidence": ["No interval supplied"]}},
    {"event_time_interval": {"earliest_ns": 4, "latest_ns": 2, "clock_session": "clock"},
     "clock_mapping": {"evidence": ["Invalid interval"]}},
    {"event_time_interval": {"earliest_ns": 1, "latest_ns": 2, "clock_session": "clock"}, "clock_mapping": None},
    {"event_time_interval": {"earliest_ns": 1, "latest_ns": 2, "clock_session": "OTHER"},
     "clock_mapping": {"evidence": ["Unrelated clock"]}},
])
def test_uncertain_diagnostic_times_cannot_be_trimmed_into_false_success(tmp_path, extra):
    gap = runwide_gap(**extra)
    path, _, _, _ = scoped_attempt_fixture(tmp_path, stream=[gap], no_output=True)
    result = role_result(evaluate(path, tmp_path / "report.json"))
    assert result["provenance"]["excluded_stream_diagnostics"] == []
    assert result["quality"]["score"] is None and result["quality"]["status"] == "unknown_output"


def test_selected_trace_gap_is_not_discarded_by_a_conflicting_runwide_timestamp(tmp_path):
    path, spec, manifest, records = scoped_attempt_fixture(tmp_path)
    records.insert(1, runwide_gap())
    spec["populations"][0]["roles"][0]["selection"]["interpretations"] = [
        interpretation(records, index) for index, row in enumerate(records) if row.get("record") == "native_output_event"]
    save_run(path, spec, manifest, records)
    result = role_result(evaluate(path, tmp_path / "report.json"))
    assert result["quality"]["status"] == "unknown_output"
    assert "native_history_gap" in result["history"]["reasons"]
    assert result["provenance"]["excluded_stream_diagnostics"] == []


def test_diagnostic_scope_uses_attempt_not_source_mapping_availability(monkeypatch, tmp_path):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    path, spec, manifest, records = scoped_attempt_fixture(tmp_path, stream=[runwide_gap()])
    records[:] = [row for row in records if row.get("record") != "audio_callback"]
    spec["populations"][0]["roles"][0]["selection"]["interpretations"] = [
        interpretation(records, index) for index, row in enumerate(records) if row.get("record") == "native_output_event"]
    save_run(path, spec, manifest, records)
    report = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    result = role_result(report)
    assert result["provenance"]["attempt_bounds"]["status"] == "bounded"
    assert result["provenance"]["source_clock_kind"] == "unavailable"
    assert result["quality"]["score"] == 96.5 and len(report["calls"]) == 2
    assert result["checkpoints"][0]["status"] == "unknown"


def test_history_view_preserves_raw_indexes_hashes_replacements_and_payloads(monkeypatch, tmp_path):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    path, spec, manifest, records = scoped_attempt_fixture(tmp_path, no_output=True)
    gap = runwide_gap()
    rows = [gap, event(seconds=11.25, event_index=789,
                       raw_evidence={"sha256": "wire", "event_index": 987, "derived_item_id": "event:987"}),
            event("买十二张票。", seconds=12), event("", seconds=13), event("", seconds=13.1)]
    manifest["streams"] = [dump(tmp_path / "run-stream.json", rows)]
    base = len(records)
    combined = records + rows
    selection = spec["populations"][0]["roles"][0]["selection"]
    selection["interpretations"] = [interpretation(combined, base + 1), interpretation(combined, base + 2, "replace", base + 1),
                                   interpretation(combined, base + 3, "clear"), interpretation(combined, base + 4, "delete", base + 2)]
    manifest["work"][0]["outcome"] = "output_observed"
    manifest["attempts"][0]["detail"]["role_outcomes"]["A"]["status"] = "output_observed"
    save_run(path, spec, manifest, records)
    result = role_result(evaluate(path, tmp_path / "report.json", transport_path="controlled"))
    history = result["history"]
    assert result["quality"]["score"] == 96.5
    assert history["items"][0]["derived_item_id"] == "event:" + str(base + 1)
    assert [row["citation"]["event_index"] for row in history["revisions"]] == list(range(base + 1, base + 5))
    assert history["revisions"][1]["replaces_event_index"] == base + 1
    assert history["revisions"][2]["archived_item_ids"] == ["event:" + str(base + 1)]
    assert history["revisions"][3]["replaces_event_index"] == base + 2
    assert [row["citation"]["event_index"] for row in history["events"]] == list(range(base + 1, base + 5))
    assert [row["citation"]["event_index"] for row in history["emissions"]] == list(range(base + 1, base + 5))
    assert history["events"][0]["event"] == rows[1]
    assert history["events"][0]["citation"]["event_sha256"] == event_sha256(rows[1])
    assert history["events"][0]["citation"]["raw_evidence"]["event_index"] == 987
    assert result["provenance"]["excluded_stream_diagnostics"][0]["event_index"] == base
    assert result["selection"]["interpretations"] == selection["interpretations"]


def test_explicit_diagnostic_interpretation_is_not_silently_discarded(tmp_path):
    path, spec, manifest, records = scoped_attempt_fixture(tmp_path, stream=[runwide_gap()])
    combined = records + [runwide_gap()]
    spec["populations"][0]["roles"][0]["selection"]["interpretations"].append(interpretation(combined, len(records), "ignore"))
    save_run(path, spec, manifest, records)
    result = role_result(evaluate(path, tmp_path / "report.json"))
    assert result["quality"]["status"] == "unknown_output"
    assert result["provenance"]["excluded_stream_diagnostics"] == []


def test_filtered_diagnostic_does_not_weaken_native_interpretation_hash_validation(tmp_path):
    path, spec, manifest, records = scoped_attempt_fixture(tmp_path, stream=[runwide_gap()])
    spec["populations"][0]["roles"][0]["selection"]["interpretations"][0]["event_sha256"] = "wrong"
    save_run(path, spec, manifest, records)
    with pytest.raises(ValueError, match="does not match the cited native event"):
        evaluate(path, tmp_path / "report.json")


def test_appending_disjoint_runwide_diagnostic_preserves_existing_stage_cache(monkeypatch, tmp_path):
    transport = ControlledTransport()
    install(monkeypatch, transport)
    path, spec, manifest, records = scoped_attempt_fixture(tmp_path)
    first = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    manifest["streams"] = [dump(tmp_path / "run-stream.json", [runwide_gap()])]
    save_run(path, spec, manifest, records)
    second = evaluate(path, tmp_path / "report.json", transport_path="controlled")
    assert role_result(second)["quality"]["score"] == 96.5
    assert len(first["calls"]) == len(second["calls"]) == len(transport.requests) == 7
    assert role_result(second)["quality"]["errors_stage"]["cached"]
    assert all(row["judgment"]["cached"] for row in role_result(second)["checkpoints"][0]["observations"])
