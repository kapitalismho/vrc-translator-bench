import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import wave

import pytest


SOURCE = Path(__file__).resolve().parents[1] / 'tools' / 'prepare_chinese.py'
spec = importlib.util.spec_from_file_location('prepare_chinese', SOURCE)
chinese = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chinese)


def segment(speaker, start, end, text='你好。', ident='s1'):
    return {'id': ident, 'speaker': speaker, 'start': start, 'end': end, 'text': text}


def test_gap_compression_keeps_target_pauses_and_other_speaker_shoulders():
    target = [segment('A', 0, 2), segment('A', 4, 6), segment('A', 20, 22)]
    context = target + [segment('B', 8, 18)]
    cuts = chinese.compression_cuts(target, context, 0, 22)
    assert [(c['start'], c['end']) for c in cuts] == [(9.5, 16.5)]
    mapping = chinese.retained_map(0, 22, cuts)
    assert chinese.mapped_intervals(2, 4, mapping) == [[2, 4]]
    assert chinese.mapped_intervals(6, 8, mapping) == [[6, 8]]
    assert chinese.mapped_intervals(18, 20, mapping) == [[11, 13]]
    assert chinese.mapped_intervals(20, 22, mapping) == [[13, 15]]
    assert mapping[-1]['playback_end'] == 15


def test_overlap_never_removes_target_speech():
    target = [segment('A', 0, 10), segment('A', 15, 20)]
    context = target + [segment('B', 8, 16)]
    cuts = chinese.compression_cuts(target, context, 0, 20)
    assert [(c['start'], c['end']) for c in cuts] == [(11.5, 13.5)]
    assert all(not (c['start'] < t['end'] and c['end'] > t['start']) for c in cuts for t in target)


def test_remaps_word_sentence_and_turn_after_cut_and_chunk_offset():
    mapping = chinese.retained_map(10, 40, [{'start': 15, 'end': 25}])
    target_word = {'text': '朋友', 'start': 30, 'end': 31}
    words = chinese.transform_units([target_word], mapping, 202, 'A', 'word')
    assert [(w['start'], w['end'], w['source_start'], w['source_end']) for w in words] == [(212, 213, 30, 31)]
    sentences = chinese.transform_units([{'text': '你好，朋友。', 'start': 28, 'end': 32}], mapping, 202, 'A', 'sentence')
    assert [(s['start'], s['end']) for s in sentences] == [(210, 214)]
    context = [segment('A', 11, 12, ident='a'), segment('A', 13, 14, ident='b'),
               segment('B', 14, 28, ident='c'), segment('A', 30, 32, ident='d')]
    turns = chinese.turns_from_labels(context, mapping, 202, 'A')
    assert [t['speaker'] for t in turns] == ['A', 'B', 'A']
    assert turns[0]['source_segment_ids'] == ['a', 'b']
    assert turns[1]['playback_fragments'] == [[206, 207], [207, 210]]
    assert turns[2]['start'] == 212
    assert [t['score'] for t in turns] == [True, False, True]


def test_rejects_cut_across_scored_lexical_reference():
    mapping = chinese.retained_map(0, 10, [{'start': 4, 'end': 7}])
    with pytest.raises(ValueError, match='Cut intersects scored word'):
        chinese.transform_units([{'text': '不能切词', 'start': 3, 'end': 8}], mapping, 0, 'A', 'word')


def test_word_times_are_raw_predictions_not_uniform_sentence_division():
    from types import SimpleNamespace
    items = [SimpleNamespace(text='你', start_time=0.1, end_time=0.2),
             SimpleNamespace(text='好', start_time=0.9, end_time=1.1)]
    chars = chinese.predicted_characters(items, '你好。', 10, 12)
    assert [(c['start'], c['end']) for c in chars] == [(10.1, 10.2), (10.9, 11.1)]
    with pytest.raises(ValueError, match='changed or dropped'):
        chinese.predicted_characters(items[:1], '你好。', 10, 12)
    items[0].end_time = -1
    with pytest.raises(ValueError, match='refusing interpolation'):
        chinese.predicted_characters(items, '你好。', 10, 12)


