# VRC Translator Bench

Local speech-corpus preparation, resumable Windows audio-to-OSC capture, application-profile preparation, derived measurements and blinded automatic quality scoring for the community translation benchmark in [issue #1](https://github.com/kapitalismho/vrc-translator-bench/issues/1). The repository implements local corpus work ([#2](https://github.com/kapitalismho/vrc-translator-bench/issues/2)), capture infrastructure ([#3](https://github.com/kapitalismho/vrc-translator-bench/issues/3)), profile findings and bounded actual-GUI development pilots ([#4](https://github.com/kapitalismho/vrc-translator-bench/issues/4)), calculation/report data ([#5](https://github.com/kapitalismho/vrc-translator-bench/issues/5)), and scoring infrastructure ([#6](https://github.com/kapitalismho/vrc-translator-bench/issues/6)), not a completed comparison or human-verified quality ranking.

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

After local data loss, the owner accepted `issue-2-local-v2`: all indexed audio retains its original hash, but the regenerated Japanese main reference has a new hash. [Recovery provenance and revision boundaries](docs/corpus.md#local-recovery-revision) distinguish restored assets from regenerated references and historical pilot evidence.

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

Windows cable calibration/playback and actual GUI-operated microphone-to-translated-OSC development pilots were observed for VRCT, VRCS and VRCLT configurations. Their bounded results, failures and cleanup limits are recorded separately from earlier PuriPuly manual-text/control probes. Use only explicitly owner-authorized application instances, keep secrets out of exported evidence, and do not run VRChat.

## Application profiles

[Profile preparation](docs/profiles.md) accounts for all 14 planned profiles, exact model/access caveats, observed GUI state and reserved OSC ports. The active plan uses ten sequential competitor waves; the owner deferred all four PuriPuly profiles. Bounded readiness requires actual audio/OSC evidence, not source availability or saved credentials. The [catalogue](profiles/catalog.json) records each current ready/blocked finding and its limits.

```powershell
python -m tools.prepare_profile_checks
bench profiles --check-ports
bench profiles --require-ready
```

The first command prepares local ten-second development clips for the three source languages. Catalogue inspection checks static wave/port/workload conflicts; `--require-ready` exits 2 while readiness evidence is missing, including owner-deferred profiles. See the [actual pilot evidence](profiles/evidence/issue45/) and separately labelled [historical control-only evidence](profiles/evidence/puripuly-control.json). [GUI operator instructions](docs/cli.md#actual-gui-development-pilots) connect actual observed GUI actions to the existing runner without hidden application API control.

## Derive measurements

```powershell
python -m bench.cli metrics --manifest .data/runs/pilot/manifest.json --spec metrics-spec.json --output .data/reports/pilot.json
```

The [metric definitions and report-data contract](docs/metrics.md) describe reference normalization, versioned application rules, cross-language alignment, timing/delivery, quality segments, diagnostics and session-clustered summaries. Optional model alignment uses `.[alignment]`; inspected, input-bound alignment caches support offline calculations. Raw capture is never rewritten. Missing correspondence, late output, failure, reference uncertainty and unsupported measurements remain visible.

Actual VRCT, VRCS and VRCLT translation streams now supply distinct-application integration inputs. Per-run interpretation and inspected correspondence remain evidence-bound: rolling context, cumulative updates, truncation and unknown relationships must not become invented final-output reconstruction or quality scores. Synthetic checks and PuriPuly manual-text probes remain separate. Derived reports can contain speech and local provenance; publish only inspected, rights-cleared derivatives with their original hashes.

## Score translation quality

```powershell
python -m bench.cli quality prepare --report .data/reports/pilot.json --root .data/quality/pilot
python -m bench.cli quality status --root .data/quality/pilot
python -m bench.cli quality score --root .data/quality/pilot --transport-spec judge.json --measurements-ended --limit 6
python -m bench.cli quality report --root .data/quality/pilot --output .data/quality/pilot/report.json --review-output .data/quality/pilot/korean-review.json
```

Follow the [quality setup, prompts, resume, MetricX and review-packet contract](docs/quality.md) to configure the selected Sign in with ChatGPT route. The durable queue preserves raw responses, actual model identity, failures and unresolved calls; missing scores never become successful zero-error judgments. Optional `.[metricx]` supplies the selected supplementary local QE model runtime. Finish timed measurements before either scorer runs. Automatic scores and prepared Korean review packets are not human semantic verification.

## Reconcile usage costs

```powershell
python -m bench.cli costs --spec tests/fixtures/costs/synthetic-spec.json --output .data/costs/synthetic.json
python -m bench.cli costs --spec tests/fixtures/costs/real-missing-spec.json --output .data/costs/real-missing.json
```

The [cost input and report contract](docs/costs.md) covers selected OpenRouter/Qwen exports, PuriPuly diagnostic usage, dated prices, request-window attribution, subscription/free conditions and explicit normalization coverage for [issue #7](https://github.com/kapitalismho/vrc-translator-bench/issues/7). The first example is synthetic arithmetic; the second uses an actual historical VRCS2 capture with missing provider evidence and therefore null costs. Neither establishes measured billing totals. PP execution remains deferred; permitted actual exports and run-bound PP usage remain empirical prerequisites.

## Contracts and rights

- [Architecture and artifact boundaries](docs/architecture.md)
- [Curation, reproduction and observed verification](docs/corpus.md)
- [Capture CLI, persistence, adapter and timing contracts](docs/cli.md)
- [Derived measurement definitions and report-data contract](docs/metrics.md)
- [Profile controls, readiness findings, waves and evidence limits](docs/profiles.md)
- [Blinded quality scoring, provenance and Korean reference review](docs/quality.md)
- [Usage-cost reconciliation, service conditions and evidence gaps](docs/costs.md)
- [Six-direction local index](corpus/manifest.json)
- [English references](corpus/english/manifest.json), [Chinese references](corpus/chinese/manifest.json), [Japanese public-safe metadata](corpus/japanese/local-preparation.json), [nonspeech attribution](corpus/nonspeech/manifest.json)

Code and maintained documentation use MIT. AMI assets retain CC BY 4.0; Chinese derived audio/timelines retain CC BY-SA 4.0. Japanese dataset-declared CC BY 3.0 does not resolve selected-video attribution. Do not publish unresolved assets, treat local paths as public download locations, or count shared source pairs as independent evidence.
