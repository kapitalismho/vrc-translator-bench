from __future__ import annotations

import copy
import json

import pytest

from bench.quality import load_plan, prepare, score, status
from bench.quality_prompts import fingerprint, parse_result
from bench.quality_report import build_report
from bench.quality_store import QualityStore
from test_quality import ROOT, Judge, dump, input_report

V1 = "contextual-esa-tone-v1"
V2 = "contextual-esa-tone-v2"
QUOTE = ("Little smiley cat there .\nUm and this would be because they're very independent ,\n"
         "uh they're very intelligent compared , to dogs maybe .\nUm and they can be very very affectionate .")


def response(text, occurrence=1, location="source", category="omission"):
    return {"esa_score": 25, "rationale": "Meaning is missing", "spans": [
        {"severity": "major", "category": category, "location": location, "text": text,
         "occurrence": occurrence, "explanation": "Missing source meaning"}]}


def test_observed_exact_quote_normalizes_but_old_wrong_offsets_stay_invalid():
    data = {"source_text": "x" * 77 + "\n" + QUOTE, "output_text": "partial translation"}
    wire = response(QUOTE)
    normalized = parse_result("esa", wire, data)
    assert normalized["spans"] == [{"severity": "major", "category": "omission", "location": "source",
                                    "text": QUOTE, "start": 78, "end": 258, "explanation": "Missing source meaning"}]
    assert normalized["esa_score"] == 25 and normalized["major_error"] is True
    old = copy.deepcopy(wire)
    old["spans"][0].pop("occurrence")
    old["spans"][0].update(start=78, end=256)
    with pytest.raises(ValueError, match="match input"):
        parse_result("esa", old, data, prompt_version=V1)
    old["spans"][0]["end"] = 258
    assert parse_result("esa", old, data, prompt_version=V1) == normalized


@pytest.mark.parametrize("text,quote,occurrence,start,end", [
    ("😀abc😀abc", "😀abc", 2, 4, 8),
    ("aaaa", "aa", 3, 2, 4),
    ("ababa", "aba", 2, 2, 5),
    ("😀한😀한", "한", 1, 1, 2),
])
@pytest.mark.parametrize("location", ["source", "output"])
def test_exact_occurrences_use_overlapping_unicode_codepoint_matches(text, quote, occurrence, start, end, location):
    data = {"source_text": text if location == "source" else "different source",
            "output_text": text if location == "output" else "different output"}
    wire = response(quote, occurrence, location, "wrong-word")
    before = copy.deepcopy(wire)
    decoded = parse_result("esa", wire, data)
    span = decoded["spans"][0]
    assert (span["start"], span["end"], span["text"]) == (start, end, quote)
    assert wire == before
    span["text"] = "changed normalized result"
    decoded["spans"].clear()
    assert wire == before


@pytest.mark.parametrize("change", [
    {"occurrence": None}, {"occurrence": True}, {"occurrence": False}, {"occurrence": 0},
    {"occurrence": -1}, {"occurrence": 1.0}, {"occurrence": "1"}, {"occurrence": 4},
    {"text": "not present"}, {"text": "é"}, {"text": None}, {"text": ""},
    {"start": 0, "end": 1}, {"start": 0}, {"end": 999},
])
def test_new_protocol_rejects_bad_occurrences_nonexact_quotes_and_offsets(change):
    wire = response("aa")
    wire["spans"][0].update(change)
    before = copy.deepcopy(wire)
    with pytest.raises(ValueError):
        parse_result("esa", wire, {"source_text": "aaaa e\u0301", "output_text": "output"})
    assert wire == before


def test_repeated_quote_without_occurrence_is_not_guessed():
    wire = response("aa")
    del wire["spans"][0]["occurrence"]
    with pytest.raises(ValueError):
        parse_result("esa", wire, {"source_text": "aaaa", "output_text": "output"})


def test_nonempty_omission_quotes_missing_source_not_existing_output():
    wire = response("present", location="output")
    with pytest.raises(ValueError, match="missing source"):
        parse_result("esa", wire, {"source_text": "missing", "output_text": "present"})


@pytest.mark.parametrize("source,output,location,category,occurrence,accepted", [
    ("missing", "", "output", "omission", 1, True),
    ("missing", "present", "output", "omission", 1, False),
    ("", "", "source", "omission", 1, False),
    ("missing", "", "output", "wrong-word", 1, False),
    ("missing", "", "output", "omission", 2, False),
])
def test_empty_quote_is_only_entirely_empty_output_omission(source, output, location, category, occurrence, accepted):
    wire = response("", occurrence, location, category)
    data = {"source_text": source, "output_text": output}
    if not accepted:
        with pytest.raises(ValueError):
            parse_result("esa", wire, data)
    else:
        result = parse_result("esa", json.dumps(wire), data)
        assert (result["spans"][0]["start"], result["spans"][0]["end"]) == (0, 0)


