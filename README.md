# VRC Translator Bench

A community benchmark for conversation translation. The approved [final plan](docs/benchmark-final-plan.md) replaces the original six-direction microphone-to-OSC evaluation with a peer-centered EN→ZH / JA→KO comparison, episode-level GEMBA-ESA quality, separate semantic-wait p50/p90, and evidence-bound costs.

**Current state: protocol reset, not a completed new benchmark.** Native-output collectors, the new corpus, synchronized T1 playback, two-stage judging and public results remain implementation work. The [migration classification and replacement issue drafts](docs/benchmark-implementation-plan.md) define that work and preserve the GPT/backend versus Claude/presentation split. GitHub issues have not been deleted or replaced by this local reset.

## What remains usable

- Windows WASAPI playback/calibration, ordered raw chatbox OSC capture, durable attempt history, interruption/resume and owned-process cleanup.
- All 14 application profiles and historical configuration, capture, failure and source evidence.
- GPT 6 Astra / Sign in with ChatGPT transport, Windows child containment and low-level durable call storage. There is currently **no scoring CLI**.
- Local cost-log ingestion, attribution, Decimal arithmetic, subscription/free/unknown treatment and original-evidence protection. New episode/pass normalization is not implemented.
- Separate path-redacted capture exports; publication still needs content and rights inspection.

The retained runner still accepts the **old single-input self/cable→OSC plan**. It does not implement peer collection, two-route T1, VRCLT split passes or the new observation-completeness contract. Historical profile readiness is not new-protocol admission.

## Install and inspect

Use Python 3.11+; actual audio additionally requires Windows WASAPI and `.[audio]`.

```powershell
python -m pip install -e ".[test]"
python -m pytest -q
python -m bench.cli --help
python -m bench.cli profiles --catalog profiles/catalog.json
```

`profiles` reports `historical_status`, `historical_ready_profiles` and `new_protocol_status: unverified`. It does not launch apps. `--check-ports` optionally probes and releases the historical loopback UDP ports; it is not future reservation or native-output readiness.

[Capture CLI documentation](docs/cli.md) describes the retained explicit-plan runner. Calibration, playback and real runs operate audio/app resources and require their applicable execution authority; this reset did not run them against translators.

## Reconcile local cost evidence

```powershell
python -m bench.cli costs --spec tests/fixtures/costs/synthetic-spec.json --output .data/costs/synthetic.json
python -m bench.cli costs --spec tests/fixtures/costs/real-missing-spec.json --output .data/costs/real-missing.json
```

The first input is synthetic arithmetic. The second binds a historical VRCS2 capture with missing usage evidence and must retain null costs. Neither supplies measured provider billing. See [costs](docs/costs.md) for the existing format and its migration limits.

## Historical evidence, not a new baseline

The previous implementation is retained at commit [`fbab10a0455d91d5419d9673499d25b7ac86c566`](https://github.com/kapitalismho/vrc-translator-bench/tree/fbab10a0455d91d5419d9673499d25b7ac86c566). Old corpus preparation, sentence-alignment/delivery/FOL/LUL analysis, single-call ESA, MetricX and supplementary sampling commands have been removed from the current package, not renamed into the new protocol.

`corpus/`, `profiles/catalog.json`, `profiles/findings/`, `profiles/evidence/` and ignored `.data/` assets retain their existing identities. Do not regenerate or rewrite their hashes to accept the reset. The old D1/D3 analysis has an integrity/acceptance hold; captured output is evidence, not an approved ranking. This reset neither repairs old scores nor completes issue #8.

Historical corpus/metric/quality guides remain explicitly marked as historical. Use the pinned revision to inspect their former implementation; do not resume old measurements or queues using this checkout.

## Contracts and rights

- [Implementation sequence, retained/retired inventory and issue drafts](docs/benchmark-implementation-plan.md)
- [Approved benchmark contract](docs/benchmark-final-plan.md)
- [Architecture and current boundaries](docs/architecture.md)
- [Capture CLI and adapter contracts](docs/cli.md)
- [Profile findings and historical evidence](docs/profiles.md)
- [Historical corpus provenance](docs/corpus.md), [historical metrics](docs/metrics.md), [judge foundations and historical scoring](docs/quality.md)
- [Usage-cost processing](docs/costs.md)

Code and maintained documentation use MIT. Imported/derived data retains source-specific terms. Audio, private transcripts, raw app/billing logs, credentials, model weights and downloads stay local unless separately cleared for publication. In particular, existing YODAS2 attribution holds and IngCrowd's noncommercial restrictions are not removed by choosing a new plan.
