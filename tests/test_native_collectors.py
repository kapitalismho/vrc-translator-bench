"""Synthetic source-derived peers only: none of these tests runs a product app."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from websockets.sync.server import serve

from bench.adapter import OperationalError
from bench.native import NativeSink
from bench.native_formats import VRCS_EVENTS, log_record, puripuly, vrcs, vrct
from bench.osc import encode
from bench.storage import Journal, digest


def wait_for(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.01)
    raise AssertionError("Synthetic peer observation was not reached")


def rows(root):
    paths = list(Path(root).glob("stream-*"))
    result = []
    for path in paths:
        result.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    return result


def outputs(root):
    return [row for row in rows(root) if row.get("record") == "native_output_event"]


def profile(family, **fields):
    return {"id": "P", "app_version": "synthetic-source-format", "collector": {"family": family, **fields}}


def attach(sink, root, roles=None):
    journal = Journal(root / "attempt.tmp")
    sink.attach("P", {"episode_id": "episode", "pass_id": "reverse-self", "attempt": "a1",
                      "wave": "W1", "capture_phase": "input",
                      "roles": roles or {"self": {"role": "B", "source_language": "zh", "target_language": "en"},
                                         "peer": {"role": "A", "source_language": "en", "target_language": "zh"}}}, journal)
    return journal


def udp_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Peer:
    def __init__(self, handler, process_request=None):
        self.server = serve(handler, "127.0.0.1", 0, process_request=process_request)
        self.port = self.server.socket.getsockname()[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.thread.join(timeout=5)


def envelope(kind, payload, source="speaker"):
    return {"api_version": "1.0", "event_id": "synthetic-event-" + kind, "type": kind,
            "timestamp": "2026-10-26T00:00:01.123456Z",
            "message_id": "connection" if kind.startswith("system.") else "native-turn",
            "source": source, "payload": payload}


def test_source_formats_keep_unknown_fields_unknown():
    raw, pp = puripuly({"output_version": 1, "topic": "translation", "channel": "peer", "text": "你好",
                       "utterance_id": "native-uuid", "sequence": 43, "instance_id": "host", "is_final": True})
    assert "is_final" not in raw
    assert "update_kind" not in pp and "revision" not in pp and "producer_time_raw" not in pp
    _, vt = vrct({"type": "RECEIVED", "message": "hi", "translation": ["你好"], "transliteration": [[]]})
    assert vt["translated_text"] == "你好" and "native_id" not in vt
    _, multi = vrct({"type": "SENT", "translation": ["one", "two"]})
    assert multi["translated_text"] is None and multi["translated_texts"] == ["one", "two"]
    raw, vs = vrcs(envelope("translation.completed", {"subtitle_id": 7, "translation": {
        "text": "你好", "source_language": None, "target_language": "zh", "created_at": "different-time",
        "source_group": {"subtitle_ids": [7, 8], "text": "hello again"}}}))
    assert vs["producer_time_raw"] != raw["payload"]["translation"]["created_at"]
    assert vs["source_group"]["subtitle_ids"] == [7, 8]
    assert vs["producer_languages"]["source_language"] is None and "revision" not in vs


def test_constructor_does_not_connect_and_close_is_durable(tmp_path):
    p = profile("vrct", url="ws://127.0.0.1:1", token_env="NOT_SET")
    sink = NativeSink(tmp_path, "run", "s", [p])
    assert sink.continuity("P")["continuous"] is False
    sink.identity("P", {"pid": 123, "token": "private"})
    sink.record({"record": "clock", "authorization": "private"})
    path, checksum = sink.close()
    assert checksum == digest(tmp_path / path) and path == "stream-s.jsonl"
    assert "private" not in (tmp_path / path).read_text(encoding="utf-8")
    assert sink.close() == (path, checksum)


def test_vrct_real_loopback_auth_and_route_attribution(tmp_path, monkeypatch):
    token = "synthetic-private-token"
    monkeypatch.setenv("NATIVE_TEST_TOKEN", token)
    release = threading.Event()
    no_client_commands = []
    def auth(connection, request):
        if parse_qs(urlsplit(request.path).query).get("token") != [token]:
            return connection.respond(403, "Forbidden")
    def handler(ws):
        release.wait(5)
        for kind in ("SENT", "RECEIVED"):
            ws.send(json.dumps({"type": kind, "message": "hello", "translation": ["你好"],
                                "src_languages": {"1": {"language": "English", "enable": True}},
                                "dst_languages": {"1": {"language": "Chinese", "enable": True}},
                                "transliteration": [[]], "api_key": token}))
        try:
            no_client_commands.append(ws.recv(timeout=0.15))
        except TimeoutError:
            no_client_commands.append(None)
        release.clear()
        release.wait(5)
    peer = Peer(handler, auth)
    sink = NativeSink(tmp_path, "run", "s", [profile("vrct", url=f"ws://127.0.0.1:{peer.port}/",
                    token_env="NATIVE_TEST_TOKEN", ocr_disabled=True, ocr_evidence={"frozen_state": "synthetic"})])
    journal = attach(sink, tmp_path)
    try:
        sink.start("P")
        assert sink.continuity("P")["continuous"] is True
        release.set()
        wait_for(lambda: len(outputs(tmp_path)) == 2)
        wait_for(lambda: no_client_commands)
        events = outputs(tmp_path)
        assert [(e["input_channel"], e["role"]) for e in events] == [("self", "B"), ("peer", "A")]
        assert all(e["producer_time_raw"] is None and e["event_time_interval"] is None and e["update_kind"] is None for e in events)
        assert all(e["native_id"] is None and e["revision"] is None for e in events)
        assert no_client_commands == [None]
        assert token not in (tmp_path / "stream-s.tmp").read_text(encoding="utf-8")
        sink.stop("P")
    finally:
        release.set()
        sink.close()
        journal.finalize()
        peer.close()


def test_vrct_rejects_bad_auth_without_leaking_query(tmp_path, monkeypatch):
    monkeypatch.setenv("NATIVE_TEST_TOKEN", "synthetic-secret")
    peer = Peer(lambda ws: None, lambda c, r: c.respond(403, "Forbidden"))
    sink = NativeSink(tmp_path, "run", "s", [profile("vrct", url=f"ws://127.0.0.1:{peer.port}/", token_env="NATIVE_TEST_TOKEN")])
    try:
        with pytest.raises(OperationalError, match="start failed"):
            sink.start("P")
        assert sink.continuity("P")["continuous"] is False
    finally:
        path, _ = sink.close()
        peer.close()
    assert "synthetic-secret" not in (tmp_path / path).read_text(encoding="utf-8")


def test_vrct_ocr_exclusion_requires_independent_state(tmp_path):
    sink = NativeSink(tmp_path, "run", "s", [profile("vrct")])
    data = json.dumps({"type": "RECEIVED", "message": "hello", "translation": ["你好"]})
    with sink.lock:
        sink.json("P", "vrct", data, time.perf_counter_ns())
    event = outputs(tmp_path)[0]
    assert event["input_channel"] is None and event["role"] is None
    assert event["boundary"] == "ocr_exclusion_unverified"
    with pytest.raises(OperationalError, match="gap"):
        sink.check("P")
    sink.close()


def test_vrcs_actual_bearer_subscribe_ack_partial_gap_disconnect(tmp_path, monkeypatch):
    token = "synthetic-bearer-token"
    monkeypatch.setenv("NATIVE_TEST_TOKEN", token)
    ack = threading.Event()
    emit = threading.Event()
    start_returned = threading.Event()
    start_errors = []
    def start():
        try:
            sink.start("P")
        except Exception as error:
            start_errors.append(error)
        finally:
            start_returned.set()
    starter = threading.Thread(target=start, daemon=True)
    requests = []
    def auth(connection, request):
        assert request.path == "/v1/events"
        if request.headers.get("Authorization") != "Bearer " + token:
            return connection.respond(401, "Unauthorized")
    def handler(ws):
        ws.send(json.dumps(envelope("system.connected", {"connection_id": "connection"}, "system")))
        requests.append(json.loads(ws.recv(timeout=5)))
        ack.wait(5)
        ws.send(json.dumps(envelope("system.subscribed", {"events": list(VRCS_EVENTS)}, "system")))
        emit.wait(5)
        ws.send(json.dumps(envelope("translation.partial", {"subtitle_id": 7, "text": "你", "target_language": "zh"})))
        ws.send(json.dumps(envelope("translation.completed", {"subtitle_id": 7, "translation": {
            "text": "你好", "source_language": None, "target_language": "zh", "source_group": {"subtitle_ids": [7, 8], "text": "hello"}}})))
        ws.send(json.dumps(envelope("system.lagged", {"dropped": 12}, "system")))
    peer = Peer(handler, auth)
    sink = NativeSink(tmp_path, "run", "s", [profile("vrcs", url=f"ws://127.0.0.1:{peer.port}/v1/events", token_env="NATIVE_TEST_TOKEN")])
    journal = attach(sink, tmp_path)
    try:
        starter.start()
        wait_for(lambda: requests)
        assert sink.continuity("P")["continuous"] is False
        # The server has the subscribe request, but its ACK is still gated.
        # Startup must remain pending; no application/input may follow it yet.
        assert not start_returned.wait(0.05)
        assert requests == [{"type": "subscribe", "events": list(VRCS_EVENTS)}]
        ack.set()
        assert start_returned.wait(5) and not start_errors
        assert sink.continuity("P")["continuous"] is True
        emit.set()
        wait_for(lambda: len(outputs(tmp_path)) == 2)
        wait_for(lambda: sink.continuity("P")["connection"] == "disconnected")
        events = outputs(tmp_path)
        assert [e["update_kind"] for e in events] == ["translation.partial", "translation.completed"]
        assert all(e["revision"] is None and e["event_time_interval"] is None for e in events)
        assert events[1]["native_id"] == "native-turn" and events[1]["source_group"]["subtitle_ids"] == [7, 8]
        assert {g["loss_or_gap"] for g in sink.continuity("P")["gaps"]} >= {"producer_lagged", "collector_disconnected"}
    finally:
        ack.set(); emit.set()
        if starter.ident is not None:
            starter.join(timeout=5)
        sink.close()
        journal.finalize()
        peer.close()


def test_kikitan_fixed_udp_separate_messages_no_adjacent_grouping(tmp_path):
    p = profile("kikitan", host="127.0.0.1", port=7272)
    sink = NativeSink(tmp_path, "run", "s", [p])
    journal = attach(sink, tmp_path, {"self": {"role": "B", "source_language": "zh", "target_language": "en"}})
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sink.start("P")
        state = sink.continuity("P")
        assert state["continuous"] is None and state["listener_uninterrupted"] is True
        for address, args in [("/microphone/translated", ["hello"]), ("/microphone/final", [True]),
                              ("/microphone/recognized", ["你好"]), ("/desktop/translated", ["unexpected desktop"])]:
            sender.sendto(encode(address, args), ("127.0.0.1", 7272))
        wait_for(lambda: len(outputs(tmp_path)) == 4)
        events = outputs(tmp_path)
        assert events[0]["translated_text"] == "hello" and events[0]["source_text"] is None
        assert events[1]["translated_text"] is None and events[1]["native_final_signal"] is True
        assert events[1]["update_kind"] is None and events[1]["native_id"] is None
        assert events[2]["source_text"] == "你好" and events[2]["translated_text"] is None
        assert events[0]["input_channel"] == "self" and events[0]["role"] == "B"
        assert events[0]["raw_evidence"]["packet_base64"]
        assert events[3]["input_channel"] == "peer" and events[3]["role"] is None
        assert all(e["event_time_interval"] is None for e in events)
        sink.stop("P")
        sink.start("P")
        assert sink.continuity("P")["generation"] == 2 and sink.continuity("P")["gaps"] == []
    finally:
        sender.close()
        sink.close()
        journal.finalize()


def test_kikitan_rejects_configurable_port_and_shared_bind(tmp_path):
    sink = NativeSink(tmp_path, "run", "s", [profile("kikitan", port=7273)])
    with pytest.raises(OperationalError):
        sink.start("P")
    sink.close()
    log = tmp_path / "vrclt.log"
    log.write_bytes(b"")
    p = profile("vrclt", port=udp_port(), log_path=str(log))
    q = {**p, "id": "Q"}
    sink = NativeSink(tmp_path, "run", "s2", [p, q])
    try:
        sink.start("P")
        with pytest.raises(OperationalError, match="already owned"):
            sink.start("Q")
    finally:
        sink.close()


def test_vrclt_udp_display_is_not_final_log_or_translation_replacement(tmp_path):
    log = tmp_path / "vrclt.log"
    log.write_bytes(b"")
    port = udp_port()
    sink = NativeSink(tmp_path, "run", "s", [profile("vrclt", port=port, log_path=str(log))])
    journal = attach(sink, tmp_path)
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sink.start("P")
        for text in ("original (partial)", "original (replacement)"):
            sender.sendto(encode("/chatbox/input", [text, True, False]), ("127.0.0.1", port))
        with log.open("ab") as target:
            target.write(b"2026-10-26 00:00:01,123 [INFO] vrclt.pipeline: FINAL [en] original  ->  full translation\n")
        wait_for(lambda: len(outputs(tmp_path)) == 3)
        events = outputs(tmp_path)
        wire = [e for e in events if e["transport"] == "osc_udp"]
        crosscheck = [e for e in events if e["transport"] == "file_tail"][0]
        assert [e["display_text"] for e in wire] == ["original (partial)", "original (replacement)"]
        assert all(e["translated_text"] is None and e["update_kind"] is None for e in wire)
        assert crosscheck["translated_text"] == "full translation"
        assert crosscheck["evidence_purpose"] == "separate_final_crosscheck_not_osc_replacement"
        assert crosscheck["event_time_interval"] is None
    finally:
        sender.close()
        sink.close()
        journal.finalize()


def test_file_tail_partial_rotation_redaction_boundaries_and_stop_drain(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    first = logs / "vrcls-20261025.log"
    old = b"[2026-10-25 00:00:00.000 INF] [Desktop] history -> not replayed\n"
    first.write_bytes(old)
    sink = NativeSink(tmp_path, "run", "s", [profile("vrcls", log_dir=str(logs))])
    journal = attach(sink, tmp_path)
    try:
        sink.start("P")
        with first.open("ab") as target:
            target.write(b"[2026-10-26 00:00:01.123 INF] [Desktop] hello -> ")
        time.sleep(0.08)
        assert outputs(tmp_path) == []
        completed_after = time.perf_counter_ns()
        with first.open("ab") as target:
            target.write("你好\n".encode())
            target.write(b"[2026-10-26 00:00:01.124 INF] CONFIG_SNAPSHOT_V1 SUPER_PRIVATE_TOKEN\n")
            target.write(b"[2026-10-26 00:00:01.125 INF] [Mic] a -> b -> c\n")
            target.write(b"continuation including CONFIG_SNAPSHOT_V1 SUPER_PRIVATE_TOKEN\n")
        wait_for(lambda: len(outputs(tmp_path)) >= 3)
        events = outputs(tmp_path)
        assert events[0]["translated_text"] == "你好" and events[0]["role"] == "A"
        assert events[0]["collector_received_monotonic"] >= completed_after
        assert events[0]["producer_time_raw"] == "2026-10-26 00:00:01.123"
        assert events[0]["event_time_interval"] is None
        assert events[1]["boundary"] == "ambiguous_log_text_boundary" and events[1]["translated_text"] is None
        assert events[2]["boundary"] == "multiline_log_record"
        second = logs / "vrcls-20261026.log"
        second.write_bytes(b"[2026-10-26 00:00:02.000 INF] [Mic] new -> rotated\n")
        wait_for(lambda: any(e.get("translated_text") == "rotated" for e in outputs(tmp_path)))
        assert any(g["loss_or_gap"] == "log_rotation_unobserved_interval" for g in sink.continuity("P")["gaps"])
        with second.open("ab") as target:
            target.write(b"[2026-10-26 00:00:03.000 INF] [Mic] final -> drained\npartial-secret")
        sink.stop("P")
        assert any(e.get("translated_text") == "drained" for e in outputs(tmp_path))
        assert any(g["loss_or_gap"] == "file_partial_line" for g in sink.continuity("P")["gaps"])
        serialized = (tmp_path / "stream-s.tmp").read_text(encoding="utf-8")
        assert "SUPER_PRIVATE_TOKEN" not in serialized and "partial-secret" not in serialized
        assert not any(e.get("translated_text") == "not replayed" for e in outputs(tmp_path))
        sink.start("P")
        assert sink.continuity("P")["continuous"] is True and sink.continuity("P")["gaps"] == []
    finally:
        sink.close()
        journal.finalize()


def test_file_tail_copytruncate_does_not_publish_old_offset_suffix(tmp_path):
    log = tmp_path / "vrcls.log"
    log.write_bytes(b"")
    sink = NativeSink(tmp_path, "run", "s", [profile("vrcls", log_path=str(log))])
    try:
        sink.start("P")
        log.write_bytes(b"[2026-10-26 00:00:01.123 INF] [Mic] a -> first\n")
        wait_for(lambda: len(outputs(tmp_path)) == 1)
        log.write_bytes(b"[2026-10-26 00:00:01.124 INF] [Mic] longer input -> a longer replacement after truncation\n")
        wait_for(lambda: len(outputs(tmp_path)) == 2)
        assert outputs(tmp_path)[1]["translated_text"] == "a longer replacement after truncation"
        assert sink.continuity("P")["continuous"] is False
    finally:
        sink.close()


def test_puripuly_real_synthetic_subprocess_no_host_or_control_commands(tmp_path, monkeypatch):
    script = tmp_path / "synthetic_cli.py"
    script.write_text('''import json,sys,time
channel=sys.argv[sys.argv.index('--channel')+1]
for sequence in (1,43):
 print(json.dumps({'output_version':1,'topic':'translation','channel':channel,'source':channel,'text':'synthetic translation','utterance_id':'native-uuid','sequence':sequence,'instance_id':'synthetic-host'}),flush=True)
time.sleep(30)
''', encoding="utf-8")
    real_popen = subprocess.Popen
    commands = []
    def launch(args, **kwargs):
        commands.append(args)
        assert args[0] == "synthetic-puripuly-cli"
        assert kwargs["env"]["PYTHONUNBUFFERED"] == "1"
        return real_popen([sys.executable, str(script), *args[1:]], **kwargs)
    monkeypatch.setattr("bench.native_process.subprocess.Popen", launch)
    sink = NativeSink(tmp_path, "run", "s", [profile("puripuly", executable="synthetic-puripuly-cli", channels=["self", "peer"])])
    journal = attach(sink, tmp_path)
    try:
        sink.start("P")
        wait_for(lambda: len(outputs(tmp_path)) == 4)
        assert sink.continuity("P")["continuous"] is True
        assert all(command[1:3] == ["events", "follow"] and "--include-translations" in command for command in commands)
        assert all(e["producer_time_raw"] is None and e["update_kind"] is None for e in outputs(tmp_path))
        assert sink.continuity("P")["gaps"] == []  # filtered sequence jumps are not loss
        with sink.lock:
            sink.json("P", "puripuly", json.dumps({"topic": "gap", "reason": "history_evicted", "sequence": 44}), time.perf_counter_ns())
        assert sink.continuity("P")["continuous"] is False
        sink.stop("P")
        sink.start("P")
        wait_for(lambda: len(outputs(tmp_path)) == 8)
        assert sink.continuity("P")["generation"] == 2 and sink.continuity("P")["continuous"] is True
    finally:
        sink.close()
        journal.finalize()


def test_detach_clears_attempt_and_clock_is_receipt_not_producer(tmp_path):
    sink = NativeSink(tmp_path, "run", "s", [profile("vrcs")])
    journal = attach(sink, tmp_path)
    sink.identity("P", {"pid": 123, "verified": False})
    sink.source("P", {"source_id": "manifest-source"})
    value = envelope("translation.completed", {"translation": {"text": "hello", "target_language": "en"}})
    received = time.perf_counter_ns()
    with sink.lock:
        sink.json("P", "vrcs", json.dumps(value), received)
    sink.detach("P")
    with sink.lock:
        sink.json("P", "vrcs", json.dumps(value), received + 1)
    events = outputs(tmp_path)
    assert events[0]["attempt"] == "a1" and events[1]["attempt"] is None
    assert events[0]["collector_received_monotonic"] == received and events[0]["event_time_interval"] is None
    assert events[0]["instance"] == {"asserted": {"pid": 123, "verified": False}, "producer": None}
    assert sink.attempt_last_output["P"] == received and sink.last_output["P"] == received + 1
    sink.close()
    attempt_path, _ = journal.finalize()
    assert len((tmp_path / attempt_path).read_text(encoding="utf-8").splitlines()) == 1


@pytest.mark.parametrize("family,text", [
    ("vrclt", "2026-10-26 00:00:01,123 [INFO] vrclt.pipeline: FINAL [auto] a -> b  ->  c\n"),
    ("vrcls", "[2026-10-26 00:00:01.123 INF] [Desktop] original only\n"),
])
def test_ambiguous_log_boundaries_not_guessed(family, text):
    fields = log_record(family, text)
    assert fields["boundary"] == "ambiguous_log_text_boundary"
    assert "translated_text" not in fields and "source_text" not in fields


def test_vrcs_wrong_connection_ack_never_claims_ready(tmp_path, monkeypatch):
    monkeypatch.setenv("NATIVE_TEST_TOKEN", "synthetic-token")
    def handler(ws):
        ws.send(json.dumps(envelope("system.connected", {"connection_id": "connection"}, "system")))
        ws.recv(timeout=5)
        ack = envelope("system.subscribed", {"events": list(VRCS_EVENTS)}, "system")
        ack["message_id"] = "wrong-connection"
        ws.send(json.dumps(ack))
    peer = Peer(handler)
    sink = NativeSink(tmp_path, "run", "s", [profile("vrcs", url=f"ws://127.0.0.1:{peer.port}/v1/events", token_env="NATIVE_TEST_TOKEN")])
    try:
        with pytest.raises(OperationalError, match="start failed"):
            sink.start("P")
        assert sink.continuity("P")["continuous"] is False
        assert not any(e.get("kind") == "collector_ready" for e in rows(tmp_path))
    finally:
        sink.close()
        peer.close()


def test_osc_raw_evidence_redacts_known_auth_and_config_payloads(tmp_path):
    sink = NativeSink(tmp_path, "run", "s", [profile("kikitan", port=7272)])
    sink.secret("synthetic-token")
    with sink.lock:
        for text in ("synthetic-token", "CONFIG_SNAPSHOT_V1 secret compressed settings"):
            sink.udp("P", encode("/microphone/translated", [text]), ("127.0.0.1", 12345), time.perf_counter_ns())
    events = outputs(tmp_path)
    assert all("packet_base64" not in e["raw_evidence"] for e in events)
    path, _ = sink.close()
    serialized = (tmp_path / path).read_text(encoding="utf-8")
    assert "synthetic-token" not in serialized and "secret compressed settings" not in serialized


def test_vrcs_loopback_existing_unauthenticated_listener(tmp_path):
    release = threading.Event()
    observed_headers = []
    def handler(ws):
        observed_headers.append(ws.request.headers.get("Authorization"))
        ws.send(json.dumps(envelope("system.connected", {"connection_id": "connection"}, "system")))
        assert json.loads(ws.recv(timeout=5)) == {"type": "subscribe", "events": list(VRCS_EVENTS)}
        ws.send(json.dumps(envelope("system.subscribed", {"events": list(VRCS_EVENTS)}, "system")))
        release.wait(5)
    peer = Peer(handler)
    sink = NativeSink(tmp_path, "run", "s", [profile("vrcs", url=f"ws://127.0.0.1:{peer.port}/v1/events")])
    try:
        sink.start("P")
        wait_for(lambda: sink.continuity("P")["continuous"] is True)
        assert observed_headers == [None]
        sink.stop("P")
    finally:
        release.set()
        sink.close()
        peer.close()


def test_vrcs_omitted_token_does_not_bypass_server_authentication(tmp_path):
    peer = Peer(lambda ws: None, lambda connection, request: connection.respond(401, "Unauthorized"))
    sink = NativeSink(tmp_path, "run", "s", [profile("vrcs", url=f"ws://127.0.0.1:{peer.port}/v1/events")])
    try:
        with pytest.raises(OperationalError, match="start failed"):
            sink.start("P")
        assert sink.continuity("P")["continuous"] is False
    finally:
        sink.close()
        peer.close()


@pytest.mark.parametrize("family,fields", [
    ("vrct", {}),
    ("vrct", {"token_env": "MISSING_NATIVE_TOKEN"}),
    ("vrcs", {"token_env": "MISSING_NATIVE_TOKEN"}),
    ("vrcs", {"token_env": ""}),
    ("vrcs", {"token_env": None}),
])
def test_explicit_token_requirement_is_not_silently_dropped(tmp_path, monkeypatch, family, fields):
    monkeypatch.delenv("MISSING_NATIVE_TOKEN", raising=False)
    endpoint = "ws://127.0.0.1:1" + ("/v1/events" if family == "vrcs" else "/")
    sink = NativeSink(tmp_path, "run", "s", [profile(family, url=endpoint, **fields)])
    with pytest.raises(OperationalError, match="start failed: ValueError"):
        sink.start("P")
    sink.close()


@pytest.mark.parametrize("fields", [
    {"display_text": " \t\r\n"}, {"translated_text": " \t\r\n"},
    {"translated_texts": ["", " \t"]},
])
def test_whitespace_evidence_does_not_restart_quiet_or_attempt_output(tmp_path, fields):
    sink = NativeSink(tmp_path, "run", "s", [profile("vrct")])
    journal = attach(sink, tmp_path)
    received = time.perf_counter_ns()
    with sink.lock:
        sink._event("P", {"translated_text": "legitimate output"}, {}, received, "synthetic")
    sink.detach("P")
    sink.attach("P", {"attempt": "fresh", "capture_phase": "quiet_precondition"}, journal)
    with sink.lock:
        sink._event("P", fields, {}, received + 1, "synthetic")
    assert sink.last_output["P"] == received and sink.attempt_last_output["P"] is None
    assert all(outputs(tmp_path)[-1][key] == value for key, value in fields.items())
    assert "output_classification" not in outputs(tmp_path)[-1]
    sink.close()
    journal.finalize()


def test_vrcs_start_returns_ready_without_losing_ack_adjacent_or_subsequent_text(tmp_path):
    input_allowed = threading.Event()
    release = threading.Event()
    def handler(ws):
        ws.send(json.dumps(envelope("system.connected", {"connection_id": "connection"}, "system")))
        ws.recv(timeout=5)
        ws.send(json.dumps(envelope("system.subscribed", {"events": list(VRCS_EVENTS)}, "system")))
        first = envelope("translation.completed", {"translation": {"text": "ACK-adjacent text", "target_language": "zh"}})
        first["event_id"] = "synthetic-first"
        ws.send(json.dumps(first))
        input_allowed.wait(5)
        second = envelope("translation.completed", {"translation": {"text": "subsequent text", "target_language": "zh"}})
        second["event_id"] = "synthetic-second"
        ws.send(json.dumps(second))
        release.wait(5)
    peer = Peer(handler)
    sink = NativeSink(tmp_path, "run", "s", [profile("vrcs", url=f"ws://127.0.0.1:{peer.port}/v1/events")])
    try:
        sink.start("P")
        # This is synchronous evidence at the public startup return boundary.
        assert sink.continuity("P")["continuous"] is True
        input_allowed.set()
        wait_for(lambda: len(outputs(tmp_path)) == 2)
        assert [event["translated_text"] for event in outputs(tmp_path)] == ["ACK-adjacent text", "subsequent text"]
        assert [event["native_event_id"] for event in outputs(tmp_path)] == ["synthetic-first", "synthetic-second"]
    finally:
        input_allowed.set(); release.set()
        sink.close()
        peer.close()


def test_vrcs_rejected_subscription_fails_start_instead_of_permitting_input(tmp_path):
    def handler(ws):
        ws.send(json.dumps(envelope("system.connected", {"connection_id": "connection"}, "system")))
        ws.recv(timeout=5)
        ws.send(json.dumps(envelope("system.error", {"code": "unknown_event_pattern"}, "system")))
    peer = Peer(handler)
    sink = NativeSink(tmp_path, "run", "s", [profile("vrcs", url=f"ws://127.0.0.1:{peer.port}/v1/events")])
    try:
        with pytest.raises(OperationalError, match="start failed"):
            sink.start("P")
        assert sink.continuity("P")["continuous"] is False
        assert not sink.transports
        assert not any(event.get("kind") == "collector_ready" for event in rows(tmp_path))
    finally:
        sink.close()
        peer.close()


def test_vrcs_missing_ack_fails_start_at_bounded_subscription_deadline(tmp_path):
    from websockets.exceptions import ConnectionClosed
    requested = threading.Event()
    disconnected = threading.Event()
    returned = threading.Event()
    errors = []
    def handler(ws):
        ws.send(json.dumps(envelope("system.connected", {"connection_id": "connection"}, "system")))
        ws.recv(timeout=5)
        requested.set()
        try:
            ws.recv(timeout=10)
        except ConnectionClosed:
            disconnected.set()
    peer = Peer(handler)
    sink = NativeSink(tmp_path, "run", "s", [profile("vrcs", url=f"ws://127.0.0.1:{peer.port}/v1/events")])
    def start():
        try:
            sink.start("P")
        except Exception as error:
            errors.append(error)
        finally:
            returned.set()
    starter = threading.Thread(target=start, daemon=True)
    started = time.monotonic()
    try:
        starter.start()
        assert requested.wait(5)
        assert returned.wait(7)
        assert time.monotonic() - started >= 4.9
        assert len(errors) == 1 and isinstance(errors[0], OperationalError)
        assert "TimeoutError" in str(errors[0])
        assert disconnected.wait(5)
        assert not sink.transports and sink.continuity("P")["continuous"] is False
        assert not any(event.get("kind") == "collector_ready" for event in rows(tmp_path))
    finally:
        starter.join(timeout=5)
        sink.close()
        peer.close()
