from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.osc import encode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--scenario", required=True, type=Path)
    args = parser.parse_args()
    scenario = json.loads(args.scenario.read_text(encoding="utf-8"))
    state = json.loads(args.state.read_text(encoding="utf-8")) if args.state.exists() else {"running": False, "starts": 0, "stops": 0}
    state["running"] = False
    alive = True
    output_lock = threading.Lock()
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind(("127.0.0.1", scenario.get("source_port", 0)))
    def reply(value):
        with output_lock:
            print(json.dumps(value), flush=True)
    def save():
        args.state.write_text(json.dumps(state), encoding="utf-8")
    def emit(stage):
        behavior = scenario.get("chunks", {}).get(stage["chunk"], {}) if stage["kind"] not in ("output_check", "resume_check") else scenario.get("check", {})
        events = behavior.get("events", [{"delay": 0.025, "address": "/chatbox/typing", "args": [True]},
                                         {"delay": 0.04, "address": "/chatbox/input", "args": [stage["chunk"] + " translation", True, False]}])
        start = time.perf_counter()
        for event in sorted(events, key=lambda item: item["delay"]):
            time.sleep(max(0, start + event["delay"] - time.perf_counter()))
            if event.get("failure"):
                reply({"event": "product_failure", **event["failure"]})
            elif event.get("invalid"):
                reply({"event": "operational_error", "message": event["invalid"]})
            else:
                udp.sendto(encode(event["address"], event["args"]), (state["osc_host"], state["osc_port"]))
    for line in sys.stdin:
        request = json.loads(line)
        method = request["method"]
        params = request["params"]
        result = {}
        if method == "preflight":
            result = {"ready": True, "supported": params["direction"] not in scenario.get("unsupported", [])}
        elif method == "configure":
            if not scenario.get("refuse_configuration"):
                state.update(params["requested_state"])
                save()
        elif method == "set_direction":
            if not scenario.get("refuse_configuration"):
                state["direction"] = params["direction"]
                save()
        elif method == "read_state":
            result = dict(state)
        elif method == "start":
            alive = True
            state["running"] = True
            state["starts"] += 1
            state.setdefault("lifecycle", []).append({"action": "start", "t_ns": time.perf_counter_ns()})
            save()
            result = {"running": True}
        elif method == "stop":
            state["running"] = False
            state["stops"] += 1
            state.setdefault("lifecycle", []).append({"action": "stop", "t_ns": time.perf_counter_ns()})
            save()
            result = {"running": False}
        elif method == "osc_identity":
            result = {"pid": os.getpid(), "source_port": udp.getsockname()[1], "synthetic": True}
        elif method == "liveness":
            result = {"alive": alive}
        elif method == "begin_stage":
            state["last_stage"] = params["stage"]
            save()
            threading.Thread(target=emit, args=(params["stage"],), daemon=True).start()
        else:
            reply({"id": request["id"], "error": {"kind": "operational", "message": "Unknown method"}})
            continue
        reply({"id": request["id"], "result": result})
    udp.close()


if __name__ == "__main__":
    main()
