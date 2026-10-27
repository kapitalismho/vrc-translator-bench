# Native-output benchmark implementation plan

## Authority and current checkpoint

The owner requested a reset from the work reached in historical issue 8, using [the final benchmark plan](benchmark-final-plan.md), a replacement issue set, and the existing **GPT/backend versus Claude/public-presentation** division. This document classifies the implementation and records the replacement outcomes. The final plan owns benchmark definitions; this document owns migration and delivery boundaries.

**The reset at `ad53f6eb0eda28724acb3f366ebd92b25e9cb3da` is complete and integrated into local `main`; that reset did not implement or run the new benchmark.** The owner subsequently authorized publication of R0–R10 and deletion of all original issues, including closed ones, but not pull requests. R0 is the program umbrella, not a request to repeat the reset. R1 implementation and bounded actual evidence are recorded below; source/rights investigation in R2 can proceed independently.

Starting state: `issue8-first-batch` at `fbab10a0455d91d5419d9673499d25b7ac86c566`; fetched `origin/main` at `1a5244a04d6a62e447a6ed888893f81a9eed9cf6`. The reset integrates the unmerged historical capture work rather than rolling it back. Pre-existing local final/redesign documents are integrated as the planning authority/history. Unrelated untracked traces and terminal-recovery drafts are not staged, deleted or rewritten.

### Published issue set

