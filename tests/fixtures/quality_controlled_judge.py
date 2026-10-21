import argparse
import json
import sys
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--mode", default="valid")
parser.add_argument("--sentinel")
args = parser.parse_args()
request = json.load(sys.stdin)
if args.mode == "block":
    Path(args.sentinel).write_text("synthetic request admitted", encoding="utf-8")
    time.sleep(60)
if args.mode == "quota":
    print(json.dumps({"status": "quota", "reason": "Synthetic controlled quota, not provider evidence", "raw": request}))
    sys.exit(0)
data = json.loads(request["prompt"]["messages"][1]["content"])
if "tone" in request["prompt"]["messages"][0]["content"].lower() and "esa_score" not in request["prompt"]["messages"][0]["content"]:
    result = {"politeness_register": 3, "rudeness_risk": 2, "naturalness": 4, "rationale": "Controlled synthetic tone result; no quality observation"}
else:
    result = {"esa_score": 20, "spans": [{"severity": "major", "category": "omission", "location": "source", "occurrence": 1,
                                         "text": data["source_text"], "explanation": "Controlled synthetic annotation; not actual judging"}],
              "rationale": "Controlled synthetic ESA result; no quality observation"}
print(json.dumps({"status": "completed", "actual_model": "synthetic-judge-v1", "model_identity_evidence": {"synthetic": True, "returned_field": "actual_model"},
                  "content": "malformed" if args.mode == "malformed" else result, "response_date": None,
                  "raw": {"synthetic": True, "request_id": request["request_id"]}}, ensure_ascii=False))
