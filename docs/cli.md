# Episode-native capture runner

The maintained [final plan](benchmark-final-plan.md), including the approved Kikitan headless WebSocket cutover, and [implementation sequence](benchmark-implementation-plan.md) govern this runner. The [published self/split amendment](https://github.com/kapitalismho/vrc-translator-bench/issues/14#issuecomment-6406954100) retains the input exception; its former UDP-primary requirement is superseded by the [published WebSocket amendment](https://github.com/kapitalismho/vrc-translator-bench/issues/15#issuecomment-6431325473). No translator is bundled. Schema-1 stage plans and old runs are not executable through a compatibility path; keep their original artifacts and use the pinned historical implementation for inspection.

## Install and operate

Python 3.11+ is required. Real audio uses Windows WASAPI shared mode. WebSocket collectors require the native extra.

```powershell
python -m pip install -e ".[audio,native]"
bench calibrate --output-device "CABLE Input(VB-Audio Virtual Cable)" --input-device "CABLE Output(VB-Audio Virtual Cable)" --output .data/calibration/cable.json
bench playback clip.wav --output-device "CABLE Input(VB-Audio Virtual Cable)" --output .data/calibration/playback.json
bench profiles --catalog profiles/catalog.json
bench run --plan plan.json --run-id pilot
bench status pilot
bench run --resume pilot
```

`python -m bench.cli` is equivalent to `bench`. `run` and `status` accept `--root` (default `.data/runs`). Resume uses the stored plan, not a replacement input. `--audio-backend clock` requires both `synthetic: true` and a synthetic execution scope; simulated input cannot establish product observation opportunity.

`calibrate` measures the selected output→input path with a seeded synthetic probe and preserves checksummed NPZ evidence. `playback` is an audio-path probe, not a translation pilot. Both accept `--output-device`; calibration also accepts `--input-device`. Use explicitly enumerated WASAPI device names or indices, never a default microphone. Calibration for one path does not establish another path's offset. Disable translated voice and keep raw passthrough away from the injection endpoint.

For an explicitly named, uniquely resolved WASAPI endpoint, the current exact device name must match the measured calibration. Enumeration indices may change; the run retains current playback device indices alongside the untouched calibration's historical indices, offset and raw hash. Numeric selectors retain the index check. Wrong or ambiguous names are rejected. Name-preserving reuse is not a new precision calibration or a persistent hardware-identity guarantee.

Capture and `quality` acquire the same per-user activity lock across worktrees/run roots. The lock cannot discover arbitrary unmanaged CPU-heavy work. Do not take screenshots, operate the GUI or run unrelated checks during input and the observation tail.

`status` exposes pending episode/pass work, attempts, outcomes, artifacts and hashes. Remaining duration is an estimate excluding setup/retries. Inspection returns 0 even if recorded work failed. Run exit codes distinguish terminal success (0), product failure (1), operational/configuration invalidity (2), and interruption (130); inspect N/A and unknown role outcomes separately.

## Evaluate retained episode histories

```powershell
bench quality --spec evaluation.json --output .data/r4/result.json
bench quality --spec evaluation.json --output .data/r4/result.json --transport judge.json
```

The first form reconstructs locally and reuses accepted cached calls; it never dispatches a provider request. The second enables new isolated calls through the explicitly configured selected route after `measurements_ended: true` and activity-lock acquisition. Neither starts a translation app or replays audio. Use a new output/store for this versioned method, not an old quality queue.

The spec binds all planned episodes, reviewed reference hashes, selected immutable attempts or retained native artifacts, logical roles and measurement conditions. Missing results keep their original planned weight. The report preserves separate quality and semantic-wait completeness, raw call identities, and protocol-derived no-output outcomes. Exit 0 means complete quality and timing for the declared full design; exit 2 can accompany a valid partial report and must not be read as “no report written.” See [quality input/result contracts](quality.md) and [weighted metrics](metrics.md).

## Profile scope

`bench profiles` inspects all fourteen profiles under `native-output-v1`. Every profile independently partitions ordinary EN→ZH, ordinary JA→KO, and T1 A/B in both pairs into confirmed and still-unverified scopes, with separately scoped blockers. A representative success does not promote sibling models, languages or T1. R6's final quality/time admission remains `pending_r6`.

`--check-ports` performs an instantaneous TCP/UDP loopback bind probe and releases the socket. Occupied app listeners can be expected; an available port proves neither authentication nor input/output. Historical self/OSC findings remain explicitly historical. The catalog is not a run plan and `--require-ready` is not supported.

## Plan schema 2

A JSON plan declares:

| Field | Contract |
|---|---|
| `schema_version` | Exactly `2`; `stages` is rejected |
| `frozen_rule_revision`, `price_table_version` | Explicit rule/price identities; a pilot label is not a main freeze |
| `execution_scope` | `{kind: "main"}`, `{kind: "pilot", reason: "..."}`, or `{kind: "synthetic"}` |
| `synthetic` | Boolean, true exactly for synthetic scope |
| `profiles` | Nonempty array of controller/native-collector/route definitions |
| `episodes` | Nonempty array of independent original-timeline inputs |

Main episodes preserve exact catalog W1–W4 membership and schedule every declared profile. Canonical profile IDs in real main/pilot plans are bound to the catalog application family and approved ordinary/T1 condition; changing a collector cannot turn PP/VRCT into a self-only exception. Custom pilot IDs and explicitly synthetic fixtures remain possible without implying canonical admission. A complete single-wave run is allowed; all fourteen need not appear in one run. Pilot subsets require an explicit reason and do not establish concurrency admission. Paths to audio/calibration resolve against the plan directory; materialization freezes source and implementation hashes.

Each profile supplies a unique safe `id`, a nonempty `adapter` argument vector (no shell), `collector`, and `expected_state` with `voice_output: false`. `routes` maps physical `self`/`peer` channels to explicit `output_device`, `input_device`, and a measured `calibration` file for real audio. Calibration must bind matching devices and intact raw evidence. Optional `metadata`, `quota_scope` and `control_timeout_seconds` retain scoped configuration/evidence. Use environment-variable names or key aliases, not credentials in plans, URLs or diagnostics.

Each episode supplies `episode_id`, `kind` (`P1`, `P2`, `P3`, `P4`, `T1`, `C1`), `language_pair` (`en-zh` or `ja-ko`), `wave`, `profiles`, and `roles`. Ordinary episodes have A; T1 has A and B. Each role contains PCM16 WAV `audio`, `source_language`, `target_language` and ordered, nonoverlapping `speech_intervals` in **original common-timeline seconds**. A is en→zh or ja→ko; B reverses it. T1 role WAVs have identical sample rate and frame length, including silence; do not compact one role's turns. C1 has no speech intervals.

Ordinary input is peer; ordinary VRCLT/Kikitan is self. T1 is simultaneous peer=A/self=B except VRCLT/Kikitan, whose A and B each run as a separate self pass. First passes for mixed families in a wave share one execution round; exception B passes run in a second round. Both split passes retain the full original timeline and common last-speech +15 seconds. Role origins are independent; both passes belong to one logical episode. Summing their costs must not double the episode denominator (R5 owns cost integration).

Distinct roles cannot play different buffers into the same physical output device. Identical source/endpoint playback can fan out to multiple profiles. WASAPI streams share a scheduled host-monotonic start but record their actual DAC origins; independent devices are not claimed sample-locked.

C1 optionally supplies both `quiet_seconds` and `quiet_max_wait_seconds`, with maximum wait at least quiet duration. Native text during the fresh precondition resets quiet. Timeout preserves `unresolved_carryover`; silence and a fixed tail do not prove clean attribution. Quiet-wait output stays separate from measured input.

## Native collector definitions

| `family` | Required/configurable fields | Primary endpoint and limits |
|---|---|---|
| `puripuly` | `executable`; optional `config_path`; `channels` self/peer | Supported `events follow --topic translation --include-translations`; flattened CLI events. No stdout subscription ACK; quiet process liveness is not subscription proof. |
| `vrct` | Loopback `url`, `token_env`; `ocr_disabled: true` and independent `ocr_evidence` for peer attribution | Authenticated WebSocket; SENT=self, RECEIVED=peer only with OCR excluded. OCR shares RECEIVED and the socket omits the UI-only source marker. |
| `vrcs` | Loopback `/v1/events` `url`, optional existing `token_env` | External API WebSocket, matching connected/subscribed ACKs; source microphone/self and speaker/peer. No replay. |
| `vrclt` | Loopback `host`, unique `port`, required `log_path`; optional sender restriction | `/chatbox/input` display text plus independent FINAL-log crosscheck. Mixed display text is not falsely called a translation-only field. |
| `kikitan` | `url: "ws://127.0.0.1:18378/"`; no token or UDP fields | Installed `--no-ui` microphone `recognition` callback. Separate source/translation/native-final fields in nested JSON; no producer timestamps or IDs. One profile owns this fixed endpoint at a time. |
| `vrcls` | Existing `log_path` or `log_dir` | Read-only `vrcls-*.log` tail, Desktop/peer and Mic/self. Preserve physical-line and multiline uncertainty; exclude configuration snapshots. |

Collectors are read-only: they do not launch translator hosts or configure providers. Authentication tokens are read from named environment variables and excluded from persisted connection URLs/raw evidence. UDP listener continuity does not guarantee packet completeness. File rotation/truncation, malformed payloads, explicit producer gaps and disconnections remain observable gaps; reconnect cannot invent missing history. PuriPuly filtered sequence jumps alone are not loss.

Windows file tails open existing logs read-only with read/write/delete sharing, so they do not block a producer's rename-based rotation. The collector drains its old handle and records the rotation gap before observing the new file; late reads retain their actual receipt time without backdating output.

VRCS collector startup returns only after validating the server's `system.connected` and matching `system.subscribed` acknowledgements, before the runner may start the app/input. Missing acknowledgements fail within the five-second subscription deadline; rejected subscriptions or connection errors also fail startup and close the transport. The same receive loop retains ACK-adjacent and later events without reconnecting. PuriPuly's CLI exposes no subscription acknowledgement, so this barrier does not invent one or wait indefinitely for its first translation.

Kikitan's collector connects before capture starts and sends no control or subscription messages. It preserves each valid `recognition` payload and its independently decoded `transcription`, `translation` and boolean `final`, including empty translations, duplicate snapshots and cumulative updates. The socket also broadcasts configuration/state messages containing credentials: those are excluded before raw persistence, with only safe diagnostic metadata retained. Malformed recognition and unexpected disconnects remain gaps; there is no reconnect/replay fallback.

Installed Kikitan 2.0.2's former user-data serializer irreversibly narrows Unicode before UDP transmission. The [original blocker and invalid attempt](../profiles/evidence/r1/kikitan-unicode-blocker.json) remain history. The owner explicitly adopted the existing UTF-8 WebSocket route after a bounded actual KIKI2 EN→ZH experiment; this is not a decoder workaround, product patch, chatbox substitution or proof that the UDP defect or KIKI1's earlier headless capture crash was repaired.

`native_output_event` records bind profile/config, episode, pass, wave, attempt, physical channel and logical role. Manifest-selected languages are separate from producer-reported languages. Preserve actual translated/source/display text, IDs, revisions and boundary fields only when emitted. Producer time/clock and `collector_received_monotonic` are different fields. Missing time mapping, finality, revisions or IDs remain null/unknown. Native producer stages differ; none is automatically user-visible rendering or provider-return time.

## Application controller protocol

One subprocess per active profile communicates via UTF-8 newline-delimited JSON. stdout is protocol-only. Requests contain `id`, `method`, `params`; reply once with matching `id` and object `result`, or `error: {kind: "operational"|"product", reason, message, scope?}`. Return independently observed effective state, not an echo of requested settings.

| Method | Required behavior |
|---|---|
| `preflight` | Receives `profile`, `episode`, `pass_spec`; return `ready: true` with observed metadata, or genuine `supported: false` with reason. Missing access is not unsupported-language N/A. |
| `read_state` | Effective state including boolean `running`, `voice_output`, and physical `channels` with role/device/language bindings. |
| `stop` | Stop only owned capture/inference and return `running: false`; runner verifies effective stopped state. |
| `reset_session` | Receives episode/pass identity; require genuine new conversation/restart evidence and return `reset: true`, `basis`, `evidence`. Screen clear alone is insufficient. |
| `configure` | Receives `requested_state`; apply supported changes, followed by independent state verification. |
| `identity` | Actual process/build/instance evidence; asserted identity is distinct from producer identity. |
| `start` | Start owned capture/inference, return `running: true`; verified again through state. |
| `begin_pass` | Receives materialized `pass_spec` and attempt ID; no GUI/computer-use work during playback. |
| `liveness` | Observed `alive`, independent `app_continuity` and `input_continuity`, optionally actual `failure`. Each continuity object has `continuous`, `evidence`, `gaps`; process life alone proves neither. |

Asynchronous `product_failure` (crash/provider/disconnection/limit) and `operational_error` events retain their observed receipt time. stderr/diagnostics are separate from native translation records. Sanitize free text at the controller: named-field redaction is not a generic secret scrubber. A separate settings path does not isolate keyrings or shared providers.

Preparation stops prior owned capture, stops the prior collector generation, genuinely resets the conversation, configures/verifies channels, establishes identity, starts collection, then starts capture before audio. Cleanup intent is recorded before start; failed acknowledgements do not remove cleanup responsibility. Resume reconciles previous ownership even for terminal work, without replaying it.

## Kikitan headless controller

Use the installed Windows Photino executable, not the separate Console project or a modified build. The Python environment must have `.[native]` installed. A profile fragment for KIKI2 is:

```json
{
  "id": "KIKI2",
  "adapter": [
    "python", "-m", "bench.kikitan_adapter",
    "--directory", "C:/benchmark/kiki2-owner",
    "--executable", "C:/installed/KikitanTranslator.Photino.exe",
    "--profile", "KIKI2"
  ],
  "collector": {
    "family": "kikitan",
    "url": "ws://127.0.0.1:18378/"
  },
  "expected_state": {"voice_output": false}
}
```

Replace the example paths with absolute local paths and supply the normal schema-2 `routes` and `episodes`. `python` must resolve to the intended installed harness environment. Use KIKI1 with its own owner directory/profile for Bing+Google; the controller preserves the profile's planned model choice. Do not put credentials into the plan or arguments. The app still uses its shared `%APPDATA%/Kikitan Translator/config.json`; there is no executable config-path override.

The controller refuses pre-existing/unrelated Kikitan instances or fixed-port ownership. It launches its own stopped `--no-ui` instance, verifies executable/process birth and listener ownership, applies supported settings only while stopped and reads them back. Keep desktop, user-data and chatbox output disabled. The first fresh owned instance can establish the first episode reset; a reused capture session requires an actual owned restart, not merely OFF/ON or clearing displayed text.

`read_state` exposes an allowlisted `app_settings` object and those public settings at the top level, plus `running`, native `status`, `voice_output` and `channels`. Public settings require their exact primitive types before projection; missing, null, nested or wrong-typed values fail with a safe error. Preflight likewise requires a string app version. Input device and configured languages come from validated app state. Logical role and output-device bindings come from the frozen harness pass and are explicitly labelled as such, not invented app observations. The no-voice claim uses the stock microphone TEXT/no-TTS pipeline basis. Native state polling does not prove uninterrupted input/provider health; liveness preserves those unknowns.

Kikitan round teardown stops capture, closes the collector, then shuts down its controller and owned app before the next pass/profile needs the shared port/settings. Controller EOF performs supported OFF/quit and guarded settings restoration. Keep its owner directory for frozen-argv recovery; do not delete it to bypass outstanding ownership or a concurrent-settings conflict. Restoration happens only after owned process exit and must not overwrite concurrent changes. Cleanup failures, including abnormal controller exit without an error reply, retain durable ownership independently of completed attempts and must not return a successful run exit; resume reconciles cleanup rather than replaying completed audio.

The app performs normal update checks, discovery, device enumeration and logging even before ON. Headless operation is not a zero-network sandbox, a separate credential store or proof of disabled vendor logging. Never publish whole settings, state messages or vendor diagnostics. The successful small KIKI2 experiment is not KIKI1, long-session, other-language, split-T1, wave or final quality/time admission.

## Actual GUI bridge

`bench.gui_operator_adapter` mediates observed GUI actions, not hidden app APIs. Use a fresh operator directory, actual owned PID, profile and unique session. Observation JSON contains `basis: "actual_visible_gui"`, `pid`, `profile`, `session`, UTC `observed_at_utc`, nonempty `evidence`, and `state` with `voice_output`, `running`, and `channels`. Each channel binds `role`, `input_device`, `output_device`, `source_language`, `target_language`.

```powershell
python -m bench.gui_operator_adapter --directory OPERATOR_DIRECTORY --owned-pid 12345 --profile VRCS1 --session SESSION --record-observation OBSERVATION_JSON
```

Requests appear as `request-NNNN.json`. Perform the supported GUI action outside measured input, inspect its result, and record a fresh observation with `--ack-sequence N`. For reset, include `session_reset` bound to the requested episode/pass, `basis` equal to `product_new_conversation` or `verified_application_restart`, and evidence. Same-process new conversation retains its owned PID/session. A restart ACK is still submitted with the **old** request's `--owned-pid` and `--session`; the observation names the new PID, a never-used session, and `process_identity` from the live Windows process (`pid`, `executable`, `clock: "windows_filetime_utc"`, `creation_filetime_100ns`). Include `session_reset.successor: {previous_pid, previous_session, pid, session, evidence: [...]}` explicitly identifying the owned replacement. The old process must have exited, the new same-executable process must have been created after the request's UTC wall time and be alive with capture stopped, and its observed identity must match a fresh independent query. Process birth UTC/FileTime is never compared numerically with request/collector monotonic clocks. Only after validating the request-bound ACK does the cached controller adopt the successor; later observations/start/stop use its new PID/session. Stale, unrelated, reused or ambiguous identities are rejected without rebinding; unrelated bystanders never become owned.

Each verified replacement is durably retained in immutable `ownership-NNNN.json`, binding the operator directory/profile, original owner, previous transition checksum, exact request and previous/successor observations. The matching response names its transition checksum. A fresh controller using the original frozen argv validates the complete request/ACK chain and restores only the current successor, including its stored process birth/executable identity; later observations retain that matching `process_identity`. Historical predecessor PIDs may have exited or been reused and are never queried or stopped as the current owner. An exited current successor establishes stopped capture; a live reused/changed tail identity does not. Missing, stale, branched, ambiguous or incompletely written history fails closed. An unresolved reset cannot use the dead-predecessor shortcut to acknowledge cleanup after a persistence failure.

The bridge deliberately reports app/input continuity unknown: a manually inspected screen plus process liveness cannot certify uninterrupted provider/capture health. Retire the session after external configuration changes. Never include unrelated processes in cleanup. Inspect screenshots/accessibility data before retaining them; hidden fields may contain secrets.

## Clocks, opportunity and persistence

Playback preserves callback `perf_counter_ns`, PortAudio current/DAC time, source frames and submitted frame count. Map source time within the relevant callback, then add the measured route offset. A positive offset means capture sees a frame later. Calibration is a practical path correction, not precision hardware certification. `clock_session` prevents joining monotonic values across independent processes/reboots without mapping.

Collection and input persist through each profile's latest bound role's **common last-input-speech +15-second horizon**, with the full source buffer retained. Simultaneous roles within that profile keep independent lower input origins and share their own common upper output cutoff; another profile's later origin/calibration does not extend it. The execution round may physically collect until the latest profile deadline, recorded separately as `round_collection_deadline_ns`; raw late history is retained outside each profile's `observation_deadline_ns` and output windows. Split passes use separate origins but the same common source endpoint. No old 60-second no-output watchdog remains. Early harness/control interruption is operational invalidity, not product no-output.

| Observation | Recorded treatment |
|---|---|
| Native text for a bound role | `output_observed`; not a quality/time admission |
| No text, full horizon and independently established app/input/collector continuity | `product_no_output` for that role |
| No text without that opportunity proof | `unknown_no_output`, not a zero score |
| Actual app/provider/disconnection/quota failure | Retained product failure with reached time; do not erase it by retry |
| Quota prevents future input | Future unplayed work remains pending, not filled with synthetic failures |
| Genuine unsupported language | N/A with reason and no played opportunity |
| Harness/control/device/settings interruption | Invalid attempt, replayable without replacing earlier history |

Collector checks apply to active profiles and their current attempt generations, not historical or already-terminal collectors. A native transport disconnect triggers an immediate independent application-health check. When a same-profile product failure is corroborated and the gaps are transport-only, retain `product_failure` and false collector continuity while healthy members finish their full input and observation horizons. Record `product_failure_observed` and `product_collector_disconnect`; terminal details retain `product_errors` and `product_disconnect_correlated`. A socket close alone, malformed/protocol/policy data, controller operational failure or an independently mixed instrumentation fault remains invalid, never fabricated product failure or no-output proof. Invalid finalization still retains any already observed product errors. Historical gaps remain intact; no reconnect or replay is introduced.

A run retains frozen/execution plans, SQLite ledger, manifest, per-attempt JSONL traces, continuous native stream and separate controller diagnostics. Trace fsync/finalization/hash precedes terminal ledger updates. Resume finalizes interrupted temporary evidence, retains earlier terminal outcomes/hashes and replays only unfinished/invalid episode-pass work with a new attempt and clock session. Delayed output carries current observation context, not invented source alignment; retain prior source-candidate provenance.

`tools.export_pilot_evidence` creates a separate path-redacted derivative after terminal capture. It does not certify arbitrary log content, remove every possible secret or grant publication rights. Preserve original hashes and inspect source-content rights. Historical `costs` run/chunk input is not new episode/pass normalization; R5 owns that cutover. Native reconstruction, judging, semantic-wait aggregation and final assembled admission belong to later outcomes, not this capture CLI.
