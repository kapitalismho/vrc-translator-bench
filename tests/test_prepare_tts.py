"""Synthetic R3 consumer-boundary checks; never provider/fidelity/billing proof."""
import copy
import csv
from datetime import datetime, timezone
import http.client
import io
import json
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import threading
import urllib.error

import pytest

from tools import prepare_tts as tts

LOAD_KEY = tts.load_key
POST_ONCE = tts.post_once
GET_ONCE = tts.get_generation_once
PCM = b"\0\0\x01\0\xff\xff\xff\x7f\0\x80\0\0"
HEADERS = {"Content-Type": "audio/pcm;rate=24000;channels=1", "X-Generation-Id": "gen-synthetic-01"}
SYNTHETIC_KEY = "synthetic-router-key-never-live"


def save(path, value):
    Path(path).write_bytes(tts.json_bytes(value))


def read(path):
    return json.loads(Path(path).read_bytes())


@pytest.fixture(autouse=True)
def isolated_clock_and_network(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 27, 12, tzinfo=timezone.utc)

    def denied(*args, **kwargs):
        raise AssertionError("No live network or actual credential reads in tests")
    monkeypatch.setattr(tts, "datetime", Clock)
    monkeypatch.setattr(tts, "post_once", denied)
    monkeypatch.setattr(tts, "get_generation_once", denied)
    monkeypatch.setattr(tts, "load_key", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


@pytest.fixture
def inputs(tmp_path):
    """Entirely invented CSV/catalogue/manifest; NO original reference bodies."""
    cache = tmp_path / "cache"
    cache.mkdir()
    parents, candidates, episodes, rows = [], [], [], []
    for i in range(1, 14):
        identity = f"synthetic-parent-{i}"
        split = "development" if i < 5 else "main"
        mapping, clips = [], []
        for n, role, person in ((1, "A", 17), (2, "A", 17), (3, "B", 18), (4, "A", 17)):
            source_id = f"{len(rows):05}"
            filename = f"waves/synthetic-{i}-{n}.wav"
            text = f"Invented source {i} {n} with repeated hesitation uh uh"
            key = "synthetic/data@synthetic-revision/train/" + source_id
            rows.append({"file_name": filename, "original_speaker_id": str(person), "transcription": text})
            mapping.append({"annotation_L": n, "role": role, "original_person": person, "natural_source_key": key})
            clips.append({"annotation_L": n, "logical_role": role, "original_speaker_id": person,
                          "natural_source_key": key, "upstream_split": "train", "upstream_id": source_id,
                          "archive_member": filename, "reference_utf8_sha256": tts.sha256(text.encode())})
        common = {"id": identity, "source_case_id": identity, "dependency_group_id": "synthetic-group-" + split,
                  "project_split": split, "roles": {"A": 17, "B": 18}}
        parent = {**common, "reference_sha256": tts.sha256(f"absent-original-reference-{i}".encode()),
                  "source_to_playback": mapping, "reference_path": "absent/never-open-this.json"}
        parents.append(parent)
        candidates.append({**common, "kind": "T1", "clips": clips})
        episodes.append({"id": f"synthetic-ja-ko-{i}", "parent_id": identity,
                         "source_case_id": identity, "dependency_group_id": common["dependency_group_id"],
                         "project_split": split, "parent_reference_sha256": parent["reference_sha256"],
                         "unresolved_source_spans": [],
                         "turns": [{"id": "t1", "role": "A", "source_annotation_Ls": [1, 2],
                                    "text": "ええ、ええ。三つです。", "adaptation_notes": "Synthetic hesitation retained"},
                                   {"id": "t2", "role": "B", "source_annotation_Ls": [3],
                                    "text": "아니요, 둘입니다.", "adaptation_notes": []},
                                   {"id": "t3", "role": "A", "source_annotation_Ls": [4],
                                    "text": "二つですね。", "adaptation_notes": ""}]})
    metadata = {}
    for split in ("train", "test", "validation"):
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=["file_name", "original_speaker_id", "transcription"])
        writer.writeheader()
        if split == "train":
            writer.writerows(rows)
        payload = buffer.getvalue().encode()
        name = split + "_metadata.csv"
        (cache / name).write_bytes(payload)
        metadata[name] = {"sha256": tts.sha256(payload), "bytes": len(payload)}
    catalogue = {"dataset": "synthetic/data", "revision": "synthetic-revision", "license": "synthetic-license",
                 "source_metadata": metadata, "candidates": candidates}
    catalogue_path = tmp_path / "catalogue.json"
    save(catalogue_path, catalogue)
    manifest = {"root_dataset": catalogue["dataset"], "root_revision": catalogue["revision"],
                "source_license": catalogue["license"], "catalogue_sha256": tts.sha256(catalogue_path.read_bytes()),
                "parents": parents, "development_additional_take_parent_ids": [parents[0]["id"], parents[2]["id"]]}
    manifest_path = tmp_path / "parents.json"
    save(manifest_path, manifest)
    bundle = {"schema_version": 1, "parent_manifest_sha256": tts.sha256(manifest_path.read_bytes()), "episodes": episodes[:4]}
    scripts_path = tmp_path / "scripts.json"
    save(scripts_path, bundle)
    return {"scripts": scripts_path, "parents": manifest_path, "catalogue": catalogue_path, "cache": cache,
            "bundle": bundle, "all_episodes": episodes}


def prepare_inputs(inputs, output, split="development"):
    return tts.prepare(inputs["scripts"], inputs["parents"], inputs["cache"], output, inputs["catalogue"], split)


@pytest.fixture
def prepared(inputs, tmp_path):
    run = tmp_path / "run"
    result = prepare_inputs(inputs, run)
    approval = {"schema_version": 1, "plan_sha256": result["plan_sha256"], "run_directory": str(run.resolve()), "owner": "synthetic owner",
                "approved_at": "2026-10-27T00:00:00Z", "expires_on": "2026-12-31", "scope": tts.SCOPE,
                "max_client_posts": 6, "api_cap_usd": "1.00", "api": tts.ENDPOINT, "model": tts.MODEL,
                "rates_usd_per_million": tts.RATES, "provider_policy": tts.POLICY,
                "setup_confirmed": True, "terms_and_rights_confirmed": True, "scripts_approved": True,
                "approval_source": "synthetic chat record", "approval_evidence": "Explicit synthetic six-client-POST scope"}
    approval_path = tmp_path / "approval.json"
    save(approval_path, approval)
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    env_file = secrets / ".env.local"
    env_file.write_text("UNRELATED_KEY=not-used\n" + tts.KEY_NAME + "=" + SYNTHETIC_KEY + "\n", encoding="utf-8")
    return run, approval_path, env_file


def enable_synthetic_key(monkeypatch):
    monkeypatch.setattr(tts, "load_key", LOAD_KEY)


def test_source_linked_preparation_preserves_identity_without_missing_reference_gate(inputs, tmp_path):
    run = tmp_path / "prepared"
    result = prepare_inputs(inputs, run)
    plan = read(run / "plan.json")
    assert result["plan_sha256"] == tts.sha256((run / "plan.json").read_bytes())
    assert plan["scripts_sha256"] == tts.sha256(inputs["scripts"].read_bytes())
    assert plan["six_client_posts_estimate_usd"] == "0.909312"
    assert [c["episode_id"] for c in plan["calls"]] == [f"synthetic-ja-ko-{i}" for i in (1, 2, 3, 4, 1, 3)]
    assert [c["take"] for c in plan["calls"]] == [1, 1, 1, 1, 2, 2]
    assert len(plan["requests"]) == 4
    evidence = read(run / "source-validation.json")
    assert evidence["original_reference_bodies_verified"] is False
    assert evidence["original_r2_handoff_complete"] is False
    assert len(evidence["parents"]) == 4 and len(evidence["parents"][0]["source_entries"]) == 4
    assert evidence["parents"][0]["expected_parent_reference_sha256"] == inputs["bundle"]["episodes"][0]["parent_reference_sha256"]
    assert not (inputs["parents"].parent / "absent").exists()
    with pytest.raises(FileExistsError):
        prepare_inputs(inputs, run)


