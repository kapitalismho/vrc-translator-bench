from array import array
import math
import shutil
import wave

import pytest

from tools.prepare_english import RATE, candidate, make_mapping, map_interval, merged, overlap, render_pcm, tick, timeline, trim_mapping, write_wave


def test_other_speaker_occupied_gap_is_cut_to_three_seconds():
    mapping, removed = make_mapping(0, tick(15), [(0, tick(1)), (tick(13), tick(15))], [(tick(2), tick(12))])
    assert removed == [{"source_start": tick(2.5), "source_end": tick(11.5), "reason": "long_target_gap_occupied_by_other_speakers"}]
    assert mapping[-1]["playback_end"] == tick(6)
    assert map_interval(tick(13), tick(15), mapping) == [[tick(4), tick(6)]]
    assert map_interval(0, tick(1), mapping) == [[0, tick(1)]]


@pytest.mark.parametrize("events,others", [
    ([(0, tick(1)), (tick(13), tick(15))], []),
    ([(0, tick(1)), (tick(9), tick(15))], [(tick(2), tick(8))]),
    ([(0, tick(1)), (tick(13), tick(15))], [(tick(2), tick(2.9))]),
])
def test_target_pauses_are_not_generic_vad_compressed(events, others):
    mapping, removed = make_mapping(0, tick(15), events, others)
    assert removed == []
    assert map_interval(0, tick(15), mapping) == [[0, tick(15)]]


def test_occupied_duration_is_union_not_double_counted():
    assert overlap(0, tick(3), [(0, tick(.6)), (0, tick(.6))]) == tick(.6)
    mapping, removed = make_mapping(0, tick(15), [(0, tick(1)), (tick(13), tick(15))], [(tick(2), tick(2.6)), (tick(2), tick(2.6))])
    assert removed == []
    assert mapping[-1]["playback_end"] == tick(15)


def test_target_vocalization_protects_occupied_gap():
    mapping, removed = make_mapping(0, tick(15), [(0, tick(1)), (tick(7), tick(8)), (tick(13), tick(15))], [(tick(2), tick(12))])
    assert removed == []
    assert mapping[-1]["playback_end"] == tick(15)


def test_context_word_crossing_deleted_audio_has_explicit_parts():
    mapping, _ = make_mapping(0, tick(15), [(0, tick(1)), (tick(13), tick(15))], [(tick(2), tick(12))])
    assert map_interval(tick(2), tick(12), mapping) == [[tick(2), tick(2.5)], [tick(2.5), tick(3)]]
    assert map_interval(tick(3), tick(10), mapping) == []
    assert map_interval(tick(2.5), tick(2.5), mapping) == [[tick(2.5), tick(2.5)]]


def test_exact_retained_boundary_is_not_duplicated():
    mapping, _ = make_mapping(0, tick(15), [(0, tick(1)), (tick(13), tick(15))], [(tick(2), tick(12))])
    assert map_interval(tick(11.5), tick(11.5), mapping) == [[tick(2.5), tick(2.5)]]
    assert map_interval(tick(15), tick(15), mapping) == [[tick(6), tick(6)]]


def test_exact_budget_does_not_bisect_target_word_and_records_padding():
    mapping = [{"source_start": tick(10), "source_end": tick(20), "playback_start": 0, "playback_end": tick(10)}]
    trimmed, padding = trim_mapping(mapping, tick(5), [(tick(14.5), tick(15.5))])
    assert trimmed[-1]["source_end"] == tick(14.5)
    assert trimmed[-1]["playback_end"] == tick(4.5)
    assert padding == tick(.5)
    assert trim_mapping(mapping, tick(5), [(tick(11), tick(16))]) is None
    assert trim_mapping(mapping, tick(11), []) is None


def test_trim_boundary_recomputed_after_compression():
    mapping, _ = make_mapping(0, tick(20), [(0, tick(1)), (tick(13), tick(20))], [(tick(2), tick(12))])
    trimmed, padding = trim_mapping(mapping, tick(5), [(tick(13), tick(14.5))])
    assert trimmed[-1]["source_end"] == tick(13)
    assert trimmed[-1]["playback_end"] == tick(4)
    assert padding == tick(1)


def test_union_of_target_events_preserves_overlap():
    assert merged([(tick(3), tick(5)), (0, tick(4)), (tick(5), tick(6))]) == [[0, tick(6)]]
    mapping, removed = make_mapping(0, tick(20), [(0, tick(4)), (tick(3), tick(10)), (tick(15), tick(20))], [(tick(4), tick(14))])
    assert removed == []
    assert mapping[-1]["playback_end"] == tick(20)


def event(identifier, speaker, start, end, text, act):
    return {"id": identifier, "speaker": speaker, "source_start": tick(start), "source_end": tick(end), "text": text,
            "kind": "w", "punctuation": False, "truncated": False, "sound_type": None, "dialogue_act": act}




def test_overlapping_target_events_do_not_leave_an_earlier_word_cut():
    mapping = [{"source_start": 0, "source_end": tick(20), "playback_start": 0, "playback_end": tick(20)}]
    trimmed, padding = trim_mapping(mapping, tick(11), [(tick(9), tick(10.5)), (tick(10), tick(12))])
    assert trimmed[-1]["source_end"] == tick(9)
    assert padding == tick(2)