The owner-authorized replacement is published. **[R1 / #15](https://github.com/kapitalismho/vrc-translator-bench/issues/15) owns native capture and early feasibility; [R0 / #14](https://github.com/kapitalismho/vrc-translator-bench/issues/14) is the program umbrella**, not an unperformed reset step.

| Key | Published issue | Execution owner |
|---|---|---|
| R0 | [#14 — Integrated benchmark program](https://github.com/kapitalismho/vrc-translator-bench/issues/14) | GPT |
| R1 | [#15 — Native collection and early feasibility](https://github.com/kapitalismho/vrc-translator-bench/issues/15) | GPT |
| R2 | [#16 — Natural conversation, reading and EN/ZH T1 parents](https://github.com/kapitalismho/vrc-translator-bench/issues/16) | GPT |
| R3 | [#17 — Reviewed JA/KO T1 reconstruction](https://github.com/kapitalismho/vrc-translator-bench/issues/17) | GPT |
| R4 | [#18 — Quality, semantic waiting and report data](https://github.com/kapitalismho/vrc-translator-bench/issues/18) | GPT |
| R5 | [#19 — Logical-episode costs and billing revisions](https://github.com/kapitalismho/vrc-translator-bench/issues/19) | GPT |
| R6 | [#20 — Integrated verification, final admission and freeze](https://github.com/kapitalismho/vrc-translator-bench/issues/20) | GPT |
| R7 | [#21 — Dated comparison and public-safe evidence](https://github.com/kapitalismho/vrc-translator-bench/issues/21) | GPT |
| R8 | [#22 — Unified scorecard, charts and methodology](https://github.com/kapitalismho/vrc-translator-bench/issues/22) | Claude |
| R9 | [#23 — Recorded-output comparison video](https://github.com/kapitalismho/vrc-translator-bench/issues/23) | Claude |
| R10 | [#24 — PuriPuly reruns and bounded development experiments](https://github.com/kapitalismho/vrc-translator-bench/issues/24) | GPT |

- All eleven titles/bodies, open states, self-assignment to `kapitalismho` and exactly one existing label were read back. R9 uses `documentation`; the other outcomes use `enhancement`. No Project membership was returned and no implementation-start or completion transition was applied.
- All ten children are native sub-issues of R0. Twenty native blocking relationships match the completion-artifact map below; they do not prohibit earlier independent investigation or interface development. R8/R9 remain siblings; R10 is not a first-release blocker.
- Original issues **1–11, including previously closed issues, were deleted**, not merely closed. The all-state issue inventory contains only the replacement set, and all eleven original node identities return `NOT_FOUND`/null. Merged PRs **12 and 13 remain unchanged**.
- Original bodies, eleven comments and metadata are preserved only in `.data/issue-migration-native-output/original-issues.json`; the initial-publication record is `.data/issue-migration-native-output/publication.json`. These local records are not published assets. Historical issue numbers elsewhere in this document identify the retired work, not executable dependencies.
- At the initial issue publication, the reset code/docs had not been pushed, so R0 carried the [approved protocol and verification amendment](https://github.com/kapitalismho/vrc-translator-bench/issues/14#issuecomment-6406764791). That revision's LF-normalized UTF-8 SHA-256 is `957f7655ae9d19e185e25d48b0265e7c76ed3509486df016ab21cf8427401a00`. Its original quote/hash remain intact as a historical source snapshot; later explicit amendments and the maintained plan govern subsequent changes.
- This transaction publishes planning issues only. No TTS/provider call, benchmark execution, account/key change, code push or PR publication occurred. Future contract changes must reconcile the maintained plan and affected issue contracts explicitly.
- The approved verification consolidation is applied to the eleven issue bodies and the R1/R6 titles. Live readback matched the submitted contracts; assignees, single labels, open states and Project memberships are unchanged. All ten children remain attached and no native blocking relationship was edited. `.data/verification-consolidation/` retains pre-amendment, expected and observed records. The current protocol differs only in §§6, 7 and 14 plus the opening amendment notice; source/TTS method, API-key gate, measurement definitions and weights are preserved. No product test or provider run was needed or performed for this documentation/issue change.
- During R1 on 2026-10-26, the owner explicitly chose **Kikitan self exception** and authorized publication of the plan/issue amendment. KIKI1/KIKI2 now join VRCLT1/VRCLT2: ordinary self input and separate A/B self T1 passes, with one logical episode and unchanged models, weights and waves. Actual Kikitan desktop/peer and simultaneous-T1 obligations are superseded, not completed. VRChat remains excluded. This publication grant does not authorize code push, PR or merge.
- The [published Kikitan amendment](https://github.com/kapitalismho/vrc-translator-bench/issues/14#issuecomment-6406954100) supplements the retained full protocol snapshot. R0/R1/R4/R5/R6/R7/R8/R9 issue bodies were updated and read back open; no issue closure or code publication occurred. R1 source inspection also corrected VRCT OCR attribution: its WebSocket omits the UI-only `source:"ocr"` field, so independent OCR-off evidence is required before attributing `RECEIVED` to peer audio.
- After the successful bounded KIKI2 WebSocket experiment, the owner requested adoption and harness integration, paused the work, and explicitly resumed it. The maintained plan supersedes Kikitan's GUI-only execution and UDP 7272 primary-output requirements with installed `--no-ui` WebSocket `recognition`; self/split conditions and all other benchmark obligations remain intact. Historical failures are retained, not declared repaired. The owner subsequently explicitly authorized R1 publication, normal merge into `main` and issue #15 closure. The [published departure and evidence limits](https://github.com/kapitalismho/vrc-translator-bench/issues/15#issuecomment-6431325473) reconcile the earlier issue contract; [PR #25](https://github.com/kapitalismho/vrc-translator-bench/pull/25) carries the accepted local history and R1 implementation. Keep original historical commit identities reachable for the retired implementation references. This publication grant does not authorize additional provider runs or final R6 admission.

### R1 implementation and actual feasibility

R1 replaces the active stage plan/runner/admission contract in place with schema-2 episodes, role timelines and derived passes. Ordinary peer, simultaneous T1, and the approved self/split exceptions retain one logical episode, independent actual origins and a common last-input-speech +15-second horizon for each profile. All simultaneous roles share their own profile's upper classification cutoff; a different profile's later horizon extends physical collection only, not valid output time. Mixed-family first passes share a wave round; exception B passes follow separately. Real canonical profile IDs bind to their approved catalog family/condition. Full catalog wave membership is enforced for main plans; explicit pilot subsets are not wave admission. The GUI controller supports an explicitly evidenced owned-successor PID/session transition and durable recovery from original frozen controller arguments. Missing or inconsistent ownership history fails closed; an exited current owner can establish stopped capture without controlling reused historical PIDs.

`bench/native.py`, `native_formats.py` and `native_transports.py` implement six primary read-only collector families. `native_process.py` contains newly launched collector CLI trees on Windows; Kikitan's separate `kikitan_adapter.py`/`kikitan_runtime.py` owns only its newly launched headless app and guarded settings restoration. Neither may terminate pre-existing translator hosts. `native_file.py` permits producer rename/delete while holding a read-only Windows log handle, retaining explicit rotation gaps. VRCS startup waits for its matching subscription acknowledgments; no corresponding ACK is invented for PuriPuly or Kikitan. Producer times, native identity/finality, mixed display text, physical-log-line limits and collector receipts remain distinct. App, input and collector continuity are independent; a live process, socket or silent log is not proof of complete observation.

The representative route-feasibility pilots used the existing authorized 40-second AMI development excerpt and a further 15-second observation tail. They exercised real installed applications with standalone playback/collection, **not the assembled Runner/controller workflow or a complete wave**. Kikitan's accepted headless WebSocket pilot additionally retained independent same-cable waveform evidence. Public-safe native/clock derivatives are linked by each confirmation; original task-local reports preserve failures and complete callback records for those accepted pilots. The later integrated Kikitan run and its distinct callback-ledger limitation are recorded separately below.

| Observed profile/scope | Primary actual evidence | Boundary |
|---|---|---|
| [PP4 ordinary EN→ZH](../profiles/evidence/r1/pp4-en-zh-confirmation.json) | Ten peer translation CLI projections; CPU-auto/Parakeet route separately observed | Concurrent Kikitan self activity prevents isolated CPU/performance or wave claims. Original follow shutdown required owned-child cleanup; repaired containment was then exercised with the real CLI and zero audio. |
| [VRCT2 ordinary EN→ZH](../profiles/evidence/r1/vrct2-en-zh-confirmation.json) | Seven Chinese `RECEIVED` WebSocket events on reversed peer language settings | Independent OCR-off observations and a controlled session exclude the unrelated OCR input; producer timestamps remain absent. |
| [VRCS2 ordinary EN→ZH](../profiles/evidence/r1/vrcs2-en-zh-confirmation.json) | Three completed Chinese translations plus four partials from `speaker` | Last translation arrived about 7.2 seconds after DAC start; no later translation was observed. Cause and complete source coverage remain unknown. |
| [VRCLT2 ordinary EN→ZH](../profiles/evidence/r1/vrclt2-en-zh-confirmation.json) | Twelve mixed English/Chinese OSC display records and ten separate FINAL-log translations | Qwen3.8 auto-detects source; UDP listener continuity is not packet completeness. FINAL file timing is not OSC or rendering time. |
| [VRCLS1 ordinary EN→ZH](../profiles/evidence/r1/vrcls1-en-zh-confirmation.json) | Five Chinese Desktop/peer log translations; named loopback selection observed in startup diagnostics | Developer-server model identity and physical-line/multiline completeness remain unknown. |
| [KIKI2 ordinary EN→ZH](../profiles/evidence/r1/kiki2-websocket-en-zh-confirmation.json) | Reused accepted installed `--no-ui` experiment: 66 recognition snapshots, 60 with Chinese translation, 24 adjacent prefix-growth observations; complete 40-second PCM and +15.0166-second tail | Original fields/raw messages retained; one native final snapshot is an incomplete phrase. No semantic-finality, KIKI1, other-language, T1, wave or final quality/time claim. |

`profiles/catalog.json` independently partitions all fourteen profiles' six scopes. The six observed ordinary EN→ZH scopes above are confirmed only for early route feasibility. The [former Kikitan UDP Unicode blocker](../profiles/evidence/r1/kikitan-unicode-blocker.json) and early invalid attempt remain immutable history, not an active blocker for the explicitly adopted WebSocket endpoint or a repaired product defect. KIKI1's earlier headless capture crash remains a scoped risk; no success is copied to its unobserved scopes. Final quality/time admission remains `pending_r6` for every profile. Existing six-direction captures and preparation guides remain labeled history, not new admission.

Owned VRCT, Kikitan, VRCS, VRCLT and VRCLS processes were closed after capture. PuriPuly's original personal intent was restored, and its pre-existing host was independently alive after the repaired collector stop. A later completion check found that host and overlay absent; the cause/time is unobserved, and neither was restarted. The earlier preservation observation is not a final-liveness claim. VRCLT's parsed settings exactly matched the original after GUI restoration. VRCS active selections were restored, but an inactive remembered model entry and its app-managed transient server port remain changed. VRCLS active settings were unchanged; automatic credential refresh and update-check metadata were preserved rather than rolled back. No app update, new account/key, TTS production or VRChat execution was performed.

R6 owns full per-profile/language/type admission, broader condition checks and assembled interruption/resume verification. R4/R5 own native reconstruction/scoring and episode-normalized cost integration. These pilots do not establish quality scores, billing, sample-locked multi-device playback, continuous internal provider health or a completed evaluation pipeline. Local implementation does not authorize code push, PR publication, merge or issue closure.

Pre-adoption checkpoint `e0cb14c` verification (historical): the Windows Python 3.12 suite completed with **386 passed in 40.41 seconds**. An actual `bench run --audio-backend clock` invocation exercised the then-current controller fixture, UDP/file collection, persistence and split A/B orchestration: two completed passes and tails of 15.0053349/15.0058824 seconds. Its `.data/episode-core-repair/runs/synthetic-core-recovery/` evidence remains synthetic and pinned to its original source hashes, not repinned to the WebSocket cutover. Separate controlled smokes covered owned Windows successor recovery, producer log rollover and delayed WebSocket ACK ordering. Those fixtures do not establish actual-app restart/rotation behavior or R6 admission.

#### Kikitan WebSocket adoption verification

The cutover adds the supported headless JSON-line controller and read-only recognition collector, removes the active Kikitan UDP fallback, and migrates catalog bindings and executable fixtures. It preserves native source/translation/final fields and raw recognition while excluding credential-bearing state/config frames before persistence. Per-round owned-app shutdown releases the fixed port/shared settings for later KIKI1/KIKI2 waves. Guarded restoration failures survive as durable cleanup ownership and a nonzero CLI result, without replaying terminal audio.

The one additional [installed-app Runner smoke](../profiles/evidence/r1/kiki2-websocket-runner-smoke.json) exercised the new controller, collector, `bench run`, actual playback, OFF/quit and exact fresh-process settings restoration. It reported exit 0 / `output_observed`, captured 66 native snapshots including 60 Chinese updates, and observed +15.013035333 seconds after the reported calibrated input end. Independent extraction then found **callback-ledger evidence loss: 1,896,000 of 1,920,000 source frames persisted, with 24,000 frames missing across 50 ranges**. The terminal playback record and translation progress remain facts, but this run is not complete serialized input accounting or flawless assembled admission. Its original attempt and reported result were not rewritten.

The cause was advancing a callback cursor to the live producer-list length after draining an earlier snapshot. The repair snapshots the end before draining and advances only through those consumed rows. A deterministic concurrent-append regression failed before the fix and passed afterward. A subsequent actual CLI/Runner smoke with a **controlled asynchronous producer, not hardware or a translation provider**, persisted all eight unique callbacks / 3,840 frames, including append-during-drain, through a +15.0093328-second tail. No additional Gemini replay was used to replace the incomplete real-run ledger.

Independent review found a second callback boundary: a final row appended after the snapshot but before observing producer completion could still be lost. The collection loop now requires completed producers and fully consumed callback cursors before normal finalization. A controlled actual CLI/Adapter/Ledger run with a 20-second timeline and speech interval `[0,1]` exercised that terminal interleaving and persisted all 960,000 frames. This same run injected controller exit 7 after terminal capture: CLI exit 2 retained cleanup ownership; cleanup-only resume returned 0 without changing the terminal trace, replaying playback, starting another host or increasing the synthetic ON count from one.

Review also found that nested values under public state-field names could reach diagnostics. Controller projection now requires exact primitive types, including a string preflight app version, and derives duplicated channel fields only from validated settings. A controlled actual JSON-line/Adapter-journal smoke rejected malformed settings and app-version readbacks, then accepted valid readbacks in the same session; the synthetic private marker was absent from the journal. These repair smokes used synthetic hosts/readbacks/PCM records, not installed applications, audio devices or translation providers. Original real and earlier controlled proofs retain their original source applicability.

The pre-publication adoption checkpoint passed **430 tests in 147.74 seconds** on Windows Python 3.12 after the independent-review repairs. The initial cutover checkpoint had 419 passing tests before those findings. Focused checks also exercised controller restoration/ownership conflicts, cleanup-only resume without terminal replay, fixed-port release across controlled sequential profiles, Unicode/cumulative event preservation, unsafe-frame exclusion, disconnects and named-device reindex handling. The separately accepted prior KIKI2 pilot remains the complete-frame/cable route-feasibility evidence; the repaired recorder has controlled-path proof, not a repeated real-app capture. R6 retains broader and final assembled admission.

#### PR product-failure isolation repair

[PR #25 review](https://github.com/kapitalismho/vrc-translator-bench/pull/25#discussion_r4384209989) identified a compound-failure defect: a confirmed application crash followed by native socket closure could become retryable harness-invalid work and invalidate healthy wave members. Independent controlled probes confirmed both event orderings and contamination from a profile already terminal during preparation. The repair scopes checks to active attempt generations, immediately correlates transport loss with independent application health, retains product-failure/reached evidence and false collector continuity, and allows healthy members and later waves to complete. Uncorroborated disconnects, protocol/schema/policy faults and mixed independent instrumentation gaps remain invalid; observed product errors are retained even then.

A standalone actual CLI/Runner/Adapter/NativeSink/Ledger smoke used a real loopback WebSocket with connection/subscription acknowledgements, synthetic application health and clock input. The confirmed-crash case returned exit 1 with **one product failure, two completed healthy attempts and zero invalid attempts**. Healthy and later-wave streams each retained 5,760 simulated frames, Unicode output and tails of 15.0096009/15.0110536 seconds. Resume preserved all terminal rows/trace hashes and one application start per profile, with no replay or reconnect. The uncorroborated-disconnect control returned exit 2, two invalid attempts, no product failures and unplayed later work. Fixture processes/endpoints were closed and the throwaway driver removed; no installed application, provider or hardware audio was used.

The final focused repair suite passed **162 tests in 141.11 seconds**, including both event orderings, preparation/quiet/final boundaries, historical generations, quota-pending behavior, immutable terminal resume and instrumentation-negative cases. The CLI smoke's original source hashes remain explicit: subsequent transport changes only add policy/extension close-code exclusions, covered by final-source checks; observed normal close/EOF behavior is unchanged. Original real-provider evidence is neither rewritten nor promoted by this repair.

Final shared Windows Python 3.12 verification after this PR repair: **446 tests passed in 152.38 seconds**. Product/test sources were frozen before that run; only this maintained verification text was updated afterward.

### R2 source-preparation checkpoint — production freeze blocked

[R2's coverage/evidence index](../corpus/r2/status.json) and
[corpus guide](corpus.md#r2-source-review-and-preparation) preserve the fixed
60-episode design while recording 27 typed main candidates, six development
candidates, two C1 candidates and three unclassified ASCEND explanations.
The three offline materializers preserve pinned sources, original grouping,
sample mappings, references and hashes without changing historical corpus bytes.
Actual final-catalogue materialization, output-byte/group checks and **21 focused
tests** passed. Source-only local ASR and waveform/alignment evidence are retained
with their failed/inconclusive attempts; no provider calls or app replay occurred.

This is not issue #16 completion. ASCEND's released utterances do not yet supply
verified paired original-recording/clock mapping or actual intervening sound for
the required P2/P3/T1 windows. Nine main and four development T1 parents remain
unaccepted, so R3 receives no frozen parent list. IngCrowd's prepared mixed-input
candidates retain named content/boundary review limits; FLEURS retains four
specific acoustic/reference/endpoint holds; nonverbal C1 speech absence is
unresolved. Automatic review is disclosed without inventing a mandatory
human-only R2 gate. Unknown repeated speakers are not certified independent.

The owner clarified noncommercial OSS use including promotion; promotion alone
does not establish a CC BY-NC violation. Source-license eligibility, actual
provider-route input terms and owner authorization to publish source-bearing
examples remain separate. Pre-result examples/repeat candidates are recorded
without inspecting benchmark-app results. No source substitution, reduced
counts, weight redistribution, TTS request, code push or issue closure occurred.
Resolve the named missing original-source and review/rights evidence before
production acceptance; reuse existing valid artifacts across issue boundaries.

### What “through issue #8” means

- Before replacement, issues #2–#7 were closed on their respective amended preparation/implementation scopes, while #1, #8 and #9–#11 were open. No linked Project items or repository Actions workflows were returned. The publication record above supersedes their page-existence/status information, not the historical implementation facts.
- The D1/D3 batch has substantial real capture and calculation evidence. The local state explicitly records `measurement_artifacts_complete__integrity_repair_required__owner_billing_pending` and `final_result_acceptance_hold: true`.
- Confirmed old analysis defects include incorrect source/output links, cumulative-output duplication, missing audible-speaker context, output-dependent scoring populations, and early harness intervention misrepresented as complete observation. Raw capture consistency does not validate those derived scores. Real product errors also remain; this is not a finding that every low score was a harness error.
- Preserve existing captures, scores, unavailable cases and the acceptance/billing hold. This reset does not fix historical scores, complete #8 or establish a new baseline.

The investigation's private source is `.data/issue8/batch-analysis-v1/discovered-analysis-issues.md`; it is not a clean-clone prerequisite. The findings needed for implementation are recorded in final-plan §6 and the evaluation acceptance criteria below. Do not publish the private report or raw app/billing logs automatically.

## Preserve, modify, retire

This table records the reset's disposition; the R1 status above supersedes its prospective capture/admission wording.

| Disposition | Current surface | Decision and reason |
|---|---|---|
| Preserve infrastructure | `bench/audio.py`, `storage.py`, `activity.py`, `adapter.py`, `gui_operator_adapter.py`, `osc.py` | Reuse actual playback/callback clocks, raw wire history, durable attempts, hashes, locks and process/observation ownership. OSC remains one transport, not the universal peer endpoint. |
| Preserve, then migrate in R1 | `bench/plan.py`, `runner.py` | Existing single-WAV/microphone/OSC stages are not episodes, synchronized T1 or split passes. Keep working infrastructure now; replace its old contract in place when the native path is implemented. The old watchdog is not new observation-opportunity proof. |
| Preserve evidence; migrate admission state in R1, finalize in R6 | `profiles/catalog.json`, `profiles/findings/`, `profiles/evidence/`, `profiles/output-checks.json` | Keep all 14 profile identities and historical bytes. R1 records observed scope/blockers without promoting representatives to all-profile readiness; R6 owns final quality/time admission. |
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
| Universal microphone→chatbox OSC endpoint | Superseded by app-native translation outputs, mostly peer; VRCLT and Kikitan self/split-T1 exceptions stay explicit. No screen-rendering claim. |
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
| R1 | GPT | Working native collection and representative early feasibility | Current profile/source evidence, small permitted inputs, scoped runtime access; final all-profile admission belongs to R6 |
| R2 | GPT | Frozen eligible natural-conversation/reading episodes and EN/ZH T1 parents | R1 input/output contracts and early feasibility, not R6 final admission |
| R3 | GPT | Reviewed JA/KO T1 reconstruction and production-cost report | R1 early feasibility, R2 eligible parents, owner-configured API key and scoped usage approval, rights/review prerequisites |
| R4 | GPT | Auditable reconstruction, two-stage quality, semantic waiting and report data | R1 native examples/contracts; R2 representative references/checkpoints |
| R5 | GPT | Logical-episode costs and later evidence revisions | R1 episode/pass/run bindings; coordinate report contract with R4 |
| R6 | GPT | Shared integrated verification, final per-profile admission and production freeze | R1–R5 artifacts and reusable evidence; pending billing allowed but no fabricated amounts |
| R7 | GPT | Dated main/repeat result package | R6 freeze and actual profile admission |
| R8 | Claude | Unified public report, audit views, two-axis charts and methodology | R4/R5 schema for development; actual R7 package for release |
| R9 | Claude | Chronological recorded-output comparison video | Preselected cleared R2/R3 clips and R7 histories |
| R10 | GPT | Separately dated reruns and bounded development experiments | An accepted R7 baseline; not a first-release blocker |

R1 resolves the minimum episode/role/pass/output/clock/outcome contracts and exercises representative real routes on small permitted samples; it does not finish the corpus or certify all profiles. R2 rights/source investigation can proceed alongside it. Corpus/TTS production needs that early feasibility evidence and disclosed blockers, not final R6 admission; do not add a reverse dependency that would make production and R6 wait on each other. R4/R5 reuse bounded evidence while R3 completes.

R1 owns shared capture contracts and early findings; R2 owns source/checkpoint definitions; R4 owns evaluated result fields/weights; R5 owns cost bindings/revisions; R6 owns assembled-path verification and final quality/time admission for all 14 profiles. R8/R9 consume those contracts without recalculating them. Each outcome updates affected callers and maintained docs. Frozen historical evidence is never a mutable implementation surface.

## Verification ownership and evidence reuse

The owner approved consolidating integrated verification in R6 rather than repeating a full check package at each issue boundary. This reallocates evidence ownership; it does not waive required behavior, regressions or unknown-state reporting.

| Stage | Evidence owned here | Not repeated here |
|---|---|---|
| R1 | Representative actual input→native collection, roles/clocks and early access/input blockers; changed-path checks | Final all-profile admission, full condition matrix or complete backend pipeline |
| R2 | Actual source/reference/timeline/rights and development/main separation | Per-app replay for corpus acceptance |
| R3 | Owner key/usage gate, approved TTS pilot, bilingual content/boundary review and production costs | Benchmark-app tests or regeneration merely for another issue |
| R4/R5 | Small calculation/reconstruction cases, local processing of retained logs, minimal actual two-stage judge operation and cost arithmetic/unknown states | Relaunching apps to demonstrate the complete pipeline |
| R6 | Shared end-to-end verification, remaining judge contrast/variation checks, final per-profile quality/time admission and freeze | Re-proving applicable earlier evidence or a full Cartesian rehearsal of the main benchmark |
| R7 | Actual main-run omissions/failures/settings changes and result-package spot checks | Repeating the R6 pilot or certifying the harness again |
| R8/R9 | Actual public surface values/links and rendered content/synchronization | App replay, judge recalls or backend revalidation solely for presentation acceptance |

- Pass the same development inputs, raw histories, judge responses and results forward with their existing version/input/configuration identities. An issue or reviewer transition alone is not a reason to rerun.
- Repeat only to resolve a changed code/input/app/model/prompt condition, a new failure/conflicting result, or a requirement the existing evidence does not establish. Name the affected relationship and check that scope; old self/OSC evidence does not become new peer evidence.
- During implementation, exercise the changed behavior and relevant regression risks. Do not attach full-suite runs, live pilots and whole-system re-review to every issue by default. Keep applicable repository review gates; use R6 for assembled-path claims.
- R6 combines existing evidence with only missing/affected checks on the planned development cases. Do not add a generalized validation framework or a separate certification campaign. After a repair, recheck its impact rather than restarting every combination.
- Keep required source/rights review before production, the owner-local API-key/usage gate before any TTS request, and TTS input review before adoption. These prevent bad or unauthorized inputs; they are not redundant app integration checks.
- Planned main-measurement repetitions, R8/R9 final-artifact inspection and R10's separately dated experiments remain in scope. R1–R5 completion is component acceptance, not an integrated measurement pass.

## Unresolved prerequisites and stop conditions

- **Kikitan:** use the approved headless WebSocket microphone/self route with `desktop_translation=false`, `send_user_data=false`, `send_to_chatbox=false` and the exact cable microphone. Preserve ordinary self and separate A/B self passes. The accepted KIKI2 EN→ZH experiment supports only that bounded route; KIKI1's earlier headless capture crash remains a separate unresolved risk. Do not launch VRChat, spoof a process, patch the app, relabel self as peer or copy historical chatbox success to unobserved WebSocket scopes.
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

Apply the Verification ownership and evidence reuse section above: R1–R5 own bounded component checks, R6 owns final admission and shared integration, and R7–R9 inspect their new artifacts without repeating the upstream campaign. Do not treat issue boundaries as fresh evidence requirements.

### Completion Criteria

First release has an actual dated R7 package, R8 public report and R9 cleared video, with reported coverage, failures, method limits and cost status traceable to common evidence. Missing required weight prevents a complete integrated-score claim. Child closure alone is not integrated acceptance. R10 remains visible until separately completed.

### Decisions and Evidence

The reset classification above distinguishes reusable infrastructure from accepted measurements. Historical issue 8 evidence retains its integrity/billing hold regardless of deletion of its issue page. The owner authorized publication of this set and deletion of the original issues; paid runs, credential/account changes, source-rights clearance and remote code push remain separately scoped.

## R1 — [GPT] Implement native collection and establish early feasibility

### Background and Goal

The retained runner captures one self input and chatbox OSC. Deliver episode-native input/collection and representative actual feasibility evidence before expensive input production. Record all fourteen profiles' known scope and blockers; final quality/time admission belongs to R6.

### Scope

Migrate the current runner/plan/profile admission in place; implement one primary read-only native collector per app family using final-plan §6. Reuse playback, persistence, lifecycle and raw evidence foundations. No application patches, OCR, hooks, TLS interception or compatibility evaluator.

### Requirements

Own the episode/role/pass, native-output, clock/gap and outcome contracts consumed downstream. Support ordinary peer input, simultaneous self/peer T1, and the approved VRCLT/Kikitan all-self/two-pass exceptions with separate origins and one logical episode. Preserve actual model/source/target/device/endpoint stages and W1–W4 concurrency intent. Keep collectors active through the common last-input-speech +15 seconds; early harness intervention is invalid, not product no-output. Preserve attempts and independent app/input/collector continuity evidence.

### Completion Criteria

Small authorized inputs demonstrate the primary native collector for each app family where accessible: the intended audio reaches the correct input, actual translation text is captured, and roles/clocks are attributable. Add checks only for materially different routes/settings or changed behavior; a connection or one packet is not enough. Record confirmed, blocked and still-unverified scope for all fourteen profiles without copying representative success to unobserved profiles. Keep relevant local regression checks, but transfer final per-profile text/time admission, the broader condition checks and assembled interruption/resume verification to R6. R1 does not require a full profile×language×type pilot or a completed evaluation pipeline.

### Decisions and Evidence

Final-plan §§4.7, 6 and 10 govern. PuriPuly peer ASR is separate, VRCS T1 shares ASR language, and VRCT peer direction is reversed. Kikitan uses the owner-approved headless WebSocket microphone/self exception without VRChat; its earlier GUI-only and user-data primary obligations are superseded. VRCLT self OSC/log timing differs. Reuse applicable input/output evidence without promoting it to unobserved scopes or R6 admission.

## R2 — [GPT] Freeze eligible natural-conversation and human-read episodes

### Background and Goal

Create actual source-linked episode inputs for the selected two-pair protocol; old AMI/AliMeeting/YODAS tracks are not substitutes.

### Scope

Prepare ASCEND EN/ZH P1–P3/T1 parents, IngCrowd JA P1–P3, FLEURS EN/JA P4, development cases and C1 candidates. Preserve historical corpus bytes. R3 supplies synthetic JA/KO T1.

### Requirements

Implement final-plan §§2–5 selection, fixed cell counts/weights, audible references, context-versus-translation scope, original-group split, nonoverlapping intervals, role buffers and pre-result semantic checkpoints. Pin source revision/split/IDs/files/licenses and actual audio/reference hashes. Prove EN/ZH T1 common origin, both sides and substantive translation targets before freezing R3 parents. Select permitted public-example candidates before viewing app results.

### Completion Criteria

Inspect actual representative WAV/EAF/transcript content and source-to-playback mappings, not only manifest shape. Verify sample positions/gaps, decoded hashes, no unintended role leakage or duplicate main/development ancestry, and all required natural/read cells. Publish rights/review levels and exact unavailable cells. Insufficient source eligibility or use rights blocks production freeze without replacing material or redistributing weight.

Pass the selected source artifacts and review evidence forward unchanged. Corpus acceptance does not require launching/replaying every translation app; R6 owns input-to-app integration.

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

Retain the approved four-dialogue method pilot and adopted-input review; they prevent invalid benchmark inputs and are not postponed to R6. Hand the actual audio, scripts and review/cost evidence to R6 without regenerating speech or launching benchmark apps solely to close this issue.

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

Use small local cases to check paraphrase versus important omission/negation/number reversal, wrong language, genuine repetition versus cumulative revision, earlier pages, audible other-speaker context, late correction, clock uncertainty and early interruption. Replay retained native histories locally and exercise a minimal actual selected-route two-stage judgment with its stored raw/result identities; do not relaunch apps to obtain another integration sample. Missing roles/weights must remain incomplete, and protocol-defined no-output zero must not masquerade as a judge response. R6 owns the assembled live history→evaluation→report path and remaining contrast/repeat-variation confirmation; reuse applicable earlier judge results instead of repeating them.

### Decisions and Evidence

R1 native examples and R2 reference/checkpoint contracts are dependencies; implementation may proceed with bounded development data while R3 completes. No MetricX, tone30/Korean100, arbitrary MQM deduction formula, legacy delivery alias or numeric score-spreading customization is included.

## R5 — [GPT] Bind costs to logical episodes and later billing evidence

### Background and Goal

Retain useful cost processing without halving VRCLT or Kikitan costs by double-counting their two physical passes or treating missing bills as free.

### Scope

Migrate existing cost consumers to episode/role/pass/run identity and the common result contract. Preserve local allowlisted ingestion, dates/currencies, ambiguity, missing components, subscriptions and source protection. No provider-account scraping or new pricing service.

### Requirements

Apply final-plan §11: actual attributable app charges over the original logical episode timeline counted once, both self-pass costs in the numerator for VRCLT and Kikitan, physical replay and production/judge costs separate. Preserve main/repeat/preparation/invalid-retry distinctions and product-billed retries. Accept later permitted owner logs as a separate evidence revision without changing frozen quality/time. Unknown is null/pending; usage×price is labelled calculated rather than actual billing.

### Completion Criteria

Run local reconciliation examples that demonstrate two-pass cost over one timeline, incomplete components, ambiguous coarse usage, subscription and pending billing. Existing capture-bound missing evidence remains null. A supplied attributable real export is reconciled when available; otherwise retain its exact evidence gap and usable later-update path, not a claim of measured billing.

Use retained records and small local examples; do not launch apps or manufacture provider usage solely to verify cost plumbing. R6 checks the assembled episode/pass/result binding. Later owner billing evidence is reconciled once when supplied, separately from frozen quality/time.

### Decisions and Evidence

R1 owns pass/window identity and R4 the report interface. Current `costs-v1` normalization is not accepted for new T1 results unchanged. The owner intends to provide billing logs later; that does not block implementation or require a fabricated numeric release.

## R6 — [GPT] Verify the integrated benchmark, finalize admission and freeze production

### Background and Goal

Prove the assembled input→app→native history→evaluation→result path before freezing and running the main population.

### Scope

Own the shared input→app→native history→quality/wait/cost→result verification and final quality/time admission for all fourteen profiles. Cover both pairs, the five types, T1 roles and VRCLT/Kikitan split conditions using the planned development cases and reusable R1–R5 evidence. This is not a full Cartesian rehearsal of the main population or a separate harness-certification campaign.

### Requirements

Freeze protocol, corpus/groups, TTS method/review, role languages/devices/timelines, checkpoints, weights, observation opportunities, app versions/routes/waves, collector stages/clocks/gaps, upstream judge/prompts and preselected repeats/examples. Keep timed app work separate from generation/judging. Do not substitute new output stages or change weights after seeing main results.

Collect existing component evidence first and run only missing checks or those affected by changed conditions. Retain exact input/app/collector/judge identities so reused evidence applies to the assembled candidate. R1–R5 need not pre-complete this issue's integration criteria, and final R6 admission is not a prerequisite for R2/R3 preparation.

### Completion Criteria

An actual shared development path reaches the common integrated/detail result package, including quality, separate p50/p90 and cost bindings/missing states. Reuse existing component checks and inspect raw-to-result relationships for valid translation, no-output and invalid/unavailable scope. Cover required role/direction attribution, VRCLT/Kikitan pass clocks, output completeness/revisions, observation tail and interruption/resume preservation through applicable evidence plus only the missing/affected runs. Complete the selected judge contrast/variation checks without recalling unchanged valid judgments solely because this is R6. Report final quality and timing admission separately for every profile, including exact blocked/unverified routes; representative-family success is not all-profile evidence. Publish the freeze only after required corpus/method prerequisites and the claimed admission scope are supported. After fixes, repeat the affected checks, not the whole campaign.

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

Actual main-run outcomes or precise blockers account for every planned profile. Inspect actual omissions, failures, setting/version drift and a small sample of the resulting raw→stored result→published-package links, including missing-role and invalid cases. Reuse R6's algorithm/integration evidence; do not rerun its development pilot or harness checks solely for this issue. New changes or contradictory evidence trigger only affected verification before the relevant claim. Required missing weights remain incomplete/N/A. Deliver permitted evidence and preselected rights-cleared clips to R8/R9 with dates, versions, synthesis limits and actual review levels. The planned main subset repetitions remain measurements, not redundant verification.

### Decisions and Evidence

R6 is the production prerequisite. Missing provider logs limit cost claims, not already valid quality/time publication. Old evidence remains a separate historical protocol; the retained integrity hold is not removed by new successful runs.

## R8 — [Claude] Publish the unified scorecard, charts and methodology

### Background and Goal

Make the native-output comparison understandable in one public view while preserving access to its detailed evidence. Execution agent: **Claude**.

### Scope

Own public tables, filters/drilldowns, charts, methodology/limitations, first-screen disclosures and correction/change-history entry point. Consume R4/R5/R7 data; do not recalculate metrics in the frontend or add an interactive replay viewer.

### Requirements

Apply final-plan §12: unified quality/p50/p90/cost table, retained detail/audit views, quality×p90 with p50/cost choices, visible condition/endpoint differences and unknown/unmet states. Distinguish VRCLT/Kikitan self/split from peer/simultaneous T1; do not draw a cross-condition Pareto claim. Disclose creator interest, automatic judgment, native-output-not-rendering endpoint, input mix and source rights on the first reading path.

### Completion Criteria

Inspect an actual populated dated report at desktop and narrow widths; spot-check displayed values and evidence links against the backend package. Show partial/missing/pending states without fabricated zero, 15-second or free-cost points. Provide accessible methodology and correction route. Labelled fixtures may support development but not published measured findings.

Use R7's stored outputs and accepted backend evidence. Do not replay source audio through apps or recall the judge solely for frontend acceptance; a concrete displayed-data discrepancy is investigated at its affected boundary.

### Decisions and Evidence

Use schema fixtures before R7 if useful; release requires actual R7 evidence. R9 is a sibling, not a frontend dependency. Preserve the existing planned earlier-benchmark repository link using its established source when available; do not modify that external repository.

## R9 — [Claude] Render the recorded-output comparison video

### Background and Goal

Preserve the earlier public-video outcome using actual native translation histories rather than implying app-screen observation. Execution agent: **Claude**.

### Scope

Own reproducible renderer inputs/settings, visual design/captions, credits and shareable video artifact. No actual app/VR screen footage, interactive replay product or unsolicited external-community posting.

### Requirements

Use R2/R3's preselected rights-cleared clips and R7 histories on a common source clock. Preserve actual output changes, misleading revisions, missing output and timing uncertainty. Label profile/date/direction, native-output replay and VRCLT/Kikitan self/split conditions. Do not select flattering replacement clips after inspecting results.

### Completion Criteria

Watch the complete rendered artifact and spot-check text/audio/event timing/provenance against retained records. All included media has usable rights and source attribution. Missing trace/rights evidence is an explicit clip blocker, not permission to fabricate output or call a reconstruction app footage.

Use the retained media and histories without a new app run, judge call or TTS take merely for video acceptance. This checks a new rendered artifact, not the upstream measurement pipeline again.

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
