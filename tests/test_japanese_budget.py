from __future__ import annotations

import unittest

from tools.japanese_budget import RATE, choose_trim_plan, crop_units, safe_crop_choices


class JapaneseBudgetTests(unittest.TestCase):
    def reference(self):
        return {
            "audio_duration_seconds": 180,
            "words": [
                {"id": 0, "block": 0, "char_start": 0, "char_end": 1, "text": "a", "start": 0.5, "end": 1.0},
                {"id": 1, "block": 0, "char_start": 1, "char_end": 2, "text": "b", "start": 177.0, "end": 177.5},
            ],
            "blocks": [{"id": 0, "start": 0, "end": 180, "text": "ab", "alignment_status": "ctc_viterbi_complete"}],
            "turns": [{"start": 0.5, "end": 1, "speaker": "a"}, {"start": 177, "end": 177.5, "speaker": "a"}],
        }

    def test_category_budget_is_exact_and_boundaries_avoid_words_and_voice(self):
        references = [self.reference() for _ in range(6)]
        plans = choose_trim_plan(references, 12)
        self.assertEqual(sum(plan["trim_samples"] for plan in plans), 12 * RATE)
        self.assertEqual(sum(plan["duration_samples"] for plan in plans), (1080 - 12) * RATE)
        for reference, plan in zip(references, plans):
            self.assertTrue(any(choice["side"] == plan["side"] and choice["minimum"] <= plan["trim_samples"] <= choice["maximum"] for choice in safe_crop_choices(reference, 12 * RATE)))
            result = crop_units(reference, plan["start_sample"], plan["end_sample"])
            self.assertEqual("".join(word["text"] for word in result["words"]), "ab")
            self.assertTrue(all(0 <= word["start"] < word["end"] <= plan["duration_samples"] / RATE for word in result["words"]))

    def test_crop_rejects_word_cut_and_projects_complete_words(self):
        reference = self.reference()
        with self.assertRaises(ValueError):
            crop_units(reference, 0, round(177.25 * RATE))
        result = crop_units(reference, 2 * RATE, 180 * RATE)
        self.assertEqual([word["text"] for word in result["words"]], ["b"])
        self.assertEqual(result["words"][0]["start"], 175)
        self.assertEqual(result["words"][0]["id"], 0)
        self.assertEqual(result["blocks"][0]["text"], "b")

    def test_untimed_block_is_not_partially_cut_to_make_budget(self):
        reference = self.reference()
        reference["words"].append({"id": 2, "block": 1, "char_start": 0, "char_end": 1, "text": "?", "start": None, "end": None})
        reference["blocks"].append({"id": 1, "start": 175, "end": 180, "text": "?", "alignment_status": "ctc_viterbi_with_unsupported_wildcards"})
        with self.assertRaises(ValueError):
            crop_units(reference, 0, 178 * RATE)
        choices = safe_crop_choices(reference, 2 * RATE)
        self.assertFalse(any(choice["side"] == "right" and choice["minimum"] <= 2 * RATE <= choice["maximum"] for choice in choices))

    def test_no_silent_boundary_is_an_explicit_failure_not_word_truncation(self):
        reference = self.reference()
        reference["turns"] = [{"start": 0, "end": 180, "speaker": "a"}]
        with self.assertRaisesRegex(ValueError, "without cutting"):
            choose_trim_plan([reference], 2)


if __name__ == "__main__":
    unittest.main()
