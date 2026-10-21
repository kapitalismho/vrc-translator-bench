from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path

import pytest

from bench import quality_metricx
from bench.quality_metricx import MetricX


class Tokenizer:
    eos_token_id = 1

    def __init__(self, size=8, eos=1):
        self.size = size
        self.eos = eos
        self.calls = []

    def __call__(self, text, **settings):
        self.calls.append((text, settings))
        return {"input_ids": [2] * (self.size - 1) + [self.eos], "attention_mask": [1] * self.size}


@pytest.fixture
def runtime(monkeypatch):
    metric = MetricX()
    tokenizer = Tokenizer()
    identity = {"model_revision": quality_metricx.MODEL_REVISION, "model_files": {"weights": "verified"}}
    monkeypatch.setattr(metric, "_versions", lambda: {"torch": "2.6.0"})
    monkeypatch.setattr(metric, "_load_tokenizer", lambda: {"spiece.model": "verified"})
    monkeypatch.setattr(metric, "_identity", lambda download=False: (identity, Path("model"), Path("tokenizer")))
    monkeypatch.setattr(metric, "_load_model", lambda actual, path: None)
    monkeypatch.setattr(metric, "_predict", lambda ids, mask: 2.5)
    metric.tokenizer = tokenizer
    return metric, tokenizer, identity