def test_scored_words_context_dialogue_acts_and_turns_share_new_timeline():
    mapping, removed = make_mapping(0, tick(15), [(0, tick(1)), (tick(13), tick(15))], [(tick(2), tick(12))])
    data = {"streams": {"A": [event("a1", "A", 0, 1, "hello", "act-a1"), event("a2", "A", 13, 15, "again", "act-a2")],
                        "B": [event("b1", "B", 2, 12, "context", "act-b1")]},
            "acts": [{"id": "act-a1", "speaker": "A", "type": "ami_da_4", "word_ids": ["a1"], "source_start": 0, "source_end": tick(1)},
                     {"id": "act-a2", "speaker": "A", "type": "ami_da_4", "word_ids": ["a2"], "source_start": tick(13), "source_end": tick(15)},
                     {"id": "act-b1", "speaker": "B", "type": "ami_da_4", "word_ids": ["b1"], "source_start": tick(2), "source_end": tick(12)}], "topics": []}
    item = {"id": "sample", "speaker": "A", "source_start": 0, "source_end": tick(15), "frames": tick(6), "mapping": mapping, "removed": removed, "padding_frames": 0}
    result = timeline(data, item)
    assert [(w["id"], w["scored"]) for w in result["words_and_events"]] == [("a1", True), ("b1", False), ("a2", True)]
    assert result["words_and_events"][1]["fully_retained"] is False
    assert result["words_and_events"][-1]["playback_start"] == tick(4)
    assert next(s for s in result["sentences"] if s["id"] == "act-a2")["playback_start"] == tick(4)
    assert [(t["speaker"], t["playback_start"]) for t in result["turns"]] == [("A", 0), ("B", tick(2)), ("A", tick(4))]


def test_partial_target_word_is_rejected():
    data = {"streams": {"A": [event("a", "A", 0, 2, "whole", "act")]}, "acts": [], "topics": []}
    item = {"id": "bad", "speaker": "A", "source_start": 0, "source_end": tick(1), "frames": tick(1),
            "mapping": [{"source_start": 0, "source_end": tick(1), "playback_start": 0, "playback_end": tick(1)}], "removed": [], "padding_frames": 0}
    with pytest.raises(ValueError, match="Target word was cut"):
        timeline(data, item)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required for actual PCM rendering")
def test_real_decoder_renders_cut_samples_and_explicit_silence(tmp_path):
    source = tmp_path / "source.wav"
    samples = array("h", (round(10000 * math.sin(2 * math.pi * 400 * n / RATE)) for n in range(RATE)))
    write_wave(source, samples.tobytes())
    item = {"id": "synthetic-test-only", "mapping": [{"source_start": 0, "source_end": RATE // 4, "playback_start": 0, "playback_end": RATE // 4},
                                                       {"source_start": RATE // 2, "source_end": RATE, "playback_start": RATE // 4, "playback_end": RATE * 3 // 4}],
            "padding_frames": RATE // 4, "frames": RATE}
    pcm, normalization = render_pcm(source, item)
    assert len(pcm) == RATE * 2
    assert pcm[-RATE // 4 * 2:] == bytes(RATE // 4 * 2)
    decoded = array("h")
    decoded.frombytes(pcm)
    assert max(abs(v) for v in decoded) == round(32767 * 10 ** (-3 / 20))
    assert normalization["source_peak_pcm16"] == 10000
    destination = tmp_path / "result.wav"
    write_wave(destination, pcm)
    with wave.open(str(destination), "rb") as stream:
        assert (stream.getframerate(), stream.getnchannels(), stream.getnframes()) == (RATE, 1, RATE)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required for actual PCM rendering")
def test_source_audio_shorter_than_metadata_is_not_silently_padded(tmp_path):
    source = tmp_path / "short.wav"
    write_wave(source, bytes(RATE * 2))
    item = {"id": "bad-source", "mapping": [{"source_start": 0, "source_end": RATE * 2, "playback_start": 0, "playback_end": RATE * 2}],
            "padding_frames": 0, "frames": RATE * 2}
    with pytest.raises(ValueError, match="Source ends before selected interval"):
        render_pcm(source, item)


def test_candidate_requires_manual_dialogue_act_for_every_scored_word():
    words = [event(f"w{i}", "A", i, i + .5, "real-source-word-test", "act") for i in range(100)]
    data = {"streams": {"A": words}, "end": tick(100), "speakers": {"A": {"channel": "0", "global_name": "test"}}}
    assert candidate(data, "test", "A", 0, 90) is not None
    words[30].pop("dialogue_act")
    assert candidate(data, "test", "A", 0, 90) is None


def test_candidate_rejects_invalid_nonword_region_without_guessing_correction():
    words = [event(f"w{i}", "A", i, i + .5, "test", "act") for i in range(100)]
    data = {"streams": {"A": words}, "end": tick(100), "speakers": {"A": {"channel": "0", "global_name": "test"}},
            "invalid_events": [{"source_start": tick(35), "source_end": tick(36), "kind": "vocalsound"}]}
    assert candidate(data, "test", "A", 0, 90) is None


def test_adjacent_words_do_not_make_whole_continuous_speech_indivisible():
    mapping = [{"source_start": 0, "source_end": tick(20), "playback_start": 0, "playback_end": tick(20)}]
    trimmed, padding = trim_mapping(mapping, tick(11), [(0, tick(10)), (tick(10), tick(12))])
    assert trimmed[-1]["source_end"] == tick(10)
    assert padding == tick(1)
