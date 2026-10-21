from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import platform
import re
from pathlib import Path


MODEL = "google/metricx-24-hybrid-xl-v2p6"
MODEL_REVISION = "f6e7f99a655582f28cb998dd3e6ca86b4217430d"
TOKENIZER = "google/mt5-xl"
TOKENIZER_REVISION = "63fc6450d80515b48e026b69ef2fbbd426433e84"
OFFICIAL_REVISION = "fc4978eb064670f7cc33e93ea4f52d38396b8ae6"
MAX_INPUT_TOKENS = 1536
REGRESSION_TOKEN = 250089
MODEL_FILES = {
    "config.json": (851, "47b47c4c4a892f2c7411a0e7711ad76f5bdcd13c176161e04f26b0dc681b4c42"),
    "pytorch_model.bin.index.json": (50781, "e00c00362f242bd766e84a3a30d820e80ba3be1c08eab2b9bf123535d5fe1c92"),
    "pytorch_model-00001-of-00002.bin": (9977015092, "f0481c16fa7171bbb1a724cce3b8598b8d78bb8e8209138fecf7fdedd5200327"),
    "pytorch_model-00002-of-00002.bin": (4993661116, "24978065a17c3d63617d92f093a1b4cdf3b94cb68b969ebd3c947c334d837cbc"),
}
TOKENIZER_FILES = {
    "config.json": (688, "ab40135afd2da5bbb3ff182e7424db595b11ffee5dc81bebd8089f6288afb1df"),
    "special_tokens_map.json": (65, "09059cedc26bc46bc09a52f05b92d4922e11917e87f3b92059bb1a63a59ab2c4"),
    "spiece.model": (4309802, "ef78f86560d809067d12bac6c09f19a462cb3af3f54d2b8acbba26e1433125d6"),
    "tokenizer_config.json": (376, "3be4bbd24c65845b1dc86186f3c7d1d61ac2e29154cb0d71133753562f8d1959"),
}
DEPENDENCIES = ("torch", "transformers", "huggingface-hub", "sentencepiece", "tokenizers", "protobuf", "accelerate", "numpy", "safetensors")
ATTRIBUTION = {
    "author": "Google LLC",
    "copyright": "Copyright 2024 Google LLC",
    "license": "Apache-2.0",
    "source": f"https://github.com/google-research/metricx/blob/{OFFICIAL_REVISION}/metricx24/models.py",
    "input_source": f"https://github.com/google-research/metricx/blob/{OFFICIAL_REVISION}/metricx24/predict.py",
    "adaptation": "Standard MT5 forward with decoder token 0, vocabulary logit 250089 and clipping to [0,25]; decoder placed on the input device instead of upstream's unconditional CUDA placement. Nonfinite logits are rejected before clipping.",
}


