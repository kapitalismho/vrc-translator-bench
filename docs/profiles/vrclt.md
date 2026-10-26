# VRCLT: VRCLT1 and VRCLT2

**Current R1 contract:** use the [episode-native CLI](../cli.md), [scope catalog](../../profiles/catalog.json) and [R1 evidence boundary](../benchmark-implementation-plan.md#r1-implementation-and-actual-feasibility). VRCLT2 ordinary EN→ZH self evidence retains mixed OSC display text and a separate FINAL-log crosscheck. Qwen3.8 auto-detects source language; a configured source is not an enforced provider constraint. Dashboard `translation_on`, not `outbound.enabled`, controls translation; OFF remains raw passthrough, not microphone mute.

The following six-direction preparation and extraction rules are historical, not a second schema-2 collector or new admission.

Initial source preparation was recorded on **2026-10-20** for [issue #4](https://github.com/kapitalismho/vrc-translator-bench/issues/4), under the [parent protocol](https://github.com/kapitalismho/vrc-translator-bench/issues/1). The actual-GUI observations below supersede historical absence/current-setting claims in [`profiles/findings/vrclt.json`](../../profiles/findings/vrclt.json).

## Current D1/D3 short preflights

The [current normal-GUI record](../../profiles/evidence/issue8/vrclt-current-preflights.json) covers both installed 1.0.1 profiles in D1 and D3. Saved-route-first order was VRCLT2 Qwen/Beijing D1/D3, then VRCLT1 Gemini D1/D3. All four CLI exits were 0; each check submitted 480,000 speech frames followed by 48,000 silent lifecycle frames. Eighteen translated chatbox inputs were retained, with none during silent stages. Normal GUI Quit and independent absence of each complete owned launcher/runtime pair established cleanup. These are short checks, not main results, quality scores or returned-model attestations.

Independent inspection verified all 24 native/public capture pairs and the 18 receipt bindings: eight files were byte-identical, sixteen had only documented path redactions. OSC payloads, ordering and numeric/timing fields were unchanged. No credential, private account/workspace hostname or absolute user path was found within the inspected public capture/rule records.

Public capture derivatives: [VRCLT1 D1](../../profiles/evidence/issue8/vrclt1-d1-preflight/export-provenance.json), [VRCLT1 D3](../../profiles/evidence/issue8/vrclt1-d3-preflight/export-provenance.json), [VRCLT2 D1](../../profiles/evidence/issue8/vrclt2-d1-preflight/export-provenance.json), [VRCLT2 D3](../../profiles/evidence/issue8/vrclt2-d3-preflight/export-provenance.json). Native originals and private diagnostic/configuration evidence remain separate.

The [VRCLT1](../../profiles/evidence/issue8/vrclt1-observed-rules.json) and [VRCLT2](../../profiles/evidence/issue8/vrclt2-observed-rules.json) rules bind these exact current receipts and source-display/streaming state. All observed messages have nonblank source, exactly one LF and nonblank translation. The strict pattern rejects CR, additional newlines, blank fields and newline-less forms as unresolved role rather than guessing a single-field source/target fallback. Historical packet-specific extraction is not reused. Context growth or eviction does not establish revision, page or final IDs.

## Retained D1 development pilots

- Both installed **1.0.1** executables match published SHA-256 `e92eee6aa418c7abc096d4def18e496593f81c93da534171807bef01e0272fc5`. Existing owner-authorized access was used; dedicated projects, quotas and billed costs were not established.
- Both planned profiles used CABLE Output, en→ja intent, text-only local output, source display and sentence streaming. Raw passthrough targeted **Realtek Digital Output**, never CABLE Input. Inbound, OSC control, feedback, VR overlays and global hotkeys were off. The normal 15-second idle timeout, 1.5-second OSC cadence and four-second page setting were preserved.
- **Initial VRCLT2 / Qwen 3.8 Beijing / UDP 19132:** The actual ten-second check produced 1,000 callbacks and no OSC; the main stage remained unplayed. The GUI reported `Voice 'Chelsie' is not supported`. This is a provider/session-parameter rejection, not proof of unsupported English/Japanese or zero main-stage delivery. [Preserved failure record](../../profiles/evidence/issue45/vrclt2-d1-initial-failure.json).
- Inspected installed bytecode and [the pinned text-only session construction](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/vrclt/qwen/session.py#L287-L329) omit all voice/clone fields. The server message does not establish that the client sent `Chelsie`. The GUI voice-ID field is not a text-only preset override; no audio-mode/model substitution or product patch was attempted.
- **Minimal Qwen repair / UDP 19131:** Entering the owner's existing Beijing workspace ID through the actual GUI selected the supported workspace-specific MAAS route. Save/restart and readback preserved the same Qwen model, region and text-only mode. One ten-second English check plus fifteen-second tail produced **three English/Japanese chatbox inputs**, four completed stages and runner exit **0**, with no visible post-check Chelsie error. Actual GUI Close and independent absence of the entire owned launcher/runtime pair established cleanup. The old rejection is no longer an unresolved runtime blocker; its internal provider cause remains unknown. [Bounded recovery record](../../profiles/evidence/issue45/vrclt2-workspace-hostcheck.json).
- **VRCLT1 / Gemini `gemini-3.5-live-translate-preview` / UDP 19131:** After a user-operated restart, the separate planned Gemini profile completed the output check and unchanged 40-second development excerpt: four completed stages, 5,000 callbacks and 26 chatbox inputs, including Japanese translations. This is not a successful Qwen retry. The numeric runner exit code was not captured; terminal manifest/session-end evidence was. [Run record](../../profiles/evidence/issue45/vrclt1-d1-observation.json).
- GUI presentation and UDP receipt are separate: the post-run subtitle field was blank, while the raw stream contains translations. No VRChat process, OSCQuery or incoming mute signal was needed for this observed Gemini path.
- **Cleanup correction:** Closing one earlier window did not remove all related runtimes. The [ownership-gap record](../../profiles/evidence/issue45/vrclt-process-ownership-gap.json) preserves that limit. The user's later restart removed the old pairs; after the Gemini run, actual GUI Quit and independent absence of its complete owned launcher/runtime pair established cleanup. [Restart evidence](../../profiles/evidence/issue45/vrclt-user-restart-ownership.json).

The earlier [GUI preparation](../../profiles/evidence/gui-preparation.json) and [installed-state inspection](../../profiles/evidence/installed-apps.json) remain historical snapshots. Translation OFF still permits raw microphone passthrough; neither that toggle nor saved settings proves stopped capture.

## Availability and evidence boundary

| Profile | Current finding | Observed route | OSC destination |
| --- | --- | --- | --- |
| VRCLT1 | **D1/D3 short preflights passed** | Google Gemini Developer Live API, requested `gemini-3.5-live-translate-preview` | `127.0.0.1:19131` |
| VRCLT2 | **D1/D3 short preflights passed** | Alibaba Cloud Model Studio, requested `qwen3.8-livetranslate-flash-realtime` through existing Beijing workspace-specific route | `127.0.0.1:19131`; distinct W3, not concurrent with VRCLT1/W1 |

Readiness is limited to the observed profile/direction, not all languages, provider isolation or quality. Raw hashes and sanitized derivatives are linked from the run records. Effective tier, numeric account limits, complete response identity and actual billing exports remain unverified; missing usage is null, not $0.

For the current D1/D3 execution, the [batch amendment](../../profiles/evidence/issue8/non-puripuly-batch-amendment.json) removes PuriPuly while retaining VRCLT1 in W1 and VRCLT2 in W3, concurrently with their remaining competitors. The [quota amendment](../../profiles/evidence/issue8/quota-isolation-amendment.json) permits existing shared or unverified capacity; new projects or replacement keys are not required. Historical isolation guidance below does not override these decisions. Fresh source-specific output checks, safe passthrough routing and confirmed owned-runtime cleanup remain necessary.

The following source-backed descriptions and isolated-launch procedure preserve the initial preparation research. They are not the control method used for the later GUI-only pilots. The owner authorized existing installed instances/access for those pilots; they do not establish fresh-user/dedicated-project privacy or quota isolation. The agent-selected serial replacement is withdrawn, and original W1/W3 placement is restored without changing historical observations.

The inspected release is [VRCLT 1.0.1](https://github.com/VRCLT/VRCLT/releases/tag/v1.0.1), published 2026-10-17. Its [tag resolves](https://api.github.com/repos/VRCLT/VRCLT/git/ref/tags/v1.0.1) to `d97574fd451f1e5af8d0c68bd13c488fab54eaae`; that revision's version constant is `1.0.1`. The installed-machine inspection independently matched both existing executables to the advertised digest above. The release itself says it was not checked with live translation engines or a headset; the later benchmark observations have their own narrower scope.

## Languages, engines and CPU

Both profiles are all-in-one remote speech translation, not separate local ASR/translation models. There is no local neural ASR or translation workload to move onto a GPU. Local microphone capture, RMS speech gating, resampling and UI still consume CPU; inbound Silero VAD is not part of these outbound-only profiles. Leave the product's speech gating, send cadence, turn handling and idle disconnect behavior unchanged.

Set the following `outbound.source_language` / `outbound.target_language` values while the app is stopped. Chinese is the benchmark's Simplified Chinese selection; Qwen maps both script variants to bare `zh` and cannot promise a separate Traditional Chinese route.

| Direction | ID | VRCLT config source / target | Gemini effective target | Qwen effective target |
| --- | --- | --- | --- | --- |
| English → Japanese | D1 | `en` / `ja` | `ja` | `ja` |
| English → Chinese | D2 | `en` / `zh-Hans` | `zh-Hans` | `zh` |
| Chinese → Korean | D3 | `zh-Hans` / `ko` | `ko` | `ko` |
| Japanese → Korean | D4 | `ja` / `ko` | `ko` | `ko` |
| Chinese → Japanese | D5 | `zh-Hans` / `ja` | `ja` | `ja` |
| Japanese → English | D6 | `ja` / `en` | `en` | `en` |

All six directions are **documented as supported**; VRCLT1 and VRCLT2 have bounded actual D1/D3 output-check confirmation here. D2/D4/D5/D6 remain unmeasured. Gemini and Qwen 3.8 automatically detect the source language; the saved source field records intended input, not a forced language recognizer. Gemini supports the listed BCP-47 codes in [Google's Live Translate guide](https://ai.google.dev/gemini-api/docs/live-api/live-translate#supported-languages). Qwen's [translation guide](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/qwen3-5-livetranslate-flash-realtime) documents Chinese, English, Japanese and Korean among 60 input/text languages; the [pinned language mapping](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/vrclt/languages.py) covers all six directions.

VRCLT1's [Gemini session](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/vrclt/gemini/session.py) explicitly requests `input_audio_transcription`, `output_audio_transcription` and `response_modalities: [AUDIO]`. Source transcription is therefore part of the selected route, not an inferred transcript from OSC. Disabling local voice playback does **not** change Gemini to a text-generation route or eliminate remotely generated audio. Its Cantonese agent-model fallback is outside these six directions; do not substitute that model.

VRCLT2's [Qwen session](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/vrclt/qwen/session.py) selects the model in the WebSocket query. Qwen 3.8 uses `output_modalities`, automatic source transcription and speaker-detection turns; it is not the older Qwen 3.5 route with `qwen3-asr-flash-realtime`. With no audio sinks, the pipeline requests `output_modalities: [text]`, so the proposed profile disables generated Qwen audio as well as local TTS. Saved installations may retain Qwen 3.5: explicitly set `qwen.model`, rather than trusting a new-default claim. Do not replace the planned 3.8 model with 3.5 if access fails.

## Access, limits, isolation and exports

### VRCLT1: Gemini

- [Google's model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-live-translate-preview) confirms the identifier, audio input and audio/transcript output. [Pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-live-translate) lists free input/output for the free tier. It also discloses free-tier data use for product improvement. Availability for a particular account/region remains unobserved.
- [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) apply **per project, not per API key**. Actual model/tier limits must be read in AI Studio; the current public page does not establish this project's numeric concurrent-session, RPM or daily allowance. No numeric free-session allowance is assumed.
- VRCLT accepts a top-level `api_key`, otherwise `GEMINI_API_KEY`; the provider project follows that key, with no application project selector. For W1, use a benchmark project/key distinct from KIKI2's project/key, not merely another key under the same project. Record public aliases, the selected free tier and the private console evidence separately. If separate projects are unavailable, separate the runs, declare shared quota, and revise W1 before freeze; never silently upgrade to paid access.
- The pinned receiver does not persist `usage_metadata` as a structured cost ledger. Its audio-byte/fragment counters are not billed token counts. Google's [AI Studio logs/datasets documentation](https://ai.google.dev/gemini-api/docs/logs-datasets) lists GenerateContent, BatchGenerateContent, StreamGenerateContent and Interactions, not this Live/Bidi route. It does not establish per-session Live export availability. No console was accessed and no export was obtained. Keep unknown usage/cost null; project-isolated dashboard evidence does not manufacture a request-level ledger.

### VRCLT2: Qwen

- Provider is **Alibaba Cloud Model Studio**, not OpenRouter. The actual owner-authorized route is **Beijing**, with the existing workspace ID entered through the GUI. The earlier Singapore proposal is superseded, not a region switch made after failure. Keep the account-specific host, workspace ID and key private.
- The supported Beijing workspace resolver constructs `wss://{workspace_id}.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime?model=qwen3.8-livetranslate-flash-realtime`. Saving that existing workspace corrected the empty-workspace fallback; the same Beijing model/text-only configuration then delivered Japanese OSC. The effective connection host and returned server identity were not independently captured.
- The [model page](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/qwen3-8-livetranslate-flash-realtime) lists **10 RPM / 100,000 TPM** for Singapore and Beijing, and Singapore list prices per million tokens of **$7.50 audio input, $20 text output, $30 audio output**. Audio output should be absent in the proposed text-only Qwen route but must be confirmed from effective state and billing, not deducted by assumption.
- [The price table](https://www.alibabacloud.com/help/en/model-studio/model-pricing#60c768c0e0ipk) lists a Singapore **1 million token** new-user allowance, valid **90 days** from activation/model release/approval, whichever is later, and no allowance in other regions. This does not establish credit for the actual Beijing account. The owner authorized use of the existing Qwen access for the short check; no new account, funding or paid fallback was created. Actual cost remains unknown.
- [Quota is account + model scoped](https://www.alibabacloud.com/help/en/model-studio/rate-limit), aggregating RAM users, workspaces and keys. A separate workspace/key improves attribution and permissions but does not create independent account rate quota. Use a dedicated benchmark key/workspace; do not claim quota isolation from a second key alone.
- [Billing and cost management](https://www.alibabacloud.com/help/en/model-studio/bill-query-and-cost-management) documents **minute-level** model-inference bills, normally delayed **2–10 minutes**, downloadable as CSV under Billing Details → Alibaba Cloud Model Studio → Export Bill CSV. It documents API Key ID, workspace ID, model, input/output type and invocation-channel breakdown. Instance ID encodes billing type/workspace/model/input-output/channel. Cost Overview has model/API-key filtering and daily/monthly trends. This is aggregate billing evidence, not an OSC-utterance or per-second receipt export. Actual Qwen 3.8 export columns/coverage were not observed.
- [Server `response.done`](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/live-translator-server-events#f2333c777d9s4) documents response identity and token usage. The pinned app does not write a complete structured usage export; DEBUG logs only the first 30 raw events per connection, truncated to 500 characters each. Do not equate these with complete billing records or enable raw transcript logging as a substitute. [Model usage documentation](https://www.alibabacloud.com/help/en/model-studio/model-usage-statistics) distinguishes console free-quota usage from exported bill details; monitoring is not the billing basis.

## Historical isolated configuration procedure

This source-derived procedure was **not executed for the later GUI-only pilots**. Its dedicated-user, separate-key and Singapore assumptions are not current observed state. The current [GUI operator bridge](../cli.md#actual-gui-development-pilots) binds actual manual observations and process ownership to the runner; it does not continuously inspect application state. No automatic VRCLT-specific control API was fabricated.

### 1. Establish ownership before startup

Use a dedicated Windows user/session without a personal VRCLT process, SteamVR autostart registration, or ambient provider credentials. VRCLT has a fixed per-user/session mutex `Local\vrclt.single-instance`; changing configuration paths does not permit two instances in that session. W1 and W3 already separate VRCLT1/2; quit VRCLT1 completely before preparing VRCLT2.

Obtain the pinned executable and check it against the release digest above. In the benchmark user's ignored `.data/apps/vrclt/VRCLT1` or `VRCLT2` directory, keep the binary, a private `config.yaml`, and separate `LocalAppData`. Copy the pinned [`config.example.yaml`](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/config.example.yaml) for a **fresh** configuration; never copy the existing personal file. Back up any previously benchmark-owned configuration before editing, including its exact idle timeout. Keep backups private: keys are plaintext. Use a private benchmark key provisioned by its owner; do not print it or put it in a command line, public snapshot or this repository.

The [entry point](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/vrclt/__main__.py) supports only `run` and `--app {vrchat,discord,custom}`. There is no configuration-path command-line flag, headless state API, device-list command or external start/stop RPC. Unknown flags are tolerated, so `--config` must **not** be mistaken for isolation. Use `VRCLT_CONFIG`; redirect `LOCALAPPDATA` as well, since logs, VAD and other auxiliary files otherwise remain shared. An isolated config path alone is insufficient.

### 2. Apply the exact settings while fully stopped

For both profiles, set these fields in the private YAML, retaining all unlisted normal audio settings:

| Key | Required value |
| --- | --- |
| `app.mode` | `vrchat` (enables OSC chatbox, not a requirement to run VRChat) |
| `app.profiles.vrchat.ui_mode` / `ui.mode` | `desktop` / `desktop` |
| `app.profiles.vrchat.voice_output` | `false` |
| `app.profiles.vrchat.passthrough_while_translating` | `true` |
| `app.profiles.vrchat.chatbox` | `true` |
| `app.profiles.vrchat.osc_control` | `false` |
| `app.profiles.vrchat.vr_overlay` / `overlay.enabled` | `false` / `false` |
| `app.profiles.vrchat.wrist_ui` / `wrist_ui.enabled` | `false` / `false` |
| `outbound.enabled` / `outbound.chatbox` | `true` / `true` |
| `outbound.text_only` / `outbound.voice_output` | `true` / `false` |
| `outbound.passthrough_while_translating` | `true` (the product forces this in text-only mode) |
| `outbound.mic_device` | The full enumerated `CABLE Output` recording-endpoint name; not a default microphone |
| `outbound.tts_device` | The full enumerated **non-injection playback endpoint** chosen below; not blank, and never `CABLE Input` |
| `outbound.monitor_device` / `outbound.glossary` | empty string / empty string |
| `outbound.echo_target_language` | `false` |
| `outbound.source_language` / `outbound.target_language` | The direction row above |
| `inbound.enabled` / `inbound.play_audio` / `inbound.allow_system_audio` | `false` / `false` / `false` |
| `dashboard.translation_on` / `dashboard.subtitles_on` | `true` / `false` |
| `control.enabled` / `control.feedback_chatbox` | `false` / `false` |
| `control.osc_listen_port` | `19231` for VRCLT1; `19232` for VRCLT2; **not bound while control is disabled** |
| `osc.ip` / `osc.port` | `127.0.0.1` / observed `19131` for VRCLT1/W1 and VRCLT2/W3; never run these two same-app profiles concurrently |
| `osc.show_source` / `osc.stream_sentences` | `true` / `true` |
| `osc.throttle_sec` / `osc.chunk_display_sec` / `osc.notification_sfx` | normal defaults `1.5` / `4.0` / `false` |
| `audio.mic_idle_disconnect_sec` | Preserve the normal selected-release value: **15.0 seconds for a fresh 1.0.1 config**; do not set 0 or extend it for the benchmark |
| `hotkeys.enabled` / `steamvr.register` / `steamvr.dashboard_panel` | `false` / `false` / `false` |
| `ui.close_action` / `ui.easy_mode` / `ui.lang` | `exit` / `false` / `en` |
| `meta.auto_setup_pending` | `false` |

**Feedback hazard:** [output-mode normalization](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/vrclt/config.py#L471-L496) overwrites `voice_output: false` with `true` when `text_only` is false. Therefore use `text_only: true` here. That setting also enables **raw microphone passthrough at unity gain**, even when translated TTS is disabled. [The outbound pipeline](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/vrclt/pipeline.py#L379-L463) sends it to `outbound.tts_device`; `tts_gain: 0` does not mute raw passthrough. Sending it to CABLE Input while capturing CABLE Output would recirculate the benchmark audio. Choose an explicitly enumerated independent playback endpoint with no route or Windows Listen/monitor path back to CABLE Input; an unused second virtual sink is suitable, or isolated headphones with no recapture. Do not change the input audio/gating to work around this. **No safe endpoint has been selected locally**, so this is an explicit blocking setup input, not a default-device fallback.

[The microphone picker](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/vrclt/setup_check.py#L40-L55) hides CABLE Output from ordinary choices. Configuration-file selection still reaches [the input resolver](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/vrclt/audio/devices.py#L86-L117), which matches case-insensitive device-name substrings with WASAPI preferred, then DirectSound/MME fallback. Use the full actual endpoint name and record the effective host API. Do not use **Find my mic** or **Auto setup**: they are designed for normal VRChat routing and can replace the deliberate CABLE input or alter VRChat settings. Setup-check warnings about absent VRChat/control packets are not evidence of an outbound dependency and must not be 'fixed' by starting VRChat.

VRCLT1 additionally sets `provider: gemini`, `model: gemini-3.5-live-translate-preview`, and its dedicated private top-level `api_key`. VRCLT2 sets `provider: qwen`, `qwen.model: qwen3.8-livetranslate-flash-realtime`, `qwen.endpoint: intl`, `qwen.workspace_id` to the dedicated workspace ID, `qwen.base_url` to an empty string, and its dedicated private `qwen.api_key`. Retain normal `qwen.voice_clone: once` and `qwen.voice: ""`; they are inactive when no generated audio is requested. Clear unused provider key fields in these fresh benchmark configs.

### 3. Launch with child-only environment overrides

After preparing the owned files and access above, use a fresh PowerShell session in the benchmark user. This example selects VRCLT1; use `VRCLT2` in `$Root` for W3. It deliberately does not obtain or print credentials. It has **not** been executed for this finding.

```powershell
$Root = (Resolve-Path '.data/apps/vrclt/VRCLT1').Path
$Start = [System.Diagnostics.ProcessStartInfo]::new()
$Start.FileName = Join-Path $Root 'vrclt-v1.0.1-windows-x64.exe'
$Start.WorkingDirectory = $Root
$Start.UseShellExecute = $false
$Start.Arguments = 'run --app vrchat'
$Start.EnvironmentVariables['LOCALAPPDATA'] = Join-Path $Root 'LocalAppData'
$Start.EnvironmentVariables['VRCLT_CONFIG'] = Join-Path $Root 'config.yaml'
$Start.EnvironmentVariables['VRCLT_NO_UPDATE_CHECK'] = '1'
foreach ($Name in @('GEMINI_API_KEY', 'GOOGLE_API_KEY', 'DASHSCOPE_API_KEY', 'OPENAI_API_KEY', 'SONIOX_API_KEY', 'GOOGLE_APPLICATION_CREDENTIALS', 'GOOGLE_GENAI_USE_VERTEXAI', 'GOOGLE_CLOUD_PROJECT', 'GOOGLE_CLOUD_LOCATION', 'GOOGLE_GEMINI_BASE_URL', 'GOOGLE_VERTEX_BASE_URL', 'VRCLT_UPDATE_REPO')) {
    $Start.EnvironmentVariables.Remove($Name)
}
$OwnedProcess = [System.Diagnostics.Process]::Start($Start)
```

Use a clean user's environment rather than claiming this list sanitizes arbitrary proxy/authentication integrations. Source evidence for these controls is [`config.py`](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/vrclt/config.py#L74-L79), [`platform_support.py`](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/vrclt/platform_support.py#L59-L66) and [`qt_ui.py`](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/vrclt/qt_ui.py#L200-L205). The last disables the automatic release **check**; the inspected update flow offers release links rather than silently replacing the executable. Do not trigger manual updates during measurement; retain the binary hash before/after and record any version change. On the first version/reset prompt choose **No** to preserve the prepared settings.

### 4. Observe preparation; keep computer use outside timed playback

The native GUI starts the runtime on launch. Inspect Full view/Settings and a redacted whitelist of the selected fields; never publish the whole YAML. Confirm source model, microphone's resolved endpoint/host API, text-only state, inbound/control disabled, destination port, languages and unchanged idle timeout. A saved YAML is intent, not effective state. Start only owned capture; do not attach to a pre-existing window. A provider session can legitimately be closed while waiting for speech, so 'not connected' is not by itself a process-death finding.

No-VRChat is **pilot-confirmed for the observed D1 routes** and source-supported: [`_start_runtime`](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/vrclt/app_controller.py#L1100-L1132) always creates outbound microphone translation, creates process-audio inbound only when enabled, and starts the avatar listener only when `control.enabled` is true. [`Chatbox`](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/vrclt/out/osc_chatbox.py) sends to the configured UDP sink without discovering VRChat. No OSCQuery or mute-state signal was supplied for the successful observations; no required incoming control port was established.

Run the shared ten-second clip after initial preparation, each direction change and resume once authorized access and a real control/capture bridge exist. Retain actual `/chatbox/input` and `/chatbox/typing` packets with times/source addresses and an effective-state snapshot. Do not use an app feedback line or typing indicator as the translation check. Stop GUI/computer-use capture and inference activity from the control tool before timed audio. Record first observed quota/disconnection errors rather than changing the service/model. The actual bounded observations are listed above; unobserved directions remain unverified.

### 5. Change direction and restore

During preparation only, set Dashboard spoken/target languages from the table; the state change requests a provider reconnect. Keep both config source values and actual autodetection behavior in evidence. For a config-file change, **quit and relaunch** using the same owned launch procedure; ordinary **Runtime restart** uses the controller's in-memory configuration, not an external-file reload. Do not restart at ordinary chunk boundaries or change the idle timeout to avoid the product's normal reconnect behavior.

When leaving a profile or cleaning up, choose **Quit** from the owned app and confirm the complete owned runtime has exited, including related launcher/child processes established during preparation. Do not kill shared ancestors or unrelated user processes. Merely toggling Translate off is not `stop`: raw microphone passthrough/capture can continue. Retain shutdown-tail OSC because the chatbox worker may send one final queued part. The historical isolated-launch environment overrides above were child-only; the actual GUI pilots instead changed the owner-authorized installed configuration. Preserve private backups and do not publish their secrets.

## Observed OSC and source-derived interpretation

The paragraph immediately below describes the retained historical development capture, not the current four short checks. Current observed-format bindings above deliberately do not generalize its single-field packets into universal extraction rules.

The actual VRCLT1 pilot received **70 OSC packets**, including **26 chatbox inputs**: three during the output check and 23 during the main stage. Observations include rolling bilingual snapshots, source-only sequence 43 and Japanese-only sequence 58. The first main-stage chatbox update retains output-check context alongside new speech. These are actual receipt observations, not explicit utterance/final IDs or proof that all context belongs to the measured source. Preserve raw order and uncertain relationships; do not concatenate every bubble or take the last packet as the final translation. See the [run evidence](../../profiles/evidence/issue45/vrclt1-d1-observation.json) and [derived-evidence index](../../profiles/evidence/issue45/metrics/actual-pilot-metric-index.json).

The following finer mechanisms remain source-backed explanations unless a particular per-run observation establishes them:

- Wire shape is `/chatbox/input` with `[text, true, notification_sfx]`, and `/chatbox/typing` with one boolean. The proposed sound flag is false. Typing is auxiliary activity, not an utterance, translation or final marker. UDP source port is not configured/pinned; distinct destination ports provide attribution, and the pilot must retain actual source addresses.
- With `osc.show_source: true`, the usual payload is cleaned source text, a newline, then cleaned translation. Source text can be absent; finalized source-only output is possible. A nonempty chatbox message therefore does not prove that translated meaning was delivered. Source-only partials are suppressed. The two lines contain no explicit language tags or utterance IDs.
- Default `osc.stream_sentences: true` builds a **rolling snapshot**, not a stream of disjoint sentences: recent finalized source/translation sentences plus the current partial share one bubble. The tail keeps up to six finalized segments, drops old context after a 15-second conversation gap, and trims oldest entries when the combined payload exceeds the 144-character budget. A growing/replaced/shortened bubble can be continued speech, a revision, or context eviction; no universal 'new message = new utterance' rule is valid.
- Segment flushes can result from server turn completion, two seconds of transcript-fragment silence, a completed translated sentence of at least eight characters, or length pressure (138 combined characters in sentence-streaming mode; other 120/140-character guards also exist). These internal finalizations are not semantic completeness and are not transmitted as IDs/final flags.
- The sender enforces at least 1.5 seconds between messages. New pending text replaces unsent parts, so received updates need not include every intermediate model hypothesis. Consecutive identical payloads are suppressed, but the dedup state resets on finalization/interruption: a repeated payload can be a final resend or a genuinely repeated utterance. Reconnection can requeue unsent microphone audio; OSC alone cannot distinguish its replay from new speech.
- `stream_sentences: false` is an existing alternative, **not the selected default**: long source/translation pairs split into paired pages of at most 144 Python string characters, displayed about four seconds apart; newer text cancels unsent pages. There are no page indices. Even the default path can reach the splitter for an oversized single entry, so do not guarantee it is page-free without observation. Do not change this setting merely to manufacture a paging pilot.
- Qwen 3.8 has item/previous-item/speaker IDs internally; those do not reach the chatbox packet. Gemini server turn/interruption events likewise do not become OSC identity fields. Application logs containing `FINAL`, counters or source/target fragments are separate diagnostics, not shared receipt timing.

Actual rolling output does not resolve every new-utterance, revision, page or resend boundary. Preserve raw packets and separate inspected/estimated grouping from observations. Revision/final-dependent metrics remain **N/A** where ambiguous.

## Remaining limits

1. The historical Chelsie rejection was bypassed by the supported existing-workspace route, without changing voice fields or product code. The initial repaired Qwen observation was a ten-second check; current D1/D3 checks are separate records. Observed UDP19131 is retained across distinct W1 (VRCLT1) and W3 (VRCLT2), superseding19132 without relying on the withdrawn single-profile layout.
2. Existing access produced current outputs. KIKI2 and VRCLT1 share the observed Google-A alias under the owner-approved quota amendment; numeric limits and actual billing/usage exports remain unverified.
3. Both profiles have bounded D1/D3 preflight evidence, not an exhaustive six-direction matrix, provider reconnect attribution or a main comparison.
4. Actual all-in-one rolling output is available. Pagination, resends and final-dependent correspondence remain uncertain where the packets lack identity fields.
