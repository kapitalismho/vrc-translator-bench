from __future__ import annotations

import argparse
import json
import os
import socket
import socketserver
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.osc import encode
from bench.storage import atomic_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--scenario", required=True, type=Path)
    parser.add_argument("--ready", required=True, type=Path)
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    scenario = json.loads(args.scenario.read_text(encoding="utf-8"))
    state = {"running": False, "starts": 0, "stops": 0, "pid": os.getpid(), "requests": [], "lifecycle": []}
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind(("127.0.0.1", scenario.get("source_port", 0)))
    lock = threading.RLock()
    failure = None
    def save():
        atomic_json(args.state, state)
    def emit(stage):
        behavior = scenario.get("check", {}) if stage["kind"] in ("output_check", "resume_check") else scenario.get("chunks", {}).get(stage["chunk"], {})
        if behavior.get("failure"):
            return
        time.sleep(0.025)
        with lock:
            if state["running"]:
                udp.sendto(encode("/chatbox/typing", [True]), (state["osc_host"], state["osc_port"]))
                udp.sendto(encode("/chatbox/input", [stage["chunk"] + " persistent synthetic output", True, False]),
                           (state["osc_host"], state["osc_port"]))
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            nonlocal failure
            request = json.loads(self.rfile.readline())
            method = request["method"]
            params = request["params"]
            with lock:
                state["requests"].append({"method": method, "controller_pid": request.get("controller_pid"), "t_ns": time.perf_counter_ns()})
                result = {}
                if method == "preflight":
                    result = {"ready": True, "supported": True}
                elif method == "configure":
                    state.update(params["requested_state"])
                elif method == "set_direction":
                    state["direction"] = params["direction"]
                elif method == "read_state":
                    if scenario.get("reconcile_state_error") and state["running"] and request.get("controller_pid") not in (0, state.get("start_controller_pid")):
                        save()
                        self.wfile.write((json.dumps({"id": request["id"], "error": {"kind": "operational", "message": "reconciliation state unavailable"}}) + "\n").encode("utf-8"))
                        return
                    if scenario.get("post_start_state_mismatch") and state["running"]:
                        result = {**state, "microphone": "wrong-after-start"}
                    else:
                        result = dict(state)
                elif method == "start":
                    state["running"] = True
                    state["start_controller_pid"] = request.get("controller_pid")
                    state["starts"] += 1
                    state["lifecycle"].append({"action": "start", "t_ns": time.perf_counter_ns(), "pid": os.getpid()})
                    result = {"running": True}
                    if scenario.get("start_reply_error"):
                        save()
                        self.wfile.write((json.dumps({"id": request["id"], "error": {"kind": "operational", "message": "start applied but acknowledgement failed"}}) + "\n").encode("utf-8"))
                        return
                elif method == "stop":
                    state["running"] = False
                    state["stops"] += 1
                    state["lifecycle"].append({"action": "stop", "t_ns": time.perf_counter_ns(), "pid": os.getpid()})
                    result = {"running": False}
                elif method == "osc_identity":
                    result = {"pid": os.getpid(), "source_port": udp.getsockname()[1], "synthetic": True}
                elif method == "liveness":
                    result = {"alive": True}
                    if failure:
                        result["failure"] = failure
                        failure = None
                elif method == "begin_stage":
                    stage = params["stage"]
                    state["last_stage"] = stage
                    behavior = scenario.get("check", {}) if stage["kind"] in ("output_check", "resume_check") else scenario.get("chunks", {}).get(stage["chunk"], {})
                    failure = behavior.get("failure")
                    threading.Thread(target=emit, args=(stage,), daemon=True).start()
                elif method == "shutdown":
                    threading.Thread(target=server.shutdown, daemon=True).start()
                else:
                    raise ValueError(f"Unknown synthetic application method: {method}")
                save()
                self.wfile.write((json.dumps({"id": request["id"], "result": result}) + "\n").encode("utf-8"))
    with socketserver.ThreadingTCPServer(("127.0.0.1", args.port), Handler) as server:
        server.daemon_threads = True
        save()
        atomic_json(args.ready, {"pid": os.getpid(), "port": server.server_address[1]})
        server.serve_forever(poll_interval=0.02)
    udp.close()


if __name__ == "__main__":
    main()
