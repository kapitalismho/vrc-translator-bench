# Historical corpus preparation

> **Historical reference only.** The AMI/AliMeeting/YODAS2 preparation, six-direction index/check and old control-track builder have been removed from the current package. Commands and completion records below describe the [pre-reset implementation](https://github.com/kapitalismho/vrc-translator-bench/tree/fbab10a0455d91d5419d9673499d25b7ac86c566), not available current commands. Frozen `corpus/` metadata and local audio/reference bytes are preserved. The [final plan §§3–5](benchmark-final-plan.md) selects ASCEND, IngCrowd, FLEURS and the bounded JA/KO T1 reconstruction; [new preparation work](benchmark-implementation-plan.md) must not overwrite or relabel this historical index.

Authority: [issue #2](https://github.com/kapitalismho/vrc-translator-bench/issues/2) and [parent #1](https://github.com/kapitalismho/vrc-translator-bench/issues/1).

## Release boundary

The owner authorized local data preparation and repository commit/push without a PR. The [approved scope amendment](https://github.com/kapitalismho/vrc-translator-bench/issues/2#issuecomment-6282606626) replaces #2's Hugging Face publication criterion with local audio, references, playback timelines, checksums, and asset-level rights/unresolved-permission records. All other preparation and practical verification obligations remain. Local outputs are not a public dataset release; future redistribution still requires authorization, a destination, and rights clearance.

Audio, downloaded corpora, model weights and environments live under ignored `.data/`. Code uses MIT; corpus assets, transcripts and timelines retain their source-specific terms. Do not apply the code license to data. Japanese derived speech text and timelines also remain in `.data/` while original-video attribution is unresolved.

- AMI: [official license](https://groups.inf.ed.ac.uk/ami/corpus/license.shtml), CC BY 4.0. Credit AMI Project and retain original notices. Human transcription/manual dialogue acts do not make the automatically forced-aligned word times human-verified.
- AliMeeting: [OpenSLR 119](https://www.openslr.org/119/), CC BY-SA 4.0. Credit Alibaba Group and supplied authors. Chinese derivative audio and timelines retain ShareAlike; a mirror's conflicting license tag cannot override the original terms.
- YODAS2: [dataset card](https://huggingface.co/datasets/espnet/yodas2), declared CC BY 3.0. Its IDs are not original YouTube IDs. The [maintainer declined to publish original IDs](https://huggingface.co/datasets/espnet/yodas2/discussions/2). Dataset-level terms alone do not supply the required video-specific attribution and provenance. No inspected Japanese candidate is cleared for redistribution.
- MUSAN: use each asset's original terms, not only the corpus-wide label. The selected SoundBible files are public-domain recordings with their creators and original URLs retained. The small pinned mirror has not been byte-compared against the complete official MUSAN archive.

## Local recovery revision

The owner approved **`issue-2-local-v2`** on 2026-10-21 after deletion of the ignored local artifacts. The original `issue-2-local-v1` metadata remains in Git at `342b13c`; `.data/japanese/accepted-local-preparation.json` also retains the original Japanese metadata. This is a new local reference revision, not byte-identical recovery of the old reference, a public release, or the main-run protocol freeze.

All indexed audio was reconstructed from the original source bytes and accepted selection/rendering records without changing its SHA-256. English and Chinese accepted references remain unchanged. Japanese development and all twenty isolated references reproduce their original hashes, but the main timeline does not:

| Japanese main timeline | SHA-256 |
|---|---|
| Original v1 | `672afdf52eeff6407db0859ca81102a63fe295c1524e1435301905f828453548` |
| Accepted regenerated v2 | `5d943315650470ef46fde720df1811849d77e13bc72f28891c13e6368144c106` |

The regenerated reference uses the same pinned source/model payloads and actual CPU inference. Its formerly unsupported main words use thirty raw-Qwen alignments and three pronunciation-CTC alignments, versus twenty-nine and four in v1. Replaying the documented historical fallback choice also failed to recover the original timeline hash; that diagnostic candidate was not adopted. Complete original prediction outputs are unavailable, so do not claim that the remaining differences are only metadata or that the two references are semantically identical.

Keep prior results bound to their original reference hashes. New runs must record v2 and its current hashes; do not silently rescore old results against it. The original `.data` run ledgers, raw captures and canonical metric caches were not recovered. Committed public-safe pilot derivatives remain historical evidence, not resumable run directories. Local recovery reports and retained failed attempts are under `.data/english`, `.data/chinese` and `.data/japanese`.

## First D1/D3 batch inputs

Issue #8's [input assembly record](../profiles/evidence/issue8/input-assembly.json)
identifies local resumable slices and the pre-result common-example selection.
This is input preparation, not a protocol freeze, measured baseline or public
dataset release.

- D1: six 300-second slices of the unchanged 1,800-second main bundle.
- D3: nine 200-second slices of the unchanged 1,800-second main bundle.
- Streaming comparison of the persisted slices against each original bundle
  confirmed byte-identical concatenated PCM and complete reference coverage.
  All ten English and sixteen Chinese separator seconds remain. The English
  1,500-second boundary divides a separator, not a lexical reference.
- Original zero-width Chinese alignment estimates remain uncertain; their
  durations are not invented to populate speech intervals.
- Common examples are the whole pre-existing shortlisted components:
  D1 `general-01`, `stress-01`, `stress-02`; D3 `zh-general-01`,
  `zh-general-02`, `zh-stress-03`. Selection preceded main-result inspection;
  source-specific attribution and redistribution terms still apply.

The existing twenty isolated inputs per direction, D1 fixed five-minute repeat,
three-minute nonspeech track, source-matched development checks and measured
calibration remain separately identified. The [observation-order record](../profiles/evidence/issue8/observation-order.json)
specifies their proposed execution order and observation tails; fresh application
admission and the single pre-result freeze remain pending.

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

No human listening was performed. Under the owner-delegated practical method below, actual excerpt payloads, digital gaps, original creator descriptions and AMI human transcripts were inspected. These support the intended construction, but do not independently certify absence of incidental speech or perceived background presentation.

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
.data/japanese/venv/Scripts/python.exe -m pip install --cache-dir .data/japanese/pip-cache numpy==2.5.4 soundfile==0.14.0 sherpa-onnx==1.13.8 transformers==5.20.2 fugashi==1.5.2 unidic-lite==1.0.8 pyopenjtalk-plus==0.4.1.post9 SudachiPy==0.7.0 SudachiDict-core==20261015
.data/japanese/venv/Scripts/python.exe -m pip install --cache-dir .data/japanese/pip-cache torch==2.14.1+cpu --index-url https://download.pytorch.org/whl/cpu
.data/japanese/venv/Scripts/python.exe tools/prepare_japanese.py acquire --with-alignment
.data/japanese/venv/Scripts/python.exe tools/prepare_japanese.py extract Yr7rGfescvQ YvBXxjwqeTy YIIDry4AVKA
.data/japanese/venv/Scripts/python.exe tools/prepare_japanese.py select
.data/japanese/venv/Scripts/python.exe tools/prepare_japanese.py render
.data/japanese/venv/Scripts/python.exe tools/prepare_japanese.py reference --threads 2
.data/japanese/venv/Scripts/python.exe -B -X utf8 tools/prepare_japanese.py complete-alignment --aligner-python .data/chinese/venv/Scripts/python.exe --model-dir .data/chinese/models/models--Qwen--Qwen3-ForcedAligner-0.6B/snapshots/c7cbfc2048c462b0d63a45797104fc9db3ad62b7 --pronunciation-python .data/japanese/venv/Scripts/python.exe --threads 2
.data/japanese/venv/Scripts/python.exe tools/prepare_japanese.py playback-references
.data/japanese/venv/Scripts/python.exe tools/prepare_japanese.py heldout
.data/japanese/venv/Scripts/python.exe tools/prepare_japanese.py check
.data/japanese/venv/Scripts/python.exe tools/prepare_japanese.py export-metadata
```

The exercised covering-alignment stage reuses the earlier Chinese Qwen environment/weights read-only with `-B`; all new Japanese predictions/caches stay in `.data/japanese`. Qwen uses Transformers 4.57.6, so do not install it over the Japanese Transformers 5.20.2 environment. For standalone Japanese preparation, the following separately supplied-path recipe is documented but has **not** been exercised as a second clean install:

```powershell
py -3.12 -m venv .data/japanese/aligner-venv
.data/japanese/aligner-venv/Scripts/python.exe -m pip install --cache-dir .data/japanese/pip-cache torch==2.14.1+cpu --index-url https://download.pytorch.org/whl/cpu
.data/japanese/aligner-venv/Scripts/python.exe -m pip install --cache-dir .data/japanese/pip-cache qwen-asr==0.0.6 transformers==4.57.6 accelerate==1.12.0 huggingface-hub==0.36.2 qwen-omni-utils==0.0.9 numpy==2.5.4 soundfile==0.14.0
$env:HF_HOME = "$PWD/.data/japanese/hf-download-cache"; $env:HF_HUB_DISABLE_IMPLICIT_TOKEN = "1"; $env:HF_HUB_DISABLE_TELEMETRY = "1"
.data/japanese/aligner-venv/Scripts/hf.exe download Qwen/Qwen3-ForcedAligner-0.6B model.safetensors config.json preprocessor_config.json tokenizer_config.json vocab.json merges.txt chat_template.json generation_config.json README.md --revision c7cbfc2048c462b0d63a45797104fc9db3ad62b7 --cache-dir .data/japanese/hf-download-cache --local-dir .data/japanese/models/covering-alignment
.data/japanese/venv/Scripts/python.exe -B -X utf8 tools/prepare_japanese.py complete-alignment --aligner-python .data/japanese/aligner-venv/Scripts/python.exe --model-dir .data/japanese/models/covering-alignment --pronunciation-python .data/japanese/venv/Scripts/python.exe --threads 2
```

Then run `playback-references`, `heldout`, `check`, and `export-metadata` as above. Covering Qwen weights add 1.836 GB. Dictionary frontend packages and bundled dictionary file hashes are pinned; external dictionary overrides or unreproduced cached readings fail explicitly. The observed optional-ONNX/Nani warning remains recorded. Effective Nani-disabled behavior is explicit, not a claim of contextually correct names/readings.

The pinned YODAS2 revision is `c9674490249665d658f527e2684848377108d82c`. Acquisition downloads one 1.406 GB Japanese shard, not the entire configuration. Reazon ASR weights/tokens total about 169 MB, but the acoustic aligner additionally needs a 1.272 GB Wav2Vec2 checkpoint and the speaker models have separate payloads. This is not a 169 MB total pipeline. The exercised Python was 3.12.10; FFmpeg was 8.0.1. Public dependency installation initially used the shared pip cache; it was left untouched. Corpus and model payloads are under `.data/japanese`.

Fixed seed `20261020` selects general candidates from the recorded pool. Source content is caption-assisted bonsai discussion and exercise-response material across three pseudonymous original videos. No casual-chat candidate was established in the inspected shard; caption-derived general tags are entirely work/discussion, while the actual casual-chat fraction is unknown. Uploaded/manual captions are supplementary evidence, never replacements for ASR words.

D4/D6 share `.data/japanese/playback/ja-main.wav`: exactly 1,800 seconds, nine chunks, general 1,188 source seconds plus 12 assigned gap seconds and stress 596 source seconds plus four gap seconds. Separate development is 300 seconds. Twenty real D6 isolated crops use a held-out source-time reserve with no overlap with main/development; this is not a claim of different original sessions or verified speaker identities. Their short/long/internally-paused tags overlap. A pre-result common shortlist is in the public-safe manifest.

Japanese audio keeps mixed speakers and source pauses; no long-gap compression or synthetic speech is used. FFmpeg loudnorm uses `I=-23`, `TP=-2`, `LRA=7`, dynamic mode, with 48 kHz mono PCM16 output. Sample-clock budget trimming uses boundaries outside aligned words, estimated voice activity and untimed recognition blocks with a 20-ms guard. Source-relative inference is preserved under `.data/japanese/source-references`; final word/sentence/turn timelines and maps are regenerated after cropping and concatenation.

ReazonSpeech k2 v2 generates the actual CPU reference in contiguous 6–8-second inference windows with inference-only padding. It differs from the explicitly named evaluated ASRs; PP4's later CPU-auto choice must still be checked before freezing independence. Fugashi/UniDic defines lexical words. An independent Japanese Wav2Vec2 model performs constrained CTC acoustic-frame alignment; RNNT token timestamp points are not treated as word intervals. Punctuation is insertion-only at estimated acoustic/speaker/window boundaries and does not establish verified Japanese syntax.

**All 3,166 main words and 427 development words have finite acoustic timing estimates.** The main has 656 automatic sentence-like units; development has 125. In the accepted regenerated v2 reference, the 33 formerly untimed main words were covered without changing regenerated Reazon text or previously supported intervals: 30 by raw dedicated Qwen forced alignment and three by genuine CTC alignment of dictionary pronunciations. Upstream timestamp interpolation is disabled. Pronunciation paths have very low uncalibrated acoustic scores; name readings and overlapping/coincident raw estimates remain uncertain. Numeric completeness is not timing accuracy. Full local timelines use playback-relative seconds; join word IDs with `chunk_id`. The v1 preparation and its 29/4 backend counts remain historical evidence, not a claim that all original reference bytes were recovered.

Speaker estimates use pyannote segmentation and 3D-Speaker ERes2Net with unknown cluster count. Over-fragmentation is substantial: 44 anonymous clusters in the 710-second held-out reserve do not mean 44 people. Raw estimated overlap, fast changes, word gaps, short turns and filler counts are exploratory proxies, not confirmed Japanese pre-predicate pauses or semantic stress labels.

The original v1 preparation validated emitted formats, durations, hashes, zero separators, split disjointness, sample-exact concatenation, source/playback mappings and insertion-only lexical preservation. Its independent review corrected isolated selection to reject either leading or trailing word intersections; its recorded forty Japanese unit tests and integrated 78 tests/29 subtests are historical results, not reruns for v2. The v2 actual artifact check again covers 42 timing artifacts with no missing bounds and confirms that all 20 isolated clips preserve 207 intersecting reserve words with zero boundary crossings. Raw-model/source-hash audits establish the regenerated acoustic basis, not equality with unavailable original predictions. Current recovery attempts and the rejected historical-path replay are retained locally; the original local failure bundle was lost.

No human listening or independent transcription validation was performed. The owner-delegated source-assisted assessment below supports provisional conversational/discussion inputs while retaining concrete ASR/caption disagreements and perceptual unknowns. Japanese remains automatic/exploratory and `NOT_RELEASE_CLEARED_LOCAL_ONLY`; it cannot establish overall superiority or be redistributed on the strength of local acceptance.

## Owner-delegated practical assessment

After receiving ten actual WAV excerpts and timed references, the owner stated that they could not judge by listening and delegated appropriate assessment to the assistant. The [recorded method decision](https://github.com/kapitalismho/vrc-translator-bench/issues/2#issuecomment-6283330068) uses a small original-source-content, recognized-output and waveform/timeline inspection, **not human listening**. It does not waive complete timing or intact isolated utterances.

`corpus/practical-assessment.json` records the 145-second sample scope, source identities, hashes, positive evidence and counterevidence. Every excerpt matched its actual parent PCM crop. Original AMI XML and AliMeeting near/far human annotations establish the sampled meeting exchanges and filler/backchannel content. Japanese supplementary captions and actual ASR outputs support instructional/discussion topics, questions, responses and handoffs, while also revealing lexical/homophone disagreements and missed short reactions. Captions were not substituted for ASR text.

The Chinese backchannel sample is quiet, with measured response-window energy above adjacent gaps; later playback-chain audibility remains unobserved. Nonspeech source descriptions and signal placement support the construction, not an auditory guarantee that incidental speech is absent. No source-type label, successful alignment, waveform identity or fragmented speaker clustering proves perceptual intelligibility, no music/TTS, or error-free reference content.

The Director accepts this bounded practical method for local preparation under the owner's delegation and retains those limitations. Timing/word-boundary defects are repaired and independently verified separately. Main-run readiness, public release rights and human reference accuracy are not inferred from this assessment.
