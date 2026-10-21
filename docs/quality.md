# Blinded translation-quality scoring

This is the automatic quality layer for [issue #6](https://github.com/kapitalismho/vrc-translator-bench/issues/6). It consumes the [issue #5 report contract](metrics.md), not application ASR as reference text. Scoring infrastructure and synthetic checks do not establish a completed application comparison. The planned judge is **GPT 6 Astra through Sign in with ChatGPT**; no API-paid fallback is provided.

## Working evaluation choices

Freeze these choices with the comparison revision in #8. They are implementation defaults, not independently validated measures of translation accuracy.

- ESA receives the source reference, target language, two earlier unscored reference turns, and interpreted final output in display order. That output already includes temporally assigned unaligned output. Preserve #5 exclusions, reconstruction uncertainty, partial references, and automatic Japanese-reference limitations.
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

New preparation generates v2 prompts. Use a **new root** to adopt this repair; `prepare` rejects an existing v1 root rather than rewriting its frozen protocol. Existing v1 queues remain readable and reportable, and `score` resumes their original prompts with the strict v1 offset decoder. Their failed responses are not reinterpreted as successes. Plan binding, per-job prompt version/hash and cache identity keep the two protocols separate.

A normal repeated scoring invocation reuses completed cache entries. Failures, quota pauses, interrupted/unknown calls, and malformed or missing responses are not successful judgments. Inspect `quality status`, resolve the cause, and explicitly pass `--retry-unresolved` to attempt unfinished calls again. Each attempt and its raw response remains available. A retry may make another service call when the previous call's terminal outcome was unknown; it is not proof that the earlier call was never admitted.

Judge `score` invocations exit 2 when retained failed, blocked, or unresolved judgments remain, even if some requested work completed. Independent `--metricx-only` exits according to its requested local outcomes: completed returns 0; unavailable, failed, oversized, or unresolved returns 2. It preserves the judge's quota/model-change/sanity pause and does not authorize judging to resume; `metricx_outcomes` and `paused` report these separate states. Inspect counts and `quality status`; exit 0 is not evidence of full planned benchmark coverage. Generated report call records contain `raw_artifact` pointers into the queue's `quality.sqlite`; retain that database with the reports. `quality status` exposes the full raw history.

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

Current raw responses, frozen plan, reports, commands and row-preserving reuse proofs are under `.data/issue6-current-smoke/`; start with `execution-report.json`, `quality.sqlite`, `quality-report.json` and `korean-review.json`. Runtime setup and exact payload checks are under `.data/issue6-runtime/setup-evidence.json`; controlled CLI observations are under `.data/issue6-control-smoke/evidence.json`. A local evidence-wrapper filename collision required report regeneration, not repeated scoring; its diagnosis is retained separately.

**Remaining evaluation obligations:** no eligible D3/D4 application-output population is present in these inputs. The populated 100-case Korean review packet therefore remains unavailable; packet-generation capability is not packet completion. Tone 30 per configuration, the full comparison and any required changed-judge calibration remain later evaluation work, not results of this smoke. Actual owner review is separate and unperformed. PuriPuly execution remains deferred. This recovery does not authorize publication, pushing, PR creation, merging or issue closure.

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