def test_constructor_and_missing_dependencies_are_lightweight(monkeypatch):
    def missing(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", missing)
    metric = MetricX()
    assert metric.model is None
    assert metric.tokenizer is None
    assert metric.cache_identity() is None
    result = metric.score("Hello.", "こんにちは。")
    assert result["status"] == "unavailable"
    assert result["score"] is None
    assert "PackageNotFoundError" in result["reason"]
    assert result["provenance"]["cache_identity"] is None
    json.dumps(result, allow_nan=False)


def test_exact_qe_text_eos_removal_and_cache_binding(runtime, monkeypatch):
    metric, tokenizer, identity = runtime
    forwarded = []
    monkeypatch.setattr(metric, "_predict", lambda ids, mask: forwarded.append((ids, mask)) or 2.5)
    result = metric.score(" First line\nSecond line ", " 翻訳一\n翻訳二 ")
    text, settings = tokenizer.calls[0]
    assert text == "source:  First line\nSecond line  candidate:  翻訳一\n翻訳二 "
    assert settings == {"truncation": False, "padding": False, "add_special_tokens": True}
    assert "reference:" not in text
    assert result["status"] == "completed"
    assert result["score"] == 2.5
    assert result["reason"] is None
    assert result["input_tokens"] == 8
    assert forwarded == [([2] * 7, [1] * 7)]
    assert result["raw"]["input"] == text
    assert result["raw"]["prediction"] == 2.5
    assert result["raw"]["forwarded_tokens"] == 7
    assert metric.cache_identity() == result["provenance"]["cache_identity"] == identity
    assert metric.score("a", "bc")["provenance"]["input_sha256"] != metric.score("ab", "c")["provenance"]["input_sha256"]
    json.dumps(result, allow_nan=False)


def test_exact_eos_inclusive_limit_is_scored(runtime, monkeypatch):
    metric, tokenizer, _ = runtime
    tokenizer.size = 1536
    forwarded = []
    monkeypatch.setattr(metric, "_predict", lambda ids, mask: forwarded.append(len(ids)) or 3.0)
    result = metric.score("source", "output")
    assert result["status"] == "completed"
    assert result["input_tokens"] == 1536
    assert forwarded == [1535]


def test_oversized_input_never_loads_or_scores_truncated_text(runtime, monkeypatch):
    metric, tokenizer, _ = runtime
    tokenizer.size = 1537

    def forbidden(*args, **kwargs):
        pytest.fail("Oversized input must not load weights or run inference")

    monkeypatch.setattr(metric, "_identity", forbidden)
    monkeypatch.setattr(metric, "_load_model", forbidden)
    monkeypatch.setattr(metric, "_predict", forbidden)
    result = metric.score("long source", "long output")
    assert result["status"] == "oversized"
    assert result["input_tokens"] == 1537
    assert result["score"] is None
    assert "no truncation or inference" in result["reason"]
    assert result["raw"]["prediction"] is None


@pytest.mark.parametrize("prediction, expected", [(-2.0, 0.0), (0.0, 0.0), (4.125, 4.125), (25.0, 25.0), (30.0, 25.0)])
def test_official_regression_clipping(runtime, monkeypatch, prediction, expected):
    metric, _, _ = runtime
    monkeypatch.setattr(metric, "_predict", lambda ids, mask: prediction)
    result = metric.score("Hello.", "こんにちは。")
    assert result["status"] == "completed"
    assert result["score"] == expected
    assert result["raw"]["unclipped_prediction"] == prediction


@pytest.mark.parametrize("prediction", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_logits_are_failures_not_clipped_success(runtime, monkeypatch, prediction):
    metric, _, _ = runtime
    monkeypatch.setattr(metric, "_predict", lambda ids, mask: prediction)
    result = metric.score("Hello.", "こんにちは。")
    assert result["status"] == "failed"
    assert result["score"] is None
    assert result["raw"]["prediction"] is None
    assert "nonfinite" in result["reason"]
    json.dumps(result, allow_nan=False)


def test_inference_failure_is_not_success_and_next_call_can_recover(runtime, monkeypatch):
    metric, _, _ = runtime

    def failed(ids, mask):
        raise RuntimeError("controlled inference failure")

    monkeypatch.setattr(metric, "_predict", failed)
    result = metric.score("Hello.", "こんにちは。")
    assert result["status"] == "failed"
    assert result["score"] is None
    assert "controlled inference failure" in result["reason"]
    monkeypatch.setattr(metric, "_predict", lambda ids, mask: 1.25)
    assert metric.score("Hello.", "こんにちは。")["status"] == "completed"


def test_absent_eos_is_not_removed_as_if_it_were_content(runtime):
    metric, tokenizer, _ = runtime
    tokenizer.eos = 7
    result = metric.score("Hello.", "こんにちは。")
    assert result["status"] == "unavailable"
    assert result["score"] is None
    assert "final EOS" in result["reason"]


def test_empty_output_is_passed_to_model_not_given_a_fabricated_score(runtime):
    metric, tokenizer, _ = runtime
    result = metric.score("Hello.", "")
    assert tokenizer.calls[0][0] == "source: Hello. candidate: "
    assert result["status"] == "completed"
    assert result["score"] == 2.5


@pytest.fixture
def local_artifacts(tmp_path, monkeypatch):
    directories = {}
    for repo, attribute in [(quality_metricx.MODEL, "MODEL_FILES"), (quality_metricx.TOKENIZER, "TOKENIZER_FILES")]:
        directory = tmp_path / repo.replace("/", "-")
        directory.mkdir()
        expected = {}
        for name in ("config.json", "fixture-weights.bin"):
            content = f"{repo}/{name}".encode()
            (directory / name).write_bytes(content)
            expected[name] = (len(content), hashlib.sha256(content).hexdigest())
        directories[repo] = directory
        monkeypatch.setattr(quality_metricx, attribute, expected)
    metric = MetricX(model_path=directories[quality_metricx.MODEL])
    monkeypatch.setattr(metric, "_versions", lambda: {"torch": "2.6.0", "transformers": "4.44.2"})
    monkeypatch.setattr(metric, "_snapshot", lambda repo, revision, files, download=False: directories[repo])
    return metric, directories


def test_cache_identity_verifies_local_bytes_without_loading_model(local_artifacts, monkeypatch):
    metric, directories = local_artifacts

    def forbidden(*args, **kwargs):
        pytest.fail("Cache identity must not load model or tokenizer")

    monkeypatch.setattr(metric, "_load_model", forbidden)
    monkeypatch.setattr(metric, "_load_tokenizer", forbidden)
    identity = metric.cache_identity()
    assert identity["model"] == quality_metricx.MODEL
    assert identity["model_revision"] == quality_metricx.MODEL_REVISION
    assert identity["tokenizer_revision"] == quality_metricx.TOKENIZER_REVISION
    assert identity["runtime"]["dtype"] == "float32"
    assert identity["model_files"]["fixture-weights.bin"] == hashlib.sha256((directories[quality_metricx.MODEL] / "fixture-weights.bin").read_bytes()).hexdigest()
    assert metric.model is None
    assert metric.tokenizer is None
    metric.device = "cuda:0"
    assert metric.cache_identity() != identity


def test_cache_identity_rejects_changed_artifact_and_recovers(local_artifacts):
    metric, directories = local_artifacts
    assert metric.cache_identity() is not None
    artifact = directories[quality_metricx.MODEL] / "fixture-weights.bin"
    original = artifact.read_bytes()
    artifact.write_bytes(b"X" * len(original))
    assert metric.cache_identity() is None
    artifact.write_bytes(original)
    assert metric.cache_identity() is not None
    artifact.unlink()
    assert metric.cache_identity() is None


def test_missing_weights_stay_missing_without_download(local_artifacts, monkeypatch):
    metric, directories = local_artifacts
    (directories[quality_metricx.MODEL] / "fixture-weights.bin").unlink()
    assert metric.cache_identity() is None
    monkeypatch.setattr(metric, "_load_tokenizer", lambda: {})
    metric.tokenizer = Tokenizer()
    result = metric.score("Hello.", "こんにちは。")
    assert result["status"] == "unavailable"
    assert result["score"] is None
    assert result["provenance"]["cache_identity"] is None


def test_cache_identity_rejects_unverified_tokenizer_overrides(local_artifacts):
    metric, directories = local_artifacts
    assert metric.cache_identity() is not None
    (directories[quality_metricx.TOKENIZER] / "tokenizer.json").write_text("{}")
    assert metric.cache_identity() is None


@pytest.mark.parametrize("filename", ["pytorch_model.bin", "adapter_config.json"])
def test_cache_identity_rejects_competing_loader_overrides(local_artifacts, monkeypatch, filename):
    metric, directories = local_artifacts
    assert metric.cache_identity() is not None
    competing = directories[quality_metricx.MODEL] / filename
    competing.write_bytes(b'{"base_model_name_or_path": "unverified-model"}' if filename == "adapter_config.json" else b"unverified consolidated checkpoint")
    assert metric.cache_identity() is None
    monkeypatch.setattr(metric, "_load_tokenizer", lambda: {})
    metric.tokenizer = Tokenizer()

    def forbidden(*args, **kwargs):
        pytest.fail("Competing checkpoint must not load weights or run inference")

    monkeypatch.setattr(metric, "_load_model", forbidden)
    monkeypatch.setattr(metric, "_predict", forbidden)
    result = metric.score("Hello.", "こんにちは。")
    assert result["status"] == "unavailable"
    assert result["score"] is None
    assert result["provenance"]["cache_identity"] is None
    assert "Unverified competing MetricX loader artifact" in result["reason"]
    assert filename in result["reason"]
    competing.unlink()
    assert metric.cache_identity() is not None


def test_actual_verified_shard_loader_rejects_competing_checkpoint_and_recovers(tmp_path, monkeypatch):
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    pytest.importorskip("accelerate")
    directory = tmp_path / "tiny-random-sharded-checkpoint"
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(1041)
        config = transformers.MT5Config(
            vocab_size=250112, d_model=4, d_ff=8, d_kv=4, num_heads=1,
            num_layers=1, num_decoder_layers=1, dropout_rate=0.0,
            decoder_start_token_id=0, pad_token_id=0, eos_token_id=1,
            tie_word_embeddings=False,
        )
        original = transformers.MT5ForConditionalGeneration(config).eval()
    original.save_pretrained(directory, safe_serialization=False, max_shard_size="5MB")
    index = json.loads((directory / "pytorch_model.bin.index.json").read_text())
    shards = set(index["weight_map"].values())
    assert len(shards) == 2
    verified = {}
    for name in ("config.json", "pytorch_model.bin.index.json", *sorted(shards)):
        path = directory / name
        verified[name] = (path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())
    monkeypatch.setattr(quality_metricx, "MODEL_FILES", verified)
    metric = MetricX(model_path=directory)
    metric.tokenizer = Tokenizer()
    monkeypatch.setattr(metric, "_load_tokenizer", lambda: {})
    monkeypatch.setattr(metric, "_tokenizer_files", lambda download=False: (tmp_path, {"synthetic_tokenizer": "fixture"}))
    with torch.inference_mode():
        expected = original(
            input_ids=torch.tensor([[2] * 7]), attention_mask=torch.tensor([[1] * 7]),
            decoder_input_ids=torch.tensor([[0]]), use_cache=False, return_dict=True,
        ).logits[0, 0, quality_metricx.REGRESSION_TOKEN].item()
    completed = metric.score("Synthetic source", "Synthetic output")
    assert completed["status"] == "completed"
    assert completed["raw"]["unclipped_prediction"] == expected
    assert completed["score"] == min(25.0, max(0.0, expected))
    assert completed["provenance"]["cache_identity"] == metric.cache_identity()
    assert completed["provenance"]["cache_identity"]["model_files"] == {name: digest for name, (_, digest) in verified.items()}
    with torch.no_grad():
        original.shared.weight[0, 0] += 1
    competing = directory / "pytorch_model.bin"
    torch.save(original.state_dict(), competing)
    assert metric.cache_identity() is None
    rejected = metric.score("Synthetic source", "Synthetic output")
    assert rejected["status"] == "unavailable"
    assert rejected["score"] is None
    assert rejected["provenance"]["cache_identity"] is None
    assert "Unverified competing MetricX loader artifact" in rejected["reason"]
    competing.unlink()
    recovered = metric.score("Synthetic source", "Synthetic output")
    assert recovered["status"] == "completed"
    assert recovered["raw"]["unclipped_prediction"] == expected
    assert recovered["provenance"]["cache_identity"] == completed["provenance"]["cache_identity"]


def test_cpu_regression_stays_on_input_device_when_cuda_is_visible(monkeypatch):
    torch = pytest.importorskip("torch")
    metric = MetricX()
    captured = []

    class Model:
        def __call__(self, **inputs):
            captured.append(inputs)
            logits = torch.zeros((1, 1, quality_metricx.REGRESSION_TOKEN + 1))
            logits[0, 0, quality_metricx.REGRESSION_TOKEN] = 4.5
            return type("Output", (), {"logits": logits})()

    metric.model = Model()
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    assert metric._predict([2, 3], [1, 1]) == 4.5
    inputs = captured[0]
    assert inputs["input_ids"].device.type == "cpu"
    assert inputs["decoder_input_ids"].device == inputs["input_ids"].device
    assert inputs["decoder_input_ids"].tolist() == [[0]]
    assert inputs["use_cache"] is False
    assert inputs["return_dict"] is True