def test_dev_only_and_unique_plan_prevent_approval_refill(inputs, tmp_path):
    inputs["bundle"]["episodes"] = inputs["bundle"]["episodes"][:4]
    save(inputs["scripts"], inputs["bundle"])
    first = prepare_inputs(inputs, tmp_path / "first")
    second = prepare_inputs(inputs, tmp_path / "second")
    assert first["planned_client_posts"] == second["planned_client_posts"] == 6
    assert first["plan_sha256"] != second["plan_sha256"]


@pytest.mark.parametrize("mutation", ["manifest", "catalogue", "csv", "reference_identity", "source_case", "dependency",
                                       "split", "foreign", "duplicate", "missing", "duplicate_L", "boolean_L", "role", "split_run",
                                       "person", "source_file", "source_text", "mapping_order"])
def test_source_identity_and_complete_run_rejection(inputs, tmp_path, mutation):
    bundle, catalogue, manifest = inputs["bundle"], read(inputs["catalogue"]), read(inputs["parents"])
    episode = bundle["episodes"][0]
    if mutation == "manifest":
        bundle["parent_manifest_sha256"] = "0" * 64
    elif mutation == "catalogue":
        inputs["catalogue"].write_bytes(b"{}")
    elif mutation == "csv":
        (inputs["cache"] / "train_metadata.csv").write_bytes(b"changed")
    elif mutation == "reference_identity":
        episode["parent_reference_sha256"] = "0" * 64
    elif mutation == "source_case":
        episode["source_case_id"] = "different"
    elif mutation == "dependency":
        episode["dependency_group_id"] = "different"
    elif mutation == "split":
        episode["project_split"] = "main"
    elif mutation == "foreign":
        episode["parent_id"] = "unrelated"
    elif mutation == "duplicate":
        bundle["episodes"].append(copy.deepcopy(episode))
    elif mutation == "missing":
        episode["turns"][0]["source_annotation_Ls"] = [1]
    elif mutation == "duplicate_L":
        episode["turns"][0]["source_annotation_Ls"] = [1, 1]
    elif mutation == "boolean_L":
        episode["turns"][0]["source_annotation_Ls"] = [True, 2]
    elif mutation == "role":
        episode["turns"][0]["role"] = "B"
    elif mutation == "split_run":
        turn = copy.deepcopy(episode["turns"][0])
        turn.update(id="extra", source_annotation_Ls=[2])
        episode["turns"][0]["source_annotation_Ls"] = [1]
        episode["turns"].insert(1, turn)
    else:
        if mutation == "person":
            catalogue["candidates"][0]["clips"][0]["original_speaker_id"] = 18
        elif mutation == "source_file":
            catalogue["candidates"][0]["clips"][0]["archive_member"] = "different.wav"
        elif mutation == "source_text":
            catalogue["candidates"][0]["clips"][0]["reference_utf8_sha256"] = "0" * 64
        else:
            manifest["parents"][0]["source_to_playback"].reverse()
        save(inputs["catalogue"], catalogue)
        manifest["catalogue_sha256"] = tts.sha256(inputs["catalogue"].read_bytes())
        save(inputs["parents"], manifest)
        bundle["parent_manifest_sha256"] = tts.sha256(inputs["parents"].read_bytes())
    save(inputs["scripts"], bundle)
    with pytest.raises(ValueError):
        prepare_inputs(inputs, tmp_path / "blocked")
    assert not (tmp_path / "blocked").exists()


@pytest.mark.parametrize("draft", [False, True])
def test_unresolved_or_draft_scripts_block_preparation(inputs, tmp_path, draft):
    if draft:
        inputs["bundle"]["preparation_status"] = "draft_pending_source_restore_and_bilingual_review"
    else:
        inputs["bundle"]["episodes"][0]["unresolved_source_spans"] = [{"source_annotation_L": 1, "cause": "synthetic unknown"}]
    save(inputs["scripts"], inputs["bundle"])
    with pytest.raises(ValueError, match="Draft|Unresolved"):
        prepare_inputs(inputs, tmp_path / "not-ready")
    assert not (tmp_path / "not-ready").exists()


@pytest.mark.parametrize("mutation", ["missing", "plan_hash", "run_directory", "setup", "rights", "source", "expiry", "scope", "route",
                                       "model", "rates", "privacy", "main", "request", "scripts", "evidence", "unresolved"])
def test_preflight_never_reads_key_or_submits(prepared, mutation):
    run, approval_path, env_file = prepared
    approval = read(approval_path)
    if mutation == "missing":
        approval_path.unlink()
    elif mutation == "plan_hash":
        approval["plan_sha256"] = "0" * 64
    elif mutation == "run_directory":
        del approval["run_directory"]
    elif mutation == "setup":
        approval["setup_confirmed"] = False
    elif mutation == "rights":
        del approval["terms_and_rights_confirmed"]
    elif mutation == "source":
        approval["approval_source"] = ""
    elif mutation == "expiry":
        approval["expires_on"] = "2027-01-01"
    elif mutation == "scope":
        approval["max_client_posts"] = 7
    elif mutation == "route":
        approval["api"] = "https://other.invalid"
    elif mutation == "model":
        approval["model"] = "google/gemini-3.8-flash-lite-tts"
    elif mutation == "rates":
        approval["rates_usd_per_million"]["output_audio"] = "18.00"
    elif mutation == "privacy":
        approval["provider_policy"]["zdr"] = False
    elif mutation in ("request", "scripts", "evidence"):
        path = {"request": "requests/synthetic-ja-ko-1.json", "scripts": "scripts.json", "evidence": "source-validation.json"}[mutation]
        with (run / path).open("ab") as target:
            target.write(b" ")
    else:
        plan = read(run / "plan.json")
        bundle = read(run / "scripts.json")
        if mutation == "main":
            bundle["episodes"][0]["project_split"] = "main"
        else:
            bundle["episodes"][0]["unresolved_source_spans"] = [{"source_annotation_L": 1}]
        save(run / "scripts.json", bundle)
        plan["scripts_sha256"] = tts.sha256((run / "scripts.json").read_bytes())
        save(run / "plan.json", plan)
        approval["plan_sha256"] = tts.sha256((run / "plan.json").read_bytes())
    if mutation != "missing":
        save(approval_path, approval)
    with pytest.raises((ValueError, FileNotFoundError)):
        tts.generate(run, approval_path, "pilot-01", env_file)
    assert not (run / "attempts/pilot-01").exists()
    assert not (run / ".generate.lock").exists()


