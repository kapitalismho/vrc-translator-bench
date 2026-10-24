from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .metrics_stats import paired_comparisons, population_eligible
from .metrics_alignment import require_current_extraction
from .storage import atomic_json, utc_now


VERSION = "metrics-batch-v1"


def _reports(report_paths, quality_report_paths):
    sources, inputs = [], []
    seen_files, seen_reports = set(), set()
    for paths, joined in ((report_paths, False), (quality_report_paths, True)):
        for path in paths:
            path = Path(path).resolve()
            raw = path.read_bytes()
            checksum = hashlib.sha256(raw).hexdigest()
            if checksum in seen_files:
                raise ValueError(f"Duplicate batch input file: {path} ({checksum})")
            seen_files.add(checksum)
            document = json.loads(raw)
            inputs.append({"path": str(path), "sha256": checksum})
            if joined:
                reports = document.get("joined_metrics_reports")
                if not isinstance(reports, list) or not reports:
                    raise ValueError(f"Expected quality report with nonempty joined_metrics_reports: {path}")
            else:
                reports = [document]
            for index, report in enumerate(reports):
                pointer = f"/joined_metrics_reports/{index}" if joined else ""
                if (report.get("schema_version") != 1 or not isinstance(report.get("run"), str)
                        or not report["run"] or not isinstance(report.get("synthetic"), bool)
                        or not isinstance(report.get("sentences"), list)
                        or not isinstance(report.get("quality_segments"), list)):
                    raise ValueError(f"Expected metrics report with run, synthetic, sentences and quality_segments: {path}#{pointer}")
                require_current_extraction(report.get("outputs", []))
                source_hash = report.get("quality_provenance", {}).get("source_report_sha256", None if joined else checksum)
                if not isinstance(source_hash, str) or not source_hash:
                    raise ValueError(f"Joined metrics report lacks quality_provenance.source_report_sha256: {path}#{pointer}")
                if source_hash in seen_reports:
                    raise ValueError(f"Duplicate source metrics report: {path}#{pointer}, run={report['run']}, source_sha256={source_hash}")
                seen_reports.add(source_hash)
                sources.append({"input_path": str(path), "input_sha256": checksum, "report_pointer": pointer,
                                "source_report_sha256": source_hash, "run": report["run"], "report": report})
    if not sources:
        raise ValueError("At least one metrics report or quality report is required")
    if len({source["report"]["synthetic"] for source in sources}) != 1:
        raise ValueError("Synthetic and non-synthetic reports must be composed separately")
    return sources, inputs


def _location(source, segment):
    return (f"{source['input_path']}#{source['report_pointer']}, run={source['run']}, "
            f"config={segment['config']}, attempt={segment['attempt_id']}, segment={segment['id']}")


def compose(report_paths=(), output_path=None, *, quality_report_paths=(), iterations=2000, seed=20261020):
    """Retain source reports and recompute only paired estimates from scoped inputs.

    Every reference-eligible chunk/shared population must be unambiguous, even
    within a report: retries are not silently selected or pooled. Original
    per-report aggregates and all failure, repeat and resume history survive.
    """
    if not isinstance(iterations, int) or isinstance(iterations, bool) or iterations < 1:
        raise ValueError("Bootstrap iterations must be a positive integer")
    sources, inputs = _reports(report_paths, quality_report_paths)
    if output_path is not None and Path(output_path).resolve() in {Path(item["path"]) for item in inputs}:
        raise ValueError("Batch output must not overwrite an input report")
    sentences, segments, population, exclusions = [], [], [], []
    seen_populations, shared_sources = {}, {}
    for source_index, source in enumerate(sources):
        report = source["report"]
        sentence_index = {}
        for sentence in report["sentences"]:
            if sentence["run"] != source["run"]:
                raise ValueError(f"Sentence run differs from source report run: {source['input_path']}, sentence={sentence['id']}")
            key = (sentence["config"], sentence["direction"], sentence["attempt_id"], sentence["id"])
            if key in sentence_index:
                raise ValueError(f"Duplicate source sentence identity: {source['input_path']}, run={source['run']}, identity={key}")
            sentence_index[key] = sentence
        selected_attempts = set()
        for segment in report["quality_segments"]:
            if not population_eligible(segment):
                exclusions.append({"source_index": source_index, "run": source["run"],
                                   **{field: segment[field] for field in ("id", "attempt_id", "config", "direction", "applicability")}})
                continue
            if not (segment.get("shared_id") and segment["reference_eligible"] and segment.get("kind") == "chunk"):
                continue
            location = _location(source, segment)
            key = (segment["direction"], segment["category"], segment["config"], segment["shared_id"])
            if key in seen_populations:
                raise ValueError(f"Duplicate reference-eligible chunk/shared population {key}: {seen_populations[key]} ; {location}. Retain one unambiguous canonical population; no retry is selected automatically")
            seen_populations[key] = location
            reference = []
            for member in segment["reference"]:
                sentence = sentence_index.get((segment["config"], segment["direction"], segment["attempt_id"], member["sentence_id"]))
                if sentence is None or sentence["kind"] != "chunk":
                    raise ValueError(f"Shared segment references a missing same-attempt chunk sentence: {location}, sentence={member['sentence_id']}")
                if sentence["session_id"] != segment["session_id"] or sentence["text"] != member["text"]:
                    raise ValueError(f"Shared source text/session disagrees with its sentence: {location}, sentence={member['sentence_id']}")
                reference.append((sentence["reference_id"], sentence["text"], sentence["session_id"]))
            if not reference:
                raise ValueError(f"Shared segment has no source reference: {location}")
            signature = (segment["session_id"], reference)
            shared_key = (segment["direction"], segment["shared_id"])
            previous = shared_sources.get(shared_key)
            if previous is not None and previous[0] != signature:
                raise ValueError(f"Incompatible shared source identity/text/session for {shared_key}: {previous[1]} ; {location}")
            shared_sources[shared_key] = (signature, location)
            attempt = (segment["config"], segment["direction"], segment["attempt_id"])
            selected_attempts.add(attempt)
            scope = (source_index, source["run"], *attempt)
            segments.append({**{field: segment[field] for field in ("shared_id", "reference_eligible", "kind", "direction", "category", "config", "start", "end", "session_id", "status", "eligible")},
                             "attempt_id": scope, "quality_score": segment.get("quality_score")})
            population.append({"source_index": source_index, "run": source["run"],
                               **{field: segment[field] for field in ("id", "attempt_id", "shared_id", "config", "direction", "category", "session_id", "status", "eligible")}})
        for sentence in report["sentences"]:
            attempt = (sentence["config"], sentence["direction"], sentence["attempt_id"])
            if attempt in selected_attempts and sentence["kind"] == "chunk":
                sentences.append({**{field: sentence[field] for field in ("start", "end", "eligible", "delivery_status", "fol", "lul")},
                                  "population_eligible": sentence.get("population_eligible", True),
                                  "attempt_id": (source_index, source["run"], *attempt)})
    result = {"schema_version": 1, "version": VERSION, "created_utc": utc_now(),
              "synthetic": sources[0]["report"]["synthetic"], "provenance": inputs, "reports": sources,
              "bootstrap": {"iterations": iterations, "seed": seed},
              "population_policy": "Only reference-eligible, analysis-applicable chunk/shared segments; any duplicate population is rejected, including within a report. No retry selection, report-quantile averaging or new independent sessions. Original per-report summaries and explicit applicability exclusions are retained unchanged.",
              "pairing_population": population,
              "pairing_exclusions": exclusions,
              "paired": paired_comparisons(sentences, segments, iterations, seed)}
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(output_path, result)
    return result
