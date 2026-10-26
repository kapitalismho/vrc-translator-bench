"""Isolated synthetic episode controller; never launches an installed app/provider."""
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
from bench.storage import atomic_json


class FixtureApplication:
    def __init__(self, state_path, scenario):
        self.path, self.scenario = state_path, scenario
        self.state = {"running": False, "starts": 0, "stops": 0, "resets": 0,
                      "pid": os.getpid(), "requests": [], "lifecycle": []}
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.bind(("127.0.0.1", scenario.get("source_port", 0)))
        self.lock = threading.RLock()
        self.failure = None
        self.generation = 0
        self.collector = None
        self.save()

    def save(self):
        atomic_json(self.path, self.state)

    def emit(self, spec, generation):
        behavior = self.scenario.get("episodes", {}).get(spec["episode_id"], {})
        events = behavior.get("events", [{"delay": 0.3, "text": "synthetic translation"}])
        started = time.perf_counter()
        for event in events:
            time.sleep(max(0, started + event["delay"] - time.perf_counter()))
            with self.lock:
                if generation != self.generation or not self.state["running"]:
                    return
                if event.get("failure"):
                    self.failure = event["failure"]
                elif event.get("invalid"):
                    self.failure = {"operational": event["invalid"]}
                else:
                    address = event.get("address", "/microphone/translated" if self.collector["family"] == "kikitan" else "/chatbox/input")
                    arguments = event.get("args", [event["text"]] if self.collector["family"] == "kikitan" else [event["text"], True, False])
                    self.udp.sendto(encode(address, arguments), (self.collector["host"], self.collector["port"]))

    def call(self, method, params, controller=0):
        with self.lock:
            self.state["requests"].append({"method": method, "controller": controller, "t_ns": time.perf_counter_ns()})
            result = {}
            if method == "preflight":
                self.collector = params["profile"]["collector"]
                result = {"ready": True, "supported": not self.scenario.get("unsupported", False),
                          "metadata": {"model": self.scenario.get("model"), "synthetic": True}}
            elif method == "reset_session":
                self.generation += 1
                self.state["resets"] += 1
                self.failure = None
                result = {"reset": True, "basis": "synthetic_new_conversation", "evidence": ["fixture generation reset"]}
            elif method == "configure":
                if not self.scenario.get("refuse_configuration"):
                    self.state.update(params["requested_state"])
            elif method == "read_state":
                if self.scenario.get("reconcile_state_error") and self.state["running"] and controller not in (0, self.state.get("start_controller")):
                    raise ValueError("reconciliation state unavailable")
                result = dict(self.state)
                if self.scenario.get("post_start_state_mismatch") and self.state["running"]:
                    result["voice_output"] = True
            elif method == "start":
                self.state["running"] = True
                self.state["start_controller"] = controller
                self.state["starts"] += 1
                self.state["lifecycle"].append({"action": "start", "t_ns": time.perf_counter_ns()})
                self.save()
                if self.scenario.get("start_reply_error"):
                    raise ValueError("start applied but acknowledgement failed")
                result = {"running": True}
            elif method == "stop":
                self.state["running"] = False
                self.generation += 1
                self.state["stops"] += 1
                self.state["lifecycle"].append({"action": "stop", "t_ns": time.perf_counter_ns()})
                result = {"running": False}
            elif method == "identity":
                result = {"pid": os.getpid(), "source_port": self.udp.getsockname()[1], "synthetic": True}
            elif method == "liveness":
                # Clock-only fixture cannot establish actual app input opportunity.
                result = {"alive": True, "app_continuity": {"continuous": None, "evidence": [], "gaps": []},
                          "input_continuity": {"continuous": None, "evidence": [], "gaps": []}}
                if self.failure:
                    if "operational" in self.failure:
                        raise ValueError(self.failure["operational"])
                    result["failure"], self.failure = self.failure, None
            elif method == "begin_pass":
                self.state["last_pass"] = params["pass_spec"]
                threading.Thread(target=self.emit, args=(params["pass_spec"], self.generation), daemon=True).start()
            else:
                raise ValueError("Unknown episode controller method")
            self.save()
            return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--scenario", type=Path, required=True)
    args = parser.parse_args()
    app = FixtureApplication(args.state, json.loads(args.scenario.read_text(encoding="utf-8")))
    try:
        for line in sys.stdin:
            request = json.loads(line)
            try:
                reply = {"id": request["id"], "result": app.call(request["method"], request["params"], os.getpid())}
            except Exception as error:
                reply = {"id": request["id"], "error": {"kind": "operational", "message": str(error)}}
            print(json.dumps(reply), flush=True)
    finally:
        app.udp.close()


if __name__ == "__main__":
    main()
