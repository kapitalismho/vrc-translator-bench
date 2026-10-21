import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench import quality_metricx
from bench.cli import main
from bench.quality import load_plan

parser = argparse.ArgumentParser()
parser.add_argument("--controlled-metricx-status", choices=("completed", "unavailable", "failed", "oversized"), default="completed")
control, arguments = parser.parse_known_args()
if arguments[:2] != ["quality", "score"] or "--metricx-only" not in arguments:
    raise ValueError("Controlled repair fixture supports only MetricX-only CLI scoring")
root = arguments[arguments.index("--root") + 1]
if load_plan(root)["synthetic"] is not True:
    raise ValueError("Controlled repair fixture requires an explicitly synthetic quality plan")


class ControlledMetricX:
    def __init__(self, model_path=None, device="cpu", allow_download=False):
        self.state = control.controlled_metricx_status

    def cache_identity(self):
        return {"synthetic": True, "fixture": "quality_repair_cli", "state": self.state}

    def score(self, source, output):
        return {"status": self.state, "score": 7.5 if self.state == "completed" else None,
                "reason": "Controlled synthetic MetricX outcome, not selected checkpoint inference", "input_tokens": None,
                "provenance": {"synthetic": True, "cache_identity": self.cache_identity()},
                "raw": {"synthetic": True, "source": source, "output": output}}


quality_metricx.MetricX = ControlledMetricX
raise SystemExit(main(arguments))
