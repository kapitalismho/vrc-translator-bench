from __future__ import annotations

import math
import shutil
from pathlib import Path


SELECTED_MODEL = "gpt-6-astra"
SDK_VERSION = "18.12.3"


def bridge_spec(specification):
    allowed = {"kind", "route", "model", "runtime", "package_root", "auth_db", "credential_id", "timeout_seconds"}
    unknown = set(specification) - allowed
    if unknown:
        raise ValueError(f"Unsupported ChatGPT bridge options: {', '.join(sorted(unknown))}")
    if specification.get("kind") != "chatgpt-sign-in-bridge" or specification.get("route") != "Sign in with ChatGPT":
        raise ValueError("The judge bridge requires the selected Sign in with ChatGPT route")
    if specification.get("model", SELECTED_MODEL) != SELECTED_MODEL:
        raise ValueError(f"The selected judge is {SELECTED_MODEL}; no model fallback is permitted")
    timeout = specification.get("timeout_seconds", 180)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Judge bridge timeout_seconds must be positive and finite")
    runtime = specification.get("runtime", "bun")
    if not isinstance(runtime, str) or not runtime:
        raise ValueError("Judge bridge runtime must identify the Bun executable")
    executable = shutil.which(runtime)
    if executable is None or Path(executable).name.lower() not in {"bun", "bun.exe"}:
        raise ValueError("Install Bun >=1.3.14 and select its executable with runtime")
    package_root = specification.get("package_root", Path.home() / ".bun" / "install" / "global" / "node_modules" / "@oh-my-pi" / "pi-ai")
    if not isinstance(package_root, (str, Path)) or not str(package_root):
        raise ValueError("package_root must identify the installed @oh-my-pi/pi-ai package")
    package_root = Path(package_root).expanduser().resolve()
    if not (package_root / "package.json").is_file():
        raise ValueError(f"Install @oh-my-pi/pi-ai@{SDK_VERSION} and specify its package_root")
    bridge = Path(__file__).with_name("quality_bridge.mjs").resolve()
    command = [executable, "--no-env-file", str(bridge), "--package-root", str(package_root), "--model", SELECTED_MODEL,
               "--timeout-seconds", str(timeout)]
    auth_db = specification.get("auth_db")
    if auth_db is not None:
        if not isinstance(auth_db, str) or not auth_db:
            raise ValueError("auth_db must identify an existing managed authentication database")
        auth_db = Path(auth_db).expanduser().resolve()
        if not auth_db.is_file():
            raise ValueError("auth_db must already exist; sign in with the supported omp client first")
        command.extend(["--auth-db", str(auth_db)])
    credential_id = specification.get("credential_id")
    if credential_id is not None:
        if isinstance(credential_id, bool) or not isinstance(credential_id, int) or credential_id <= 0:
            raise ValueError("credential_id must be a positive stored OAuth row identifier")
        command.extend(["--credential-id", str(credential_id)])
    return {"kind": "chatgpt-sign-in-bridge", "route": "Sign in with ChatGPT", "command": command,
            "bridge_path": str(bridge), "timeout_seconds": timeout + 10}
