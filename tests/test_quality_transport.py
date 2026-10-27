from __future__ import annotations

import json
import sys

import pytest

from bench.quality_transport import CommandTransport


PROMPT = {"version": "controlled-transport-v1", "messages": [
    {"role": "system", "content": "Return a controlled structured response."},
    {"role": "user", "content": '{"source":"Hello","output":"안녕하세요 🌍"}'},
]}


def command(stdout, returncode=0):
    return [sys.executable, "-c",
            "import json,sys; request=json.load(sys.stdin); "
            "assert request['schema_version']==1; assert request['request_id']==17; "
            "sys.stdout.write(sys.argv[1]); sys.stderr.write('controlled diagnostic\\n'); "
            "raise SystemExit(int(sys.argv[2]))", stdout, str(returncode)]


def call(stdout, returncode=0):
    transport = CommandTransport({"kind": "synthetic-command", "command": command(stdout, returncode)})
    return transport.call(PROMPT, 17)


@pytest.mark.parametrize("stdout,state", [
    ("not a complete JSON envelope", "unresolved"),
    ('{"status":"completed"', "unresolved"),
    ('{"status":"completed","content":NaN}', "unresolved"),
    ('{"status":"completed","content":Infinity}', "unresolved"),
    ("null", "failed"),
    ("[]", "failed"),
    ('"completed"', "failed"),
])
def test_malformed_or_nonobject_envelope_retains_streams_not_success(stdout, state):
    envelope = call(stdout)
    assert envelope["status"] == state
    assert envelope["raw"] == {"stdout": stdout, "stderr": "controlled diagnostic\n", "returncode": 0}
    assert envelope.get("actual_model") is None
    assert envelope.get("content") is None


@pytest.mark.parametrize("state", ["quota", "unavailable", "failed", "unresolved"])
def test_provider_failure_and_unknown_outcomes_remain_distinct_with_raw_evidence(state):
    supplied = {"status": state, "reason": "Controlled outcome; not provider evidence",
                "actual_model": None, "raw": {"synthetic": True, "event": "controlled-terminal-or-interruption"}}
    stdout = json.dumps(supplied)
    envelope = call(stdout)
    assert envelope == {**supplied, "transport_raw": {
        "stdout": stdout, "stderr": "controlled diagnostic\n", "returncode": 0}}
    assert envelope.get("content") is None


@pytest.mark.parametrize("include_status", [True, False])
def test_nonzero_exit_cannot_promote_purported_completed_envelope(include_status):
    supplied = {"actual_model": "controlled-returned-model", "content": {"synthetic": True},
                "raw": {"synthetic": True}}
    if include_status:
        supplied["status"] = "completed"
    stdout = json.dumps(supplied)
    envelope = call(stdout, 23)
    assert envelope["status"] == "unresolved"
    assert "nonzero" in envelope["reason"]
    assert envelope["actual_model"] == supplied["actual_model"]
    assert envelope["content"] == supplied["content"]
    assert envelope["raw"] == supplied["raw"]
    assert envelope["transport_raw"] == {"stdout": stdout, "stderr": "controlled diagnostic\n", "returncode": 23}


def test_nonzero_provider_failure_keeps_failure_not_completion_unknown():
    supplied = {"status": "failed", "reason": "Controlled explicit provider rejection", "raw": {"synthetic": True}}
    envelope = call(json.dumps(supplied), 23)
    assert envelope["status"] == "failed"
    assert envelope["reason"] == supplied["reason"]
    assert envelope["raw"] == supplied["raw"]
    assert envelope["transport_raw"]["returncode"] == 23


def test_request_is_complete_unicode_and_credential_environment_is_removed(monkeypatch):
    credential_names = ("OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN", "PI_REQ_DEBUG")
    for name in credential_names:
        monkeypatch.setenv(name, "controlled-not-a-real-credential")
    monkeypatch.setenv("QUALITY_TEST_ALLOWED", "controlled-nonsecret")
    expected_request = {"schema_version": 1, "request_id": 17, "prompt": PROMPT}
    response = {"status": "completed", "actual_model": "controlled-returned-model",
                "model_identity_evidence": {"synthetic": True}, "content": "independent controlled response",
                "raw": {"synthetic": True, "request_contract_accepted": True}}
    code = (
        "import json,os,sys; request=json.load(sys.stdin); "
        "assert request==json.loads(sys.argv[1]); "
        "assert all(name not in os.environ for name in json.loads(sys.argv[2])); "
        "assert os.environ['QUALITY_TEST_ALLOWED']=='controlled-nonsecret'; print(sys.argv[3])"
    )
    transport = CommandTransport({"kind": "synthetic-command", "command": [sys.executable, "-c", code,
        json.dumps(expected_request, ensure_ascii=False), json.dumps(credential_names), json.dumps(response)]})
    envelope = transport.call(PROMPT, 17)
    assert {key: value for key, value in envelope.items() if key != "transport_raw"} == response
    assert envelope["transport_raw"]["returncode"] == 0
    assert envelope["transport_raw"]["stderr"] == ""


def test_transport_preserves_unparsed_content_for_its_consumer():
    supplied = {"status": "completed", "actual_model": "controlled-returned-model",
                "model_identity_evidence": {"synthetic": True}, "content": "not a judgment JSON object",
                "raw": {"synthetic": True}}
    envelope = call(json.dumps(supplied))
    assert envelope["content"] == supplied["content"]
    assert envelope["raw"] == supplied["raw"]
    assert envelope["status"] == "completed"
    # Terminal transport success is not a claim that a future rubric consumer accepted the content.
