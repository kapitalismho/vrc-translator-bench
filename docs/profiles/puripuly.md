# PuriPuly profiles: PP1–PP4

## Finding and version boundary

All four profiles are **owner-deferred / blocked**, not ready or unsupported. The owner explicitly excluded PP1–PP4 from the current empirical pass: do not launch, update, build or run PuriPuly for these pilots. The historical 2026-10-20 installed snapshot identified **2.8.2**, whose public CLI was exercised with isolated configuration and an empty encrypted secret store. The inspected development checkout identified **2.9.0**, commit `a52fcc97a93d34e040545f388e77a55724cf3c91`. Do not transfer capabilities between these builds or treat that historical snapshot as a new current-version observation.

The deferral supersedes the earlier planned owner update to 2.9.0. No completed update, Index execution or new PuriPuly translation is claimed. Keep earlier control-only evidence intact. Missing CPU assets in the fresh isolated probe never established that the owner's normal model store was empty.

| Profile | Planned route | Discovered constraint |
|---|---|---|
| PP1 | Owner-accepted mixed Gemma 4 26B/31B / OpenRouter + Gemini 3.5 Transcribe | Public `gemma4_26b_31b` selection uses a 26B/31B list and latency-based routing. The owner accepted that mixed route; actual returned model/provider, separate access and audio output remain unobserved and are now deferred. |
| PP2 | GPT 6 Luna / Sign in with ChatGPT + Gemini 3.5 Transcribe | `gpt_6_luna` / `chatgpt` is supported in the source and installed choices. No benchmark subscription authorization, entitlement, quota or completed translation was observed. No API-paid fallback is authorized. |
| PP3 | Index Translator + Gemini 3.5 Transcribe | Installed 2.8.2 choices lack `index_translate_35b`; inspected 2.9.0 source supports it. A matching installed build and isolated Google project are required. “Free” translation does not establish zero ASR charges. |
| PP4 | Index Translator + CPU-auto ASR | Same historical installed Index mismatch. The isolated probe's missing assets are not a claim about the normal model store. No CPU model load/recognition was performed; further observation is owner-deferred. |

The source constant for the Gemini ASR route is `gemini-3.5-transcribe-live`; do not replace it with a similarly named file-transcription API. CPU auto-selection must remain `local_cpu_auto`, with actual language-specific runtime model recorded after each direction change. Source intent is not proof that weights loaded or that inference ran on CPU.

## Historical public control procedure — do not execute during deferral

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

Use PP1/2/3/4 send ports 19101/19102/19103/19104 and receive ports 19201/19202/19203/19204. The loopback host is established in the dedicated bootstrap and checked through `osc status`. Disable `vrc_mic_intercept`; no mute signal or OSCQuery was needed for the observed manual-output path. No VRChat process was present before the direction/restart output observation. Audio-to-OSC dependence remains unverified.

Language codes observed in choices include `en`, `ja`, `zh-CN`, `ko`. Map D1 en→ja, D2 en→zh-CN, D3 zh-CN→ko, D4 ja→ko, D5 zh-CN→ja, D6 ja→en. `zh-Hans` was rejected; the corrected `zh-CN` applied and persisted across restart. Language catalog support is not verified engine coverage.

Provider changes, only after inspecting the selected build's choices:

- PP1: `stt.provider: gemini_transcribe`, `translation.model: gemma4_26b_31b`, `translation.connection: openrouter` describes the discovered mixed-model route, which the owner accepted before deferring all PP execution. Preserve the mixed26B/31B identity; do not launch this profile during the deferral.
- PP2: `stt.provider: gemini_transcribe`, `translation.model: gpt_6_luna`, `translation.connection: chatgpt`. `auth login chatgpt --open-browser` is an explicit operator action; `auth status` must confirm it. Do not enroll or purchase a fallback.
- PP3: `stt.provider: gemini_transcribe`, `translation.model: index_translate_35b`, `translation.connection: public_api`, only on a build advertising these choices.
- PP4: as PP3, but `stt.provider: local_cpu_auto`. Prepare required assets through public `models` commands; record `models status` and `asr status`, not guessed CPU model IDs.

Index has an important normal product behavior: its availability check may persist a switch to managed Gemma, or OpenRouter when managed allowance is exhausted. Inspect effective route after enabling translation, direction changes and resume. A switch makes an Index-labelled measurement invalid; do not silently count another route as Index or suppress the product's fallback behavior.

