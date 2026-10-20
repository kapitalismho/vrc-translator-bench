from __future__ import annotations

import argparse
import json
import os
import socket
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    for line in sys.stdin:
        request = json.loads(line)
        request["controller_pid"] = os.getpid()
        try:
            with socket.create_connection(("127.0.0.1", args.port), timeout=5) as connection:
                stream = connection.makefile("rwb")
                stream.write((json.dumps(request) + "\n").encode("utf-8"))
                stream.flush()
                response = json.loads(stream.readline())
                stream.close()
        except (OSError, ValueError) as error:
            response = {"id": request["id"], "error": {"kind": "operational", "message": str(error)}}
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
