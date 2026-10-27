# VRCT and VRCS profile findings

**Current R1 contract:** use the [episode-native CLI](../cli.md), [scope catalog](../../profiles/catalog.json) and [R1 evidence boundary](../benchmark-implementation-plan.md#r1-implementation-and-actual-feasibility). VRCT2 and VRCS2 ordinary EN→ZH peer evidence uses their native WebSockets, not the historical self/chatbox route below. VRCT requires independent OCR-off evidence solely to exclude a non-audio input source; OCR is not collected or evaluated. VRCS2 produced three completed translations early in the input; later coverage remains unknown.

The following preparation records are historical. Their six-direction admission, endpoints and execution instructions do not supersede schema 2 or establish new native-profile admission.

Initial research date: 2026-10-20. Authority: [parent #1](https://github.com/kapitalismho/vrc-translator-bench/issues/1) and [profile preparation #4](https://github.com/kapitalismho/vrc-translator-bench/issues/4). The actual-GUI observations below supersede runtime-absence claims in the historical [source findings](../../profiles/findings/vrct-vrcs.json). Source/configuration procedures below remain reference material, not the control method authorized for the current GUI-only execution.

## Actual GUI development pilots

- **VRCT1, 3.6.0:** Google Web Speech ASR, `m2m100_418M-ct2-int8` CPU translation, explicitly selected supported `int8` processing, Windows WASAPI CABLE Output, en→ja and UDP 19111. The actual ten-second check and 40-second excerpt completed four stages, 5,000 callbacks and six bilingual OSC inputs. The GUI also displayed source/Japanese text and retained CTranslate2 as the main engine. CPU/int8 is observed configuration, not independent backend execution-type instrumentation. [Run evidence](../../profiles/evidence/issue45/vrct1-d1-observation.json).
- **VRCS2, 0.2.8:** Gemini `gemini-3.5-transcribe-live` plus requested paid OpenRouter `google/gemma-4-26b-a4b-it`, CABLE Output, speaker capture/mute synchronization off, UDP 19122. D1 produced Japanese translated OSC. A separate target change and same-process capture resume produced Chinese OSC; this is not process-restart persistence or interrupted-run resume. [D1](../../profiles/evidence/issue45/vrcs2-d1-observation.json), [D2](../../profiles/evidence/issue45/vrcs2-d2-resume-observation.json).
- **VRCS1, 0.2.8:** The GUI downloaded the managed Qwen runtime/model and selected Qwen3-ASR 0.6B Q8_0 CPU with the same requested Gemma route, UDP 19121. D1 produced Japanese OSC; independent process arguments showed CPU-only device/offload flags. [Run](../../profiles/evidence/issue45/vrcs1-d1-observation.json), [CPU observation](../../profiles/evidence/issue45/vrcs1-cpu-runtime.json).
- VRCS changed from the earlier installed 0.2.2 to 0.2.8 before measurement; update initiation was not established and the operator did not select an update action. Automatic checks were subsequently disabled through the GUI. GUI closure and independent process/port observations confirmed owned VRCS/local-inference exit.
- VRCT remained 3.6.0; the inspected update panel showed the CPU version and no automatic-update toggle. No update/install action was selected. After VRCT1, actual GUI microphone and translation switches were OFF. The app was retained for subsequent profiles; later window/control access became unavailable while its processes remained alive. **Full VRCT process cleanup is not claimed.**

Existing owner-authorized access was used, not separately quota-isolated benchmark accounts. Current source-specific preflights below supersede the earlier configuration-only findings where actual output was obtained. Saved credentials, local assets and source support alone do not establish readiness. The earlier [installed snapshot](../../profiles/evidence/installed-apps.json) and [GUI-only preparation](../../profiles/evidence/gui-preparation.json) remain historical.

### Retained issue #8 GUI-only preparation

- **VRCT3, 3.6.0:** Actual GUI selected Google ASR and exact requested OpenRouter `google/gemma-4-26b-a4b-it`, CABLE Output / Windows WASAPI and port **19113**. D1 then D3 were configured with microphone/translation stopped; runtime access/output was not exercised. This configuration was then replaced by VRCT2.
- **VRCT2, 3.6.0:** Actual GUI selected Whisper **base / CPU / int8**, Google web translation and port **19112**, D3 then D1, also stopped. Initial port-entry attempts did not persist correctly; the corrected paced entry was confirmed in the GUI and allowlisted stored intent. The unsuccessful images are not successful port evidence. Neither profile received benchmark audio or a new output check. [VRCT preparation](../../profiles/evidence/issue8/vrct-preparation.json).
- **VRCS1, 0.2.8:** Actual GUI selected CABLE Output 48 kHz mono, local Qwen3-ASR 0.6B Q8_0 CPU and requested Gemma 26B Japanese. During Audio inspection an unexpected square Stop indicator was stopped immediately; Recognition subsequently showed **Model not_loaded**. No deliberate start or benchmark playback had been issued, but zero pre-stop capture/provider activity is not established. At that pass D3 Korean selection was unconfirmed and VRCS2 preparation remained pending; the current preflights below supersede those pending findings. [VRCS preparation](../../profiles/evidence/issue8/vrcs-preparation.json).

Foreground interference suspended that GUI-preparation pass. The VRCT window-closing attempt did not establish process exit; full cleanup remains pending, not a product failure. Historical VRCS1 D1 readiness remains evidence-specific and is not renewed by this configuration-only pass. These records are not current-state guarantees; participating profiles still require fresh authorized GUI admission and their applicable audio/output checks.

The earlier [continuation-only amendment](../../profiles/evidence/issue8/continuation-only-amendment.json) retained completed cohort-A results without remeasurement. The subsequent [repair-and-retry amendment](../../profiles/evidence/issue8/repair-retry-amendment.json) authorizes fixing VRCT1/VRCT3 D1 and VRCS1 D1/D3 blockers and regrouping still-unmeasured profiles concurrently; it preserves their original failures and the completed measurements. New main launches require amended membership and a new freeze. The [quota amendment](../../profiles/evidence/issue8/quota-isolation-amendment.json) permits shared/unverified capacity without changing keys, tiers or routes. The [supplementary-scope amendment](../../profiles/evidence/issue8/supplementary-scope-amendment.json) keeps tone30, Korean100 and owner-review tasks removed; primary automatic quality, latency, delivery, failure and cost work remains.

### Current D1/D3 VRCS preflights

**VRCS2 passed both source-specific audio-to-OSC checks** on 0.2.8, using the existing Gemini Transcribe and exact requested paid Gemma route. Each real CLI run completed four stages with no invalid/product-failure stages and two nonempty bilingual OSC inputs. CABLE Output remained 48 kHz mono with speaker capture and mute synchronization off. Actual GUI stop acknowledgements completed both runs; these checks are not main measurements or quality scores. [Four-slot record and export inspection](../../profiles/evidence/issue8/vrcs-current-preflights.json), [D1 public capture](../../profiles/evidence/issue8/vrcs2-d1-preflight/export-provenance.json), [D3 public capture](../../profiles/evidence/issue8/vrcs2-d3-preflight/export-provenance.json).

**VRCS1 now passes both repair source checks through the approved CPU-runtime override.** The original D1 startup and distinct D3 recovery startup after ordinary GUI runtime download timed out. Defender recorded successful security actions on required `b11501/mtmd.dll`, classifying it as `Trojan:Win32/Bearfoos.A!ml`; this is Defender's finding, not an independent malware or false-positive determination. Those failures and the original managed runtime remain unchanged. [Original security observation](../../profiles/evidence/issue8/vrcs-runtime-security-observation.json), [actual repair and checks](../../profiles/evidence/issue8/vrcs-runtime-retry-finding.json).

The owner-approved [startup-only exception](../../profiles/evidence/issue8/vrcs-runtime-launch-amendment.json) launched the unchanged desktop executable with process-only `VRCS_LLAMA_SERVER` pointing to the complete official same-release CPU distribution. Actual desktop-spawned children loaded the exact original Qwen model/projector with CPU-only arguments. Both10s checks completed four stages without invalid/product-failure stages and produced two bilingual destination inputs; D1 also emitted one source-only input, which is not a translation. Both one-second silent stages received no OSC. Native stop, normal desktop close and owned-process absence were verified. The D1 run had already begun when40s steering arrived; future D1 startup checks must use40s. Future launches still require this scoped override and fresh native admission. Do not change global environment variables, restore quarantine, disable protection or patch individual DLLs into the old runtime. Configuration/capture/cleanup remain GUI operations.

### Current D1/D3 VRCT preflights

The [six-slot record](../../profiles/evidence/issue8/vrct-current-preflights.json) retains all seven actual checks, including the original VRCT3 D1 no-output result and its separate later cleanup timeout. The single authorized fresh-control recheck also produced no output; VRCT1 D1 likewise returned `output_check_no_output`. Their causes remain unknown, not unsupported-language or main-result findings. [Original interrupted capture](../../profiles/evidence/issue8/vrct3-d1-initial-interrupted/export-provenance.json), [VRCT3 recheck](../../profiles/evidence/issue8/vrct3-d1-preflight/export-provenance.json), [VRCT1 D1](../../profiles/evidence/issue8/vrct1-d1-preflight/export-provenance.json).

All checks used the declared preserved microphone baseline, manual threshold 300 and VAD off; an unexpected pre-playback selection was corrected before audio, not tuned using results. Final actual GUI/backend stop acknowledgements and all seven bridge retirements are retained. The owned GUI/backend remained open, so full process exit is not claimed.

All 38 manifest-listed native/exported capture pairs passed independent hash and recursive privacy inspection, with no numeric or OSC-content changes. The interrupted original's unlisted temporary streams remain local and unfinalized; its derivative does not manufacture a complete stream.

The [new D1 retries](../../profiles/evidence/issue8/vrct-d1-retry-finding.json) localized the original failures to Google English ASR no-match before translation, without proving their cause. Under the [common40s D1 startup amendment](../../profiles/evidence/issue8/d1-startup-check-amendment.json), both unchanged routes produced five fresh bilingual Japanese destination inputs and completed four diagnostic stages. Genuine stop, bridge retirement, normal GUI close and owned-process absence were retained. These new admissions do not rewrite the original10s failures or establish main results.

## Findings and evidence boundary

| Profile | Current finding | Selected/source-resolved configuration | Remaining boundary |
| --- | --- | --- | --- |
| VRCT1 | **D3 preflight passed; D1 amended40s retry passed** | 3.6.0; CPU M2M418M int8 translation plus Google Web Speech ASR | [New D1 finding](../../profiles/evidence/issue8/vrct-d1-retry-finding.json); original10s no-match retained; fresh runtime binding required |
| VRCT2 | **D1/D3 preflights passed** | Whisper `base` CPU `int8` + Google web, port19112 | [D1](../../profiles/evidence/issue8/vrct2-d1-preflight/export-provenance.json), [D3](../../profiles/evidence/issue8/vrct2-d3-preflight/export-provenance.json); main behavior remains unmeasured |
| VRCT3 | **D3 preflight passed; D1 amended40s retry passed** | Google ASR + requested `google/gemma-4-26b-a4b-it`, port19113 | [New D1 finding](../../profiles/evidence/issue8/vrct-d1-retry-finding.json); no returned-model/upstream attestation |
| VRCS1 | **Runtime repaired; D1/D3 source checks passed** | Qwen3-ASR0.6B Q8_0 CPU + requested Gemma26B | [Scoped CPU-runtime repair](../../profiles/evidence/issue8/vrcs-runtime-retry-finding.json); ordinary launch without override is not admitted |
| VRCS2 | **passed current D1/D3 preflights** | 0.2.8; Gemini Live ASR plus requested paid Gemma 26B | Main measurement, quality, long-session behavior and actual usage/cost not established by short checks |

Readiness is limited to the observed directions and evidence. Sanitized exports link to unchanged local raw hashes; they do not certify quality, all-profile compatibility or billing. No VRChat process or fake OSCQuery/mute signal was required for the observed VRCT1/VRCS paths.

Source tables cover all six required directions; untested directions remain source-supported, not runtime-confirmed. The owner accepted VRCS2's paid OpenRouter translation route. Gemini's advertised free ASR tier does not make the whole profile free.

### Pinned application versions

- VRCT release [`v3.6.0`](https://github.com/misyaguziya/VRCT/releases/tag/v3.6.0), source commit **`7ad46876e60d7b6e053489090797e2228f320da5`**. Its config declares `3.6.0`. GitHub lists `VRCT_3.6.0_x64-setup.exe` with SHA-256 `7177419926f693e2d020e60727ca263d4c0f17213987a9c0aa04c8bdc291e8ac`; this is release metadata, not a locally verified installer. Default `develop` was separately observed at `732034c82ad2d848544f872665420ae9c864cead`; findings below use the release commit, not that branch tip. [T1]
- VRCS release [`0.2.8`](https://github.com/Dreaminko/VRCS/releases/tag/0.2.8), tag resolved by source clone to **`b9cd2189f12afbefbaae3e70a2c361f7303fdb54`**. Core declares `0.2.8`. GitHub lists `VRCS-0.2.8-windows-x64.exe` with SHA-256 `b00bc744202ec960011e663d2961e3a8afe80580d937a26881d3b03ab183058a`. Default `main` was observed at `394fbf8b0860ac55c44e4b104565ce02e78885d3`, later than this release; no newer-branch behavior is attributed to 0.2.8. [S1]

## Model routes, access and isolation

### VRCT1: local translation and Google Web Speech

Set `SELECTED_TRANSLATION_ENGINES[tab]="CTranslate2"`, `CTRANSLATE2_WEIGHT_TYPE="m2m100_418M-ct2-int8"`, and select the CPU descriptor returned by VRCT's compute-device list. Set `SELECTED_TRANSLATION_COMPUTE_TYPE="int8"` only after confirming it is in that descriptor's `compute_types`. This is the app's supported quantized conversion, not a claim to run the original full-precision `facebook/m2m100_418M` checkpoint. Weights come from `jncraton/m2m100_418M-ct2-int8`; the tokenizer is `facebook/m2m100_418M`. Downloader/tokenizer calls do not pin an immutable Hugging Face revision. Freeze actual downloaded file hashes/revisions before measurement; none were obtained here. [T2]

Set `SELECTED_TRANSCRIPTION_ENGINE="Google"`. The app calls `recognize_google` without an operator key. Its dependency is pinned to `misyaguziya/custom_speech_recognition@afae7ff78cd5da36e864122f16972d2b0044e03f`. That dependency documents a generic key for personal/testing use which may be revoked. Its historical 50-requests/day statement concerns **a user's own keys**, not a verified allocation for this shared generic route. Neither a production entitlement nor a guaranteed/IP-isolated quota is established. No numeric remaining quota, billing export or observed $0 cost exists. Do not relabel this as Google Cloud Speech-to-Text. [T3]

### VRCT2: Google web translation and Whisper base

Set `SELECTED_TRANSLATION_ENGINES[tab]="Google"`, `SELECTED_TRANSCRIPTION_ENGINE="Whisper"`, `WHISPER_WEIGHT_TYPE="base"`; select the returned CPU transcription descriptor and supported `SELECTED_TRANSCRIPTION_COMPUTE_TYPE="int8"`. The app uses `faster-whisper==1.1.1`, `ctranslate2==4.6.0`, and `Systran/faster-whisper-base`, not `base.en`. Runtime creation uses four CPU threads, one worker and local files only. Downloads do not specify an immutable model revision. [T2, T4]

Google translation is the app's **web** engine, called through bundled compiled `translator_engines.pyd`. The inspected wrapper passes the Google engine to that extension, not a user-billed Google Cloud Translation API credential. Its exact HTTP implementation/model identity is not exposed by the inspected Python source. Access, service-side/IP limits and remaining allowance are unknown; a free user interface is not a verified quota or measured cost. Retain the pinned bundled extension's hash at installation and record any engine fallback. [T5]

### VRCT3, VRCS1 and VRCS2: OpenRouter

The selected paid model ID is `google/gemma-4-26b-a4b-it`. `google/gemma-4-26b-a4b-it:free` is a **different routing/tier selection**. Do not silently append `:free`, substitute 31B, use an auto router, or enable another paid service. VRCS and the current VRCT3 D3 preflight accepted the requested exact model and produced translations; returned model/upstream identity remains unobserved. VRCT3 D1 produced no output in its bounded checks. [P1]

VRCT uses fixed base URL `https://openrouter.ai/api/v1`, an operator key in `AUTH_KEYS.OpenRouter_API`, `SELECTED_OPENROUTER_MODEL`, and non-streaming LangChain `ChatOpenAI`. No `provider.only`, `provider.order`, `allow_fallbacks`, or equivalent setting is passed in the inspected client. It returns text and does not expose OpenRouter generation ID, returned model or upstream provider through its translation return value/OSC. Its key setter performs an authenticated access check and model listing; **do not execute it as an unauthenticated discovery operation**. [T6]

VRCS uses provider ID `openrouter`, the same fixed base URL, a separate API profile UUID and `translation.microphone_targets[].profile_id/model`. Its inspected profile schema has no arbitrary request-body/provider-routing field; custom headers are not the OpenRouter `provider` JSON object. It supports text/stream handling but returns a string to translation consumers. Logs can record a sanitized **generation ID**, requested model, token counts and finish reason. The logged `provider` is the configured gateway/provider label, not proof of the selected OpenRouter upstream; logged model is the requested model. [S2, S3]

OpenRouter normally load balances/falls back among providers. Its API supports provider allowlists and disabling fallback, but neither app exposes those request controls in the inspected paths. Provider pinning is therefore **not established**. Do not modify the competing apps or insert a new proxy. If the owner supplies an external account restriction, separately document it; otherwise disclose unpinned routing and record obtainable actual providers. OpenRouter's authenticated `GET /api/v1/generation?id=...` can expose `model`, `provider_name`, token usage and cost for a generation. VRCS log IDs supply a potential join; VRCT would require an owner-authorized activity/export route, whose availability/granularity was not exercised. No provider record was fetched here. [P2, P3]

Separate OpenRouter key aliases can improve attribution and budget control, **not** guarantee independent global/account/provider rate capacity. Public OpenRouter documentation says additional keys/accounts do not increase governed capacity. The `:free` model limits (20 RPM; 50 RPD without the documented credit-purchase threshold, 1,000 RPD after it) must not be applied as the paid route's quota. Actual balance, per-key budgets, account capacity and upstream restrictions remain unknown. Current batch authority does not permit changing existing accounts, keys, tiers or routes. [P4]

### VRCS1: actual local Qwen package

Set `asr.backend="qwen_local_managed"`, `asr.managed_qwen.package_id="qwen3-asr-0.6b-q8_0"`, `asr.managed_qwen.device="cpu"`, and `asr.active_profile_id=null`. The package source is **`ggml-org/Qwen3-ASR-0.6B-GGUF@928ab958557df9aa2ef1c93e0e83c7ad0933fae2`**, not an unquantized Python Qwen runtime. Required files are: [S4]

| File | Bytes | SHA-256 from source manifest |
| --- | ---: | --- |
| `Qwen3-ASR-0.6B-Q8_0.gguf` | 804749248 | `bca259818b50ca7c4c05e9bdb35a5dc04fa039653a6d6f3f0f331f96f6aa1971` |
| `mmproj-Qwen3-ASR-0.6B-Q8_0.gguf` | 214392480 | `41a342b5e4c514e968cb756de6cd1b7be39eff43c44c57a2ef5fc6522e36603d` |

The managed llama-server runtime is pinned to `b11501`, archive SHA-256 `6bf677025ae9ccdf5ca5e1ee1961ecaf25759f8cf63e875925a83bfaf00b7475`. CPU launch includes `--device none --gpu-layers 0 --no-mmproj-offload --no-op-offload`. Keep `device="cpu"`, not `auto`. The later actual VRCS1 GUI download/start and independent process-argument observation established CPU-only flags for that run; the source-manifest hashes in this section are not substitutes for individually observed file digests. [S4]

### VRCS2: actual Gemini route and the free claim

Set `asr.backend="gemini_transcribe"`, `asr.active_profile_id` to the dedicated Gemini API profile UUID, and `asr.service_settings.gemini_transcribe.model="gemini-3.5-transcribe-live"`. The app opens `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent` with a key, sends `models/gemini-3.5-transcribe-live`, text response modality and PCM16 mono 16 kHz audio. This is the **Google Gemini Developer Live API**, not OpenRouter ASR, Vertex AI, AI Studio browser automation, or the file-transcription model `gemini-3.5-transcribe`. [S5]

Official pricing currently advertises free input/output for this Live ASR model. Paid pricing is $3.50/M input audio tokens and $21/M output text tokens; approximately $0.009/min is an estimate, not measured usage. Free-tier content may be used to improve products. Google applies limits **per project, not per key**; distinct keys alone do not isolate quota. The [current quota amendment](../../profiles/evidence/issue8/quota-isolation-amendment.json) permits shared/unverified capacity for this D1/D3 batch and records an observed shared free-tier condition with VRCS2's project still unknown. Numeric allowance, effective usage and cost remain unestablished; do not change projects or billing. [G1, G2]

Official Live documentation gives a **10-minute continuous-streaming session limit**. VRCS has reconnect logic, but seamless operation across this limit was not observed; retain reconnect/failure evidence rather than promising uninterrupted 30-minute directions or restarting every chunk to hide behavior. PP1 source was separately inspected at `a52fcc97a93d34e040545f388e77a55724cf3c91`, where `providers/stt/gemini_transcribe.py` also selects `gemini-3.5-transcribe-live`; do not claim PP1 uses the file model. PP1's remaining first measurement is separate from completed VRCS2 runs, not evidence of co-measurement. [G3, PP]

The selected translation component remains the paid OpenRouter slug. Thus “free ASR, paid translation” is source-compatible, while “entirely free VRCS2” is not established. A switch to OpenRouter `:free` or another model is an owner decision and would need its own limits and route disclosure; no substitution was made.

## Required directions

Chinese uses Simplified Mandarin. These are requested settings, not observed language output or quality claims. Source tables contain the needed languages; runtime availability still gates every direction. [T3, T7, S5, S6, G3]

| ID | Direction | VRCT source language / country | VRCT target language / country | VRCS `asr.language` | VRCS microphone target |
| --- | --- | --- | --- | --- | --- |
| D1 | en-ja | `English` / `United States` | `Japanese` / `Japan` | `en` | `ja` |
| D2 | en-zh | `English` / `United States` | `Chinese Simplified` / `China` | `en` | `zh-Hans` |
| D3 | zh-ko | `Chinese Simplified` / `China` | `Korean` / `South Korea` | `zh` | `ko` |
| D4 | ja-ko | `Japanese` / `Japan` | `Korean` / `South Korea` | `ja` | `ko` |
| D5 | zh-ja | `Chinese Simplified` / `China` | `Japanese` / `Japan` | `zh` | `ja` |
| D6 | ja-en | `Japanese` / `Japan` | `English` / `United States` | `ja` | `en` |

VRCT's ASR language mapping is `en-US`, `cmn-Hans-CN`, `ja-JP` for Google and `en`, `zh`, `ja` for Whisper. Its m2m100 translation mapping is `en/zh/ja/ko`; Google web and OpenRouter language tables include all four. VRCS maps the Gemini input codes to the same three Google locale codes; the local Qwen model card includes Chinese, English and Japanese. Its LLM translation table includes `en`, `zh-Hans`, `ja` and `ko`. Availability in a configuration table does not establish model-specific translation competence.

## Reversible VRCT control procedure

CLI/config discovery found a native **stdin JSON backend**, not a public `--profile` CLI or the benchmark's own JSON-lines protocol. Source startup command from a pristine dedicated release checkout is:

```powershell
python .\src-python\mainloop.py
```

**Do not run this command during source discovery.** `Controller.init()` checks/downloads the selected CTranslate2 **and** Whisper models when online, even if the intended route is cloud-only. It also checks configured credentials and releases. A dedicated dependency-complete runtime and pre-provisioned weights are prerequisites under this investigation's no-heavy-download/no-provider-call restriction. [T8]

1. Use a pristine dedicated install/source copy, not copied personal settings. Config is `config.json` beside the frozen Python backend executable, or beside `src-python/config.py` in a source run. Preserve a private byte-for-byte backup of this instance's settings before changes. Never publish `AUTH_KEYS`, `TRANSCRIPTION_AUTH_KEYS` or `WEBSOCKET_AUTH_TOKEN`. Multiple settings files do not by themselves establish process/credential ownership. [T1]
2. Keep only one VRCT configuration active at a time. Stop microphone/speaker/OCR capture before preparation. In the GUI, use the microphone and translation toggles, device/translation/recognition settings and Advanced OSC settings. The supported backend paths below provide a source-based automated alternative; no GUI was used here. [T9]
3. For a controller-owned backend, keep stdin/stdout open; wait for successful `/run/initialization_complete`, and feed `/run/feed_watchdog` every 20 seconds, including initialization. Input is one JSON object per line with `endpoint` and `data`. For non-null data, `data` is **base64 of UTF-8 JSON**, even for a scalar. Responses use `status`, `endpoint`, `result`; interleaved logs/events are not request acknowledgements. Correlate serialized requests by endpoint, not the runner's request-ID scheme. Do not use the upstream interactive test client as a benchmark adapter. [T9]
4. The following Python expression emits a real **request**, not an observed response, for VRCT1's destination port:

```powershell
python -c "import base64,json; print(json.dumps({'endpoint':'/set/data/osc_port','data':base64.b64encode(json.dumps(19111).encode()).decode()}))"
```

Send that line over the already-owned backend's stdin; running the expression alone does not configure an application. No credential-bearing requests should be printed or retained in a public transcript.

| Operation | Native endpoint / value |
| --- | --- |
| Version and effective selection | `/get/data/version`, `/get/data/selected_tab_no`, `/get/data/selected_translation_engines`, `/get/data/selected_transcription_engine` |
| Stop capture / translation | `/set/disable/transcription_send`, `/set/disable/transcription_receive`, `/set/disable/ocr_capture`, `/set/disable/translation`, all with `data:null` |
| CPU selection | Get `/get/data/selectable_translation_compute_device_list` or `/get/data/selectable_transcription_compute_device_list`; send the **returned CPU object** to `/set/data/selected_translation_compute_device` or `/set/data/selected_transcription_compute_device`; then supported `"int8"` to corresponding `/set/data/selected_*_compute_type` |
| Engine/model | `/set/data/selected_translation_engines` with the full tab-to-engine map; `/set/data/selected_transcription_engine` with `"Google"` or `"Whisper"`; `/set/data/selected_ctranslate2_weight_type`; `/set/data/selected_whisper_weight_type`; `/set/data/selected_openrouter_model` |
| Direction | `/set/data/selected_your_languages` and `/set/data/selected_target_languages` with complete nested maps read from the app; edit current tab only |
| Microphone | `/set/disable/auto_mic_select`; get `/get/data/selectable_mic_host_list`, `/get/data/selectable_mic_device_list`; select returned host then exact **CABLE Output** capture endpoint using `/set/data/selected_mic_host` and `/set/data/selected_mic_device` |
| OSC | `/set/data/osc_ip_address` = `"127.0.0.1"`; `/set/data/osc_port` = `19111`, `19112` or `19113`; `/set/enable/send_message_to_vrc`; `/set/disable/send_received_message_to_vrc`; `/set/disable/vrc_mic_mute_sync` |
| Start | `/set/enable/translation`, then `/set/enable/transcription_send`; keep speaker/OCR disabled |
| Cleanup | Stop capture/translation using the disable paths; then `/run/shutdown`; confirm the owned process exits before restoring its backed-up config |

The source-language map shape is `SELECTED_YOUR_LANGUAGES[tab]["1"]={"language":...,"country":...,"enable":true}`. Targets use `SELECTED_TARGET_LANGUAGES[tab]["1".."3"]`; enable exactly one target and preserve the other entries with `enable:false`. Use the direction table above. Select tab `"1"` explicitly or record the actual chosen tab. [T1, T9]

Read back all affected getters after changes: engine/model, complete language maps, compute device/type, auto-mic selection, mic host/device, OSC host/port and mute flag. Source may change an unavailable translation engine to CTranslate2, and Whisper initialization defaults to Google unless valid Whisper weights load. A requested value or successful save is therefore not proof of the effective pipeline. Translation enable/capture flags are deliberately nonpersistent and have no equivalent running-state getter in the inspected map: preserve actual toggle acknowledgements/notifications and observed owned process/GUI state; do not synthesize `running` from `config.json`. A future runner adapter must solve independent effective-state reporting, not echo settings. [T1, T4, T9, T10]

Built-in microphone-to-chatbox output does not call TTS in the inspected path. Do not connect external VRCT-TTS/WebSocket consumers, overlays or speaker-input loops. There is no discovered universal `voice_output:false` VRCT key to invent. Translation presentation defaults should be snapshotted, not tuned during measurement. Startup checks for releases in the background; installation uses explicit update commands. No disable-check flag was found. Decline update installation, record version before/after, and exclude any attempt whose application changes. [T5, T8, T11]

## Reversible VRCS control procedure

VRCS has an independently runnable Rust core with environment configuration and authenticated HTTP API; the desktop embeds that core. The standalone entry reads `VRCS_CONFIG`, `VRCS_HOST`, `VRCS_PORT`, `VRCS_SESSION_TOKEN`, `VRCS_SILERO_MODEL`, `VRCS_ASR_MODEL_DIR` and `VRCS_LOG_DIR`. No command-line argument parser was found in the inspected entry. Desktop settings instead use the user's local-data `.vrcs/config.json`; a production desktop chooses a dynamic HTTP port/token and does **not** use `CoreOptions::from_env()` to select its config. Do not claim setting `VRCS_CONFIG` isolates the installed desktop. [S7]

1. Prefer an operator-provisioned standalone `vrcs-core.exe` from the pinned release source with its dependencies/model assets, or a fresh benchmark Windows account for the desktop. A separate `VRCS_CONFIG` file alone does not isolate Windows Credential Manager. Core source can be built with `cargo build --manifest-path .\core\Cargo.toml --release`; this command was **not run**, and the published desktop installer is not evidence of a separately supplied core executable. [S1, S7]
2. Use separate private data/model/log paths and an ephemeral control token. Clear the OpenRouter/Gemini provider environment overrides before launch unless they are explicitly dedicated to this profile: `VRCS_OPENROUTER_API_KEY`, `OPENROUTER_API_KEY`, legacy `VRCS_OPENAI_COMPATIBLE_API_KEY`, `VRCS_GEMINI_API_KEY`, `GEMINI_API_KEY`. Never inspect/log their values. Source lookup gives environment values precedence over stored per-profile keys. Stored targets are `VRCS/API/profile/{uuid}`, with legacy fallbacks; create new UUIDs through the app/API, never reuse personal profiles. [S8]
3. In a dedicated preparation shell, launch the provisioned core with these values (use `19222` and the VRCS2 private directory for VRCS2):

```powershell
$env:VRCS_CONFIG = Join-Path $PWD '.data\profiles\VRCS1\config.json'
$env:VRCS_HOST = '127.0.0.1'
$env:VRCS_PORT = '19221'
$env:VRCS_SESSION_TOKEN = [guid]::NewGuid().ToString('N')
& $CoreExecutable
```

`$CoreExecutable` is the provisioned, pinned core path; no such usable binary was established here. Supply the known-owned token privately to the controller. Without a supplied token the core prints its generated token to stderr, so raw startup diagnostics must not be public. Do not launch until ambient credentials, ownership, assets and possible automatic model preparation have been reviewed. [S7]

4. The following PowerShell commands target that known-owned core only. They are executable control syntax, **not calls performed during this investigation**:

```powershell
$base = 'http://127.0.0.1:19221'
$headers = @{ Authorization = "Bearer $env:VRCS_SESSION_TOKEN" }
Invoke-RestMethod -Uri "$base/health" -Headers $headers
Invoke-RestMethod -Uri "$base/api/audio/devices" -Headers $headers
Invoke-RestMethod -Method Post -Uri "$base/api/capture/stop" -Headers $headers
$response = Invoke-WebRequest -Uri "$base/api/settings" -Headers $headers
$originalSettings = $response.Content
$settings = $response.Content | ConvertFrom-Json
$headers['x-vrcs-config-revision'] = $response.Headers['x-vrcs-config-revision'][0]
```

Use PowerShell 7 for the header-array indexing shown. Keep original settings and profile IDs privately for restoration. `GET /health` reports version, schema, capture requested/running, actual microphone endpoint/state, VAD and ASR status, errors, mute-sync state and OSC target/send state. Settings are schema **33** and `PUT /api/settings` expects a complete settings object, not a JSON Merge Patch. Use the fresh `x-vrcs-config-revision` value from GET for every write; stale writes can conflict. In particular, without the revision, ASR backend/service selection may be preserved rather than applied. [S9]

5. Create a new API profile through `POST /api/asr/profiles` with `{"name":"bench-vrcs1-openrouter","provider":"openrouter","enabled_capabilities":["text_translation"]}`. Retain the returned UUID. For VRCS2, also create provider `gemini` with capability `speech_to_text`. Set each key privately through `PUT /api/asr/profiles/{uuid}/credential` with an `api_key` field. No keys or project names belong in public artifacts; use aliases. Profile creation returns new UUIDs, and `PUT /api/settings` protects profile-owned records, so do **not** attempt to insert credentials/new profile definitions through a settings patch. For Gemini selection, `PUT /api/asr/active` accepts `profile_id` and `service_id:"gemini_transcribe"`; then GET settings again. Key creation/change can reload a running pipeline; do it only while capture is stopped. [S2, S8, S9]

6. Set the following fields on the complete returned settings object and PUT it back. Read effective settings and health again before capture. Every `profile_id` below is the UUID actually returned by the profile API, not a handwritten alias. [S4-S6, S9]

| Setting | VRCS1 | VRCS2 |
| --- | --- | --- |
| `audio.output.mode`, `.device_id` | `"disabled"`, `null` | same |
| `audio.microphone.mode`, `.device_id` | `"device"`, returned numeric CABLE Output capture-device ID | same |
| `asr.backend` | `"qwen_local_managed"` | `"gemini_transcribe"` |
| `asr.active_profile_id` | `null` | dedicated Gemini profile UUID |
| `asr.managed_qwen.package_id`, `.device` | `"qwen3-asr-0.6b-q8_0"`, `"cpu"` | not the active ASR route |
| `asr.service_settings.gemini_transcribe.model` | not the active ASR route | `"gemini-3.5-transcribe-live"` |
| `asr.language` | direction-table input code | same |
| `translation.mode` | `"automatic"` | same |
| `translation.microphone_targets` | exactly one target: direction-table language, dedicated OpenRouter `profile_id`, `model:"google/gemma-4-26b-a4b-it"`; record thinking/prompt/context settings | same, with VRCS2's own OpenRouter profile/key |
| `features.osc_chatbox`, `osc.enabled` | `true`, `true` | same |
| `osc.port` | `19121` | `19122` |
| `osc.mute_sync_enabled` | `false` | `false` |
| `osc.preserve_original_text`, `.translation_strategy` | snapshot actual selection; one target avoids round-robin language confounding | same |

Disable VR overlay, OCR, VRCX/world context, external API and other optional integrations for this microphone-only preparation; do not change the product's segmentation behavior to make the comparison faster. `audio.output` controls **captured speaker audio**, not TTS. No built-in TTS route was found in the inspected feature/config schema; leave external synthesis clients disconnected and confirm no voice playback in the eventual pilot.

7. After profiles are configured and a new settings GET has populated `$settings` and the revision header, a full settings write and capture commands use:

```powershell
$body = $settings | ConvertTo-Json -Depth 100 -Compress
Invoke-RestMethod -Method Put -Uri "$base/api/settings" -Headers $headers -ContentType 'application/json' -Body $body
Invoke-RestMethod -Uri "$base/api/settings" -Headers $headers
Invoke-RestMethod -Method Post -Uri "$base/api/capture/start" -Headers $headers
Invoke-RestMethod -Uri "$base/health" -Headers $headers
Invoke-RestMethod -Method Post -Uri "$base/api/capture/stop" -Headers $headers
Invoke-RestMethod -Uri "$base/health" -Headers $headers
```

Do not run the start line until access is authorized; it can perform paid inference. Automatic translation must really be enabled; a manual OSC test/message is not the required audio-to-translation pilot. Direction changes modify `asr.language` and the single microphone target in the current complete settings, followed by effective-state and ten-second output checks outside timed playback. Do not restart at ordinary chunk boundaries. GUI fallback is Recognition, API profile/translation-target, audio-device and OSC settings; use the global capture control and confirm health, not window visibility.

8. On cleanup stop owned capture, verify `capture_running:false` and `capture_requested:false`, restore this instance's original settings with a fresh revision, then delete only newly created benchmark profile credentials/profiles through their DELETE endpoints. Stop the owned core normally with Ctrl+C. Restore prior shell environment without printing it. Desktop fallback: Settings → Software Update, disable automatic update checks; source stores `checkForUpdatesAutomatically:false` in its `preferences.json` (web mode uses localStorage `vrcs.checkForUpdatesAutomatically`). Back up and restore that preference. Install is a separate action; do not accept it during measurement. Standalone core has no desktop updater loop. [S7-S10]

## Ports, no-VRChat scope and waves

| Profile | Restored planned wave | Chatbox destination | Application control |
| --- | --- | --- | --- |
| VRCT1 | W2 | `127.0.0.1:19111` UDP | Actual GUI plus manual-observation runner bridge |
| VRCT2 | W3 | `127.0.0.1:19112` UDP | Actual GUI plus manual-observation runner bridge; D1/D3 output observed |
| VRCT3 | W1 | `127.0.0.1:19113` UDP | Actual GUI plus manual-observation runner bridge; D3 output observed |
| VRCS1 | W4 | `127.0.0.1:19121` UDP | Actual GUI plus manual-observation runner bridge |
| VRCS2 | W2 | `127.0.0.1:19122` UDP | Actual GUI plus manual-observation runner bridge |

Actual translated-UDP destinations were observed for the current passed VRCT/VRCS2 source-specific preflights above and retained historical pilots. Senders use OS-assigned UDP source ports; do not invent fixed source ports. The final VRCT1 D3 sender port62900 matched owned backend PID27816 in a post-run kernel observation; bridge-recorded GUI PID23896 is a different identity, and that observation does not retroactively attest every earlier sender. VRCT's OSC receive/OSCQuery ports and VRCS desktop HTTP port are dynamic, unlike historical standalone-control examples above. VRCT's optional WebSocket was disabled in the inspected GUI. Keep unrelated consumers disconnected and never run multiple configurations of one app concurrently. [T1, T12, S7, S11]

VRCT `VRC_MIC_MUTE_SYNC=false` bypasses mute-driven capture gating. Its ordinary OSC helper can advertise OSCQuery without establishing a dependency on VRChat. VRCS must disable mute synchronization to avoid its unknown-mute-state gate. The actual named pilots produced translated UDP without VRChat or supplied OSCQuery/mute signals. This does not establish that every untested mode has the same dependency. [T12, S11]

The original cumulative W1–W4 design remains in the [catalogue](../../profiles/catalog.json). Completed VRCT1 D3, VRCT3 D3 and VRCS2 D1/D3 results remain unchanged. The [repair-and-retry amendment](../../profiles/evidence/issue8/repair-retry-amendment.json) allows still-unmeasured repaired VRCT3 D1 with PP4, VRCT1 D1 with PP1 and VRCS1 D1/D3 with PP3; VRCT2 remains with VRCLT2/PP2 in W3. New membership requires a new freeze and actual runtime/output/cleanup admission. The quota amendment permits shared/unverified capacity, not a claim of isolation. PP3 standalone observation remains pending. Retained preparation records do not establish main completion.

## Actual OSC observations and source-derived interpretation

**VRCT1:** Six bilingual inputs were received, one during the check and five during main playback. Main sequence 4→5 expands the same exposed English clause and its Japanese translation; this supports a bounded cumulative-update observation, not a universal final/new-utterance rule. No page/final IDs were present.

**VRCS:** Cloud and local-ASR traces contain source-only followed by bilingual output. VRCS1 also supplied an actual 144-character packet with English ellipsis and more Japanese content; no missing source text or page chain was reconstructed. Per-run rules and inspected correspondence are in the [metric-evidence index](../../profiles/evidence/issue45/metrics/actual-pilot-metric-index.json). Unknown revision/resend relationships remain unknown.

The current VRCS2 D1/D3 checks each yielded two newline-separated source/translation payloads. The [current extraction rule](../../profiles/evidence/issue8/vrcs2-observed-rules.json) split all four real payloads through the metrics interpreter without assigning revision/resend relationships. Its preflight clock and sequence references identify evidence only; they must not become main-run correspondence or relationship claims.

The fresh [VRCT1](../../profiles/evidence/issue8/vrct1-observed-rules.json), [VRCT2](../../profiles/evidence/issue8/vrct2-observed-rules.json) and [VRCT3](../../profiles/evidence/issue8/vrct3-observed-rules.json) rules preserve observed source-first newline framing. The actual metrics interpreter split all ten payloads exactly, retaining unknown relationships and content-change status. VRCT1/VRCT3 rules have observed D3 coverage only; no payload format is claimed for their failed D1 checks.

The following detailed mechanisms remain source-backed explanations unless identified in a particular run:

- **VRCT:** sends `/chatbox/input` with text, `true`, and the configured notification boolean; typing packets are separate. Growing cumulative ASR buffers can produce revised text for one spoken interval, including Whisper as well as Google in this release. Exact consecutive microphone transcripts are suppressed; subsequent different text is translated and sent. The microphone pipeline formats a whole current result and sends it; no page/utterance/revision/final identifier is carried in OSC. A GUI resend resubmits the stored original message and can retrigger translation. Do not assume a new packet is a new utterance, a longer string is final, or repeated text is always a transport resend. No pagination claim is established for this path. [T3, T5, T10, T12, T13]
- **VRCS:** sends `/chatbox/input` with text, `true`, `false`. Automatic output is microphone-based; speaker subtitles do not imply chatbox sends. Its dispatcher has a 1.2-second translation grace, 1.5-second send interval, bounded display queue, and late-translation resend logic with a 30-second TTL for eligible current output. Chatbox formatting uses a 144-character limit and truncation rather than a page-ID protocol. Local DB/events may contain message/subtitle identities and resend diagnostics, but OSC packets contain none of them. An original-only packet followed by a bilingual/translated packet can be one utterance's update, not two deliveries. Similarity, timing and the TTL alone cannot disambiguate a new utterance, revision or resend. [S11, S12]
- Preserve raw packet order/timestamps/text. Treat typing and empty text separately. Until actual streams justify an app-specific grouping rule, revision/page/final-dependent metrics are **N/A**. Last received update is not a universal final translation, and absence of observed pages is not evidence that every UI/output mode is unpaged. A GUI/manual OSC test cannot establish ASR/translation behavior.

Current VRCT/VRCS source preflight dispositions are recorded above; preserve their startup/no-output blockers rather than silently admitting failed slots. Main admission still requires fresh actual state for available profiles and applicable quota/usage/provider observations. The current batch accepts shared/unverified quota under its linked amendment; independent projects are not an extra admission requirement for this execution. The [GUI operator bridge](../cli.md#actual-gui-development-pilots) uses fresh actual observations and independent process liveness, not continuous native capture-state truth.

## Sources

Application links below are immutable commit links. Provider/model documentation is a public snapshot read on the research date, not immutable pricing or entitlement evidence.

- **T1:** VRCT [configuration, version, storage, flags and defaults](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/config.py#L840-L1182), [model/device/key defaults](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/config.py#L1248-L1385).
- **T2:** VRCT [m2m100 model/tokenizer and downloader](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/models/translation/translation_utils.py#L54-L206), [CPU translator creation](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/models/translation/translation_translator.py#L449-L481), [returned compute descriptor](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/utils.py#L465-L479).
- **T3:** VRCT [Google/Whisper provider calls](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/models/transcription/transcription_providers.py#L77-L167), [dependency pin](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/requirements.txt#L61-L66), [pinned speech dependency's access caveat](https://github.com/misyaguziya/custom_speech_recognition/blob/afae7ff78cd5da36e864122f16972d2b0044e03f/reference/library-reference.rst#L215-L230).
- **T4:** VRCT [Whisper models/download/runtime](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/models/transcription/transcription_whisper.py#L42-L206), [runtime engine default/fallback](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/models/transcription/transcription_transcriber.py#L150-L169), [dependency versions](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/requirements.txt#L6-L8).
- **T5:** VRCT [bundled web translator wrapper](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/models/translation/translation_translator.py#L17-L35), [message processing/fallback and output](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/controller.py#L997-L1142).
- **T6:** VRCT [OpenRouter client](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/models/translation/translation_openrouter.py#L19-L182).
- **T7:** VRCT [translation-language tables](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/models/translation/translation_settings/languages/languages.yml), [ASR locales](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/models/transcription/transcription_languages.py).
- **T8:** VRCT [startup downloads](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/controller.py#L4729-L4858), [background release check](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/controller.py#L5266-L5280).
- **T9:** VRCT [endpoint map](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/mainloop.py#L173-L638), [request decode/entry](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/mainloop.py#L717-L918), [base64 JSON decode](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/utils.py#L547-L556), [response serializer](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/utils.py#L674-L718).
- **T10:** VRCT [language/engine changes](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/controller.py#L1536-L1618), [cumulative ASR updates](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/models/transcription/transcription_transcriber.py#L265-L450), [repeat suppression](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/model.py#L1573-L1581).
- **T11:** VRCT [explicit update handler](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/controller.py#L3577-L3582).
- **T12:** VRCT [OSC wire/dynamic receive ports](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/models/osc/osc.py#L52-L194), [mute gating](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/model.py#L1634-L1708).
- **T13:** VRCT [GUI resend sends stored original](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-ui/views/app/main_page/main_section/message_container/log_box/message_container/MessageContainer.jsx#L20-L22).
- **S1:** VRCS [core version/features](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/Cargo.toml#L1-L11).
- **S2:** VRCS [API profile schema](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/config/profile.rs#L5-L45), [profile creation/credentials](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/server/cloud.rs#L17-L79), [fixed provider endpoints/environment variables](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/providers/mod.rs#L751-L794).
- **S3:** VRCS [OpenAI-compatible request/response](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/llm/openai_compatible.rs#L165-L241), [generation-ID/token logging](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/llm/openai_compatible.rs#L638-L684).
- **S4:** VRCS [exact Qwen package manifest](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/asr/qwen_models/manifest.rs#L16-L34), [runtime pin](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/asr/qwen_runtime_download.rs#L11-L35), [CPU launch](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/asr/qwen_runtime.rs#L525-L565), [Qwen official model card](https://huggingface.co/Qwen/Qwen3-ASR-0.6B).
- **S5:** VRCS [recognition keys and model default](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/config/recognition.rs#L13-L62), [Gemini model default](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/config/recognition.rs#L141-L146), [Gemini WebSocket/setup/audio/language mapping](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/asr/streaming/provider/gemini.rs#L14-L144), [reconnect path](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/asr/streaming.rs#L392-L537).
- **S6:** VRCS [translation target/prompt schema](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/config/translation.rs#L41-L90), [language table](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/providers/mod.rs#L122-L126), [audio schema](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/config/audio.rs#L3-L40), [audio modes](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/config/validation.rs#L234-L260).
- **S7:** VRCS [standalone environment inputs](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/lib.rs#L56-L79), [standalone startup/token output/shutdown](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/main.rs#L3-L36), [desktop dynamic connection](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/apps/desktop/src-tauri/src/lib.rs#L81-L106), [desktop config root](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/apps/desktop/src-tauri/src/lib.rs#L549-L575).
- **S8:** VRCS [credential precedence/namespacing](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/credentials.rs#L113-L196).
- **S9:** VRCS [authenticated API routes](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/server/mod.rs#L140-L331), [health state](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/server/mod.rs#L397-L473), [revision-protected settings writes](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/server/settings.rs#L16-L183), [capture start/stop](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/server/capture.rs#L519-L606).
- **S10:** VRCS [update preference](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/apps/desktop/src/updates/update-preferences.ts#L3-L24), [check/install separation](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/apps/desktop/src/updates/useAppUpdater.ts#L103-L135).
- **S11:** VRCS [OSC configuration](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/config/integrations.rs#L25-L39), [OSC gate/timing/queue](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/osc/mod.rs#L27-L43), [mute gate](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/osc/mod.rs#L312-L345), [wire](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/osc/transport.rs#L6-L22).
- **S12:** VRCS [late translation updates and send scheduling](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/osc/mod.rs#L632-L798), [chatbox formatting/truncation](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/chatbox.rs).
- **P1:** [OpenRouter paid model identity](https://openrouter.ai/google/gemma-4-26b-a4b-it), [distinct free variant](https://openrouter.ai/google/gemma-4-26b-a4b-it:free).
- **P2:** [OpenRouter provider routing](https://openrouter.ai/docs/guides/routing/provider-selection).
- **P3:** [OpenRouter generation metadata API](https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation).
- **P4:** [OpenRouter limits and key/global capacity caveat](https://openrouter.ai/docs/api_reference/limits).
- **G1:** [Gemini pricing: Transcribe Live](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-transcribe-live).
- **G2:** [Gemini project-scoped rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).
- **G3:** [Gemini Live transcription, languages and 10-minute limit](https://ai.google.dev/gemini-api/docs/live-api/live-transcribe).
- **PP:** [PP1 Gemini Live source inspected by parent](https://github.com/kapitalismho/PuriPuly-heart/blob/a52fcc97a93d34e040545f388e77a55724cf3c91/src/puripuly_heart/providers/stt/gemini_transcribe.py).
