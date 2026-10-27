# VRC Translator Bench

A community benchmark for conversation translation. The approved [final plan](docs/benchmark-final-plan.md) replaces the original six-direction microphone-to-OSC evaluation with a peer-centered EN→ZH / JA→KO comparison, episode-level GEMBA-ESA quality, separate semantic-wait p50/p90, and evidence-bound costs.

**Current state: native capture and source preparation, not a completed benchmark.** R1 supplies episode/role/pass execution and early feasibility. [R2 preparation](docs/corpus.md#r2-source-review-and-preparation) supplies pinned local candidates and actual source-review evidence. The owner-approved ASCEND amendment permits approximate speaker-offset reconstruction, declared paced fallback and same-speaker P3 continuations; it supersedes the original-clock/missing-gap-audio gate, not the remaining content, role, grouping or rights checks. Two-stage judging, final all-profile admission and public results remain separate work. The [implementation plan and published R0–R10 issues](docs/benchmark-implementation-plan.md) preserve the GPT/backend versus Claude/presentation split.

## What remains usable

- Windows WASAPI playback/calibration, episode/role/pass routing, app-native output collection, durable attempt history, interruption/resume and owned-process cleanup.
- All 14 application profiles, independent native feasibility scopes and retained historical configuration, capture, failure and source evidence.
- GPT 6 Astra / Sign in with ChatGPT transport, Windows child containment and low-level durable call storage. There is currently **no scoring CLI**.
- Local cost-log ingestion, attribution, Decimal arithmetic, subscription/free/unknown treatment and original-evidence protection. New episode/pass normalization is not implemented.
- Separate path-redacted capture exports; publication still needs content and rights inspection.
- Offline ASCEND, IngCrowd and FLEURS/C1 materializers for 51 main source episodes, 12 development episodes and two controls, with source/sample/reference checks and nine main/four development ASCEND T1 parents. Runtime execution plans and R6 admission remain separate.

The runner accepts **episode schema 2**, not historical stage plans. Ordinary inputs are peer; T1 uses simultaneous peer/self. The owner-approved VRCLT and Kikitan exceptions use self for ordinary cases and separate A/B self passes for T1, with one logical episode. Native receipt clocks do not certify producer completion or screen rendering. Historical profile readiness is not new-protocol admission.

Kikitan's approved primary is its installed `--no-ui` WebSocket `recognition` output, not user-data OSC. The owner adopted this route after a bounded KIKI2 EN→ZH experiment. The original UDP Unicode defect and KIKI1 headless crash remain historical evidence; no application patch or automatic admission of other scopes is implied. See the [current Kikitan contract](docs/benchmark-final-plan.md#kikitan--kiki1kiki2).

## Install and inspect

Use Python 3.11+; actual audio requires Windows WASAPI and `.[audio]`. WebSocket collectors require `.[native]`.

```powershell
python -m pip install -e ".[audio,native,test]"
python -m pytest -q
python -m bench.cli --help
python -m bench.cli profiles --catalog profiles/catalog.json
```

`profiles` reports each profile's confirmed, blocked and unverified native condition scopes, separately from R6's pending final quality/time admission. It does not launch apps. `--check-ports` probes and releases relevant native loopback ports; availability is not collection or translation evidence.

[Capture CLI documentation](docs/cli.md) defines the episode plan, native collectors, adapter lifecycle and clock/outcome boundaries. Real runs require explicit device selection and scoped app/service authority. No new corpus or TTS production is implied by a small development smoke.

## Reconcile local cost evidence

```powershell
python -m bench.cli costs --spec tests/fixtures/costs/synthetic-spec.json --output .data/costs/synthetic.json
python -m bench.cli costs --spec tests/fixtures/costs/real-missing-spec.json --output .data/costs/real-missing.json
```

The first input is synthetic arithmetic. The second binds a historical VRCS2 capture with missing usage evidence and must retain null costs. Neither supplies measured provider billing. See [costs](docs/costs.md) for the existing format and its migration limits.

## Historical evidence, not a new baseline

The previous implementation is retained at commit [`fbab10a0455d91d5419d9673499d25b7ac86c566`](https://github.com/kapitalismho/vrc-translator-bench/tree/fbab10a0455d91d5419d9673499d25b7ac86c566). Old corpus preparation, sentence-alignment/delivery/FOL/LUL analysis, single-call ESA, MetricX and supplementary sampling commands have been removed from the current package, not renamed into the new protocol.

`corpus/`, historical fields in `profiles/catalog.json`, `profiles/findings/`, `profiles/evidence/` and ignored `.data/` assets retain their evidence identities. Do not regenerate or rewrite historical hashes. The old D1/D3 analysis has an integrity/acceptance hold; captured output is evidence, not an approved ranking. R1 does not repair old scores or complete the retired issue #8.

Historical sections of the corpus/metric/quality guides remain explicitly marked as historical. The corpus guide also documents current R2 candidate preparation. Use the pinned revision to inspect former implementations; do not resume old measurements or queues using this checkout.

## Contracts and rights

- [Implementation sequence, retained/retired inventory and published issues](docs/benchmark-implementation-plan.md)
- [Approved benchmark contract](docs/benchmark-final-plan.md)
- [Architecture and current boundaries](docs/architecture.md)
- [Capture CLI and adapter contracts](docs/cli.md)
- [Profile findings and historical evidence](docs/profiles.md)
- [R2 preparation and historical corpus provenance](docs/corpus.md), [historical metrics](docs/metrics.md), [judge foundations and historical scoring](docs/quality.md)
- [Usage-cost processing](docs/costs.md)

Code and maintained documentation use MIT. Imported/derived data retains source-specific terms. Audio, private transcripts, raw app/billing logs, credentials, model weights and downloads stay local unless separately cleared for publication. In particular, existing YODAS2 attribution holds and IngCrowd's noncommercial restrictions are not removed by choosing a new plan.