def test_ctc_repair_uses_acoustic_path_and_keeps_repeated_characters():
    np = pytest.importorskip('numpy')
    probabilities = np.full((12, 3), -20.0)
    for frame, token in enumerate([0, 1, 1, 0, 0, 0, 0, 0, 2, 2, 0, 0]):
        probabilities[frame, token] = 0
    assert chinese.ctc_path(probabilities, [1, 2], 0) == [(1, 3), (8, 10)]
    repeated = np.full((5, 2), -20.0)
    repeated[[0, 2, 4], 0] = 0
    repeated[[1, 3], 1] = 0
    assert chinese.ctc_path(repeated, [1, 1], 0) == [(1, 2), (3, 4)]
    with pytest.raises(ValueError, match='No monotone CTC path'):
        chinese.ctc_path(probabilities[:1], [1, 2], 0)


def test_zero_length_raw_prediction_is_retained_as_uncertain_point():
    mapping = chinese.retained_map(10, 20, [])
    result = chinese.transform_units([{'text': '嗯', 'start': 12, 'end': 12}], mapping, 202, 'A', 'word')
    assert [(w['start'], w['end'], w['text']) for w in result] == [(204, 204, '嗯')]


def test_punctuation_and_word_segmentation_preserve_human_lexical_text():
    pytest.importorskip('jieba')
    text = '你好，朋友。嗯，好'
    chars = [{'text': c, 'start': i, 'end': i + 0.1}
             for i, c in enumerate(chinese.lexical(text))]
    words, sentences, pauses = chinese.units({'text': text}, chars)
    assert ''.join(chinese.lexical(w['text']) for w in words) == chinese.lexical(text)
    assert ''.join(s['text'] for s in sentences) == text + '。'
    assert [(s['start'], s['end']) for s in sentences] == [(0, 3.1), (4, 5.1)]
    assert len(pauses) == 4


def test_textgrid_uses_headset_identity_not_generic_tier_name(tmp_path):
    path = tmp_path / 'R0001_M0001_F_SPK0001.TextGrid'
    path.write_text('''File type = "ooTextFile"
Object class = "TextGrid"
item []:
    item [1]:
        class = "IntervalTier"
        name = "c1"
        intervals [1]:
            xmin = 1.25
            xmax = 2.75
            text = "他说""你好""。"
        intervals [2]:
            xmin = 2.75
            xmax = 4
            text = ""
''', encoding='utf-8')
    result = chinese.parse_textgrid(path, 'SPK0001')
    assert result[0]['speaker'] == 'SPK0001'
    assert result[0]['text'] == '他说"你好"。'
    assert len(result) == 1


def test_concatenation_inserts_exact_two_seconds_and_retains_pcm(tmp_path, monkeypatch):
    monkeypatch.setattr(chinese, 'ROOT', tmp_path)
    assets = []
    for name, sample in [('one.wav', b'\x01\x00'), ('two.wav', b'\x02\x00')]:
        with wave.open(str(tmp_path / name), 'wb') as stream:
            stream.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
            stream.writeframes(sample * 48000)
        assets.append({'path': name})
    out = tmp_path / 'bundle.wav'
    chinese.concatenate(assets, out)
    with wave.open(str(out), 'rb') as stream:
        assert stream.getnframes() == 192000
        assert stream.readframes(48000) == b'\x01\x00' * 48000
        assert stream.readframes(96000) == b'\0' * 192000
        assert stream.readframes(48000) == b'\x02\x00' * 48000


@pytest.fixture
def local_smoke_checkout(tmp_path):
    root = SOURCE.parents[1]
    for name in ('tools/prepare_chinese.py', 'tests/test_chinese_real.py', 'corpus/chinese/manifest.json'):
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, destination)
    return tmp_path


def test_local_smoke_skips_tracked_manifest_without_ignored_audio(local_smoke_checkout):
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', '-q', '-rs', 'tests/test_chinese_real.py'],
        cwd=local_smoke_checkout, capture_output=True, text=True, encoding='utf-8',
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '4 skipped' in result.stdout
    assert 'Local AliMeeting main WAV is absent' in result.stdout
    assert not (local_smoke_checkout / '.data').exists()


@pytest.mark.parametrize('test_name', [
    'test_real_d3_d5_bundles_have_exact_frames_and_separators',
    'test_real_transformed_words_match_human_text_and_piecewise_map',
])
def test_local_smoke_does_not_skip_corrupt_or_incomplete_preparation(local_smoke_checkout, test_name):
    audio = local_smoke_checkout / '.data/chinese/audio/zh-main.wav'
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b'corrupt local audio')
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', '-q', f'tests/test_chinese_real.py::{test_name}'],
        cwd=local_smoke_checkout, capture_output=True, text=True, encoding='utf-8',
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert '1 failed' in result.stdout
    assert 'skipped' not in result.stdout
