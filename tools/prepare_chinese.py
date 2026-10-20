from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import wave

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '.data' / 'chinese'
META = ROOT / 'corpus' / 'chinese'
ARCHIVE_URL = 'https://speech-lab-share-data.oss-cn-shanghai.aliyuncs.com/AliMeeting/openlr/Eval_Ali.tar.gz'
ARCHIVE_BYTES = 3673718355
ARCHIVE_SHA256 = 'dc47343b2474b5ebcf458927e878155f6ddeb59c85e685b3645c32a1f9578d92'
MODEL = 'Qwen/Qwen3-ForcedAligner-0.6B'
MODEL_REVISION = 'c7cbfc2048c462b0d63a45797104fc9db3ad62b7'
CTC_MODELS = (
    ('wbbbbb/wav2vec2-large-chinese-zh-cn', 'b654b5f3df69725df32808de454a1b865c829e4c'),
    ('jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn', '99ccb2737be22b8bb50dcfcc39ad4d567fb90cfd'),
)
SEED = 20261020
RATE = 48000
LICENSE = 'CC-BY-SA-4.0'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def relative(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def run(args):
    return subprocess.run([str(x) for x in args], check=True, capture_output=True).stdout


def acquire(_args):
    path = DATA / 'downloads' / 'Eval_Ali.tar.gz'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size != ARCHIVE_BYTES:
        offset = path.stat().st_size if path.exists() else 0
        request = urllib.request.Request(ARCHIVE_URL, headers={'Range': f'bytes={offset}-'} if offset else {})
        with urllib.request.urlopen(request, timeout=120) as response:
            if offset and response.status != 206:
                raise RuntimeError('Server did not honor resume; existing partial archive retained.')
            with path.open('ab' if offset else 'wb') as out:
                shutil.copyfileobj(response, out, 4 * 1024 * 1024)
    if path.stat().st_size != ARCHIVE_BYTES:
        raise RuntimeError(f'Archive size mismatch: {path.stat().st_size}; expected {ARCHIVE_BYTES}')
    digest = sha256(path)
    if digest != ARCHIVE_SHA256:
        raise RuntimeError(f'Official archive differs from locally frozen source SHA-256: {digest}')
    source = {'url': ARCHIVE_URL, 'bytes': path.stat().st_size, 'sha256': digest,
              'sha256_authority': 'Locally computed; upstream publishes no SHA-256 at catalog.',
              'catalog': 'https://www.openslr.org/119/', 'license': LICENSE, 'split': 'Eval'}
    save(META / 'archive.json', source)
    entries, notices = [], []
    with tarfile.open(path, mode='r|gz') as archive:
        for member in archive:
            entries.append({'name': member.name, 'bytes': member.size})
            if not member.isfile():
                continue
            name = Path(member.name)
            if name.is_absolute() or '..' in name.parts:
                raise RuntimeError(f'Unsafe archive path: {name}')
            notice = bool(re.search(r'(?i)(license|copying|notice|readme|citation)', name.name))
            wanted = ('_near/' in member.name and name.suffix.lower() in {'.wav', '.textgrid'}) or ('_far/' in member.name and name.suffix.lower() == '.textgrid') or notice
            if not wanted:
                continue
            dest = DATA / 'source' / name
            if not dest.exists() or dest.stat().st_size != member.size:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as inp, dest.open('wb') as out:
                    shutil.copyfileobj(inp, out)
            if notice:
                notices.append({'path': relative(dest), 'sha256': sha256(dest),
                                'text': dest.read_text(encoding='utf-8', errors='replace') if member.size < 100000 else None})
    save(META / 'archive-inventory.json', {'entries': entries, 'embedded_notices': notices,
                                         'notice_search': 'Case-insensitive license/copying/notice/readme/citation filenames across entire original archive.'})
    inventory(None)


def parse_textgrid(path, speaker=None):
    raw = Path(path).read_bytes()
    for encoding in ('utf-8-sig', 'utf-16', 'gb18030'):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeError:
            continue
    else:
        raise ValueError(f'Cannot decode {path}')
    records = []
    for tier in re.split(r'(?m)^\s*item\s*\[\d+\]:', text)[1:]:
        match = re.search(r'name\s*=\s*"((?:[^"]|"")*)"', tier)
        if not match:
            continue
        label = speaker or match.group(1).replace('""', '"').split('_')[-1]
        for number, start, end, mark in re.findall(r'intervals\s*\[(\d+)\]:\s*xmin\s*=\s*([\d.eE+-]+)\s*xmax\s*=\s*([\d.eE+-]+)\s*text\s*=\s*"((?:[^"]|"")*)"', tier):
            mark = mark.replace('""', '"').strip()
            if mark:
                records.append({'id': f'{Path(path).stem}:{label}:{number}', 'speaker': label,
                                'start': float(start), 'end': float(end), 'text': mark})
    return sorted(records, key=lambda r: (r['start'], r['end'], r['speaker']))


def inventory(_args):
    tracks = []
    for audio in sorted((DATA / 'source').rglob('*.wav')):
        if '_near' not in audio.as_posix():
            continue
        session = '_'.join(audio.stem.split('_')[:2])
        speaker = audio.stem.split('_')[-1]
        grid = audio.parent.parent / 'textgrid_dir' / (audio.stem + '.TextGrid')
        far = list((DATA / 'source').rglob(session + '.TextGrid'))
        far = [p for p in far if '_far/' in p.as_posix()]
        if not grid.exists() or len(far) != 1:
            raise RuntimeError(f'Missing unambiguous annotations for {audio}')
        with wave.open(str(audio), 'rb') as stream:
            if stream.getnchannels() != 1 or stream.getsampwidth() != 2:
                raise ValueError(f'Expected actual mono PCM16 headset: {audio}')
            seconds = stream.getnframes() / stream.getframerate()
            sample_rate = stream.getframerate()
        segments = parse_textgrid(grid, speaker)
        tracks.append({'id': audio.stem, 'session': session, 'speaker': speaker, 'split': 'Eval',
                       'audio': relative(audio), 'textgrid': relative(grid), 'context_textgrid': relative(far[0]),
                       'channel_zero_based': 0, 'input_mode': 'selected-participant-headset',
                       'duration': seconds, 'sample_rate': sample_rate,
                       'sha256': sha256(audio), 'textgrid_sha256': sha256(grid),
                       'context_textgrid_sha256': sha256(far[0]),
                       'archive_member': audio.relative_to(DATA / 'source').as_posix(),
                       'source_url': ARCHIVE_URL, 'license': LICENSE, 'segments': segments})
    if not tracks:
        raise RuntimeError('No official near/headset WAVs extracted. Run acquire first.')
    save(META / 'inventory.json', {'tracks': tracks})
    print(json.dumps([{'id': t['id'], 'segments': len(t['segments']),
                       'speech_seconds': round(sum(s['end'] - s['start'] for s in t['segments']), 2),
                       'opening_text': ''.join(s['text'] for s in t['segments'][:8])} for t in tracks], ensure_ascii=False, indent=2))


def compression_cuts(target, context, start, end):
    cuts = []
    occupied = sorted((s['start'], s['end']) for s in target)
    merged = []
    for a, b in occupied:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    for left, right in zip(merged, merged[1:]):
        a, b = max(start, left[1]), min(end, right[0])
        others = [(max(a, s['start']), min(b, s['end'])) for s in context
                  if s['speaker'] != target[0]['speaker'] and s['start'] < b and s['end'] > a]
        others = [(x, y) for x, y in others if x < y]
        if others:
            x, y = min(x for x, _ in others), max(y for _, y in others)
            if y - x > 3.0:
                cuts.append({'start': x + 1.5, 'end': y - 1.5, 'other_occupied_span': [x, y],
                             'reason': 'Target silent; other-speaker span reduced to 3s; target-silent shoulders retained.'})
    return cuts


def retained_map(start, end, cuts):
    pieces, cursor, playback = [], start, 0.0
    for cut in cuts + [{'start': end, 'end': end}]:
        a, b = max(start, cut['start']), min(end, cut['end'])
        if a > cursor:
            length = a - cursor
            pieces.append({'source_start': cursor, 'source_end': a,
                           'playback_start': playback, 'playback_end': playback + length})
            playback += length
        cursor = max(cursor, b)
    return pieces


def mapped_intervals(start, end, pieces, offset=0.0):
    if start == end:
        for p in pieces:
            if p['source_start'] <= start <= p['source_end']:
                point = offset + p['playback_start'] + start - p['source_start']
                return [[point, point]]
        return []
    spans = []
    for p in pieces:
        a, b = max(start, p['source_start']), min(end, p['source_end'])
        if a < b:
            spans.append([offset + p['playback_start'] + a - p['source_start'],
                          offset + p['playback_start'] + b - p['source_start']])
    return spans


def endpoint(start, duration, cuts, maximum):
    remaining, cursor = duration, start
    for cut in cuts + [{'start': maximum, 'end': maximum}]:
        length = cut['start'] - cursor
        if remaining <= length:
            return cursor + remaining
        remaining -= length
        cursor = cut['end']
    return None


def stress_features(segments):
    texts = [s['text'] for s in segments]
    return {'backchannel': sum(bool(re.fullmatch(r'[嗯哦噢啊好对是行哎诶呃唔哈]+[，。！？!?、]*', t)) for t in texts),
            'trailing_filler': sum(bool(re.search(r'[嗯呃啊呀呢吧嘛哦噢][，。！？!?、]*$', t)) for t in texts),
            'multiple_sentences': sum(len(re.findall(r'[。！？!?]', t)) >= 2 for t in texts)}


def candidates(track, desired):
    target = track['segments']
    context = parse_textgrid(ROOT / track['context_textgrid'])
    cuts = compression_cuts(target, context, 0, track['duration'])
    result = []
    for segment in target:
        start = max(0, segment['start'] - 0.25)
        if any(s['start'] < start < s['end'] for s in target):
            continue
        end = endpoint(start, desired, [c for c in cuts if c['start'] >= start], track['duration'])
        if end is None or any(s['start'] < end < s['end'] for s in target):
            continue
        included = [s for s in target if s['start'] >= start and s['end'] <= end]
        if sum(s['end'] - s['start'] for s in included) < 0.15 * desired:
            continue
        actual_cuts = compression_cuts(target, context, start, end)
        pieces = retained_map(start, end, actual_cuts)
        if not pieces or abs(pieces[-1]['playback_end'] - desired) > 0.00001:
            continue
        result.append({'source_start': start, 'source_end': end, 'duration': desired,
                       'mapping': pieces, 'removed_gaps': actual_cuts, 'stress_features': stress_features(included)})
    return result


def select(args):
    tracks = load(META / 'inventory.json')['tracks']
    curation = load(args.curation)
    rng = random.Random(SEED)
    by_session = {}
    for track in tracks:
        by_session.setdefault(track['session'], []).append(track)
    roles = curation['sessions']
    chosen, used = [], []

    def choose(session, desired, category, deliberate=False):
        options = []
        for track in by_session[session]:
            for candidate in candidates(track, desired):
                if any(old['session'] == session and candidate['source_start'] < old['source_end'] and candidate['source_end'] > old['source_start'] for old in used):
                    continue
                options.append((track, candidate))
        if not options:
            raise RuntimeError(f'No whole-utterance {desired}s candidate for {session}/{category}.')
        rng.shuffle(options)
        if deliberate:
            options.sort(key=lambda x: sum(x[1]['stress_features'].values()), reverse=True)
        track, candidate = options[0]
        item = {**{k: v for k, v in track.items() if k != 'segments'}, **candidate,
                'chunk_id': f'zh-{category}-{1 + sum(c["category"] == category for c in chosen):02}',
                'category': category, 'topic': roles[session]['topic'],
                'casual_chat': roles[session]['casual_chat'], 'tags': roles[session]['tags'],
                'selection': 'deliberate-text-pattern-stress' if deliberate else 'fixed-seed-eligible-pool'}
        chosen.append(item)
        used.append(item)

    general = [s for s, row in roles.items() if row['role'] == 'main']
    general.sort(key=lambda s: (not roles[s]['casual_chat'], 'everyday-topic' not in roles[s]['tags'], s))
    if len(general) != 6:
        raise ValueError('This frozen schedule requires six main sessions and separate dev/heldout sessions.')
    for session in general:
        choose(session, 198, 'general')
    stress_sessions = sorted(general, key=lambda s: -max(sum(stress_features(t['segments']).values()) for t in by_session[s]))
    for session, duration in zip(stress_sessions, (198, 198, 200)):
        choose(session, duration, 'stress', True)
    dev = [s for s, row in roles.items() if row['role'] == 'dev']
    if len(dev) != 1:
        raise ValueError('Exactly one reserved development session required.')
    choose(dev[0], 149, 'dev')
    choose(dev[0], 149, 'dev')
    heldout = [s for s, row in roles.items() if row['role'] == 'heldout']
    if len(heldout) != 1:
        raise ValueError('Exactly one reserved isolated-response session required.')
    heldout_candidates = []
    for track in by_session[heldout[0]]:
        available = [s for s in track['segments'] if lexical(s['text']) and s['end'] - s['start'] <= 20]
        rng.shuffle(available)
        for segment in available[:35]:
            heldout_candidates.append({'track_id': track['id'], 'segment': segment})
    save(META / 'selection.json', {'seed': SEED, 'curation': curation, 'chunks': chosen,
                                  'heldout_candidates': heldout_candidates,
                                  'eligibility': ['Official Eval participant headset only; complete human utterances at boundaries.',
                                                  '2-5min transformed chunks; target annotated speech at least 15%.',
                                                  'Session-disjoint main/development/isolated; no main source interval reused.',
                                                  'General prioritizes curation-tagged casual sessions; fixed Python random seed.',
                                                  'Stress separate, ranked by annotated backchannels/trailing fillers/multi-sentence speech.',
                                                  'No result-dependent clip choice.'],
                                  'directions': ['D3', 'D5'], 'same_audio': True})
    print(f'Selected {len(chosen)} chunks and {len(heldout_candidates)} heldout alignment candidates.')


def lexical(text):
    return ''.join(c for c in text if c.isalpha() or c.isdigit())


def predicted_characters(items, text, segment_start, segment_end):
    expected = lexical(text)
    if ''.join(item.text for item in items) != expected:
        raise ValueError('Forced aligner changed or dropped human lexical characters.')
    chars = []
    for item in items:
        start, end = float(item.start_time), float(item.end_time)
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start <= end <= segment_end - segment_start + 0.02):
            raise ValueError(f'Invalid raw model timing for {item.text}: {start}-{end}; refusing interpolation.')
        chars.append({'text': item.text, 'start': segment_start + start,
                      'end': min(segment_end, segment_start + end),
                      'timing_method': 'Raw dedicated forced-aligner timestamp prediction; no interpolation.'})
    return chars


