"""Source-derived, deliberately non-reconstructing native output projections.

Unknown finality, language, timing and revision relationships stay unknown. Raw
JSON is allowlisted here before it can reach the durable collector journal.
"""
from __future__ import annotations

import json
import re


VRCS_EVENTS = (
    "asr.partial", "asr.final", "asr.cancelled", "asr.reset", "asr.failed",
    "translation.live_updated", "translation.started", "translation.partial",
    "translation.completed", "translation.failed", "chatbox.sent",
)


def pick(value, fields):
    return {key: value[key] for key in fields if key in value}


def _text(value):
    return value if isinstance(value, str) else None


def puripuly(value):
    raw = pick(value, ("output_version", "topic", "channel", "source", "text",
                       "utterance_id", "sequence", "instance_id", "reason", "after",
                       "snapshot_required", "state"))
    topic = raw.get("topic")
    if topic == "gap":
        return raw, {"loss_or_gap": "producer_gap", "native_endpoint": "gap"}
    if topic not in ("translation", "transcript", "session_state_changed"):
        return raw, None
    channel = raw.get("channel")
    if channel not in ("self", "peer"):
        channel = None
    fields = {"input_channel": channel, "native_endpoint": topic,
              "native_id": raw.get("utterance_id") or None,
              "native_sequence": raw.get("sequence"),
              "producer_instance": raw.get("instance_id"),
              "endpoint_stage": ("peer_post_overlay_projection" if channel == "peer"
                                 else "self_pre_overlay_chatbox_projection"),
              "translated_text": _text(raw.get("text")) if topic == "translation" else None,
              "source_text": _text(raw.get("text")) if topic == "transcript" else None}
    if topic != "translation":
        fields["endpoint_stage"] = topic
    return raw, fields


def vrct(value):
    raw = pick(value, ("type", "source", "src_languages", "dst_languages", "message",
                       "translation", "transliteration"))
    kind = raw.get("type")
    if kind not in ("SENT", "RECEIVED"):
        return raw, None
    if raw.get("source") == "ocr":
        return raw, {"excluded": "ocr", "native_endpoint": kind}
    translations = raw.get("translation")
    texts = translations if isinstance(translations, list) and all(isinstance(t, str) for t in translations) else None
    return raw, {"input_channel": "self" if kind == "SENT" else "peer",
                 "native_endpoint": kind, "endpoint_stage": "post_osc_ui_dispatch_websocket",
                 "source_text": _text(raw.get("message")),
                 # Arrays retain their boundaries; joining would invent a target mapping.
                 "translated_text": texts[0] if texts is not None and len(texts) == 1 else None,
                 "translated_texts": texts,
                 "producer_languages": pick(raw, ("src_languages", "dst_languages")),
                 "boundary": "multiple_translation_targets" if texts and len(texts) > 1 else None}


def vrcs(value):
    raw = pick(value, ("api_version", "event_id", "type", "timestamp", "message_id", "source"))
    kind = raw.get("type")
    payload = value.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    payload_fields = ("subtitle_id", "text", "language", "target_language", "utterance_id",
                      "source_utterance_id", "completed_original", "translation", "source_group",
                      "conversation_preview", "code", "reason", "connection_id", "events", "dropped")
    safe = pick(payload, payload_fields)
    for key, fields in {
        "translation": ("text", "source_language", "target_language", "provider", "model", "created_at", "source_group"),
        "source_group": ("subtitle_ids", "text"),
        "conversation_preview": ("text", "translation"),
    }.items():
        if isinstance(safe.get(key), dict):
            safe[key] = pick(safe[key], fields)
    translation = safe.get("translation")
    if isinstance(translation, dict) and isinstance(translation.get("source_group"), dict):
        translation["source_group"] = pick(translation["source_group"], ("subtitle_ids", "text"))
    raw["payload"] = safe
    fields = {"native_endpoint": kind, "producer_time_raw": raw.get("timestamp"),
              "producer_clock": "app_utc_wall", "native_id": raw.get("message_id"),
              "native_event_id": raw.get("event_id"),
              "input_channel": {"speaker": "peer", "microphone": "self"}.get(raw.get("source"))}
    if kind == "system.lagged":
        return raw, {**fields, "loss_or_gap": "producer_lagged", "dropped": safe.get("dropped")}
    if isinstance(kind, str) and kind.startswith("system."):
        return raw, {**fields, "control": kind}
    if kind not in VRCS_EVENTS:
        return raw, None
    fields["update_kind"] = kind
    fields["endpoint_stage"] = kind
    if kind == "translation.completed" and isinstance(translation, dict):
        group = translation.get("source_group")
        fields.update(translated_text=_text(translation.get("text")),
                      source_text=_text(group.get("text")) if isinstance(group, dict) else None,
                      producer_languages=pick(translation, ("source_language", "target_language")),
                      source_group=group)
    elif kind == "translation.partial":
        fields.update(translated_text=_text(safe.get("text")),
                      producer_languages=pick(safe, ("target_language",)))
    elif kind == "translation.live_updated":
        fields.update(translated_text=_text(safe.get("translation")), source_text=_text(safe.get("text")),
                      producer_languages=pick(safe, ("language", "target_language")))
    elif kind.startswith("asr."):
        fields.update(source_text=_text(safe.get("text")), producer_languages=pick(safe, ("language",)))
    return raw, fields


