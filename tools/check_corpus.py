from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import wave

ROOT = Path(__file__).resolve().parents[1]
DIRECTIONS = {
    "D1": ("en", "ja"), "D2": ("en", "zh"), "D3": ("zh", "ko"),
    "D4": ("ja", "ko"), "D5": ("zh", "ja"), "D6": ("ja", "en"),
}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_file(asset: dict) -> Path:
    path = ROOT / asset["path"]
    if digest(path) != asset["sha256"]:
        raise ValueError(f"SHA-256 mismatch: {asset['path']}")
    return path


def verify_audio(asset: dict, duration: int | None = None) -> None:
    path = verify_file(asset)
    with wave.open(str(path), "rb") as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (1, 2, 48000):
            raise ValueError(f"Expected mono PCM16 48 kHz: {path}")
        frames = stream.getnframes()
        if frames != asset["frames"] or frames <= 0:
            raise ValueError(f"Frame count mismatch: {path}")
        if duration is not None and frames != duration * 48000:
            raise ValueError(f"Expected exactly {duration} seconds: {path}")
        if asset["duration_seconds"] != frames / 48000:
            raise ValueError(f"Manifest duration mismatch: {path}")
        remaining = frames
        while remaining:
            block = stream.readframes(min(remaining, 48000))
            if not block or len(block) % 2:
                raise ValueError(f"Truncated PCM payload: {path}")
            remaining -= len(block) // 2


def check(index: dict) -> dict:
    directions = index["directions"]
    if len(directions) != 6 or {d["id"] for d in directions} != set(DIRECTIONS):
        raise ValueError("Direction matrix must contain D1 through D6 exactly once")
    groups = index["source_groups"]
    if set(groups) != {"en", "zh", "ja"}:
        raise ValueError("Expected exactly three shared source groups")
    for direction in directions:
        source, target = DIRECTIONS[direction["id"]]
        if (direction["source_group"], direction["target_language"]) != (source, target):
            raise ValueError(f"Direction/source reuse mismatch: {direction['id']}")
    checked = 0
    for language, group in groups.items():
        verify_file(group["manifest"])
        verify_file(group["main_timeline"])
        verify_audio(group["main"], 1800)
        verify_audio(group["development"], 300)
        totals = group["category_seconds_including_separators"]
        if totals != {"general": 1200, "stress": 600}:
            raise ValueError(f"Unexpected category budgets: {language}")
        if len(group["isolated"]) != 20:
            raise ValueError(f"Expected 20 isolated utterances: {language}")
        if len({asset["path"] for asset in group["isolated"]}) != 20:
            raise ValueError(f"Duplicate isolated asset: {language}")
        for asset in group["isolated"]:
            verify_audio(asset)
        checked += 22
    supplements = index["supplementary"]
    verify_file(supplements["nonspeech_manifest"])
    verify_audio(supplements["nonspeech"], 180)
    verify_audio(supplements["D1_repeat"], 300)
    with wave.open(str(ROOT / groups["en"]["main"]["path"]), "rb") as main, wave.open(str(ROOT / supplements["D1_repeat"]["path"]), "rb") as repeat:
        for _ in range(300):
            if main.readframes(48000) != repeat.readframes(48000):
                raise ValueError("D1 repeat is not the exact first five minutes of English main")
    return {"status": "passed", "directions": 6, "unique_main_source_seconds": 5400,
            "audio_assets_checked": checked + 2, "scope": "Local hashes, decoded WAV format/frames, direction sharing, budgets, 60 isolated assets and exact repeat prefix; no listening or linguistic validation"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the local six-direction corpus index against actual audio.")
    parser.add_argument("--manifest", type=Path, default=ROOT / "corpus/manifest.json")
    args = parser.parse_args()
    print(json.dumps(check(json.loads(args.manifest.read_text(encoding="utf-8"))), indent=2))


if __name__ == "__main__":
    main()
