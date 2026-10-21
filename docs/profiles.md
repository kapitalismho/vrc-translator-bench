# Application profile preparation

This is the preparation deliverable for [issue #4](https://github.com/kapitalismho/vrc-translator-bench/issues/4), not a completed comparison. **VRCT1, VRCS1, VRCS2, VRCLT1 and VRCLT2 have bounded real-audio readiness evidence; the other catalogue findings remain blocked or owner-deferred.** Engine availability, account access and actual output are not inferred from source support. No profile is declared unsupported merely because its access/pilot is missing.

## GUI preparation of installed applications

The owner subsequently authorized changing the installed apps through computer use and requested closing completed windows. [Redacted preparation evidence](../profiles/evidence/gui-preparation.json) records the actual GUI observations, saved settings, private backups and startup caveats. This supersedes the **current-setting** claims in the earlier read-only snapshot below; it does not promote any profile to audio-pilot readiness.

For the remaining pilots, the owner subsequently required computer use through the actual application GUIs for preparation, capture start/stop and cleanup, superseding the earlier preference for CLI/headless application control in this execution. The benchmark runner still owns timed audio playback and raw OSC recording. GUI observation and interaction must stop during timed playback; requested settings or controller acknowledgements do not replace observed application state. Earlier headless/control-only observations remain historical evidence, not GUI verification.

The owner then explicitly deferred **all PuriPuly profiles (PP1–PP4)** from this execution. Do not launch, update, build or run PuriPuly to complete these pilots. Keep the four catalogue entries with an owner-deferred reason; this is neither unsupported functionality nor an observed product failure. Historical PuriPuly evidence stays identifiable, and PuriPuly-specific runtime/access/usage observations remain deferred. The active empirical scope is the ten competitor profiles; their actual output styles can supply the small issue #5 integration sample.

### Actual development captures

- **VRCS2:** GUI-operated 0.2.8, Gemini `gemini-3.5-transcribe-live` plus requested OpenRouter `google/gemma-4-26b-a4b-it`. D1 produced translated Japanese OSC; a separate D2 target change and same-process capture resume produced Chinese translated OSC. Both runners exited 0 with four completed stages. This is not process-restart persistence or interrupted-harness resume. [D1 evidence](../profiles/evidence/issue45/vrcs2-d1-observation.json), [D2 evidence](../profiles/evidence/issue45/vrcs2-d2-resume-observation.json).
- **VRCS1:** GUI-installed Qwen3-ASR 0.6B Q8_0 runtime/model, CPU selected, with the same requested Gemma translation route. The owned inference process independently showed CPU-only device/offload flags. D1 completed four stages and received translated Japanese OSC. [Run evidence](../profiles/evidence/issue45/vrcs1-d1-observation.json), [CPU evidence](../profiles/evidence/issue45/vrcs1-cpu-runtime.json).
- **VRCT1:** GUI-operated 3.6.0, Google Web Speech ASR plus CPU `m2m100_418M-ct2-int8`, explicitly selected supported `int8` processing and WASAPI CABLE Output. D1 completed four stages, runner exit 0, 5,000 callbacks and six bilingual Japanese OSC inputs. The GUI independently displayed source/translation and retained the CTranslate2 engine. CPU/int8 is observed configuration, not independent execution-type instrumentation. [Run evidence](../profiles/evidence/issue45/vrct1-d1-observation.json).
- **VRCLT1:** Actual GUI-operated 1.0.1, planned Gemini `gemini-3.5-live-translate-preview`, text-only local output and normal 15-second idle behavior. D1 completed four stages with 5,000 audio callbacks and 26 chatbox inputs, including rolling bilingual Japanese output. The GUI subtitle field was blank at the post-run observation; raw UDP, not a claimed GUI transcript, proves translation. The terminal manifest and session end are retained; the numeric runner exit code was not captured. [Run evidence](../profiles/evidence/issue45/vrclt1-d1-observation.json).
- **VRCLT2:** The initial Qwen 3.8 Beijing check failed with `Voice 'Chelsie' is not supported`, despite inspected text-only code omitting voice fields. That [failure evidence](../profiles/evidence/issue45/vrclt2-d1-initial-failure.json) remains preserved. A later owner-requested minimal GUI correction entered the existing Beijing workspace ID, without changing the Qwen model, region or voice settings. One ten-second check produced **three English/Japanese OSC messages**; runner exit was **0**, and the entire owned app pair exited after GUI Close. This establishes a supported endpoint correction, not the provider's internal cause. The selected sequential plan adopts observed UDP19131 for separate S03/S04 waves, superseding the old19132 reservation without another audio run. [Recovery evidence](../profiles/evidence/issue45/vrclt2-workspace-hostcheck.json), [superseding wave decision](../profiles/evidence/issue45/sequential-wave-decision.json).
- **VRCLT cleanup correction:** Closing one observed process initially left other related runtimes alive. A later user-operated restart removed the old pairs; the VRCLT1 pilot then tracked its complete owned launcher/runtime pair and confirmed both absent after actual GUI Quit. [Ownership gap](../profiles/evidence/issue45/vrclt-process-ownership-gap.json), [user restart](../profiles/evidence/issue45/vrclt-user-restart-ownership.json). One window's disappearance is not whole-runtime cleanup.
- The completed full D1 pilots use an unchanged 40-second English development excerpt after the common ten-second output check. They retain actual callback/DAC timing, the earlier measured cable correction and raw UDP receive order. The D2 run and minimal Qwen endpoint diagnostic are output-check/lifecycle observations, not additional scored dialogue samples or the full nonspeech protocol.
- VRCS changed from installed 0.2.2 to 0.2.8 before measurement. Update initiation was not established; the operator did not click an update action. Automatic update checks were then disabled through the GUI. The owned VRCS and local inference processes exited after GUI closure, and the earlier pre-GUI-override debugging listener was independently confirmed absent.
- The earlier KIKI1 native/headless attempt crashed before audio playback in microphone processing. Zero callbacks and zero OSC in that failed attempt are **not** zero delivery for played speech. The operational-invalid direction attempt and native crash evidence are both retained. [Failure chronology](../profiles/evidence/issue45/kiki1-failure.json).
- **Remaining GUI prerequisite:** After VRCT1, actual microphone/translation switches were OFF. Its window later became inaccessible, computer-control authorization was inactive and the renewed authorization request timed out; independent inspection still found its GUI/backend processes alive. No further audio was started and no full VRCT process exit is claimed. VRCT2/VRCT3, VRCLS1, KIKI2 and the separately requested actual-GUI KIKI1 attempt need restored visible GUI access and authorization. This is not a product failure. [Prerequisite record](../profiles/evidence/issue45/gui-execution-prerequisite.json).

These observations use existing owner-authorized access. Actual upstream OpenRouter provider/returned identity, account isolation, quotas and billed costs remain unknown where the application does not expose them. Safe exports under `profiles/evidence/issue45/` are explicitly redacted derivatives linked to original hashes, not replacements for authoritative local raw captures.

### Earlier GUI-only preparation

| App | Initial saved profile | Saved benchmark configuration |
|---|---|---|
| VRCT | VRCT1 | Google Web Speech + CPU M2M; CABLE Output/WASAPI; en→ja; OSC `19111`; capture/translation left off |
| VRCS | VRCS2 | Gemini Transcribe Live + one Gemma 26B OpenRouter target; CABLE Output; en→ja; OSC `19122`; speaker capture and mute synchronization off |
| VRCLS | VRCLS1 | Remote recognition + developer translation; CABLE Output; en→ja; OSC `19141`; microphone/control autostarts and TTS off |
| kikitan | KIKI1 | Bing + Google Translate; repaired CABLE Output selection; en→ja; OSC `19151`; desktop capture off |
| VRCLT | VRCLT2 | Qwen 3.8 Beijing; CABLE Output; en→ja intent; text-only; OSC `19132`; inbound/control/VR overlays off; translation left off |

Most changes used the actual GUI. File-backed exceptions were startup safety guards, VRCS 0.2.2's OSC port (not exposed in the inspected GUI), and VRCLT's input/playback routing before reopening. Existing accounts and keys were not manually changed, no update was requested, and PuriPuly was untouched. Original configurations are backed up under the ignored `.data/issue4/gui-preparation-20261021T024343/`; these files contain secrets and must not be published.

**Startup caveats:** kikitan initially displayed `STOP` without an operator start request and was stopped immediately when observed. Its message history was empty, but automatic provider activity was not measured. VRCLT translation OFF is **raw passthrough**, not microphone stop; its `outbound.enabled` flag is not a reliable capture guard. The first launch retained its previous audio routing. Before reopening, input was set to CABLE Output and passthrough playback to **Realtek Digital Output**, not CABLE Input. Final text-only mode still has unity-gain raw passthrough; the safe non-injection output must remain selected. The normal 15-second idle disconnect was preserved.

At that earlier preparation checkpoint, only one initial profile per application was selected and no microphone-to-translated-OSC pilot had run. Its saved values and GUI state were preparation evidence, not runtime delivery proof. The subsequent actual captures above supersede that runtime limitation only for their named profiles and directions; dedicated quota/project isolation and provider costs are still not established.


## Installed-machine correction

The owner confirmed that every application was installed and initially planned a PuriPuly 2.9.0 update; later PuriPuly execution was explicitly deferred. A subsequent **read-only inspection** confirmed all five other apps, existing configuration and several stored credentials. Earlier source-discovery statements about missing installations/access were too broad; the historical installation facts are in [installed-apps.json](../profiles/evidence/installed-apps.json). A blocked finding need not mean the application is absent.

| App | Actual installed version | Preparation gap observed before GUI changes |
|---|---|---|
| VRCT | 3.6.0 backend; stale uninstall entry says 3.4.0 | M2M and Whisper base files exist, both CPU selected; saved combination runs both local workloads and uses Virtual Desktop/MME input, port 9000 |
| VRCS | 0.2.2, schema 30 | Gemini Live ASR and credential targets exist; translation targets are DeepSeek/GPT-5 mini, OSC off; standard model store lacks managed Qwen package |
| VRCLS | 0.7.0-20260913, assembly 0.7.0.1015 | Remote/developer route and authorized-account token presence confirmed; default microphone, port 9000 and microphone autostart enabled |
| kikitan | 2.0.2, product version identifies inspected source commit | Bing/Google en→ja selected and Gemini key present; stored microphone name contains replacement characters, port 9000 |
| VRCLT | 1.0.1 portable; both copies match release SHA-256 | Qwen 3.8 Beijing selected; both provider keys present; voice output targets CABLE Input, inbound/control enabled, port 9000 |

VRCT's actual version was read from the frozen backend's `_VERSION` assignment using matching Python 3.11 bytecode inspection, without executing app code. Its 23 M2M and four Whisper marker-listed files exist with matching cached sizes; this is not inference proof. VRCS credential checks examined target metadata only, not credential blobs. Existing credential presence does not prove validity, quota, or separate benchmark projects. VRCLT's saved Beijing route does not require the proposed Singapore workspace merely because a previous preparation example used Singapore.

At that earlier read-only inspection, no matching named application processes were running and no app was launched, updated or reconfigured. Those observations are historical, not a description of subsequent GUI preparation or pilots. No PuriPuly update is claimed from this execution.

## Artifacts and commands

- [`profiles/catalog.json`](../profiles/catalog.json): every parent profile, planned versus observed fields, six-direction accounting, port reservations, wave placement and readiness findings.
- [PuriPuly](profiles/puripuly.md), [VRCT/VRCS](profiles/vrct-vrcs.md), [kikitan/VRCLS](profiles/kikitan-vrcls.md), [VRCLT](profiles/vrclt.md): version-pinned control procedures, exact configuration keys, real routes, language mappings, access/export findings and OSC interpretation limits. The three competitor JSON files under `profiles/findings/` are source-discovery evidence, not live application state.
- [`profiles/output-checks.json`](../profiles/output-checks.json): three local ten-second development-audio excerpts, source and output hashes, six-direction reuse. Audio remains under source-specific terms in ignored `.data/`.
- [`profiles/evidence/`](../profiles/evidence/): historical PuriPuly manual-text/control observations and clip/cable evidence; `issue45/` adds actual GUI-operated translated-audio observations, sanitized raw derivatives and source-bound metric evidence.

```powershell
python -m pip install -e ".[audio]"
python -m tools.prepare_profile_checks
bench profiles
bench profiles --check-ports
bench profiles --require-ready
```

`bench profiles` inspects the tracked catalogue, not private app state. It checks all 14 IDs and six directions, linked files, unique wave membership, same-app exclusion, at most one CPU-local ASR/translation workload, conflicting assigned OSC send/receive ports and explicitly exclusive quota scopes. `--check-ports` attempts exclusive loopback UDP binds and releases them before exit; it cannot reserve ports for a later app, discover dynamic listeners or check TCP control ports. Use before launching the owned apps. A known occupied port is reported as unavailable, not silently reassigned.

Ordinary inspection exits 0 for a valid catalogue even if findings are blocked. `--require-ready` exits 2 unless all profiles have readiness evidence and any requested port check passes. Invalid catalogues exit 2. Ready admission requires observed version/route, effective state evidence, verified microphone/TTS routing, at least one verified direction and an actual no-VRChat audio-to-OSC evidence path. A manual-text OSC trace or source-supported route cannot satisfy it. This is an evidence-presence guard, not automatic certification of the content of an operator record.

The catalogue is **not** a `bench run` plan. Do not replace its null adapter/state fields with fake control acknowledgements. The runner's [long-lived adapter protocol](cli.md#application-adapter-protocol) requires genuine lifecycle observations. The [GUI operator bridge](cli.md#actual-gui-development-pilots) now connects actual GUI actions and explicit manual-state evidence to that protocol; it is not an automated continuous application-state observer. No competing application or PuriPuly source was changed.

## Working waves

The selected arrangement is now **ten sequential single-competitor waves S01–S10**, with four separate nonexecuted PuriPuly reservations accounting for the owner's deferral. See the [catalogue](../profiles/catalog.json) and [wave decision](../profiles/evidence/issue45/sequential-wave-decision.json). This removes simultaneous same-app/local-workload/assigned-port contention without pretending that existing keys provide quota isolation. It is not a main-run freeze.

The original four-wave layout below is retained as history, not the active execution plan:

| Wave | CPU-local profile | Other profiles | Required isolation before activation |
|---|---|---|---|
| W1 | PP4 (ASR) | KIKI2, VRCLT1, VRCT3 | Separate Google projects for KIKI2/VRCLT1; kikitan control TCP 18378 owned exclusively; safe VRCLT passthrough endpoint |
| W2 | VRCT1 (translation) | PP1, VRCS2, KIKI1 | Separate Google projects and attributed OpenRouter keys for PP1/VRCS2; owner-approved mixed PP1 and paid VRCS2 routes still require runtime evidence |
| W3 | VRCT2 (ASR) | VRCLT2, PP2 | Qwen account/workspace quota and ChatGPT entitlement verified; no remaining VRCLT1 process |
| W4 | VRCS1 (ASR) | PP3, VRCLS1 | No remaining VRCS2 process; actual VRCLS package/server entitlement; no simultaneous PP4 Index use |

The selected sequential plan has no known simultaneous same-app, assigned OSC-port or CPU-local workload conflict. Actual owned process/port cleanup is still required between profiles. Shared daily/account/public-IP quotas can accumulate across sequential runs; separate keys and separate times do not create independent Gemini project, Qwen account or OpenRouter capacity.

The revised arrangement loses the intended simultaneous shared-engine pair measurements. PuriPuly pair measurements are additionally deferred by the owner. Record that loss rather than claiming equivalent co-measurement or quota independence. The revision does not authorize a new paid service, route or model substitution.

Stop all leaving-wave capture/inference and confirm ownership before activating the next wave. Same-app configurations may share global settings, keyrings, mutexes or control ports even with separate files. Do not restart apps merely at ordinary audio chunks. Config reloads that require restart are preparation/direction changes and must be disclosed. Never change product silence/idle behavior to improve benchmark results.

## Short checks and measured-run boundary

The ten-second excerpts are the first ten seconds of each **development** bundle, selected before measured app results. This is a reversible working selection, not a final common-video excerpt or human listening judgment. Generation verifies source hashes and copies PCM frames unchanged; local provenance stays in the manifest. Re-run the command after obtaining the issue #2 local assets; missing or changed source audio is an error.

The current runner has one `output_check.audio` per plan. Use a **source-language-specific plan**: English for D1/D2, Chinese for D3/D5, Japanese for D4/D6. Do not feed an English check to a fixed Chinese/Japanese ASR configuration. Each plan uses the corresponding actual audio path plus the existing measured cable calibration. A ten-second output check alone is not an annotated speech stage; actual pilot stages still need correct `speech_intervals` from their reference timeline.

After initial setup, each direction change and resume:

1. Read actual version, microphone/host API, effective source/target, ASR/model/provider route, CPU backend where applicable, OSC destination and voice-output state. Save only allowlisted, redacted fields or cropped screenshots. Preserve private full state separately if necessary.
2. Confirm no VRChat process and no unexpected capture/translation app. Start only the owned profile; keep TTS and raw passthrough off CABLE Input. Supply no OSCQuery/mute signal unless an actual dependency was observed; a true VRChat-process dependency blocks the profile under the parent scope.
3. Stop computer-use screen capture and inference before timed playback. Run the ten-second clip through the runner and retain its ordered raw stream, callback timing, state and manifest. Do not count typing, startup notices or source-only text as proof of translated output.
4. Inspect a few packets against the known clip. If routing/settings are wrong, record operational invalidity. Preserve genuine provider/crash/quota failures as product failures; do not change models or erase the first attempt.

Whole settings/log files are unsafe: kikitan state contains keys; VRCLS can log compressed/base64 full configuration; several products store plaintext keys. Compression and masking a few known field names are not redaction. Publish only safe selected state fields and benchmark-owned non-sensitive text. No passwords, tokens, provider keys, authorization URLs, account identifiers or personal paths belong in public evidence.

VRCT exposed saved provider keys and a connection token in its accessibility tree during operator inspection, even when those fields were outside the visible screenshot. The owner was notified and key rotation recommended. Do not dump whole accessibility trees or query-bearing connection URLs; inspect only necessary controls and explicitly allowlisted values. The exposed values must not enter repository evidence.

## OSC rules and observation status

PuriPuly's installed 2.8.2 control probe produced a short single-message output and a two-page output using **manual synthetic text with translation/capture disabled**. The actual seven-packet trace is retained. Typing false preceded the second page, disproving typing-as-final in this path. After a real direction setting change and application restart, another manual submission produced UDP output without VRChat. These observations do not establish any PP profile's ASR or translation readiness.

The actual VRCS streams include source-only text followed by source-plus-translation and later bilingual utterance-like messages. Actual VRCLT1 streams include rolling bilingual snapshots, source-only and translation-only observations, and output-check context carried into the main stage. VRCT1 supplies a bounded cumulative source/translation expansion between two actual packets. Per-run rules retain uncertain revision/resend/context relationships rather than treating the last packet as universal final output. Unobserved kikitan behavior remains source-derived. Revisions, pagination, resends and new utterances have no universal OSC IDs. Keep grouping/alignment estimates separate; revision/final-dependent metrics remain N/A when ambiguous. A last update is not proof of fully delivered meaning.

## Access/model decisions and remaining prerequisites

- **PP1:** The owner subsequently authorized PuriPuly's actual 26B/31B automatic Gemma route instead of the original 26B-only interpretation. Record the mixed route and actual returned model/provider where exposed; do not label every response 26B or infer provider pinning.
- **PP3/PP4:** Further update, capability, CPU-asset and Index observations are owner-deferred. The earlier isolated 2.8.2 probe did not establish that the owner's normal model store was empty. Do not launch or update PuriPuly to resolve these gaps in this execution.
- **VRCS2:** The owner subsequently authorized the currently configured paid OpenRouter Gemma translation route. This supersedes the planned wholly-free description, not the selected model. Gemini ASR's advertised free tier does not make translation free; measured cost remains unknown until supported by usage evidence. No `:free` substitution or new paid fallback is authorized.
- **KIKI2/VRCLT1:** Same planned model but differing requested modalities. VRCLT1 now has an actual successful Live audio/OSC pilot; KIKI2 still needs its own observation. Separate projects, effective tier and quota isolation remain unverified; sequential scheduling does not establish them.
- **VRCLS1:** The installed generation is now identified as C# 0.7.0-20260913 with existing website-authorized tokens. Its exact server models, token validity and current entitlement remain unverified; historical Python trial limits must not be assigned to it.
- **Usage exports:** OpenRouter per-generation metadata and Qwen minute-level export granularity are documented. The inspected application paths do not provide a complete run-bound provider identity/usage ledger, and no authenticated account export was obtained. PuriPuly ASR request-level usage logging was not found. These are evidence-availability findings, not verified account export access. Actual export acquisition and measured-cost reconciliation remain prerequisites for #7; missing cost is null, never $0.
- **Sign in with ChatGPT:** Neither Luna translation access/limits nor Astra judge access/limits has been exercised. Do not create an API-paid fallback.

The access investigation distinguishes supported configuration from inaccessible measurements: separate keys are configurable but do not prove separate quota projects/accounts; selected sequential waves therefore make no independence claim. VRCT/VRCS expose a requested OpenRouter route, not a verified returned upstream provider or usable per-generation ledger. The actual paid VRCS2 route was owner-approved; no free-route claim survives that decision. VRCLS's installed C# generation is established, but its private server model/entitlement/limits are not exposed by the inspected configuration or public source; saved authorization does not prove validity. No account console/export access or numeric allowance was verified. Existing keys are not authority to invent those values, create new projects, or assume a documented API is enabled for this account.

PP-specific runtime entitlement/export questions remain owner-deferred. The inspected ChatGPT error handling demonstrates that entitlement and usage limits can reject a request, not that Luna or Astra is available. The deferred PP2 translation route and the separate #6 judge-access prerequisite retain that uncertainty; neither receives a paid API fallback.

The preparation deliverable accounts for all fourteen profiles, with five bounded-ready D1 configurations, four owner-deferred PP configurations and five temporarily blocked competitor configurations. The latter are dated operator/access findings, not permanent unsupported-product judgments; KIKI1's earlier native crash remains a separate observed failure. VRCT was last observed capture-OFF with related processes alive; full exit was not established, and no future wave may assume it. The workable sequential plan requires fresh supported cleanup/state confirmation before activation. No all-ready environment, quota independence, complete usage export or completed comparison is claimed.

## Verification performed

- Retained ROOT integration after fixture isolation: `.data/check-venv/Scripts/python.exe -m pytest -q` — **228 passed, 29 subtests passed, no skips**, 38.58 seconds. This precedes the final export-redaction repair and evidence/document reconciliation; it is not a newly repeated full suite.
- The preceding integration run retained **4 failures, 224 passes and 29 subtests**. Four profile checks depended on the production wave layout/readiness paths. Isolated synthetic catalogue fixtures now exercise the same CPU, port, quota and readiness invariants without depending on current pilot results; focused checks passed 6/6 before the successful full suite.
- Before the Qwen port/readiness reconciliation, `python -m bench.cli profiles --catalog profiles/catalog.json --check-ports` exited 0 with four bounded-ready profiles and all 18 then-reserved UDP endpoints available at inspection. `--require-ready` exited 2 as expected for the remaining blocked/deferred profiles. These historical results are not current app cleanup proof or future port reservation.
- Final minimal checks: `tests/test_profiles.py`, `tests/test_gui_pilot.py` and `tests/test_metrics.py` passed **62 tests**; the separately repaired export suite passed **4 tests**. The actual catalog CLI exited 0 with five bounded-ready configurations and nine blocked/deferred findings, validating the selected non-concurrent shared-port arrangement without new audio or a new port-availability claim.
- Publication inspection found private checkout paths inside string-encoded JSON in six public manifest derivatives. The exporter was repaired and those derivatives regenerated; all 65 original capture files and 29 previously exported stream/attempt files retained their bytes. All 35 original/export hash pairs matched. Public export redaction includes nested serialized JSON, but does not replace manual credential/content inspection.

- At the historical preparation checkpoint, installed `bench.exe profiles --check-ports` inspected 14 blocked findings and four waves, exited 0, and bound/released all 18 assigned UDP endpoints successfully. `bench.exe profiles --require-ready` exited 2 with no ready profiles. This is static/evidence admission plus an instantaneous port check, not current app certification. [Historical command evidence](../profiles/evidence/catalogue-cli.json).
- At the earlier preparation checkpoint, `.data/check-venv/Scripts/python.exe -m pytest -q` passed **116 tests and 29 subtests**. Profile behavior coverage includes unsupported readiness promotion, manual-text versus audio evidence, competing CPU workloads, capture/control-port conflicts, shared quota conflicts and occupied sockets.
- The three generated checks each contain **480,000 unchanged PCM frames** at 48 kHz; source-prefix bytes and hashes matched. The installed playback command completed the English ten-second clip with **1,000 callbacks**, explicitly `translation_pilot: false`. [Clip/cable evidence](../profiles/evidence/output-checks.json).
- The real PuriPuly control observations and their negative/corrected setup attempts are retained separately. An invalid `zh-Hans` direction was rejected; `zh-CN` then applied and survived restart. Owned hosts were stopped and the temporary empty encrypted secret store was removed. Those isolated PuriPuly probes did not change private app state; the later owner-authorized competitor preparation did change the five installed configurations.
- The first catalogue smoke exposed an incorrect literal procedure-path lookup; it was corrected before the successful installed-command observations. The first playback attempt lacked the environment's optional audio dependencies; after installing the declared audio extra, the actual playback completed. Neither failure was hidden or classified as a product failure.

**Remaining verification boundary:** the current bounded captures do not establish every competitor profile, complete live quota/usage exports, or simultaneous wave execution. GUI presentation and settings interaction are distinct from translated OSC receipt. Unrelated user background workloads were not isolated; development-pilot timing is not a fair performance ranking. Per-profile evidence and the active catalogue carry the narrower actual outcomes; remaining gaps are not passing tests.