def test_reserved_post_raw_pcm_wav_consumer_and_secret_file_preservation(prepared, monkeypatch):
    run, approval, env_file = prepared
    enable_synthetic_key(monkeypatch)
    secret_bytes = env_file.read_bytes()
    sent = []

    def post(payload, key):
        attempt = run / "attempts/pilot-01"
        reservation = read(attempt / "reservation.json")
        assert reservation["client_post_allowance_consumed"] is True
        assert reservation["reserved_usd"] == "0.151552" and reservation["upstream_attempt_count"] is None
        assert (attempt / "approval.json").read_bytes() == approval.read_bytes()
        assert key == SYNTHETIC_KEY
        request = json.loads(payload)
        frozen_turns = read(run / "scripts.json")["episodes"][0]["turns"]
        assert [item["text"] for item in request["input"]] == [turn["text"] for turn in frozen_turns]
        assert [item["voice"] for item in request["input"]] == ["Puck", "Kore", "Puck"]
        assert all(set(item) == {"text", "voice"} for item in request["input"])
        assert request["instructions"] and all(request["instructions"] not in item["text"] for item in request["input"])
        sent.append(payload)
        return 200, {**HEADERS, "Authorization": "must-never-be-recorded"}, PCM, True
    monkeypatch.setattr(tts, "post_once", post)
    result = tts.generate(run, approval, "pilot-01", env_file)
    assert result["status"] == "generated_pending_actual_audio_review" and len(sent) == 1
    attempt = run / "attempts/pilot-01"
    assert (attempt / "audio.pcm").read_bytes() == PCM
    assert tts.decode_wave((attempt / "audio.wav").read_bytes()) == PCM
    ledger = read(attempt / "result.json")
    assert ledger["usage"] is ledger["api_consumption_usd"] is None
    assert ledger["adopted"] is False and ledger["generation_id"] == HEADERS["X-Generation-Id"]
    assert ledger["pcm16le_sha256"] == tts.sha256(PCM)
    assert read(attempt / "response-metadata.json")["headers"] == HEADERS
    assert env_file.read_bytes() == secret_bytes
    assert all(SYNTHETIC_KEY.encode() not in p.read_bytes() for p in run.rglob("*") if p.is_file())
    with pytest.raises(ValueError, match="next planned"):
        tts.generate(run, approval, "pilot-01", env_file)
    assert len(sent) == 1


def test_failed_and_uncertain_posts_exhaust_allowance_without_retry(prepared, monkeypatch):
    run, approval, env_file = prepared
    enable_synthetic_key(monkeypatch)
    posted = []

    def post(payload, key):
        posted.append(payload)
        if len(posted) % 2:
            raise TimeoutError("never log " + SYNTHETIC_KEY)
        return 500, {"Content-Type": "application/json"}, tts.json_bytes({"error": SYNTHETIC_KEY}), True
    monkeypatch.setattr(tts, "post_once", post)
    for i in range(1, 7):
        result = tts.generate(run, approval, f"pilot-{i:02}", env_file)
        assert result["client_post_allowance_consumed"] is True and result["reserved_client_posts"] == i
        assert result["status"] in ("uncertain_transport_or_local_failure", "failed_response_retained")
    with pytest.raises(ValueError, match="exhausted"):
        tts.generate(run, approval, "pilot-07", env_file)
    assert len(posted) == 6
    assert read(run / "attempts/pilot-02/result.json")["api_consumption_usd"] is None
    assert b"REDACTED" in (run / "attempts/pilot-02/response.safe.bin").read_bytes()
    assert all(SYNTHETIC_KEY.encode() not in p.read_bytes() for p in run.rglob("*") if p.is_file())


def test_interrupted_slot_consumed_and_stale_lock_not_reclaimed(prepared, monkeypatch):
    run, approval, env_file = prepared
    enable_synthetic_key(monkeypatch)
    monkeypatch.setattr(tts, "post_once", lambda *args: (200, HEADERS, PCM, True))
    (run / "attempts/pilot-01").mkdir(parents=True)
    with pytest.raises(ValueError, match="next planned"):
        tts.generate(run, approval, "pilot-01", env_file)
    assert tts.generate(run, approval, "pilot-02", env_file)["reserved_client_posts"] == 2
    (run / ".generate.lock").write_bytes(b"stale synthetic lock")
    with pytest.raises(ValueError, match="locked"):
        tts.generate(run, approval, "pilot-03", env_file)
    assert not (run / "attempts/pilot-03").exists()


def test_concurrent_calls_do_not_duplicate_submission(prepared, monkeypatch):
    run, approval, env_file = prepared
    enable_synthetic_key(monkeypatch)
    entered, release, outcomes = threading.Event(), threading.Event(), []

    def post(*args):
        entered.set()
        assert release.wait(10)
        return 200, HEADERS, PCM, True
    monkeypatch.setattr(tts, "post_once", post)
    worker = threading.Thread(target=lambda: outcomes.append(tts.generate(run, approval, "pilot-01", env_file)))
    worker.start()
    try:
        assert entered.wait(10)
        with pytest.raises(ValueError, match="locked"):
            tts.generate(run, approval, "pilot-01", env_file)
    finally:
        release.set()
        worker.join(10)
    assert len(outcomes) == 1 and outcomes[0]["reserved_client_posts"] == 1
    assert len(list((run / "attempts").iterdir())) == 1


@pytest.mark.parametrize("body,content_type,complete", [(b"", HEADERS["Content-Type"], True),
    (b"\x01", HEADERS["Content-Type"], True), (b"RIFF00", HEADERS["Content-Type"], True),
    (PCM, "audio/pcm;rate=16000;channels=1", True), (PCM, "audio/pcm;rate=24000;channels=2", True),
    (PCM, "audio/wav", True), (PCM, "audio/pcm", True), (PCM, HEADERS["Content-Type"], False),
    (b'{"error":"not audio"}', "application/json", True)])
def test_malformed_truncated_or_wrong_format_response_retained(prepared, monkeypatch, body, content_type, complete):
    run, approval, env_file = prepared
    enable_synthetic_key(monkeypatch)
    monkeypatch.setattr(tts, "post_once", lambda *args: (200, {"Content-Type": content_type}, body, complete))
    result = tts.generate(run, approval, "pilot-01", env_file)
    assert result["status"] == "failed_response_retained"
    attempt = run / "attempts/pilot-01"
    assert (attempt / ("audio.pcm" if content_type.startswith("audio/") else "response.safe.bin")).read_bytes() == body
    assert not (attempt / "audio.wav").exists()
    assert read(attempt / "reservation.json")["client_post_allowance_consumed"] is True


@pytest.mark.parametrize("assignment,expected", [
    ("VRC_BENCH_GEMINI_API_KEY=literal-key", "literal-key"),
    (' VRC_BENCH_GEMINI_API_KEY = "literal-key" ', "literal-key"),
    ("VRC_BENCH_GEMINI_API_KEY='literal-key'", "literal-key"),
    ('export VRC_BENCH_GEMINI_API_KEY="literal-key"', "literal-key"),
    ("export VRC_BENCH_GEMINI_API_KEY=one\nVRC_BENCH_GEMINI_API_KEY=two", None),
    ("OPENROUTER_API_KEY=ambient\nGOOGLE_API_KEY=ambient", None),
    ("VRC_BENCH_GEMINI_API_KEY=", None),
    ("VRC_BENCH_GEMINI_API_KEY=one\nVRC_BENCH_GEMINI_API_KEY=two", None),
    ("VRC_BENCH_GEMINI_API_KEY=${OPENROUTER_API_KEY}", None),
    ("VRC_BENCH_GEMINI_API_KEY=$(command)", None),
    ("VRC_BENCH_GEMINI_API_KEY=%OTHER%", None),
    ("VRC_BENCH_GEMINI_API_KEY=literal #comment", None),
    ('VRC_BENCH_GEMINI_API_KEY="unterminated', None)])
def test_exact_literal_secret_parser_no_expansion_or_fallback(tmp_path, monkeypatch, assignment, expected):
    env_file = tmp_path / ".env.local"
    env_file.write_text(assignment, encoding="utf-8")
    before = env_file.read_bytes()
    monkeypatch.setattr(tts.os, "environ", {tts.KEY_NAME: "must-not-be-read", "OPENROUTER_API_KEY": "must-not-be-read"})
    if expected is None:
        with pytest.raises(ValueError):
            LOAD_KEY(env_file)
    else:
        assert LOAD_KEY(env_file) == expected
    assert env_file.read_bytes() == before


