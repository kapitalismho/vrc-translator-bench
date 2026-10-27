"""Independent synthetic application, deliberately survives controller exit."""
from __future__ import annotations

import argparse
import json
import socketserver
import threading
from pathlib import Path

from controlled_adapter import FixtureApplication
from bench.storage import atomic_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--scenario", required=True, type=Path)
    parser.add_argument("--ready", required=True, type=Path)
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    app = FixtureApplication(args.state, json.loads(args.scenario.read_text(encoding="utf-8")))

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            request = json.loads(self.rfile.readline())
            try:
                if request["method"] == "shutdown":
                    threading.Thread(target=server.shutdown, daemon=True).start()
                    result = {}
                else:
                    result = app.call(request["method"], request["params"], request.get("controller_pid", 0))
                reply = {"id": request["id"], "result": result}
            except Exception as error:
                reply = {"id": request["id"], "error": {"kind": "operational", "message": str(error)}}
            self.wfile.write((json.dumps(reply) + "\n").encode())

    try:
        with socketserver.ThreadingTCPServer(("127.0.0.1", args.port), Handler) as server:
            server.daemon_threads = True
            atomic_json(args.ready, {"pid": app.state["pid"], "port": server.server_address[1]})
            server.serve_forever(poll_interval=0.02)
    finally:
        app.close()


if __name__ == "__main__":
    main()
