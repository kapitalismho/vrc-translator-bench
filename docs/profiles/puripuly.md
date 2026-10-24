# PuriPuly profiles: PP1–PP4

## Finding and version boundary

Retained **PuriPuly2.9.1** [actual CLI-driven source/lifecycle checks](../../profiles/evidence/issue8/pp291-current-preflights.json) cover PP1–PP4 in D1/D3. The old owned host was normally closed, then the supported product command-line `run-gui` entrypoint actually launched a fresh desktop GUI host; all settings/capture/status/stop used the public `puripuly` CLI. Do not substitute `puripuly app start/restart`: those commands launch headless. The [installed-build amendment](../../profiles/evidence/issue8/pp291-installed-build-amendment.json) records the prelaunch identity change and zero-main R hold. The earlier [2.9.0 GUI checks and full cleanup](../../profiles/evidence/issue8/pp-restored-v1/current-preflights.json), older PP4 captures and2.8.2 isolated control observations remain history, not new-build admission. Startup checks do not establish main quality or cost; the installed release commit remains unattested.

The [restoration amendment](../../profiles/evidence/issue8/puripuly-restoration-amendment.json), [continuation-only authority](../../profiles/evidence/issue8/continuation-only-amendment.json) and [repair-and-retry amendment](../../profiles/evidence/issue8/repair-retry-amendment.json) retain their historical schedules and no-replay boundaries. The [owner-resumed execution recipe](../../profiles/evidence/issue8/owner-resumed-pp-v1/execution-recipe.json) released the intervening owner reservation and was executed in order: same-ledger PP4D3 continuation, PP1 D1/D3, PP2 D1/D3, PP3 standalone D1, then PP3 D1/D3. All eight phases are terminal and registered in the [capture-completion record](../../profiles/evidence/issue8/owner-resumed-pp-v1/capture-completion.json), with standalone kept outside the primary population. Completed peers were not replayed; VRCLS D1 is registered and D3 is quota-stopped. D1 startup used the [common40s excerpt](../../profiles/evidence/issue8/d1-startup-check-amendment.json), while D3 used10s. Tone/Korean review stays removed.

| Profile | Selected route | 2.9.1 preflight D1 / D3 target inputs |
|---|---|---|
| PP1 | Owner-accepted mixed Gemma4 26B/31B / OpenRouter + Gemini3.5 Transcribe | 7 / 2 |
| PP2 | GPT6Luna / existing ChatGPT connection + Gemini3.5 Transcribe | 9 / 2 |
| PP3 | Index official API + Gemini3.5 Transcribe | 9 / 2 |
| PP4 | Index official API + CPU-auto ASR | 10 / 2 |

The source constant for the Gemini ASR route is `gemini-3.5-transcribe-live`; do not replace it with a similarly named file-transcription API. CPU auto-selection must remain `local_cpu_auto`, with actual language-specific runtime model recorded after each direction change. Source intent is not proof that weights loaded or that inference ran on CPU.

Each2.9.1 slot ran once, CLI exit0 and four done stages with no invalid/product failure. D1 used40s and D3 used10s, each with the existing one-second silent lifecycle and separate tails. Actual destination text was inspected against the source, then consumed through the field interpreter with new capture-bound rules. Silent-lifecycle OSC was zero, not a full nonspeech/FPR result. Initialized running ASR was `parakeet-tdt-0.6b-v3-int8-sherpa` for PP4 D1, `qwen3-asr-0.6b-int8-sherpa` for PP4 D3 and `gemini-3.5-transcribe-live` for PP1–PP3.

All four profiles sent to19104; receive ports were19204 for PP4 and19201 for PP1–PP3. The [historical port record](../../profiles/evidence/issue8/pp-restored-v1/actual-osc-port-decision.json) preserves PP1's displayed19101 versus effective19104 mismatch; it was not silently repaired. Nonconcurrent reuse requires fresh wave-local uniqueness. Requested routes are not returned-model/provider or server-fallback attestation; quota and attributable cost remain unestablished. The2.9.0 [normal full-app cleanup](../../profiles/evidence/issue8/pp-restored-v1/normal-cleanup.json) is historical. After all2.9.1 diagnostics, the fresh GUI host was retained STOPPED with terminal-applied PP4D1 settings and a clean new-instance record in the original journal root; the old journal was not reset. No new account, paid fallback or completed-main replay occurred.

The [current2.9.1 output-route source evidence](../../profiles/evidence/issue8/pp291-voice-output-basis.json) establishes a text/UI/OSC-only selected translation composition, with no synthesized-voice destination or TTS enable setting in the inspected path. Adapter `voice_output=false` is source-derived unsupported-route metadata, not runtime TTS telemetry. Its frozen `Pinned2.9.0` wording is not silently relabeled or treated as new-build evidence. This does not claim the whole process or OS can never emit sound.

