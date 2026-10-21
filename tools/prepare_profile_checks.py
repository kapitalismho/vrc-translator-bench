from __future__ import annotations

import argparse
import hashlib
import json
import wave
from pathlib import Path

from bench.storage import atomic_json, digest


def prepare(corpus_path, output, manifest_path):
    corpus_path = Path(corpus_path).resolve()
    root = corpus_path.parent.parent
    output = Path(output).resolve()
    manifest_path = Path(manifest_path).resolve()
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    clips = {}
    prepared = []
    for language in ("en", "zh", "ja"):
        group = corpus["source_groups"][language]
        source = group["development"]
        path = root / source["path"].replace("\\", "/")
        if digest(path) != source["sha256"]:
            raise ValueError(f"{language} development source checksum changed")
        with wave.open(str(path), "rb") as audio:
            if audio.getsampwidth() != 2 or audio.getnchannels() != 1 or audio.getframerate() != 48000:
                raise ValueError("Profile checks require prepared 48 kHz mono PCM16 sources")
            frames = audio.getframerate() * 10
            pcm = audio.readframes(frames)
            if len(pcm) != frames * 2:
                raise ValueError(f"{language} development source is shorter than ten seconds")
            prepared.append((language, audio.getparams(), pcm))
        clips[language] = {"source": source, "source_manifest": group["manifest"], "source_start_frame": 0,
                           "frames": frames, "sample_rate": 48000, "duration_seconds": 10,
                           "pcm_sha256": hashlib.sha256(pcm).hexdigest(), "semantic_output_verified": False}
    output.mkdir(parents=True, exist_ok=True)
    for language, params, pcm in prepared:
        destination = output / f"{language}-output-check.wav"
        with wave.open(str(destination), "wb") as audio:
            audio.setparams(params)
            audio.writeframes(pcm)
        try:
            recorded_path = destination.relative_to(root).as_posix()
        except ValueError:
            recorded_path = str(destination)
        clips[language].update(path=recorded_path, sha256=digest(destination))
    record = {"schema_version": 1, "status": "prepared_not_translator_verified", "corpus_sha256": digest(corpus_path),
              "selection": "First ten seconds of each existing development bundle, before any measured app output; reversible working default",
              "directions": {"D1": "en", "D2": "en", "D3": "zh", "D4": "ja", "D5": "zh", "D6": "ja"},
              "clips": clips, "redistribution": "Audio remains local under source-specific terms; Japanese publication rights unresolved",
              "runner_use": "Use the matching source clip as output_check.audio in a source-language-specific run plan; do not reuse English checks for Chinese/Japanese capture"}
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(manifest_path, record)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=Path("corpus/manifest.json"))
    parser.add_argument("--output", type=Path, default=Path(".data/issue4/output-checks"))
    parser.add_argument("--manifest", type=Path, default=Path("profiles/output-checks.json"))
    args = parser.parse_args(argv)
    result = prepare(args.corpus, args.output, args.manifest)
    print(json.dumps({"status": result["status"], "clips": {language: value["path"] for language, value in result["clips"].items()}}, indent=2))


if __name__ == "__main__":
    main()
