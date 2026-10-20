from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request
import wave

import numpy as np

RATE = 48000
ROOT = Path(__file__).resolve().parents[1]
MUSAN_REVISION = "3edcfdf89b56dbe6a395ff29f9c29489e03d1321"
MUSAN_URL = f"https://huggingface.co/datasets/FluidInference/musan/resolve/{MUSAN_REVISION}/noise/sound-bible"
SOURCES = {
    "keyboard": {
        "filename": "keyboard.mp3",
        "url": "https://cdn.freesound.org/previews/380/380135_3249786-hq.mp3",
        "expected_sha256": "060cbad136d2b64525c0483d374b5133792f668449bed3f939c083020be6ec65",
        "title": "Computer Keyboard - typing sounds.wav",
        "creator": "yottasounds",
        "source_page": "https://freesound.org/people/yottasounds/sounds/380135/",
        "license": "CC0-1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "representation": "Freesound HQ MP3 rendition, not original WAV; real recorded keyboard",
    },
    "coin": {
        "filename": "noise-sound-bible-0017.wav",
        "url": f"{MUSAN_URL}/noise-sound-bible-0017.wav",
        "expected_sha256": "1dda7a8cf3a52004921fa7cce6bc06b400f9e85116adfaa9692b746dab47455b",
        "title": "Coin Drop",
        "creator": "Willem Hunt",
        "source_page": "https://soundbible.com/2081-Coin-Drop.html",
        "license": "Public Domain",
        "license_url": f"{MUSAN_URL}/LICENSE",
        "representation": "MUSAN SoundBible recording via pinned mirror",
    },
    "snap": {
        "filename": "noise-sound-bible-0029.wav",
        "url": f"{MUSAN_URL}/noise-sound-bible-0029.wav",
        "expected_sha256": "277b7127e277f4965a3069ce309354ad2c2322e3b6dc6d3cae443f988de22d38",
        "title": "Finger Snapping",
        "creator": "Maddie Fix",
        "source_page": "https://soundbible.com/1978-Finger-Snapping.html",
        "license": "Public Domain",
        "license_url": f"{MUSAN_URL}/LICENSE",
        "representation": "MUSAN SoundBible recording via pinned mirror",
    },
    "background": {
        "filename": "ES2003a.Mix-Headset.wav",
        "url": "https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus/ES2003a/audio/ES2003a.Mix-Headset.wav",
        "title": "AMI ES2003a mixed headset conversation",
        "creator": "AMI Project — AMI Meeting Corpus",
        "source_page": "https://groups.inf.ed.ac.uk/ami/corpus/",
        "license": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "terms_evidence": "https://groups.inf.ed.ac.uk/ami/corpus/license.shtml",
        "session_id": "ES2003a",
        "split": "AMI scenario-only official development",
        "input_mode": "mixed_headset_background_conversation",
        "representation": "Official mixed headset WAV; not a target-speaker scored input",
    },
}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def acquire(source: dict, directory: Path) -> Path:
    path = directory / source["filename"]
    if not path.exists():
        temporary = path.with_suffix(path.suffix + ".part")
        request = urllib.request.Request(source["url"], headers={"User-Agent": "vrc-translator-bench/0.1"})
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as stream:
            shutil.copyfileobj(response, stream)
        temporary.replace(path)
    if source.get("expected_sha256") and sha256(path) != source["expected_sha256"]:
        raise ValueError(f"Source checksum mismatch: {path}")
    return path


def decode(path: Path, start: float = 0, duration: float | None = None) -> np.ndarray:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-i", str(path), "-ss", str(start)]
    if duration is not None:
        command += ["-t", str(duration)]
    command += ["-vn", "-ac", "1", "-ar", str(RATE), "-f", "f32le", "pipe:1"]
    result = subprocess.run(command, check=True, stdout=subprocess.PIPE)
    data = np.frombuffer(result.stdout, dtype="<f4")
    if not len(data) or not np.isfinite(data).all():
        raise ValueError(f"Invalid decoded audio: {path}")
    if duration is not None and len(data) != round(duration * RATE):
        raise ValueError(f"Incomplete source interval: {path}: {len(data)} samples")
    return data


def normalize(data: np.ndarray, peak: float = 0.5, rms: float | None = None) -> tuple[np.ndarray, float]:
    maximum = float(np.max(np.abs(data)))
    if maximum == 0:
        raise ValueError("Expected recorded sound, got digital silence")
    gain = peak / maximum
    if rms is not None:
        gain = min(gain, rms / float(np.sqrt(np.mean(data.astype(np.float64) ** 2))))
    return data * gain, gain


