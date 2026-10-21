from __future__ import annotations

import argparse
import hashlib
import json
import sys
import wave
import uuid
from pathlib import Path


def render_slice(source, destination, start_seconds=34, end_seconds=74):
    source = Path(source)
    destination = Path(destination)
    with wave.open(str(source), "rb") as reader:
        params = reader.getparams()
        start = round(start_seconds * params.framerate)
        end = round(end_seconds * params.framerate)
        if not 0 <= start < end <= reader.getnframes():
            raise ValueError("Pilot source interval is outside audio")
        reader.setpos(start)
        pcm = reader.readframes(end - start)
    with wave.open(str(destination), "wb") as writer:
        writer.setparams(params)
        writer.writeframes(pcm)
    return {"source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "source_start_frame": start, "source_end_frame": end,
            "frames": end - start, "sample_rate": params.framerate,
            "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
            "audio_sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}


def prepare(root, profile, pid, port, direction="D1", check_only=False):
    if direction not in ("D1", "D2"):
        raise ValueError("This English development pilot only supports D1/D2; use source-matching audio for other directions")
    root = Path(root).resolve()
    name = profile.lower() + ("-" + direction.lower() if direction != "D1" else "")
    output = root / ".data" / "issue45" / "plans" / name
    output.mkdir(parents=True, exist_ok=True)
    intervals = []
    if check_only:
        audio = output / "one-second-silent-lifecycle-observation.wav"
        with wave.open(str(audio), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(48000)
            writer.writeframes(b"\0\0" * 48000)
        provenance = {"kind": "direction_change_capture_resume_output_check_only", "scored_source": False,
                      "silent_stage_frames": 48000, "sample_rate": 48000,
                      "purpose": "One second digital silence satisfies the runner stage contract after the real ten-second speech output check; not a scored speech sample."}
    else:
        source = root / ".data/english/audio/development-01.wav"
        audio = output / "english-development-34-74.wav"
        provenance = render_slice(source, audio)
        provenance.update({"source": str(source.relative_to(root)), "native_clip_id": "development-01",
                           "original_session": "ES2014a", "target_speaker": "C", "channel": 2,
                           "category": "development", "selection_basis": "nine complete native dialogue-act units and turn24; independent of output-check prefix"})
        reference = root / "corpus/english/timelines/development-01.json"
        native = json.loads(reference.read_text(encoding="utf-8"))
        provenance["reference"] = str(reference.relative_to(root))
        provenance["reference_sha256"] = hashlib.sha256(reference.read_bytes()).hexdigest()
        for word in native["words_and_events"]:
            if not word.get("scored") or word.get("punctuation") or word.get("kind") != "w":
                continue
            start = max(0, (word["playback_start"] - 34 * 48000) / 48000)
            end = min(40, (word["playback_end"] - 34 * 48000) / 48000)
            if start >= end:
                continue
            if intervals and start <= intervals[-1][1]:
                intervals[-1][1] = max(intervals[-1][1], end)
            else:
                intervals.append([start, end])
        provenance["speech_intervals"] = intervals
        provenance["speech_basis"] = "Union of retained scored lexical forced-alignment intervals; not independently observed acoustic voice activity"
    operator = root / ".data" / "issue45" / "gui" / profile.lower()
    session = uuid.uuid4().hex
    operator = operator / session
    provenance["gui_observation_session"] = session
    provenance["gui_operator_directory"] = str(operator)
    plan = {"frozen_rule_revision": "issue45-real-gui-development-pilot-not-main-freeze",
            "price_table_version": "unknown-not-zero",
            "calibration": str(root / ".data/issue3/calibration/cable.json"),
            "output_device": "CABLE Input(VB-Audio Virtual Cable)",
            "output_check": {"audio": str(root / ".data/issue4/output-checks/en-output-check.wav"), "tail_seconds": 15},
            "profiles": [{"id": profile, "adapter": [sys.executable, "-m", "bench.gui_operator_adapter", "--directory", str(operator), "--owned-pid", str(pid), "--profile", profile, "--session", session],
                          "control_timeout_seconds": 600, "osc": {"host": "127.0.0.1", "port": port},
                          "expected_state": {"microphone": "CABLE Output(VB-Audio Virtual Cable)", "voice_output": False,
                                             "osc_host": "127.0.0.1", "osc_port": port},
                          "metadata": {"purpose": "real GUI-prepared development pilot", "provenance": str(output / "provenance.json")}}],
            "stages": [{"kind": "nonspeech" if check_only else "chunk", "chunk": "capture-resume-observation" if check_only else "development-01-34-74",
                        "wave": "gui-pilot-sequential", "direction": direction, "profiles": [profile], "audio": str(audio),
                        "speech_intervals": intervals, "tail_seconds": 2 if check_only else 20}]}
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    path = output / "plan.json"
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--profile", required=True)
    parser.add_argument("--owned-pid", type=int, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--direction", choices=("D1", "D2"), default="D1")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    print(prepare(args.root, args.profile, args.owned_pid, args.port, args.direction, args.check_only))


if __name__ == "__main__":
    main()