def legacy_plan(root):
    plan = json.loads((ROOT / "tests/fixtures/quality_v1_plan.json").read_text(encoding="utf-8"))
    dump(root / "quality-plan.json", plan)
    return plan


class LegacyJudge(Judge):
    def call(self, prompt, call_id):
        envelope = super().call(prompt, call_id)
        result = envelope["content"]
        if "esa_score" in result:
            data = json.loads(prompt["messages"][1]["content"])
            span = {"severity": "major", "category": "omission", "location": "source",
                    "text": data["source_text"], "start": 0, "end": len(data["source_text"]),
                    "explanation": "Controlled legacy source omission"}
            if self.mode == "bad-offset":
                span["end"] -= 1
            result["spans"] = [span]
        return envelope


def test_legacy_pending_plan_resumes_exact_prompt_strictly_and_retains_failed_history(tmp_path):
    root = tmp_path / "old"
    frozen = legacy_plan(root)
    frozen_bytes = (root / "quality-plan.json").read_bytes()
    assert load_plan(root) == frozen
    assert status(root)["pending_or_unresolved_for_model"] == 5
    first = score(root, LegacyJudge(mode="bad-offset"), "synthetic-v1", limit=1)
    assert first["call_states"] == {"failed": 1}
    assert first["calls"][0]["result"] is None
    assert build_report(root)["sanity"][0]["status"] == "missing"
    judge = LegacyJudge()
    resumed = score(root, judge, "synthetic-v1", retry_unresolved=True)
    assert resumed["completed_for_model"] == 5
    assert resumed["calls"][0] == first["calls"][0]
    assert judge.requests == [job["prompt"] for job in frozen["jobs"]]
    assert (root / "quality-plan.json").read_bytes() == frozen_bytes
    report = build_report(root)
    assert report["version"] == V1
    assert report["records"][0]["esa"]["major_error"] is True
    assert report["execution"]["calls"][0]["state"] == "failed"
    fresh = LegacyJudge()
    assert score(root, fresh, "synthetic-v1")["completed_for_model"] == 5
    assert fresh.requests == []
    with pytest.raises(ValueError, match="new root"):
        prepare([input_report(tmp_path / "input.json")], root)
    assert (root / "quality-plan.json").read_bytes() == frozen_bytes


def test_legacy_queue_rejects_new_wire_response_instead_of_promoting_decoder(tmp_path):
    root = tmp_path / "old"
    legacy_plan(root)
    result = score(root, Judge(), "synthetic-v1", limit=1)
    assert result["call_states"] == {"failed": 1}
    assert result["calls"][0]["result"] is None
    assert result["calls"][0]["raw"]["content"]["spans"][0]["occurrence"] == 1


def test_new_prompt_never_reuses_old_model_result_for_same_input(tmp_path):
    old_root = tmp_path / "old"
    old = legacy_plan(old_root)
    previous = score(old_root, LegacyJudge(), "synthetic-v1", limit=1)["calls"][0]
    root = tmp_path / "new"
    current = prepare([input_report(tmp_path / "input.json")], root)
    assert current["version"] == V2
    assert current["jobs"][0]["input_hash"] == old["jobs"][0]["input_hash"]
    assert current["jobs"][0]["prompt_hash"] != old["jobs"][0]["prompt_hash"]
    store = QualityStore(root)
    try:
        call = store.start(old["jobs"][0], "synthetic-v1", LegacyJudge.provenance)
        store.raw(call, previous["raw"])
        store.finish(call, "completed", previous["raw"], previous["result"])
    finally:
        store.close()
    judge = Judge()
    state = score(root, judge, "synthetic-v1")
    assert len(judge.requests) == state["jobs"] == 5
    assert state["completed_for_model"] == 5
    assert len(state["calls"]) == 6
    assert judge.requests == [job["prompt"] for job in current["jobs"]]


@pytest.mark.parametrize("corruption", ["unknown-version", "mixed-job-version", "binding", "prompt-hash"])
def test_stored_protocol_binding_and_job_versions_fail_closed(tmp_path, corruption):
    root = tmp_path / "old"
    plan = legacy_plan(root)
    if corruption == "unknown-version":
        plan["version"] = "contextual-esa-tone-v999"
    elif corruption == "mixed-job-version":
        plan["jobs"][0]["prompt"]["version"] = V2
        plan["jobs"][0]["prompt_hash"] = fingerprint(plan["jobs"][0]["prompt"])
    elif corruption == "prompt-hash":
        plan["jobs"][0]["prompt_hash"] = "wrong"
    else:
        plan["limitations"].append("changed without binding")
    if corruption != "binding":
        plan["binding"] = fingerprint({key: value for key, value in plan.items() if key != "binding"})
    dump(root / "quality-plan.json", plan)
    with pytest.raises(ValueError):
        load_plan(root)


def test_unknown_decoder_protocol_is_rejected():
    with pytest.raises(ValueError, match="version"):
        parse_result("esa", response("source"), {"source_text": "source", "output_text": "output"}, prompt_version="unknown")
