# Episode-native capture runner

The [final plan](benchmark-final-plan.md), [Kikitan self/split amendment](https://github.com/kapitalismho/vrc-translator-bench/issues/14#issuecomment-6406954100) and [implementation sequence](benchmark-implementation-plan.md) govern this runner. No translator is bundled. Schema-1 stage plans and old runs are not executable through a compatibility path; keep their original artifacts and use the pinned historical implementation for inspection.

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

Capture acquires the per-user activity lock across worktrees/run roots. It cannot discover arbitrary unmanaged CPU-heavy work. Do not take screenshots, operate the GUI or run unrelated checks during input and the observation tail. Judging must acquire the same exclusion; there is no scoring command here.

`status` exposes pending episode/pass work, attempts, outcomes, artifacts and hashes. Remaining duration is an estimate excluding setup/retries. Inspection returns 0 even if recorded work failed. Run exit codes distinguish terminal success (0), product failure (1), operational/configuration invalidity (2), and interruption (130); inspect N/A and unknown role outcomes separately.

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
| `kikitan` | Loopback `host`, fixed `port: 7272`; optional sender restriction | `/microphone/recognized`, `/microphone/translated`, `/microphone/final` user-data. No fabricated adjacency links or finality. Desktop/VRChat is outside the approved condition. |
| `vrcls` | Existing `log_path` or `log_dir` | Read-only `vrcls-*.log` tail, Desktop/peer and Mic/self. Preserve physical-line and multiline uncertainty; exclude configuration snapshots. |

Collectors are read-only: they do not launch translator hosts or configure providers. Authentication tokens are read from named environment variables and excluded from persisted connection URLs/raw evidence. UDP listener continuity does not guarantee packet completeness. File rotation/truncation, malformed payloads, explicit producer gaps and disconnections remain observable gaps; reconnect cannot invent missing history. PuriPuly filtered sequence jumps alone are not loss.

Windows file tails open existing logs read-only with read/write/delete sharing, so they do not block a producer's rename-based rotation. The collector drains its old handle and records the rotation gap before observing the new file; late reads retain their actual receipt time without backdating output.

VRCS collector startup returns only after validating the server's `system.connected` and matching `system.subscribed` acknowledgements, before the runner may start the app/input. Missing acknowledgements fail within the five-second subscription deadline; rejected subscriptions or connection errors also fail startup and close the transport. The same receive loop retains ACK-adjacent and later events without reconnecting. PuriPuly's CLI exposes no subscription acknowledgement, so this barrier does not invent one or wait indefinitely for its first translation.

Installed Kikitan 2.0.2's user-data serializer casts UTF-16 characters to single bytes, irreversibly corrupting Chinese before UDP transmission. The [observed blocker](../profiles/evidence/r1/kikitan-unicode-blocker.json) prevents KIKI2 ordinary EN→ZH confirmation; decoder replacement or GUI text cannot recover or substitute the primary native output. This is distinct from the UTF-8-capable historical chatbox path. No product patch or alternate endpoint is silently introduced.

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

## Actual GUI bridge

`bench.gui_operator_adapter` mediates observed GUI actions, not hidden app APIs. Use a fresh operator directory, actual owned PID, profile and unique session. Observation JSON contains `basis: "actual_visible_gui"`, `pid`, `profile`, `session`, UTC `observed_at_utc`, nonempty `evidence`, and `state` with `voice_output`, `running`, and `channels`. Each channel binds `role`, `input_device`, `output_device`, `source_language`, `target_language`.

```powershell
python -m bench.gui_operator_adapter --directory OPERATOR_DIRECTORY --owned-pid 12345 --profile VRCS1 --session SESSION --record-observation OBSERVATION_JSON
```

Requests appear as `request-NNNN.json`. Perform the supported GUI action outside measured input, inspect its result, and record a fresh observation with `--ack-sequence N`. For reset, include `session_reset` bound to the requested episode/pass, `basis` equal to `product_new_conversation` or `verified_application_restart`, and evidence. Same-process new conversation retains its owned PID/session. A restart ACK is still submitted with the **old** request's `--owned-pid` and `--session`; the observation names the new PID, a never-used session, and `process_identity` from the live Windows process (`pid`, `executable`, `clock: "windows_filetime_utc"`, `creation_filetime_100ns`). Include `session_reset.successor: {previous_pid, previous_session, pid, session, evidence: [...]}` explicitly identifying the owned replacement. The old process must have exited, the new same-executable process must have been created after the request's UTC wall time and be alive with capture stopped, and its observed identity must match a fresh independent query. Process birth UTC/FileTime is never compared numerically with request/collector monotonic clocks. Only after validating the request-bound ACK does the cached controller adopt the successor; later observations/start/stop use its new PID/session. Stale, unrelated, reused or ambiguous identities are rejected without rebinding; unrelated bystanders never become owned.

The bridge deliberately reports app/input continuity unknown: a manually inspected screen plus process liveness cannot certify uninterrupted provider/capture health. Retire the session after external configuration changes. Never include unrelated processes in cleanup. Inspect screenshots/accessibility data before retaining them; hidden fields may contain secrets.

## Clocks, opportunity and persistence

Playback preserves callback `perf_counter_ns`, PortAudio current/DAC time, source frames and submitted frame count. Map source time within the relevant callback, then add the measured route offset. A positive offset means capture sees a frame later. Calibration is a practical path correction, not precision hardware certification. `clock_session` prevents joining monotonic values across independent processes/reboots without mapping.

Collection and input persist through the latest role's **common last-input-speech +15-second horizon**, with the full source buffer retained. Simultaneous roles keep independent lower input origins but share this actual common upper output cutoff, including when device origins/calibration differ; output after an earlier channel's individual +15 point but before the common deadline is not discarded. Split passes use separate origins but the same common source endpoint. No old 60-second no-output watchdog remains. Early harness/control interruption is operational invalidity, not product no-output.

| Observation | Recorded treatment |
|---|---|
| Native text for a bound role | `output_observed`; not a quality/time admission |
| No text, full horizon and independently established app/input/collector continuity | `product_no_output` for that role |
| No text without that opportunity proof | `unknown_no_output`, not a zero score |
| Actual app/provider/disconnection/quota failure | Retained product failure with reached time; do not erase it by retry |
| Quota prevents future input | Future unplayed work remains pending, not filled with synthetic failures |
| Genuine unsupported language | N/A with reason and no played opportunity |
| Harness/control/device/settings interruption | Invalid attempt, replayable without replacing earlier history |

A run retains frozen/execution plans, SQLite ledger, manifest, per-attempt JSONL traces, continuous native stream and separate controller diagnostics. Trace fsync/finalization/hash precedes terminal ledger updates. Resume finalizes interrupted temporary evidence, retains earlier terminal outcomes/hashes and replays only unfinished/invalid episode-pass work with a new attempt and clock session. Delayed output carries current observation context, not invented source alignment; retain prior source-candidate provenance.

`tools.export_pilot_evidence` creates a separate path-redacted derivative after terminal capture. It does not certify arbitrary log content, remove every possible secret or grant publication rights. Preserve original hashes and inspect source-content rights. Historical `costs` run/chunk input is not new episode/pass normalization; R5 owns that cutover. Native reconstruction, judging, semantic-wait aggregation and final assembled admission belong to later outcomes, not this capture CLI.