def assemble(inputs: dict[str, np.ndarray]) -> tuple[np.ndarray, list[dict]]:
    audio = np.zeros(180 * RATE, dtype=np.float32)
    events = []
    for name, playback_start, source_start, seconds in [
        ("keyboard", 60, 10, 30), ("coin", 90, 0, None),
        ("snap", 100, 0, None), ("background", 120, 120, 60),
    ]:
        data = inputs[name]
        if seconds is not None and len(data) != seconds * RATE:
            raise ValueError(f"Incorrect {name} interval duration")
        if name in {"coin", "snap"} and len(data) > 10 * RATE:
            raise ValueError(f"Nonverbal event overruns its allocated slot: {name}")
        normalized, gain = normalize(data, rms=10 ** (-30 / 20) if name == "background" else None)
        begin = playback_start * RATE
        end = begin + len(normalized)
        audio[begin:end] = normalized
        events.append({
            "source_id": name, "playback_start_sample": begin, "playback_end_sample": end,
            "source_start_seconds": source_start, "source_end_seconds": source_start + len(data) / RATE,
            "gain_linear": gain, "transformation": "crop, mono downmix, 48kHz resampling, constant gain, placement; no speech synthesis or time stretching",
        })
    return audio, events


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the local 180-second licensed nonspeech/background track.")
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".data/nonspeech")
    parser.add_argument("--manifest", type=Path, default=ROOT / "corpus/nonspeech/manifest.json")
    args = parser.parse_args()
    downloads = args.data_dir / "sources"
    downloads.mkdir(parents=True, exist_ok=True)
    paths = {name: acquire(source, downloads) for name, source in SOURCES.items()}
    inputs = {
        "keyboard": decode(paths["keyboard"], 10, 30),
        "coin": decode(paths["coin"]), "snap": decode(paths["snap"]),
        "background": decode(paths["background"], 120, 60),
    }
    audio, events = assemble(inputs)
    output = args.data_dir / "nonspeech.wav"
    with wave.open(str(output), "wb") as stream:
        stream.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        stream.writeframes(np.rint(audio * 32767).astype("<i2").tobytes())
    def relative(path: Path) -> str:
        return Path(__import__("os").path.relpath(path.resolve(), ROOT)).as_posix()
    manifest = {
        "schema_version": 1, "id": "nonspeech-v1", "status": "local_prepared_not_listened_or_released",
        "audio": {"path": relative(output), "sha256": sha256(output), "sample_rate": RATE,
                  "channels": 1, "sample_count": len(audio), "duration_seconds": len(audio) / RATE},
        "scoring_intervals": [
            {"label": "silence_keyboard_nonverbal", "start_sample": 0, "end_sample": 120 * RATE},
            {"label": "background_human_conversation", "start_sample": 120 * RATE, "end_sample": 180 * RATE},
        ],
        "composition": {"digital_silence_seconds": 120 - sum(len(inputs[k]) for k in ("keyboard", "coin", "snap")) / RATE,
                        "keyboard_seconds": 30, "nonverbal_seconds": (len(inputs["coin"]) + len(inputs["snap"])) / RATE,
                        "background_conversation_seconds": 60},
        "source_to_playback": events,
        "sources": [{"id": name, **source, "local_path": relative(paths[name]), "sha256": sha256(paths[name])}
                    for name, source in SOURCES.items()],
        "attribution": "MUSAN: David Snyder, Guoguo Chen and Daniel Povey (2015); retain individual SoundBible terms. AMI Project; yottasounds. No endorsement implied. Source licenses retain their warranty disclaimers.",
        "background_evidence": {"annotation_archive": "ami_public_manual_1.6.2.zip",
                                "source_interval_seconds": [120, 180],
                                "fully_contained_lexical_word_counts": {"B": 55, "C": 17},
                                "basis": "AMI human transcript with automatic word alignment; two speakers in the selected minute; no independent listening confirmation"},
        "verification_limits": ["No human listening performed. Confirm absence of incidental speech in keyboard/nonverbal intervals before freeze.",
                                "Background is attenuated recorded meeting conversation, not a physical-room recording of distant speakers.",
                                "No Hugging Face publication; owner authorized local data preparation only.",
                                "MUSAN small assets came from a pinned mirror, not a byte comparison against the full official archive."],
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"audio": manifest["audio"], "composition": manifest["composition"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
