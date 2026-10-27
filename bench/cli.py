from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .adapter import OperationalError
from .audio import Playback, calibrate
from .plan import IDENTIFIER, load_plan
from .paths import DataPaths
from .runner import Runner
from .profiles import inspect_catalog
from .storage import Ledger, atomic_json, utc_now


def parser():
    root = argparse.ArgumentParser(prog="bench", description="Episode-native translation-output capture and evidence ledger.")
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run an explicit episode/role/pass plan; clock runs are synthetic, not app admission")
    selection = run.add_mutually_exclusive_group(required=True)
    selection.add_argument("--plan", type=Path)
    selection.add_argument("--resume")
    run.add_argument("--run-id")
    run.add_argument("--root", type=Path, default=Path(".data/runs"))
    run.add_argument("--audio-backend", choices=("wasapi", "clock"), default="wasapi")
    status = commands.add_parser("status")
    status.add_argument("run_id")
    status.add_argument("--root", type=Path, default=Path(".data/runs"))
    calibration = commands.add_parser("calibrate")
    calibration.add_argument("--output", type=Path, default=Path(".data/calibration/cable.json"))
    calibration.add_argument("--output-device", required=True)
    calibration.add_argument("--input-device", required=True)
    playback = commands.add_parser("playback")
    playback.add_argument("audio", type=Path)
    playback.add_argument("--output-device", required=True)
    playback.add_argument("--output", type=Path, default=Path(".data/calibration/playback.json"))
    costs = commands.add_parser("costs", help="Reconcile local evidence into an immutable cost revision bound to an R4 report")
    costs.add_argument("--spec", type=Path, required=True)
    costs.add_argument("--output", type=Path, required=True)
    quality = commands.add_parser("quality", help="Evaluate bound episode histories; preserve incomplete quality and waiting results")
    quality.add_argument("--spec", type=Path, required=True)
    quality.add_argument("--output", type=Path, required=True)
    quality.add_argument("--transport", type=Path, help="Explicit selected-route configuration; omit for offline reconstruction/cache reuse")
    profiles = commands.add_parser("profiles", help="Inspect all 14 profiles' native early feasibility; R6 owns final admission")
    profiles.add_argument("--catalog", type=Path, default=Path("profiles/catalog.json"))
    profiles.add_argument("--check-ports", action="store_true")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        paths = DataPaths()
        if hasattr(args, "output"):
            args.output = paths.output(args.output)
        if args.command == "quality":
            paths.output(str(args.output) + ".store")
        if args.command == "calibrate":
            paths.output(args.output.with_suffix(".npz"))
        if hasattr(args, "root"):
            args.root = paths.output(args.root)
        for name in ("spec", "transport", "catalog", "plan", "audio"):
            value = getattr(args, name, None)
            if value is not None:
                setattr(args, name, paths.input(value))
        if args.command == "quality":
            from .quality import evaluate
            result = evaluate(args.spec, args.output, transport_path=args.transport)
            print(json.dumps({"report": str(args.output), "schema_version": result["schema_version"],
                              "status": result["status"]}, indent=2))
            return 0 if result["status"] == "complete" else 2
        if args.command == "costs":
            from .costs import derive
            result = derive(args.spec, args.output)
            print(json.dumps({"report": str(args.output), "version": result["version"],
                              "revision": result["revision"]["id"], "status": result["status"],
                              "components": len(result["components"]), "records": len(result["records"]),
                              "pending_populations": sum(row["cost"] is None for row in result["populations"])}, indent=2))
            return 0
        if args.command == "profiles":
            result = inspect_catalog(args.catalog, check_ports=args.check_ports)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        if args.command == "calibrate":
            result = calibrate(args.output, args.output_device, args.input_device)
            print(json.dumps({"status": result["status"], "offset_ns": result["offset_ns"], "artifact": str(args.output)}, indent=2))
            return 0
        if args.command == "playback":
            player = Playback(args.audio, args.output_device)
            started = utc_now()
            try:
                player.start()
                while not player.done.wait(0.01):
                    player.check()
                player.check()
                result = {"kind": "cable_only_playback", "translation_pilot": False, "wall_start": started,
                          "wall_end": utc_now(), "audio": str(args.audio.resolve()), "devices": player.devices,
                          "source": player.info, "dac_start_ns": player.first_dac_ns, "end_ns": player.finished_ns,
                          "callbacks": player.records}
            finally:
                player.close()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            atomic_json(args.output, result)
            print(json.dumps({"artifact": str(args.output), "frames": player.info["frames"], "callbacks": len(player.records), "translation_pilot": False}, indent=2))
            return 0
        run_id = args.run_id if args.command == "status" else args.resume or args.run_id or time.strftime("%Y%m%dT%H%M%S")
        if not IDENTIFIER.fullmatch(run_id):
            raise ValueError("Run ID must be a safe identifier")
        root = paths.output(args.root / run_id)
        if args.command == "status":
            plan = json.loads((root / "execution-plan.json").read_text(encoding="utf-8"))
            ledger = Ledger(root)
            try:
                result = ledger.export(plan)
            finally:
                ledger.close()
            result.update({"manifest": str(root / "manifest.json"), "ledger": str(root / "ledger.sqlite")})
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        if args.resume:
            plan = json.loads((root / "execution-plan.json").read_text(encoding="utf-8"))
        else:
            plan = load_plan(args.plan, run_id)
            root.mkdir(parents=True, exist_ok=False)
            atomic_json(root / "frozen-plan.json", plan)
            atomic_json(root / "execution-plan.json", plan)
        report = Runner(root, plan, args.audio_backend == "clock", bool(args.resume)).run()
        print(json.dumps({"run": run_id, "counts": report["counts"], "manifest": str(root / "manifest.json")}, indent=2))
        return 1 if report["counts"]["product_failure"] else 0
    except KeyboardInterrupt:
        print("Interrupted; resume this run to preserve history and replay unfinished profile work", file=sys.stderr)
        return 130
    except (OperationalError, OSError, ValueError, KeyError) as error:
        print(f"bench: {error}", file=sys.stderr)
        return 2




if __name__ == "__main__":
    raise SystemExit(main())