def ctc_path(log_probs, tokens, blank):
    import numpy as np
    labels = np.full(2 * len(tokens) + 1, blank, dtype=np.int64)
    labels[1::2] = tokens
    width = len(labels)
    previous = np.full(width, -np.inf)
    previous[0] = 0
    back = np.zeros((len(log_probs), width), dtype=np.uint8)
    skip_ok = np.zeros(width, dtype=bool)
    skip_ok[2:] = (labels[2:] != blank) & (labels[2:] != labels[:-2])
    for frame, emissions in enumerate(log_probs):
        choices = np.stack((previous, np.concatenate(([-np.inf], previous[:-1])),
                            np.concatenate(([-np.inf, -np.inf], previous[:-2]))))
        choices[2, ~skip_ok] = -np.inf
        steps = np.argmax(choices, axis=0)
        back[frame] = steps
        previous = choices[steps, np.arange(width)] + emissions[labels]
    state = width - 1 if previous[-1] > previous[-2] else width - 2
    if not np.isfinite(previous[state]):
        raise ValueError('No monotone CTC path; refusing invented timings.')
    frames = [[] for _ in tokens]
    for frame in range(len(log_probs) - 1, -1, -1):
        if state % 2:
            frames[state // 2].append(frame)
        state -= int(back[frame, state])
    if any(not f for f in frames):
        raise ValueError('CTC path omitted a human token.')
    return [(min(f), max(f) + 1) for f in frames]


def repair_alignment(failures, requests, cache):
    import numpy as np
    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
    processors, models, unresolved, repaired = {}, {}, [], []
    for failure in failures:
        key = failure['id']
        track, segment = requests[key]
        normalized = lexical(segment['text']).upper()
        try:
            selected = None
            for model_id, revision in CTC_MODELS:
                if model_id not in processors:
                    processors[model_id] = Wav2Vec2Processor.from_pretrained(model_id, revision=revision, cache_dir=DATA / 'models')
                processor = processors[model_id]
                vocab = processor.tokenizer.get_vocab()
                if normalized and all(c in vocab for c in normalized):
                    selected = (model_id, revision, processor, vocab)
                    break
            if selected is None:
                raise ValueError('No CTC model covers all original lexical characters.')
            model_id, revision, processor, vocab = selected
            if model_id not in models:
                model, info = Wav2Vec2ForCTC.from_pretrained(model_id, revision=revision, cache_dir=DATA / 'models', output_loading_info=True)
                if info['missing_keys'] or info['mismatched_keys']:
                    raise ValueError(f'CTC model has uninitialized/mismatched parameters: {info}')
                models[model_id] = model.eval()
            duration = segment['end'] - segment['start']
            pcm = run(['ffmpeg', '-v', 'error', '-ss', segment['start'], '-i', ROOT / track['audio'],
                       '-t', duration, '-ac', '1', '-ar', '16000', '-f', 'f32le', 'pipe:1'])
            samples = np.frombuffer(pcm, dtype='<f4').copy()
            inputs = processor(samples, sampling_rate=16000, return_tensors='pt')
            with torch.inference_mode():
                log_probs = models[model_id](**inputs).logits[0].log_softmax(-1).numpy()
            positions = ctc_path(log_probs, [vocab[c] for c in normalized], processor.tokenizer.pad_token_id)
            chars = [{'text': c, 'start': segment['start'] + a * 0.02,
                      'end': min(segment['end'], segment['start'] + b * 0.02),
                      'timing_method': 'Monotone CTC Viterbi path against unchanged human characters; 20ms frames.'}
                     for c, (a, b) in zip(lexical(segment['text']), positions)]
            fingerprint = hashlib.sha256(json.dumps([MODEL_REVISION, track['sha256'], segment], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            save(cache / (hashlib.sha256(key.encode()).hexdigest() + '.json'),
                 {'id': key, 'fingerprint': fingerprint, 'model': model_id, 'revision': revision,
                  'primary_revision': MODEL_REVISION, 'primary_rejection': failure,
                  'method': 'Vocabulary-covered monotone CTC forced alignment after rejecting invalid raw primary timestamp predictions.',
                  'text': segment['text'], 'chars': chars, 'timing_uncertainty': 'Automatic CTC boundaries; not human timing verification.'})
            repaired.append({'id': key, 'model': model_id, 'revision': revision})
        except (ValueError, RuntimeError) as error:
            unresolved.append({**failure, 'ctc_repair_failure': str(error)})
    return repaired, unresolved


def alignment_requests(selection, tracks):
    requests = {}
    for chunk in selection['chunks']:
        track = tracks[chunk['id']]
        for segment in track['segments']:
            if segment['start'] >= chunk['source_start'] and segment['end'] <= chunk['source_end']:
                requests[segment['id']] = (track, segment)
    for candidate in selection['heldout_candidates']:
        requests[candidate['segment']['id']] = (tracks[candidate['track_id']], candidate['segment'])
    return requests


def align(args):
    os.environ['HF_HOME'] = str(DATA / 'models' / 'huggingface')
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    os.environ['DO_NOT_TRACK'] = '1'
    os.environ['NUMBA_CACHE_DIR'] = str(DATA / 'cache' / 'numba')
    os.environ['TEMP'] = str(DATA / 'cache')
    (DATA / 'cache').mkdir(parents=True, exist_ok=True)
    import numpy as np
    import torch
    from huggingface_hub import snapshot_download
    from qwen_asr import Qwen3ForcedAligner
    torch.set_num_threads(args.threads)
    snapshot = snapshot_download(MODEL, revision=MODEL_REVISION, cache_dir=DATA / 'models')
    model = Qwen3ForcedAligner.from_pretrained(snapshot, dtype=torch.float32, device_map='cpu', attn_implementation='eager')
    model.aligner_processor.fix_timestamp = lambda predictions: predictions.tolist()
    tracks = {t['id']: t for t in load(META / 'inventory.json')['tracks']}
    requests = alignment_requests(load(META / 'selection.json'), tracks)
    cache = DATA / 'alignment'
    cache.mkdir(parents=True, exist_ok=True)
    failures = []
    count = 0
    for key, (track, segment) in requests.items():
        dest = cache / (hashlib.sha256(key.encode()).hexdigest() + '.json')
        fingerprint = hashlib.sha256(json.dumps([MODEL_REVISION, track['sha256'], segment], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if dest.exists() and load(dest).get('fingerprint') == fingerprint:
            continue
        text = segment['text']
        duration = segment['end'] - segment['start']
        if not lexical(text) or duration > 60:
            failures.append({'id': key, 'text': text, 'reason': 'No lexical tokens or human segment exceeds 60s.'})
            continue
        pcm = run(['ffmpeg', '-v', 'error', '-ss', segment['start'], '-i', ROOT / track['audio'], '-t', duration,
                   '-ac', '1', '-ar', '16000', '-f', 'f32le', 'pipe:1'])
        samples = np.frombuffer(pcm, dtype='<f4').copy()
        try:
            with torch.inference_mode():
                result = model.align(audio=(samples, 16000), text=' '.join(lexical(text)), language='Chinese')[0]
            chars = predicted_characters(list(result), text, segment['start'], segment['end'])
            save(dest, {'id': key, 'fingerprint': fingerprint, 'model': MODEL, 'revision': MODEL_REVISION,
                        'method': 'CPU dedicated forced alignment; every immutable human lexical character is a requested unit. Upstream timestamp repair/interpolation disabled.',
                        'text': text, 'chars': chars,
                        'timing_uncertainty': 'Automatic raw word-boundary predictions, not human timing verification. Zero-length/overlapping estimates remain explicitly uncertain.'})
            count += 1
            if count % 10 == 0:
                print(f'Aligned {count}; current {key}', flush=True)
        except (ValueError, RuntimeError) as error:
            failures.append({'id': key, 'text': text, 'reason': str(error)})
    primary_failures = failures
    del model
    repaired, failures = repair_alignment(primary_failures, requests, cache) if primary_failures else ([], [])
    retained_rejections = {item['id']: item for item in primary_failures}
    retained_repairs = {item['id']: item for item in repaired}
    for key in requests:
        cached = cache / (hashlib.sha256(key.encode()).hexdigest() + '.json')
        if cached.exists():
            record = load(cached)
            if record.get('primary_rejection'):
                retained_rejections[key] = record['primary_rejection']
                retained_repairs[key] = {'id': key, 'model': record['model'], 'revision': record['revision']}
    save(META / 'alignment-report.json', {'model': MODEL, 'revision': MODEL_REVISION, 'requested': len(requests),
                                         'newly_aligned_primary': count, 'primary_failures': list(retained_rejections.values()),
                                         'ctc_repairs': list(retained_repairs.values()), 'failures': failures,
                                         'timestamp_repair': 'Disabled upstream fix_timestamp: invalid predictions receive genuine vocabulary-covered CTC alignment, never interpolation.'})
    if failures:
        raise RuntimeError(f'{len(failures)} alignment failures recorded; build refuses missing target word timings.')


def read_alignment(segment):
    path = DATA / 'alignment' / (hashlib.sha256(segment['id'].encode()).hexdigest() + '.json')
    if not path.exists():
        raise RuntimeError(f'Missing forced alignment: {segment["id"]}; run align.')
    result = load(path)
    if result['text'] != segment['text'] or result.get('primary_revision', result['revision']) != MODEL_REVISION:
        raise RuntimeError(f'Stale forced alignment: {segment["id"]}')
    return result['chars']


def units(segment, chars):
    import jieba
    jieba.dt.tmp_dir = str(DATA / 'cache')
    (DATA / 'cache').mkdir(parents=True, exist_ok=True)
    text = segment['text']
    restored = text if re.search(r'[。！？!?；;]$', text) else text + '。'
    words, sentences = [], []
    index = 0
    for token in jieba.cut(text, HMM=False):
        clean = lexical(token)
        if not clean:
            continue
        part = chars[index:index + len(clean)]
        if ''.join(c['text'] for c in part) != clean:
            raise ValueError('Word segmentation changed lexical text.')
        words.append({'text': token, 'start': min(c['start'] for c in part), 'end': max(c['end'] for c in part),
                      'source_segment_id': segment.get('id'), 'timing_method': 'Extent of raw forced-aligned character predictions; no duration spreading.',
                      'timing_uncertainty': 'Automatic estimate; zero-length and overlapping predictions are not human-corrected.'})
        index += len(clean)
    index = 0
    for sentence in re.findall(r'[^。！？!?；;]+[。！？!?；;]*|[。！？!?；;]+', restored):
        n = len(lexical(sentence))
        if not n:
            continue
        part = chars[index:index + n]
        sentences.append({'text': sentence, 'start': min(c['start'] for c in part), 'end': max(c['end'] for c in part),
                          'source_segment_id': segment.get('id'), 'punctuation_status': 'Original punctuation retained; terminal full stop appended only if absent, with uncertain segment-based boundary.'})
        index += n
    if index != len(chars):
        raise ValueError('Sentence splitting dropped lexical characters.')
    pauses = []
    lexical_positions = [i for i, char in enumerate(text) if char.isalpha() or char.isdigit()]
    for i, (left, right) in enumerate(zip(chars, chars[1:])):
        between_text = text[lexical_positions[i] + 1:lexical_positions[i + 1]]
        if right['start'] - left['end'] >= 0.3 - 1e-9 and not re.search(r'[。！？!?；;]', between_text):
            between = lexical(text)[:i + 1]
            pauses.append({'start': left['end'], 'end': right['start'], 'after_lexical_prefix': between,
                           'evidence': 'Dedicated forced-aligner estimated inter-character gap, not listening-confirmed silence.'})
    return words, sentences, pauses


def transform_units(records, mapping, offset, speaker, kind):
    output = []
    for record in records:
        spans = mapped_intervals(record['start'], record['end'], mapping, offset)
        if not spans:
            continue
        retained = sum(b - a for a, b in spans)
        if abs(retained - (record['end'] - record['start'])) > 0.0001:
            raise ValueError(f'Cut intersects scored {kind}: {record}')
        output.append({**record, 'source_start': record['start'], 'source_end': record['end'],
                       'start': spans[0][0], 'end': spans[-1][1], 'speaker': speaker, 'score': True})
    return output


def turns_from_labels(context, mapping, offset, target):
    turns = []
    for segment in sorted(context, key=lambda s: (s['start'], s['end'], s['speaker'])):
        spans = mapped_intervals(segment['start'], segment['end'], mapping, offset)
        if not spans:
            continue
        if turns and turns[-1]['speaker'] == segment['speaker']:
            turns[-1]['end'] = max(turns[-1]['end'], spans[-1][1])
            turns[-1]['source_segment_ids'].append(segment['id'])
            turns[-1]['playback_fragments'].extend(spans)
        else:
            turns.append({'speaker': segment['speaker'], 'start': spans[0][0], 'end': spans[-1][1],
                          'score': segment['speaker'] == target, 'source_segment_ids': [segment['id']],
                          'playback_fragments': spans, 'definition': 'A label change in source-onset-ordered human speaker intervals begins a turn; overlap retained, not inferred diarization.'})
    return turns


def render(chunk, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    filters = []
    labels = []
    for i, piece in enumerate(chunk['mapping']):
        label = f'a{i}'
        filters.append(f'[0:a]atrim=start={piece["source_start"]:.9f}:end={piece["source_end"]:.9f},asetpts=PTS-STARTPTS[{label}]')
        labels.append(f'[{label}]')
    filters.append(''.join(labels) + f'concat=n={len(labels)}:v=0:a=1,aresample={RATE},aformat=sample_fmts=s16:channel_layouts=mono[out]')
    raw = output.with_suffix('.raw.wav')
    run(['ffmpeg', '-v', 'error', '-y', '-i', ROOT / chunk['audio'], '-filter_complex', ';'.join(filters), '-map', '[out]', '-c:a', 'pcm_s16le', raw])
    measured = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(raw), '-af', 'loudnorm=I=-23:TP=-2:LRA=11:print_format=json', '-f', 'null', '-'], capture_output=True, check=True).stderr.decode('utf-8', errors='replace')
    match = re.search(r'\{[^{}]*"input_i"[^{}]*\}', measured, re.S)
    if not match:
        raise RuntimeError('ffmpeg did not return loudness measurement.')
    loudness = json.loads(match.group())
    if not math.isfinite(float(loudness['input_i'])):
        raise RuntimeError('Selected clip has no measurable speech loudness.')
    af = ('loudnorm=I=-23:TP=-2:LRA=11:linear=true:'
          f'measured_I={loudness["input_i"]}:measured_TP={loudness["input_tp"]}:measured_LRA={loudness["input_lra"]}:'
          f'measured_thresh={loudness["input_thresh"]}:offset={loudness["target_offset"]},aresample={RATE},'
          f'apad=whole_len={round(chunk["duration"] * RATE)},atrim=end_sample={round(chunk["duration"] * RATE)}')
    run(['ffmpeg', '-v', 'error', '-y', '-i', raw, '-af', af, '-ar', RATE, '-ac', '1', '-c:a', 'pcm_s16le', output])
    raw.unlink()
    with wave.open(str(output), 'rb') as stream:
        if stream.getnframes() != round(chunk['duration'] * RATE):
            raise RuntimeError('Rendered frame count mismatch.')
    return {'path': relative(output), 'sha256': sha256(output), 'frames': round(chunk['duration'] * RATE),
            'sample_rate': RATE, 'channels': 1, 'pcm_bits': 16, 'normalization': 'ffmpeg two-pass EBU R128 -23 LUFS, -2dBTP, LRA11',
            'normalization_measurements': loudness}


def build(args):
    selection = load(META / 'selection.json')
    tracks = {t['id']: t for t in load(META / 'inventory.json')['tracks']}
    bundles = {}
    stress_counts = {}
    for category_group, categories in (('main', {'general', 'stress'}), ('dev', {'dev'})):
        chunks = [c for c in selection['chunks'] if c['category'] in categories]
        offset, rendered, references = 0.0, [], []
        for i, chunk in enumerate(chunks):
            track = tracks[chunk['id']]
            selected = [s for s in track['segments'] if s['start'] >= chunk['source_start'] and s['end'] <= chunk['source_end']]
            words, sentences, pauses = [], [], []
            for segment in selected:
                w, s, p = units(segment, read_alignment(segment))
                words.extend(w)
                sentences.extend(s)
                pauses.extend(p)
            transformed_words = transform_units(words, chunk['mapping'], offset, chunk['speaker'], 'word')
            transformed_sentences = transform_units(sentences, chunk['mapping'], offset, chunk['speaker'], 'sentence')
            transformed_pauses = transform_units(pauses, chunk['mapping'], offset, chunk['speaker'], 'pause')
            context = parse_textgrid(ROOT / chunk['context_textgrid'])
            context_rows = []
            for segment in context:
                if segment['speaker'] == chunk['speaker'] or segment['end'] < chunk['source_start'] - 30 or segment['start'] > chunk['source_end']:
                    continue
                context_rows.append({**segment, 'source_start': segment['start'], 'source_end': segment['end'],
                                     'playback_fragments': mapped_intervals(segment['start'], segment['end'], chunk['mapping'], offset),
                                     'score': False, 'reference_level': 'Human source segment context only; no invented within-segment word timing.'})
            audio = render(chunk, DATA / 'audio' / (chunk['chunk_id'] + '.wav'))
            rendered.append(audio)
            counts = {**chunk['stress_features'], 'estimated_internal_gaps_ge_300ms': len(transformed_pauses)}
            if chunk['category'] == 'stress':
                for key, value in counts.items():
                    stress_counts[key] = stress_counts.get(key, 0) + value
            references.append({**chunk, 'playback_start': offset, 'playback_end': offset + chunk['duration'],
                               'audio': audio, 'mapping': [{**p, 'playback_start': p['playback_start'] + offset,
                                                            'playback_end': p['playback_end'] + offset} for p in chunk['mapping']],
                               'words': transformed_words, 'sentences': transformed_sentences,
                               'raw_human_segments': selected,
                               'turns': turns_from_labels(context, chunk['mapping'], offset, chunk['speaker']),
                               'context': context_rows, 'estimated_internal_pauses': transformed_pauses,
                               'timing_diagnostics': {'zero_length_words': sum(w['start'] == w['end'] for w in transformed_words),
                                                      'overlapping_adjacent_words': sum(a['end'] > b['start'] for a, b in zip(transformed_words, transformed_words[1:]))},
                               'stress_counts': counts,
                               'reference_level': 'Human lexical transcript and speaker labels; original/restored punctuation; automatic dedicated forced-aligner word timing.',
                               'uncertainty': 'No independent listening/transcription validation. Segmentation and forced-alignment errors remain possible. Non-target context words are not scored.'})
            offset += chunk['duration'] + (2 if i < len(chunks) - 1 else 0)
        bundle = DATA / 'audio' / f'zh-{category_group}.wav'
        concatenate(rendered, bundle)
        bundles[category_group] = {'audio': relative(bundle), 'sha256': sha256(bundle), 'duration': offset,
                                  'directions': ['D3', 'D5'], 'chunks': references,
                                  'interchunk_silence_seconds': 2, 'license': LICENSE}
    isolated = make_isolated(selection, tracks)
    main = bundles['main']
    if abs(main['duration'] - 1800) > 0.00001 or abs(bundles['dev']['duration'] - 300) > 0.00001:
        raise RuntimeError('Bundle duration contract violated.')
    general = [c for c in main['chunks'] if c['category'] == 'general']
    casual = sum(c['duration'] for c in general if c['casual_chat'])
    result = {'schema': 'vrc-translator-bench.chinese.v1', 'status': 'local-preparation-not-published',
              'directions': {'D3': {'source': 'main', 'target_language': 'ko'}, 'D5': {'source': 'main', 'target_language': 'ja'}},
              'bundles': bundles, 'isolated_D3': isolated,
              'preparation': {'python': sys.version.split()[0],
                              'packages': {name: importlib.metadata.version(name) for name in ('torch', 'transformers', 'qwen-asr', 'numpy', 'jieba')},
                              'ffmpeg': run(['ffmpeg', '-version']).decode('utf-8').splitlines()[0],
                              'aligner': {'model': MODEL, 'revision': MODEL_REVISION, 'timestamp_interpolation': False}},
              'category_totals': {'general_playback_seconds_including_following_separators': 1200,
                                  'stress_playback_seconds_including_internal_separators': 600,
                                  'general_chunk_audio_seconds_excluding_separators': 1188,
                                  'stress_chunk_audio_seconds_excluding_separators': 596,
                                  'casual_general_audio_proportion': casual / 1188},
              'stress_counts': stress_counts, 'common_clip_shortlist': [c['chunk_id'] for c in main['chunks'][:2]] + [main['chunks'][-1]['chunk_id']],
              'shortlist_status': 'Frozen before application results; no results inspected.',
              'license': LICENSE, 'attribution': 'AliMeeting, Alibaba Group; Yu et al., M2MeT ICASSP 2022; https://www.openslr.org/119/',
              'stress_count_evidence': 'Text-pattern candidate counts and model-estimated internal gaps; not listening-confirmed stress labels.',
              'changes': ['Participant headset selection', 'Other-speaker gap compression retaining 3s and target-silent shoulders',
                          '48kHz mono resampling and -23LUFS normalization', '2s interchunk silence',
                          'Terminal punctuation only where missing; human lexical text unchanged',
                          'Dedicated forced character timing without interpolation; jieba HMM-disabled word segmentation', 'Playback-relative word/sentence/speaker-change turn remapping'],
              'release': {'permission': 'Owner authorized local use only, no upload', 'publication_required': False,
                          'completion_scope': 'Owner revised issue #2 completion to local audio/reference/checksum/rights-and-unresolved-record preparation.',
                          'derived_audio_and_timelines_license': LICENSE}}
    save(META / 'manifest.json', result)
    print(json.dumps({'main_seconds': main['duration'], 'dev_seconds': bundles['dev']['duration'],
                      'isolated_count': len(isolated), 'stress_counts': stress_counts, 'casual_proportion': casual / 1188}, indent=2))


def concatenate(assets, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    silence = b'\0' * (RATE * 2 * 2)
    with wave.open(str(output), 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        for i, asset in enumerate(assets):
            with wave.open(str(ROOT / asset['path']), 'rb') as inp:
                if inp.getparams()[:3] != (1, 2, RATE):
                    raise ValueError('Unexpected chunk format.')
                while data := inp.readframes(RATE):
                    out.writeframesraw(data)
            if i < len(assets) - 1:
                out.writeframesraw(silence)


def make_isolated(selection, tracks):
    pool = []
    for candidate in selection['heldout_candidates']:
        segment = candidate['segment']
        words, sentences, pauses = units(segment, read_alignment(segment))
        seconds = segment['end'] - segment['start']
        tags = (['short'] if seconds <= 2 else []) + (['long'] if seconds >= 6 else []) + (['internally-paused-alignment-estimated'] if pauses else [])
        pool.append((candidate, words, sentences, pauses, tags))
    chosen = []
    for required in ('short', 'long', 'internally-paused-alignment-estimated'):
        available = [x for x in pool if required in x[4] and x not in chosen]
        if not available:
            raise RuntimeError(f'Heldout pool lacks {required}; do not fabricate an isolated category.')
        chosen.append(available[0])
    chosen.extend(x for x in pool if x not in chosen)
    if len(chosen) < 20:
        raise RuntimeError('Fewer than 20 genuine heldout utterances.')
    result = []
    for i, (candidate, words, sentences, pauses, tags) in enumerate(chosen[:20]):
        segment = candidate['segment']
        track = tracks[candidate['track_id']]
        previous = max((s['end'] for s in track['segments'] if s['end'] <= segment['start']), default=0)
        following = min((s['start'] for s in track['segments'] if s['start'] >= segment['end']), default=track['duration'])
        start = max(0, segment['start'] - min(0.1, (segment['start'] - previous) / 2))
        end = min(track['duration'], segment['end'] + min(0.1, (following - segment['end']) / 2))
        chunk = {**{k: v for k, v in track.items() if k != 'segments'}, 'duration': end - start,
                 'source_start': start, 'source_end': end, 'mapping': retained_map(start, end, [])}
        audio = render(chunk, DATA / 'audio' / f'zh-isolated-{i + 1:02}.wav')
        result.append({**chunk, 'clip_id': f'zh-isolated-{i + 1:02}', 'audio': audio, 'tags': tags,
                       'raw_text': segment['text'], 'words': transform_units(words, chunk['mapping'], 0, track['speaker'], 'word'),
                       'sentences': transform_units(sentences, chunk['mapping'], 0, track['speaker'], 'sentence'),
                       'estimated_internal_pauses': transform_units(pauses, chunk['mapping'], 0, track['speaker'], 'pause'),
                       'turns': [{'speaker': track['speaker'], 'start': segment['start'] - start, 'end': segment['end'] - start, 'score': True}],
                       'reference_uncertainty': 'Human text; automatically estimated word times and internal gaps, not listening-confirmed.'})
    return result


def main():
    parser = argparse.ArgumentParser(description='Prepare original AliMeeting Eval headsets locally for shared D3/D5 playback. Audio/model/cache remain in .data/chinese.')
    commands = parser.add_subparsers(dest='command', required=True)
    for name, fn in (('acquire', acquire), ('inventory', inventory), ('select', select), ('align', align), ('build', build)):
        child = commands.add_parser(name)
        child.set_defaults(fn=fn)
        if name == 'select':
            child.add_argument('--curation', type=Path, default=META / 'curation.json')
        if name == 'align':
            child.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    args.fn(args)


if __name__ == '__main__':
    main()