def test_missing_selected_secret_file_has_no_ambient_fallback(prepared, monkeypatch):
    run, approval, env_file = prepared
    enable_synthetic_key(monkeypatch)
    env_file.unlink()
    monkeypatch.setattr(tts.os, "environ", {tts.KEY_NAME: "ambient-must-not-be-used"})
    with pytest.raises(FileNotFoundError):
        tts.generate(run, approval, "pilot-01", env_file)
    assert not (run / "attempts/pilot-01").exists()


@pytest.mark.parametrize("partial,error,read_error", [(False, False, None), (True, False, None), (False, True, None),
                                                    (False, False, TimeoutError), (False, False, OSError)])
def test_real_stdlib_transport_allowlists_headers_and_reads_once(monkeypatch, partial, error, read_error):
    seen = []

    class Headers:
        def get(self, name):
            assert name in ("Content-Type", "X-Generation-Id")
            return HEADERS.get(name)

    class Response:
        status = 200
        headers = Headers()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            if partial:
                raise http.client.IncompleteRead(PCM, 10)
            if read_error:
                raise read_error("Sensitive body-read failure must not be logged")
            return PCM

    class Opener:
        def open(self, request, timeout):
            seen.append(request)
            assert request.full_url == tts.ENDPOINT and request.method == "POST"
            assert request.get_header("Authorization") == "Bearer synthetic-key"
            assert request.get_header("X-goog-api-key") is None and timeout == 180
            if error:
                raise urllib.error.HTTPError(tts.ENDPOINT, 500, "sensitive message", HEADERS, io.BytesIO(b"failure"))
            return Response()

    def build(*handlers):
        assert handlers[0].proxies == {} and isinstance(handlers[1], tts.NoRedirect)
        assert handlers[1].redirect_request(None, None, 302, None, None, "https://foreign.invalid") is None
        return Opener()
    monkeypatch.setattr(tts.urllib.request, "build_opener", build)
    status, headers, body, complete = POST_ONCE(b"{}", "synthetic-key")
    assert status == (500 if error else 200) and headers == HEADERS
    assert body == (b"failure" if error else b"" if read_error else PCM)
    assert complete is (not partial and read_error is None)
    assert len(seen) == 1


def generate_for_accounting(prepared, monkeypatch):
    run, approval, env_file = prepared
    enable_synthetic_key(monkeypatch)
    monkeypatch.setattr(tts, "post_once", lambda *args: (200, HEADERS, PCM, True))
    tts.generate(run, approval, "pilot-01", env_file)
    return run, env_file


@pytest.mark.parametrize("cost", [None, 0, 0.012345, 0.151552])
def test_one_shot_accounting_preserves_metadata_nulls_and_never_refunds(prepared, monkeypatch, cost):
    run, env_file = generate_for_accounting(prepared, monkeypatch)
    original_result = (run / "attempts/pilot-01/result.json").read_bytes()
    called = []
    data = {"id": HEADERS["X-Generation-Id"], "native_tokens_prompt": 12, "provider_name": "synthetic-provider",
            "model": tts.MODEL, "provider_responses": [{"status": "synthetic-route-observation"}]}
    if cost is not None:
        data["total_cost"] = cost
    body = tts.json_bytes({"data": data})

    def get(generation_id, key):
        assert generation_id == HEADERS["X-Generation-Id"] and key == SYNTHETIC_KEY
        assert (run / "attempts/pilot-01/reconciliation/reservation.json").exists()
        called.append(generation_id)
        return 200, {"Content-Type": "application/json"}, body, True
    monkeypatch.setattr(tts, "get_generation_once", get)
    result = tts.reconcile(run, "pilot-01", env_file)
    assert result["status"] == "accounting_recorded" and result["api_consumption_usd"] == cost
    output = run / "attempts/pilot-01/reconciliation"
    ledger = read(output / "result.json")
    assert (output / "response.safe.json").read_bytes() == body
    assert ledger["metadata"]["native_tokens_completion"] is None
    assert ledger["metadata"]["native_tokens_prompt"] == 12 and ledger["metadata"]["upstream_id"] is None
    assert ledger["metadata"]["provider_responses"] == data["provider_responses"]
    assert ledger["client_post_allowance_changed"] is False
    assert (run / "attempts/pilot-01/result.json").read_bytes() == original_result
    with pytest.raises(ValueError, match="already attempted"):
        tts.reconcile(run, "pilot-01", env_file)
    assert len(called) == 1
    assert tts.generate(run, prepared[1], "pilot-02", env_file)["reserved_client_posts"] == 2


@pytest.mark.parametrize("mode", ["timeout", "http", "malformed", "mismatch"])
def test_failed_accounting_remains_unknown_and_cannot_poll(prepared, monkeypatch, mode):
    run, env_file = generate_for_accounting(prepared, monkeypatch)
    called = []

    def get(*args):
        called.append(args)
        if mode == "timeout":
            raise TimeoutError(SYNTHETIC_KEY)
        body = b"{" if mode == "malformed" else tts.json_bytes({"data": {"id": "wrong-id", "error": SYNTHETIC_KEY}})
        return (500 if mode == "http" else 200), {"Content-Type": "application/json"}, body, True
    monkeypatch.setattr(tts, "get_generation_once", get)
    result = tts.reconcile(run, "pilot-01", env_file)
    assert result["status"] == "accounting_unknown" and result["api_consumption_usd"] is None
    with pytest.raises(ValueError, match="already attempted"):
        tts.reconcile(run, "pilot-01", env_file)
    assert len(called) == 1
    assert all(SYNTHETIC_KEY.encode() not in p.read_bytes() for p in run.rglob("*") if p.is_file())
    assert tts.generate(run, prepared[1], "pilot-02", env_file)["reserved_client_posts"] == 2


def test_accounting_requires_recorded_generation_id_before_secret_read(prepared, monkeypatch):
    run, env_file = generate_for_accounting(prepared, monkeypatch)
    result_path = run / "attempts/pilot-01/result.json"
    result = read(result_path)
    result["generation_id"] = None
    save(result_path, result)
    monkeypatch.setattr(tts, "load_key", lambda *args: pytest.fail("Must reject before credential access"))
    with pytest.raises(ValueError, match="recorded generation ID"):
        tts.reconcile(run, "pilot-01", env_file)
    assert not (run / "attempts/pilot-01/reconciliation").exists()


def test_accounting_transport_encodes_id_and_uses_only_get(monkeypatch):
    seen = []

    def open_once(request):
        seen.append(request)
        assert request.method == "GET" and request.data is None
        assert request.full_url == "https://openrouter.ai/api/v1/generation?id=gen-test%3A123"
        assert request.get_header("Authorization") == "Bearer synthetic-key"
        return 200, {}, b"{}", True
    monkeypatch.setattr(tts, "open_once", open_once)
    assert GET_ONCE("gen-test:123", "synthetic-key") == (200, {}, b"{}", True)
    assert len(seen) == 1


@pytest.fixture
def split_inputs(tmp_path):
    wav_path = tmp_path / "generated.wav"
    wav_path.write_bytes(tts.encode_wave(PCM))
    review = {"schema_version": 1, "wav_sha256": tts.sha256(wav_path.read_bytes()), "actual_audio_reviewed": True,
              "reviewer": "synthetic reviewer", "reviewed_at": "2026-10-27",
              "evidence": "synthetic boundary exercise, NOT real speech review",
              "silence_policy": "Assign leading/trailing silence to adjoining role without deleting samples",
              "intervals": [{"start_sample": 0, "end_sample": 3, "role": "A"},
                            {"start_sample": 3, "end_sample": 6, "role": "B"}]}
    review_path = tmp_path / "review.json"
    save(review_path, review)
    return wav_path, review_path, review