The renewed continuation recovered two stranded hosts by bounded normal Windows close handling under the [legacy-host amendment](../../profiles/evidence/issue8/pp-legacy-host-normal-close-amendment.json), without force termination. The owned host's earlier public `app stop` result remains `unknown_execution`, not retrospectively successful. A fresh original-config `run-gui` host then passed actual PP4D3 source playback, Korean OSC output, and supported capture-stop/replacement-controller OFF checks. Those observations precede new main work and do not replace per-phase guarded admission.

The later eight-phase execution completed on2026-10-24UTC under capture revision `eb286b1bdc82972f9222054968c813ab32e304d9`. PP1/D3's zero-frame Cable-open failure was recovered by exact-name fresh-process native resume; its nine completed primary chunks and seven completed isolated items were not replayed. Final owned-host `app stop` returned exit0 and terminal `stopped`; its `cleanup_outcome=unobserved` remains verbatim, with exact owned-process absence independently observed and the capture journal/UDP reservation cleared. Native provider/ASR errors and cancellations remain preserved separately from work-DONE status. These are capture and owned-cleanup outcomes, not completed quality or cost analysis.

Retained native metadata establishes an Index success and503 followed by a provider rebuild and Gemma401 attempts during original PP4D3 chunk05. Preserve that rawDONE chunk and all original failures; do not replay it or infer the actor/settings-commit cause. Whole-chunk pure-Index exclusion and any dependent cross-attempt output uncertainty belong in a separately hash-bound analysis overlay, not rewritten capture history. The PP-only W4 and PP3 standalone records cannot be labeled a measured concurrent-peer load contrast.

## Retained 2.9.0 PP4 preflights

The [public-safe summary](../../profiles/evidence/issue8/pp4-preflight.json) binds retained observation/stop records, local GUI images, terminal manifests, native streams and public derivatives by SHA-256. GUI executable SHA-256: `2f9b9938e0b7e03731f7cfa57056a68f78d05eb099312f6c07e9b71a8440ac31`. Retained installer identity: `PuriPulyHeart-Setup-2.9.0.exe`, SHA-256 `2b2232a4cb6c7876fc2d26957338d10021e4abef3f418d0423f221299b9a3193` (owner-supplied identity; not copied or rehashed in this reconciliation).

Actual GUI settings were `local_cpu_auto`, `index_translate_35b`, `public_api`, CABLE Output on Windows WASAPI (Compatibility Mode), OSC `127.0.0.1:19104` / receive `19204`, peer capture off and no TTS enabled. Retained public read-only `asr status` corroborated running CPU-auto providers/resources/live capture. This is not a new state query or independent compute-backend instrumentation.

| Direction | Runtime ASR | Terminal work | Recorded output |
|---|---|---|---|
| D1 en→ja | `parakeet-tdt-0.6b-v3-int8-sherpa` | 4 done, 0 product failure, 0 invalid/pending | 1,100 callbacks; 2 Japanese chatbox inputs, 4 typing packets |
| D3 zh-CN→ko | `qwen3-asr-0.6b-int8-sherpa` | 4 done, 0 product failure, 0 invalid/pending | 1,100 callbacks; 2 Korean chatbox inputs, 4 typing packets |

Each run contains setup, direction, a **ten-second development output check + 15-second tail**, then a **one-second silent lifecycle + two-second tail**. The check accounts for 1,000 callbacks and all six OSC packets; the lifecycle accounts for 100 callbacks and no OSC. This is not the full nonspeech protocol or a zero-hallucination certification. TALK was stopped through the actual GUI at `10:18:31.620921Z` (D1) and `10:26:41.678688Z` (D3); the owned app was retained, not fully exited. Terminal session-end records are present; numeric runner exit codes are not supplied by these sources.

Representative raw `/chatbox/input` payloads, each with `true, false` flags:

- D1 receive sequence 2: `えーっと…今日はポケットに何か入ってる？`; sequence 5: `今すぐこれやらないといけないのかな？`
- D3 receive sequence 2: `제 말은, 추석 말이죠. 그러니까...`; sequence 5 expands that Korean text to `제 말은, 추석 말이죠. 그러니까... 사람들이 중국을 더 잘 이해할 수 있도록... 음... 어떤 활동을 해야 한다는 거죠, 그렇죠?`

