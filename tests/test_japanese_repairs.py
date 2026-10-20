from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace

import numpy as np

from tools import prepare_japanese as prep
from tools.japanese_alignment import configure_surface_processor, context_requests, prediction_unit_index, raw_word_predictions
from tools.japanese_pronunciation import audit_cached_readings, pronunciation_targets
from tools.japanese_reference import punctuate


class JapaneseRepairTests(unittest.TestCase):
    def reserve(self):
        return {"source_start": 100.0, "audio_duration_seconds": 10, "blocks": [{"id": 0, "start": 0.8, "end": 2.3, "text": "unit"}], "words": [{"id": 0, "text": "unit", "start": 1.0, "end": 2.0, "speaker": "a", "speaker_ambiguous": False, "block": 0}], "diarization_segments": [{"start": 1.0, "end": 2.0, "speaker": "a"}]}

    def isolated(self, reserve):
        entry = {"id": "synthetic", "source_start": 100.92, "source_end": 102.08}
        word = reserve["words"][0]
        artifact = {"words": [{"origin_word_id": 0, "text": word["text"], "source_start": 100 + word["start"], "source_end": 100 + word["end"], "start": 100 + word["start"] - entry["source_start"], "end": 100 + word["end"] - entry["source_start"]}]}
        return entry, artifact

    def test_candidate_rejects_leading_word_intersection(self):
        reserve = self.reserve()
        reserve["words"].append({**reserve["words"][0], "start": 0.8, "end": 1.1})
        self.assertEqual(prep.isolated_candidates(reserve), [])

    def test_candidate_rejects_trailing_word_intersection(self):
        reserve = self.reserve()
        reserve["words"].append({**reserve["words"][0], "start": 1.9, "end": 2.3})
        self.assertEqual(prep.isolated_candidates(reserve), [])

    def test_candidate_accepts_complete_words_at_both_exact_edges(self):
        reserve = self.reserve()
        reserve["words"][0].update(start=0.92, end=2.08)
        candidates = prep.isolated_candidates(reserve)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["word_ids"], [0])

    def test_candidate_preserves_missing_endpoint_and_speaker_exclusions(self):
        for endpoint in ("start", "end"):
            with self.subTest(endpoint=endpoint):
                reserve = self.reserve()
                reserve["words"][0][endpoint] = None
                self.assertEqual(prep.isolated_candidates(reserve), [])
        reserve = self.reserve()
        reserve["diarization_segments"].append({"start": 1.5, "end": 1.6, "speaker": "b"})
        self.assertEqual(prep.isolated_candidates(reserve), [])

    def test_intersection_audit_accepts_all_words_and_exact_source_mapping(self):
        reserve = self.reserve()
        entry, artifact = self.isolated(reserve)
        audit = prep.audit_isolated_reference(entry, artifact, reserve)
        self.assertEqual(audit["boundary_crossings"], 0)
        self.assertEqual(audit["intersecting_source_word_count"], 1)
        self.assertTrue(audit["all_intersections_retained"])

    def test_intersection_audit_rejects_each_crossing_even_if_reference_omits_it(self):
        for start, end in ((0.8, 1.1), (1.9, 2.3)):
            with self.subTest(start=start, end=end):
                reserve = self.reserve()
                entry, artifact = self.isolated(reserve)
                reserve["words"].append({**reserve["words"][0], "start": start, "end": end})
                with self.assertRaisesRegex(ValueError, "crosses aligned word"):
                    prep.audit_isolated_reference(entry, artifact, reserve)

    def test_intersection_audit_rejects_omitted_complete_word(self):
        reserve = self.reserve()
        entry, artifact = self.isolated(reserve)
        reserve["words"].append({**reserve["words"][0], "start": 1.5, "end": 1.8})
        with self.assertRaisesRegex(ValueError, "omits or adds"):
            prep.audit_isolated_reference(entry, artifact, reserve)

    def test_intersection_audit_rejects_bad_mapping_and_untimed_block(self):
        reserve = self.reserve()
        entry, artifact = self.isolated(reserve)
        artifact["words"][0]["source_start"] += 0.01
        with self.assertRaisesRegex(ValueError, "mapping mismatch"):
            prep.audit_isolated_reference(entry, artifact, reserve)
        entry, artifact = self.isolated(reserve)
        reserve["words"].append({**reserve["words"][0], "block": 1, "start": None, "end": None})
        reserve["blocks"].append({"id": 1, "start": 1.2, "end": 1.4})
        with self.assertRaisesRegex(ValueError, "untimed ASR block"):
            prep.audit_isolated_reference(entry, artifact, reserve)

    def test_raw_predictions_preserve_nonuniform_intervals(self):
        raw = [{"text": "a", "start": 0.12, "end": 0.34}, {"text": "b", "start": 0.56, "end": 1.32}]
        self.assertEqual(raw_word_predictions(raw, ["a", "b"], 2, {0, 1}), raw)

    def test_raw_predictions_reject_lexical_replacement_deletion_and_reordering(self):
        for texts in (["a"], ["a", "c"], ["b", "a"]):
            with self.subTest(texts=texts):
                with self.assertRaisesRegex(ValueError, "changed/dropped"):
                    raw_word_predictions([{"text": text, "start": 0.1, "end": 0.2} for text in texts], ["a", "b"], 2, {0})

    def test_raw_predictions_reject_invalid_or_empty_required_intervals(self):
        for start, end in ((float("nan"), 0.2), (0.1, float("inf")), (-0.1, 0.2), (0.3, 0.2), (0.1, 2.021), (0.1, 0.1)):
            with self.subTest(start=start, end=end):
                with self.assertRaises(ValueError):
                    raw_word_predictions([{"text": "a", "start": start, "end": end}], ["a"], 2, {0})

    def test_raw_predictions_allow_only_bounded_physical_end_clipping(self):
        prediction = raw_word_predictions([{"text": "a", "start": 1.8, "end": 2.01}], ["a"], 2, {0})
        self.assertEqual(prediction[0]["end"], 2)
        contextual = [{"text": "a", "start": 0, "end": 0}, {"text": "b", "start": 0.4, "end": 0.8}]
        self.assertEqual(raw_word_predictions(contextual, ["a", "b"], 2, {1}), contextual)

    def test_dedicated_processor_disables_timestamp_interpolation(self):
        processor = SimpleNamespace()
        configure_surface_processor(processor, ["surface_a", "surface_b"])
        reversed_points = np.array([100, 80, 140])
        self.assertEqual(processor.fix_timestamp(reversed_points), [100, 80, 140])
        self.assertEqual(processor.tokenize_japanese("not replacement text"), ["surface_a", "surface_b"])

    def test_context_requests_keep_true_block_edges_for_edge_oov(self):
        block = {"start": 0, "end": 20}
        leading = context_requests([{"start": None, "end": None}, {"start": 8, "end": 9}], {0}, block)
        trailing = context_requests([{"start": 8, "end": 9}, {"start": None, "end": None}], {1}, block)
        self.assertEqual(leading[0]["start"], 0)
        self.assertEqual(trailing[0]["end"], 20)
        self.assertEqual(leading[0]["required"], [0])
        self.assertEqual(trailing[0]["required"], [1])

    def test_pronunciation_targets_use_dictionary_units_without_surface_rewriting(self):
        surfaces = ["symbol", "name"]
        features = {"symbol": [{"pron": "カ’ナ"}], "name": [{"pron": "キ"}, {"pron": "クケ"}]}
        readings, spans = pronunciation_targets(surfaces, features.__getitem__, {char: index for index, char in enumerate("カナキクケ")})
        self.assertEqual(surfaces, ["symbol", "name"])
        self.assertEqual(readings, ["カナ", "キクケ"])
        self.assertEqual(spans, [(0, 2), (2, 5)])

    def test_pronunciation_targets_reject_uncovered_or_missing_reading(self):
        for features in ([], [{"pron": "*"}], [{"pron": "unknown"}]):
            with self.subTest(features=features):
                with self.assertRaisesRegex(ValueError, "does not cover"):
                    pronunciation_targets(["unit"], lambda _: features, {"カ": 1})

    def test_final_inventory_requires_numeric_words_and_sentence_bounds(self):
        reference = {"words": [{"start": 0.1, "end": 0.5}], "sentences": [{"start": 0.1, "end": 0.5}]}
        inventory = prep.timing_inventory("synthetic", reference, 1)
        self.assertEqual(inventory["missing_words_bounds"], 0)
        self.assertEqual(inventory["missing_sentences_bounds"], 0)
        for kind in ("words", "sentences"):
            for value in (None, float("nan"), float("inf")):
                with self.subTest(kind=kind, value=value):
                    missing = copy.deepcopy(reference)
                    missing[kind][0]["start"] = value
                    with self.assertRaisesRegex(ValueError, "missing/nonfinite"):
                        prep.timing_inventory("synthetic", missing, 1)
        invalid = copy.deepcopy(reference)
        invalid["sentences"][0]["end"] = 0.05
        with self.assertRaisesRegex(ValueError, "outside audio"):
            prep.timing_inventory("synthetic", invalid, 1)

    def test_sentence_bounds_cover_actual_overlapping_word_intervals(self):
        words = [{"id": 0, "text": "first", "start": 1.0, "end": 1.4, "speaker": "a", "block": 0}, {"id": 1, "text": "second", "start": 0.8, "end": 1.2, "speaker": "a", "block": 0}]
        sentences = punctuate(words)
        self.assertEqual(len(sentences), 1)
        self.assertEqual((sentences[0]["start"], sentences[0]["end"]), (0.8, 1.4))
        self.assertEqual(sentences[0]["text"], "firstsecond。")

    def test_baseline_audit_preserves_lexical_units_blocks_and_supported_intervals(self):
        baseline = {"words": [{"text": "a", "start": 0.1, "end": 0.2}, {"text": "b", "start": None, "end": None}], "blocks": [{"id": 0, "text": "ab"}]}
        current = copy.deepcopy(baseline)
        current["words"][1].update(start=0.5, end=0.9)
        self.assertEqual(prep.audit_baseline_lexical(current, baseline)["previously_supported_intervals_unchanged"], 1)
        for mutate in (lambda item: item["words"][0].update(start=0.11), lambda item: item["words"][1].update(text="c"), lambda item: item["blocks"][0].update(text="changed")):
            bad = copy.deepcopy(current)
            mutate(bad)
            with self.assertRaises(ValueError):
                prep.audit_baseline_lexical(bad, baseline)

    def alignment_evidence(self):
        word = {"id": 0, "block": 0, "text": "a", "start": 1.1, "end": 1.7, "timing_status": "dedicated_forced_aligner_raw_surface_word", "alignment_prediction_path": ".data/japanese/synthetic.json", "alignment_model": "controlled_model", "alignment_model_revision": "controlled_revision"}
        reference = {"source_start": 100, "words": [word]}
        prediction = {"text": "a", "start": 0.1, "end": 0.7}
        record = {"source_audio_sha256": "source_hash", "model": "controlled_model", "revision": "controlled_revision", "source_start_sample_16k": 101 * 16000, "source_end_sample_16k": 103 * 16000, "acoustic_input_samples": 32000, "timestamp_interpolation": False, "surface_words": ["a"], "raw_predictions": [prediction], "accepted": True}
        return reference, record

    def test_acoustic_evidence_audit_accepts_raw_mapping_and_rejects_changed_time(self):
        reference, record = self.alignment_evidence()
        audit = prep.audit_covering_alignment(reference, "source_hash", lambda _: record)
        self.assertEqual(audit["dedicated_surface_words"], 1)
        reference["words"][0]["start"] += 0.01
        with self.assertRaisesRegex(ValueError, "does not match"):
            prep.audit_covering_alignment(reference, "source_hash", lambda _: record)

    def test_acoustic_evidence_audit_rejects_wrong_source_and_rejected_prediction(self):
        reference, record = self.alignment_evidence()
        with self.assertRaisesRegex(ValueError, "provenance mismatch"):
            prep.audit_covering_alignment(reference, "wrong_source", lambda _: record)
        record["accepted"] = False
        with self.assertRaisesRegex(ValueError, "Rejected raw prediction"):
            prep.audit_covering_alignment(reference, "source_hash", lambda _: record)

    def test_pronunciation_evidence_audit_requires_complete_acoustic_occupancy(self):
        reference, record = self.alignment_evidence()
        reference["words"][0]["timing_status"] = "ctc_forced_aligned_dictionary_pronunciation"
        record["predictions"] = record["raw_predictions"]
        record["pronunciation_words"] = ["カナ"]
        record["ctc_pronunciation_character_frames"] = [{"start_frame": 1, "end_frame": 2, "mean_probability": 0.4}, {"start_frame": 2, "end_frame": 3, "mean_probability": 0.5}]
        audit = prep.audit_covering_alignment(reference, "source_hash", lambda _: record)
        self.assertEqual(audit["pronunciation_ctc_words"], 1)
        record["ctc_pronunciation_character_frames"].pop()
        with self.assertRaisesRegex(ValueError, "lacks complete"):
            prep.audit_covering_alignment(reference, "source_hash", lambda _: record)

    def test_repeated_raw_units_keep_distinct_actual_prediction_ordinals(self):
        reference, record = self.alignment_evidence()
        template = reference["words"][0]
        reference["words"] = [{"id": 0, "block": 0, "text": "left"}, {**template, "id": 1, "alignment_prediction_index": 1}, {**template, "id": 2, "alignment_prediction_index": 2}, {"id": 3, "block": 0, "text": "right"}]
        record["surface_words"] = ["left", "a", "a", "right"]
        record["raw_predictions"] = [{"text": "left", "start": 0, "end": 0.1}, {"text": "a", "start": 0.1, "end": 0.7}, {"text": "a", "start": 0.1, "end": 0.7}, {"text": "right", "start": 0.8, "end": 1.0}]
        self.assertEqual(prep.audit_covering_alignment(reference, "source_hash", lambda _: record)["dedicated_surface_words"], 2)
        reference["words"][2]["alignment_prediction_index"] = 1
        with self.assertRaisesRegex(ValueError, "ordinal differs"):
            prep.audit_covering_alignment(reference, "source_hash", lambda _: record)

    def test_ambiguous_context_ordinal_is_rejected_not_guessed(self):
        reference = {"words": [{"id": index, "block": 0, "text": "a"} for index in range(3)]}
        with self.assertRaisesRegex(ValueError, "unique actual lexical-context"):
            prediction_unit_index(reference, reference["words"][1], {"surface_words": ["a", "a"]})

    def test_pinned_reading_reproduction_retains_exact_cached_inputs(self):
        record = {"surface_words": ["symbol", "name"], "pronunciation_words": ["カナ", "キクケ"]}
        features = {"symbol": [{"pron": "カ’ナ"}], "name": [{"pron": "キクケ"}]}
        self.assertEqual(audit_cached_readings(record, features.__getitem__), 2)
        features["name"] = [{"pron": "キケク"}]
        with self.assertRaisesRegex(ValueError, "does not reproduce"):
            audit_cached_readings(record, features.__getitem__)

    def test_metadata_guard_rejects_new_private_alignment_content_fields(self):
        for key in ("surface_word", "surface_words", "word_text", "pronunciation", "pronunciation_words", "raw_predictions", "observations"):
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, "Refusing to export"):
                    prep.assert_metadata_only({"nested": {key: ["private"]}})


if __name__ == "__main__":
    unittest.main()
