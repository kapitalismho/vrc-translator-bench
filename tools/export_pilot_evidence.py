from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench.paths import DataPathError, DataPaths
from bench.storage import atomic_json


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def redact_paths(value, replacements, changes, pointer=""):
    if isinstance(value, dict):
        return {key: redact_paths(item, replacements, changes, pointer + "/" + key) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_paths(item, replacements, changes, pointer + "/" + str(index)) for index, item in enumerate(value)]
    if isinstance(value, str):
        if value.lstrip().startswith(("{", "[", '"')):
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                pass
            else:
                nested_changes = []
                derived = redact_paths(decoded, replacements, nested_changes)
                if nested_changes:
                    changes.append(pointer)
                    return json.dumps(derived, ensure_ascii=False, separators=(",", ":"))
        result = value
        for source, label in replacements:
            result = result.replace(source, label)
        if result != value:
            changes.append(pointer)
        return result
    return value


def export(run_directory, output, repository):
    run_directory = Path(run_directory).resolve()
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new evidence directory; never overwrite earlier evidence")
    output.mkdir(parents=True, exist_ok=True)
    repository = Path(repository).resolve()
    replacements = []
    for path, label in [(repository, "[LOCAL_REPOSITORY]"), (Path(os.environ.get("USERPROFILE", str(repository.parent))), "[LOCAL_USER]")]:
        replacements.extend([(str(path), label), (path.as_posix(), label)])
    manifest_path = run_directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    names = ["manifest.json", *[item["path"] for item in manifest["streams"]],
             *[item["trace"] for item in manifest["attempts"] if item.get("trace")]]
    files = []
    for name in dict.fromkeys(names):
        source = run_directory / name
        if source.parent != run_directory:
            raise ValueError("Capture evidence must be a direct child of the run directory")
        changes = []
        if source.suffix == ".jsonl":
            records = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line]
            derived = [redact_paths(record, replacements, changes, "/rows/" + str(index)) for index, record in enumerate(records)]
            if not changes:
                payload = source.read_bytes()
            else:
                payload = ("".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in derived)).encode()
            (output / name).write_bytes(payload)
        else:
            derived = redact_paths(manifest, replacements, changes)
            derived["derived_export_notice"] = "Path-redacted public derivative, not authoritative runner state. Original trace/stream checksum fields identify immutable native files; see export-provenance.json for derived-file hashes."
            atomic_json(output / name, derived)
        files.append({"name": name, "original_sha256": checksum(source), "export_sha256": checksum(output / name),
                      "byte_identical": checksum(source) == checksum(output / name), "redacted_json_pointers": changes})
    provenance = {"schema_version": 1, "kind": "public_safe_path_redacted_capture_derivative",
                  "authority": "Original runner manifest, ledger, frozen plan and streams remain unchanged locally.",
                  "redactions": "Only local repository/user path prefixes replaced, including inside serialized JSON strings. Unchanged strings retain their original text. No raw diagnostics or account/configuration files exported.",
                  "timing_policy": "All original numeric callback/DAC/OSC timestamps, order, payload text, source provenance and outcome history retained; none reconstructed.",
                  "files": files}
    atomic_json(output / "export-provenance.json", provenance)
    return provenance


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    paths = DataPaths()
    try:
        args.output = paths.output(args.output)
        args.run_directory = paths.input(args.run_directory)
    except DataPathError as error:
        parser.error(str(error))
    result = export(args.run_directory, args.output, args.repository)
    print(json.dumps({"files": len(result["files"]), "output": str(args.output)}))


if __name__ == "__main__":
    main()
