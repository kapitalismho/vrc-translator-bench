from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf

from tools import prepare_japanese as prep
from tools.japanese_reference import acoustic_stats, align_characters, ctc_align, merge_speaker_turns, punctuate, speaker_at


class JapanesePreparationTests(unittest.TestCase):
    def setUp(self):
        base = prep.LOCAL / "test-state"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.temp.name)
        self.local = self.root / ".data" / "japanese"
        self.local.mkdir(parents=True)
        self.root_patch = patch.object(prep, "ROOT", self.root)
        self.local_patch = patch.object(prep, "LOCAL", self.local)
        self.root_patch.start()
        self.local_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.addCleanup(self.local_patch.stop)
        self.addCleanup(self.temp.cleanup)

    def selection(self):
        prep.select()
        return prep.load(self.local / "selection.json")

    def test_selection_reproducible_source_disjoint_and_honest(self):
        first = self.selection()
        self.assertEqual(first, self.selection())
        self.assertFalse(first["rights"]["release_cleared"])
        self.assertFalse(first["listening_performed"])
        self.assertEqual(first["casual_chat_seconds_confirmed"], 0)
        main = [chunk for chunk in first["chunks"] if chunk["split"] == "main"]
        self.assertEqual(sum(chunk["source_end"] - chunk["source_start"] for chunk in main if chunk["category"] == "general"), 1200)
        self.assertEqual(sum(chunk["source_end"] - chunk["source_start"] for chunk in main if chunk["category"] == "stress"), 600)
        for index, a in enumerate(first["chunks"]):
            for b in first["chunks"][index + 1:]:
                if a["source_id"] == b["source_id"]:
                    self.assertFalse(a["source_start"] < b["source_end"] and a["source_end"] > b["source_start"])
        selected = {(chunk["source_id"], chunk["source_start"], chunk["source_end"]) for chunk in main if chunk["category"] == "general"}
        pool = {(chunk["source_id"], chunk["source_start"], chunk["source_end"]) for chunk in first["general_candidate_pool"]}
        self.assertLess(selected, pool)

    def test_assembly_preserves_samples_and_two_second_gap_mapping(self):
        chunks = []
        signals = [np.full(4800, 0.125, dtype=np.float32), np.full(9600, -0.25, dtype=np.float32)]
        for index, signal in enumerate(signals):
            path = self.local / f"{index}.wav"
            sf.write(path, signal, 48000, subtype="PCM_16")
            chunks.append({"id": str(index), "source_id": f"source{index}", "source_start": 10, "source_end": 10 + len(signal) / 48000, "audio": {"path": str(path.relative_to(self.root))}})
        output = self.local / "combined.wav"
        mapping = prep.assemble(chunks, output)
        audio, rate = sf.read(output, dtype="float32")
        self.assertEqual(rate, 48000)
        self.assertEqual(mapping[0]["playback_start"], 0)
        self.assertEqual(mapping[1]["playback_start"], 2.1)
        self.assertEqual(mapping[1]["playback_end"], 2.3)
        np.testing.assert_array_equal(audio[:4800], signals[0])
        np.testing.assert_array_equal(audio[4800:100800], 0)
        np.testing.assert_array_equal(audio[100800:], signals[1])

    def test_ctc_forced_alignment_excludes_blank_edges_and_handles_repeated_tokens(self):
        probabilities = np.full((7, 3), 0.005)
        for frame, token in enumerate([0, 1, 1, 0, 1, 2, 0]):
            probabilities[frame, token] = 0.99
        result = ctc_align(np.log(probabilities), [1, 1, 2])
        self.assertEqual([(item["start_frame"], item["end_frame"]) for item in result], [(1, 3), (4, 5), (5, 6)])
        with self.assertRaises(ValueError):
            ctc_align(np.log(probabilities[:2]), [1, 1])
        with self.assertRaises(ValueError):
            ctc_align(np.log(probabilities), [0])

    def test_oov_wildcard_preserves_supported_acoustic_constraints(self):
        probabilities = np.full((7, 4), 0.001)
        for frame, token in enumerate([0, 1, 0, 3, 0, 2, 0]):
            probabilities[frame, token] = 0.997
        result, unsupported = align_characters(np.log(probabilities), "a?b", {"a": 1, "b": 2})
        self.assertEqual(unsupported, {1})
        self.assertEqual((result[0]["start_frame"], result[0]["end_frame"]), (1, 2))
        self.assertEqual((result[2]["start_frame"], result[2]["end_frame"]), (5, 6))

    def test_punctuation_inserts_only_and_marks_heuristic(self):
        words = [{"id": 0, "text": "これは", "start": 0.1, "end": 0.4, "speaker": "speaker_00", "block": 0}, {"id": 1, "text": "本物", "start": 1.1, "end": 1.5, "speaker": "speaker_00", "block": 0}, {"id": 2, "text": "です", "start": 1.5, "end": 1.8, "speaker": "speaker_00", "block": 0}]
        sentences = punctuate(words)
        restored = "".join(sentence["text"] for sentence in sentences)
        self.assertEqual(restored.replace("。", ""), "".join(word["text"] for word in words))
        self.assertEqual(len(sentences), 2)
        self.assertTrue(all("heuristic" in sentence["punctuation"] for sentence in sentences))

    def test_estimated_speaker_overlap_is_not_hidden(self):
        turns = [{"start": 0, "end": 1, "speaker": "a"}, {"start": 0.5, "end": 2, "speaker": "b"}]
        self.assertEqual(speaker_at(0.7, 0.9, turns), ("a", True))
        self.assertEqual(speaker_at(3, 4, turns), ("unknown", False))

    def test_turns_follow_speaker_changes_not_same_speaker_pauses(self):
        segments = [{"start": 0, "end": 1, "speaker": "a"}, {"start": 2, "end": 3, "speaker": "a"}, {"start": 3, "end": 4, "speaker": "b"}, {"start": 4, "end": 5, "speaker": "a"}]
        result = merge_speaker_turns(segments)
        self.assertEqual([(item["start"], item["end"], item["speaker"]) for item in result], [(0, 3, "a"), (3, 4, "b"), (4, 5, "a")])
        self.assertEqual(segments[0]["end"], 1)

    def test_silence_inside_coalesced_turns_does_not_inflate_overlap(self):
        segments = [{"start": 0, "end": 10, "speaker": "b"}, {"start": 1, "end": 2, "speaker": "a"}, {"start": 8, "end": 9, "speaker": "a"}]
        turns = merge_speaker_turns(segments)
        self.assertEqual(len(turns), 2)
        stats = acoustic_stats([], turns, segments)
        self.assertEqual(stats["estimated_pairwise_overlap_seconds"], 2)
        self.assertIn("Raw estimated", stats["overlap_basis"])

    def test_isolated_candidate_rejects_intruding_speaker(self):
        reference = {"audio_duration_seconds": 10, "blocks": [{"id": 0, "start": 0.9, "end": 2.1}], "words": [{"start": 1, "end": 2, "speaker": "a", "speaker_ambiguous": False, "block": 0}], "diarization_segments": [{"start": 0.9, "end": 2.1, "speaker": "a"}, {"start": 1.5, "end": 1.7, "speaker": "b"}]}
        self.assertEqual(prep.isolated_candidates(reference), [])
        reference["diarization_segments"].pop()
        result = prep.isolated_candidates(reference)
        self.assertEqual(len(result), 1)
        self.assertIn("short", result[0]["tags"])

    def test_public_metadata_has_no_derived_speech_content(self):
        selection = self.selection()
        selection["chunks"][0]["transcript"] = "PRIVATE_DERIVED_SPEECH_SENTINEL"
        selection["chunks"][0]["words"] = [{"text": "PRIVATE_DERIVED_SPEECH_SENTINEL"}]
        value = prep.public_metadata(selection, {})
        serialized = json.dumps(value)
        self.assertNotIn("PRIVATE_DERIVED_SPEECH_SENTINEL", serialized)
        self.assertFalse(value["rights"]["release_cleared"])
        self.assertIsNone(value["sources"][0]["original_video_url"])
        self.assertIn("NO_AUDIO", value["publication"])
        prep.assert_metadata_only(value)
        with self.assertRaises(ValueError):
            prep.assert_metadata_only({"nested": [{"words": [{"text": "PRIVATE_DERIVED_SPEECH_SENTINEL"}]}]})


if __name__ == "__main__":
    unittest.main()
