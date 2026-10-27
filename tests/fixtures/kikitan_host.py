"""Local synthetic Kikitan wire peer; never imports an installed app/provider."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time

from websockets.sync.server import serve

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bench.storage import atomic_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--scenario", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    scenario = json.loads(args.scenario.read_text(encoding="utf-8"))
    if scenario.get("fail_startup"):
        return  # no WebSocket, no provider, actual owned process exit
    status = 0
    clients = set()
    lock = threading.RLock()

    def receipt(action, **details):
        with args.events.open("a", encoding="utf-8") as target:
            target.write(json.dumps({"action": action, "pid": os.getpid(), "t_ns": time.perf_counter_ns(), **details}) + "\n")

    def state():
        return json.dumps({"method": "state", "data": json.dumps({"status": status, "config": config,
                          "microphones": [{"name": "synthetic-cable-capture", "default": False}], "app_version": "synthetic-wire-peer"})})

    def connected(ws):
        nonlocal status
        with lock:
            clients.add(ws)
            receipt("connected", clients=len(clients))
        try:
            for frame in ws:
                value = json.loads(frame)
                method, data = value["method"], value["data"]
                with lock:
                    receipt(method, data=data if method == "control" else None, clients=len(clients))
                    if method == "control":
                        if data == "OFF":
                            status = 0
                        elif scenario.get("crash_on_start"):
                            os._exit(19)
                        elif scenario.get("provider_error"):
                            ws.send(json.dumps({"method": "notification", "data": json.dumps({"level": 2, "msg": "private-provider-secret-marker"})}))
                        else:
                            status = 2
                            def later():
                                time.sleep(.3)
                                with lock:
                                    if status == 2:
                                        for current in list(clients):
                                            current.send(json.dumps({"method": "recognition", "data": json.dumps({
                                                "transcription": "fixture source continued", "translation": "本地合成🦊修正", "final": True})}))
                            threading.Thread(target=later, daemon=True).start()
                            for client in list(clients):
                                client.send(json.dumps({"method": "recognition", "data": json.dumps({
                                    "transcription": "fixture source", "translation": "本地合成🦊", "final": False})}))
                        for client in list(clients):
                            client.send(state())
                    elif method == "update_config":
                        update = json.loads(data)
                        if not scenario.get("refuse_configuration"):
                            config[update["field"]] = update["value"]
                            if update["field"] in ("recognizer", "translator"):
                                other = "translator" if update["field"] == "recognizer" else "recognizer"
                                if update["value"] == 2:
                                    config[other] = 2
                                elif config.get(other) == 2:
                                    config[other] = 0
                            atomic_json(args.config, config)
                        for client in list(clients):
                            client.send(state())
                    elif method == "send_app_state":
                        ws.send(state())
                    elif method == "quit":
                        if status != 0:
                            receipt("unsafe_quit_while_running")
                        if not scenario.get("hang_quit"):
                            os._exit(0)
                    else:
                        receipt("unexpected_control")
        finally:
            with lock:
                clients.discard(ws)

    with serve(connected, "127.0.0.1", 18378) as server:
        receipt("ready")
        server.serve_forever()


if __name__ == "__main__":
    main()
