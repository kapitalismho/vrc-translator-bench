# VRC Translator Bench

Local speech-corpus preparation, resumable Windows audio-to-OSC capture, and derived measurements for the community translation benchmark in [issue #1](https://github.com/kapitalismho/vrc-translator-bench/issues/1). The repository implements the local corpus work in [issue #2](https://github.com/kapitalismho/vrc-translator-bench/issues/2), capture infrastructure in [issue #3](https://github.com/kapitalismho/vrc-translator-bench/issues/3), and the calculation/report-data layer in [issue #5](https://github.com/kapitalismho/vrc-translator-bench/issues/5). This is not a completed application comparison or quality-judging system.

The owner [replaced the Hugging Face publication criterion with local preparation](https://github.com/kapitalismho/vrc-translator-bench/issues/2#issuecomment-6282606626). No public audio dataset has been published. Audio, model weights and downloads remain in ignored `.data/`; Git contains preparation code and permitted metadata.

## Local inputs

`corpus/manifest.json` is the six-direction index. Each pair references the same physical main waveform rather than duplicated source evidence.

| Shared directions | Source | Main playback | Separate development | Isolated responses |
|---|---|---:|---:|---:|
| D1 English → Japanese / D2 English → Chinese | AMI scenario-only test headsets | 30 min | 5 min | 20 for D1 |
| D3 Chinese → Korean / D5 Chinese → Japanese | AliMeeting Eval headsets | 30 min | 5 min | 20 for D3 |
| D4 Japanese → Korean / D6 Japanese → English | YODAS2 mixed-speaker candidates | 30 min | 5 min | 20 for D6 |

Each main budget is 20 minutes general plus 10 minutes separately selected stress **including recorded separator accounting**, not 30 minutes of uninterrupted speaking. A three-minute nonspeech/background track, the exact five-minute D1 repeat prefix and pre-result common-clip shortlists are also identified. Main-run protocol freeze and final common-excerpt selection belong to issue #8.

English and Chinese use human lexical references with automatic timing. Japanese is **automatic and exploratory**, with estimated speakers, provisional conversation eligibility and unresolved original-video rights. Its 3,166 main words now have acoustic timing estimates, including low-confidence covering alignment for formerly unsupported words; numeric completeness is not accuracy. Japanese full text/timelines remain local. No human listening or independent transcription-validation study is claimed.

The owner delegated practical assessment rather than providing a listening judgment. [The sample record](corpus/practical-assessment.json) combines original human annotations/supplementary captions, actual recognized content and waveform checks, including Japanese reference disagreements and perceptual limits. It is not a human-listening result.

## Run

Use Python 3.11+ and FFmpeg on PATH; actual preparation was exercised with Python 3.12 and 3.14 on Windows. Chinese and Japanese model pipelines use separate Python 3.12 environments and CPU inference.

```powershell
py -3.12 -m venv .data/check-venv
.data/check-venv/Scripts/python.exe -m pip install -e ".[test]"
.data/check-venv/Scripts/python.exe -m pytest -q
```

Follow [corpus preparation](docs/corpus.md) for source acquisition, optional model dependencies, per-language commands, licenses and limitations. After preparing all local bundles:

```powershell
.data/check-venv/Scripts/python.exe -m tools.index_corpus
.data/check-venv/Scripts/python.exe -m tools.check_corpus
```

The index builder refuses missing or checksum-mismatched audio; it does not fill missing material. The checker verifies actual local waveform hashes/frames, direction sharing, duration budgets, reference hashes and the repeat prefix. It does not certify linguistic correctness or rights. On a clean clone, explicit Chinese real-material smoke tests skip until local audio exists; deterministic tests remain available.

## Capture runs

The `bench` CLI provides real-time WASAPI shared-mode cable playback, measured cable correction, ordered OSC capture, per-profile attempt history, resume and operator status:

```powershell
python -m pip install -e ".[audio]"
bench calibrate --output .data/calibration/cable.json
bench run --plan plan.json --run-id pilot
bench status pilot
bench run --resume pilot
```

Follow the [runner CLI, plan and adapter contract](docs/cli.md) to prepare the plan and application adapter. Artifacts default to ignored `.data/runs`. Completed and product-failed work survives resume; interrupted work retains invalid evidence and gets a new marked attempt.

Windows cable calibration/playback was observed. A real translator pilot was **not run**: an isolated configured translator was unavailable. Synthetic process/OSC checks do not establish real application translation. Application-specific preparation belongs to issue #4; do not attach this runner to a personal app instance or run VRChat.

## Derive measurements

```powershell
python -m bench.cli metrics --manifest .data/runs/pilot/manifest.json --spec metrics-spec.json --output .data/reports/pilot.json
```

The [metric definitions and report-data contract](docs/metrics.md) describe reference normalization, versioned application rules, cross-language alignment, timing/delivery, quality segments, diagnostics and session-clustered summaries. Optional model alignment uses `.[alignment]`; inspected, input-bound alignment caches support offline calculations. Raw capture is never rewritten. Missing correspondence, late output, failure, reference uncertainty and unsupported measurements remain visible.

Actual distinct-application translation traces and observed interpretation rules remain a #4 integration prerequisite. Synthetic boundary checks and retained PuriPuly manual-text OSC observations do not establish audio-to-translated-OSC accuracy. Derived reports can contain speech and local provenance: keep them local until their content and rights are cleared.

## Contracts and rights

- [Architecture and artifact boundaries](docs/architecture.md)
- [Curation, reproduction and observed verification](docs/corpus.md)
- [Capture CLI, persistence, adapter and timing contracts](docs/cli.md)
- [Derived measurement definitions and report-data contract](docs/metrics.md)
- [Six-direction local index](corpus/manifest.json)
- [English references](corpus/english/manifest.json), [Chinese references](corpus/chinese/manifest.json), [Japanese public-safe metadata](corpus/japanese/local-preparation.json), [nonspeech attribution](corpus/nonspeech/manifest.json)

Code and maintained documentation use MIT. AMI assets retain CC BY 4.0; Chinese derived audio/timelines retain CC BY-SA 4.0. Japanese dataset-declared CC BY 3.0 does not resolve selected-video attribution. Do not publish unresolved assets, treat local paths as public download locations, or count shared source pairs as independent evidence.
