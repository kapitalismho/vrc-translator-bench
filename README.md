# VRC Translator Bench

Local speech-corpus preparation for the community translation benchmark in [issue #1](https://github.com/kapitalismho/vrc-translator-bench/issues/1). This repository currently implements [issue #2](https://github.com/kapitalismho/vrc-translator-bench/issues/2), not the application runner, scoring system or comparison results.

The owner [replaced the Hugging Face publication criterion with local preparation](https://github.com/kapitalismho/vrc-translator-bench/issues/2#issuecomment-6282606626). No public audio dataset has been published. Audio, model weights and downloads remain in ignored `.data/`; Git contains preparation code and permitted metadata.

## Local inputs

`corpus/manifest.json` is the six-direction index. Each pair references the same physical main waveform rather than duplicated source evidence.

| Shared directions | Source | Main playback | Separate development | Isolated responses |
|---|---|---:|---:|---:|
| D1 English → Japanese / D2 English → Chinese | AMI scenario-only test headsets | 30 min | 5 min | 20 for D1 |
| D3 Chinese → Korean / D5 Chinese → Japanese | AliMeeting Eval headsets | 30 min | 5 min | 20 for D3 |
| D4 Japanese → Korean / D6 Japanese → English | YODAS2 mixed-speaker candidates | 30 min | 5 min | 20 for D6 |

Each main budget is 20 minutes general plus 10 minutes separately selected stress **including recorded separator accounting**, not 30 minutes of uninterrupted speaking. A three-minute nonspeech/background track, the exact five-minute D1 repeat prefix and pre-result common-clip shortlists are also identified. Main-run protocol freeze and final common-excerpt selection belong to issue #8.

English and Chinese use human lexical references with automatic timing. Japanese is **automatic and exploratory**, with estimated speakers, provisional conversation eligibility and unresolved original-video rights. Its current main reference retains 33 untimed words out of 3,166 rather than fabricating times. Japanese full text/timelines remain local. No human listening or independent transcription-validation study is claimed; numerical waveform and transformed-timeline checks are documented.

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

## Contracts and rights

- [Architecture and artifact boundaries](docs/architecture.md)
- [Curation, reproduction and observed verification](docs/corpus.md)
- [Six-direction local index](corpus/manifest.json)
- [English references](corpus/english/manifest.json), [Chinese references](corpus/chinese/manifest.json), [Japanese public-safe metadata](corpus/japanese/local-preparation.json), [nonspeech attribution](corpus/nonspeech/manifest.json)

Code and maintained documentation use MIT. AMI assets retain CC BY 4.0; Chinese derived audio/timelines retain CC BY-SA 4.0. Japanese dataset-declared CC BY 3.0 does not resolve selected-video attribution. Do not publish unresolved assets, treat local paths as public download locations, or count shared source pairs as independent evidence.
