# Usage costs and service conditions

`bench costs` reconciles permitted local evidence for [R5 #19](https://github.com/kapitalismho/vrc-translator-bench/issues/19). It binds a frozen [R4 common result](quality.md#input-and-result-bindings) to a separate cost evidence revision. It never calls a provider, opens billing accounts, launches applications or changes quality/time originals. Public presentation and R6 assembled admission remain separate work.

The active specification is **`schema_version: 2`** and the output is **`r5-cost-evidence-v1`**. The old `version: 1` specification and chunk/sentence `denominators` are not an alternate normalization path. Historical captures remain readable only as explicitly historical evidence; they do not acquire invented episode identities or become new benchmark results.

## Run

Python 3.11+ and the standard library are sufficient:

```powershell
python -m bench.cli costs --spec tests/fixtures/costs/synthetic-spec.json --output .data/costs/synthetic.json
python -m bench.cli costs --spec tests/fixtures/costs/real-missing-spec.json --output .data/costs/real-missing.json
```

The first specification contains invented source-shaped usage and prices. The second binds preserved actual VRCS2 development-capture derivatives but no app billing export. Neither establishes measured app billing. Exit 0 means an artifact was generated or the identical revision was reused, not complete billing; invalid inputs exit 2. Inspect status, coverage and reasons rather than the exit code alone.

Keep private specifications and logs in ignored local storage. Top-level paths resolve relative to the specification. Embedded capture paths resolve relative to the manifest; absolute paths also work. Output and its atomic `.tmp` sibling cannot alias consumed inputs, linked capture/reference artifacts, the common report or prior revisions, including existing hard links. Existing output is reusable only for identical evidence; changed evidence requires a new revision and destination.

## Input specification, schema version 2

| Field | Meaning |
|---|---|
| `schema_version` | Required integer `2` |
| `revision` | Required safe `id`; optional `previous: {path, sha256}` binds the prior cost artifact |
| `mode` | Default `episode`; `historical_evidence_only` forbids episode normalization/common-report claims |
| `common_report` | Required `{path, sha256}` in episode mode; R4 `schema_version: 1`, `kind: "episode_quality"`, `report_version: "r4-episode-quality-v1"` |
| `synthetic` | Identify calculation fixtures; synthetic input cannot establish actual measured billing |
| `manifests` | Observed capture artifacts, with unique source `id`, `path` and derivative `export_provenance` where applicable |
| `windows` | Explicit observed pass windows with run/profile/episode/pass/attempt/role identity and evidence |
| `timelines` | For standalone inputs, `{episode_id, artifact: {path, sha256}}`; artifact carries matching `episode_id` and positive `timeline_seconds` |
| `components` | Complete named service/provider inventory, treatment and selected-window coverage |
| `sources` | Permitted selected provider records, PP logs or submitted-audio intervals |
| `price_tables` | Dated exact-model token/audio rates; no default prices or network lookup |
| `consumption_summaries` | Optional inspected, hash-bound retained production/TTS/judge consumption; never app billing |
| `evidence_files` | Optional `{id, path}` supporting files retained by content hash |

Use non-secret IDs and aliases. The common report owns planned episodes, source identity, profile/measurement condition and selected role attempts. Existing optional population/role `cost_binding_id` values are carried forward; they are not permission to attach a different run or pass. A missing selected role stays missing. Cost processing neither rejudges nor renormalizes quality weights.

### Capture and standalone bindings

Schema-2 Runner manifests supply `run`, `work.profile/episode_id/pass_id`, attempt identity/state and role routing. Cost ingestion verifies trace checksums and derives observed input from callback frames/sample rate and the retained wall/monotonic mapping. The frozen episode frames/rate supplies the logical timeline; an attempt wall duration is not a substitute. Separate attempts, resumed history, incomplete input and invalid attempts remain visible.

Standalone windows require `id`, `run`, `wave`, `profile`, `episode_id`, `pass_id`, `attempt_id`, `roles`, `purpose`, `state`, timezone-aware `start`/`end`, observed `replayed_seconds`, `input_complete`, and `evidence`. Their `role_bindings` map each role to the SHA-256 of its canonical R4 selection. A standalone timeline is an explicit hash-bound operator claim, not automatically independently measured audio. Do not manufacture bindings for historical captures.

Active window bounds include the evidenced observation interval. Request-start attribution uses those bounds, not an implicit extra 30 seconds. Replay seconds remain separate from observation/preparation time. Only historical stage-manifest evidence retains the former playback-end +30-second rule. Coarse or overlapping windows do not authorize nearest-window attribution.

Historical mode retains stage-manifest attempt histories and actual callback windows without an R4 join, logical-episode rate, or sentence denominator. Public derivatives require `export_provenance`; derivative hashes must match that record rather than original private-file hashes. A derivative is not a recovered original ledger or resumable run directory.

## Provider CSV/JSON records

A `provider_export` source requires `id`, `path`, `provider` (`openrouter` or `qwen`), `format` (`csv` or `json`), and `fields` mapping normalized names to inspected export columns/properties. JSON `records_path` selects the record array; nested properties use dot notation. `constants` may supply established values, not guesses.

Normalized fields include `request_id`, request `start`/`end`, `model`, `upstream_provider`, `key_alias`, `cost`, `currency`, `input_tokens`, `cached_tokens`, `output_tokens`, `reasoning_tokens`, `audio_seconds`, `audio_start`/`audio_end`, `product_retry`, and scope `run`, `wave`, `profile`, `episode_id`, `pass_id`, `role`, `attempt_id`, `window_id`, `ledger`. Missing values remain null. Request start is not completion/export time or source-audio time. Provider-returned identities cannot be replaced by requested models. Map account/key identifiers to inspected non-secret `aliases.key_alias`; `aliases.model` may normalize documented labels.

Every source requires:

- `permitted: true` and publication-safe `selection_evidence`.
- Either inspected `benchmark_only: true` or `select` with allowed raw mapped values. Filtering happens privately before aliasing and normalization.
- For attributable provider billing, `isolation: {verified: true, evidence: "..."}`. A planned sole consumer, separate key or sequential wave alone is not evidence of workload isolation.

`scope` and `component` narrow only independently evidenced identity; never use them to choose arbitrarily between ambiguous consumers. Default `granularity` is `request`. Minute/hour/day records retain their bucket boundaries, native currency and coarse scope. A numeric coarse amount requires scope/isolation evidence and cannot be divided among episodes. USD totals do not silently convert other or unknown currencies.

These are operator-mapped inputs, not a claim of validated current native OpenRouter/Qwen export schemas. Inspect actual columns, units, timestamp semantics, taxes/discounts, rounding/minimums and completeness before mapping a real export. Keep unestablished billing conditions explicit.

### PuriPuly diagnostics

`kind: "pp_log"` reads the production `[Diagnostic][LlmLatency]` grammar. Configure `session`, `process_id`, fixed-offset `timezone` (for example `+09:00`), `component`, `start_basis` (`network_ms` or `attempt_ms`) and `timing_evidence`. PP logs require an inspected benchmark-only session/process excerpt. Split process restarts and UTC-offset changes; counters can restart. Optional `provider_aliases` maps observed provider labels.

`attempt_end` carries observed tokens and actual/requested model/tier. `request_end` is logical request identity, not a second charge. Error/cancelled attempts remain; `none` means unknown. Known sums retain observed-call counts so partial usage cannot masquerade as complete. Start is reconstructed from completion minus the explicitly selected duration, with unknown logging delay disclosed. No native provider generation ID or key alias is invented. The inspected grammar originated in PuriPuly revision `38cba9735c5bee2325cd7a4e528f15a466f886f4`; it is not evidence of a new empirical PP billing run.

### Submitted ASR audio

PP recognition terminal counters do not establish complete Gemini network submission: deduplication and a separate streaming path prevent that inference. Do not sum payload and terminal counters, substitute replay duration or infer audio from transcript length.

`kind: "submitted_audio"`, `basis: "vad_passed_submitted"` accepts evidenced actual submitted intervals. Map timezone-aware request `start` separately from numeric source `audio_start`/`audio_end`; duration comes from source bounds, not request wall time. Identify genuine resubmissions separately from duplicate rows. VAD alone is not submission proof. Alternatively, `basis: "diagnostic_audio_sent"` accepts mapped `audio_seconds` from an evidenced complete send ledger. Without either source, ASR usage remains unknown.

## Components, access and prices

Components declare `id`, `profile`, `provider`, `treatment`, optional actual `models`, `key_aliases`, `upstream_providers`, `price_table`, and `coverage: {window_ids, complete, evidence}`. Coverage is an operator assertion, not independently certified export completeness. Missing identity makes attribution conditional.

`services` contains `translation`, `asr`, or both. Complete app totals require both services and every declared component. An all-in-one component requires `services_evidence`. PP1 requires OpenRouter translation plus separate Gemini ASR; PP2 requires subscription translation plus separate Gemini ASR. Do not combine or relabel those obligations. A paid route cannot become free by changing a requested model suffix.

| Treatment | Meaning |
|---|---|
| `provider` | Attributable actual export amounts; internal calculations and reconciliation differences stay separate |
| `usage` | Usage × applicable dated rate; calculated, not actual billed cost |
| `subscription` | Access condition with null per-request actual fee; supplementary API equivalent is never the subscription charge |
| `free` | Zero only with complete selected-window evidence and covering `access.observed_eligible`, `access.evidence`, `access.window_ids`; conflicting positive charge prevents complete zero |
| `unknown` | Null with `missing_reason`, never free |

`access` retains condition, quota, observed eligibility, evidence, selected windows and `limit_status` (`reached`, `not_observed`, `unknown`). Supported quota fields are `unit`, `observed_limit`, `remaining`, `period`, `reset_at`. `scope_start` and `reached_at` can establish elapsed minutes to a limit; unknown is not infinite. Preserve dates and account/project scope across waves.

Price tables require `id`, exact `provider`/`model`, `date`, timezone-aware `valid_from`/`valid_until`, `currency: "USD"`, and `evidence`. Exactly one table must apply at request start. Token tables use `basis: "tokens"`, `per_tokens`, `rates` (`input`, `cached`, `output`, optional `reasoning`) and explicit containment booleans `input_includes_cached`/`output_includes_reasoning`. Contained tokens are charged once. Missing categories or inconsistent containment remain unknown. Audio tables use `basis: "audio_seconds"`, `per_second`. These calculations do not establish rounding, minimums, tax or discounts.

## Attribution and reconciliation

Identified duplicate requests and repeated physical rows collapse with provenance. Conflicting alternatives remain excluded and keep affected totals uncertain. A missing request ID does not make possible cross-source copies additive. Distinct product-billed retries remain separate charges, including requests in the evidenced observation tail. A harness replay is a separate attempt/purpose, not a product retry.

Aggregate/detail overlap cannot produce an additive amount. Coarse amounts retain `known_export_amount`, native currency, scope/candidates and isolation uncertainty. Selected unmatched rows remain in `records`; unexpected model/upstream identity retains potential candidates rather than disappearing from affected coverage. Do not subtract uncertain PP estimates from a shared bill and assign the remainder to VRCS2.

## Report fields and denominators

The cost revision retains `common_report`, `revision`, `provenance`, dated `price_tables`, observed `windows`, attempts, selected normalized `records`, component/profile summaries, `coarse_costs`, `populations` and separate `ledger_groups`.

For each bound population:

- `cost` and `per_input_hour` require actual attributable charges or evidenced free access for the complete selected app inventory.
- `calculated_cost` and `calculated_per_input_hour` explicitly distinguish usage-based calculations; they are not actual billing when any component is calculated.
- `logical_episode_seconds` counts each frozen episode timeline once, including original/declared inserted gaps but excluding preparation and observation tail.
- `physical_replay_seconds` retains selected physical pass duration; `submitted_role_timeline_seconds` additionally distinguishes simultaneous role streams.
- Both VRCLT and Kikitan T1 pass charges enter the numerator. Two 60-second passes with $0.01 and $0.02 charges mean $0.03 / 60 seconds = **$1.80/input hour**, not $0.90. These are illustrative values, not measured prices.
- Full selected main input is required for a comparable normalized rate. Missing roles/components and partial/invalid input preserve known subtotals but not a complete rate. Product no-output is not removed merely because it failed translation.
- Quality type weights, reference sentences, successful outputs and submitted ASR audio seconds do not replace the logical timeline denominator.

`ledger_groups` separates main, repeat, preparation, harness-retry and harness-invalid work. Production, TTS and judge accounting never enters the app input-hour numerator. Component and profile subtotals retain incomplete observed amounts; all-unknown stays null. Subscription equivalents remain supplementary.

Optional `consumption_summaries` are restricted to `production`, `tts` or `judge`. Each requires permission, inspected selection evidence, a hash-bound artifact, currency and an explicit field mapping for `known_subtotal`, `total`, `unknown_calls`. They report retained consumption summaries, not native provider exports or cash/credit proof. Unknown calls prevent a complete total. Referencing the same generated TTS input for multiple profiles does not multiply production cost.

## Later owner billing evidence

1. Keep the common R4 report, selected captures/references and prior cost artifact unchanged.
2. Inspect the permitted owner export locally. Establish request/time/model/alias scope, native currency, coverage and isolation; preserve unresolved ambiguity.
3. Create a new schema-2 specification with a new `revision.id`, `revision.previous` containing the prior artifact path/hash, and the **same** frozen common-report hash.
4. Add selected local sources and applicable dated pricing evidence. Do not replace missing bills with an estimate or rewrite quality/time to make the join work.
5. Run `bench costs` to a new output path and inspect actual versus calculated totals, missing components and populations. Identical re-ingestion is idempotent, not another charge or revision.

The revision records its evidence identity and previous linkage. Later billing is a separate evidence update, not permission for new provider usage, app reruns or account scraping.

## Retained evidence and exact gaps

The historical VRCS2 fixture retains four attempts and distinct 10-second output-check/40-second development windows. It lacks permitted authenticated OpenRouter records, returned model/upstream/key identity, complete selected-run coverage/isolation and Gemini project-tier/usage or a complete submitted-audio ledger. Its costs remain null. Capture export provenance is not billing evidence. Historical measurement integrity holds remain in force.

No ingestible authenticated translation-app billing export was found in the inspected checkout. This bounded discovery does not claim that the owner has no export elsewhere. Later permitted owner logs are the prerequisite for measured app-billing reconciliation, not for implementing this path.

Real **production consumption** does exist in [`corpus/r3/status.json`](../corpus/r3/status.json): known pilot subtotal $0.1151360 and main subtotal $0.1444215, combined $0.2595575. Pilot-01 and main-09 accounting lookups returned HTTP404; complete totals remain null. Cash/credit, fees, taxes/FX and human/editing cost are unknown. Referenced private `.data/r3` receipts are not present in this checkout; the retained summary is not a newly ingested authenticated export. No lookup is repeated for cost-plumbing verification.

## Publication boundary

Reports omit raw input paths, raw provider rows and provider request IDs. Source IDs/hashes, normalized fields and hashed identity preserve local traceability, not automatic anonymization. Operators must inspect aliases, model/quota/evidence strings, selection and output. Do not publish credentials, complete private exports, unrelated activity or private account identifiers. Preserve originals locally and publish only permitted inspected excerpts. Electricity, hardware and setup are not silently folded into app usage totals; separate production/access conditions remain visible.
