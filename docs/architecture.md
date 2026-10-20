# Architecture

This repository implements local corpus preparation for issue #2, reusable Windows audio-to-OSC capture infrastructure for issue #3, and the derived measurement/report-data layer for issue #5. Application-specific profile preparation, quality judging, billing and public presentation remain separate outcomes. Capture and metric routines do not imply a completed real-translator pilot or comparison.

## Data flow

1. Language-specific scripts acquire pinned original corpora or identified dataset revisions into ignored `.data/<language>/`.
2. Selection records retain fixed seeds, original sessions, source/channel choices, categories and holdout membership before application results.
3. Rendering produces normalized 48 kHz mono PCM16 waveforms. Reference generation/transformations retain source-to-playback mappings and explicit uncertainty.
4. Per-language manifests identify actual local audio and references with hashes and licenses. Japanese full speech text and timelines stay local because video-specific release rights are unresolved.
5. `tools/index_corpus.py` produces `corpus/manifest.json` from those actual artifacts. `tools/check_corpus.py` checks the index against local files. The index is an integration view, not a second annotation source.
6. `bench` materializes a requested run plan, starts profile-owned adapter subprocesses and keeps an ordered UDP sink active across real-time playback and observation tails.
7. Per-profile SQLite attempts and atomic JSONL finalization retain completed, product-failed and interrupted work. Resume compares effective application state and performs an output check before replaying unfinished work.
8. Raw OSC streams, callback/DAC timing, measured cable correction and separate diagnostics supply downstream metrics. Source grouping/alignment is not inferred by the capture runner.
9. `bench metrics` reads immutable capture artifacts and explicit reference/rule inputs, normalizes source coordinates, and derives separately identified output relationships and source correspondence.
10. Sentence/turn measurements, isolated responses, quality segments and diagnostics feed report-data summaries. Session clustering preserves original recording identity; external quality scores and internal application diagnostics retain separate provenance.

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
| `bench/cli.py`, `bench/plan.py` | Operator commands and frozen run/profile/stage inputs |
| `bench/runner.py`, `bench/storage.py` | Stage orchestration, per-profile durable attempts, failure handling, resume, manifest and status |
| `bench/audio.py` | Shared-mode WASAPI playback, callback/DAC clock mapping and bounded measured cable correction |
| `bench/osc.py` | Ordered raw UDP/OSC capture across chunks and observation tails |
| `bench/adapter.py` | Long-lived subprocess JSON control boundary; application-specific implementations belong to issue #4 |
| `docs/cli.md` | Runner CLI, plan, adapter, raw timing and persistence contracts |
| `bench/metrics_inputs.py` | Native corpus normalization, capture identity/checksums and cable-corrected source-clock mapping |
| `bench/metrics_alignment.py` | Versioned output interpretation, input-bound alignment cache and optional pinned SimAlign |
| `bench/metrics.py` | Timing/delivery, isolated windows, quality-segment assembly and report orchestration |
| `bench/metrics_diagnostics.py`, `bench/metrics_stats.py` | Evidence-gated diagnostics and original-session statistical summaries |
| `docs/metrics.md` | Working calculation definitions, report-data contract and verification limits |
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
- Capture uses `perf_counter_ns` within an explicit clock session; UTC windows serve provider-usage attribution, not latency. Positive cable correction adds capture-path delay to source playback time.
- An event's current chunk is capture context, not source alignment. Continuous streams retain late events after attempt finalization, with earlier playback provenance. Downstream consumers must not interpret a finalized per-attempt trace as the entire future observation window.
- Typing is retained but never translation output. Product failure, operational invalidity and unsupported N/A remain distinct; resume preserves terminal history and marks replayed attempts.
- Adapters own actual application readiness, effective state and startup isolation. A control acknowledgement or synthetic UDP output is not evidence of a configured real translator. No ordinary chunk-boundary application restart is introduced.
- Metrics never overwrite raw capture or native references. Unaligned outputs remain in quality inputs; missing, late, operationally invalid and unsupported evidence are distinct.
- App-dependent revisions/final reconstruction and source CER require applicable evidence. A current capture chunk, typing signal or text similarity alone is not source/finality proof.
- Reference ambiguity reduces the metric claim: partial units and ambiguous containing turns retain explicit reasons and population accounting. Quality context is two preceding reference turns, not scored source.
- Metric reports inherit source-content restrictions, including local-only Japanese speech. Public presentation and main-run freeze are downstream responsibilities.

## Verification boundary

Deterministic tests cover mapping/word boundaries, pause preservation, lexical preservation, CTC paths, overlap, isolated boundaries, safe metadata export and clean-checkout smoke gating. Real preparation commands produced the local waveforms. Source-aligned PCM comparisons and emitted-frame/hash checks support the transformation claims, not independent transcription correctness or listening-based eligibility.

The owner-delegated practical method is recorded in `corpus/practical-assessment.json` and the linked issue decision. It adds bounded inspection of original source content, actual ASR/caption disagreements and ten emitted excerpts; it does not claim human listening or replace timing/utterance correctness checks.

No private account, live translation service, microphone capture, VRChat process or OSC destination is used by routine corpus checks. Public dependency installation may use the normal pip cache; corpus/model payloads remain in `.data/`. Do not delete shared caches as cleanup.

Capture behavior checks use isolated controlled adapters, synthetic WAVs and loopback UDP. Actual Windows shared-mode cable calibration and playback were observed separately. No isolated configured translator was available for the real audio-to-OSC pilot; that observation remains explicitly not run. See `docs/cli.md` for the evidence boundary and operator contract. Application-specific settings and minimal OSCQuery/mute dependencies remain with profile preparation, not speculative runner behavior.

## Release boundary

The owner-approved local-only amendment is linked in `docs/corpus.md`. Local acceptance does not grant redistribution rights or create a retrievable HF revision. Japanese release is held until original-video attribution and permission are resolved. Chinese ShareAlike obligations survive future audio/video adaptation. MIT applies to code/documentation only, not imported or derived corpus content.
