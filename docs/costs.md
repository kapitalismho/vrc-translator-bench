# Usage costs and service conditions

`bench costs` implements local cost processing for [issue #7](https://github.com/kapitalismho/vrc-translator-bench/issues/7). It reads permitted selected usage records, PuriPuly diagnostic logs and observed run windows, then writes a separate JSON report. It never calls a provider, opens billing accounts, runs applications or changes raw captures. Public chart presentation and the full dated comparison remain downstream work.

## Run

Python 3.11+ and the standard library are sufficient. From the repository root:

```powershell
python -m bench.cli costs --spec tests/fixtures/costs/synthetic-spec.json --output .data/costs/synthetic.json
python -m bench.cli costs --spec tests/fixtures/costs/real-missing-spec.json --output .data/costs/real-missing.json
```

The first example uses invented prices and source-shaped synthetic records, not an authenticated export. The second consumes preserved, redacted **actual VRCS2 development-capture derivatives**. It has no provider records: costs and normalized costs remain null. Exit 0 means the report was generated, not that billing evidence is complete. Invalid inputs exit 2. Review component statuses and reasons.

Copy a specification into your ignored local data directory for the full dated run and update its relative paths. Top-level source, manifest, evidence and export-provenance paths resolve relative to the specification, not the current directory. Embedded attempt trace names and `manifests[].traces` overrides resolve relative to the manifest directory; absolute paths also work. Output cannot replace an input, a manifest-linked raw artifact (including skipped control traces and streams), or its atomic-write temporary path. Do not commit private specifications, logs or complete billing exports.

## Input specification, version 1

The executable examples are the compact schema reference. Top-level fields:

| Field | Meaning |
|---|---|
| `version` | Required integer `1` |
| `synthetic` | Explicitly identify synthetic calculation examples; not evidence that a run occurred |
| `windows` | Explicit observed windows: `id`, `run`, `wave`, `profile`, `chunk`, `kind`, `population`, `state`, timezone-aware `start`/`end`, and `evidence` |
| `manifests` | Existing runner captures: `id`, `path`, optional `export_provenance`, `populations` mapping zero-based stage numbers to labels, optional `traces` mapping attempt IDs to trace paths |
| `components` | Named provider/access components, described below; enumerate every service needed for the profile |
| `sources` | Selected provider records, PP logs or submitted-audio intervals |
| `price_tables` | Dated model-specific token/audio rates; no default or inferred current prices |
| `denominators` | Explicit observed population, window/component IDs, replay seconds, reference sentences and evidence |
| `evidence_files` | Optional `{id, path}` supporting files retained by content hash only |

Identifiers and aliases must be non-secret. Use distinct window IDs for different runs, attempts and replays. `population` separates development, general, stress, repeats and nonspeech; do not combine them into an undisclosed conversation denominator.

### Run windows

Manifest ingestion joins `attempts.work_id` to `work.id` and the indexed plan stage. It preserves attempt state, number, resumed status and separate setup/direction history. It reads the attempt trace and derives replay duration from contiguous submitted callback source frames divided by the stage sample rate, **not** planned duration or attempt wall length. Missing traces/timing stay missing; no planned playback is substituted.

The wall-clock playback start is derived from the trace's wall/monotonic anchor and DAC timing in the same clock session. This is a derived UTC mapping, not a directly logged provider timestamp. `actual_dac_observed` and `window_basis` disclose the boundary. Interrupted/invalid attempts are not silently replaced by successful later attempts. Select the actual appropriate denominator subset explicitly.

For public capture derivatives, supply `export_provenance`. Embedded manifest checksums refer to native originals; the export provenance supplies the derivative checksums that must match the files being read. A derivative is not a recovered original ledger or a resumable run directory.

### Provider CSV/JSON records

A `provider_export` source requires `id`, `path`, `provider` (`openrouter` or `qwen`), `format` (`csv` or `json`), and a `fields` mapping from normalized names to actual export column/property names. JSON `records_path` is an optional sequence of object keys leading to the record array; nested field properties use dot notation. `constants` can supply normalized values established for the entire selected excerpt, not guesses.

Normalized names are `request_id`, `start`, `end`, `model`, `upstream_provider`, `key_alias`, `cost`, `currency`, `input_tokens`, `cached_tokens`, `output_tokens`, `reasoning_tokens`, `audio_seconds`, `audio_start`, and `audio_end`. Missing fields remain null. `start` must mean **request start**, not completion/export time or audio-source time. If the actual export does not establish that field, leave it missing. Provider-reported actual model/upstream identity must not be replaced by the application's requested model. Map credential/account/key identifiers to inspected non-secret aliases with `aliases.key_alias`; `aliases.model` can normalize documented model labels. No foreign-exchange conversion is performed; supported report totals use USD, while other currencies remain unresolved.

Every source requires:

- `permitted: true` and publication-safe `selection_evidence` identifying the operator's inspection.
- Either `benchmark_only: true` for an inspected benchmark-owned excerpt, or `select` mapping normalized field names to allowed **raw mapped values**. Filtering occurs privately before aliasing and normalization; unrelated rows do not enter the report.
- For attributable provider costs, `isolation: {verified: true, evidence: "..."}` documenting actual account/workload isolation. A planned sole consumer, successful translation, separate key or sequential wave is not this evidence.

`scope` can bind records to `{run, wave}` when supported. `component` can bind an independently identified component. Do not use these fields to choose arbitrarily between ambiguous consumers. Default `granularity` is `request`; for minute/hour/day exports supply their native granularity and explicit bucket start/end. Coarse records remain coarse even when only one chunk overlaps. A numeric attributable coarse cost additionally requires `scope_evidence`, both scope identifiers, and verified isolation evidence; otherwise only the known export amount is retained, with attribution unresolved.

The mapped format is deliberately not advertised as a verified current native OpenRouter/Qwen export schema. No authenticated benchmark export was available during implementation. Inspect the real columns, units, timestamp semantics, rounding and coverage before constructing the mapping. OpenRouter per-generation metadata and Qwen minute-level billing exports are documented in the [profile findings](profiles.md); documented availability is not demonstrated account export access.

### PuriPuly LLM diagnostics

`kind: "pp_log"` reads the production file-log shape:

```text
2026-10-20 21:00:01.000 [INFO] pid=42 logger: [Diagnostic][LlmLatency] attempt_end request_id=1 attempt=1 provider=openrouter model=synthetic/gemma actual_model=synthetic/gemma status=success attempt_ms=1000 network_ms=1000 input_tokens=1000 output_tokens=300 cached_input_tokens=200 reasoning_tokens=50
```

This line illustrates the grammar; it is not empirical usage. Configure `session`, `process_id`, explicit fixed UTC offset `timezone` (for example `+09:00`), `component`, `start_basis` (`network_ms` or `attempt_ms`) and `timing_evidence`. PP sources require an inspected `benchmark_only` session/process excerpt. Split logs across process restarts or UTC-offset changes; process-local request counters can restart. Optional `provider_aliases` maps observed provider labels to the component provider.

`attempt_end` carries tokens and actual/requested model/tier. `request_end` carries logical request identity and request duration; it is not a second usage charge. Logical requests and provider attempts are counted separately, retaining error/cancelled attempts rather than assuming they are unbilled. `none` is unknown, not zero. Known token sums include observed-call counts so a partial sum cannot be read as complete usage; when no calls expose a field, its known sum is null, while explicitly observed zero remains zero.

Both events are emitted at completion. Starts are reconstructed as completion minus the explicitly selected duration, labelled approximate with unknown logging delay. There is no native provider generation ID or key alias in these messages. `actual_model=none` remains unknown; the requested model is retained separately. The grammar was inspected in PuriPuly source revision `38cba9735c5bee2325cd7a4e528f15a466f886f4`, not validated against a new benchmark PP run. That source revision differs from the historical profile-discovery revision.

### Gemini ASR usage

The available PP source does not establish complete Gemini audio sent from its recognition terminal counters. Those counters measure successful per-turn input writes; deduplication and a separate streaming path prevent treating them as a complete network-send or billing ledger. Do not sum `payload_received` and terminal totals, substitute replay duration, or infer audio from transcript length.

The supported fallback is `kind: "submitted_audio"`, `basis: "vad_passed_submitted"`, with evidence of the actual VAD-passed submitted intervals. Map timezone-aware request `start` separately from numeric audio-source bounds `audio_start`/`audio_end` in seconds. The routine calculates audio duration from those source bounds, never from elapsed request wall time. Identify submissions uniquely, distinguish genuine resubmissions from duplicate export rows, and state coverage. A VAD decision without submission evidence is insufficient. Alternatively, `basis: "diagnostic_audio_sent"` accepts explicitly mapped `audio_seconds` from an evidenced complete diagnostic send ledger; the currently inspected PP Recognition counters do not qualify. If neither ledger is available, ASR cost remains unknown. Actual Gemini billable rounding/minimums remain unestablished.

### Components, access and prices

A component has `id`, `profile`, `provider`, `treatment`, optional actual `models`, `key_aliases`, `upstream_providers`, optional `price_table`, and `coverage: {window_ids, complete, evidence}`. Coverage is an **operator-supplied assertion**, not an independent proof of export completeness. Missing required model/key/provider identity makes attribution conditional.

Declare the component's `services` as a unique list containing `translation`, `asr`, or both. A complete profile requires both services; missing inventory leaves the profile total unknown while preserving independent component amounts. A generic all-in-one component covering both needs a nonempty explanatory `services_evidence`. PP1 requires OpenRouter translation and separate Gemini ASR; PP2 requires subscription translation and separate Gemini ASR. These obligations cannot be combined or relabelled. Declare all other required service components too; an operator inventory is not automatic discovery of an application's providers.

| Treatment/profile | Report behavior |
|---|---|
| `provider`: PP1 OpenRouter, VRCT3, VRCS1, VRCS2, VRCLT2 Qwen | Attributable provider amounts govern. Internal PP1 token calculations and provider-minus-internal difference remain separate, with call/price coverage and `reconciliation_coverage_equal` claim. No residual amount is automatically assigned to VRCS2. |
| `usage`: separately evidenced Gemini ASR | Usage multiplied by an applicable dated price; explicitly a usage-based calculation, not an invoice claim |
| `subscription`: PP2 translation | Subscription access marker; actual numeric cost remains null. Any dated token calculation is `supplementary_api_equivalent`, never an actual subscription fee. Add Gemini ASR separately. |
| `free`: observed eligible Index/free-tier components | Zero only with complete selected-window evidence and `access.observed_eligible: true`, `access.evidence`, and covering `access.window_ids`. A positive attributable provider charge contradicts this claim and remains an unknown conflict, never complete zero. |
| `unknown` | Null cost and `missing_reason`; use for unavailable usage/access evidence |

Current authority supersedes the original plan: VRCS2's paid OpenRouter Gemma route was accepted; there is no whole-profile free claim or authorized `:free` substitution. PP1–PP4 empirical execution remains owner-deferred. The active arrangement is sequential competitor waves, not historical W2 co-measurement. See [profile decisions](../profiles/evidence/issue45/decisions-and-candidate.json) and [wave decisions](../profiles/evidence/issue45/sequential-wave-decision.json). VRCLT2 is the sole planned Qwen-account consumer, but actual isolation must still be evidenced.

`access` retains `condition`, `quota`, `limit_status` (`reached`, `not_observed`, `unknown`), evidence and eligible windows. Structured quota fields are `unit`, `observed_limit`, `remaining`, `period`, and `reset_at`; other quota keys are omitted. With `scope_start` and `reached_at`, `minutes_to_limit` is the elapsed difference; an unknown or unobserved limit is not an infinite allowance. Retain the observation scope and date, including cumulative account/project quotas across waves.

Each price table has `id`, `provider`, exact actual `model`, `date`, timezone-aware `valid_from`/`valid_until`, `currency: "USD"`, and `evidence` identifying the inspected price source. A request needs exactly one applicable table at its start time. Token tables use `basis: "tokens"`, `per_tokens`, `rates` (`input`, `cached`, `output`, optional `reasoning`) and explicit `input_includes_cached`/`output_includes_reasoning` booleans. Contained tokens are charged once; without a distinct cached/reasoning rate, the containing category rate is used. Inconsistent containment or missing token categories stay unknown. Audio tables use `basis: "audio_seconds"` and `per_second`. No rounding/minimum investigation or current-price lookup is implied.

## Attribution and reconciliation

The working rule is inclusive: request **start** belongs to a candidate from playback-window start through **playback end + 30 seconds**. Playback end is not the later observation-tail or attempt end. Model, provider, bound run/wave/component and non-secret key aliases constrain candidates. Overlapping grace periods, shared keys, missing identities and absent account-isolation evidence remain ambiguous/conditional; first-match and nearest-window allocation are not used.

Identified repeated provider requests and repeated physical source rows are collapsed with their source references, independently of inspection wording. Conflicting normalized alternatives remain separate linked excluded records so each potentially affected consumer retains uncertainty. Possible cross-source copies cannot become additive merely because only one export exposes a request ID. Distinct identified calls remain separate. Aggregate/detail overlap excludes additive detail; overlapping aggregate buckets do not imply a known union total. Coarse export amounts remain in `coarse_costs`, with native granularity, candidate scopes, mixed-workload uncertainty and known export amount. An attributable wave/coarse cost is not a precise component/chunk amount. Do not add coarse and component reports together as an overall total.

All safely selected normalized evidence remains in `records`, including selected-but-unmatched rows counted by `unmatched_record_count`. Unexpected actual model/upstream identity on an otherwise matching provider/key/time retains `potential_candidates` and makes affected totals unresolved. A demonstrably different key does not contaminate an unrelated consumer's amount.

PP1 provider and internal amounts may differ because of coverage, actual model, usage semantics, price validity or billing rules. The report preserves both and their difference when comparable data exist; equal-coverage assertions are explicit. It does not certify a billing audit or resolve a shared-account remainder by subtraction.

## Report fields and denominators

`costs-v1` includes `provenance`, dated `price_tables`, observed `windows`, attempt history, selected normalized `records`, attribution candidates/exclusions, `components`, `profiles`, `coarse_costs`, and `denominators`. Component `status` distinguishes complete, partial, unknown and subscription. `known_subtotal` is not a complete cost. Profiles disclose `required_services`, `covered_services`, `missing_services` and `inventory_issues`. A profile total is null if its service inventory is incomplete or any declared component is missing, partial, subscription-based or covers a different subset.

Attempt `state` describes that individual attempt; `work_outcome` is explicitly the work item's final outcome, which may come from a later successful retry. Report `synthetic` is true if declared by the specification or any source, or imported playback explicitly has `actual_dac_observed: false`; a false top-level declaration cannot relabel those synthetic inputs as real.

A denominator names unique `window_ids`, `component_ids`, `population`, actual `replay_seconds`, `reference_sentences` and `evidence`. Default `scope: "profile"` requires the complete declared component inventory and both services, with complete costs on exactly that selected subset. Explicit `scope: "component"` permits a separately labelled `cost_kind: "component_subtotal"`; it is never a profile total.

Supplied replay seconds must agree with the sum of selected actual `replayed_seconds`, or observed explicit window durations where callback duration is unavailable. Contradictory positive values block normalization rather than overriding either source. The report retains supplied and `observed_replay_seconds`, `replay_seconds_consistent`, `window_populations`, and `mixed_populations`. Cost per replayed conversation hour is cost × 3600 / replay seconds; cost per 1,000 reference sentences is cost × 1000 / reference sentences. Zero/missing denominators remain null. Reference counts come from the relevant source/reference evidence, not OSC packet count. Keep source-specific human versus automatic reference limitations and partial-coverage exclusions visible. The command does not infer missing sentence counts or allocate account totals proportionally to playback.

## Observed verification and evidence gaps

The two CLI commands above were exercised through the repository's `bench.cli` entry point. The synthetic hand reconciliation produced:

| Synthetic quantity | USD |
|---|---:|
| Governing PP1 OpenRouter records | 0.005 |
| PP1 internal token calculation | 0.00235 |
| Provider minus internal | 0.00265 |
| ASR: ten submitted seconds | 0.001 |
| Complete example profile | 0.006 |
| Per replayed hour, with 20-second denominator | 1.08 |
| Per 1,000 reference sentences, with ten-sentence denominator | 0.6 |

These numbers are invented fixture arithmetic, not service prices or benchmark costs. The actual VRCS2 derivative produced separate ten-second output-check and forty-second development windows, retained four attempts, and used the explicitly evidenced nine native reference units for the development denominator. Its total and both normalized costs were null. That check establishes compatibility with existing capture artifacts and honest missing-cost reporting, **not measured billing reconciliation**.

After accounting-safety repairs, focused cost checks passed **95 tests**. Integration in a task-local Python 3.12 environment installed with `.[test]` passed **464 tests and 29 subtests, with six skips**: four require absent local AliMeeting audio and two require the optional `torch` dependency. Skips are not passes. Both examples also ran through that environment's installed `bench.exe` entry point and emitted the same arithmetic/missing-cost results with explicit service inventory and duration consistency. Earlier full-suite collection attempts in the global Python and existing shared check environment stopped because `soundfile` was absent; the isolated environment resolved that dependency without modifying the shared environment. No lint/type checker is configured or claimed.

No permitted benchmark-bound authenticated OpenRouter/Qwen export or PP empirical token/audio ledger was found in the inspected repository/evidence roots. Bounded local discovery is not proof that no account export exists anywhere. Existing profile findings explicitly record that authenticated exports were not obtained. A discovered private PP log was not inspected or repurposed: ownership, permission and run linkage were not established. No new provider call, PP execution, account isolation or free-tier entitlement was observed.

The unexercised empirical criterion is precise: supply permitted actual OpenRouter/Qwen records with model/key/time granularity and isolation evidence, and PP usage plus complete submitted-ASR evidence linked to an authorized short run. PP execution remains deferred unless the owner changes that decision. Current actual requested routes, returned identities, export completeness, Gemini tier, rounding/minimums and subscription allocation retain their separate known/unknown states. Do not close this evidence gap using synthetic examples or claim a measured total. The reusable routine can be applied to the later dated run without requiring that full run as a development prerequisite.

## Publication boundary

Reports omit input paths, raw provider rows and raw provider request IDs; source IDs, content hashes, selected normalized values and hashed identities retain local traceability. Selection and ID syntax are **not automatic secret redaction**. The operator must inspect aliases, model labels, quota/evidence strings, source selection and the final report. Never publish credentials, full private exports, unrelated activity or private account identifiers. Keep raw originals locally and publish only permitted inspected excerpts with the price dates, attribution rule, coverage, reconciliation differences and limitations needed to reproduce the stated calculation. Power, setup, hardware and TTS costs remain excluded.
