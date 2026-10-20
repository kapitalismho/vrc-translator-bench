# Derived OSC measurements

This is the calculation and report-data layer for [issue #5](https://github.com/kapitalismho/vrc-translator-bench/issues/5). It consumes prepared references from [#2](https://github.com/kapitalismho/vrc-translator-bench/issues/2) and captured endpoint records from [#3](https://github.com/kapitalismho/vrc-translator-bench/issues/3). Application-specific interpretation evidence belongs to [#4](https://github.com/kapitalismho/vrc-translator-bench/issues/4); judging belongs to [#6](https://github.com/kapitalismho/vrc-translator-bench/issues/6). These measurements are not a public scorecard, a semantic-completion detector, or a single overall score.

## Calculation decisions before the main-run freeze

The following are the working calculation definitions. The final input/rule/model revisions must be recorded by the main-run freeze in #8. Implementing a definition does not establish that the corresponding application or alignment evidence is available.

| Measurement | Definition and units |
|---|---|
| Continuous-dialogue observation deadline | Containing reference turn end + 15 seconds; output at the deadline is included |
| Sentence first-output latency (FOL) | First corresponding output received by the deadline minus sentence start, in seconds |
| Sentence last-update latency (LUL) | Last corresponding content-changing output received by the deadline minus sentence end, in seconds |
| Turn LUL | Last related content change received by the turn deadline minus turn end, in seconds |
| Delivery | Reference sentences with determinable corresponding output by the deadline / eligible reference sentences |
| Unaligned-output rate | Observed translation outputs without determinable source correspondence / observed translation outputs; retain the underlying output records and exact denominator |
| Isolated-response window | Utterance start through utterance end + 10 seconds; associate window output without cross-language alignment |
| Isolated-response timing | First response minus utterance start, first response minus utterance end, and last content change minus utterance end, in seconds |
| Quality segment | Approximately 30 seconds, cut only at reference sentence boundaries; **two preceding reference turns** are unscored context |
| FOL duration bins | Source sentence duration <2 seconds, 2–5 seconds inclusive, and >5 seconds |
| Uncertainty | Original-session-clustered 95% bootstrap; paired comparisons use shared reference segments |

Source times are transformed playback times corrected to cable capture. Output times are OSC receipt times. See [capture clock mapping](cli.md#clock-and-endpoint-records). Do not subtract monotonic timestamps from different clock sessions. Do not infer a source assignment from the currently active capture chunk: delayed output can belong to earlier playback.

Negative latency is retained when the observed timing supports it. Missing output has null latency, not an arbitrary timeout latency. LUL means the last observed content update, not proven semantic completion. Resends do not create content changes; revision-dependent measurements require applicable interpretation evidence.

No corresponding output before a deadline, output after the deadline, and output with undetermined correspondence are different observations. An unaligned output is retained and assigned to its nearest temporal quality segment; it is not silently discarded or credited as delivery. Obvious alignment problems must restrict the claim or produce an explicit unknown/N/A reason.

Prepared reference units do not always have a unique containing turn. Retain candidate turn identities and report deadline-dependent values as unknown with `ambiguous_containing_turn` when the reference cannot establish one; do not synthesize a containing turn from a convenient end time. Report affected reference counts and denominator coverage. Partial reference units remain visible but are excluded from complete-reference deadline metrics with `partial_reference`; punctuation-only units are not eligible speech. These policies reduce claims rather than conceal reference uncertainty.

## Interpretation and scoring boundaries

Raw OSC observations remain unchanged. Derived grouping and source alignment are estimates stored separately, with rule/model provenance and uncertainty. OSC does not provide universal translation, revision, page or final IDs. An unsupported final-text reconstruction, revision count, erased-character count, endpoint boundary, or source CER must remain N/A rather than become a heuristic presented as fact.

SimAlign-family alignment is the working cross-language method, not a guarantee of correspondence. Preserve source sentence/turn/original-session identity and reference uncertainty. Cached or inspected links must identify their method and inputs; controlled fixture links do not validate a model. Isolated-response results are a separate test, not continuous-dialogue latency. Retain identifiable late carryover and attach externally supplied quality scores without treating unscored output as correct.

Quality inputs contain target-speaker reference text, unscored earlier-turn context, interpreted final output in display order, and temporally assigned unaligned output. Japanese references remain automatic/exploratory; Japanese CER is automatic-reference guidance, not verified recognition accuracy. Japanese speech-derived report content inherits the local-only release restriction.

Sentence splits and merges describe message segmentation, not translation merit. Boundary loss/duplication, message rate per speaking minute, duplicate/order-change observations, uninterrupted-speech accumulation, endpoint-delay versus mid-sentence-cut pairs, and exploratory Japanese speaker-boundary/pre-predicate diagnostics require their stated evidence. Do not replace speaking time with elapsed audio duration. PuriPuly internal endpoint/ASR/queue/first-token/generation/output timings remain separate from cross-application OSC endpoint measurements.

Count nonspeech output separately for the observed two-minute silence/nonverbal interval and one-minute background-speech interval. Report those observed three-minute counts, never an hourly extrapolation.

## Reporting populations and uncertainty

Keep configuration, direction and category explicit. General, deliberately selected stress, and verified casual-chat-only views are separate. Preserve first-attempt product failures, operational invalidity, unsupported status, retries and resume provenance. Common-success-only comparisons are supplementary, not replacements for the retained-attempt results.

Report p50/p90 latency alongside delivery, unaligned-output rate, first-attempt failures and major-error segment rate. Quality-rate denominators must disclose score coverage. Show original-session values when session count is small. Chopped segments and two target languages using the same audio are not independent recordings. Bootstrap uncertainty excludes reference, alignment and judge bias.

Repeated-subset results expose run-to-run variation; resumed-chunk sensitivity reports summaries with and without resumed chunks. Neither constitutes a validation of the benchmark's statistical or linguistic accuracy.

## Command and inputs

```powershell
python -m bench.cli metrics --manifest .data/runs/pilot/manifest.json --spec metrics-spec.json --output .data/reports/pilot.json
```

`bench metrics` is equivalent. `--alignment-cache cache.json` selects an inspected cache. Without cached correspondence, the optional SimAlign backend uses local model files by default; `--allow-model-download` explicitly permits acquisition. Missing dependencies/model evidence must remain visible in the report rather than trigger a different alignment method.

The specification is JSON with `schema_version: 1` and a nonempty `version`. Paths in the specification resolve against its directory; paths in the capture manifest resolve against the manifest directory. Explicit command-line `--alignment-cache` paths resolve against the working directory and may name an earlier generated report containing `alignment_cache`. Absolute reference paths allow an isolated worktree to use an existing local corpus without copying or regenerating it.

| Specification field | Meaning |
|---|---|
| `rules` | Object keyed by captured configuration ID. Each rule has `version`, nonempty `evidence`, and `style`: `append`, `revision`, `pagination`, or `unknown` |
| `rules[config].text_pattern` | Optional full-message regex with named `translation` and optional `source` groups; distinguishes translated text from exposed source text |
| `rules[config].relationships` | Object keyed by `clock_session:recv_seq`, with `relation` (`new`, `revision`, `pagination`, `resend`, `unknown`) and, for related updates, `parent_id` |
| `rules[config].supports` | Evidence-supported capabilities such as `revision`, `erasure` and `resend`; not a statement that every repeated string is the same utterance |
| `references` | Object keyed by capture stage index as a string; maps stage audio to a prepared reference |
| `references[stage].path`, `pointer` | Native timeline path and optional JSON pointer, such as Chinese `/bundles/main/chunks` or `/isolated_D3/0` |
| `references[stage].units` | Required `samples` or `seconds`; English samples use `sample_rate` (48,000 by default) |
| `references[stage].metadata_path` | Optional native metadata manifest: English `assets` or Japanese `chunks` supply original sessions and category labels |
| `references[stage].session_id`, `source_group`, `category` | Explicit reference identity/population where not supplied by native metadata; original session is not inferred from the capture chunk |
| `references[stage].offset_seconds` | Subtract a known bundle origin exactly once when stage audio is a standalone excerpt; already placed native Chinese/Japanese coordinates must not receive an extra chunk offset |
| `references[stage].clips` | Explicit clip metadata overrides, with native clip identity and original-session/category evidence |
| `alignment` | Backend `simalign` or `cache`; optional cache path or pinned local model snapshot |
| `quality_scores` | Externally supplied scores keyed by generated quality-segment identity; `major_error` is a boolean, with judge provenance retained |
| `isolated_quality_scores` | Externally supplied scores keyed by attempt ID, with scoring provenance |
| `evidence` | Object keyed by output ID, with `provenance`; identifiable boundary records require matching `clock_session` and `boundary.identifiable: true` |
| `nonspeech_intervals` | Object keyed by stage index, with `label`, `start`, `end` in seconds; defaults are [0,120) silence/nonverbal and [120,180) background conversation |
| `common_clips` | Array of `chunk_id`, optional `start`/`end` seconds and selection provenance; the shortlist does not imply the later freeze occurred |
| `puripuly_internal` | Internal timestamp records with their own provenance and clock session, separate from common endpoint metrics |
| `long_speech_min_seconds` | Continuous-speech diagnostic threshold, default 30 seconds |
| `bootstrap` | `iterations` (default 2000) and `seed` (default 20261020) |

A global paging/revision style does not assert that every successive message belongs to one group. Explicit relationships connect only outputs whose association is supported. Retain uncertain observations when that connection cannot be established.

Alignment caches have `schema_version: 1`, `version`, `provenance`, and `links` keyed by output ID. Each link records `status` (`aligned`, `unknown`, `unrelated`), `sentence_ids`, a reason and available token links/confidence. Only aligned entries carry source IDs. IDs for normalized sentences are scoped by attempt and native clip/unit identity; generated IDs remain marked as generated. A required `binding` hashes raw output, interpreted text/relationship/full rule identity, and same-config/clock source IDs, text, times and directions. Use `bench.metrics_alignment.cache_binding(output, sentences)` when preparing inspected links. Stale evidence fails rather than silently transferring to changed inputs. Source links may cross captured chunk/attempt/direction boundaries, but never configuration or clock session.

### Optional model runtime

Install `.[metrics]` in a separate environment. The implemented method uses SimAlign 0.4, multilingual BERT `google-bert/bert-base-multilingual-cased` at revision `3f076fdb1ab68d5b2880cb87a0886f315b8146f8`, layer 8, word-level `itermax`, CPU inference, and the versioned Unicode-word/CJK-character tokenizer. `alignment.model_path` can name that local Hugging Face snapshot directory; `alignment.model_revision` must match. Reports retain model-file hashes and runtime versions.

This method is an estimate, not semantic validation. A real native-library probe produced a questionable `like` → `は` token link. Successful model execution and a pinned revision do not prove source correspondence; inspect representative matches before the main-run freeze.

Automatic source candidates use a disclosed same-clock window: from five seconds before source onset through the containing-turn deadline (or sentence end when unknown) plus 120 seconds. Output outside the window remains unknown. Inputs exceeding 500 model wordpieces remain unknown instead of being silently truncated. This window and tokenization are working method choices to record in the main-run freeze, not validated accuracy thresholds.

## Report-data contract

The output is one JSON object, `schema_version: 1`, calculation `version: "issue5-v1"`. Consumers must inspect `synthetic`, limitations and evidence coverage before presenting a result.

| Output section | Consumer contract |
|---|---|
| `created_utc`, `measurement_date`, `specification_version`, `run` | Generation/date/input-version identity; do not replace measurement date with report-generation date |
| `definitions`, `limitations` | Applied formulas, population policy and unsupported claims |
| `provenance`, `alignment_provenance`, `application_observations`, `harness` | Checksummed input paths, actual model/runtime details, application metadata and capture implementation identity |
| `attempts` | Retained status, first-attempt history, failure reasons and resume provenance |
| `outputs` | Untouched `raw` observation plus derived text/source text, relationship/parent/group, rule evidence, content-change certainty, alignment and quality-segment identity |
| `sentences`, `turns` | Original/generated identity, source session/speaker/category, native reference evidence, uncertainty, candidate turns, timing, delivery and late/unknown output identities |
| `quality_segments` | Approximately 30-second reference units, two unscored earlier turns, final display-order output, unaligned output and externally supplied quality score |
| `isolated` | Separate utterance-window response timing, no-output/timeout, carryover and quality; not continuous-dialogue latency |
| `diagnostics` | Per-attempt segmentation/message measurements, nonspeech counts, common-clip timelines and separately identified PuriPuly internal decomposition |
| `aggregates`, `paired` | Config/direction/category/casual views, original-session values/intervals and shared-segment paired comparisons; common-success comparisons are supplementary |
| `repeats`, `repeat_variation`, `resume_sensitivity` | Repeated-subset observations and summaries with/without resumed chunks |
| `output_population` | Global output denominator and alignment-status accounting, including orphan output |
| `alignment_cache` | Input-bound reusable correspondence evidence, not a new raw observation |

Measurement objects carry `value`, `unit`, `reason` and relevant denominator/evidence fields. Unavailable values are JSON `null`, never NaN or a fabricated zero. Playback `start`/`end` are seconds; `native_coordinate_units` and `offset_seconds` preserve normalization provenance. `*_ns` values are nanoseconds within the named clock session, not UTC timestamps.

Product-failed attempts remain in the measurement population when reference/timing evidence exists. Operational-invalid, unsupported, partial-reference, nonlexical/unscored, ambiguous-containing-turn and unavailable-source-timing records remain in the report with reasons and denominator-coverage counts. Unknown correspondence stays in eligible delivery denominators, with `unresolved_sentences` and correspondence bounds. Quality eligibility is distinct from deadline/turn eligibility.

Unaligned-rate denominators include all observed translation outputs in the declared global or source population, including resends, late and orphan output. Outputs known to be unrelated also lack a linked source; `alignment_status_counts` keeps them distinct from unresolved correspondence. Known-unrelated output does not turn a sentence's no-output result into unknown. Source-population denominators can be smaller than the global denominator; never omit that distinction.

First-attempt product-failure rates exclude operational-invalid and unsupported first attempts from their product-failure denominator but preserve all first-attempt status counts. Missing quality scores are unscored, not zero-error judgments. Reports expose session-level values; fewer than two original sessions yields no bootstrap interval. Paired comparisons match shared reference segments rather than treating each target language as a new recording.

### Diagnostic evidence

Identifiable boundary evidence may carry `source_boundary_ns`, `sentence_end_ns`, `predicate_end_ns`, `source_speakers`/`speaker_crossing`, and `expected_source_unit_ids`/`delivered_source_unit_ids`. Endpoint-delay versus cut pairs use OSC receipt minus the corresponding source boundary and preserve whether the cut precedes sentence end. Boundary loss and duplication compare expected/delivered unit identities; absent identity evidence is N/A.

Source CER is Levenshtein distance divided by reference Unicode code points, without punctuation/whitespace normalization. It requires an app-exposed source field and source correspondence; Japanese remains automatic-reference guidance. Supported erased-character measurement uses previous Unicode code-point length minus longest-common-subsequence length. Splitting/merging counts alone imply no quality preference.

Internal PuriPuly records may contain `speech_end_ns`, `endpoint_ns`, `asr_start_ns`, `asr_end_ns`, `queued_ns`, `generation_start_ns`, `first_token_ns`, `generation_end_ns`, and `output_ns`. Missing pairs remain N/A. These do not replace OSC receipt latency.

## Hand-worked boundaries and observed checks

With DAC origin 10.0 seconds and cable correction +0.1 seconds, source origin is 10.1 seconds. A sentence at playback [0,2] has source bounds [10.1,12.1]. If its containing turn ends at playback 4, the deadline is 29.1. Related content-changing outputs at 11 and 12 give FOL **0.9 seconds** and LUL **−0.1 seconds**. Output exactly at 29.1 is on time; 29.100000001 is late. Missing output has null latency. Unresolved output remains in the quality input rather than proving delivery or disappearing.

Executed checks on the implementation candidate:

- Focused behavior suite: 24 tests passed, no skips. Covers exact/late deadlines, negative LUL, unknown/no-output separation, failed/resumed attempts, grouping, unaligned quality assignment, isolated carryover, diagnostics, aggregation and stale-cache rejection.
- Repository integration: 130 tests and 29 subtests passed; four existing Chinese real-audio tests skipped because this worktree lacks their `.data/chinese/audio/zh-main.wav`. Shared local corpus metadata was used by the focused checks; no missing audio was fabricated.
- CLI with an actual prepared English reference and explicitly synthetic OSC/playback/cached correspondence produced FOL 0.4 seconds, LUL 0.16 seconds, one delivered sentence and a null one-session interval.
- Actual Japanese local timeline normalization retained 656 sentences, 333 turns and three original sessions. Strict turn evidence marked 181 units ambiguous rather than inventing deadlines. No Japanese speech text was published.
- Retained PuriPuly 2.8.2 manual-text UDP probes produced four output records and two orphan quality segments. The known page link was retained, an earlier standalone prefix was not erased, and repeated text after restart was not called a resend. All correspondence remained unknown because these probes have no source playback. Typing false preceded the last observed page and was not used as a finality marker.
- Real pinned CPU SimAlign through the actual CLI produced FOL 1.5 seconds and LUL −0.5 seconds on a tiny synthetic bilingual fixture. A late output and a different-clock orphan were retained; global unaligned rate was 1/3. This verifies execution/provenance/arithmetic, not alignment accuracy or real translation.

Development checks found and repaired an orphan-only quality-assignment crash and an explicit relative cache-path resolution error; focused regression checks retain these boundaries. Local observations and controlled inputs are under `.data/issue5-worker-final/`, `.data/issue5-director/`, and `.data/issue5-alignment/`; those local paths are not published datasets.

**Remaining empirical prerequisite:** #4 has not supplied different applications' actual microphone-to-translated-OSC examples and observed interpretation rules. The available PuriPuly manual-text probe does not satisfy that criterion. Synthetic append/revision/pagination fixtures exercise calculations but cannot establish real-app readiness or translation timing. Issue #5 must not be closed as fully empirically verified on that basis. No human listening, independent semantic-accuracy study, live provider call or public result publication is claimed.
