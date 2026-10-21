import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bench.quality_judge import bridge_spec


BASE = {"kind": "chatgpt-sign-in-bridge", "route": "Sign in with ChatGPT"}
BRIDGE = Path(__file__).resolve().parents[1] / "bench" / "quality_bridge.mjs"


@pytest.fixture
def installed_spec(tmp_path, monkeypatch):
    root = tmp_path / "pi-ai"
    root.mkdir()
    (root / "package.json").write_text('{"name":"@oh-my-pi/pi-ai","version":"18.12.3"}', encoding="utf-8")
    monkeypatch.setattr("bench.quality_judge.shutil.which", lambda _: str(tmp_path / "bun.exe"))
    return {**BASE, "package_root": str(root)}


def test_spec_selects_only_bundled_bridge_and_subscription(installed_spec):
    spec = bridge_spec(installed_spec)
    assert spec["kind"] == BASE["kind"]
    assert spec["route"] == "Sign in with ChatGPT"
    assert spec["command"][1:3] == ["--no-env-file", str(BRIDGE)]
    assert spec["command"][-4:] == ["--model", "gpt-6-astra", "--timeout-seconds", "180"]
    assert Path(spec["bridge_path"]) == BRIDGE
    assert spec["timeout_seconds"] == 190


@pytest.mark.parametrize("options", [
    {"model": "gpt-6-luna"}, {"command": ["node", "arbitrary.js"]}, {"provider": "openai"},
    {"api_key": "not-a-real-key"}, {"route": "paid API"}, {"runtime": "node"},
    {"timeout_seconds": 0}, {"timeout_seconds": float("inf")}, {"timeout_seconds": True},
    {"credential_id": 0}, {"credential_id": True}, {"auth_db": "does-not-exist.db"},
])
def test_spec_rejects_route_model_execution_and_credential_substitutions(installed_spec, options, monkeypatch):
    if options.get("runtime") == "node":
        monkeypatch.setattr("bench.quality_judge.shutil.which", lambda _: "node.exe")
    with pytest.raises(ValueError):
        bridge_spec({**installed_spec, **options})


def bridge_operation(operation, data):
    bun = shutil.which("bun")
    if not bun:
        pytest.skip("Bridge contract checks require Bun; no live inference is performed")
    code = f"import {{ inferenceEnvelope, validateRequest, validatePayload }} from {json.dumps(BRIDGE.as_uri())};\n"
    code += "const input=JSON.parse(await Bun.stdin.text());\n"
    if operation == "envelope":
        code += "process.stdout.write(JSON.stringify(inferenceEnvelope(input.raw,input.outcome)));"
    else:
        code += "try { const context=validateRequest(input.request); if(input.payload)validatePayload(input.payload,context); process.stdout.write(JSON.stringify({accepted:true,context})); } catch { process.stdout.write(JSON.stringify({accepted:false})); }"
    result = subprocess.run([bun, "--no-env-file", "--eval", code], input=json.dumps(data), capture_output=True,
                            text=True, encoding="utf-8", timeout=20)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def event(value):
    data = json.dumps(value)
    return {"event": value["type"], "data": data, "raw": ["data: " + data]}


def response(model="gpt-6-astra", **changes):
    return {"id": "synthetic-response-id", "model": model, "status": "completed", "created_at": 1792530000,
            "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": '{"score":100}'}]}], **changes}