Before a measured stage, use the runner's ten-second audio check, and stop all GUI/computer-use capture/inference during timed playback. Use supported CLI queries/events for observations. Do not restart at ordinary chunk boundaries. On cleanup, `capture set self off`, verify effective stopped state, then `app stop` for the owned config. Do not log out a personal account or stop by arbitrary PID.

No auto-update toggle was established from the public CLI. Pin/hash the executable and record version at preparation/resume/end; do not accept an update during measurement. The isolated probe did not install or update the app.

## Credentials, limits and retained evidence

PP1 and VRCS2 can be configured with independent Google credentials. Isolation requires **distinct projects** for project-scoped Gemini quotas, not merely two keys in one project. Record project aliases and usage windows; no secret values. Distinct OpenRouter keys permit attribution but do not prove separate account-level quotas. No benchmark keys/projects were provisioned or validated.

The source OpenRouter request for the combined Gemma selection contains `google/gemma-4-26b-a4b-it` and `google/gemma-4-31b-it`, provider `only` list `cloudflare`, `coreweave/fp4`, `deepinfra/turbo`, `dekallm/bf16`, `nextbit/bf16`, `makora`, latency sorting and `allow_fallbacks: true`. The public selection is not a single-provider pin. Record response identity rather than the UI label. PuriPuly's inspected LLM timing observation retains `actual_model` and token counts but does not retain OpenRouter generation ID/upstream provider name there. OpenRouter's authenticated per-generation metadata API documents `model`, `provider_name`, token counts, `created_at`, `total_cost` and ID. Export access and matching actual account records remain untested; missing evidence is not $0.

Gemini ASR implementation was searched for usage/token/billing handling: no usage-metadata capture was found. Public diagnostic/ASR state can describe runtime/recovery, not a demonstrated per-request ASR billing ledger. Provider-side project usage export is required before cost reconciliation; its availability/granularity remains unknown. Do not infer billable duration from transcript length or local capture time.

The ChatGPT source handles subscription ineligibility, route-not-supported and usage-limit responses. A supported login command does not establish the owner's entitlement, numeric limits, export availability or the planned GPT 6 Astra judge access. Both Luna translation authorization and Astra evaluation access remain unverified; neither receives a paid API fallback.

## Observed OSC and limits

Public-safe raw evidence: [`../../profiles/evidence/puripuly-control.jsonl`](../../profiles/evidence/puripuly-control.jsonl), [`../../profiles/evidence/puripuly-direction-resume.jsonl`](../../profiles/evidence/puripuly-direction-resume.jsonl), and [`../../profiles/evidence/puripuly-control.json`](../../profiles/evidence/puripuly-control.json).

These are real application UDP messages from **manual synthetic text, translation disabled, capture off**, not PP1–PP4 microphone/translation results. The development benchmark excludes synthetic-speech tracks; this control probe is not such a track and supplies no benchmark score.

- A short submitted text produced typing true, one `/chatbox/input` with `[text, true, false]`, then typing false.
- One long submission produced two text messages; its second page arrived about 3.03 seconds after the first. Typing false occurred **before** page two: it is not a final-output marker.
- This known manual submission establishes pagination in this control path. It does not establish that arbitrary pairs of live messages are pages rather than new utterances/revisions.
- Source documentation describes progressive corrections and suppression of an identical compatible final result. Neither revisions nor resend behavior were empirically isolated here.
- A later manual submission after en→zh-CN configuration and restart still emitted the source text, because translation was disabled. This confirms resumed control/output, not Chinese translation correctness.

No profile has an observed ten-second microphone-to-translated-OSC example. Revision-dependent metrics remain N/A. No universal final-output reconstruction is supplied.

## Sources

- [Public CLI at inspected revision](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/docs/cli.md)
- [OSC contract](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/docs/vrchat-osc.md)
- [Model resolution](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/src/puripuly_heart/config/runtime_resolution.py)
- [OpenRouter payload and response handling](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/src/puripuly_heart/providers/llm/openrouter.py)
- [LLM observation fields](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/src/puripuly_heart/core/llm/latency.py)
- [Gemini ASR](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/src/puripuly_heart/providers/stt/gemini_transcribe.py)
- [Secret store construction](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/src/puripuly_heart/app/wiring/wiring_secrets_factory.py)
- [OpenRouter generation metadata](https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation)