def _sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class MetricX:
    def __init__(self, model_path=None, device="cpu", allow_download=False):
        self.model_path = Path(model_path) if model_path is not None else None
        self.device = str(device)
        self.allow_download = allow_download
        self.tokenizer = None
        self.model = None
        self._hashes = {}
        self._loaded_identity = None
        self._tokenizer_identity = None

    def _versions(self):
        versions = {name: importlib.metadata.version(name) for name in DEPENDENCIES}
        release = re.match(r"(\d+)\.(\d+)", versions["torch"])
        if release is None or tuple(map(int, release.groups())) < (2, 6):
            raise ValueError("MetricX PyTorch checkpoint loading requires torch>=2.6")
        return versions

    def _snapshot(self, repo, revision, files, download=False):
        from huggingface_hub import snapshot_download

        return Path(snapshot_download(repo, revision=revision, allow_patterns=list(files), local_files_only=not download))

    def _verify(self, directory, expected):
        hashes = {}
        for name, (size, digest) in expected.items():
            path = directory / name
            stat = path.stat()
            if stat.st_size != size:
                raise ValueError(f"Unverified MetricX artifact size: {path}")
            signature = (str(path.resolve()), stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            actual = self._hashes.get(signature)
            if actual is None:
                actual = _sha256(path)
                self._hashes[signature] = actual
            if actual != digest:
                raise ValueError(f"Unverified MetricX artifact SHA256: {path}")
            hashes[name] = actual
        return hashes

    def _tokenizer_files(self, download=False):
        directory = self._snapshot(TOKENIZER, TOKENIZER_REVISION, TOKENIZER_FILES, download)
        for name in ("tokenizer.json", "added_tokens.json", "chat_template.jinja"):
            if (directory / name).exists():
                raise ValueError(f"Unverified additional MetricX tokenizer artifact: {directory / name}")
        hashes = self._verify(directory, TOKENIZER_FILES)
        return directory, hashes

    def _identity(self, download=False):
        versions = self._versions()
        model = self.model_path if self.model_path is not None else self._snapshot(MODEL, MODEL_REVISION, MODEL_FILES, download)
        for name in ("pytorch_model.bin", "adapter_config.json"):
            if (model / name).exists():
                raise ValueError(f"Unverified competing MetricX loader artifact: {model / name}")
        model_files = self._verify(model, MODEL_FILES)
        tokenizer, tokenizer_files = self._tokenizer_files(download)
        identity = {
            "method": "metricx24-hybrid-qe-mt5-regression-v1",
            "model": MODEL, "model_revision": MODEL_REVISION,
            "model_last_modified_utc": "2024-12-12T16:35:44Z", "model_files": model_files,
            "tokenizer": TOKENIZER, "tokenizer_revision": TOKENIZER_REVISION, "tokenizer_files": tokenizer_files,
            "official_code_revision": OFFICIAL_REVISION, "implementation_sha256": _sha256(__file__),
            "attribution": ATTRIBUTION,
            "dependencies": versions,
            "runtime": {"python": platform.python_version(), "platform": platform.platform(), "machine": platform.machine(), "device": self.device, "dtype": "float32", "batch_size": 1},
            "input": {"format": "source: {source} candidate: {output}", "context": False, "max_input_tokens_including_eos": MAX_INPUT_TOKENS, "truncation": False, "remove_final_eos": True, "tokenizer_use_fast": True, "tokenizer_legacy": True},
            "regression": {"decoder_token": 0, "vocabulary_logit": REGRESSION_TOKEN, "clip": [0, 25], "lower_is_better": True},
        }
        return identity, model, tokenizer

    def cache_identity(self):
        try:
            identity, _, _ = self._identity()
            return identity
        except (ImportError, OSError, ValueError, RuntimeError):
            return None

    def _load_tokenizer(self):
        from transformers import AutoTokenizer

        directory, hashes = self._tokenizer_files(self.allow_download)
        if self.tokenizer is None or hashes != self._tokenizer_identity:
            self.tokenizer = AutoTokenizer.from_pretrained(str(directory), local_files_only=True, use_fast=True, legacy=True)
            self._tokenizer_identity = hashes
        return hashes

    def _load_model(self, identity, directory):
        import torch
        from transformers import MT5ForConditionalGeneration

        if self.model is not None and self._loaded_identity == identity:
            return
        self.model = None
        model, loading = MT5ForConditionalGeneration.from_pretrained(
            str(directory), local_files_only=True, torch_dtype=torch.float32,
            low_cpu_mem_usage=True, use_safetensors=False, output_loading_info=True,
        )
        if any(loading.get(key) for key in ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")):
            raise ValueError(f"MetricX checkpoint did not load exactly: {loading}")
        model.to(torch.device(self.device))
        model.eval()
        self.model = model
        self._loaded_identity = identity

    def _predict(self, input_ids, attention_mask):
        import torch

        ids = torch.tensor([input_ids], dtype=torch.long, device=self.device)
        mask = torch.tensor([attention_mask], dtype=torch.long, device=self.device)
        with torch.inference_mode():
            result = self.model(input_ids=ids, attention_mask=mask, decoder_input_ids=ids.new_zeros((1, 1)), use_cache=False, return_dict=True)
        return float(result.logits[0, 0, REGRESSION_TOKEN].item())

    def score(self, source: str, output: str) -> dict:
        formatted = f"source: {source} candidate: {output}"
        binding = json.dumps({"source": source, "output": output}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        provenance = {"model": MODEL, "requested_model_revision": MODEL_REVISION, "tokenizer": TOKENIZER,
                      "input_sha256": hashlib.sha256(binding.encode("utf-8")).hexdigest(),
                      "formatted_input_sha256": hashlib.sha256(formatted.encode("utf-8")).hexdigest(),
                      "cache_identity": None, "attribution": ATTRIBUTION}
        result = {"status": "unavailable", "score": None, "reason": None, "provenance": provenance, "input_tokens": None,
                  "raw": {"input": formatted, "prediction": None}}
        try:
            self._versions()
            tokenizer_files = self._load_tokenizer()
            provenance["tokenizer_revision"] = TOKENIZER_REVISION
            provenance["tokenizer_files"] = tokenizer_files
            encoded = self.tokenizer(formatted, truncation=False, padding=False, add_special_tokens=True)
            ids, mask = encoded["input_ids"], encoded["attention_mask"]
            result["input_tokens"] = len(ids)
            if len(ids) > MAX_INPUT_TOKENS:
                result.update(status="oversized", reason=f"Full EOS-inclusive input has {len(ids)} tokens; limit is {MAX_INPUT_TOKENS}; no truncation or inference performed")
                return result
            if not ids or ids[-1] != self.tokenizer.eos_token_id or len(mask) != len(ids):
                raise ValueError("MetricX tokenizer did not supply the expected final EOS and attention mask")
            identity, directory, _ = self._identity(self.allow_download)
            provenance["cache_identity"] = identity
            self._load_model(identity, directory)
        except (ImportError, OSError, ValueError, RuntimeError) as error:
            result["reason"] = f"MetricX unavailable: {type(error).__name__}: {error}"
            return result
        try:
            prediction = self._predict(ids[:-1], mask[:-1])
            result["raw"]["forwarded_tokens"] = len(ids) - 1
            if not math.isfinite(prediction):
                result.update(status="failed", reason="MetricX returned a nonfinite regression logit")
                result["raw"]["nonfinite_prediction"] = str(prediction)
                return result
            result["raw"]["unclipped_prediction"] = prediction
            score = min(25.0, max(0.0, prediction))
            result["raw"]["prediction"] = score
            result.update(status="completed", score=score)
        except (OSError, ValueError, RuntimeError, TypeError, AttributeError, IndexError) as error:
            result.update(status="failed", reason=f"MetricX inference failed: {type(error).__name__}: {error}")
        return result
