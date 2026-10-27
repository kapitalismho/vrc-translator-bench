"""Read-only native log ownership, including actual Windows producer rollover."""
from __future__ import annotations

import io
import logging
import logging.handlers
import os
import sys
import threading
import time

import pytest

from bench.adapter import OperationalError
from bench.native import NativeSink
from bench.native_file import open_log_readonly
from bench.native_transports import FileTail
from test_native_collectors import outputs, profile, udp_port, wait_for


def hold_tail_polling(monkeypatch):
    """Keep the real handle open while deterministically arranging rotation.

    Only polling is gated. The actual opener, Windows handle, producer rename,
    old-handle drain, new-file observation and journal all remain real.
    """
    release = threading.Event()
    receive = FileTail.receive
    def held_receive(self):
        if not release.wait(5):
            raise TimeoutError("Synthetic producer did not release file polling")
        receive(self)
    monkeypatch.setattr(FileTail, "receive", held_receive)
    return release


def test_log_opener_is_read_only_and_never_creates_missing_files(tmp_path):
    path = tmp_path / "producer.log"
    path.write_bytes(b"existing producer bytes")
    with open_log_readonly(path) as source:
        assert source.read() == b"existing producer bytes"
        assert source.readable() and not source.writable()
        with pytest.raises(io.UnsupportedOperation):
            source.write(b"must not write")
    assert path.read_bytes() == b"existing producer bytes"
    missing = tmp_path / "missing.log"
    with pytest.raises(OSError):
        open_log_readonly(missing)
    assert not missing.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows FILE_SHARE_DELETE regression")
def test_active_tail_allows_rename_and_drains_old_file_without_backdating(tmp_path, monkeypatch):
    release = hold_tail_polling(monkeypatch)
    path = tmp_path / "vrcls.log"
    backup = tmp_path / "vrcls.log.1"
    seed = b"[2026-10-26 00:00:00.000 INF] [Mic] history -> not replayed\n"
    before_rename = b"[2026-10-26 00:00:01.000 INF] [Mic] first -> buffered\n"
    after_rename = b"[2026-10-26 00:00:02.000 INF] [Mic] second -> drained\n"
    current = b"[2026-10-26 00:00:03.000 INF] [Mic] third -> current\n"
    path.write_bytes(seed)
    sink = NativeSink(tmp_path, "run", "s", [profile("vrcls", log_path=str(path))])
    old_handle = None
    try:
        sink.start("P")
        old_handle = sink.transports["P"][0].file
        with path.open("ab") as producer:
            producer.write(before_rename)
        path.rename(backup)  # must succeed while the collector handle is open
        assert not old_handle.closed
        with backup.open("ab") as producer:
            producer.write(after_rename)
        path.write_bytes(current)
        assert backup.read_bytes() == seed + before_rename + after_rename
        released_ns = time.perf_counter_ns()
        release.set()
        wait_for(lambda: len(outputs(tmp_path)) == 3)
        events = outputs(tmp_path)
        assert [event["translated_text"] for event in events] == ["buffered", "drained", "current"]
        assert [event["raw_evidence"]["offset"] for event in events] == [len(seed), len(seed) + len(before_rename), 0]
        identities = [event["raw_evidence"]["file_identity"] for event in events]
        assert identities[0] == identities[1] and identities[1] != identities[2]
        assert all(event["collector_received_monotonic"] >= released_ns and event["event_time_interval"] is None for event in events)
        assert old_handle.closed
        continuity = sink.continuity("P")
        assert continuity["continuous"] is False
        assert any(gap["loss_or_gap"] == "log_rotation_unobserved_interval" for gap in continuity["gaps"])
        with pytest.raises(OperationalError, match="observation gap"):
            sink.check("P")
    finally:
        release.set()
        sink.close()
    assert old_handle is not None and old_handle.closed


@pytest.mark.skipif(os.name != "nt", reason="Windows RotatingFileHandler producer noninterference")
def test_rotating_file_handler_preserves_triggering_final_record_with_active_native_sink(tmp_path, monkeypatch):
    release = hold_tail_polling(monkeypatch)
    path = tmp_path / "vrclt.log"
    seed = b"2026-10-26 00:00:00,000 [INFO] vrclt.pipeline: FINAL [en] seed  ->  " + b"x" * 700 + b"\n"
    path.write_bytes(seed)
    errors = []
    class ObservedRotatingHandler(logging.handlers.RotatingFileHandler):
        def handleError(self, record):
            errors.append(sys.exc_info()[1])
    handler = ObservedRotatingHandler(path, maxBytes=512, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] vrclt.pipeline: %(message)s"))
    logger = logging.getLogger("native-rotation-" + tmp_path.name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    sink = NativeSink(tmp_path, "run", "s", [profile("vrclt", port=udp_port(), log_path=str(path))])
    try:
        sink.start("P")
        logger.info("FINAL [en] triggering source  ->  durable output")
        handler.flush()
        # Inspect both producer files before stopping or releasing its collector.
        assert not errors
        assert path.with_name(path.name + ".1").read_bytes() == seed
        assert "triggering source  ->  durable output" in path.read_text(encoding="utf-8")
        released_ns = time.perf_counter_ns()
        release.set()
        wait_for(lambda: len(outputs(tmp_path)) == 1)
        logger.info("FINAL [en] later source  ->  later output")
        handler.flush()
        wait_for(lambda: len(outputs(tmp_path)) == 2)
        assert not errors
        events = outputs(tmp_path)
        assert [event["translated_text"] for event in events] == ["durable output", "later output"]
        assert all(event["evidence_purpose"] == "separate_final_crosscheck_not_osc_replacement" for event in events)
        assert events[0]["raw_evidence"]["offset"] == 0
        assert all(event["collector_received_monotonic"] >= released_ns and event["event_time_interval"] is None for event in events)
        assert any(gap["loss_or_gap"] == "log_rotation_unobserved_interval" for gap in sink.continuity("P")["gaps"])
        assert sink.continuity("P")["continuous"] is False
    finally:
        release.set()
        sink.close()
        handler.close()
        logger.removeHandler(handler)


@pytest.mark.skipif(os.name != "nt", reason="Windows native-handle to CRT ownership transfer")
def test_log_opener_closes_transferred_descriptor_if_stream_construction_fails(tmp_path, monkeypatch):
    import msvcrt
    path = tmp_path / "producer.log"
    path.write_bytes(b"producer content")
    descriptors = []
    convert = msvcrt.open_osfhandle
    def track(handle, flags):
        descriptor = convert(handle, flags)
        descriptors.append(descriptor)
        return descriptor
    original = OSError("synthetic stream construction failure")
    def fail(*args, **kwargs):
        raise original
    with monkeypatch.context() as patch:
        patch.setattr(msvcrt, "open_osfhandle", track)
        patch.setattr(os, "fdopen", fail)
        with pytest.raises(OSError) as observed:
            open_log_readonly(path)
    assert observed.value is original and len(descriptors) == 1
    with pytest.raises(OSError):
        os.fstat(descriptors[0])
    path.rename(tmp_path / "producer-renamed.log")
