from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .quality_process import UnsupportedJudgePlatform, run_command
from .storage import digest


def invalid_constant(value):
    raise ValueError(f"Nonfinite JSON constant: {value}")


class CommandTransport:
    def __init__(self, specification):
        self.specification = specification
        self.synthetic = specification.get("kind") == "synthetic-command"
        if specification.get("kind") not in ("synthetic-command", "chatgpt-sign-in-bridge"):
            raise ValueError("Only controlled synthetic or selected Sign in with ChatGPT bridge transports are supported; no paid API fallback")
        command = specification.get("command")
        if not isinstance(command, list) or not command or any(not isinstance(value, str) or not value for value in command):
            raise ValueError("Judge transport command must be an argument vector")
        self.command = command
        self.timeout = specification.get("timeout_seconds", 180)
        if not isinstance(self.timeout, (int, float)) or isinstance(self.timeout, bool) or self.timeout <= 0:
            raise ValueError("Judge transport timeout must be positive")
        if not self.synthetic and specification.get("route") != "Sign in with ChatGPT":
            raise ValueError("Real transport must use the selected subscription route")
        self.provenance = {"kind": specification["kind"], "synthetic": self.synthetic,
                           "route": "controlled synthetic; not a judge observation" if self.synthetic else "Sign in with ChatGPT",
                           "command": command, "bridge_sha256": specification.get("bridge_sha256"),
                           "timeout_seconds": self.timeout,
                           "process_containment": "windows-job-kill-on-close" if os.name == "nt" else
                               "synthetic-only; no parent-death guarantee" if self.synthetic else "unsupported-real-judge-platform"}

    def call(self, request, call_id):
        environment = os.environ.copy()
        for name in ("OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN", "PI_REQ_DEBUG"):
            environment.pop(name, None)
        payload = {"schema_version": 1, "request_id": call_id, "prompt": request}
        try:
            result = run_command(self.command, input=json.dumps(payload, ensure_ascii=False), timeout=self.timeout,
                                 env=environment, synthetic=self.synthetic)
        except subprocess.TimeoutExpired as error:
            def text(value):
                return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
            return {"status": "unresolved", "reason": "Judge transport timed out; admission/completion unknown",
                    "raw": {"stdout": text(error.stdout), "stderr": text(error.stderr)}}
        except UnsupportedJudgePlatform as error:
            return {"status": "unavailable", "reason": str(error), "raw": None}
        raw = {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
        try:
            envelope = json.loads(result.stdout, parse_constant=invalid_constant)
        except (ValueError, TypeError):
            return {"status": "unresolved", "reason": "Judge bridge returned no complete JSON envelope; admission/completion unknown", "raw": raw}
        if not isinstance(envelope, dict):
            return {"status": "failed", "reason": "Judge bridge envelope is not an object", "raw": raw}
        envelope["transport_raw"] = raw
        if result.returncode and envelope.get("status", "completed") == "completed":
            envelope["status"] = "unresolved"
            envelope["reason"] = "Transport exited nonzero despite purported completed response"
        return envelope


def load_transport(path):
    path = Path(path)
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("kind") == "chatgpt-sign-in-bridge":
        from .quality_judge import bridge_spec
        supplied = bridge_spec(spec)
        supplied["bridge_sha256"] = digest(supplied["bridge_path"])
        return CommandTransport(supplied)
    return CommandTransport(spec)