The runner's output-check guard only requires nonempty `/chatbox/input`; inspection separately establishes Japanese/Korean target-language text, **not source-meaning equivalence, accuracy or completeness**. Typing is not translated output or universal finality. The D3 same-prefix expansion is a bounded update observation, not a reconstructed utterance/page/finality rule. Old D1 GUI text visible before D3 audio is not D3 output.

Public derivatives: [D1 manifest](../../profiles/evidence/issue8/pp4-d1-preflight/manifest.json), [D1 provenance](../../profiles/evidence/issue8/pp4-d1-preflight/export-provenance.json), [D3 manifest](../../profiles/evidence/issue8/pp4-d3-preflight/manifest.json), [D3 provenance](../../profiles/evidence/issue8/pp4-d3-preflight/export-provenance.json). The actual exporter produced six files per run. All twelve native/derivative hash pairs matched; four files were byte-identical and eight path-redacted. Numeric timing/order and benchmark text were retained; repository/user paths, including serialized JSON, were redacted. Original runs are unchanged. Raw diagnostics, personal settings/private backups, credentials, executables, installer and GUI images were not exported.

These earlier observations establish neither returned upstream identity, cost, thirty-minute stability nor later-direction coverage. The separately identified fresh eight-slot checks above supply restored-cohort operational admission; neither set is a main measurement.


## Current public CLI control

