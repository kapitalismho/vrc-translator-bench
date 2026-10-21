# Capture runner

The runner implements [issue #3](https://github.com/kapitalismho/vrc-translator-bench/issues/3). Application-specific adapters, prepared settings and readiness findings belong to [issue #4](https://github.com/kapitalismho/vrc-translator-bench/issues/4). No translator is bundled. Do not run VRChat for this benchmark.

## Install and operate

Python 3.11+ is required. Actual audio uses Windows WASAPI shared mode and the optional audio dependencies:

```powershell
python -m pip install -e ".[audio]"
bench calibrate --output .data/calibration/cable.json
bench playback clip.wav --output .data/calibration/playback.json
bench run --plan plan.json --run-id pilot
bench status pilot
bench run --resume pilot
```

`python -m bench.cli` is equivalent to `bench`. `calibrate` measures the CABLE Input → CABLE Output path using a short synthetic probe. `playback` is a cable-only probe, not a translation pilot. Both accept `--output-device`; calibration also accepts `--input-device`. Use exact WASAPI device names or currently enumerated indices, not a default microphone. Keep translated voice output disabled and off the injection path.

`run` and `status` accept `--root`, default `.data/runs`. A new run requires `--plan`; `--run-id` is optional. Resume uses the stored plan and does not replace it. `--audio-backend clock` is restricted to plans explicitly marked `synthetic: true`; synthetic audio/OSC does not establish real translation behavior.

Capture and quality scoring share a per-user OS activity lock across worktrees and run roots. A competing managed operation exits before capture starts. The lock releases on process exit; resume remains available after the competing operation finishes. This conservatively prevents all managed capture/scoring overlap, including PP2 judging contention. See [quality measurement exclusion](quality.md#measurement-exclusion) for unmanaged-process limits.

`status` prints JSON with progress counts, pending stages, attempt history, failure/invalid reasons, checksums and artifact locations. Remaining seconds are explicitly **estimated** and exclude setup, restart and retries. Exit codes:

| Code | Meaning |
|---|---|
| 0 | Requested work is terminal without product failure; inspect N/A outcomes separately |
| 1 | Retained product failure exists |
| 2 | Operational invalidity, configuration or access error |
| 130 | Operator interruption |

`status` returns 0 if inspection succeeds, even when the run contains failures.

## Profile preparation commands

`bench profiles --catalog profiles/catalog.json` inspects all 14 recorded findings and the working waves. Add `--check-ports` for an instantaneous loopback UDP availability probe and `--require-ready` to return 2 when real readiness evidence is missing. A valid blocked catalogue otherwise exits 0 for inspection. These commands do not start/configure translators or certify the contents of operator evidence.

`python -m tools.prepare_profile_checks` prepares three ten-second development-audio checks and `profiles/output-checks.json`. Use source-language-specific run plans because `output_check.audio` is currently a single clip per plan. See [profile control procedures, access findings and observed limits](profiles.md). The catalogue is not a runner plan, and documented manual preparation is not a fabricated subprocess adapter.

### Actual-GUI development pilots

`tools.prepare_gui_pilot` prepares the bounded English development pilot used in `profiles/evidence/issue45/`, not a main comparison:

```powershell
python -m tools.prepare_gui_pilot --root . --profile VRCS1 --owned-pid 12345 --port 19121
```

Replace the PID with the actual owned GUI process. The command prints the plan path and creates a unique operator session under `.data/issue45/gui/<profile>/`. It requires the prepared English audio/output-check files and the measured `.data/issue3/calibration/cable.json`; it does not launch or configure an app. D1/D2 are supported for this English-only helper. The default measured excerpt is original PCM `[34,74)` seconds of `development-01`, with a separate ten-second output check. `--direction D2 --check-only` uses the output check plus a one-second silent lifecycle stage: this is not a scored dialogue or the full nonspeech protocol.

The plan starts `bench.gui_operator_adapter`, which waits for an operator rather than calling a hidden application API. Prepare the app through its actual GUI, then record an observation file with:

- `basis: "actual_visible_gui"`, actual `pid`, `profile`, the generated `session`, UTC `observed_at_utc`, and nonempty `evidence` paths to the inspected GUI observations.
- `state` containing actual `microphone`, boolean `voice_output`, `osc_host`, integer `osc_port`, direction ID and boolean `running`.
- Optional `metadata` for actual version/model/provider, CPU evidence, capture semantics, access limits and observation uncertainty. Never include credentials.

Register that file using the same PID/profile/session arguments as the generated plan:

```powershell
python -m bench.gui_operator_adapter --directory OPERATOR_DIRECTORY --owned-pid 12345 --profile VRCS1 --session SESSION --record-observation OBSERVATION_JSON
```

Then run the printed plan with the normal `bench run` command. A required start/stop/configuration action creates `request-NNNN.json`. Inspect the request, perform the actual GUI action outside timed playback, verify its result, and record a **fresh** observation using the same command plus `--ack-sequence N`. An observation predating the request, another PID/session or an unconfirmed capture transition is rejected. Pending changes invalidate prior state; an acknowledgement alone is not an application observation.

Once playback begins, stop all computer-use screenshots/input and unrelated CPU-heavy checks until the runner requests cleanup. GUI state is manually observed, not continuously polled; independent process liveness does not prove continuous capture or translation health. Preserve raw output and any provider/application errors.

Some apps retain microphone capture and raw passthrough when translation is off. For these apps, safely enable the intended translation route before the initial observation, record `running: true`, and let the runner adopt that actual capture. Do not fabricate a stopped initial state. At cleanup, fully quit the owned app through its GUI and independently verify the whole owned runtime, including identified launcher/child processes, before recording `running: false`. A vanished window or one exited PID is insufficient when related runtimes remain. Never include shared ancestors or unrelated user processes in cleanup. Keep raw passthrough off the injection endpoint even with translated voice disabled.

After an external profile/direction change or application restart, retire the old operator directory by writing `invalidated.json` with the reason and prepare a new session. The retired session rejects further acknowledgements. Keep earlier observations and finalized raw capture artifacts unchanged; sanitized publication copies must identify themselves as derivatives and retain original hashes.

Inspect screenshots and accessibility values before retaining them: offscreen credential fields can be present in a full accessibility tree. Use necessary controls and allowlisted values rather than publishing complete trees, configuration, logs or query-bearing connection URLs.

Create a separate publication derivative only after the run is terminal:

```powershell
python -m tools.export_pilot_evidence --run-directory .data/issue45/runs/RUN --output profiles/evidence/issue45/NEW_EXPORT
```

Use a new export destination and inspect the result for secrets, private paths and source-content rights. The derivative records original hashes and its transformations; it does not replace authoritative raw evidence or certify arbitrary diagnostics as safe.

## Plan contract

Supply a JSON object. Relative audio/calibration paths resolve against the plan directory. The runner materializes the plan and source hashes before execution.

| Field | Contract |
|---|---|
| `frozen_rule_revision` | Required actual frozen-rule identifier; a development label is not a main-run freeze |
| `price_table_version` | Required price-table identifier; unknown prices are not zero cost |
| `profiles` | Nonempty array of profile objects below |
| `output_check` | Object with `audio` naming a PCM16 mono/stereo WAV; optional `tail_seconds`, default 15 |
| `stages` | Nonempty ordered array of stage objects below |
| `calibration` | For real runs, path to a measured `bench calibrate` JSON file with matching NPZ evidence checksum |
| `output_device` | Optional exact WASAPI output device name/index |
| `synthetic` | Defaults false; true marks controlled infrastructure observations, not a real profile |

Each profile requires:

- Unique safe `id` and `adapter` subprocess argument vector; commands execute without a shell.
- `osc` with loopback `host: "127.0.0.1"` and destination `port`. Prefer a distinct port per profile. Sharing a port requires a distinct pinned `source_port` for every sharing profile and confirmation from `osc_identity`. Optional `source_host` defaults to loopback. Unexpected or ambiguous packets remain unassigned.
- `expected_state` containing effective `microphone` (CABLE Output), `voice_output: false`, `osc_host` and `osc_port` matching the sink. Additional requested keys are compared too.
- Optional `metadata` for versions, actual models/providers/routes, settings and redacted evidence paths; `key_aliases` for aliases, never credentials.
- Optional `quota_scope` for profiles sharing a limiting account/service, default profile ID; `control_timeout_seconds`, default 30.

Each stage requires `kind` (`chunk`, `isolated`, `nonspeech`, `repeat`), `wave`, `direction`, `profiles` and PCM16 WAV `audio`. `chunk` defaults to `chunk-N`. Conversation resume units should be 2–5 minutes; short pilots are allowed. Speech stages require ordered, nonoverlapping `speech_intervals: [[start_seconds, end_seconds], ...]` in transformed playback coordinates. These annotations drive the continuing-speech watchdog; do not substitute elapsed audio duration for speech. Nonspeech has no speech requirement. `tail_seconds` defaults to 10 for isolated work, otherwise 15. Choose tails consistent with frozen observation windows and preserve later raw events for downstream attribution.

The runner records setup, direction-change and output-check stages. Use the common ten-second check clip for real prepared profiles. Checks occur after initial setup, direction changes and resume; typing or empty text does not satisfy them. A successful check proves received output, not semantic accuracy.

At wave transitions, profiles leaving the wave stop capture/inference; entering profiles are prepared and started just before their work. Retained profiles stay running across ordinary chunk and direction boundaries. Resume prepares/checks each wave before its first unfinished playback rather than activating all future profiles together. The OSC sink and earlier playback provenance remain available across these transitions.

## Application adapter protocol

One long-lived subprocess per active profile communicates through UTF-8 newline-delimited JSON. stdout is protocol-only. Each request has `id`, `method` and object `params`. Respond once with the matching `id` and an object `result`, or an `error` object:

```json
{"id": 1, "error": {"kind": "operational", "reason": "configuration", "message": "Requested input is unavailable"}}
```

`kind` is `operational` or `product`; `scope` is optional. Return genuine observed application state, not echoes of requested settings. Acknowledgement does not replace the runner's effective-state comparison or UDP observation.

| Method | Parameters and result |
|---|---|
| `preflight` | Receives `profile`, `direction`; return `ready: true`, or `supported: false` with a reason for unsupported language. Optional `metadata` records actual version/model/provider/settings/evidence. Inaccessible or unverified setup is operational, not N/A. |
| `read_state` | Return effective requested-state keys, `direction` ID and boolean `running`; optional actual metadata/evidence. |
| `configure` | Receives `requested_state`; correct supported settings. Runner reads state again to verify. |
| `set_direction` | Receives `direction`; adapter maps it to languages. Followed by effective-state check and output check. |
| `start` | Start owned capture/inference, return `running: true`; runner verifies effective state. |
| `stop` | Stop only the application/capture owned by this adapter; return `running: false`, then confirm effective `running: false` through `read_state`. Used when leaving the active wave, at final cleanup or before restart for the next chunk after a crash, never routinely at chunk boundaries. |
| `osc_identity` | Return available process/instance identity and `source_port` if source-port attribution is pinned. |
| `liveness` | Return `alive: true/false` for observed application liveness; optional `failure: {reason, message, scope}` reports provider, disconnection or quota failure. Control-process failure alone is operational, not proof of an application crash. |
| `begin_stage` | Receives materialized `stage` and attempt ID before playback; respond with an object. May bracket diagnostics; must not restart the app or perform GUI/computer-use capture during timed playback. |

Report application state independently of controller lifetime. A new controller must not assume capture stopped when its predecessor exited. The runner durably claims cleanup responsibility before sending `start` and when it observes running capture, so later acknowledgement/state/identity failures still receive supported stop and effective-state confirmation. Such claims are cleanup intent, not proof that capture started; the original operational-invalid attempt remains intact.

Asynchronous stdout records may be:

- `{"event":"product_failure","reason":"crash|provider|disconnection|limit","message":"...","scope":"..."}` with one actual reason, not the illustrated pipe-separated alternatives.
- `{"event":"operational_error","message":"..."}`.
- Diagnostic objects, retained separately from the common OSC endpoint. stderr is also retained as diagnostics.

Sanitize diagnostics in the adapter. Structured credential-named fields receive additional runner redaction, but arbitrary stderr/free text cannot be reliably credential-redacted. Preserve PuriPuly internal timing/usage events through this separate channel; they never replace shared OSC receipt timing. OSCQuery/mute signaling is deliberately absent until an observed profile dependency requires it.

Profile preparation owns startup isolation, secrets, environment credentials, provider access and cleanup. A separate settings file alone does not isolate application-wide keyrings. Do not attach adapters to arbitrary personal instances. Routine checks use synthetic state and local resources, not private transcripts or live services.

## Clock and endpoint records

Latency timestamps use `perf_counter_ns`; UTC wall-clock windows support provider-usage attribution. A `clock_session` distinguishes runner processes, including resume across a reboot. Do not join monotonic values across sessions as if they shared a proven origin.

Playback records actual callback `perf_counter_ns`, PortAudio current/DAC times, source frame and frame count. Host-reported DAC time is mapped into the runner clock as:

```text
mapped_dac_ns = callback_perf_ns + (outputBufferDacTime - currentTime) * 1e9
source_at_capture_ns = mapped_dac_ns
                     + (source_frame - callback.source_frame) / sample_rate * 1e9
                     + cable_offset_ns
```

A positive cable offset means capture sees the frame later. Calibration cross-correlates a bounded seeded probe against CABLE Output, retaining DAC/ADC observations and checksummed NPZ evidence. This is a practical path correction, not precision hardware certification. Absent correction is null, never a fabricated measured zero; real runs require measured calibration.

Raw `/chatbox/input` and `/chatbox/typing` events carry `t_ns`, `run`, `wave`, `config`, `direction`, `chunk`, `attempt`, `observer`, `address`, `args`, `recv_seq`, source host/port, available process identity and clock session. A single receiver preserves receive order and OSC bundle wire order. Typing never counts as translation output. Invalid datagrams remain diagnostic packet records; unassigned packets remain in the continuous stream.

The sink stays open across chunks and observation tails. A delayed earlier-chunk output received during the next chunk carries the **current capture context**, not an asserted source alignment. `source_candidate_provenance` retains actual earlier playback identities/times. The continuous stream remains authoritative after individual attempt traces finalize; historical traces are not rewritten. [Issue #5](https://github.com/kapitalismho/vrc-translator-bench/issues/5) owns separate estimated grouping/alignment, observation deadlines and unaligned/late-output treatment.

Use `bench metrics --manifest RUN/manifest.json --spec metrics-spec.json --output report.json` to derive measurements without changing captured observations. See [metric definitions and report-data inputs](metrics.md). The metrics specification supplies versioned per-app interpretation rules and explicit prepared-reference paths; capture context alone does not establish source correspondence.

Use `bench quality prepare`, `score`, `status`, and `report` on those derived reports for blinded ESA, supplementary MetricX, durable scoring resume and Korean reference-review preparation. See the [scoring contract](quality.md); missing responses and unavailable models remain missing scores, not successful judgments.

## Persistence and failure semantics

A run directory contains:

- Immutable `frozen-plan.json` and append-extended `execution-plan.json` for resume checks.
- `ledger.sqlite` and inspectable `manifest.json`.
- Per-attempt JSONL traces with final checksums.
- Continuous `stream-SESSION.jsonl` and separate `diagnostic-PROFILE-SESSION.jsonl`.

Continuous streams also retain `record: "audio_callback"` and playback metadata rows, so playback evidence survives even when all profile attempts have already finalized as failures. OSC rows are identified by their `address` and `recv_seq`; consumers must not treat every JSONL row as a translation event.

The manifest carries harness revision/source hashes, rule/price versions, source hashes, profile metadata, actual state/preflight evidence, aliases, CPU/OS, calibration, wall-clock windows and failure/invalid/resume history. Local absolute paths and app diagnostics may be sensitive: inspect/redact before publication. Artifacts default to ignored `.data/`.

Frozen `harness_revision`, `harness_sources` and `harness_implementation` identify the original loaded harness. Revision lookup uses that package's recognized checkout, not the operator's working directory. Non-checkout installations or unavailable Git revision report `unknown`, with package version, loaded-package path and source hashes retained. Each `session_start` records the actually loaded implementation; the manifest's `session_implementations` exposes resumed-process provenance without rewriting the frozen identity or inventing metadata for older sessions.

Ledger states are `pending`, `running`, `done`, `product_failure`, `invalid`. Unsupported language is `done` with outcome `N/A` and reason, not a successful measurement or a sixth state. Work becomes durably running **before playback**. Trace flush/fsync, atomic finalization and checksum precede its terminal ledger update. Each retry receives a new attempt number; terminal history is retained.

Resume finalizes surviving temporary evidence and marks unfinished attempts `invalid(interrupted)`. It preserves completed/product-failed profile outcomes, compares and corrects requested application state, performs the short output check, then replays only unfinished/operational-invalid work from its chunk start. Resumed attempts are marked because application context may differ.

Before replay, resume also reads effective state for previously run-owned profiles whose source work is already terminal. It may stop surviving capture before later-wave startup or final cleanup, but never configures/starts those terminal profiles merely to reconcile them, replays their audio or rewrites their attempts/checksums. Future-wave profiles are not activated early.

| Observation | Treatment |
|---|---|
| Application crash, provider/disconnection error | `product_failure`; retain first attempt. Restart a crashed application for the next chunk, not to erase failure. |
| 60 seconds without nonempty chatbox input during continuing annotated speech | `product_failure`; typing is not output. |
| Quota blocks continuing | `product_failure(limit)` for remaining unfinished work in the affected quota scope, with reached wall/monotonic time. Earlier completed/failure outcomes remain intact. |
| Unsupported language | N/A with reason |
| Wrong routing/input/settings, adapter-control failure, PC/harness interruption | Operational `invalid`; resumable without deleting earlier attempts |
| Output-check no-output | Operational invalidity, not a successful translation check |

Adjacent speech intervals share a watchdog baseline: `[0,90]` and `[0,30], [30,60], [60,90]` represent the same continuing speech. Positive-duration silence resets that interval; recent nonempty chatbox output still prevents timeout.

## Observed verification and limits

The implementation was exercised on Windows with a real WASAPI shared-mode cable-only probe: measured correction **+112.375 ms**, normalized correlation **0.999664**. A separate one-second synthetic PCM16 playback submitted 48,000 frames across 100 callback records. Local evidence is in `.data/issue3/calibration/{cable.json,cable.npz,playback-final.json}`. These observations establish cable transport/callback evidence, not translation or physical DAC precision.

The focused capture and repair suites executed 32 passing behavior tests. The integrated repository run (`.data/check-venv/Scripts/python.exe -m pytest -q`) passed 110 tests and 29 subtests. Installed `bench.exe` run/status and intentional process termination/resume were also exercised with controlled subprocess adapters and local UDP. Status preserved the interrupted chunk's first attempt as `invalid(interrupted)` and completed attempt 2 with `resumed=1`; earlier completed traces/checksums remained intact. Separate inspected records distinguish provider product failure, quota propagation, unsupported N/A and operational settings invalidity. These synthetic runs use a clock backend, not audio recognition.

Repair observations used an independent TCP-controlled synthetic application that outlived its controller: terminal-profile capture was stopped before the next wave, and post-start invalidity still confirmed cleanup. An installed-command run from a foreign checkout and resume through a copied non-checkout package retained frozen original identity while recording actual per-session provenance. Evidence remains under `.data/issue3/repair-r1-r4/`; all traffic was controlled loopback, with no provider or hardware use in these repair checks.

**Actual translator audio-to-OSC integration is now observed in bounded development pilots.** GUI-operated VRCT CPU-M2M translation and VRCS cloud-ASR/CPU-local-Qwen configurations produced translated OSC through this runner; a VRCS target-language change and same-process capture resume completed another output check. A planned VRCLT1 Gemini pilot supplied actual all-in-one rolling bilingual output, while VRCLT2's failed Qwen output check remains separate. These runs used owner-authorized installed applications and existing access, not independently quota-isolated accounts. They do not establish provider pinning, complete usage exports, all-profile readiness or a main comparison. See `profiles/evidence/issue45/` and [current profile findings](profiles.md), including the remaining GUI-access and VRCT full-process-cleanup prerequisite.

Earlier issue #4 preparation exercised an isolated installed PuriPuly 2.8.2 instance through its public CLI: effective OSC state, settings changes, restart persistence and actual manual-text UDP output, including two pages with typing false before the second page. That evidence explicitly labels capture/translation disabled. A separate ten-second English development clip completed 480,000 frames and 1,000 callbacks through `bench playback`. Neither historical observation is a microphone-to-translated-OSC pilot. The owner has since reported PuriPuly updated and removed its execution deferral. Resumed PP preparation follows the existing GUI protocol and requires post-update observations; the old control probe is not current-build readiness evidence.
