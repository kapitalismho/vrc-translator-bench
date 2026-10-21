# PuriPuly profiles: PP1–PP4

## Finding and version boundary

Retained actual-GUI PP4 preparation now identifies **PuriPuly 2.9.0**, not merely an owner-reported update. D1 and D3 produced translated-target-language OSC through CPU-auto ASR plus Index official API. The generic catalogue still marks PP4 **blocked** because its required bounded historical no-VRChat admission evidence is unknown; that does not erase the successful output checks. PP1/PP2/PP3 GUI/version history proves neither provider access nor their own pilots. The older **2.8.2** isolated public-CLI/empty-secret-store observations remain historical control evidence; the inspected development checkout was 2.9.0 at `a52fcc97a93d34e040545f388e77a55724cf3c91`.

After the earlier [deferral withdrawal](../../profiles/evidence/issue45/decisions-and-candidate.json), the owner requested [other-app-first preparation](../../profiles/evidence/issue8/owner-use-preparation-order.json), then explicitly **excluded PP1–PP4 from this execution** under the [current batch amendment](../../profiles/evidence/issue8/non-puripuly-batch-amendment.json). PuriPuly manipulation stays suspended. PP3 standalone observation is pending, not performed or waived as complete. All four profiles and six directions remain in the cumulative catalogue. Subsequent owner changes to personal settings are unknown; retained preflights are not current-state guarantees or permission to resume.

| Profile | Planned route | Discovered constraint |
|---|---|---|
| PP1 | Owner-accepted mixed Gemma 4 26B/31B / OpenRouter + Gemini 3.5 Transcribe | Public `gemma4_26b_31b` selection uses a 26B/31B list and latency-based routing. The owner accepted that mixed route; actual returned model/provider, separate access and audio output remain unobserved. |
| PP2 | GPT 6 Luna / Sign in with ChatGPT + Gemini 3.5 Transcribe | `gpt_6_luna` / `chatgpt` was supported in the inspected source and historical installed choices. Existing permitted accounts may be used; runtime entitlement, quota and completed translation remain unverified. No API-paid fallback is authorized. |
| PP3 | Index Translator + Gemini 3.5 Transcribe | Historical 2.8.2 missing-choice evidence is not a 2.9.0 capability finding. PP4's Index output does not establish PP3 Gemini ASR access or output. PP3 remains pending outside this execution. |
| PP4 | Index Translator + CPU-auto ASR | Actual 2.9.0 D1/D3 ten-second checks produced Japanese/Korean OSC; language-specific CPU-auto runtime IDs are retained below. Generic readiness admission remains blocked for missing historical no-VRChat evidence, not missing Index output/assets. |

The source constant for the Gemini ASR route is `gemini-3.5-transcribe-live`; do not replace it with a similarly named file-transcription API. CPU auto-selection must remain `local_cpu_auto`, with actual language-specific runtime model recorded after each direction change. Source intent is not proof that weights loaded or that inference ran on CPU.

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

These observations establish neither returned upstream model/provider identity, tier/usage/cost, thirty-minute stability, restart persistence nor D2/D4/D5/D6 runtime coverage. Fresh authorized admission is required for any later PuriPuly work; the current ten-competitor batch excludes it.


## Historical public control procedure