def test_split_exact_samples_equal_length_hashes_and_noncertification(split_inputs, tmp_path):
    wav_path, review_path, review = split_inputs
    output = tmp_path / "split"
    assert tts.split(wav_path, review_path, output)["pcm_reconstruction"] == "passed"
    a, b = (tts.decode_wave((output / (role + ".wav")).read_bytes()) for role in ("A", "B"))
    assert len(PCM) == len(a) == len(b) == 12
    assert a == PCM[:6] + bytes(6) and b == bytes(6) + PCM[6:]
    summed = b"".join(struct.pack("<h", x + y) for (x,), (y,) in zip(struct.iter_unpack("<h", a), struct.iter_unpack("<h", b)))
    assert summed == PCM
    timeline = read(output / "timeline.json")
    assert timeline["assets"]["A"]["pcm16le_sha256"] == tts.sha256(a)
    assert timeline["assets"]["B"]["wav_sha256"] == tts.sha256((output / "B.wav").read_bytes())
    assert timeline["intervals"] == review["intervals"]
    assert timeline["adopted"] is False and "NOT speaker/content certification" in timeline["reconstruction"]
    assert (output / "original.wav").read_bytes() == wav_path.read_bytes()
    with pytest.raises(FileExistsError):
        tts.split(wav_path, review_path, output)


@pytest.mark.parametrize("mutation", ["hash", "review", "evidence", "silence", "gap", "overlap", "fraction", "out_of_bounds", "tail", "zero", "role"])
def test_split_rejects_invalid_review_or_sample_partition(split_inputs, tmp_path, mutation):
    wav_path, review_path, review = split_inputs
    if mutation == "hash":
        review["wav_sha256"] = "0" * 64
    elif mutation == "review":
        review["actual_audio_reviewed"] = False
    elif mutation == "evidence":
        review["evidence"] = ""
    elif mutation == "silence":
        review["silence_policy"] = ""
    elif mutation == "gap":
        review["intervals"][1]["start_sample"] = 4
    elif mutation == "overlap":
        review["intervals"][1]["start_sample"] = 2
    elif mutation == "fraction":
        review["intervals"][0]["start_sample"] = 0.0
    elif mutation == "out_of_bounds":
        review["intervals"][1]["end_sample"] = 7
    elif mutation == "tail":
        review["intervals"][1]["end_sample"] = 5
    elif mutation == "zero":
        review["intervals"][0]["end_sample"] = 0
    else:
        review["intervals"][1]["role"] = "unknown"
    save(review_path, review)
    with pytest.raises(ValueError):
        tts.split(wav_path, review_path, tmp_path / "bad-split")
    assert not (tmp_path / "bad-split").exists()


def test_partial_wav_sample_is_never_silently_discarded():
    with pytest.raises(ValueError, match="truncated"):
        tts.decode_wave(tts.encode_wave(b"\x01\x00\xff"))


def test_actual_cli_offline_prepare_split_and_missing_approval_smoke(inputs, split_inputs, tmp_path):
    wav_path, review_path, _ = split_inputs
    guard = tmp_path / "guard"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(
        "import socket\ndef denied(*a, **k):\n    raise RuntimeError('network disabled for CLI smoke')\n"
        "socket.socket.connect = denied\nsocket.create_connection = denied\n", encoding="utf-8")
    env = {"PYTHONPATH": str(guard), "PYTHONIOENCODING": "utf-8"}
    script = str(Path(tts.__file__).resolve())
    commands = [[sys.executable, script, "prepare", "--scripts", str(inputs["scripts"]), "--parents", str(inputs["parents"]),
                 "--catalogue", str(inputs["catalogue"]), "--source-cache", str(inputs["cache"]), "--output", str(tmp_path / "cli-run")],
                [sys.executable, script, "split", "--wav", str(wav_path), "--review", str(review_path), "--output", str(tmp_path / "cli-split")]]
    for command in commands:
        result = subprocess.run(command, env=env, text=True, encoding="utf-8", capture_output=True, timeout=20)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["status"] in ("prepared_not_authorized_not_audio_reviewed", "split_not_adopted")
    result = subprocess.run([sys.executable, script, "generate", "--run", str(tmp_path / "cli-run"),
                             "--approval", str(tmp_path / "no-approval.json"), "--call", "pilot-01", "--env-file", "never-read"],
                            env=env, text=True, encoding="utf-8", capture_output=True, timeout=20)
    assert result.returncode == 1 and "blocked" in result.stderr
    assert not (tmp_path / "cli-run/attempts/pilot-01").exists()


def test_attempt_and_accounting_persistence_across_fresh_processes(prepared):
    run, approval, env_file = prepared
    code = """
import socket, sys
from datetime import datetime, timezone
from tools import prepare_tts as t
def denied(*args, **kwargs):
    raise RuntimeError('network disabled')
socket.socket.connect = denied
socket.create_connection = denied
t.datetime = type('Clock', (), {'now': staticmethod(lambda tz=None: datetime(2026, 10, 27, tzinfo=timezone.utc))})
mode = sys.argv.pop(1)
def post(*args):
    if mode == 'timeout':
        raise TimeoutError('synthetic unknown outcome')
    return 200, HEADERS, PCM, True
t.post_once = post
t.get_generation_once = lambda *args: (200, {'Content-Type':'application/json'}, b'{"data":{"total_cost":0.01}}', True)
raise SystemExit(t.main())
""".replace("HEADERS", repr(HEADERS)).replace("PCM", repr(PCM))
    base = [sys.executable, "-c", code]
    common = ["--run", str(run), "--env-file", str(env_file)]
    for mode, command, expected_code in (
        ("timeout", ["generate"] + common + ["--approval", str(approval), "--call", "pilot-01"], 1),
        ("success", ["generate"] + common + ["--approval", str(approval), "--call", "pilot-01"], 1),
        ("success", ["generate"] + common + ["--approval", str(approval), "--call", "pilot-02"], 0),
        ("success", ["reconcile"] + common + ["--call", "pilot-02"], 0),
        ("success", ["reconcile"] + common + ["--call", "pilot-02"], 1)):
        result = subprocess.run(base + [mode] + command, cwd=Path(tts.__file__).resolve().parents[1],
                                env={"PYTHONIOENCODING": "utf-8"}, text=True, encoding="utf-8", capture_output=True, timeout=20)
        assert result.returncode == expected_code, result.stderr
    assert read(run / "attempts/pilot-01/reservation.json")["client_post_allowance_consumed"] is True
    assert read(run / "attempts/pilot-01/result.json")["status"] == "uncertain_transport_or_local_failure"
    assert read(run / "attempts/pilot-02/result.json")["status"] == "generated_pending_actual_audio_review"
    assert read(run / "attempts/pilot-02/reconciliation/result.json")["api_consumption_usd"] == 0.01
    assert {p.name for p in (run / "attempts").iterdir()} == {"pilot-01", "pilot-02"}


def test_selected_secret_inside_run_is_rejected_without_copying_or_consuming(prepared, monkeypatch):
    run, approval, env_file = prepared
    selected = run / ".env.local"
    selected.write_bytes(env_file.read_bytes())
    original = selected.read_bytes()
    enable_synthetic_key(monkeypatch)
    with pytest.raises(ValueError, match="outside run"):
        tts.generate(run, approval, "pilot-01", selected)
    assert selected.read_bytes() == original
    assert not (run / "attempts/pilot-01").exists()


