from __future__ import annotations

import hashlib
import json
from pathlib import Path
import wave

ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def file_record(path: str) -> dict:
    with (ROOT / path).open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": path, "sha256": digest}


def audio_record(path: str, expected: str) -> dict:
    record = file_record(path)
    if record["sha256"] != expected:
        raise ValueError(f"Language manifest audio hash mismatch: {path}")
    with wave.open(str(ROOT / path), "rb") as stream:
        if stream.getnchannels() != 1 or stream.getframerate() != 48000 or stream.getsampwidth() != 2:
            raise ValueError(f"Not normalized mono PCM16 48 kHz: {path}")
        record.update(frames=stream.getnframes(), duration_seconds=stream.getnframes() / 48000)
    return record


def build() -> dict:
    english_path = "corpus/english/manifest.json"
    chinese_path = "corpus/chinese/manifest.json"
    japanese_path = "corpus/japanese/local-preparation.json"
    en, zh, ja = load(english_path), load(chinese_path), load(japanese_path)
    english_bundles = {item["id"]: item for item in en["bundles"]}
    def en_audio(item):
        return audio_record(item["audio_path"], item["audio_sha256"])
    def zh_audio(item):
        return audio_record(item["audio"], item["sha256"])
    def ja_audio(item):
        return audio_record(item["local_audio_path"], item["audio_sha256"])
    groups = {
        "en": {
            "manifest": file_record(english_path),
            "main": en_audio(english_bundles["main"]),
            "development": en_audio(english_bundles["development"]),
            "isolated": [en_audio(item) for item in en["assets"] if item["id"].startswith("isolated-")],
            "reference_level": "Human transcript/manual dialogue acts; automatic corpus word alignment",
            "timeline_units": "Integer samples at 48000 Hz, including source coordinates",
            "main_timeline": file_record(english_bundles["main"]["timeline_path"]),
            "category_seconds_including_separators": {"general": en["duration_accounting"]["general_total_seconds"], "stress": en["duration_accounting"]["stress_total_seconds"]},
            "common_shortlist": "corpus/english/common-shortlist.json",
            "casual_chat": en["casual_chat"],
            "original_sessions_and_channels": "corpus/english/manifest.json#/assets",
            "license": "CC-BY-4.0",
        },
        "zh": {
            "manifest": file_record(chinese_path),
            "main": zh_audio(zh["bundles"]["main"]),
            "development": zh_audio(zh["bundles"]["dev"]),
            "isolated": [audio_record(item["audio"]["path"], item["audio"]["sha256"]) for item in zh["isolated_D3"]],
            "reference_level": "Human lexical transcript/speaker labels; automatic forced word alignment and punctuation completion",
            "timeline_units": "Seconds relative to containing playback bundle; source seconds retained",
            "main_timeline": file_record(chinese_path),
            "main_timeline_pointer": "/bundles/main/chunks",
            "category_seconds_including_separators": {"general": zh["category_totals"]["general_playback_seconds_including_following_separators"], "stress": zh["category_totals"]["stress_playback_seconds_including_internal_separators"]},
            "common_shortlist": zh["common_clip_shortlist"],
            "casual_chat": {"verified_general_fraction": zh["category_totals"]["casual_general_audio_proportion"], "basis": "Conservative verified-unprompted definition; prompted everyday discussion is not certified casual"},
            "original_sessions_and_channels": "corpus/chinese/manifest.json#/bundles/main/chunks",
            "license": "CC-BY-SA-4.0",
        },
        "ja": {
            "manifest": file_record(japanese_path),
            "main": ja_audio(ja["playback_assets"]["main"]),
            "development": ja_audio(ja["playback_assets"]["dev"]),
            "isolated": [audio_record(item["audio"]["path"], item["audio"]["sha256"]) for item in ja["heldout"]["entries"]],
            "reference_level": "Automatic and exploratory; estimated speakers and genuine acoustic word intervals with uncalibrated/low-score and dictionary-reading uncertainty",
            "timeline_units": "Seconds relative to containing playback bundle; join word IDs with chunk_id; preparation rejects missing word or sentence bounds",
            "main_timeline": file_record(ja["playback_assets"]["main"]["local_timeline_path"]),
            "timing_completion": ja["alignment_completion"],
            "category_seconds_including_separators": {"general": ja["general_elapsed_seconds"], "stress": ja["stress_elapsed_seconds"]},
            "common_shortlist": ja["common_clip_shortlist"],
            "casual_chat": {"actual_fraction": ja.get("actual_casual_chat_fraction"), "caption_tag_fraction": ja.get("caption_tag_casual_chat_fraction_of_general_candidates"), "basis": "Caption-assisted candidate classification; not human-confirmed eligibility"},
            "original_sessions_and_channels": "corpus/japanese/local-preparation.json#/chunks",
            "license": "Dataset-declared CC-BY-3.0; original-video attribution/permission unresolved; NOT release cleared",
            "publication": "Full Japanese speech text, references and audio are local only",
        },
    }
    nonspeech = load("corpus/nonspeech/manifest.json")
    return {
        "schema_version": 1,
        "local_revision": "issue-2-local-v1",
        "status": "local_preparation_not_public_dataset_or_main_run_freeze",
        "authority": "https://github.com/kapitalismho/vrc-translator-bench/issues/2#issuecomment-6282606626",
        "publication": {"hugging_face_repository": None, "hugging_face_revision": None, "authorized": False,
                        "scope": "Owner replaced HF publication criterion with local artifacts and rights/unresolved records; no public retrievability claimed"},
        "directions": [{"id": key, "source_group": source, "target_language": target} for key, source, target in
                       [("D1", "en", "ja"), ("D2", "en", "zh"), ("D3", "zh", "ko"), ("D4", "ja", "ko"), ("D5", "zh", "ja"), ("D6", "ja", "en")]],
        "source_groups": groups,
        "supplementary": {"D1_repeat": en_audio(en["repeat"]), "nonspeech": audio_record(nonspeech["audio"]["path"], nonspeech["audio"]["sha256"]),
                          "nonspeech_manifest": file_record("corpus/nonspeech/manifest.json")},
        "interpretation": ["Shared target-language directions are not independent source evidence.",
                           "General and deliberately selected stress are separate populations; do not combine into representative ranking.",
                           "Category budgets include disclosed interchunk silence; they are not speaking-time denominators.",
                           "Normalization policy and timing uncertainty are source-specific and documented, not a claim of equal recording conditions.",
                           "No human listening, independent transcription-validation study or main application comparison is claimed.",
                           "Common shortlists precede results; the integrated main-run freeze belongs to issue #8."],
    }


def main() -> None:
    index = build()
    from tools.check_corpus import check
    result = check(index)
    (ROOT / "corpus/manifest.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
