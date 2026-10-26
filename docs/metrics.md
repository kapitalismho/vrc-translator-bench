# Historical OSC measurements

> **Retired evaluation contract.** `bench metrics`, `metrics-batch`, all `bench/metrics*.py` modules and their old alignment dependencies have been removed. Definitions, commands and observations below explain retained historical artifacts at [the pre-reset revision](https://github.com/kapitalismho/vrc-translator-bench/tree/fbab10a0455d91d5419d9673499d25b7ac86c566); they are not active instructions or accepted new-benchmark results. The old analysis remains under an integrity hold. Episode quality and separate weighted semantic-wait p50/p90 are specified in [the final plan §§7–10](benchmark-final-plan.md) and remain [implementation work](benchmark-implementation-plan.md). No old delivery/FOL/LUL field is a new metric alias.

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
| Unaligned-output rate | Role-confirmed translation outputs without determinable source correspondence / role-confirmed translation outputs; retain raw observations and unresolved-role coverage separately |
| Isolated-response window | Utterance start through utterance end + 10 seconds; associate role-confirmed translation within the window without cross-language alignment, retaining unresolved-role activity separately |
| Isolated-response timing | First response minus utterance start, first response minus utterance end, and last content change minus utterance end, in seconds |
| Quality segment | Approximately 30 seconds, cut only at reference sentence boundaries; **two preceding reference turns** are unscored context |
| FOL duration bins | Source sentence duration <2 seconds, 2–5 seconds inclusive, and >5 seconds |
| Uncertainty | Original-session-clustered 95% bootstrap; paired comparisons use shared reference segments |

Source times are transformed playback times corrected to cable capture. Output times are OSC receipt times. See [capture clock mapping](cli.md#clock-and-endpoint-records). Do not subtract monotonic timestamps from different clock sessions. Do not infer a source assignment from the currently active capture chunk: delayed output can belong to earlier playback.

Sample-native reference boundaries retain exact native-sample, sample-rate and excerpt-offset arithmetic through callback selection and nanosecond rounding. Public playback-second fields remain floating-point values, but those rounded values are not converted back to frames for sample-native clock mapping. At a shared callback boundary, use the later callback's observed DAC timestamp. Seconds-native references retain their fractional-second timing without blanket sample rounding.

Negative latency is retained when the observed timing supports it. Missing output has null latency, not an arbitrary timeout latency. LUL means the last observed content update, not proven semantic completion. Resends do not create content changes; revision-dependent measurements require applicable interpretation evidence.

No corresponding output before a deadline, output after the deadline, and output with undetermined correspondence are different observations. A role-confirmed translation with unknown correspondence is retained and assigned to its nearest temporal quality segment; it is not silently discarded or credited as delivery. Unresolved text role follows the separate exclusion boundary below. Obvious alignment problems must restrict the claim or produce an explicit unknown/N/A reason.

Prepared reference units do not always have a unique containing turn. Retain candidate turn identities and report deadline-dependent values as unknown with `ambiguous_containing_turn` when the reference cannot establish one; do not synthesize a containing turn from a convenient end time. Report affected reference counts and denominator coverage. Partial reference units remain visible but are excluded from complete-reference deadline metrics with `partial_reference`; punctuation-only units are not eligible speech. These policies reduce claims rather than conceal reference uncertainty.

## Interpretation and scoring boundaries

Raw OSC observations remain unchanged. Derived grouping and source alignment are estimates stored separately, with rule/model provenance and uncertainty. OSC does not provide universal translation, revision, page or final IDs. An unsupported final-text reconstruction, revision count, erased-character count, endpoint boundary, or source CER must remain N/A rather than become a heuristic presented as fact.

A frozen extraction-pattern mismatch has `output_role: "unresolved"`, `text: null`, `source_text: null` and `extraction: "pattern_mismatch_unresolved_role"`. Preserve the complete raw packet and rule provenance; do not fall back to treating mixed source/target text as translation. Existing source/time candidates preserve possible-delivery uncertainty but cannot grant model/cache alignment, CER, grouping or final-output credit. Such a row cannot serve as a revision/pagination/resend parent. Two null interpreted texts do not establish duplicate translated content.

All affected candidate quality segments retain `unresolved_output_ids` and become ineligible with `quality_eligibility_reason: "unresolved_output_role"`. This is unavailable extraction, not an empty translation or an omission judgment. Known empty extracted translation remains a separate `source_only` observation; matched nonempty translation remains usable even with an empty recognized-source field. Isolated unresolved-only activity reports `unknown_output_role`, not a false no-output timeout. Nonspeech retains raw endpoint activity separately from known translated counts. Common-clip replay uses retained `raw_text`, not null interpreted text.

When source bounds are unavailable, unresolved activity also excludes untimed reference-bearing quality segments from its exact captured attempt/frozen-stage population, matching configuration, clock, direction and capture kind. `untimed_capture_quality_segment_ids` records this conservative exclusion coverage, not sentence correspondence. Timed allocation and orphan observations remain intact; this does not invent cross-attempt untimed carryover or alter missing-timing behavior when no unresolved role was observed.

SimAlign-family alignment is the working cross-language proposal method, not proof of correspondence. Its maximum matching also produces links for unrelated text. Model proposals therefore retain token links and candidate identities but stay `unknown` for delivery until inspected, input-bound correspondence evidence supports a source assignment. This prevents forced token matches from becoming falsely delivered sentences. Isolated-response results use window association instead and remain a separate test.

Quality inputs contain target-speaker reference text, unscored earlier-turn context, interpreted final output in display order, and temporally assigned role-confirmed translations with unknown correspondence. Unresolved-role text is not a scoring input. Japanese references remain automatic/exploratory; Japanese CER is automatic-reference guidance, not verified recognition accuracy. Japanese speech-derived report content inherits the local-only release restriction.

Sentence splits and merges describe message segmentation, not translation merit. Boundary loss/duplication, message rate per speaking minute, duplicate/order-change observations, uninterrupted-speech accumulation, endpoint-delay versus mid-sentence-cut pairs, and exploratory Japanese speaker-boundary/pre-predicate diagnostics require their stated evidence. Do not replace speaking time with elapsed audio duration. PuriPuly internal endpoint/ASR/queue/first-token/generation/output timings remain separate from cross-application OSC endpoint measurements.

Count nonspeech output separately for the observed two-minute silence/nonverbal interval and one-minute background-speech interval. Report those observed three-minute counts, never an hourly extrapolation.

The optional observed pre-nonspeech quiet gate is described in the
[runner contract](cli.md#plan-contract). Its delayed output is retained in
`quiet_precondition_observations`, outside measured translation/alignment,
quality, nonspeech and global output denominators. Each nonspeech diagnostic
retains the complete `nonspeech_quiet_wait` evidence and the
`quiet_precondition_met` / `unresolved_carryover` flags.

`count` remains the raw observed interval count. `clean_nonspeech_count` is
available only when quiet was actually established and playback timing is
available. Timeout leaves clean attribution null with a carryover reason,
without discarding the actual three-minute playback or fabricating a zero.
Historical captures without the gate retain their observed counts; their quiet
precondition and clean attribution are unknown, not retrospectively certified.

## Reporting populations and uncertainty

Keep configuration, direction and category explicit. General, deliberately selected stress, and verified casual-chat-only views are separate. Preserve first-attempt product failures, operational invalidity, unsupported status, retries and resume provenance. Common-success-only comparisons are supplementary, not replacements for the retained-attempt results.

Report p50/p90 latency alongside delivery, unaligned-output rate, first-attempt failures and major-error segment rate. Quality-rate denominators must disclose score coverage. Show original-session values when session count is small. Chopped segments and two target languages using the same audio are not independent recordings. Bootstrap uncertainty excludes reference, alignment and judge bias.

Repeated-subset results expose run-to-run variation; resumed-chunk sensitivity reports summaries with and without resumed chunks. Neither constitutes a validation of the benchmark's statistical or linguistic accuracy.

### Cross-wave paired composition

Use actual retained wave/direction reports, then the joined quality report after scoring:

```powershell
python -m bench.cli metrics-batch --report wave1-d1.json --report wave2-d1.json --output batch-paired.json
python -m bench.cli metrics-batch --quality-report batch-quality.json --output batch-scored-paired.json
```

Repeat `--report` for every retained canonical metrics report. `--quality-report` consumes `joined_metrics_reports`; do not also supply original reports already represented there. Composition performs no capture, judging, inference or provider calls.

The batch envelope preserves each source report unchanged, including category/casual, turn, output, repeat, resume and failure summaries, with input/source hashes, run IDs and joined-report JSON pointers. Only paired estimates combine reports, using the existing estimator and narrowly projected, run/config/direction/attempt-scoped inputs. Shared reference and original-session identities remain unchanged; report percentiles are never averaged.

Any duplicate reference-eligible chunk/shared population is rejected, including duplicates within one report or successful retries after failures. Diagnostics identify the source/run/attempt; resolve the actual canonical population without silently selecting a successful retry or erasing failure evidence. Shared source identity, text and original session must agree; output-specific quality eligibility may differ.


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

`bench quality` consumes these report segments and emits joined reports; see [quality scoring](quality.md). It retains missing scores, source eligibility and judge provenance rather than assigning missing-as-zero.

A global paging/revision style does not assert that every successive message belongs to one group. Explicit relationships connect only outputs whose association is supported. Retain uncertain observations when that connection cannot be established.

Alignment caches have `schema_version: 1`, `version`, `provenance`, and `links` keyed by output ID. Each link records `status` (`aligned`, `unknown`, `unrelated`), `sentence_ids`, a reason and available token links/confidence. Only aligned entries carry source IDs. IDs for normalized sentences are scoped by attempt and native clip/unit identity; generated IDs remain marked as generated. A required `binding` hashes raw output, interpreted text/relationship/full rule identity, and same-config/clock source IDs, text, times and directions. Use `bench.metrics_alignment.cache_binding(output, sentences)` when preparing inspected links. Stale evidence fails rather than silently transferring to changed inputs. Source links may cross captured chunk/attempt/direction boundaries, but never configuration or clock session.

An `aligned` cache entry additionally requires `adjudication: {"decision": "confirmed", "method": "...", "evidence": ["..."]}`. Record the actual method and evidence, for example assistant inspection of the exact bilingual pair or synthetic fixture ground truth; never claim human validation that did not occur. Keep the original proposal/token evidence and binding when recording a decision. A prior automatically aligned report without adjudication is rejected, not silently promoted to inspected evidence.

### Optional model runtime

Install `.[alignment]` in a separate environment (`python -m pip install -e ".[alignment]"`). The implemented method uses SimAlign 0.4, multilingual BERT `google-bert/bert-base-multilingual-cased` at revision `3f076fdb1ab68d5b2880cb87a0886f315b8146f8`, layer 8, word-level `itermax`, CPU inference, and the versioned Unicode-word/CJK-character tokenizer. `alignment.model_path` can name that local Hugging Face snapshot directory; `alignment.model_revision` must match. Reports retain model-file hashes and runtime versions.

This method is an estimate, not semantic validation. A real native-library probe produced a questionable `like` → `は` token link; independent review also observed unrelated or competing source sentences receiving links. The model now generates explicit lexical proposals rather than definitive delivery credit. Retain `proposed_sentence_ids`, token links, rejected support and ambiguity reasons; do not treat a useful proposal as a confirmed source match.

Inspect proposals against the retained source/output evidence, record the correspondence decision and provenance in the exported bound cache, then rerun with `--alignment-cache`. Confirmed cache links supply sentence timing/delivery; unresolved entries retain null latency and remain in delivery coverage. This is an executable proposal-and-adjudication workflow, not an automatic semantic-accuracy claim or a new calibration-study gate.

Same-clock candidate search retains late-output possibilities through the containing-turn deadline (or sentence end when unknown) plus 120 seconds. Punctuation-only and future-source support do not establish a model proposal. Inputs exceeding 500 model wordpieces remain unknown instead of being silently truncated. These working method choices must be recorded at the main-run freeze.

## Optional analysis applicability

Collection completion does not establish runtime-route identity. A retained `done`
chunk may contain mixed routes while its source, raw output and failure incidents
remain valid observations. Derive a **new report** with an explicit population gate:

```powershell
python -m bench.cli metrics --manifest native-manifest.json --spec frozen-metrics-spec.json --applicability index-applicability.json --output index-primary.json
```

The Python entry point is `bench.metrics.derive(..., applicability_path=...)`.
Omitting the optional input retains existing behavior; profile names, failures and
current settings never automatically infer an exclusion.

The input has exactly these top-level fields:

| Field | Contract |
| --- | --- |
| `schema_version`, `version` | `1`, `"analysis-applicability-v1"` |
| `population` | Nonempty analysis-population name |
| `manifest_sha256`, `spec_sha256` | Exact original native manifest and metrics-spec hashes |
| `exclusions` | Nonempty array of whole-attempt exclusions |

Each exclusion has exactly `run`, `config`, `direction`, integer `attempt_id`,
integer `stage`, nonempty `reason` and nonempty `evidence`. The complete native
selector must identify one unambiguous reference-bearing `chunk` or `repeat`;
`stage` is the zero-based plan index, not a quality-segment number. Missing,
nonexistent, mismatched, duplicate or ambiguous selectors fail. There are no
wildcards, retry promotion or within-chunk splits. Reference-free and isolated
windows are outside this input's scope.

Each evidence item has exactly `path` and `sha256`; relative paths resolve beside
the applicability file. Missing or changed evidence and stale manifest/spec hashes
fail. Record the authorized decision, observed events and attribution limits in
the evidence. Hash binding does not authenticate authors or prove provider success,
cause, actor, output-to-provider correspondence or billable usage.

Original manifest/spec provenance remains intact; the report appends applicability
and evidence hashes. Its `applicability` section retains the decision and excluded
attempt/sentence/turn/segment counts. Native files, collection outcomes, references,
raw packets and known failures are not rewritten. Output cannot overwrite bound
inputs. The analysis hash is not a new capture identity.

Directly excluded attempts, source rows and captured outputs carry
`population_eligible: false` and `applicability.exclusion_kind: "direct"`.
An output's confirmed SOURCE correspondence is preserved; it does not establish
the provider that produced that output. Directly mixed origins cannot supply
pure-route delivery, timing, output-rate or quality credit through a clean source
attempt or through an unaligned quality-segment display placement.

Dependent source, turn, quality and relevant first-attempt populations become
ineligible with `applicability.exclusion_kind: "dependent"`, reason
`excluded_capture_output_dependency`, `dependent_output_ids` and the original
hash-bound `origin_exclusions`. Unknown correspondence/display allocation retains
uncertainty over the affected reference population. Confirmed correspondence
limits source dependency to its confirmed sources rather than all old candidates.
The existing isolated-window consumer also excludes a window containing a
directly mixed origin; isolated attempts remain unavailable as direct selectors.
Dependency propagation is seeded only by explicitly selected capture origins:
otherwise clean output origins do not become mixed merely because their source
attempt becomes dependency-excluded, and independent dependent-free sources
remain usable.

Sentence/turn/quality rows preserve previous eligibility/reasons (and quality
timing eligibility), then become ineligible. `analysis_applicability_excluded`
is the default direct reason; an existing extraction/reference reason survives.
Quality `reference_eligible` remains the native reference/status judgment.
Original delivery status, FOL/LUL, source links, text, incidents and supplied scores
remain excluded diagnostic evidence. Do not rewrite an affected source as a
missing-output failure or recalculate favorable timings from only trusted output.

Aggregation excludes affected rows from delivery/latency, turn LUL, session
bootstrap, source-population output rates, quality and first-attempt denominators.
The report distinguishes `direct_excluded_counts`, `dependent_excluded_counts`,
total `excluded_counts` and directly mixed `excluded_output_ids`. Known collection
outcomes remain unchanged. Repeat/resume and quality joining reuse these gates.

Prepare a **new quality queue root** from the derived report. Excluded segments
remain records but create no ESA/tone/MetricX jobs or quality samples; sanity
controls remain independent. Frozen queues reject changed report hashes.
In-report and cross-report pairing use the retained first completed/product-failed
primary source selection BEFORE analysis exclusions: an excluded primary is never
replaced by a later successful retry. An earlier operational-invalid attempt does
not block a later legitimate terminal primary. In-report duplicate retained-primary
shared populations are rejected before applicability; `metrics-batch` retains its
stricter rejection of every duplicate native reference-eligible chunk/shared
population, including an excluded first attempt and a successful retry, before
applying exclusions. Resolve the actual canonical source explicitly; exclusions
cannot bypass duplicate or shared-source identity checks. Pairing then requires
both native reference and analysis-population eligibility.
`metrics-batch.pairing_exclusions` retains rejected segment identities/decisions,
and `reports` retains all source history. An output-specific quality exclusion
alone still does not remove an applicable delivery/latency pair.
Global `output_population` remains raw observed translation, not a pure-route claim.

### Cost population

The [existing cost contract](costs.md#report-fields-and-denominators) requires
explicit observed `window_ids`; the cost CLI does **not** consume applicability
automatically. Retain the mixed window and incidents as evidence, but exclude it
consistently from Index-primary component `coverage.window_ids`, free-access
`access.window_ids` and normalized denominator `window_ids`. Bind the analysis
hash and native attempt-to-window mapping in existing evidence/population fields.
Derive replay duration and reference counts from that same selected subset.

Carry both direct and dependent attempt exclusions into that explicit cost-window
selection. A dependency-excluded window is not thereby a mixed provider origin;
retain that distinction and its original collection status. If only part of a
source window remains eligible for one measurement, the cost contract still has
whole observed windows, not invented per-output charge allocation. Compare a
quality/metric/cost point only on the same explicitly selected supported subset;
otherwise retain separate populations or an unknown/partial normalized amount.

Complete coverage and observed free eligibility remain necessary. A failed request,
HTTP401 or missing fallback output does not prove zero cost. Mixed or unassignable
carryover cost remains unknown/partial or separately labelled diagnostic cost;
never prorate it by elapsed time, split at an unsupported rebuild boundary or
rewrite collection status to obtain a free-cost point.

## Report-data contract

The output is one JSON object, `schema_version: 1`, calculation `version: "issue5-v1"`. Consumers must inspect `synthetic`, limitations and evidence coverage before presenting a result.

| Output section | Consumer contract |
|---|---|
| `created_utc`, `measurement_date`, `specification_version`, `run` | Generation/date/input-version identity; do not replace measurement date with report-generation date |
| `definitions`, `limitations` | Applied formulas, population policy and unsupported claims |
| `provenance`, `alignment_provenance`, `application_observations`, `harness` | Checksummed input paths, actual model/runtime details, application metadata and capture implementation identity |
| `attempts` | Retained status, first-attempt history, failure reasons and resume provenance |
| `outputs` | Role-confirmed translations and unresolved-role endpoint observations, distinguished by `output_role`; untouched `raw`, nullable interpreted text/source, relationship/parent/group, rule evidence, content-change certainty, source candidates/confirmed links and quality-segment identity |
| `nontranslation_observations` | Source-only observations retain raw payload and extraction evidence without entering translation, delivery or unaligned-output denominators |
| `quiet_precondition_observations` | Preserved pre-playback wait output and source-only observations, raw payload and candidate provenance; excluded from measured output populations |
| `sentences`, `turns` | Original/generated identity, source session/speaker/category, native reference evidence, uncertainty, candidate turns, timing, delivery and late/unknown output identities |
| `quality_segments` | Approximately 30-second reference units, two unscored earlier turns, final display-order output, unaligned translation, unresolved-role IDs/eligibility and externally supplied quality score |
| `quality_score_coverage` | Total/eligible/excluded segment and supplied-score counts, with exclusion reasons mapped to affected segment IDs |
| `isolated` | Separate utterance-window translation timing, no-output/timeout versus unknown role, retained endpoint activity, carryover and quality eligibility; not continuous-dialogue latency |
| `diagnostics` | Per-attempt segmentation/message measurements, separate nonspeech raw/translation counts, common-clip events with `raw_text` and interpreted `text`/`output_role`, and separately identified PuriPuly internal decomposition |
| `aggregates`, `paired` | Config/direction/category/casual views, original-session values/intervals and shared-segment paired comparisons; common-success comparisons are supplementary |
| `repeats`, `repeat_variation`, `resume_sensitivity` | Repeated-subset observations and summaries with/without resumed chunks |
| `output_population` | Known translation denominator and alignment status, `observed_nonempty_chatbox_inputs`, `output_role_counts` and `unresolved_output_ids`, including orphan output |
| `alignment_cache` | Input-bound reusable correspondence evidence, not a new raw observation |

Measurement objects carry `value`, `unit`, `reason` and relevant denominator/evidence fields. Unavailable values are JSON `null`, never NaN or a fabricated zero. Playback `start`/`end` are seconds; `native_coordinate_units` and `offset_seconds` preserve normalization provenance. `*_ns` values are nanoseconds within the named clock session, not UTC timestamps.

Product-failed attempts remain in the measurement population when reference/timing evidence exists. Operational-invalid, unsupported, partial-reference, nonlexical/unscored, ambiguous-containing-turn and unavailable-source-timing records remain in the report with reasons and denominator-coverage counts. Unknown correspondence stays in eligible delivery denominators, with `unresolved_sentences` and correspondence bounds. Quality eligibility is distinct from deadline/turn eligibility.

Quality segments distinguish `reference_eligible` (source/status population) from `eligible` (supported quality-scoring input). If one indivisible output has confirmed links across multiple quality segments, its `source_quality_segment_ids` names all affected segments, which retain `source_linked_output_ids` and `cross_segment_output_ids`. The text is displayed once, not split into invented spans or duplicated as independent delivery. Every affected quality input becomes N/A with `quality_eligibility_reason: "unresolved_merged_output_allocation"` unless unresolved text role also applies; then `unresolved_output_role` remains primary and merged-output provenance is still retained. Supplied scores remain visible but are excluded. Source eligibility, sentence/turn timing and paired delivery/latency remain available; paired major-error differences require both quality inputs eligible.

Unaligned-rate denominators include all role-confirmed translation outputs in the declared global or source population, including resends, late and orphan output. Unresolved text roles are excluded from that denominator but retained in role coverage and raw observation IDs; they are not known absent translations. Outputs known to be unrelated also lack a linked source; `alignment_status_counts` keeps them distinct from unresolved correspondence. Known-unrelated output does not turn a sentence's no-output result into unknown. Source-population denominators can be smaller than the global denominator; never omit that distinction.

Subgroup output attribution uses confirmed linked source identities, otherwise the assigned quality-segment population; raw attempt identity alone never assigns every output to every category. `unaligned_output_rate.population_attribution` exposes selection-basis counts, ambiguous/excluded output IDs and unassigned capture IDs. `output_population` retains global unassigned and ambiguous-population IDs. Output spanning populations can be nonexclusive: do not sum subgroup denominators into the global denominator. A reference-free output-check, nonspeech or isolated observation remains in its own test population rather than entering continuous quality text by nearest-time fallback.

Explicit historical `pattern_mismatch_unknown_translation` artifacts used the unsafe mixed-text fallback. New quality preparation/frozen-plan loading, aggregate recomputation and batch composition reject those artifacts with a rederivation/new-queue requirement. Preserve original reports and queues unchanged; derive corrected reports from their retained raw evidence rather than silently rewriting history. Ordinary historical matched outputs retain their prior behavior.

First-attempt product-failure rates exclude operational-invalid and unsupported first attempts from their product-failure denominator but preserve all first-attempt status counts. Missing quality scores are unscored, not zero-error judgments. Reports expose session-level values; fewer than two original sessions yields no bootstrap interval. Paired comparisons match shared reference segments rather than treating each target language as a new recording.

`turn_lul_p50` and `turn_lul_p90` are separate from sentence `lul_p50`/`lul_p90`. They use original-session clusters and expose `reference_turns`, `eligible_turns`, `measurable_turns`, `turn_denominator_coverage`, `turn_lul_unavailable_reasons`, session values and interval reasons. The same turn summaries accompany repeat and resumed-sensitivity views; sentence LUL is not substituted for turn LUL.

### Diagnostic evidence

Identifiable boundary evidence may carry `source_boundary_ns`, `sentence_end_ns`, `predicate_end_ns`, `source_speakers`/`speaker_crossing`, and `expected_source_unit_ids`/`delivered_source_unit_ids`. Endpoint-delay versus cut pairs use OSC receipt minus the corresponding source boundary and preserve whether the cut precedes sentence end. Boundary loss and duplication compare expected/delivered unit identities; absent identity evidence is N/A.

Source CER is Levenshtein distance divided by reference Unicode code points, without punctuation/whitespace normalization. It requires an app-exposed source field and source correspondence; Japanese remains automatic-reference guidance. Supported erased-character measurement uses previous Unicode code-point length minus longest-common-subsequence length. Splitting/merging counts alone imply no quality preference.

Split source messages need explicit coverage before CER assembly: `evidence[output_id].source_coverage` is an array of `{sentence_id, start, end}` half-open Unicode code-point spans in reference text, accompanied by outer evidence provenance. Count reference characters once. A single complete exposed-source message retains ordinary CER; multiple messages with absent, overlapping or gapped coverage yield N/A instead of duplicated deletion penalties. Translation append style alone does not establish source-fragment assembly.

Explicit source spans must be integer, in bounds and attached to that output's linked reference; combined coverage must be complete, nonoverlapping and in source order. Merged references concatenate exact reference strings in source order without inserted separators. If any source-bearing component has unresolved reconstruction, attempt CER is N/A; supported character/edit counts and unresolved evidence remain visible rather than silently producing a selected partial CER.

Internal PuriPuly records may contain `speech_end_ns`, `endpoint_ns`, `asr_start_ns`, `asr_end_ns`, `queued_ns`, `generation_start_ns`, `first_token_ns`, `generation_end_ns`, and `output_ns`. Missing pairs remain N/A. These do not replace OSC receipt latency.

## Hand-worked boundaries and observed checks

With DAC origin 10.0 seconds and cable correction +0.1 seconds, source origin is 10.1 seconds. A sentence at playback [0,2] has source bounds [10.1,12.1]. If its containing turn ends at playback 4, the deadline is 29.1. Related content-changing outputs at 11 and 12 give FOL **0.9 seconds** and LUL **−0.1 seconds**. Output exactly at 29.1 is on time; 29.100000001 is late. Missing output has null latency. Role-confirmed translation with unresolved correspondence remains in quality input without proving delivery; unresolved text role instead makes affected quality input unavailable.

Initial candidate checks (before independent-review repairs):

- Focused behavior suite: 24 tests passed, no skips. Covers exact/late deadlines, negative LUL, unknown/no-output separation, failed/resumed attempts, grouping, unaligned quality assignment, isolated carryover, diagnostics, aggregation and stale-cache rejection.
- Repository integration: 130 tests and 29 subtests passed; four existing Chinese real-audio tests skipped because this worktree lacks their `.data/chinese/audio/zh-main.wav`. Shared local corpus metadata was used by the focused checks; no missing audio was fabricated.
- CLI with an actual prepared English reference and explicitly synthetic OSC/playback/cached correspondence produced FOL 0.4 seconds, LUL 0.16 seconds, one delivered sentence and a null one-session interval.
- Actual Japanese local timeline normalization retained 656 sentences, 333 turns and three original sessions. Strict turn evidence marked 181 units ambiguous rather than inventing deadlines. No Japanese speech text was published.
- Retained PuriPuly 2.8.2 manual-text UDP probes produced four output records and two orphan quality segments. The known page link was retained, an earlier standalone prefix was not erased, and repeated text after restart was not called a resend. All correspondence remained unknown because these probes have no source playback. Typing false preceded the last observed page and was not used as a finality marker.
- The initial real CPU SimAlign CLI produced FOL 1.5 seconds and LUL −0.5 seconds on a tiny synthetic fixture. **That automatic source-credit behavior was rejected in independent review:** an unrelated/competing-input probe showed forced links. The execution observation remains historical evidence, not validation of the repaired correspondence policy; model-only output now requires adjudication before latency credit.

Development checks found and repaired an orphan-only quality-assignment crash and an explicit relative cache-path resolution error; focused regression checks retain these boundaries. Local observations and controlled inputs are under `.data/issue5-worker-final/`, `.data/issue5-director/`, and `.data/issue5-alignment/`; those local paths are not published datasets.

Integrated repair checks:

- Final integrated repository suite: **199 tests and 29 subtests passed; four unchanged local-audio checks skipped** for the same missing worktree audio. Core metric checks include native Chinese context recovery; statistics and CER repairs have separate behavior coverage.
- Actual pinned offline model CLI processed positive, unrelated, competing, future-source and punctuation-only cases: all five outputs stayed unknown without adjudication. Useful proposals remained; future/punctuation support was rejected as source authority. The unrelated example still produced lexical links, demonstrating why they are not delivery proof.
- An explicit inspected cache confirmed only the positive synthetic bilingual pair: FOL 1.5 seconds, LUL −0.5 seconds; six other reference sentences remained unknown. A legacy automatically aligned cache without adjudication exited 2. Fifteen recorded observations covered raw/proposal preservation and the negative/positive boundaries.
- The installed `bench.exe metrics` command replayed the confirmed cache successfully: seven reference sentences, five outputs and five quality segments. The corrected `pip install -e ".[alignment]"` instruction completed successfully in the owned alignment environment.
- Controlled category/casual CLI output kept general, stress and casual denominators distinct, retained delayed source attribution, and exposed turn LUL separately from sentence LUL. Original-session values and null unavailable measurements remained visible.
- Controlled split-source CLI cases produced CER 0/11 for explicitly covered exact fragments, 2/11 for fragments with real character errors, and N/A with a reason for unproved fragment/snapshot assembly. No duplicate full-reference denominator remained.

Independent-review repairs also covered explicit-parent page revisions, aligned pages crossing quality boundaries, repeated equal-text utterances, source-only extraction, empty native Chinese context, and separation of reference-free output checks from continuous scoring. Repair observations are retained locally under `.data/issue5-core-repair/` and `.data/issue5-diagnostic-repair/`; they are controlled verification, not application comparison results.

A terminal audit additionally found a single merged message crossing two quality segments without a supported per-segment translation allocation. The repaired actual CLI retained one display placement and linked both source segments, excluded their two supplied scores with reasons, and preserved 3/3 sentence delivery and the original two-output denominator. A third independent segment remained scorable. Fifteen composition checks passed; `.data/issue5-t1/` retains the controlled evidence. Paired-comparison regressions also preserve delivery/FOL/LUL pairs while excluding unsupported major-error comparisons, including product-failure, invalid/unsupported and ambiguous-timing cases.

### Actual application samples

The earlier missing-real-trace prerequisite is now covered by inspected **VRCS 0.2.8** and **VRCLT 1.0.1** speech-to-translated-OSC observations. The [artifact index](../profiles/evidence/issue45/metrics/actual-pilot-metric-index.json) links source binding, raw hashes, observed rules, sanitized results and the retained local calculation records. VRCS1/VRCS2 are two configurations of one app; VRCLT1 supplies the distinct all-in-one rolling/mixed-role style. The separate Qwen endpoint-repair check is not included in these metric samples.

All three samples reuse one 40-second English development excerpt from original session ES2014a, nine complete manual dialogue-act reference units and two earlier context turns. Word times are automatically aligned, and dialogue acts are not independently verified grammatical sentences. These are bounded integration examples, not independent recordings, a fair performance ranking or frozen main results. Unrelated background user activity was not isolated.

| Configuration | Related-content delivery | FOL p50 / p90, seconds | Supported sentence LUL |
| --- | --- | --- | --- |
| VRCS2 | 3/9; six no-output-before-deadline | 3.086 / 4.543 | 0.436 seconds for one unit; otherwise N/A |
| VRCS1 | 8/9 confirmed; one unresolved | 3.630 / 6.788 | 0.404 seconds for one unit; otherwise N/A |
| VRCLT1 | 9/9 related-content units | 4.759 / 5.969 | N/A for rolling output |

Delivery and FOL are conditional on inspected source correspondence; they do not establish complete or accurate meaning transfer. Missing output has null latency. Unknown filler and rolling fragments remain unknown rather than receiving forced source credit. Rolling content changes do not establish revision identity, finality or semantic completion; unsupported LUL, erasure and final reconstruction remain N/A.

Denominators retain their scope: global unaligned translation counts are 2/6, 3/12 and 5/25 respectively; the continuous/measured-stage counts are 0/4, 1/10 and 2/22. Source-only and typing observations are preserved but excluded from translation denominators. Reference-free output-check translations remain separate. VRCLT's mixed check/main packet retains its prefix and provenance; only its inspected new acknowledgment receives source credit.

Unknown translated output reaches quality inputs. An indivisible merged packet crossing source quality-segment boundaries is displayed once and linked to both segments; both affected inputs are unscorable with `unresolved_merged_output_allocation`, rather than inventing translation spans or duplicating the text. The retained VRCLT mixed-carryover example is protected by that cross-segment guard; it does not demonstrate a generic standalone carryover guard. No quality scores, major-error rates, session-clustered confidence intervals or repeated-run conclusions are claimed from these samples.

The actual CLI derivations and bounded checks are recorded in the index: 25 checks for each VRCS sample and 29 plus four mixed-carryover checks for VRCLT. All 18 source bounds per sample were checked against integer-frame callback arithmetic after correcting a native-frame float round-trip defect. Pre-repair artifacts and first failed/invalid attempts remain preserved. The historical cable correction was reused, not newly precision-certified. These observations replace the old missing-input statement; they are bounded integration evidence, not a completed comparison.