def test_one_approval_allows_original_alias_but_rejects_seven_preoperation_copies(prepared, monkeypatch, tmp_path):
    run, approval, env_file = prepared
    copies = [tmp_path / f"copied-run-{i}" for i in range(7)]
    for copied in copies:
        shutil.copytree(run, copied)  # Every copy predates the first reservation.
    posted = []
    enable_synthetic_key(monkeypatch)

    def post(*args):
        posted.append(args)
        return 200, HEADERS, PCM, True
    monkeypatch.setattr(tts, "post_once", post)
    alias = run / ".." / run.name
    assert tts.generate(alias, approval, "pilot-01", env_file)["reserved_client_posts"] == 1
    monkeypatch.setattr(tts, "load_key", lambda *args: pytest.fail("Relocated copy must fail before credential access"))
    for copied in copies:
        with pytest.raises(ValueError, match="canonical run directory"):
            tts.generate(copied, approval, "pilot-01", env_file)
        assert not (copied / "attempts").exists()
    assert len(posted) == 1
    copied_result = tmp_path / "copied-after-generation"
    shutil.copytree(run, copied_result)
    with pytest.raises(ValueError, match="canonical run directory"):
        tts.reconcile(copied_result, "pilot-01", env_file)
    assert not (copied_result / "attempts/pilot-01/reconciliation").exists()


@pytest.mark.parametrize("cost", [1.01, 1.00, 0.16, 0.151553])
def test_recorded_overcap_or_overreservation_cost_blocks_next_post(prepared, monkeypatch, cost):
    run, env_file = generate_for_accounting(prepared, monkeypatch)
    monkeypatch.setattr(tts, "get_generation_once", lambda *args:
                        (200, {"Content-Type": "application/json"}, tts.json_bytes({"data": {"total_cost": cost}}), True))
    assert tts.reconcile(run, "pilot-01", env_file)["api_consumption_usd"] == cost
    accounting_path = run / "attempts/pilot-01/reconciliation/result.json"
    retained = accounting_path.read_bytes()
    monkeypatch.setattr(tts, "load_key", lambda *args: pytest.fail("Known budget contradiction must precede credential access"))
    monkeypatch.setattr(tts, "post_once", lambda *args: pytest.fail("Known budget contradiction cannot authorize another POST"))
    with pytest.raises(ValueError, match="cap|reservation"):
        tts.generate(run, prepared[1], "pilot-02", env_file)
    assert not (run / "attempts/pilot-02").exists()
    assert accounting_path.read_bytes() == retained
    assert read(run / "attempts/pilot-01/reservation.json")["client_post_allowance_consumed"] is True


@pytest.mark.parametrize("mutation", ["disagree", "missing", "partial", "interrupted"])
def test_malformed_retained_budget_evidence_fails_closed(prepared, monkeypatch, mutation):
    run, env_file = generate_for_accounting(prepared, monkeypatch)
    monkeypatch.setattr(tts, "get_generation_once", lambda *args:
                        (200, {"Content-Type": "application/json"}, b'{"data":{"total_cost":0}}', True))
    assert tts.reconcile(run, "pilot-01", env_file)["status"] == "accounting_recorded"
    path = run / "attempts/pilot-01/reconciliation/result.json"
    record = read(path)
    if mutation == "disagree":
        record["metadata"]["total_cost"] = 0.01
    elif mutation == "missing":
        del record["api_consumption_usd"]
    if mutation == "partial":
        path.write_bytes(b"{")
    elif mutation == "interrupted":
        path.unlink()
    else:
        save(path, record)
    monkeypatch.setattr(tts, "load_key", lambda *args: pytest.fail("Malformed budget evidence must fail before credential access"))
    monkeypatch.setattr(tts, "post_once", lambda *args: pytest.fail("Malformed budget evidence cannot authorize another POST"))
    assert tts.main(["generate", "--run", str(run), "--approval", str(prepared[1]), "--call", "pilot-02",
                     "--env-file", str(env_file)]) == 1
    assert not (run / "attempts/pilot-02").exists()


def test_header_timeout_accounting_and_budget_stop_through_fresh_cli_processes(prepared, tmp_path):
    run, approval, env_file = prepared
    observations = tmp_path / "controlled-http-methods.txt"
    code = """
import socket, sys
from pathlib import Path
from datetime import datetime, timezone
from tools import prepare_tts as t
def denied(*args, **kwargs):
    raise RuntimeError('network disabled')
socket.socket.connect = denied
socket.create_connection = denied
t.datetime = type('Clock', (), {'now': staticmethod(lambda tz=None: datetime(2026, 10, 27, tzinfo=timezone.utc))})
mode = sys.argv.pop(1)
class Response:
    status = 200
    def __init__(self, audio):
        self.audio = audio
        self.headers = HEADERS if audio else {'Content-Type': 'application/json'}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self):
        if self.audio:
            raise TimeoutError('synthetic failure after actual headers')
        return b'{"data":{"total_cost":1.01}}'
class Opener:
    def open(self, request, timeout):
        with Path(OBSERVATIONS).open('a', encoding='utf-8') as output:
            output.write(request.method + '\\n')
        if mode == 'before-headers':
            raise TimeoutError('synthetic failure before headers')
        return Response(request.method == 'POST')
t.urllib.request.build_opener = lambda *handlers: Opener()
raise SystemExit(t.main())
""".replace("HEADERS", repr(HEADERS)).replace("OBSERVATIONS", repr(str(observations)))
    base = [sys.executable, "-c", code]
    common = ["--run", str(run), "--env-file", str(env_file)]
    for mode, command, expected_code in (
        ("before-headers", ["generate"] + common + ["--approval", str(approval), "--call", "pilot-01"], 1),
        ("body-timeout", ["generate"] + common + ["--approval", str(approval), "--call", "pilot-02"], 1),
        ("account", ["reconcile"] + common + ["--call", "pilot-02"], 0),
        ("unused", ["generate"] + common + ["--approval", str(approval), "--call", "pilot-03"], 1),
        ("account", ["reconcile"] + common + ["--call", "pilot-02"], 1)):
        result = subprocess.run(base + [mode] + command, cwd=Path(tts.__file__).resolve().parents[1],
                                env={"PYTHONIOENCODING": "utf-8"}, text=True, encoding="utf-8", capture_output=True, timeout=20)
        assert result.returncode == expected_code, result.stderr
    unidentified = run / "attempts/pilot-01"
    assert read(unidentified / "result.json")["generation_id"] is None
    assert not (unidentified / "response-metadata.json").exists()
    interrupted = run / "attempts/pilot-02"
    metadata = read(interrupted / "response-metadata.json")
    assert metadata["http_status"] == 200 and metadata["headers"] == HEADERS and metadata["body_complete"] is False
    assert read(interrupted / "result.json")["generation_id"] == HEADERS["X-Generation-Id"]
    assert read(interrupted / "reservation.json")["client_post_allowance_consumed"] is True
    assert (interrupted / "audio.pcm").read_bytes() == b""
    assert not (interrupted / "audio.wav").exists()
    assert read(interrupted / "reconciliation/result.json")["api_consumption_usd"] == 1.01
    assert observations.read_text().splitlines() == ["POST", "POST", "GET"]
    assert not (run / "attempts/pilot-03").exists()


