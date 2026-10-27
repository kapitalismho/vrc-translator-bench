# Architecture

The [maintained final benchmark plan](benchmark-final-plan.md), including the owner-approved Kikitan headless WebSocket cutover, owns the current local protocol. The [published self/split amendment](https://github.com/kapitalismho/vrc-translator-bench/issues/14#issuecomment-6406954100) records its earlier input exception; its UDP-primary requirement is superseded locally, not silently claimed updated remotely. The [implementation plan](benchmark-implementation-plan.md) owns outcome and publication boundaries. Native capture is a component, not an implemented or admitted end-to-end evaluation pipeline.

## Retained executable surfaces

| Surface | Current responsibility | Boundary before new measurement |
|---|---|---|
| `bench/audio.py` | Explicit WASAPI PCM routes, callback/DAC mapping, scheduled role starts and measured path correction; explicitly synthetic clock backend | Distinct devices retain actual origins/skew; no sample-accurate shared-hardware-clock claim |
| `bench/adapter.py`, `gui_operator_adapter.py` | Subprocess lifecycle, independently observed state, identity/session-bound operator acknowledgements | Manual GUI state and process liveness do not establish continuous input/provider health |
| `bench/kikitan_adapter.py`, `kikitan_runtime.py` | Supported headless control, exclusive shared-settings/port ownership, process identity, fresh sessions and guarded restoration | Own new installed instances only; public state is allowlisted and app/input continuity remains unknown |
| `bench/plan.py`, `runner.py` | Schema-2 episodes, physical channel/logical role/pass bindings, owned lifecycle and immutable attempts | Historical stage plans are rejected; final profile admission belongs to R6 |
| `bench/native.py`, `native_formats.py`, `native_transports.py`, `osc.py` | Read-only CLI/WebSocket/UDP/file collection, allowlisted native events, raw evidence, receipt clocks and gaps | Missing producer time, IDs, revision links or finality remain unknown; receipt is not rendering |
| `bench/storage.py`, `activity.py` | Atomic artifacts, hashes, journal, episode/pass ledger and OS locks | Keep original evidence immutable; callers must acquire the appropriate lock |
| `bench/profiles.py` | All 14 profiles' independent native feasibility scopes and fixed wave constraints | Historical self findings never promote a new scope; R1 cannot grant R6 final admission |
| `bench/quality_store.py` | Durable call/raw-response/cache/recovery ledger | Not a scheduler, rubric, result validator or two-stage evaluation implementation |
| `bench/quality_transport.py`, `quality_process.py`, `quality_judge.py`, `quality_bridge.mjs` | Selected Astra subscription transport, isolated request payload, observed identity and owned Windows process tree | No public scoring command or paid/model fallback; future orchestration must acquire activity exclusion and validate judgments |
| `bench/cost_inputs.py`, `costs.py` | Selected local usage records, attribution, dated Decimal calculations, partial/unknown/subscription conditions | Existing run/chunk normalization, not logical episode + role/pass cost binding |
| `tools/export_pilot_evidence.py` | Separate capture derivatives with original/export hashes and path redaction | Not a generic secret scrubber or permission to publish transcripts/logs |

The public CLI retains `run`, `status`, `calibrate`, `playback`, `profiles`, and `costs`. Obsolete `metrics`, `metrics-batch`, `quality`, `prepare-english`, corpus builders and generated-pilot commands have no compatibility aliases.

## Episode-native boundary

One episode preserves source identity and role WAVs on the original common timeline. Physical input channels are distinct from logical A/B roles. VRCLT and Kikitan use two separately originated self passes for T1; the other families retain simultaneous peer/self. Mixed-family first passes within a wave share a scheduled execution round; exception B passes follow separately. Actual concurrency admission still requires runtime evidence.

Collectors begin before measured input and remain active through the common last-input-speech +15-second horizon. App, input and collector continuity are separate facts. A connected socket, living controller or silent OSC listener is not sufficient proof of a product no-output outcome. Early harness interruption is invalid. Product failures and unknown observation opportunity remain distinct; unplayed future work is not filled with zero scores or synthetic product failures.

Kikitan control and collection use distinct clients of the same stock loopback WebSocket server. Only the controller sends supported app commands. The collector preserves recognition messages but excludes secret-bearing state/configuration frames before raw persistence. Kikitan's owned controller/app lifetime ends at round teardown so KIKI1 and KIKI2 can use the same fixed port/settings in their separate waves; this does not serialize other wave members or change split-pass weighting. Outstanding controller cleanup is durable and separate from capture ownership and completed attempt results.

Later outcomes supply frozen corpus/checkpoints, native-output reconstruction, independent GEMBA-ESA error and score calls, weighted semantic-wait CDFs, logical-episode cost binding, and a common report consumed by Claude's presentation. The existing cost path remains historical run/chunk accounting until R5; do not pass new episodes through it as if normalization had migrated. No legacy evaluator or renamed score is retained.

## Evidence and ownership

- Frozen `corpus/` and `profiles/` records retain paths and bytes; `.gitattributes` preserves their checksum semantics. Local `.data/` audio, logs, ledgers and historical scripts are not cleanup targets.
- Issue #8 continuation/materialization helpers are task-local historical execution records. Do not update their pinned hashes to make them accept the new checkout.
- Capture collector lifetime and application translation opportunity are separate. Known early-stop and reconstruction findings remain unresolved for the historical comparison; this reset removes the obsolete evaluator, not the evidence or its acceptance hold.
- Preserve the established W1–W4 concurrency intent. New peer/T1 routing, same-app isolation and actual resource/clock conditions must be verified before a new schedule is frozen; do not silently serialize it.
- GPT owns backend contracts, data, measurement, judging, costs and experimental evidence. Claude owns public tables/charts/methodology presentation and chronological example rendering. Both consume the same versioned report; the frontend does not recalculate scores.
- A static adapter, passing unit test or successful historical self capture does not establish a new actual-app peer/T1 result. Live acceptance belongs to the affected implementation outcome under scoped app/service authority.

Historical implementation and detailed prior architecture remain at [the pre-reset revision](https://github.com/kapitalismho/vrc-translator-bench/blob/fbab10a0455d91d5419d9673499d25b7ac86c566/docs/architecture.md). No old results are migrated into a new ranking by this change.
