import argparse
import json
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=("valid", "quota"), default="valid")
parser.add_argument("--model", default="quality-repair-baseline")
parser.add_argument("--movement", action="store_true")
args = parser.parse_args()
request = json.load(sys.stdin)
if args.mode == "quota":
    print(json.dumps({"status": "quota", "reason": "Controlled synthetic repair quota; not provider evidence", "raw": {"synthetic": True}}))
    raise SystemExit(0)
data = json.loads(request["prompt"]["messages"][1]["content"])
if "esa_score" in request["prompt"]["messages"][0]["content"]:
    result = {"esa_score": 20, "spans": [{"severity": "major", "category": "omission", "location": "source", "occurrence": 1,
                                         "text": data["source_text"], "explanation": "Controlled synthetic repair annotation"}], "rationale": "Controlled synthetic response; not observed translation quality"}
    if args.movement and data["output_text"].endswith(" 0"):
        result.update(esa_score=30, spans=[])
else:
    result = {"politeness_register": 3, "rudeness_risk": 1, "naturalness": 4, "rationale": "Controlled synthetic repair response"}
print(json.dumps({"status": "completed", "actual_model": args.model, "model_identity_evidence": {"synthetic": True},
                  "response_date": None, "content": result, "raw": {"synthetic": True, "request_id": request["request_id"]}}))
