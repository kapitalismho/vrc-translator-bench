# Native-output benchmark implementation plan

## Authority and current checkpoint

The owner requested a reset from the work reached in historical issue 8, using [the final benchmark plan](benchmark-final-plan.md), a replacement issue set, and the existing **GPT/backend versus Claude/public-presentation** division. This document classifies the implementation and records the replacement outcomes. The final plan owns benchmark definitions; this document owns migration and delivery boundaries.

**The reset at `ad53f6eb0eda28724acb3f366ebd92b25e9cb3da` is complete and integrated into local `main`; it did not implement or run the new benchmark.** The owner subsequently authorized publication of R0–R10 and deletion of all original issues, including closed ones, but not pull requests. R0 is the program umbrella, not a request to repeat the reset. Start implementation with R1; source/rights investigation in R2 can proceed alongside it.

Starting state: `issue8-first-batch` at `fbab10a0455d91d5419d9673499d25b7ac86c566`; fetched `origin/main` at `1a5244a04d6a62e447a6ed888893f81a9eed9cf6`. The reset integrates the unmerged historical capture work rather than rolling it back. Pre-existing local final/redesign documents are integrated as the planning authority/history. Unrelated untracked traces and terminal-recovery drafts are not staged, deleted or rewritten.

### Published issue set