These commands document the earlier 2.8.2 control probe, not the current execution method or confirmed updated-build interfaces. Resumed PP preparation follows the [existing actual-GUI requirement](../profiles.md#gui-preparation-of-installed-applications); removing the deferral does not revoke that requirement.

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

Use PP1/2/3/4 send ports 19101/19102/19103/19104 and receive ports 19201/19202/19203/19204. In the historical isolated control procedure, the loopback host was established in the dedicated bootstrap and checked through `osc status`; no mute signal or OSCQuery was needed for its manual-output path. Its no-VRChat direction/restart observation must not be transferred to the later PP4 preflight windows. PP4 audio-to-OSC output is now retained above, with historical process absence still unknown.

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

PP1 and VRCS2 can be configured with independent Google credentials. Project-scoped isolation requires **distinct projects**, not merely two keys in one project; distinct OpenRouter keys permit attribution but do not prove separate account-level capacity. The [owner-approved quota amendment](../../profiles/evidence/issue8/quota-isolation-amendment.json) permits shared/unverified quotas for the D1/D3 batch only, without changing accounts, keys, tiers or routes. The later competitor-only amendment excludes PP1–PP4 from this execution. Neither amendment establishes isolation, numeric limits or measured cost.

The source OpenRouter request for the combined Gemma selection contains `google/gemma-4-26b-a4b-it` and `google/gemma-4-31b-it`, provider `only` list `cloudflare`, `coreweave/fp4`, `deepinfra/turbo`, `dekallm/bf16`, `nextbit/bf16`, `makora`, latency sorting and `allow_fallbacks: true`. The public selection is not a single-provider pin. Record response identity rather than the UI label. PuriPuly's inspected LLM timing observation retains `actual_model` and token counts but does not retain OpenRouter generation ID/upstream provider name there. OpenRouter's authenticated per-generation metadata API documents `model`, `provider_name`, token counts, `created_at`, `total_cost` and ID. Export access and matching actual account records remain untested; missing evidence is not $0.

Gemini ASR implementation was searched for usage/token/billing handling: no usage-metadata capture was found. Public diagnostic/ASR state can describe runtime/recovery, not a demonstrated per-request ASR billing ledger. Provider-side project usage export is required before cost reconciliation; its availability/granularity remains unknown. Do not infer billable duration from transcript length or local capture time.

The ChatGPT source handles subscription ineligibility, route-not-supported and usage-limit responses. A supported login command does not establish the owner's entitlement, numeric limits, export availability or the planned GPT 6 Astra judge access. Both Luna translation authorization and Astra evaluation access remain unverified; neither receives a paid API fallback.

## Observed OSC and limits

Historical public-safe **manual control** evidence: [`../../profiles/evidence/puripuly-control.jsonl`](../../profiles/evidence/puripuly-control.jsonl), [`../../profiles/evidence/puripuly-direction-resume.jsonl`](../../profiles/evidence/puripuly-direction-resume.jsonl), and [`../../profiles/evidence/puripuly-control.json`](../../profiles/evidence/puripuly-control.json). The separate actual 2.9.0 PP4 preflights are documented above.

These are real application UDP messages from **manual synthetic text, translation disabled, capture off**, not PP1–PP4 microphone/translation results. The development benchmark excludes synthetic-speech tracks; this control probe is not such a track and supplies no benchmark score.

- A short submitted text produced typing true, one `/chatbox/input` with `[text, true, false]`, then typing false.
- One long submission produced two text messages; its second page arrived about 3.03 seconds after the first. Typing false occurred **before** page two: it is not a final-output marker.
- This known manual submission establishes pagination in this control path. It does not establish that arbitrary pairs of live messages are pages rather than new utterances/revisions.
- Source documentation describes progressive corrections and suppression of an identical compatible final result. Neither revisions nor resend behavior were empirically isolated here.
- A later manual submission after en→zh-CN configuration and restart still emitted the source text, because translation was disabled. This confirms resumed control/output, not Chinese translation correctness.

PP4 now has observed ten-second audio-to-translated-target-language OSC examples for D1/D3, not semantic-quality or all-direction certification. PP1/PP2/PP3 still lack their own audio-to-OSC checks. Revision-dependent metrics remain N/A where ambiguous; no universal final-output reconstruction is supplied.

## Sources

- [Public CLI at inspected revision](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/docs/cli.md)
- [OSC contract](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/docs/vrchat-osc.md)
- [Model resolution](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/src/puripuly_heart/config/runtime_resolution.py)
- [OpenRouter payload and response handling](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/src/puripuly_heart/providers/llm/openrouter.py)
- [LLM observation fields](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/src/puripuly_heart/core/llm/latency.py)
- [Gemini ASR](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/src/puripuly_heart/providers/stt/gemini_transcribe.py)
- [Secret store construction](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/src/puripuly_heart/app/wiring/wiring_secrets_factory.py)
- [OpenRouter generation metadata](https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation)