def kikitan_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate Kikitan JSON field")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique)


def kikitan(value):
    """Only the exact recognition envelope is safe to retain verbatim.

    State/error/config frames contain nested JSON strings, including credentials.
    Do not treat recursive named-field redaction as a privacy boundary.
    """
    if value.get("method") != "recognition":
        return None
    if set(value) != {"method", "data"} or not isinstance(value["data"], str):
        raise ValueError("Invalid Kikitan recognition envelope")
    payload = kikitan_json(value["data"])
    if (not isinstance(payload, dict) or set(payload) != {"transcription", "translation", "final"}
            or not isinstance(payload["transcription"], str)
            or not isinstance(payload["translation"], str) or type(payload["final"]) is not bool):
        raise ValueError("Invalid Kikitan recognition payload")
    return {"input_channel": "self", "native_endpoint": "recognition",
            "endpoint_stage": "translation_output", "source_text": payload["transcription"],
            "translated_text": payload["translation"], "native_final_signal": payload["final"]}


def osc(family, address, args):
    if family != "vrclt" or address not in ("/chatbox/input", "/chatbox/typing"):
        return None
    if address == "/chatbox/input" and (not args or not isinstance(args[0], str)):
        return {"native_endpoint": address, "boundary": "invalid_chatbox_arguments"}
    return {"input_channel": "self", "native_endpoint": address,
            "endpoint_stage": "self_chatbox_udp", "display_text": args[0] if address == "/chatbox/input" else None,
            "boundary": "unstructured_chatbox_text" if address == "/chatbox/input" else None}


# Both file loggers use a millisecond wall-clock prefix. The family-specific
# parser below additionally requires the exact source output marker.
LOG_TIME = re.compile(r"^\ufeff?\[?(?P<timestamp>\d{4}-\d\d-\d\d \d\d:\d\d:\d\d[.,]\d{3})(?=\s|\])")


def log_record(family, text):
    timestamp = LOG_TIME.match(text)
    if not timestamp:
        return None
    if "CONFIG_SNAPSHOT" in text:
        return {"excluded": "config_snapshot"}
    if family == "vrclt":
        marker = re.match(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} \[INFO\] vrclt\.pipeline: FINAL \[([^\]\r\n]+)\] ", text)
        if not marker:
            return None
        channel = "self"
        body = text[marker.end():].rstrip("\r\n")
        extra = {"producer_languages": {"detected_source_language": marker.group(1)},
                 "update_kind": "FINAL", "endpoint_stage": "final_log_crosscheck",
                 "evidence_purpose": "separate_final_crosscheck_not_osc_replacement"}
    else:
        marker = re.match(r"^\ufeff?\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} INF\] \[(Desktop|Mic)\] ", text)
        if not marker:
            return None
        channel = "peer" if marker.group(1) == "Desktop" else "self"
        body = text[marker.end():].rstrip("\r\n")
        extra = {"endpoint_stage": "recognition_result_file_log"}
    fields = {"input_channel": channel, "native_endpoint": "FINAL" if family == "vrclt" else f"[{marker.group(1)}]",
              "producer_time_raw": timestamp.group("timestamp"),
              "producer_clock": "app_local_wall_timezone_unverified", **extra}
    separator = "  ->  " if family == "vrclt" else " -> "
    if body.count("->") != 1 or body.count(separator) != 1 or "\n" in body or "\r" in body:
        fields["boundary"] = "ambiguous_log_text_boundary"
    else:
        source, translated = body.split(separator)
        fields.update(source_text=source, translated_text=translated)
    return fields
