# Corpus preparation

Authority: [issue #2](https://github.com/kapitalismho/vrc-translator-bench/issues/2) and [parent #1](https://github.com/kapitalismho/vrc-translator-bench/issues/1).

## Release boundary

The owner authorized local data preparation and repository commit/push without a PR. The [approved scope amendment](https://github.com/kapitalismho/vrc-translator-bench/issues/2#issuecomment-6282606626) replaces #2's Hugging Face publication criterion with local audio, references, playback timelines, checksums, and asset-level rights/unresolved-permission records. All other preparation and practical verification obligations remain. Local outputs are not a public dataset release; future redistribution still requires authorization, a destination, and rights clearance.

Audio, downloaded corpora, model weights and environments live under ignored `.data/`. Code uses MIT; corpus assets, transcripts and timelines retain their source-specific terms. Do not apply the code license to data. Japanese derived speech text and timelines also remain in `.data/` while original-video attribution is unresolved.

- AMI: [official license](https://groups.inf.ed.ac.uk/ami/corpus/license.shtml), CC BY 4.0. Credit AMI Project and retain original notices. Human transcription/manual dialogue acts do not make the automatically forced-aligned word times human-verified.
- AliMeeting: [OpenSLR 119](https://www.openslr.org/119/), CC BY-SA 4.0. Credit Alibaba Group and supplied authors. Chinese derivative audio and timelines retain ShareAlike; a mirror's conflicting license tag cannot override the original terms.
- YODAS2: [dataset card](https://huggingface.co/datasets/espnet/yodas2), declared CC BY 3.0. Its IDs are not original YouTube IDs. The [maintainer declined to publish original IDs](https://huggingface.co/datasets/espnet/yodas2/discussions/2). Dataset-level terms alone do not supply the required video-specific attribution and provenance. No inspected Japanese candidate is cleared for redistribution.
- MUSAN: use each asset's original terms, not only the corpus-wide label. The selected SoundBible files are public-domain recordings with their creators and original URLs retained. The small pinned mirror has not been byte-compared against the complete official MUSAN archive.

## Nonspeech/background track

Run from the repository root with Python, NumPy and FFmpeg on PATH:

```powershell
py tools/prepare_nonspeech.py
py -m pytest tests/test_nonspeech.py -q
ffprobe -v error -show_entries stream=codec_name,sample_rate,channels,duration -of json .data/nonspeech/nonspeech.wav
```

The script downloads only four named recordings, verifies the three remotely pinned keyboard/noise hashes, and records the actual AMI source and output hashes. Output is `.data/nonspeech/nonspeech.wav`; metadata and asset attribution are in `corpus/nonspeech/manifest.json`. The 180-second PCM16 mono track has 8,640,000 samples at 48 kHz.

| Playback interval | Content | Treatment |
|---|---|---|
| 0–60 s | Digital silence | Exact zero samples |
| 60–90 s | Real keyboard typing | Freesound sound 380135, yottasounds, CC0; source 10–40 s of the HQ MP3 rendition, not the original WAV |
| 90–120 s | Coin drop and finger snaps, separated by silence | MUSAN `noise-sound-bible-0017` at 90 s and `noise-sound-bible-0029` at 100 s; full source recordings, no repeated events |
| 120–180 s | Background human conversation | Official AMI `ES2003a.Mix-Headset.wav`, source 120–180 s; independent of the scenario-test main selections |

Scoring has exactly two intervals: `[0,120)` silence/keyboard/nonverbal and `[120,180)` background human conversation. Do not merge their output counts or extrapolate them to an hourly rate. Inserted silence has no source recording; every recorded event has a source-to-playback entry. This diagnostic track does not use the main corpus's two-second chunk separators.

Recorded components are downmixed/resampled and receive constant gain with a peak ceiling of 0.5 full scale. Background additionally has an RMS ceiling of −30 dBFS; the peak ceiling takes precedence, so its observed RMS may be lower. The output background is attenuated meeting speech, not a recording made at a measured physical distance. The AMI reference contains 55 fully contained words from speaker B and 17 from C in the selected source minute; these establish conversational content, not an independent listening check.

Observed checks: the actual build completed; FFprobe reported 48 kHz mono PCM16 and 180 seconds; two focused tests passed. Direct emitted-sample inspection confirmed the first minute is digital silence. Background RMS was −30.404 dBFS because of the peak ceiling. An initial probe incorrectly expected exactly −30 dBFS; the observed result exposed that probe assumption, not clipping or missing audio. FFmpeg emitted inferred mono-channel-layout warnings while decoding source WAVs.

No human listening was performed. Before freezing this track, listen to a small keyboard/nonverbal sample to exclude incidental speech and to the background interval to confirm the intended presentation. Creator descriptions and transcript inspection are not a substitute for that observation.

## Chinese D3/D5 preparation

`tools/prepare_chinese.py` uses the original AliMeeting Eval archive, not a third-party audio mirror. `corpus/chinese/archive.json` records its hash; `inventory.json` records all 25 headset tracks across eight sessions. `curation.json` records topics and reserves whole sessions before fixed-seed selection (`20261020`). General sampling is separate from deliberate stress selection. Everyday family/school and shopping topics receive priority, but no material is certified spontaneous casual chat; the verified-casual proportion is conservatively zero.

Create the isolated optional environment:

```powershell
py -3.12 -m venv .data/chinese/venv
$env:PIP_CACHE_DIR = "$PWD/.data/chinese/cache/pip"
.data/chinese/venv/Scripts/python.exe -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
.data/chinese/venv/Scripts/python.exe -m pip install qwen-asr==0.0.6 jieba==0.42.1 numpy==2.5.4 pytest==9.1.1
.data/chinese/venv/Scripts/python.exe -X utf8 tools/prepare_chinese.py acquire
.data/chinese/venv/Scripts/python.exe -X utf8 tools/prepare_chinese.py select
.data/chinese/venv/Scripts/python.exe -X utf8 tools/prepare_chinese.py align --threads 4
.data/chinese/venv/Scripts/python.exe -X utf8 tools/prepare_chinese.py build
```

FFmpeg must be on PATH. The observed environment was Python 3.12.10, CPU Torch 2.14.1, Transformers 4.57.6 and FFmpeg 8.0.1. Corpus/model downloads and alignment caches remain under `.data/chinese`.

`corpus/chinese/manifest.json` is the reference and playback contract:

- Both D3 and D5 use `.data/chinese/audio/zh-main.wav`: 1,800 seconds, nine chunks, six original sessions and nine selected target speakers. General is 1,200 seconds and stress 600 seconds **including assigned two-second separators**; actual chunk audio totals 1,784 seconds and separators total 16 seconds.
- Each chunk selects the participant's actual mono headset, not a microphone-array channel. Other speakers' annotations supply unscored context and speaker-change turns. Compression removes only other-speaker-occupied portions of target-silent gaps, retaining three seconds and silent shoulders. Target's own pauses remain.
- `bundles.main.chunks` carries source-to-playback spans, target words, reference sentences, turns, context, source identities and per-asset hashes. All reference times are regenerated after compression and chunk placement.
- `.data/chinese/audio/zh-dev.wav` is a separate 300-second probe from reserved session `R8009_M8019`, shared by D3/D5. `isolated_D3` identifies 20 real held-out clips from `R8009_M8020`, including short, long and alignment-estimated internally paused speech.
- `common_clip_shortlist` identifies pre-result candidates. It is not a claim that the later main-run protocol has been frozen.

Human lexical text is preserved. Existing punctuation remains; a terminal full stop is restored only where absent, with segment-boundary uncertainty disclosed. Word timing is automatic: pinned Qwen3 ForcedAligner raw predictions are checked without timestamp interpolation. Twelve invalid predictions among 532 segments were rejected and repaired by genuine vocabulary-covered CTC alignment, with original failures retained in `alignment-report.json`. Model revisions and decisions are in `alignment-decisions.json`. This is forced alignment of human text, not substitution with evaluated-ASR output.

Zero-length and overlapping word estimates remain explicitly uncertain instead of being silently deleted or given invented duration. Pause/backchannel/filler counts are model- or text-pattern candidates, not listening-confirmed linguistic labels. Stress material must not enter a representative general-conversation ranking.

Focused and real-material checks:

```powershell
.data/chinese/venv/Scripts/python.exe -m pytest tests/test_chinese_preparation.py tests/test_chinese_real.py -q
```

The real-material checks inspect emitted frames, exact separator silence, hashes, immutable human text, transformed reference mappings and session separation. Six small waveform windows are compared against independently cropped source headsets, checking the actual selected audio rather than just self-consistent JSON. These are not an independent transcription or listening study. Chinese audio, transcripts and timelines remain CC BY-SA 4.0; retain `attribution.json` and change notices with any permitted derivative.

## English D1/D2 preparation

```powershell
py tools/prepare_english.py plan
py tools/prepare_english.py prepare
py tools/prepare_english.py check
py -m pytest tests/test_english_timeline.py -q
```

The English CLI uses the standard library and FFmpeg. `plan` acquires the official manual-annotation archive and records fixed-seed selections; `prepare` downloads only selected official headset files and emits audio/timelines; `check` validates the actual local output. The observed Python was 3.14.2. `selection-policy.json` records seed `20261020`, eligibility and transformation rules before selection.

The declared partition is **AMI official scenario-only test/SC**, not full-corpus-ASR test. Full-corpus's additional natural meetings lack the required manual dialogue acts. All chosen sessions are scenario meetings. Only the original `top.14` interval in ES2014d is counted as casual chat: 89.699 retained playback seconds, about 4.98% of main or 7.47% of the 20-minute general budget. Surrounding work discussion is not relabelled casual.

`corpus/english/manifest.json` identifies 31 rendered assets, source hashes and participant/channel/global-speaker mappings:

- D1/D2 both use `.data/english/audio/main.wav` and `corpus/english/timelines/main.json`: 1,800 seconds across six source sessions. Four general chunks total 1,192 seconds plus eight seconds of assigned separators; two stress chunks total 598 seconds plus two seconds of separator.
- `.data/english/audio/development.wav` contains two separate 149-second chunks and a two-second separator. Development source sessions are absent from main.
- Twenty `isolated-XX.wav` clips are real complete dialogue acts from held-out TS3007a, including seven short, six long and seven internally-paused candidates. Holdout is by original meeting, not a claim of globally disjoint speaker identities across meeting phases.
- `.data/english/audio/repeat.wav` is the exact first 300 seconds of main, including the first following separator. `common-shortlist.json` retains three pre-result candidate clips.

Only the chosen participant's lexical speech is scored. Other-speaker context remains unscored and may not be audible in the selected headset. Original human transcripts and manual dialogue acts define reference words and DA-based sentence units; source word times are automatic forced alignment. A dialogue act is not a claim of a linguistically validated grammatical sentence. Speaker-label changes define turns with overlap retained.

Target-event gaps longer than eight seconds with at least one second of other-speaker word activity are reduced to three seconds. Gaps without that activity and all shorter target pauses are retained. Every removed/retained span, separator and edge pad is explicit; word/DA/turn playback times are rebuilt. Up to two seconds of edge silence per chunk may avoid cutting a target word; actual main edge padding is 2.204 seconds total, included in chunk budgets and not counted as speech. Audio is upsampled from released 16 kHz headsets to 48 kHz mono PCM16 with constant −3 dBFS peak normalization.

The exercised `check` command verified 31 audio/timeline pairs, including hashes, sample budgets, target-only complete lexical coverage, manual-DA coverage, mapped words and exact repeat/separator samples. Nineteen focused regression tests passed. Three mapped 100-ms windows after real compression boundaries matched independently decoded source PCM16 exactly; see `execution-report.json`. No human listening or independent acoustic validation of stress candidates is claimed. Preserve `AMI-LICENCE.txt`, attribution and transformation notices.

## Japanese D4/D6 exploratory preparation

All Japanese speech text, captions, full references and audio remain local. `corpus/japanese/local-preparation.json` is a public-safe inventory of source IDs, hashes, durations, methods and unresolved rights; it is not a publishable Japanese dataset.

```powershell
py -3.12 -m venv .data/japanese/venv
.data/japanese/venv/Scripts/python.exe -m pip install --cache-dir .data/japanese/pip-cache numpy==2.5.4 soundfile==0.14.0 sherpa-onnx==1.13.8 transformers==5.20.2 fugashi==1.5.2 unidic-lite==1.0.8
.data/japanese/venv/Scripts/python.exe -m pip install --cache-dir .data/japanese/pip-cache torch==2.14.1+cpu --index-url https://download.pytorch.org/whl/cpu
.data/japanese/venv/Scripts/python.exe tools/prepare_japanese.py acquire --with-alignment
.data/japanese/venv/Scripts/python.exe tools/prepare_japanese.py extract Yr7rGfescvQ YvBXxjwqeTy YIIDry4AVKA
.data/japanese/venv/Scripts/python.exe tools/prepare_japanese.py select
.data/japanese/venv/Scripts/python.exe tools/prepare_japanese.py render
.data/japanese/venv/Scripts/python.exe tools/prepare_japanese.py reference --threads 2
.data/japanese/venv/Scripts/python.exe tools/prepare_japanese.py playback-references
.data/japanese/venv/Scripts/python.exe tools/prepare_japanese.py heldout
.data/japanese/venv/Scripts/python.exe tools/prepare_japanese.py check
.data/japanese/venv/Scripts/python.exe tools/prepare_japanese.py export-metadata
```

The pinned YODAS2 revision is `c9674490249665d658f527e2684848377108d82c`. Acquisition downloads one 1.406 GB Japanese shard, not the entire configuration. Reazon ASR weights/tokens total about 169 MB, but the acoustic aligner additionally needs a 1.272 GB Wav2Vec2 checkpoint and the speaker models have separate payloads. This is not a 169 MB total pipeline. The exercised Python was 3.12.10; FFmpeg was 8.0.1. Public dependency installation initially used the shared pip cache; it was left untouched. Corpus and model payloads are under `.data/japanese`.

Fixed seed `20261020` selects general candidates from the recorded pool. Source content is caption-assisted bonsai discussion and exercise-response material across three pseudonymous original videos. No casual-chat candidate was established in the inspected shard; caption-derived general tags are entirely work/discussion, while the actual casual-chat fraction is unknown. Uploaded/manual captions are supplementary evidence, never replacements for ASR words.

D4/D6 share `.data/japanese/playback/ja-main.wav`: exactly 1,800 seconds, nine chunks, general 1,188 source seconds plus 12 assigned gap seconds and stress 596 source seconds plus four gap seconds. Separate development is 300 seconds. Twenty real D6 isolated crops use a held-out source-time reserve with no overlap with main/development; this is not a claim of different original sessions or verified speaker identities. Their short/long/internally-paused tags overlap. A pre-result common shortlist is in the public-safe manifest.

Japanese audio keeps mixed speakers and source pauses; no long-gap compression or synthetic speech is used. FFmpeg loudnorm uses `I=-23`, `TP=-2`, `LRA=7`, dynamic mode, with 48 kHz mono PCM16 output. Sample-clock budget trimming uses boundaries outside aligned words, estimated voice activity and untimed recognition blocks with a 20-ms guard. Source-relative inference is preserved under `.data/japanese/source-references`; final word/sentence/turn timelines and maps are regenerated after cropping and concatenation.

ReazonSpeech k2 v2 generates the actual CPU reference in contiguous 6–8-second inference windows with inference-only padding. It differs from the explicitly named evaluated ASRs; PP4's later CPU-auto choice must still be checked before freezing independence. Fugashi/UniDic defines lexical words. An independent Japanese Wav2Vec2 model performs constrained CTC acoustic-frame alignment; RNNT token timestamp points are not treated as word intervals. Punctuation is insertion-only at estimated acoustic/speaker/window boundaries and does not establish verified Japanese syntax.

**The main reference has 3,166 recognized words, of which 3,133 have acoustic word intervals and 33 remain explicitly untimed because their glyphs are outside the aligner's vocabulary.** Consumers must preserve those words and their uncertainty, not invent times or count them as verified timed reference. The development reference has 427 aligned words. Full local timelines use playback-relative seconds; word IDs are chunk-local, so join with `chunk_id`. Automatic sentence-like units and estimated turns are not human annotations.

Speaker estimates use pyannote segmentation and 3D-Speaker ERes2Net with unknown cluster count. Over-fragmentation is substantial: 44 anonymous clusters in the 710-second held-out reserve do not mean 44 people. Raw estimated overlap, fast changes, word gaps, short turns and filler counts are exploratory proxies, not confirmed Japanese pre-predicate pauses or semantic stress labels.

Actual checks validated emitted formats, durations, hashes, zero separators, split disjointness, sample-exact concatenation, source/playback mappings and insertion-only lexical preservation. Fourteen Japanese unit tests passed. The interim 1,816-second bundle failed the newly unified elapsed-budget check; the final 1,800-second bundle passed after word-safe crop/remapping, without rerunning unchanged inference.

No human listening or content validation was performed. Thirty minutes of suitable mixed conversation is therefore not human-confirmed, and complete word timing is not established. Japanese remains automatic/exploratory and `NOT_RELEASE_CLEARED_LOCAL_ONLY`; it cannot establish overall superiority or be redistributed on the strength of local acceptance.