The [owner's CLI-control amendment](../../profiles/evidence/issue8/puripuly-cli-control-amendment.json) authorizes ongoing public-CLI preparation, settings, start/stop, status and normal owned-instance lifecycle for PP1–PP4, superseding PuriPuly's GUI-only requirement. Other applications are unchanged. Use the original installed instance and existing authorized accounts/routes, not a new isolated profile or direct live-config edits.

On the installed 2.9.0 instance, `settings choices` and `settings apply --help` confirmed the supported interface. An actual `settings apply --file … --expected-revision 2` committed revision3 with `settings_commit_success_runtime_applied`. Subsequent `settings current`, `app status`, `capture status`, `osc status` and `overlay status` confirmed PP4 English→Japanese, exact Cable/WASAPI compatibility selection, CPU-auto ASR, Index/public API, effective manual send19104/receive19204 and inactive self/peer capture, translation and overlay. The GUI also showed CPU-auto and Index. See [bounded preparation evidence](../../profiles/evidence/issue8/pp4-cli-preparation.json); this is not a new output check, restart-persistence claim or main result.

The continuation adapter implements the existing runner stdio protocol using the installed public CLI. It binds the original configuration and actual host PID/instance, checks ownership before mutation, distinguishes accepted/pending/terminal operations from effective state, and uses revision-guarded settings changes. It neither starts a replacement host automatically nor presents CLI observations as GUI evidence. Other translators keep their GUI bridge.

One [actual PP4 D1 control lifecycle](../../profiles/evidence/issue8/pp-cli-lifecycle-check.json) observed effective CPU-auto/Parakeet capture plus translation, then self/peer capture and translation OFF with ASR resources released. The host remained open. No benchmark audio or translated-output test was replayed. Ordinary chunks retain capture; supported cleanup stops self capture/translation before any normal owned-app shutdown.

The subsequent [controlled failure-boundary repair](../../profiles/evidence/issue8/pp-cli-failure-repair.json) retains known operation IDs from official `unknown_execution` receipts even without a top-level `terminal` flag. Resolve owned uncertain operations without replaying mutations: unsupported/requested cancellation or momentary OFF cannot certify cleanup. Observed provider failures cross stdio as `product/provider`; identity/revision/transport uncertainty remains operational, and cleanup preserves the first failure. The separate44 controlled checks exercised real stdio and runner control/ledger boundaries, not additional native activation or measurement.

That same-controller repair did not preserve ownership across controller replacement. The [subsequent recovery repair](../../profiles/evidence/issue8/pp-cli-recovery-repair.json) journals responsibility and delivery uncertainty before dispatch, bound to the actual owned host PID/instance and CLI/config identity. Fresh `read_state`/resume cannot declare stopped cleanup while responsibility remains. Resolve the original operation and confirm OFF before release; changing scratch directories or deleting/resetting journals is not recovery. Unknown-ID uncertainty remains an operational blocker requiring explicit owned-host lifecycle reconciliation. Its separate63 recovery and44 retained-boundary checks used controlled transport, not native fault injection.


## Historical public control procedure

The commands below document the earlier 2.8.2 isolated control probe. Its dedicated-config bootstrap and credential isolation are historical test conditions, not instructions to replace the current owner-approved installed profile. Validate current command choices and instance identity before use; the CLI-control amendment above governs current PuriPuly execution.

Use the same explicit `--config <dedicated-settings-path>` on every command. A distinct config alone does **not** isolate Windows keyring credentials: the default keyring service is shared. Use a dedicated Windows benchmark account, or initialize a new canonical config with `intent.secrets.backend: encrypted_file` and a private relative `encrypted_file_path`, and supply `PURIPULY_HEART_SECRETS_PASSPHRASE` only in the owned process environment. Clear inherited provider credential variables. Do not copy personal settings or secrets. The isolated probe used fresh APPDATA/LOCALAPPDATA/USERPROFILE directories, an environment allowlist and no provider credentials.

Initial bootstrap files must include `settings_version`, `intent` **and** `state`; schema version must match the actual application. The first incomplete bootstrap failed with `CanonicalSettingsPersistenceError`; the corrected schema-51 bootstrap started successfully. Subsequent settings changes use the public owner, never direct rewrites of a live config.

With `<pp>` denoting `puripuly.exe --config <dedicated-settings-path> --timeout 30`:

```text
<pp> app start --background
<pp> capabilities
<pp> settings choices
<pp> audio devices list
<pp> settings current
<pp> settings apply --file changes.json --expected-revision <observed-revision>
<pp> query providers.status
<pp> capture status
<pp> asr status
<pp> models status
<pp> osc status
<pp> translation set on
<pp> capture set self on
```

Record completed operation status, committed settings and effective channel/OSC state. `translation_runtime_ready` only means a provider attached, not that a request succeeded. Stop peer capture and overlays; no peer audio or TTS belongs on the injection route. Choose the exact CABLE Output name from `audio devices list`, and `Windows WASAPI (Compatibility Mode)` (shared-mode path). The observed name was `CABLE Output(VB-Audio Virtual Cable)`.

Supported focused change shape observed on 2.8.2:

```json
{
  "changes": {
    "audio.input_host_api": "Windows WASAPI (Compatibility Mode)",
    "audio.input_device": "CABLE Output(VB-Audio Virtual Cable)",
    "languages": {"source": "en", "target": "ja", "secondary_target": ""},
    "osc.connection": {"mode": "manual", "send_port": 19104, "receive_port": 19204},
    "chatbox.activation_notice.enabled": false
  }
}
```

The original requested PP1/2/3/4 send ports were19101/19102/19103/19104, with receive ports19201/19202/19203/19204. Fresh PP1 preparation displayed19101 but retained actual manual send19104/receive19201, including after a separate normal-GUI commit. The [observed-port decision](../../profiles/evidence/issue8/pp-restored-v1/observed-port-decision.json) permits using the corroborated effective endpoint: PuriPuly profiles occupy different waves, so nonconcurrent send19104 reuse is allowed with fresh per-profile evidence and wave-local uniqueness. Do not claim the requested port worked, repair product code or bypass normal settings. Freeze actual admitted routes before main measurement. Historical control findings are not current runtime admission.

Language codes observed in choices include `en`, `ja`, `zh-CN`, `ko`. Map D1 en→ja, D2 en→zh-CN, D3 zh-CN→ko, D4 ja→ko, D5 zh-CN→ja, D6 ja→en. `zh-Hans` was rejected; the corrected `zh-CN` applied and persisted across restart. Language catalog support is not verified engine coverage.

Provider changes, only after inspecting the selected build's choices:

- PP1: `stt.provider: gemini_transcribe`, `translation.model: gemma4_26b_31b`, `translation.connection: openrouter` describes the discovered mixed-model route accepted by the owner. Preserve the mixed26B/31B identity after the deferral withdrawal.
- PP2: `stt.provider: gemini_transcribe`, `translation.model: gpt_6_luna`, `translation.connection: chatgpt`. `auth login chatgpt --open-browser` is an explicit operator action; `auth status` must confirm it. Do not enroll or purchase a fallback.
- PP3: `stt.provider: gemini_transcribe`, `translation.model: index_translate_35b`, `translation.connection: public_api`, only on a build advertising these choices.
- PP4: as PP3, but `stt.provider: local_cpu_auto`. Prepare required assets through public `models` commands; record `models status` and `asr status`, not guessed CPU model IDs.

Index has an important normal product behavior: its availability check may persist a switch to managed Gemma, or OpenRouter when managed allowance is exhausted. Inspect effective route after enabling translation, direction changes and resume. A switch makes an Index-labelled measurement invalid; do not silently count another route as Index or suppress the product's fallback behavior.

Before a measured stage, use the runner's ten-second audio check, and stop all GUI/computer-use capture/inference during timed playback. Use supported CLI queries/events for observations. Do not restart at ordinary chunk boundaries. On cleanup, `capture set self off`, verify effective stopped state, then `app stop` for the owned config. Do not log out a personal account or stop by arbitrary PID.

No auto-update toggle was established from the public CLI. Pin/hash the executable and record version at preparation/resume/end; do not accept an update during measurement. The isolated probe did not install or update the app.

## Credentials, limits and retained evidence

PP1 and VRCS2 can be configured with independent Google credentials. Project-scoped isolation requires **distinct projects**, not merely two keys in one project; distinct OpenRouter keys permit attribution but do not prove separate account-level capacity. The [owner-approved quota amendment](../../profiles/evidence/issue8/quota-isolation-amendment.json), retained by the restoration amendment, permits shared/unverified quotas for the D1/D3 batch only, without changing accounts, keys, tiers or routes. It establishes neither isolation, numeric limits nor measured cost.

The source OpenRouter request for the combined Gemma selection contains `google/gemma-4-26b-a4b-it` and `google/gemma-4-31b-it`, provider `only` list `cloudflare`, `coreweave/fp4`, `deepinfra/turbo`, `dekallm/bf16`, `nextbit/bf16`, `makora`, latency sorting and `allow_fallbacks: true`. The public selection is not a single-provider pin. Record response identity rather than the UI label. PuriPuly's inspected LLM timing observation retains `actual_model` and token counts but does not retain OpenRouter generation ID/upstream provider name there. OpenRouter's authenticated per-generation metadata API documents `model`, `provider_name`, token counts, `created_at`, `total_cost` and ID. Export access and matching actual account records remain untested; missing evidence is not $0.

Gemini ASR implementation was searched for usage/token/billing handling: no usage-metadata capture was found. Public diagnostic/ASR state can describe runtime/recovery, not a demonstrated per-request ASR billing ledger. Provider-side project usage export is required before cost reconciliation; its availability/granularity remains unknown. Do not infer billable duration from transcript length or local capture time.

The ChatGPT source handles subscription ineligibility, route-not-supported and usage-limit responses. Fresh PP2 D1/D3 checks produced source-specific target-language candidates using the existing connected account and selected Luna route, without new login or payment. They establish neither numeric allowance, returned upstream identity, export access nor the separate Astra judge's current availability. No paid API fallback is authorized.

## Observed OSC and limits

Historical public-safe **manual control** evidence: [`../../profiles/evidence/puripuly-control.jsonl`](../../profiles/evidence/puripuly-control.jsonl), [`../../profiles/evidence/puripuly-direction-resume.jsonl`](../../profiles/evidence/puripuly-direction-resume.jsonl), and [`../../profiles/evidence/puripuly-control.json`](../../profiles/evidence/puripuly-control.json). The separate actual 2.9.0 PP4 preflights are documented above.

These are real application UDP messages from **manual synthetic text, translation disabled, capture off**, not PP1–PP4 microphone/translation results. The development benchmark excludes synthetic-speech tracks; this control probe is not such a track and supplies no benchmark score.

- A short submitted text produced typing true, one `/chatbox/input` with `[text, true, false]`, then typing false.
- One long submission produced two text messages; its second page arrived about 3.03 seconds after the first. Typing false occurred **before** page two: it is not a final-output marker.
- This known manual submission establishes pagination in this control path. It does not establish that arbitrary pairs of live messages are pages rather than new utterances/revisions.
- Source documentation describes progressive corrections and suppression of an identical compatible final result. Neither revisions nor resend behavior were empirically isolated here.
- A later manual submission after en→zh-CN configuration and restart still emitted the source text, because translation was disabled. This confirms resumed control/output, not Chinese translation correctness.

Fresh PP1–PP4 D1/D3 checks supply per-direction translation-only payload observations and extraction rules. Typing false is not finality; no universal page/revision/resend relationship is asserted. Revision-dependent metrics remain N/A where ambiguous. These checks do not certify semantic quality, long-run health or unmeasured directions.

## Sources

- [Public CLI at inspected revision](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/docs/cli.md)
- [OSC contract](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/docs/vrchat-osc.md)
- [Model resolution](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/src/puripuly_heart/config/runtime_resolution.py)
- [OpenRouter payload and response handling](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/src/puripuly_heart/providers/llm/openrouter.py)
- [LLM observation fields](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/src/puripuly_heart/core/llm/latency.py)
- [Gemini ASR](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/src/puripuly_heart/providers/stt/gemini_transcribe.py)
- [Secret store construction](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/src/puripuly_heart/app/wiring/wiring_secrets_factory.py)
- [OpenRouter generation metadata](https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation)
