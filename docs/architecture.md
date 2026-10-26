# Architecture

The [final benchmark plan](benchmark-final-plan.md) owns the intended protocol. The [implementation plan](benchmark-implementation-plan.md) owns the reset classification and future outcome boundaries. This checkout preserves reusable infrastructure; it does not yet execute the native-output benchmark.

## Retained executable surfaces

| Surface | Current responsibility | Boundary before new measurement |
|---|---|---|
| `bench/audio.py` | WASAPI PCM playback, callback/DAC mapping, measured cable correction; explicitly synthetic clock backend | One cable route, not synchronized role streams or every app's peer input |
| `bench/adapter.py`, `gui_operator_adapter.py` | Subprocess lifecycle, observed state, identity/session-bound operator acknowledgements | Self/OSC fields are historical; source inspection is not effective app readiness |
| `bench/plan.py`, `runner.py` | Frozen explicit plans, per-profile attempts, owned capture, resume, failure history | Old stage/direction/single-WAV contract and watchdog; no episode/pass or new observation-completeness guarantee |
| `bench/osc.py` | Ordered raw `/chatbox/input` and `/chatbox/typing`, continuous stream and receipt clock | Not a universal peer collector; receipt is not producer completion or screen rendering |
| `bench/storage.py`, `activity.py` | Atomic artifacts, hashes, journal, run ledger, OS locks | Keep original evidence immutable; callers must acquire the appropriate lock |
| `bench/profiles.py` | Validate the 14-profile historical inventory, linked evidence and static wave constraints | Returns historical findings, not new-protocol admission |
| `bench/quality_store.py` | Durable call/raw-response/cache/recovery ledger | Not a scheduler, rubric, result validator or two-stage evaluation implementation |
| `bench/quality_transport.py`, `quality_process.py`, `quality_judge.py`, `quality_bridge.mjs` | Selected Astra subscription transport, isolated request payload, observed identity and owned Windows process tree | No public scoring command or paid/model fallback; future orchestration must acquire activity exclusion and validate judgments |
| `bench/cost_inputs.py`, `costs.py` | Selected local usage records, attribution, dated Decimal calculations, partial/unknown/subscription conditions | Existing run/chunk normalization, not logical episode + role/pass cost binding |
| `tools/export_pilot_evidence.py` | Separate capture derivatives with original/export hashes and path redaction | Not a generic secret scrubber or permission to publish transcripts/logs |

The public CLI retains `run`, `status`, `calibrate`, `playback`, `profiles`, and `costs`. Obsolete `metrics`, `metrics-batch`, `quality`, `prepare-english`, corpus builders and generated-pilot commands have no compatibility aliases.

## Intended cutover

Implement one episode-native path, not a parallel legacy evaluator. The native-input/collector outcome first owns the shared episode, role/pass, native output, clock/gap and outcome contracts. Small permitted development inputs are sufficient for that feasibility pilot; full corpus/TTS production waits for its findings.

Later outcomes supply frozen corpus/checkpoints, faithful native-output reconstruction, independent GEMBA-ESA error and score calls, weighted semantic-wait CDFs, logical-episode cost binding, and a versioned report consumed by Claude's presentation. Preserve unknown native fields rather than inventing IDs/finality. Preserve invalid/unsupported/indeterminate scope instead of renormalizing it away.

The old runner, profile inspector and cost normalization are **scheduled for in-place migration**, not certified as already compatible. No old D1–D6 identifier, OSC timestamp, correspondence score or cached judgment receives a new meaning silently. The new runtime must reject incompatible historical input rather than route through a shim.

## Evidence and ownership

- Frozen `corpus/` and `profiles/` records retain paths and bytes; `.gitattributes` preserves their checksum semantics. Local `.data/` audio, logs, ledgers and historical scripts are not cleanup targets.
- Issue #8 continuation/materialization helpers are task-local historical execution records. Do not update their pinned hashes to make them accept the new checkout.
- Capture collector lifetime and application translation opportunity are separate. Known early-stop and reconstruction findings remain unresolved for the historical comparison; this reset removes the obsolete evaluator, not the evidence or its acceptance hold.
- Preserve the established W1–W4 concurrency intent. New peer/T1 routing, same-app isolation and actual resource/clock conditions must be verified before a new schedule is frozen; do not silently serialize it.
- GPT owns backend contracts, data, measurement, judging, costs and experimental evidence. Claude owns public tables/charts/methodology presentation and chronological example rendering. Both consume the same versioned report; the frontend does not recalculate scores.
- A static adapter, passing unit test or successful historical self capture does not establish a new actual-app peer/T1 result. Live acceptance belongs to the affected implementation outcome under scoped app/service authority.

Historical implementation and detailed prior architecture remain at [the pre-reset revision](https://github.com/kapitalismho/vrc-translator-bench/blob/fbab10a0455d91d5419d9673499d25b7ac86c566/docs/architecture.md). No old results are migrated into a new ranking by this change.