@pytest.mark.parametrize("cost", ["NaN", "Infinity", -0.01, True, "not-money"])
def test_invalid_reported_cost_is_retained_unknown_and_blocks_more_spending(prepared, monkeypatch, cost):
    run, env_file = generate_for_accounting(prepared, monkeypatch)
    body = tts.json_bytes({"data": {"total_cost": cost}})
    monkeypatch.setattr(tts, "get_generation_once", lambda *args:
                        (200, {"Content-Type": "application/json"}, body, True))
    result = tts.reconcile(run, "pilot-01", env_file)
    assert result["status"] == "accounting_unknown" and result["api_consumption_usd"] is None
    output = run / "attempts/pilot-01/reconciliation"
    assert (output / "response.safe.json").read_bytes() == body
    assert read(output / "result.json")["metadata"]["total_cost"] == cost
    monkeypatch.setattr(tts, "load_key", lambda *args: pytest.fail("Invalid known budget evidence must precede credential access"))
    monkeypatch.setattr(tts, "post_once", lambda *args: pytest.fail("Invalid known budget evidence cannot authorize another POST"))
    with pytest.raises(ValueError, match="accounting cost"):
        tts.generate(run, prepared[1], "pilot-02", env_file)
    assert not (run / "attempts/pilot-02").exists()


def test_zero_cost_reconciliation_never_refills_six_post_slots(prepared, monkeypatch):
    run, approval, env_file = prepared
    enable_synthetic_key(monkeypatch)
    posted = []

    def post(*args):
        posted.append(args)
        return 200, {**HEADERS, "X-Generation-Id": f"gen-zero-{len(posted)}"}, PCM, True
    monkeypatch.setattr(tts, "post_once", post)
    monkeypatch.setattr(tts, "get_generation_once", lambda generation_id, key:
                        (200, {"Content-Type": "application/json"}, tts.json_bytes({"data": {"id": generation_id, "total_cost": 0}}), True))
    for i in range(1, 7):
        call_id = f"pilot-{i:02}"
        assert tts.generate(run, approval, call_id, env_file)["reserved_client_posts"] == i
        assert tts.reconcile(run, call_id, env_file)["api_consumption_usd"] == 0
    with pytest.raises(ValueError, match="exhausted"):
        tts.generate(run, approval, "pilot-07", env_file)
    assert len(posted) == 6


@pytest.fixture
def main_inputs(inputs):
    bundle = copy.deepcopy(inputs["bundle"])
    bundle["episodes"] = copy.deepcopy(inputs["all_episodes"][4:])
    path = inputs["scripts"].parent / "main-scripts.json"
    save(path, bundle)
    return {**inputs, "scripts": path, "bundle": bundle}


@pytest.fixture
def main_prepared(main_inputs, prepared, tmp_path):
    run = tmp_path / "main-run"
    result = prepare_inputs(main_inputs, run, "main")
    plan = read(run / "plan.json")
    # This is isolated synthetic review data, never a real adoption receipt.
    receipt = {"schema_version": 1, "scope": tts.METHOD_SCOPE,
               "parent_manifest_sha256": plan["parent_manifest_sha256"], "model": tts.MODEL,
               "voices": {"A": "Puck", "B": "Kore"}, "instructions_sha256": plan["instructions_sha256"],
               "development_parent_ids": plan["pilot_development_parent_ids"],
               "pilot_plan_sha256": tts.sha256((prepared[0] / "plan.json").read_bytes()),
               "actual_ja_ko_quality_review_approved": True, "actual_role_boundary_verification_approved": True,
               "method_adopted": True, "reviewer": "Synthetic reviewer", "reviewed_at": "2026-10-27",
               "evidence": "Synthetic test attestation only, not real listening or boundary verification"}
    receipt_path = tmp_path / "synthetic-pilot-method.json"
    save(receipt_path, receipt)
    approval = read(prepared[1])
    approval.update({"plan_sha256": result["plan_sha256"], "run_directory": str(run.resolve()), "scope": tts.MAIN_SCOPE,
                     "max_client_posts": 9, "api_cap_usd": "1.50",
                     "pilot_method_receipt_sha256": tts.sha256(receipt_path.read_bytes())})
    approval_path = tmp_path / "main-approval.json"
    save(approval_path, approval)
    return run, approval_path, prepared[2], receipt_path


def test_main_offline_preparation_selects_exact_nine_without_method_adoption(main_inputs, tmp_path):
    run = tmp_path / "main-offline"
    result = prepare_inputs(main_inputs, run, "main")
    assert result["planned_client_posts"] == 9
    plan = read(run / "plan.json")
    assert [call["id"] for call in plan["calls"]] == [f"main-{i:02}" for i in range(1, 10)]
    assert len({call["episode_id"] for call in plan["calls"]}) == 9 and all(call["take"] == 1 for call in plan["calls"])
    assert [entry["parent_id"] for entry in plan["requests"]] == [e["parent_id"] for e in main_inputs["bundle"]["episodes"]]
    assert plan["api_cap_usd"] == "1.50" and plan["nine_client_posts_estimate_usd"] == "1.363968"
    assert not (run / "attempts").exists() and not (run / "pilot-method.json").exists()
    with pytest.raises(ValueError, match="split"):
        prepare_inputs(main_inputs, tmp_path / "wrong-default-split")


@pytest.mark.parametrize("mutation", ["missing", "mixed", "duplicate", "wrong_split", "foreign"])
def test_main_preparation_rejects_incomplete_mixed_or_foreign_sources(main_inputs, tmp_path, mutation):
    bundle = main_inputs["bundle"]
    if mutation == "missing":
        bundle["episodes"].pop()
    elif mutation == "mixed":
        bundle["episodes"].append(copy.deepcopy(main_inputs["all_episodes"][0]))
    elif mutation == "duplicate":
        bundle["episodes"].append(copy.deepcopy(bundle["episodes"][0]))
    elif mutation == "wrong_split":
        bundle["episodes"][0]["project_split"] = "development"
    else:
        bundle["episodes"][0]["parent_id"] = "foreign-parent"
    save(main_inputs["scripts"], bundle)
    with pytest.raises(ValueError):
        prepare_inputs(main_inputs, tmp_path / "blocked-main", "main")
    assert not (tmp_path / "blocked-main").exists()


@pytest.mark.parametrize("target_main", [True, False])
def test_phase_approvals_cannot_cross_even_if_plan_and_location_are_rebound(main_prepared, prepared, monkeypatch, tmp_path, target_main):
    target = main_prepared if target_main else prepared
    source = prepared if target_main else main_prepared
    approval = read(source[1])
    approval.update({"plan_sha256": tts.sha256((target[0] / "plan.json").read_bytes()), "run_directory": str(target[0].resolve())})
    path = tmp_path / "foreign-phase-approval.json"
    save(path, approval)
    call = "main-01" if target_main else "pilot-01"
    with pytest.raises(ValueError, match="scope mismatch"):
        tts.generate(target[0], path, call, target[2], main_prepared[3] if target_main else None)
    assert not (target[0] / "attempts").exists()


@pytest.mark.parametrize("mutation", ["missing", "hash", "scope", "manifest", "model", "voices", "instructions",
                                       "coverage", "quality", "boundaries", "adopted", "reviewer", "pilot_identity"])
