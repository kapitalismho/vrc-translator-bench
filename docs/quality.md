# Episode GEMBA-ESA quality and semantic checkpoints

## Current evaluation

`bench quality --spec SPEC.json --output RESULT.json [--transport JUDGE.json]` evaluates explicitly bound episode/role histories. Without `--transport`, it reconstructs locally and reuses validated stored judgments; missing judgments remain incomplete. A transport permits new calls only after the spec declares `measurements_ended: true` and the evaluator acquires the same user-wide `activity.exclusive_activity()` lock as capture. No translation app is launched by evaluation.

The selected route remains **GPT 6 Astra / Sign in with ChatGPT**, with no paid/model fallback. `quality_store.QualityStore`, `quality_transport`, `quality_process`, `quality_judge`, and `quality_bridge.mjs` retain durable calls/raw responses, returned model identity and Windows child containment. A new result owns a separate store; historical queues, scores and alignment caches are not migrated.

### Two independent stages

The upstream methodology is pinned to [MicrosoftTranslator/GEMBA `bf1f113479c26f555e564659df1a491dde606adf`](https://github.com/MicrosoftTranslator/GEMBA/blob/bf1f113479c26f555e564659df1a491dde606adf/gemba/gemba_esa.py), source SHA-256 `9c109e163ad2db8c172ce7005c7452999158252914cd14b885fa762c4a98c29f`.

Upstream GEMBA code and data are **CC BY-SA 4.0**, not MIT. The adapted `bench/quality_prompts.py` module retains that license, attribution, source link, modification notice and warranty disclaimer; see [LICENSE](../LICENSE). Other original benchmark modules retain the repository's MIT terms. This attribution change does not alter the actual prompt bytes or invalidate stored prompt identities.

1. Identify errors using the upstream taxonomy and minor/major definitions. Validate exact source/translation quotes and occurrences; malformed evidence is rejected, not silently repaired.
2. In a new conversation, supply the same source/translation and accepted first-stage evidence for a direct continuous 0–100 score. Preserve anchors 0/33/66/100; do not calculate scores from error counts.

The three original few-shot examples and answers are retained as labelled demonstrations in the system message. This explicit serialization adapts upstream's eight-message example sequence to the retained bridge's exactly-one-system/one-user contract. Both stages use separate calls, not continued conversation state. Upstream identity, adapted prompt identity, complete blinded inputs, raw response, parsed result and actual returned model remain separately auditable. Failed/unresolved calls are retained rather than retried implicitly or treated as no errors.

One target language and one logical role are judged per input. Other audible speakers and code-switched context remain available with their scored/context-only scope. Product/model/price/speed metadata stays outside the blinded request. Natural source repetition and accurate paraphrase are not inherently errors. Missing reviewed references, uncertain text extraction and unknown observation opportunity are not zero scores.

### Native reconstruction and waiting

`bench.history` keeps raw events unchanged. Evidence-bound append/replace/clear interpretation preserves genuine repetition, revision chains and earlier emitted pages. A presentation clear does not retract prior meaning. String-prefix similarity, last-packet selection and invented native IDs are not reconstruction rules. Ambiguous endpoint relationships remain unavailable until supported by evidence; a separate FINAL log is not a substitute for earlier OSC output.

Semantic decisions use only source units and native output available at each checkpoint's 0/2/5/10/15-second cutoff. Future answers or late corrections cannot satisfy an earlier cutoff. First correct output, later wrong revision and correction remain separate evidence. Unknown clock mapping or an interval crossing a cutoff remains uncertain, not an exact receipt-time claim. Native-output waiting is not screen-rendering or human-response latency.

Checkpoint-only quotes may name `side: "history"` with an opaque `history_index`, exact `text` and one-based `occurrence`. The index selects an admitted append/replace emission in that observation's blinded history, not a native event ID. Validation searches its emitted text, never an invented quote or `previous_text`; future/unavailable indexes and presentation-only operations are rejected. `native_history_citations` maps accepted local indexes back to raw-event evidence. This preserves first-correct meaning even when the correct emission is replaced between observation points, without mixing superseded errors into final-quality text.

For Runner manifests, input timing is derived from the hash-bound role WAV format and actual submitted callback ranges: `input_ns = callback.dac_t_ns + round((sample - source_frame) / sample_rate * 1e9) + measured_calibration_offset_ns`. Prepending scheduled silence does not submit source frames. A first input origin alone does not prove a linear clock. Frame gaps, overlaps and callback status errors remain unknown input even if a later record says playback completed. Missing timing evidence alone need not discard defensible final quality.

Each pass retains the original common final-speech +15-second horizon. Use the profile classification deadline, not a later round/collector completion time. No-output certification also checks scoped arrays, extraction, clock, attribution and gap evidence; empty primary text fields are insufficient.

Fully observed total no-output with a genuine translation target yields protocol-derived quality 0 and waiting unmet, with no fabricated judge call. Harness interruption, unsupported/unplayed work, ambiguous references or output, and judge failure remain distinct incomplete outcomes. Planned missing episodes, roles and checkpoints keep their weight. [Weighted result fields and CDF rules](metrics.md#current-weighted-result-contract) apply independently to quality and waiting.

R4 component verification is not R6 assembled-path admission. Retained R1 logs may legitimately replay to unknown because producer time or native revision relationships were never established. R3 requires the actual uncertainty-bearing reviewed reference, not an intended script relabelled as acoustic gold. Remaining live contrast/repeat-variation checks and profile admission belong to R6.

### Input and result bindings

The evaluation spec uses `schema_version: 1`, a nonempty `protocol_revision`, explicit `episodes`, and explicit `populations`. Artifact bindings contain `path` and `sha256`; relative paths are resolved from the spec, or from the run manifest for its own artifacts. Hash mismatch is an input error, not permission to repair a frozen reference.

The report destination and its atomic `.tmp` sibling must not alias any consumed source, reference, manifest, trace, stream, interpretation, transport configuration, profile catalog or spec. Resolved-path and existing hard-link collisions are rejected before opening the judge store or dispatching.

| Object | Required meaning |
|---|---|
| Episode | `episode_id`, `source_case_id`, `language_pair` (`en-zh`/`ja-ko`), `kind`, and checksummed `reference`; optional reference `case_id` selects one case |
| Population | `profile`, `measurement_condition`, selected `roles`, and optional explicit structured `condition` for custom inputs; missing planned roles remain incomplete |
| Role selection | `episode_id`, logical `role`, and exactly one checksummed `run_manifest` or standalone `history` selection |
| Manifest selection | `attempt_id`, `pass_id`; checksummed trace and frozen source/route evidence must match the planned profile/episode/pass. Explicit `clock` overrides are rejected |
| Standalone selection | Explicit `scope`, `outcome`, and optional evidence-bound `clock`/`interpretations`; historical exports are not assumed to be full Runner attempts |
| Standalone clock | Integer `origin_ns`, `horizon_ns`, nonempty `clock_session`, retained mapping `evidence`, and optional integer `input_available_until_ns`; an absent mapping is not a zero offset |
| Normalized reference | `source_case_id`, exact `source_units`, and `semantic_checkpoints`; preserve upstream source and uncertainty citations |
| Source unit | Unique `id`, logical `role`, exact `text`, relative integer `start_ns`/`end_ns`, nonempty `citations`; optional `translation_targets`, `context_only`, and localized `uncertainty` |
| Checkpoint | Unique `checkpoint_id`, role, `evidence_end_seconds`, required meaning/concepts and fixed `[0,2,5,10,15]` observation offsets |

The normalized reference is a consumer contract, not authority to rewrite source text. Ordinary mixed-speaker input has one runtime role A while preserving original speaker identity; T1 keeps A/B separately. Preserve target-language context without awarding translation credit. R3 mappings must carry actual reviewed uncertainty and descendant timing, never the English/Chinese parent's timing or a bare intended script.

The [final-only recovery handoff](../profiles/evidence/r6/final-main-handoff.json) supplies explicit R3 consumer adapters without changing this reader. Within-turn checkpoints require reviewed descendant semantic spans and newly measured operational endpoints, not a parent's timestamp or the end of an unrelated later clause. Splitting a reviewed turn into causal source units must reconstruct its complete text exactly. Keep each localized uncertainty with its available span; a full-turn ASR observation embedded in prefix uncertainty must not reveal future source text. Native alignment-grid resolution is not a certified total timing-error bound. The recorded offline ingestion and prefix checks do not establish app output or measured waiting time.

IngCrowd's original `speaker` is preserved as `original_person` with `original_person_scope: "dialogue_local"` in the blinded context; it is not a globally identified participant. Explicit standalone `input_available_until_ns` bounds also gate final quality and protocol no-output zero. If required role input was not fully available, final quality is `unknown_input`/null regardless of a contradictory completion flag; earlier supported checkpoints may still be retained independently.

Canonical profile conditions come from `profiles/catalog.json`; a selected manifest's `plan.profiles[].condition` must agree. Structured conditions use `ordinary_input`, `t1_mode` and role-to-channel `roles`. Their normalized labels are `self/split` or `peer/simultaneous`: canonical Kikitan/VRCLT cannot be relabelled as peer/simultaneous. Selected channels, passes and role routing must match. Populations, roles and selected-role provenance retain `condition` and `condition_evidence` with authority hashes. Custom labels without structured authority remain explicitly population-declared, not a verified physical mapping.

`bench.history.reconstruct_history` accepts raw events and explicit role/scope/cutoff/horizon bindings. Interpretations bind a zero-based `event_index` and canonical `event_sha256` to an operation plus `rule: {id, description, evidence}`. `replace`/`delete` name `replaces_event_index`; optional exact `text_field`/`text_span` extraction cannot introduce replacement wording. A mapped `event_time_interval` requires clock-mapping evidence. Canonical event hashes identify the retained JSON object; original-wire `raw_evidence.sha256` retains its different meaning.

Standalone `scope` may retain `run` and `wave` alongside `profile`, `episode`, `attempt`, `pass_id`, `channel`, `clock_session` and `target_language`. Reconstruction excludes records with conflicting explicit execution identities; mixed unselected run/wave values remain ambiguous rather than merged. The original selection stays in report provenance for cost binding. Missing identities are not invented, and this support does not establish observation completeness or final admission.

When run or wave is selected explicitly or inferred uniquely, each admitted output must carry that identity; missing membership leaves reconstruction unavailable. Histories with neither selected nor inferred execution identity retain identity-free behavior. Condition routing validation applies the same explicit run/wave conflict exclusions before checking selected native roles and channels.

The [R6 identity-repair evidence](../profiles/evidence/r6/identity-repair.json) records 244 passing focused tests and six actual offline CLI cases: selected output progresses despite unrelated wrong-route records, missing execution membership remains unknown, and selected routing contradictions still fail before report/store creation. Existing matching PP4 judgments were not recalled.

Run-wide collector diagnostics are scoped using the selected checksummed trace's unique `attempt_start`/`attempt_end`, validated against its run, profile, episode, attempt, pass, clock and available ledger bounds. Only unscoped stream gap records proved wholly outside that interval are excluded; preparation-time gaps, touching/overlapping intervals, uncertain clocks/bounds, selected-trace records and explicitly interpreted records remain subject to normal history rules. This does not use first audio input as the attempt start. `attempt_bounds` and `excluded_stream_diagnostics` retain the boundary proof, raw excluded event and stream artifact/index; history citations and interpretation indexes continue to refer to the original combined records.

The report uses `kind: "episode_quality"`, `report_version: "r4-episode-quality-v1"`, `schema_version: 1`, and `status: "complete" | "incomplete"`. `planned_episodes` preserves the denominator. Each population contains `role_results` and one `aggregate`; condition labels remain attached. `calls` links durable raw responses and stage identities to the separate `RESULT.json.store/quality.sqlite` store. Keep this store and the referenced immutable artifacts with a result handoff; the summary JSON alone is not the raw evidence archive.

Cost reconciliation consumes this report by SHA-256 without changing its schema, selected roles, judgments or aggregates. Optional episode/population/role `cost_binding_id` values carry through the external [R5 cost revision](costs.md); identity still requires matching profile, measurement condition, episode, role, run, pass and selected attempt. Later owner billing appends a cost evidence revision referencing the same frozen report. An incomplete quality/time result does not become complete because costs are available, and missing billing is not zero.

For a bounded two-stage check, `bench.quality.judge_role(data, store_path=..., transport_path=..., measurements_ended=True, bindings=...)` uses the same stage executor without launching capture or asserting a complete weighted population. Its `data` contains `source_language`, `target_language`, `source`, `output` and `context`; provenance belongs in `bindings`, outside the blinded prompt.

The [retained final selected-route sample](../profiles/evidence/r4/minimal-judge-final.json) binds actual returned model, upstream/prompt/input/result/raw hashes, isolated per-stage payload evidence and fresh-process cache reuse. It is one task-owned negation/number counterexample, not app quality, a calibrated ranking, or completed R6 variation testing.

## Historical scoring reference

Everything below records the [pre-reset implementation](https://github.com/kapitalismho/vrc-translator-bench/tree/fbab10a0455d91d5419d9673499d25b7ac86c566). Its old subcommands/extras are not compatibility aliases for the current `bench quality --spec` interface, and its successful observations do not validate the new methodology. Historical scoring/sampling/MetricX and queue commands remain retired. The selected transport configuration and isolation principles remain useful.

This is the automatic quality layer for [issue #6](https://github.com/kapitalismho/vrc-translator-bench/issues/6). It consumes the [issue #5 report contract](metrics.md), not application ASR as reference text. Scoring infrastructure and synthetic checks do not establish a completed application comparison. The planned judge is **GPT 6 Astra through Sign in with ChatGPT**; no API-paid fallback is provided.

## Working evaluation choices

Freeze these choices with the comparison revision in #8. They are implementation defaults, not independently validated measures of translation accuracy.

- ESA receives the source reference, target language, two earlier unscored reference turns, and interpreted final output in display order. That output includes temporally assigned role-confirmed translation with unknown correspondence, not unresolved-role mixed text. Preserve #5 exclusions, reconstruction uncertainty, partial references, and automatic Japanese-reference limitations.
- Application, engine, creator, price, latency, capture IDs, and report metadata are not sent to the judge. Speaker identities are pseudonymized consistently within a call. Reference/output content is untrusted data, not instructions. Blinding metadata does not promise that linguistic content can never reveal its origin.
- Each judgment starts an independent conversation. Configurations are shuffled within shared-source groups with a recorded seed; earlier judgments are never conversation context. Queue resume does not resume a judge conversation.
- ESA requests minor/major error spans and a 0–100 score. In `contextual-esa-tone-v2`, the judge supplies exact quoted `text` and a mandatory positive, 1-based `occurrence` within the selected source/output, counting overlapping matches. Python derives half-open Unicode-codepoint `start`/`end` offsets for the normalized result; the judge no longer counts characters. Raw responses remain unchanged. Nonexact quotes, invalid occurrences and model-supplied offset fields are rejected rather than repaired. Omissions quote missing source content; an entirely empty output may instead use an empty output omission with occurrence 1, normalized to `[0,0)`. Conversation context and roughly 30-second segments modify standard GEMBA-ESA practice.
- Representative outputs are **ESA mean** and **segments with at least one major span / scored eligible segments**, with eligible and missing denominators. Span counts are supplementary annotations, not independent real-error counts. No combined ESA/MetricX/latency overall score is defined.
- Tone is supplementary: a frozen deterministic sample of 30 eligible segments per configuration across available directions/categories. It covers politeness/register consistency, rudeness risk, and naturalness. Small populations retain an explicit shortfall rather than duplicating samples.
- The tiny sanity set contains empty, wrong-language, and unrelated translations. A score above 50 or absence of a major span triggers investigation or an explicit retained `--sanity-limitation`; this is an obvious-failure guard, not a validated evaluator threshold or a larger validation study.

## Prepare, score, inspect, resume

Use the checkout's Python environment, or the installed `bench` entry point:

```powershell
python -m bench.cli quality prepare --report .data/reports/pilot.json --root .data/quality/pilot
python -m bench.cli quality status --root .data/quality/pilot
python -m bench.cli quality score --root .data/quality/pilot --transport-spec judge.json --measurements-ended --limit 6
python -m bench.cli quality report --root .data/quality/pilot --output .data/quality/pilot/report.json --review-output .data/quality/pilot/korean-review.json
```

Repeat `--report` to assemble configurations from multiple reports. Preparation freezes the inputs, seed, sample membership, and prompts; use a new root for changed inputs or prompt versions. `--seed` defaults to `20261020`. The input reports remain unchanged.

An extraction-role exclusion retains the record with `input: null`, `input_unavailable_reason: "unresolved_output_role"` and the affected segment's `unresolved_output_ids`. No ESA, tone or MetricX job is created for it; coverage and raw identities remain visible. Null input is not an empty output string and must not be scored as an omission. Reports and MetricX lookup retain this unavailable state; externally supplied scores cannot override input eligibility.

Explicit legacy `pattern_mismatch_unknown_translation` artifacts are rejected before new scoring/composition, including frozen-plan loading. Rederive corrected metrics from retained raw observations and prepare a new queue. Do not edit historical reports or frozen queues; this safety boundary does not change valid historical matched inputs or judge prompts.

### Explicit core-only execution scope

Default preparation still includes supplementary tone sampling/jobs and Korean reference-review reporting. For the owner-amended current D1/D3 execution, prepare a **new** queue with both opt-outs:

```powershell
python -m bench.cli quality prepare --report .data/reports/pilot.json --root .data/quality/core-only --skip-tone --skip-korean-review
python -m bench.cli quality report --root .data/quality/core-only --output .data/quality/core-only/report.json
```

`--skip-tone` prevents tone sample selection and tone judge jobs; reports omit tone scores, summaries and sample/shortfall sections. `--skip-korean-review` prevents Korean packet selection and generation; reports omit `korean_review` rather than fabricate an empty packet or a coverage shortfall. Either flag may be used independently. ESA inputs/jobs, sanity checks, the fixed changed-judge calibration sample, MetricX eligibility and cost/metrics accounting are unchanged. Preparation and reporting do not perform inference.

The booleans are frozen as `evaluation_scope.tone` and `evaluation_scope.korean_review` in the bound quality plan. Reusing a root with different requested scope is rejected, including omitting flags for a previously core-only root; repeat its original flags or use a new root. Plans without `evaluation_scope` retain the historical full behavior and are not rewritten. A review-disabled plan rejects report `--review-output` or `--human-notes` before writing report/packet files. These opt-outs do not change judge prompts, model selection or service/payment routes.

The [current D1/D3 scope amendment](../profiles/evidence/issue8/supplementary-scope-amendment.json) removes tone-30, Korean-100 and owner-review obligations from that execution. Reusable supplementary features and historical observations below remain available; their historical shortfalls are not current execution requirements.


New preparation generates v2 prompts. Use a **new root** to adopt this repair; `prepare` rejects an existing v1 root rather than rewriting its frozen protocol. Existing v1 queues remain readable and reportable, and `score` resumes their original prompts with the strict v1 offset decoder. Their failed responses are not reinterpreted as successes. Plan binding, per-job prompt version/hash and cache identity keep the two protocols separate.

A normal repeated scoring invocation reuses completed cache entries. Failures, quota pauses, interrupted/unknown calls, and malformed or missing responses are not successful judgments. Inspect `quality status`, resolve the cause, and explicitly pass `--retry-unresolved` to attempt unfinished calls again. Each attempt and its raw response remains available. A retry may make another service call when the previous call's terminal outcome was unknown; it is not proof that the earlier call was never admitted.

Judge `score` invocations exit 2 when retained failed, blocked, or unresolved judgments remain, even if some requested work completed. Independent `--metricx-only` exits according to its requested local outcomes: completed returns 0; unavailable, failed, oversized, or unresolved returns 2. It preserves the judge's quota/model-change/sanity pause and does not authorize judging to resume; `metricx_outcomes` and `paused` report these separate states. Inspect counts and `quality status`; exit 0 is not evidence of full planned benchmark coverage. Generated report call records contain `raw_artifact` pointers into the queue's `quality.sqlite`; retain that database with the reports. `quality status` exposes the full raw history.

Each `quality report` invocation reads model selection, histories, cached judgments, calibration and execution status from one SQLite snapshot. Scoring can continue and commit while a report is built; those newer results appear in a subsequent report rather than partially entering the current report.

`--limit` bounds admitted calls, not a claimed quota allowance. Use one call at a time. The issue's roughly 2,300-call estimate is not a service guarantee. Quota pauses do not switch account, model, payment route, or service tier.

### Selected subscription transport

The real subscription bridge requires **Windows**, Bun 1.3.14 or later, and **`@oh-my-pi/pi-ai@18.12.3`** with its matching dependencies. It calls the low-level subscription provider directly, not a coding-agent session: no inherited repository instructions, tools, MCP, hooks, memories, or earlier conversation are supplied. The actual outgoing payload is checked before its one permitted inference POST. Raw inference events are retained; broad request/auth debug logging is disabled. Real dispatch on other operating systems fails before spawning a child; cross-platform synthetic fixtures are not real judging support.

Use an existing Omp-managed `openai-codex` OAuth login. Codex CLI login alone does not establish that this separate managed store has an account. If installation/login is needed:

```powershell
bun add --global @oh-my-pi/pi-ai@18.12.3
bun add --global @oh-my-pi/pi-coding-agent@18.12.3
omp login openai-codex
```

These are setup instructions, not a requirement to replace a newer shared Omp installation. Prefer an isolated pinned SDK when Omp is already installed. Save `judge.json`:

```json
{
  "kind": "chatgpt-sign-in-bridge",
  "route": "Sign in with ChatGPT",
  "timeout_seconds": 180
}
```

Optional fields are `runtime` (Bun executable), `package_root` (installed `pi-ai` directory), `auth_db` (existing managed database), and `credential_id` (exact positive OAuth row ID). The package root defaults to `~/.bun/install/global/node_modules/@oh-my-pi/pi-ai`. One stored OAuth account is selected unambiguously; multiple accounts require an explicit row, never automatic rotation. The supported auth manager may refresh that account; credentials remain in process memory and managed storage, not scoring artifacts. Do not export tokens into this specification.

If an existing global SDK has a different version, keep the current Omp installation and use an isolated installation of the pinned SDK through `package_root`. The historical smoke used a task-local 18.12.3 installation while leaving global 18.12.4 and the managed login unchanged.

The transport's optional `model` field accepts only `gpt-6-astra`. The scorer's separate `--model` selects the expected **returned identity/cache namespace**, not a different transport model. A returned-identity change pauses scoring; inspect its raw evidence before evaluating the frozen calibration sample with the new expected identity. A different planned judge still requires an owner decision and an explicit implementation change.

### Measurement exclusion

Capture `Runner.run` and quality scoring share an OS advisory lock at `~/.cache/vrc-translator-bench/activity.lock`. The conservative policy excludes **all managed capture** while judging or MetricX runs, not only PP2. The lock spans worktrees and run roots under the same user and is released when the owning process exits. Do not delete the lock file to bypass a running owner.

Each Windows judge child belongs to a non-inherited kill-on-close Job Object before the scorer sends its complete stdin request. Normal and timeout paths terminate/wait for owned descendants before releasing the activity lock; terminating only the scoring parent also terminates its owned job. Before admission, the bridge rejects incomplete/empty stdin without authenticating or dispatching. This contains local clients, **not provider-side execution already admitted**: interrupted remote calls remain unresolved, and retry may submit another call. Forced termination may leave an owned temporary directory because it bypasses normal cleanup; never delete shared auth/cache/log resources as cleanup.

Real scoring and MetricX require `--measurements-ended`. This is an operator assertion for external/unmanaged measurements, not automatic discovery of every application. The scorer also inspects `.data/runs` and additional repeatable `--capture-root` paths. Stop timed app measurements first. Older runner versions, another OS account, external apps, and directly invoked inference libraries do not participate in this lock. GPU scoring is allowed only after timed measurements end.

## Provenance, cache, and judge changes

The durable queue retains source/context/output identity, prompt/version, immutable jobs, per-call history, raw responses, observer dates, and exposed response-level model identity. Requested model names and catalog/thread configuration are not substituted for actual returned model identifiers. Unexposed provider dates stay absent; local observation time is not a model release date. Missing actual model provenance prevents a successful reusable judgment.

Cache reuse requires matching input/context/output, prompt/version, and actual judge identity. Previous responses survive model changes. A fixed sample of up to 100 exact source/output cases is selected at preparation, before results. `--calibration-only --model MODEL` evaluates that same sample under a changed judge. Reports describe paired score movement and missing calibration coverage; calibration is not proof of equivalence. `quality report --model ACTUAL` selects a returned model explicitly; mixed-version results must remain identifiable.

Calibration counts every frozen sampled record key, even when identical prompts share one cached response. Such cases retain their individual sample weights and paired coverage. Cached sanity outcomes for the selected actual model are checked before resumed admission, including recovery after a result/settings commit gap; model changes cannot bypass investigation. A passing sanity result or an explicitly retained applicable limitation permits progress without erasing earlier responses.

Changing the planned judge or paid route requires a new owner decision. Exposing `--model` enables the required version-change/calibration workflow; it is not authorization to silently substitute an unavailable judge.

## MetricX-24 Hybrid QE

Install in a separate scoring environment when necessary:

```powershell
python -m pip install -e ".[metricx]"
python -m bench.cli quality score --root .data/quality/pilot --metricx-only --measurements-ended --allow-model-download
```

The selected checkpoint is `google/metricx-24-hybrid-xl-v2p6`, not the large, XXL, or bfloat16 variant. `--metricx` also runs the supplementary metric during a judge invocation; `--metricx-model-path` selects a local model snapshot, and `--metricx-device` defaults to `cpu`. Missing dependencies or weights produce unavailable values with reasons, not fabricated predictions.

The runtime follows the [pinned upstream QE protocol](https://github.com/google-research/metricx/blob/fc4978eb064670f7cc33e93ea4f52d38396b8ae6/metricx24/predict.py):

- Model revision `f6e7f99a655582f28cb998dd3e6ca86b4217430d`; `google/mt5-xl` tokenizer revision `63fc6450d80515b48e026b69ef2fbbd426433e84`.
- Input is exactly `source: {source} candidate: {output}`, with source/output text joined in the same segment order as ESA. No target reference translation, conversation context, or metadata is added.
- Count the entire untruncated tokenized input including EOS. Above **1,536 tokens**, retain the input/count and an oversized missing-score result. Do not silently truncate, summarize, split, or increase the limit. Accepted input removes the final EOS as upstream does.
- The MT5 regression computation uses one decoder token `0`, vocabulary logit `250089`, and clipping to `[0,25]`. **Lower is better.** Standard Transformers MT5 implements the same projection with device-correct decoder placement rather than copying the upstream model class's CUDA-selection bug.
- Actual local files, revisions, runtime/device, token counts, and prediction provenance support cache identity. Requested names alone do not validate model-file reuse. A local directory containing a competing consolidated `pytorch_model.bin` or an `adapter_config.json` loader override alongside the pinned shards is rejected before identity/cache reuse or inference; otherwise Transformers could prefer unverified weights or redirect the base model.

The selected float32 weights occupy about 13.94 GiB before runtime overhead and activations. The pinned loader already uses low-memory initialization and file-backed mappings; free physical RAM below the weight size is not by itself proof that inference cannot run. Windows private mappings still require system commit, and existing automatic pagefile growth needs disk space. Check these resources before inference without changing user settings or stopping unrelated processes. A small successful run is not a maximum-input memory guarantee. Oversized or unavailable results remain visible in coverage, never zero-error scores.

## Reports and Korean reference review

Generated reports preserve source reports and join automatic scores by report/segment identity. Missing scores remain null, exclusions remain excluded, and original categories, attempts, reference uncertainty, and provenance survive. Major-error and paired summaries use eligible scored populations, not missing-as-zero. PP2 is identified in report metadata as belonging to the judge's GPT model family; this identifier is never judge input.

Isolated-response quality is window-only. A joined score is reused only when an eligible same-attempt isolated segment has exactly the same ordered reference texts and final output IDs/texts as the isolated window. A nonmatching or unscored window retains null with a reason; prior supplied scores remain separate historical evidence. Continuous-segment scores are not silently substituted for the isolated test.

The disagreement list uses absolute differences between ESA and reversed MetricX ranks within direction/category, not subtraction of their incompatible raw scales. It is a review prioritization aid. Agreement is not truth; disagreement is not evidence of model-family bias. **ESA receives conversation context; MetricX does not.**

The Korean packet selects D3/D4 eligible outputs: 50 random cases, then 50 high-disagreement cases without overlap. Each stratum aims for 25 PP2 and 25 other-family cases; available remaining cases can fill family deficits, with achieved counts and shortfalls disclosed. Missing paired automatic scores cannot create high-disagreement cases. Fewer than 100 suitable cases produces a partial packet, not a claim that the planned sample was completed.

Owner review covers Korean fluency, tone, and obvious Korean problems only. It does not verify Chinese/Japanese source semantics. The packet starts with human review unperformed. Optional `--human-notes` reads a separate JSON object with `performed` and `notes` (`key`, `note`, and optional metadata); these reference-only observations never overwrite automatic scores. Do not mark review performed merely because a packet was generated.

Keep artifacts local until source rights and content are cleared. Japanese speech-derived material remains automatic-reference/exploratory and subject to the existing local-only restriction. Inspect raw responses and provenance for sensitive local metadata before any publication.

## Current recovery verification

On 2026-10-21, the historical implementation was reconstructed separately before integration onto `812582d`. Replay included 85 successful writes/edits and excluded eight failed patches. Archived final reads matched 4,080 observed lines; twelve Git blob-prefix comparisons and the five-file integrated diff matched. The synthetic legacy-plan fixture was deterministically reconstructed from its generation inputs and observed timestamp; its size, line count and 94 observed lines match, but no full historical blob hash is available. Recovery records are under `.data/recovery/issue6-reconstructed/records/`.

Only the 31 quality-related paths were integrated. The current [v2 corpus and recovery boundaries](corpus.md#local-recovery-revision) remain intact. The missing original run ledgers, full scoring caches and canonical report files were not fabricated or treated as restored.

Fresh verification used the current checkout:

- `bench metrics` re-derived two actual reports from immutable public-safe VRCS2/VRCLT1 pilot exports and the unchanged English reference. Owned derivative manifests bind checksums to the exported bytes and retain original-to-export provenance. All six complete quality-segment objects match the archived inputs exactly; the new report envelopes have new hashes. `.data/issue6-inputs/evidence-index.json` records the derivation. These are historical translator observations freshly processed, not new translator runs or a Japanese-main-v2 evaluation.
- A new queue completed seven selected-route `gpt-6-astra` judgments: three sanity cases, two ESA and two tone cases. Each retained raw response exposes the returned model and date, one inference POST, and independent payload isolation. Empty, wrong-language and unrelated sanity outputs received ESA 0, 10 and 0, respectively, each with a major span. No paid API, alternate judge, old score import or unresolved live call was used.
- The exact pinned MetricX XL model completed five CPU float32 predictions on the same two eligible inputs plus the sanity set. Fresh processes reused all seven judge rows and five MetricX rows unchanged, adding no calls or predictions. The selected model runs despite physical RAM being smaller than its weight size; this is not a maximum-input memory guarantee.
- MetricX assigned the wrong-language sanity output a low error score (about 0.623), an observed limitation: its pinned source/candidate input has no intended-target-language metadata. Retain this counterexample; low QE error is not proof of target-language compliance or semantic correctness.
- Generated reports retain two eligible paired results and four null-score exclusions. The disagreement list has two rows; this tiny sample cannot establish agreement as truth, model-family bias or a comparison ranking. The Korean packet selects zero cases and explicitly reports a 100-case shortfall, with human review unperformed.
- The lightweight activity/quality/protocol/transport/process/MetricX run passed 138 tests and skipped two Torch-dependent tests. The isolated MetricX environment passed all 23 MetricX tests, including those two; capture regressions passed 16 tests. No full-suite or type-check claim is made.
- Actual controlled CLI checks rejected capture and scoring while the shared lock was held, then completed six synthetic capture stages through fresh-process resume. Malformed and interrupted judge calls remained visible; explicit recovery completed five synthetic jobs, and fresh-process reuse preserved all seven historical call rows. Joined missing/excluded scores remained null. These controls used no translator, audio device or real service.
- During PR review, a concurrent-report defect was reproduced in four deterministic cases: a score committed between independent report reads could disagree with the report's history, calibration or completion counts. Report generation now holds one SQLite read snapshot. The affected seven-file suite passed 141 tests with two existing Torch-dependent skips. A controlled actual CLI report remained coherently unscored while separate scoring processes committed five judge results and four MetricX results; a fresh-process report then included all of them. Output-error cleanup and subsequent scoring/report recovery also passed. These synthetic concurrency checks did not repeat live judging or selected-model inference; evidence is under `.data/issue6-report-snapshot-repair/`.

Current raw responses, frozen plan, reports, commands and row-preserving reuse proofs are under `.data/issue6-current-smoke/`; start with `execution-report.json`, `quality.sqlite`, `quality-report.json` and `korean-review.json`. Runtime setup and exact payload checks are under `.data/issue6-runtime/setup-evidence.json`; controlled CLI observations are under `.data/issue6-control-smoke/evidence.json`. A local evidence-wrapper filename collision required report regeneration, not repeated scoring; its diagnosis is retained separately.

**Coverage limits of that historical smoke:** no eligible D3/D4 application-output population was present. The populated 100-case Korean packet and tone 30 per configuration were not completed, and actual owner review was unperformed. These historical shortfalls are not pending obligations of the owner-amended current D1/D3 execution, which explicitly opts out of those supplementary features. The full comparison and any applicable changed-judge calibration are not established by the smoke. Publication and issue closure require separate owner authority.

## Historical bounded real-input verification

The following observations predate local data loss. The source was reconstructed from the 86 preserved session/log files under `.data/recovery/issue6-session/`, not from an intact historical checkout or queue. The final historical candidate `6fac9017cf93db15fe85a9e7e8565aa311f95981` did **not** receive a completed independent-review verdict. These results are historical evidence, not current reruns.

The owner requested minimum working-path checks, not the full planned sample populations. Before data loss on 2026-10-21:

- Accepted #4/#5 reports at `342b13c` supplied two eligible VRCS2 segments. Two VRCLT1 continuous segments with indivisible cross-segment output and two reference-free output-check segments remained excluded. These inputs reuse one forty-second English development recording; this is not a distinct-application quality comparison.
- Seven v2 Astra calls completed: all three tiny sanity cases, two real ESA cases and two tone cases. The formerly failing nonempty translation received a valid structured result with exact anchored spans. Empty-output tone dimensions correctly remained null. The original v1 malformed responses and failed/null outcomes were preserved.
- Both exact selected MetricX XL shards passed their existing size/hash checks. The unchanged CPU float32 loader completed five predictions on the three sanity inputs and the same two eligible real segments. Existing Windows automatic pagefile management grew the allocation during inference; no OS setting, model, dtype or loader was changed. This establishes actual selected-model execution, not an evaluator-accuracy or memory-safety study.
- Fresh scoring invocations reused all seven judge results and all five MetricX results without additional calls or predictions. After integration with the accepted upstream code, actual quality cache/report commands and the profile-catalog command exited 0; all twelve stored result rows remained unchanged. The combined report retained the four exclusions and populated paired-score review data for the two eligible cases, without treating agreement as truth.
- The affected quality/protocol/transport/process suite passed **115 tests**, with no skips. The full repository suite was not rerun for this repair. Legacy queue status/report and strict frozen-prompt resume, Unicode/repeated-quote boundaries, raw-response immutability and prompt-version cache separation were covered.
- Configuration-level tone 30, calibration 100 and Korean-review 100 remain planned evaluation populations, not mandatory infrastructure smoke sizes. This D1-only input has no Korean review cases; the packet reports its shortfall and human review remains unperformed. No full comparison, actual judge-change calibration or Chinese/Japanese semantic review is claimed.

Historical evidence paths were `.data/issue6-span-repair/`, `.data/issue6-metricx-real/`, and `.data/issue6-final-repair/`. Their complete queues and canonical reports were not recovered. The preserved main-session record 1105 and child `quote-span-repair.jsonl`, `metricx-real-run.jsonl`, and `span-integration-review.jsonl` retain the execution records. Do not treat these paths as available current caches or reinterpret old scores against the regenerated Japanese main reference.

## Historical v1 checks and retained failure records

- Capture/scoring admission: an actual controlled `bench run` invocation exited 2 while the shared activity lock was held, without opening a capture stream. A fresh-process resume after release completed six synthetic stages. The focused activity/capture regression run passed 34 tests.
- The core queue/report behavior suite passed 20 tests; the real-bridge boundary suite passed 30. Controlled subprocess checks covered interruption, fresh-process resume, quota, invalid responses, actual-model changes, and report population joins without calling a service.
- Before v2, the integrated repository run passed **298 tests and 29 subtests**, with six skips: four unchanged missing-local-audio checks and two Torch-dependent checks in the lightweight environment. Both Torch checks passed in the separate MetricX environment's 23-test run.
- A built wheel installed in an isolated environment included the adjacent JavaScript bridge. Its installed `bench.exe` ran from outside the checkout import path, generated joined reports/review data, and performed a fresh cache-only scoring invocation: exit 2, six completed jobs, one unresolved job, and all eight call records unchanged. No new provider call was made.
- After lifecycle repairs, a rebuilt installed wheel completed five controlled synthetic jobs through the contained launcher. A fresh scoring invocation reused all five without adding a call; no provider was contacted.
- Eight actual selected-route calls on two public synthetic Chinese/Japanese-to-Korean assembled examples produced six validated ESA/tone results and two rejected wrong-language sanity responses. Both rejected attempts quoted 52-character spans starting at 0, but their end offsets were 51 and 50 respectively; the unchanged validator retained them as failures. Empty and unrelated sanity outputs received ESA 0 with major spans. **The wrong-language case remains unscored; no full three-case sanity pass is claimed.** No actual translator output or private corpus was sent.
- A fresh-process no-retry invocation reused all six completed judgments without adding calls and exposed the malformed result. One explicitly authorized same-prompt retry added a retained second failure, not a replacement score. The original invocation/replay predated a CLI exit-code repair and exited 0 despite accurate missing counts; the repaired command exits 2 for this state.
- The generated live-smoke report joined two source reports, retained all MetricX scores as null, produced no disagreement-ranked cases, and prepared two Korean reference cases with a 98-case shortfall. Calibration likewise lacked 98 cases; tone lacked 29 per available configuration. Human review remained unperformed.
- MetricX: 20 focused behavior tests passed. The pinned real tokenizer counted four synthetic positive/unrelated/empty/wrong-language inputs at 26/25/16/26 tokens; each retained null scores because selected weights were unavailable. A 1,608-token input was rejected as oversized before inference.
- The standard-MT5 projection matched the pinned official regression implementation exactly on four tiny random-weight cases. A real `from_pretrained` round-trip also matched. These are implementation/loader checks, **not actual selected-XL quality scores**.
- Earlier selected-XL execution was not performed: weights were absent, and free physical RAM was compared with their 13.94 GiB size. That observation did not establish an allocation failure; the physical-RAM-only blocker diagnosis is superseded by the actual mapped-loader execution above. No earlier tiny-model prediction is relabeled as a selected-XL result.
- At that checkpoint, accepted #4/#5 real report inputs were not yet available. The synthetic observations below their original evidence roots remain synthetic; the later real-input checks are recorded separately above.

The original task-local evidence roots were `.data/issue6-director/`, `.data/issue6-core/`, `.data/issue6-transport/`, and `.data/issue6-metricx/`. References to these and other historical roots below describe archived observations; their full contents are no longer available. The recovered sessions preserve initial failures and later corrections, not published benchmark data or current resumable state. No human Korean reference review is claimed.

Independent-review repair checks reproduced and corrected competing model-file selection and parent-only process termination. The old loader used different consolidated weights while retaining the verified-shard identity; the repaired runtime rejects that directory and adapter-config overrides. The old scorer left a controlled child and descendant alive after parent-only termination while its activity lock was available; the repaired Windows launcher terminated both. Twenty-three MetricX tests and eleven auth-free lifecycle tests covered rejection plus normal loading, completion, timeout, early-input failure, explicit resume and cache reuse.

Thirty-five core/join/repair tests covered preserved pauses, cached/changed-model sanity gating and duplicate-input calibration. An actual controlled CLI sequence preserved a quota pause across completed and unavailable MetricX-only work, rejected ordinary judging, then allowed explicit recovery without changing the original quota record. A generated calibration report retained all three sampled records despite only two distinct prompts; differences of 0, 10, and 10 yielded mean movement 6.6667 with zero missing pairs. This is controlled arithmetic, not real-model calibration. Repair evidence is under `.data/issue6-core-repair/`; no additional live judge calls or selected-XL predictions were made.

A further controlled CLI recovery probe interrupted state logically between a committed returned-model change and its pause-setting update. The durable model mismatch now takes precedence over an older quota pause: retrying the old expected model admitted zero calls. Selecting the returned model still required an applicable explicit limitation for its failed sanity result; a passing sanity result allowed progress without that limitation. Fresh invocations reused the completed records. Before/after regression and CLI evidence is under `.data/issue6-model-gap/`.

An integrated repair run initially failed one descendant-exit assertion. A retained original process handle proved that Windows job accounting could reach zero before the process handle signaled, rather than a reused PID causing the observation. Cleanup now closes the job's child-admission gate, retains handles whose job membership is verified, terminates owned processes, and waits for those exact handles to signal before returning. Fresh controlled CLI normal/timeout/parent-only termination checks and the final integrated suite passed without post-return sleep tolerances. The failed run and diagnosis remain under `.data/issue6-director/repair-suite-failure.json` and `.data/issue6-transport/exit-signal-diagnosis/`.
