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


def is_translation(output):
    return output.get("output_role", "translation") == "translation" and output.get("extraction") != "pattern_mismatch_unknown_translation"


def require_current_extraction(outputs):
    if any(row.get("extraction") == "pattern_mismatch_unknown_translation" for row in outputs):
        raise ValueError("Legacy unresolved text role: rederive metrics and prepare a new quality queue; retained reports/queues are not rewritten")


def interpret(events, rules):
    outputs, nontranslation, previous = [], [], {}
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
        role = "translation"
        if rule.get("text_pattern"):
            match = re.fullmatch(rule["text_pattern"], text, re.DOTALL)
            if match is None:
                extraction = "pattern_mismatch_unresolved_role"
                text, role, style = None, "unresolved", "unknown"
            else:
                text = match.group("translation")
                source = match.groupdict().get("source")
        if text is not None and not text.strip():
            nontranslation.append({"id": f"{event.get('clock_session', 'unknown')}:{event['recv_seq']}", "raw": event,
                                   "text": text, "source_text": source, "extraction": extraction, "output_role": "source_only",
                                   "reason": "empty_extracted_translation", "rules_version": rule.get("version"),
                                   "rule_sha256": hashlib.sha256(json.dumps(rule, sort_keys=True, ensure_ascii=False).encode()).hexdigest()})
            continue
        key = (event.get("clock_session"), event.get("config"), event.get("direction"))
        prior = previous.get(key)
        identity = f"{event.get('clock_session', 'unknown')}:{event['recv_seq']}"
        duplicate = role == "translation" and prior is not None and prior["text"] == text
        explicit = rule.get("relationships", {}).get(identity) if role == "translation" else None
        relation = "new" if style == "append" else "unknown"
        parent = prior["id"] if prior and role == "translation" else None
        group = identity
        if explicit:
            relation = explicit["relation"]
            parent = explicit.get("parent_id")
            if relation not in ("new", "revision", "pagination", "resend", "unknown"):
                raise ValueError("Invalid explicit relationship")
            if relation in ("revision", "pagination", "resend"):
                linked = next((row for row in outputs if row["id"] == parent), None)
                if linked is None or not is_translation(linked) or linked["raw"].get("clock_session") != event.get("clock_session") or linked["raw"].get("config") != event.get("config"):
                    raise ValueError("Grouping parent must be earlier translated output in the same config and clock")
                group = linked["group_id"]
        changed = False if relation == "resend" else None if relation == "unknown" else True
        output = {"id": identity, "raw": event, "text": text, "source_text": source,
                  "extraction": extraction, "output_role": role, "relation": relation, "parent_id": parent,
                  "group_id": group, "content_changed": changed, "duplicate_observed": duplicate,
                  "interpretation": {"version": rule.get("version"), "evidence": rule.get("evidence", []),
                                     "rule_sha256": hashlib.sha256(json.dumps(rule, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                                     "style": style, "supports": rule.get("supports", {}),
                                     "uncertainty": rule.get("uncertainty", "unknown" if style == "unknown" else "estimated from explicit rules")}}
        outputs.append(output)
        if role == "translation":
            previous[key] = output
    return outputs, nontranslation


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
        self.provenance = {"backend": self.backend, "confidence": "No calibrated semantic confidence", "correspondence_policy": "adjudicated_bound_cache_only"}
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
        if not is_translation(output):
            return {"status": "unknown", "sentence_ids": [], "method": "unresolved_output_role",
                    "reason": "unresolved_output_role", "candidate_ids": [row["id"] for row in candidates],
                    "cached_correspondence_rejected": identity in self.links}
        if identity in self.links:
            entry = dict(self.links[identity])
            if entry.get("binding") != cache_binding(output, all_sentences):
                raise ValueError(f"Stale alignment cache binding: {identity}")
            if entry.get("status") not in ("aligned", "unknown", "unrelated"):
                raise ValueError(f"Invalid cached alignment status: {identity}")
            ids = entry.get("sentence_ids", [])
            if (entry["status"] == "aligned") != bool(ids):
                raise ValueError("Aligned cache entries require sentence_ids, other statuses prohibit them")
            adjudication = entry.get("adjudication") or {}
            if ids and (not isinstance(adjudication, dict) or adjudication.get("decision") != "confirmed"
                        or not isinstance(adjudication.get("method"), str) or not adjudication["method"].strip()
                        or not isinstance(adjudication.get("evidence"), list) or not adjudication["evidence"]):
                raise ValueError(f"Aligned cache entry requires explicit adjudication: {identity}")
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
        references = {row["id"]: row for row in candidates}
        proposals, rejected = set(), []
        for left, right in links:
            identity = owners[left]
            if references[identity]["start_ns"] > output["raw"]["t_ns"]:
                rejected.append({"sentence_id": identity, "token_link": [left, right], "reason": "future_source_support"})
            elif not re.search(r"[^\W_]", source[left], re.UNICODE) or not re.search(r"[^\W_]", target[right], re.UNICODE):
                rejected.append({"sentence_id": identity, "token_link": [left, right], "reason": "punctuation_only_support"})
            else:
                proposals.add(identity)
        viable = sorted({owner for index, owner in enumerate(owners) if references[owner]["start_ns"] <= output["raw"]["t_ns"]
                         and re.search(r"[^\W_]", source[index], re.UNICODE)})
        return {"status": "unknown", "sentence_ids": [], "method": "simalign", "proposal_status": "requires_adjudication",
                "proposed_sentence_ids": sorted(proposals), "rejected_support": rejected,
                "competing_candidate_ids": viable if len(viable) > 1 else [],
                "ambiguity_reason": "no_eligible_lexical_support" if not proposals else "multiple_eligible_source_candidates" if len(viable) > 1 else "uncalibrated_lexical_proposal",
                "token_links": links, "source_tokens": source, "source_owners": owners, "target_tokens": target,
                "candidate_evidence": [{"sentence_id": row["id"], "start_ns": row["start_ns"], "end_ns": row["end_ns"],
                                        "temporal_status": "future_source" if row["start_ns"] > output["raw"]["t_ns"] else "source_started"} for row in candidates],
                "confidence": None, "reason": "Model proposals require inspected bound-cache adjudication before source correspondence or delivery credit",
                "candidate_ids": [row["id"] for row in candidates]}


def final_outputs(outputs):
    final = []
    positions = {}
    for output in outputs:
        if not is_translation(output):
            continue
        parent_position = positions.get(output.get("parent_id"))
        if output["relation"] == "resend":
            if parent_position is not None:
                positions[output["id"]] = parent_position
            continue
        if output["relation"] == "revision" and parent_position is not None:
            final[parent_position] = output
            positions[output["id"]] = parent_position
        else:
            positions[output["id"]] = len(final)
            final.append(output)
    return final