def test_main_method_gate_precedes_credentials_reservation_and_http(main_prepared, mutation):
    run, approval_path, env_file, receipt_path = main_prepared
    receipt, approval = read(receipt_path), read(approval_path)
    selected = receipt_path
    if mutation == "missing":
        selected = None
    elif mutation == "hash":
        with receipt_path.open("ab") as output:
            output.write(b" ")
    else:
        field = {"scope": "scope", "manifest": "parent_manifest_sha256", "model": "model", "voices": "voices",
                 "instructions": "instructions_sha256", "coverage": "development_parent_ids", "quality": "actual_ja_ko_quality_review_approved",
                 "boundaries": "actual_role_boundary_verification_approved", "adopted": "method_adopted", "reviewer": "reviewer",
                 "pilot_identity": "pilot_plan_sha256"}[mutation]
        if mutation in ("quality", "boundaries", "adopted"):
            receipt[field] = False
        elif mutation == "coverage":
            receipt[field].pop()
        elif mutation == "voices":
            receipt[field] = {"A": "Kore", "B": "Puck"}
        else:
            receipt[field] = "" if mutation == "reviewer" else "foreign"
        save(receipt_path, receipt)
        approval["pilot_method_receipt_sha256"] = tts.sha256(receipt_path.read_bytes())
        save(approval_path, approval)
    with pytest.raises(ValueError):
        tts.generate(run, approval_path, "main-01", env_file, selected)
    assert not (run / "attempts").exists()


@pytest.mark.parametrize("mutation", ["count", "cap", "prefix", "duplicate", "retake"])
def test_main_fixed_batch_cannot_become_arbitrary_configuration(main_prepared, mutation):
    run, approval_path, env_file, receipt_path = main_prepared
    plan = read(run / "plan.json")
    if mutation == "count":
        plan["max_client_posts"] = 10
    elif mutation == "cap":
        plan["api_cap_usd"] = "2.00"
    elif mutation == "prefix":
        plan["calls"][0]["id"] = "pilot-01"
    elif mutation == "duplicate":
        plan["calls"][1]["episode_id"] = plan["calls"][0]["episode_id"]
    else:
        plan["calls"][0]["take"] = 2
    save(run / "plan.json", plan)
    approval = read(approval_path)
    approval["plan_sha256"] = tts.sha256((run / "plan.json").read_bytes())
    save(approval_path, approval)
    with pytest.raises(ValueError):
        tts.generate(run, approval_path, "main-01", env_file, receipt_path)
    assert not (run / "attempts").exists()


def test_main_nine_slots_retain_success_failed_and_uncertain_results(main_prepared, monkeypatch):
    run, approval, env_file, receipt = main_prepared
    enable_synthetic_key(monkeypatch)
    posted = []

    def post(*args):
        posted.append(args)
        if len(posted) in (2, 8):
            raise TimeoutError("Synthetic uncertain main result")
        if len(posted) == 4:
            return 500, {"Content-Type": "application/json"}, b'{"error":"synthetic"}', True
        return 200, {**HEADERS, "X-Generation-Id": f"gen-main-{len(posted)}"}, PCM, True
    monkeypatch.setattr(tts, "post_once", post)
    for i in range(1, 10):
        call = f"main-{i:02}"
        result = tts.generate(run, approval, call, env_file, receipt)
        assert result["reserved_client_posts"] == i and result["client_post_allowance_consumed"] is True
        attempt = run / "attempts" / call
        assert (attempt / "pilot-method.json").read_bytes() == receipt.read_bytes()
        assert read(attempt / "reservation.json")["category"] == "production"
        if i not in (2, 4, 8):
            assert tts.decode_wave((attempt / "audio.wav").read_bytes()) == PCM
            assert (attempt / "audio.pcm").read_bytes() == PCM
            assert read(attempt / "result.json")["adopted"] is False
        else:
            assert not (attempt / "audio.wav").exists()
    with pytest.raises(ValueError, match="exhausted"):
        tts.generate(run, approval, "main-10", env_file, receipt)
    assert len(posted) == 9
    assert sum(tts.Decimal(read(p / "reservation.json")["reserved_usd"]) for p in (run / "attempts").iterdir()) == tts.Decimal("1.363968")


@pytest.mark.parametrize("cost", [1.51, 0.16])
def test_main_known_cap_or_reservation_contradiction_stops_next_call(main_prepared, monkeypatch, cost):
    run, approval, env_file, receipt = main_prepared
    enable_synthetic_key(monkeypatch)
    monkeypatch.setattr(tts, "post_once", lambda *args: (200, HEADERS, PCM, True))
    tts.generate(run, approval, "main-01", env_file, receipt)
    monkeypatch.setattr(tts, "get_generation_once", lambda *args:
                        (200, {"Content-Type": "application/json"}, tts.json_bytes({"data": {"total_cost": cost}}), True))
    assert tts.reconcile(run, "main-01", env_file)["api_consumption_usd"] == cost
    monkeypatch.setattr(tts, "load_key", lambda *args: pytest.fail("Known main budget contradiction must precede secret access"))
    with pytest.raises(ValueError, match="cap|reservation"):
        tts.generate(run, approval, "main-02", env_file, receipt)
    assert not (run / "attempts/main-02").exists()


def test_actual_main_cli_receipt_gate_wavs_accounting_and_terminal_stop(main_prepared, tmp_path):
    run, approval, env_file, receipt = main_prepared
    guard = tmp_path / "main-cli-guard"
    guard.mkdir()
    observations = tmp_path / "main-cli-controlled-http.txt"
    code = """
import datetime, socket, sys, urllib.request
from pathlib import Path
class Clock(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime.datetime(2026, 10, 27, tzinfo=datetime.timezone.utc)
datetime.datetime = Clock
def denied(*args, **kwargs):
    raise RuntimeError('network disabled for synthetic main CLI')
socket.socket.connect = denied
socket.create_connection = denied
class Response:
    status = 200
    def __init__(self, audio):
        self.audio = audio
        call = sys.argv[sys.argv.index('--call') + 1]
        self.headers = {'Content-Type': 'audio/pcm;rate=24000;channels=1', 'X-Generation-Id': 'gen-synthetic-' + call} if audio else {'Content-Type': 'application/json'}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self):
        return AUDIO_BYTES if self.audio else b'{"data":{"total_cost":0.01}}'
class Opener:
    def open(self, request, timeout):
        with Path(OBSERVATIONS).open('a', encoding='utf-8') as output:
            output.write(request.method + '\\n')
        return Response(request.method == 'POST')
urllib.request.build_opener = lambda *handlers: Opener()
""".replace("AUDIO_BYTES", repr(PCM)).replace("OBSERVATIONS", repr(str(observations)))
    (guard / "sitecustomize.py").write_text(code, encoding="utf-8")
    env = {"PYTHONPATH": str(guard), "PYTHONIOENCODING": "utf-8"}
    script = str(Path(tts.__file__).resolve())
    base = [sys.executable, script, "generate", "--run", str(run), "--approval", str(approval), "--env-file", str(env_file)]

    def invoke(args):
        return subprocess.run(args, env=env, text=True, encoding="utf-8", capture_output=True, timeout=20)
    blocked = invoke(base + ["--call", "main-01"])
    assert blocked.returncode == 1 and not observations.exists() and not (run / "attempts").exists()
    for i in range(1, 10):
        call = f"main-{i:02}"
        result = invoke(base + ["--call", call, "--pilot-method", str(receipt)])
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["reserved_client_posts"] == i
        attempt = run / "attempts" / call
        assert tts.decode_wave((attempt / "audio.wav").read_bytes()) == PCM
        assert read(attempt / "result.json")["pcm16le_sha256"] == tts.sha256(PCM)
    for call in ("main-10", "main-01"):
        assert invoke(base + ["--call", call, "--pilot-method", str(receipt)]).returncode == 1
    accounting = invoke([sys.executable, script, "reconcile", "--run", str(run), "--env-file", str(env_file), "--call", "main-01"])
    assert accounting.returncode == 0 and json.loads(accounting.stdout)["api_consumption_usd"] == 0.01
    assert observations.read_text().splitlines() == ["POST"] * 9 + ["GET"]
    assert not (run / "attempts/main-10").exists()
    assert read(run / "attempts/main-01/reconciliation/result.json")["client_post_allowance_changed"] is False