def test_raw_terminal_identity_and_date_are_preserved_not_configured_alias():
    terminal = event({"type": "response.completed", "response": response("gpt-6-astra-2026-10-01")})
    raw = {"events": [terminal], "response_metadata": {"status": 200, "date": "Tue, 20 Oct 2026 12:00:00 GMT"}}
    result = bridge_operation("envelope", {"raw": raw})
    assert result["status"] == "completed"
    assert result["actual_model"] == "gpt-6-astra-2026-10-01"
    assert result["model_identity_evidence"]["source"] == "raw inference response.model"
    assert result["model_identity_evidence"]["event_index"] == 0
    assert result["response_date"] == datetime.fromtimestamp(1792530000, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    assert result["content"] == '{"score":100}'
    assert result["raw"] == raw


def test_created_alias_without_terminal_identity_remains_unresolved():
    terminal_response = response()
    terminal_response.pop("model")
    raw = {"events": [event({"type": "response.created", "response": response()}),
                      event({"type": "response.completed", "response": terminal_response})]}
    result = bridge_operation("envelope", {"raw": raw})
    assert result["status"] == "unresolved"
    assert result["actual_model"] is None
    assert result["model_identity_evidence"] is None
    assert result["raw"] == raw


@pytest.mark.parametrize("raw,outcome,expected", [
    ({"events": [event({"type": "response.created", "response": response()})]}, {}, "unresolved"),
    ({"events": [event({"type": "response.completed", "response": response("gpt-6-luna")})]}, {}, "unresolved"),
    ({"events": [event({"type": "response.completed", "response": response(output=[])})]}, {}, "unresolved"),
    ({"events": [event({"type": "response.incomplete", "response": response(status="incomplete")})]}, {}, "unresolved"),
    ({"events": [event({"type": "response.failed", "response": response(status="failed")})]}, {}, "failed"),
    ({"events": [], "response_metadata": {"status": 429}, "http_error": '{"error":{"code":"usage_limit_reached"}}'}, {}, "quota"),
    ({"events": [event({"type": "error", "code": "usage_limit_reached"})]}, {}, "quota"),
    ({"events": [event({"type": "response.completed", "response": response()})]}, {"redispatch_blocked": True}, "unresolved"),
])
def test_failure_partial_empty_quota_and_reroute_cannot_be_success(raw, outcome, expected):
    result = bridge_operation("envelope", {"raw": raw, "outcome": outcome})
    assert result["status"] == expected
    assert result["raw"] == raw


def test_no_date_exposure_is_not_replaced_with_observer_date():
    value = response()
    value.pop("created_at")
    result = bridge_operation("envelope", {"raw": {"events": [event({"type": "response.completed", "response": value})],
        "observed_end_utc": "2026-10-21T00:00:00Z"}})
    assert result["status"] == "completed"
    assert result["response_date"] is None


def request():
    return {"schema_version": 1, "request_id": 1, "prompt": {"version": "synthetic-v1", "messages": [
        {"role": "system", "content": "Return a structured translation judgment."},
        {"role": "user", "content": '{"source":"Hello","output":"안녕하세요"}'},
    ]}}


def test_context_has_only_current_blinded_messages_and_no_tools():
    result = bridge_operation("validate", {"request": request()})
    assert result["accepted"] is True
    assert result["context"]["tools"] == []
    assert result["context"]["systemPrompt"] == [request()["prompt"]["messages"][0]["content"]]
    assert len(result["context"]["messages"]) == 1
    assert result["context"]["messages"][0]["content"] == request()["prompt"]["messages"][1]["content"]


@pytest.mark.parametrize("change", ["tool", "history", "instructions", "paid-tier", "extra-input"])
def test_wire_payload_rejects_contamination(change):
    prompt = request()
    payload = {"model": "gpt-6-astra", "store": False, "instructions": prompt["prompt"]["messages"][0]["content"],
               "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt["prompt"]["messages"][1]["content"]}]}]}
    if change == "tool":
        payload["tools"] = [{"type": "web_search"}]
    elif change == "history":
        payload["previous_response_id"] = "old-conversation"
    elif change == "instructions":
        payload["instructions"] += " Additional inherited instructions."
    elif change == "paid-tier":
        payload["service_tier"] = "priority"
    else:
        payload["input"].append({"role": "developer", "content": "repo instructions"})
    assert bridge_operation("validate", {"request": prompt, "payload": payload})["accepted"] is False
