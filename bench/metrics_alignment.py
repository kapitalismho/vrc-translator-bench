from __future__ import annotations

import importlib.metadata
import hashlib
import json
import re
from pathlib import Path

from .metrics_inputs import load_json, fingerprint, resolve


MODEL = "google-bert/bert-base-multilingual-cased"
MODEL_REVISION = "3f076fdb1ab68d5b2880cb87a0886f315b8146f8"


def tokens(text):
    return re.findall(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]|[^\W_]+|[^\w\s]", text, re.UNICODE)


def interpret(events, rules):
    outputs, previous = [], {}
    for event in events:
        if event["address"] != "/chatbox/input" or not event.get("args") or not isinstance(event["args"][0], str) or not event["args"][0].strip():
            continue
        rule = rules.get(event.get("config"), {})
        style = rule.get("style", "unknown")
        if style not in ("append", "revision", "pagination", "unknown"):
            raise ValueError(f"Unsupported interpretation style: {style}")
        if rule and (not rule.get("version") or not rule.get("evidence")):
            raise ValueError("Per-app rules require version and evidence")
        text, source = event["args"][0], None
        extraction = "full_message"
        if rule.get("text_pattern"):
            match = re.fullmatch(rule["text_pattern"], text, re.DOTALL)
            if match is None:
                extraction = "pattern_mismatch_unknown_translation"
                style = "unknown"
            else:
                text = match.group("translation")
                source = match.groupdict().get("source")
        key = (event.get("clock_session"), event.get("config"), event.get("direction"))
        prior = previous.get(key)
        identity = f"{event.get('clock_session', 'unknown')}:{event['recv_seq']}"
        duplicate = prior is not None and prior["text"] == text
        explicit = rule.get("relationships", {}).get(identity)
        relation = "resend" if duplicate and rule.get("supports", {}).get("resend") else "new" if style == "append" else "unknown"
        parent = prior["id"] if prior else None
        group = identity
        if explicit:
            relation = explicit["relation"]
            parent = explicit.get("parent_id")
            if relation not in ("new", "revision", "pagination", "resend", "unknown"):
                raise ValueError("Invalid explicit relationship")
            if relation in ("revision", "pagination", "resend"):
                linked = next((row for row in outputs if row["id"] == parent), None)
                if linked is None or linked["raw"].get("clock_session") != event.get("clock_session") or linked["raw"].get("config") != event.get("config"):
                    raise ValueError("Grouping parent must be earlier output in the same config and clock")
                group = linked["group_id"]
        elif relation == "resend" and prior:
            group = prior["group_id"]
        changed = False if relation == "resend" else None if relation == "unknown" else True
        output = {"id": identity, "raw": event, "text": text, "source_text": source,
                  "extraction": extraction, "relation": relation, "parent_id": parent,
                  "group_id": group, "content_changed": changed, "duplicate_observed": duplicate,
                  "interpretation": {"version": rule.get("version"), "evidence": rule.get("evidence", []),
                                     "rule_sha256": hashlib.sha256(json.dumps(rule, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                                     "style": style, "supports": rule.get("supports", {}),
                                     "uncertainty": rule.get("uncertainty", "unknown" if style == "unknown" else "estimated from explicit rules")}}
        outputs.append(output)
        previous[key] = output
    return outputs


def cache_binding(output, sentences):
    sources = [{key: row[key] for key in ("id", "text", "start_ns", "end_ns", "clock_session", "direction")} for row in sentences
               if row["config"] == output["raw"].get("config") and row["clock_session"] == output["raw"].get("clock_session")]
    return {
        "output_sha256": hashlib.sha256(json.dumps(output["raw"], sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        "rules_version": output["interpretation"]["version"],
        "interpretation_sha256": hashlib.sha256(json.dumps({key: output[key] for key in ("text", "source_text", "relation", "group_id", "interpretation")}, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        "sources_sha256": hashlib.sha256(json.dumps(sources, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
    }


class Alignment:
    def __init__(self, spec, base, cache_path=None, allow_download=False):
        self.settings = spec.get("alignment", {})
        self.backend = self.settings.get("backend", "simalign")
        if self.backend not in ("simalign", "cache"):
            raise ValueError("Alignment backend must be simalign or cache")
        self.allow_download = allow_download
        self.base = base
        self.aligner = None
        self.error = None
        self.links = {}
        self.provenance = {"backend": self.backend, "confidence": "No calibrated semantic confidence"}
        path = Path(cache_path) if cache_path is not None else resolve(base, self.settings["cache"]) if self.settings.get("cache") else None
        if path is not None:
            data = load_json(path)
            data = data.get("alignment_cache", data)
            if data.get("schema_version") != 1 or not data.get("version") or not data.get("provenance"):
                raise ValueError("Alignment cache requires schema_version=1, version and provenance")
            self.links = data["links"]
            self.provenance["cache"] = {"path": str(path), "sha256": fingerprint(path), "version": data["version"], "provenance": data["provenance"]}

    def model(self):
        if self.aligner is not None or self.error:
            return
        try:
            from huggingface_hub import snapshot_download
            from simalign import SentenceAligner
            version = importlib.metadata.version("simalign")
            if version != "0.4":
                raise ValueError("SimAlign integration requires simalign==0.4")
            if self.settings.get("model_path"):
                if self.settings.get("model_revision") != MODEL_REVISION:
                    raise ValueError("Local model_path requires exact pinned model_revision")
                model = str(resolve(self.base, self.settings["model_path"]))
                if Path(model).name != MODEL_REVISION:
                    raise ValueError("Local model_path must be the pinned Hugging Face snapshot directory")
            else:
                model = snapshot_download(MODEL, revision=MODEL_REVISION, local_files_only=not self.allow_download,
                                          allow_patterns=["config.json", "model.safetensors", "tokenizer*", "vocab.txt"])
            self.aligner = SentenceAligner(model=model, token_type="word", matching_methods="i", device="cpu", layer=8)
            self.provenance.update({"package": "simalign", "version": version, "model": MODEL, "revision": MODEL_REVISION,
                                    "layer": 8, "matching": "itermax", "tokenization": "unicode-word-and-CJK-character-v1", "device": "cpu"})
            self.provenance["dependencies"] = {name: importlib.metadata.version(name) for name in ("torch", "transformers", "huggingface-hub", "numpy")}
            self.provenance["local_snapshot"] = str(model)
            self.provenance["model_files"] = {path.name: fingerprint(path) for path in Path(model).iterdir() if path.is_file()}
        except (ImportError, OSError, ValueError, RuntimeError) as error:
            self.error = f"SimAlign unavailable: {type(error).__name__}: {error}"
            self.provenance["unavailable_reason"] = self.error

    def align(self, output, candidates, all_sentences):
        identity = output["id"]
        if identity in self.links:
            entry = dict(self.links[identity])
            if entry.get("binding") != cache_binding(output, all_sentences):
                raise ValueError(f"Stale alignment cache binding: {identity}")
            if entry.get("status") not in ("aligned", "unknown", "unrelated"):
                raise ValueError(f"Invalid cached alignment status: {identity}")
            ids = entry.get("sentence_ids", [])
            if (entry["status"] == "aligned") != bool(ids):
                raise ValueError("Aligned cache entries require sentence_ids, other statuses prohibit them")
            valid = {row["id"]: row for row in all_sentences}
            for source_id in ids:
                if source_id not in valid:
                    raise ValueError(f"Cached alignment references unknown sentence: {source_id}")
                row = valid[source_id]
                if row["config"] != output["raw"].get("config") or row["clock_session"] != output["raw"].get("clock_session"):
                    raise ValueError("Cached alignment cannot cross config or clock session")
            return {**entry, "sentence_ids": ids, "method": "explicit_cache", "candidate_ids": [row["id"] for row in candidates]}
        if self.backend == "cache":
            return {"status": "unknown", "sentence_ids": [], "method": "explicit_cache", "reason": "No cached correspondence evidence", "candidate_ids": [row["id"] for row in candidates]}
        if not candidates:
            return {"status": "unknown", "sentence_ids": [], "method": "simalign", "reason": "No same-clock source candidate", "candidate_ids": []}
        self.model()
        if self.error:
            return {"status": "unknown", "sentence_ids": [], "method": "simalign", "reason": self.error, "candidate_ids": [row["id"] for row in candidates]}
        source, owners = [], []
        for row in candidates:
            parts = tokens(row["text"])
            source.extend(parts)
            owners.extend([row["id"]] * len(parts))
        target = tokens(output["text"])
        tokenizer = self.aligner.embed_loader.tokenizer
        lengths = [sum(len(tokenizer.tokenize(word)) for word in words) for words in (source, target)]
        if not source or not target or max(lengths) > 500:
            return {"status": "unknown", "sentence_ids": [], "method": "simalign", "reason": "Empty tokens or model context would truncate; no silent truncation", "candidate_ids": [row["id"] for row in candidates]}
        links = sorted(self.aligner.get_word_aligns(source, target)["itermax"])
        ids = sorted({owners[left] for left, right in links})
        return {"status": "aligned" if ids else "unknown", "sentence_ids": ids, "method": "simalign",
                "token_links": links, "source_tokens": source, "source_owners": owners, "target_tokens": target,
                "confidence": None, "reason": "Uncalibrated lexical alignment; not semantic correctness", "candidate_ids": [row["id"] for row in candidates]}


def final_outputs(outputs):
    final = []
    positions = {}
    for output in outputs:
        if output["relation"] == "resend":
            continue
        if output["relation"] == "revision" and output["group_id"] in positions:
            final[positions[output["group_id"]]] = output
        else:
            positions[output["group_id"]] = len(final)
            final.append(output)
    return final