The owner-authorized replacement is published. **Start implementation at [R1 / #15](https://github.com/kapitalismho/vrc-translator-bench/issues/15); [R0 / #14](https://github.com/kapitalismho/vrc-translator-bench/issues/14) is the program umbrella**, not an unperformed reset step.

| Key | Published issue | Execution owner |
|---|---|---|
| R0 | [#14 — Integrated benchmark program](https://github.com/kapitalismho/vrc-translator-bench/issues/14) | GPT |
| R1 | [#15 — Native input/output and fourteen-profile comparability](https://github.com/kapitalismho/vrc-translator-bench/issues/15) | GPT |
| R2 | [#16 — Natural conversation, reading and EN/ZH T1 parents](https://github.com/kapitalismho/vrc-translator-bench/issues/16) | GPT |
| R3 | [#17 — Reviewed JA/KO T1 reconstruction](https://github.com/kapitalismho/vrc-translator-bench/issues/17) | GPT |
| R4 | [#18 — Quality, semantic waiting and report data](https://github.com/kapitalismho/vrc-translator-bench/issues/18) | GPT |
| R5 | [#19 — Logical-episode costs and billing revisions](https://github.com/kapitalismho/vrc-translator-bench/issues/19) | GPT |
| R6 | [#20 — Integrated pilot and production freeze](https://github.com/kapitalismho/vrc-translator-bench/issues/20) | GPT |
| R7 | [#21 — Dated comparison and public-safe evidence](https://github.com/kapitalismho/vrc-translator-bench/issues/21) | GPT |
| R8 | [#22 — Unified scorecard, charts and methodology](https://github.com/kapitalismho/vrc-translator-bench/issues/22) | Claude |
| R9 | [#23 — Recorded-output comparison video](https://github.com/kapitalismho/vrc-translator-bench/issues/23) | Claude |
| R10 | [#24 — PuriPuly reruns and bounded development experiments](https://github.com/kapitalismho/vrc-translator-bench/issues/24) | GPT |

- All eleven titles/bodies, open states, self-assignment to `kapitalismho` and exactly one existing label were read back. R9 uses `documentation`; the other outcomes use `enhancement`. No Project membership was returned and no implementation-start or completion transition was applied.
- All ten children are native sub-issues of R0. Twenty native blocking relationships match the completion-artifact map below; they do not prohibit earlier independent investigation or interface development. R8/R9 remain siblings; R10 is not a first-release blocker.
- Original issues **1–11, including previously closed issues, were deleted**, not merely closed. The all-state issue inventory contains only the replacement set, and all eleven original node identities return `NOT_FOUND`/null. Merged PRs **12 and 13 remain unchanged**.
- Original bodies, eleven comments and metadata are preserved only in `.data/issue-migration-native-output/original-issues.json`; the verification/relationship record is `.data/issue-migration-native-output/publication.json`. These local records are not published assets. Historical issue numbers elsewhere in this document identify the retired work, not executable dependencies.
- Because the reset code/docs have not been pushed, R0 carries a [complete approved protocol source snapshot](https://github.com/kapitalismho/vrc-translator-bench/issues/14#issuecomment-6406410375), including the owner-local API-key gate before any TTS request. Its LF-normalized UTF-8 SHA-256 is `6b6c21b91af1e8a66b57a12c317ef5042f53df905adc23efc1ef3dc5b37aeea8`. This publishes the same final-plan revision, not a second independently mutable protocol.
- This transaction publishes planning issues only. No TTS/provider call, benchmark execution, account/key change, code push or PR publication occurred. Future contract changes must reconcile the maintained plan and affected issue contracts explicitly.

### What “through issue #8” means

- Before replacement, issues #2–#7 were closed on their respective amended preparation/implementation scopes, while #1, #8 and #9–#11 were open. No linked Project items or repository Actions workflows were returned. The publication record above supersedes their page-existence/status information, not the historical implementation facts.
- The D1/D3 batch has substantial real capture and calculation evidence. The local state explicitly records `measurement_artifacts_complete__integrity_repair_required__owner_billing_pending` and `final_result_acceptance_hold: true`.
- Confirmed old analysis defects include incorrect source/output links, cumulative-output duplication, missing audible-speaker context, output-dependent scoring populations, and early harness intervention misrepresented as complete observation. Raw capture consistency does not validate those derived scores. Real product errors also remain; this is not a finding that every low score was a harness error.
- Preserve existing captures, scores, unavailable cases and the acceptance/billing hold. This reset does not fix historical scores, complete #8 or establish a new baseline.

The investigation's private source is `.data/issue8/batch-analysis-v1/discovered-analysis-issues.md`; it is not a clean-clone prerequisite. The findings needed for implementation are recorded in final-plan §6 and the evaluation acceptance criteria below. Do not publish the private report or raw app/billing logs automatically.

## Preserve, modify, retire

| Disposition | Current surface | Decision and reason |
|---|---|---|
| Preserve infrastructure | `bench/audio.py`, `storage.py`, `activity.py`, `adapter.py`, `gui_operator_adapter.py`, `osc.py` | Reuse actual playback/callback clocks, raw wire history, durable attempts, hashes, locks and process/observation ownership. OSC remains one transport, not the universal peer endpoint. |
| Preserve, then migrate in R1 | `bench/plan.py`, `runner.py` | Existing single-WAV/microphone/OSC stages are not episodes, synchronized T1 or split passes. Keep working infrastructure now; replace its old contract in place when the native path is implemented. The old watchdog is not new observation-opportunity proof. |
| Preserve evidence; migrate admission in R1 | `profiles/catalog.json`, `profiles/findings/`, `profiles/evidence/`, `profiles/output-checks.json` | Keep all 14 profile identities and historical bytes. Do not reset old failures or promote self readiness into peer readiness. The current inspector labels its findings historical and returns new-protocol unverified. |
| Preserve foundations; new orchestration in R4 | `quality_store.py`, `quality_transport.py`, `quality_process.py`, `quality_judge.py`, `quality_bridge.mjs` | Keep call/raw-response/cache/recovery storage and selected subscription transport/containment. Remove MetricX-specific store logic. These primitives are not a complete queue scheduler or new judge. |
| Preserve, then migrate in R5 | `bench/cost_inputs.py`, `costs.py` | Keep allowlisted log ingestion, attribution, dated Decimal prices, component completeness and unknown/subscription states. Replace old run/chunk/sentence denominators with episode/pass binding before new publication. |
| Preserve utility | `tools/export_pilot_evidence.py` | Keep separate derivative/hash/path-redaction export. It does not clear rights or sanitize arbitrary secrets. |
| Retire active analysis | All six `bench/metrics*.py` modules | Remove old sentence correspondence, SimAlign, delivery, FOL/LUL, 30-second assembly and old population composition. No aliases or compatibility adapters into the new metrics. |
| Retire active scoring | `quality.py`, `quality_prompts.py`, `quality_sampling.py`, `quality_report.py`, `quality_metricx.py` | Remove the old single-call ESA, D1–D6 mapping, old report join, tone/Korean sampling and MetricX. Do not retain an alternate evaluator solely to satisfy old tests. |
| Retire active corpus production | `prepare_english`, `prepare_chinese`, `prepare_japanese`, four `japanese_*` helpers, `index_corpus`, `check_corpus`, `prepare_nonspeech`, `prepare_profile_checks`, `prepare_gui_pilot` | Their AMI/AliMeeting/YODAS2 budgets, automatic Japanese references, old check clips and issue45 plans do not implement the selected episode corpus. New preparation reuses simple WAV/hash patterns, not a generic corpus framework. |
| Preserve immutable historical data | `corpus/**`, local `.data/**`, frozen plans/registries/caches/queues/scores and source snapshots | No deletion, regeneration, move or hash substitution. Old nonspeech assets may be rebound to C1 only after suitability/rights review; they do not improve quality or waiting scores. |
| Preserve historical implementation | Git revision `fbab10a0455d91d5419d9673499d25b7ac86c566` | Inspect former commands at their actual revision. Do not refresh old issue8 materializer hashes to run them against this reset. No second legacy runtime/package is introduced. |

Tests for removed products are retired with those products. Keep capture/resume/quiet/ownership, GUI observation, export, profile integrity, cost evidence and judge process/store behavior tests. Migrate process/store tests off the deleted scorer rather than dropping containment and recovery protection. Remove obsolete extras/entry points and update every active CLI/document consumer.

### Protocol and issue disposition

| Previous obligation | Replacement disposition |
|---|---|
| Six directions, 30-minute tracks and D1/D3-first accumulation | Superseded in this replacement roadmap by the final plan's two language pairs and five episode types. Unmeasured old directions are not claimed completed. |
| Universal microphone→chatbox OSC endpoint | Superseded by app-native translation outputs, mostly peer; VRCLT self/split-T1 exception stays explicit. No screen-rendering claim. |
| Sentence correspondence/delivery/FOL/LUL and old ESA/MetricX | Superseded, not repaired or renamed. New episode GEMBA-ESA and semantic-wait p50/p90 require new execution evidence. |
| Tone30, Korean100 and owner-review population gates | Already removed by the [recorded supplementary-scope amendment](../profiles/evidence/issue8/supplementary-scope-amendment.json); not completed evaluations and not restored. |
| All 14 profiles, original concurrent-wave intent, CPU-local benchmark conditions, first-attempt/failure visibility | Preserved. New routing and runtime admission must be established; no silent profile deletion, model substitution or serialization. |
| Claude public report and comparison video | Preserved as R8/R9, consuming native-output histories rather than old OSC-only score definitions. |
| GPT PuriPuly reruns and bounded ASR/segmentation development | Preserved as R10 follow-up, not a first-release gate and not authority to modify PuriPuly. |
| Historical rights, privacy, access and billing limitations | Preserved. Source selection is not rights-holder permission; a merge is not a paid-run or account-change grant. |

The owner explicitly authorized replacement publication and deletion of the original issue pages, not marking unmet work completed. Preserve their bodies, requirement-bearing comments and metadata in a local pre-deletion record; preserve linked artifacts and Git history. Publish the replacement set and record its actual relationships before deleting only the captured original issue IDs. Use the established `[GPT]`/`[Claude]` ownership convention, self-assignment and one existing type label per issue. Remote code push is separate from this issue-publication authority.

## Execution order and shared ownership

| Key | Owner | Observable outcome | Required input for completion |
|---|---|---|---|
| R0 | GPT | Integrated native-output benchmark program | R1–R9 for first release; R10 tracked separately |
| R1 | GPT | Usable native input/collection path and per-profile comparability decisions | Current profile/source evidence, small permitted development inputs, scoped runtime access |
| R2 | GPT | Frozen eligible natural-conversation/reading episodes and EN/ZH T1 parents | R1's actual input/output contracts before production |
| R3 | GPT | Reviewed JA/KO T1 reconstruction and production-cost report | R1 feasibility, R2 eligible parents, owner-configured API key and scoped usage approval, rights/review prerequisites |
| R4 | GPT | Auditable reconstruction, two-stage quality, semantic waiting and report data | R1 native examples/contracts; R2 representative references/checkpoints |
| R5 | GPT | Logical-episode costs and later evidence revisions | R1 episode/pass/run bindings; coordinate report contract with R4 |
| R6 | GPT | Actual integrated development pilot and production freeze | R1–R5, with pending billing allowed but no fabricated amounts |
| R7 | GPT | Dated main/repeat result package | R6 freeze and actual profile admission |
| R8 | Claude | Unified public report, audit views, two-axis charts and methodology | R4/R5 schema for development; actual R7 package for release |
| R9 | Claude | Chronological recorded-output comparison video | Preselected cleared R2/R3 clips and R7 histories |
| R10 | GPT | Separately dated reruns and bounded development experiments | An accepted R7 baseline; not a first-release blocker |

R1 is not a request to finish the entire corpus first. Resolve the minimum episode/role/pass/output/clock/outcome contracts there and exercise them on small permitted samples. R2 rights/source investigation can proceed in parallel, but main corpus and TTS production wait for the collection feasibility decision. R4/R5 can develop against bounded evidence while R3 completes. Do not split every parser/schema into a separate issue or add a standalone harness-certification program.

R1 owns shared capture contracts; R2 owns source/checkpoint definitions; R4 owns evaluated result fields/weights; R5 owns cost bindings/revisions. R8/R9 consume those contracts without recalculating them. Each implementing outcome updates its maintained docs and all affected callers. Frozen historical evidence is never a mutable implementation surface.

## Unresolved prerequisites and stop conditions

- **Kikitan:** actual peer capture targets VRChat process audio. Earlier experiment authority excluded running VRChat. The final plan identifies this prerequisite but is not permission to launch/operate it. R1 must obtain the specific runtime authorization or record the exact blocked row; no fake executable, generic player or microphone relabeling.
- **Collection:** full text and usable timing are separate admissions. A missing producer timestamp alone is not a reason to build invasive instrumentation; verify a useful observation interval. Real truncation, missing intermediate history, ambiguous roles and collector gaps remain substantive limits.
- **ASCEND T1:** verify both original sides and common timing before making parents. Insufficient eligible material blocks the fixed corpus freeze; it does not authorize synthetic English/Chinese parents or arbitrary gaps.
- **IngCrowd:** adoption is settled, but actual use-purpose/noncommercial compatibility, external-service input and public examples need rights review. Do not substitute another source silently.
- **Gemini 3.8 Flash TTS:** before any live request, including development generation, ask the owner to configure an appropriate Google Gemini API key locally for the selected model. Specify the actual configuration location, required project/model/billing access and proposed bounded usage. Wait for setup confirmation and scoped usage authorization; never request or expose the secret value in issues/chat/source/logs, borrow another app's credentials or substitute a provider. Both JA and KO still require actual content/listening/role-boundary review.
- **Judge:** use the selected existing Astra subscription route; no paid fallback. Real two-stage discrimination and bounded variability remain unmeasured.
- **Billing:** the owner will provide permitted logs later. Implement bindings now; retain pending/unknown cost without delaying otherwise valid quality/time reporting or inventing zero.

# Replacement issue contracts

## R0 — [GPT] Deliver the native-output conversation translation comparison

### Background and Goal

Replace the old six-direction OSC experiment with the approved peer-centered conversation benchmark while preserving historical evidence and explicit limitations. Execution agent: **GPT**; public presentation belongs to Claude in R8/R9.

### Scope

Own shared scope, dependency/decision accounting and integrated acceptance. The [final plan](benchmark-final-plan.md) is the sole authority for dataset choices, weights, channel exceptions, methodology and public claims. Preserve R10 as a separately tracked follow-up. The reset is already complete on local `main`; R0 coordinates the remaining work and R1 is the implementation entry point.

### Requirements

Use the R1–R10 index above. Preserve all 14 profiles, native-output/no-modification/no-screen-capture measurement, two language pairs, required T1 and reading, GEMBA-ESA, separate p50/p90 and evidence-bound costs. Do not silently restore superseded six-direction or supplementary-evaluation obligations.

### Completion Criteria

First release has an actual dated R7 package, R8 public report and R9 cleared video, with reported coverage, failures, method limits and cost status traceable to common evidence. Missing required weight prevents a complete integrated-score claim. Child closure alone is not integrated acceptance. R10 remains visible until separately completed.

### Decisions and Evidence

The reset classification above distinguishes reusable infrastructure from accepted measurements. Historical issue 8 evidence retains its integrity/billing hold regardless of deletion of its issue page. The owner authorized publication of this set and deletion of the original issues; paid runs, credential/account changes, source-rights clearance and remote code push remain separately scoped.

## R1 — [GPT] Establish native-output comparability for all fourteen profiles

### Background and Goal

The retained runner captures one self input and chatbox OSC. Deliver actual episode-native input/collection and a defensible admission decision for each profile before expensive corpus production.

### Scope

Migrate the current runner/plan/profile admission in place; implement one primary read-only native collector per app family using final-plan §6. Reuse playback, persistence, lifecycle and raw evidence foundations. No application patches, OCR, hooks, TLS interception or compatibility evaluator.

### Requirements

Own the episode/role/pass, native-output, clock/gap and outcome contracts consumed downstream. Support ordinary peer input, simultaneous self/peer T1, and the approved VRCLT all-self/two-pass exception with separate origins and one logical episode. Preserve actual model/source/target/device/endpoint stages and W1–W4 concurrency intent. Keep collectors active through the common last-input-speech +15 seconds; early harness intervention is invalid, not product no-output. Preserve attempts and independent app/input/collector continuity evidence.

### Completion Criteria

Small actual authorized inputs establish per-profile text completeness, revisions/repetition, roles, silence/tail behavior and timing limits for both pairs and required directions. Exercise a real supported positive path and relevant incomplete/invalid paths; connection or one packet is insufficient. Publish quality/time admission separately for every profile, with exact blockers. Verify restart/resume preserves original evidence and no same-role audio is time-compressed. Unavailable required route/access remains blocked, not a fabricated pilot pass.

### Decisions and Evidence

Final-plan §§4.7, 6 and 10 govern. PuriPuly peer ASR is separate, VRCS T1 shares ASR language, VRCT peer direction is reversed, Kikitan needs actual process audio, and VRCLT self OSC/log timing differs. Resolve Kikitan authorization before live operation. Existing self pilot evidence is reusable history, not new admission.

## R2 — [GPT] Freeze eligible natural-conversation and human-read episodes

### Background and Goal

Create actual source-linked episode inputs for the selected two-pair protocol; old AMI/AliMeeting/YODAS tracks are not substitutes.

### Scope

Prepare ASCEND EN/ZH P1–P3/T1 parents, IngCrowd JA P1–P3, FLEURS EN/JA P4, development cases and C1 candidates. Preserve historical corpus bytes. R3 supplies synthetic JA/KO T1.

### Requirements

Implement final-plan §§2–5 selection, fixed cell counts/weights, audible references, context-versus-translation scope, original-group split, nonoverlapping intervals, role buffers and pre-result semantic checkpoints. Pin source revision/split/IDs/files/licenses and actual audio/reference hashes. Prove EN/ZH T1 common origin, both sides and substantive translation targets before freezing R3 parents. Select permitted public-example candidates before viewing app results.

### Completion Criteria

Inspect actual representative WAV/EAF/transcript content and source-to-playback mappings, not only manifest shape. Verify sample positions/gaps, decoded hashes, no unintended role leakage or duplicate main/development ancestry, and all required natural/read cells. Publish rights/review levels and exact unavailable cells. Insufficient source eligibility or use rights blocks production freeze without replacing material or redistributing weight.

### Decisions and Evidence

R1 supplies input/output contracts and feasibility before main production. IngCrowd adoption is settled; noncommercial and external-service/publication permissions are not assumed. FLEURS shared sentence IDs and ASCEND parent groups remain dependence units. Existing nonspeech assets need new C1 suitability binding and do not add quality/time credit.

## R3 — [GPT] Deliver reviewed Japanese/Korean T1 reconstructions

### Background and Goal

Reconstruct the frozen EN/ZH T1 cases as faithful Japanese/Korean conversations with usable role-specific audio.

### Scope

Use **Gemini 3.8 Flash TTS only** for JA/KO T1. Own scripts, actual generation, bilingual review, role timing and separate production-cost/quality reporting; do not synthesize IngCrowd general conversation or English/Chinese parents.

### Requirements

Follow final-plan §§4.3–4.6 and 11.3: whole-dialogue request per episode first, two stock voices, four separate development dialogues and bounded method checks, documented complete-turn fallback only when necessary. Preserve negation/numbers/conditions/repair, parent identity, failed takes and regeneration causes. Use actual generated timing, equal-length role buffers and frozen hashes; do not concatenate WAV file bytes or compress silent role intervals.

Before the first live TTS request, including the four-dialogue development pilot, ask the owner to configure an appropriate Google Gemini API key locally for `gemini-3.8-flash-tts`. State the exact environment variable or secret-setting location used by the implementation, required model/project/billing access, proposed calls and cost cap. Wait for the owner's setup confirmation and scoped usage approval. Never request the key value in issues or chat, commit/log it, reuse another app's credentials without approval, or silently change provider. Missing configuration/access blocks generation, not independent script preparation.

### Completion Criteria

Record secret-free owner setup confirmation and usage authorization before any generation. Actual JA and KO content/listening and boundary review supports the adopted method before nine main reconstructions are frozen. Show role-buffer sum/sample integrity and genuine speaker/content assignment separately. Report first-pass/rejected/adopted outcomes, API consumption, cash/credit, review work and unknown costs. Unavailable credentials, generation authority or bilingual review remain explicit prerequisites, not synthetic-quality passes.

### Decisions and Evidence

R2 eligible parents and rights precede production; R1 feasibility precedes corpus spending. Model choice is approved, but spending/account/terms actions need their scoped authorization. Independent ASR is advisory and does not certify pronunciation/naturalness.

## R4 — [GPT] Produce auditable episode quality and semantic-wait results

### Background and Goal

Produce useful quality and waiting outcomes without the old sentence-linking, window-allocation and cumulative-repetition artifacts.

### Scope

Implement native history reconstruction, two-stage GEMBA-ESA, checkpoint decisions, weighted aggregates and the versioned result data consumed by costs/presentation. Reuse the retained store/transport, not old prompts, scores or alignment caches.

### Requirements

Apply final-plan §§6–10 and 13. Preserve supported append/replace/clear history and raw citations without guessing native IDs. Judge each target role independently: errors/minor-major first, then direct 0–100 score in a separate conversation; retain upstream/prompt/input/model identity and validated exact quotes. Acquire measurement exclusion, retain unresolved calls, and separate cache identities by stage and changed inputs. Use only then-available source/output at 0/2/5/10/15 seconds. Weight episodes/roles as specified; compute p50/p90 from the weighted CDF, never means of quantiles. Preserve invalid/unknown/unmet/no-output distinctions and planned missing weight.

### Completion Criteria

Hand-worked positive/negative cases cover correct paraphrase, important omission/negation/number reversal, wrong language, genuine repetition versus cumulative revision, earlier pages, audible other-speaker context, late correction, clock uncertainty and early app interruption. Actual selected-route two-stage judging separates obvious contrasts and records bounded repeat variation. A small real native history traces through reconstruction and checkpoints to report fields. Missing roles/weights cannot produce a complete aggregate; an actual fully observed no-output can receive protocol-defined zero without pretending a model returned it.

### Decisions and Evidence

R1 native examples and R2 reference/checkpoint contracts are dependencies; implementation may proceed with bounded development data while R3 completes. No MetricX, tone30/Korean100, arbitrary MQM deduction formula, legacy delivery alias or numeric score-spreading customization is included.

## R5 — [GPT] Bind costs to logical episodes and later billing evidence

### Background and Goal

Retain useful cost processing without halving VRCLT costs by double-counting its two physical passes or treating missing bills as free.

### Scope

Migrate existing cost consumers to episode/role/pass/run identity and the common result contract. Preserve local allowlisted ingestion, dates/currencies, ambiguity, missing components, subscriptions and source protection. No provider-account scraping or new pricing service.

### Requirements

Apply final-plan §11: actual attributable app charges over the original logical episode timeline counted once, both VRCLT pass costs in the numerator, physical replay and production/judge costs separate. Preserve main/repeat/preparation/invalid-retry distinctions and product-billed retries. Accept later permitted owner logs as a separate evidence revision without changing frozen quality/time. Unknown is null/pending; usage×price is labelled calculated rather than actual billing.

### Completion Criteria

Run local reconciliation examples that demonstrate two-pass cost over one timeline, incomplete components, ambiguous coarse usage, subscription and pending billing. Existing capture-bound missing evidence remains null. A supplied attributable real export is reconciled when available; otherwise retain its exact evidence gap and usable later-update path, not a claim of measured billing.

### Decisions and Evidence

R1 owns pass/window identity and R4 the report interface. Current `costs-v1` normalization is not accepted for new T1 results unchanged. The owner intends to provide billing logs later; that does not block implementation or require a fabricated numeric release.

## R6 — [GPT] Demonstrate the integrated development pilot and freeze production

### Background and Goal

Prove the assembled input→app→native history→evaluation→result path before freezing and running the main population.

### Scope

Integrate R1–R5 across both pairs and all five types, with T1 roles and VRCLT split conditions explicit. Own the production freeze and reproducible operating guidance, not a separate harness-certification campaign.

### Requirements

Freeze protocol, corpus/groups, TTS method/review, role languages/devices/timelines, checkpoints, weights, observation opportunities, app versions/routes/waves, collector stages/clocks/gaps, upstream judge/prompts and preselected repeats/examples. Keep timed app work separate from generation/judging. Do not substitute new output stages or change weights after seeing main results.

### Completion Criteria

An actual development run reaches the common integrated/detail result package with raw-to-table checks of valid translation, no-output and invalid/unavailable scope. Observe both T1 directions, separate-pass clock handling, final observation tail and interruption/resume evidence preservation. Every profile has its admission/blocked status; no missing prerequisite is reported as a pass. Publish the freeze only after required corpus cells and method prerequisites are satisfied.

### Decisions and Evidence

Depends on R1–R5. Costs may remain pending actual billing, but their IDs/denominators and missing states must work. Any material change to concurrency, input route, source, scope or model goes back to the owner before the affected measurement.

## R7 — [GPT] Deliver the dated comparison and public-safe evidence package

### Background and Goal

Execute the frozen main comparison and selected repetitions, retaining actual failures and evidence rather than only successful outputs.

### Scope

Own main execution, dated immutable result assembly, coverage/uncertainty accounting, public-safe example export and subsequent billing evidence revision. Do not repair or relabel the old D1/D3 scores as this baseline.

### Requirements

Use R6 freeze, all 14 profiles and final-plan population. Preserve first product attempts, operational-invalid replacements, quota-stopped/unplayed work and C1 separately. Produce integrated/detail table data and chart data from one stored result, including condition/stage, quality/time/billing coverage and error evidence. Cost evidence can arrive later without altering quality/time originals.

### Completion Criteria

Actual run outcomes or precise blockers account for every planned profile. A small raw→history→judgment/checkpoint→weighted report reconciliation includes missing-role and failed/invalid cases. Required missing weights remain incomplete/N/A; do not present a silently narrowed full result. Deliver permitted evidence and preselected rights-cleared clips to R8/R9, with dates, versions, synthesis limits and actual review levels.

### Decisions and Evidence

R6 is the production prerequisite. Missing provider logs limit cost claims, not already valid quality/time publication. Old evidence remains a separate historical protocol; the retained integrity hold is not removed by new successful runs.

## R8 — [Claude] Publish the unified scorecard, charts and methodology

### Background and Goal

Make the native-output comparison understandable in one public view while preserving access to its detailed evidence. Execution agent: **Claude**.

### Scope

Own public tables, filters/drilldowns, charts, methodology/limitations, first-screen disclosures and correction/change-history entry point. Consume R4/R5/R7 data; do not recalculate metrics in the frontend or add an interactive replay viewer.

### Requirements

Apply final-plan §12: unified quality/p50/p90/cost table, retained detail/audit views, quality×p90 with p50/cost choices, visible condition/endpoint differences and unknown/unmet states. Distinguish VRCLT self/split from peer/simultaneous T1; do not draw a cross-condition Pareto claim. Disclose creator interest, automatic judgment, native-output-not-rendering endpoint, input mix and source rights on the first reading path.

### Completion Criteria

Inspect an actual populated dated report at desktop and narrow widths; spot-check displayed values and evidence links against the backend package. Show partial/missing/pending states without fabricated zero, 15-second or free-cost points. Provide accessible methodology and correction route. Labelled fixtures may support development but not published measured findings.

### Decisions and Evidence

Use schema fixtures before R7 if useful; release requires actual R7 evidence. R9 is a sibling, not a frontend dependency. Preserve the existing planned earlier-benchmark repository link using its established source when available; do not modify that external repository.

## R9 — [Claude] Render the recorded-output comparison video

### Background and Goal

Preserve the earlier public-video outcome using actual native translation histories rather than implying app-screen observation. Execution agent: **Claude**.

### Scope

Own reproducible renderer inputs/settings, visual design/captions, credits and shareable video artifact. No actual app/VR screen footage, interactive replay product or unsolicited external-community posting.

### Requirements

Use R2/R3's preselected rights-cleared clips and R7 histories on a common source clock. Preserve actual output changes, misleading revisions, missing output and timing uncertainty. Label profile/date/direction, native-output replay and VRCLT self/split conditions. Do not select flattering replacement clips after inspecting results.

### Completion Criteria

Watch the complete rendered artifact and spot-check text/audio/event timing/provenance against retained records. All included media has usable rights and source attribution. Missing trace/rights evidence is an explicit clip blocker, not permission to fabricate output or call a reconstruction app footage.

### Decisions and Evidence

This preserves old issue #10's presentation intent while replacing its OSC-only endpoint. Rendering is separate from collecting the measurement and does not violate the no-screen-capture collection decision.

## R10 — [GPT] Support PuriPuly reruns and bounded ASR/segmentation experiments

### Background and Goal

Use an accepted dated baseline for later development without presenting archived competitors or rescores as current competitor behavior.

### Scope

Own on-demand rerun/rescore tooling, separate development probes, PuriPuly-only reference/system-ASR × reference/actual-boundaries 2×2 and Smart Turn v3.2 on/off plus `hangover_ms`, `silence_ms`, `grace_ms` sweeps. Preserve old issue #11 intent; no recurring campaign or PuriPuly source edit is authorized.

### Requirements

Retain all baseline traces/installers/settings, new run/judge/input identities and immutable old results. Report conditional effects/interactions, not additive blame allocation. Distinguish public-input-informed tuning from untouched evaluation. Preserve the bounded five-minute old/new environment-drift check where applicable; establish isolated coexistence or disclose nearby serial comparison. Current-competitor superiority requires current competitor runs.

### Completion Criteria

A small real supported rerun/rescore produces separately dated evidence without overwriting originals. Demonstrate a bounded 2×2/sweep path or record a supported negative interface finding and the exact next decision, not fake experiment rows. Document retained prerequisites and permitted claims.

### Decisions and Evidence

Requires an accepted R7 baseline; does not block first publication. Old D1/D3 flawed/unaccepted derived scores are not the new benchmark baseline. Public presentation changes remain Claude-owned.

# Reset verification and integration boundary

This record covers the cleanup candidate, not the future R1–R10 implementation or a translator benchmark.

- Full retained suite: `.data/check-venv/Scripts/python.exe -B -m pytest -q -ra` — **247 passed**, no failures or skips, 47.78 seconds. The migrated Windows containment/store/transport/judge subset separately collected and passed all 68 cases; retained GUI/export checks passed 9 cases.
- Installed editable package and actual `bench.exe`: help lists only retained commands; `metrics`, `metrics-batch`, and `quality` reject as invalid choices with exit 2. Installed console-script metadata contains only `bench`; `prepare-english.exe` is absent.
- Actual installed CLI smoke: synthetic clock playback plus the existing controlled loopback adapter produced `c1 translation` and `c2 translation`, completed five work stages, and preserved all five prior attempt trace checksums on resume. Inventory inspection returned 14 profiles with historical-self-OSC scope and new-protocol unverified. This used no translator, hardware audio or provider.
- Actual installed cost CLI: existing synthetic fixture retained total 0.006 USD and 1.08 USD/replayed hour; the historical VRCS2 fixture retained null total/normalized costs with no usage records. These are fixture arithmetic and missing-evidence behavior, not new billing measurements or new episode normalization.
- Actual low-level call-store smoke: a committed Unicode response survived close/reopen in a fresh process; matching prompt/model reused it, differing prompt/model did not. Controlled stored data is not a live judge response.
- All **348 tracked files under `corpus/` and `profiles/`** matched their exact `fbab10a` Git blob bytes. Ignored local originals were not rewritten or deleted. Python parsing covered 32 surviving source/test files; document-link inspection found no missing nonprivate targets among 148 local links. Three explicitly local-only investigation links are not promised public assets.
- Initial `pip install --no-deps --no-build-isolation -e .` failed because the existing check environment lacked `setuptools.build_meta`. Normal isolated-build `pip install --no-deps -e .` then built/installed successfully. No project dependency workaround was added.
- No repository CI workflow, configured linter, formatter or type checker was found. Syntax parsing and passing tests are not described as lint/type-check/CI passes.

Throwaway CLI/cost/store smoke artifacts were removed by their temporary-directory contexts. No translator launch, settings change, actual audio benchmark, TTS generation, live judge call, provider/account access or paid operation occurred. The authorized integration endpoint is local `main` and switching this worktree to it; remote push/PR publication and issue create/delete/closure are not performed by this checkpoint.
