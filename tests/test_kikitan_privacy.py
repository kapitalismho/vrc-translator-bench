"""Pure synthetic readbacks through real JSON-line serialization and diagnostics.

No process/runtime/settings/device/provider boundary is invoked by these tests.
"""
from __future__ import annotations

import copy
import io
import json
import sys

import pytest

from bench.adapter import Adapter
import bench.kikitan_adapter as module
from bench.storage import Journal


MARKER = "SYNTHETIC_PRIVATE_NESTED_MARKER"
BINDING = {"role": "A", "input_device": "synthetic-capture", "output_device": "synthetic-output",
           "source_language": "en", "target_language": "zh"}


def valid_state():
    return {"status": 0, "app_version": "synthetic-2.0.2", "config": {
        "recognizer": 0, "translator": 0, "source_language": "en", "target_language": "zh",
        "microphone": "synthetic-capture", "desktop_translation": False, "send_user_data": False,
        "send_to_chatbox": False, "speech_to_text_only": False, "disable_when_muted": False,
        "translation_only": False, "send_without_waiting_for_finish": False,
        "chatbox_wait_per_char_ms": 0, "osc_port": 0,
        "gemini_api_key": MARKER, "private_extra": {"nested": [MARKER]},
    }}


@pytest.mark.parametrize("case,method", [
    ("nested_setting_dict", "read_state"),
    ("nested_channel_list", "stop"),
    ("nested_version_list", "preflight"),
    ("bool_as_int", "read_state"),
    ("int_as_bool", "read_state"),
    ("null", "read_state"),
    ("missing", "read_state"),
])
def test_public_projection_rejects_then_recovers_before_diagnostic_persistence(tmp_path, monkeypatch, capsys, case, method):
    bad = copy.deepcopy(valid_state())
    if case == "nested_setting_dict":
        bad["config"]["recognizer"] = {"gemini_api_key": MARKER}
    elif case == "nested_channel_list":
        bad["config"]["microphone"] = [{"gemini_api_key": MARKER}]
    elif case == "nested_version_list":
        bad["app_version"] = [{"gemini_api_key": MARKER}]
    elif case == "bool_as_int":
        bad["config"]["recognizer"] = False
    elif case == "int_as_bool":
        bad["config"]["send_user_data"] = 0
    elif case == "null":
        bad["config"]["target_language"] = None
    elif case == "missing":
        del bad["config"]["microphone"]

    controller = object.__new__(module.KikitanController)
    controller.profile = "KIKI2"
    controller.record = {"channels": {"self": BINDING}}
    controller._owned_alive = lambda: True
    controller._connect = lambda: None
    controller._send = lambda *args: None
    controller._receipt = lambda *args, **kwargs: None
    controller.close = lambda: None
    frames = iter([bad, valid_state()])
    controller._state_until = lambda predicate: controller._frame(json.dumps({"method": "state", "data": json.dumps(next(frames))}))
    monkeypatch.setattr(module, "KikitanController", lambda *args: controller)
    params = {"profile": {"id": "KIKI2", "collector": {"family": "kikitan", "url": "ws://127.0.0.1:18378/"}}} if method == "preflight" else {}
    requests = [{"id": sequence, "method": method, "params": params} for sequence in (1, 2)]
    monkeypatch.setattr(sys, "stdin", io.StringIO("".join(json.dumps(request) + "\n" for request in requests)))
    assert module.main(["--directory", str(tmp_path), "--executable", sys.executable, "--profile", "KIKI2"]) == 0
    serialized = capsys.readouterr().out
    replies = [json.loads(line) for line in serialized.splitlines()]

    # This is the same persistence consumer Adapter.call reaches before any
    # Runner validation; it must see only safe rejection or primitive projection.
    consumer = object.__new__(Adapter)
    consumer.log = Journal(tmp_path / "diagnostic.tmp")
    for reply in replies:
        consumer._record("response", reply)
    path, _ = consumer.log.finalize()
    assert MARKER not in serialized
    assert MARKER not in (tmp_path / path).read_text(encoding="utf-8")
    assert replies[0] == {"id": 1, "error": {"kind": "operational", "reason": "kikitan_ValueError",
                                            "message": "Kikitan control failed: kikitan_ValueError"}}
    good = replies[1]["result"]
    if method == "preflight":
        assert good["ready"] is True and good["metadata"]["app_version"] == "synthetic-2.0.2"
    else:
        assert good["running"] is False and good["voice_output"] is False
        assert good["recognizer"] == good["translator"] == good["chatbox_wait_per_char_ms"] == good["osc_port"] == 0
        assert type(good["recognizer"]) is int and type(good["send_user_data"]) is bool
        assert good["send_user_data"] is False
        assert good["channels"]["self"] == BINDING
        assert good["app_settings"]["microphone"] == "synthetic-capture"
        assert "gemini_api_key" not in good and "private_extra" not in good["app_settings"]
