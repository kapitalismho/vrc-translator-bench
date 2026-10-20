# Architecture

This repository began without committed implementation. Its current boundary is local corpus preparation for issue #2. No application runner, OSC capture, scoring, billing or public presentation implementation is implied.

## Data flow

1. Language-specific scripts acquire pinned original corpora or identified dataset revisions into ignored `.data/<language>/`.
2. Selection records retain fixed seeds, original sessions, source/channel choices, categories and holdout membership before application results.
3. Rendering produces normalized 48 kHz mono PCM16 waveforms. Reference generation/transformations retain source-to-playback mappings and explicit uncertainty.
4. Per-language manifests identify actual local audio and references with hashes and licenses. Japanese full speech text and timelines stay local because video-specific release rights are unresolved.
5. `tools/index_corpus.py` produces `corpus/manifest.json` from those actual artifacts. `tools/check_corpus.py` checks the index against local files. The index is an integration view, not a second annotation source.

## Owned surfaces

| Surface | Responsibility |
|---|---|
| `tools/prepare_english.py` | AMI acquisition/selection, headset transformation, manual-DA reference mapping, isolated/repeat/common selections, artifact checks |
| `tools/prepare_chinese.py` | Original AliMeeting Eval acquisition, headset selection, human-text forced alignment, transformed references and local checksums |
| `tools/prepare_japanese.py` | Pinned YODAS2 acquisition, selection/rendering, local orchestration, heldout clips, checks and public-safe metadata export |
| `tools/japanese_reference.py` | Actual independent automatic ASR, acoustic alignment, estimated speakers and insertion-only punctuation |
| `tools/japanese_budget.py` | Word/voice-safe source trimming and remapping to exact elapsed budgets |
| `tools/japanese_alignment.py`, `tools/japanese_pronunciation.py` | Covering raw dedicated-model and dictionary-pronunciation CTC timing for retained unsupported words; source/hash/prediction audits |
| `tools/prepare_nonspeech.py` | Recorded keyboard/nonverbal assets, separate background conversation and two scoring intervals |
| `tools/index_corpus.py`, `tools/check_corpus.py` | Six-direction reuse index, actual file/hash/frame checks and D1 repeat identity |
| `corpus/` | Permitted selection, reference, provenance, license and checksum records; no audio |
| `.data/` | Local source/audio/models/environments and unresolved Japanese derived content; never staged for Git |

Language-specific preparation remains explicit because the sources have materially different annotations and rights. There is no generic corpus-provider framework. Heavy model dependencies are isolated from the lightweight integration/test environment.

## Consumer contracts

- Direction `source_group` is one of `en`, `zh`, `ja`; D1/D2, D3/D5 and D4/D6 each share the group's exact main audio object. Six directions represent only three independent source tracks.
- Each main track is exactly 1,800 elapsed seconds: general 1,200 and stress 600 with disclosed two-second-separator allocation. Development is separately 300 seconds per source group. Speaking time, original source span and elapsed playback are different quantities.
- Root audio records use integer `frames` at 48 kHz and `duration_seconds`. File paths are repository-relative local paths, not release URLs.
- Corpus metadata is checksummed as file bytes. `.gitattributes` disables Git newline conversion under `corpus/`, preserving the measured bytes in commits and fresh checkouts. Regenerating metadata requires rebuilding the root index; do not normalize or reformat hashed references independently.
- English reference coordinates are **integer 48 kHz samples**. Chinese and Japanese reference coordinates are **seconds**. Use each group's `timeline_units`; never infer units from a generic `start` field.
- English DA units, Chinese punctuation-completed units and Japanese automatic sentence-like units retain their different evidence levels. Do not present them as uniformly human-verified sentences.
- Japanese word IDs are local to a chunk. Join with `(chunk_id, word_id)`. Final preparation rejects missing/nonfinite word or sentence bounds, while low acoustic scores, overlapping model estimates and dictionary-reading uncertainty remain explicit. Numeric timing completeness does not establish accuracy; estimated speaker labels are not person identities.
- Original session identities, selected-speaker scoring and unscored earlier context stay in language manifests. Session clustering cannot treat chopped clips or target-language reuse as independent recordings.
- General and deliberate stress populations remain separate. Common shortlists precede results; the full comparison freeze is not performed by this preparation code.

## Verification boundary

Deterministic tests cover mapping/word boundaries, pause preservation, lexical preservation, CTC paths, overlap, isolated boundaries, safe metadata export and clean-checkout smoke gating. Real preparation commands produced the local waveforms. Source-aligned PCM comparisons and emitted-frame/hash checks support the transformation claims, not independent transcription correctness or listening-based eligibility.

The owner-delegated practical method is recorded in `corpus/practical-assessment.json` and the linked issue decision. It adds bounded inspection of original source content, actual ASR/caption disagreements and ten emitted excerpts; it does not claim human listening or replace timing/utterance correctness checks.

No private account, live translation service, microphone capture, VRChat process or OSC destination is used by routine corpus checks. Public dependency installation may use the normal pip cache; corpus/model payloads remain in `.data/`. Do not delete shared caches as cleanup.

## Release boundary

The owner-approved local-only amendment is linked in `docs/corpus.md`. Local acceptance does not grant redistribution rights or create a retrievable HF revision. Japanese release is held until original-video attribution and permission are resolved. Chinese ShareAlike obligations survive future audio/video adaptation. MIT applies to code/documentation only, not imported or derived corpus content.
