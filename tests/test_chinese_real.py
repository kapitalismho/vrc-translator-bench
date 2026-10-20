import importlib.util
from pathlib import Path
import wave

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('chinese_real', ROOT / 'tools' / 'prepare_chinese.py')
chinese = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chinese)
MANIFEST = ROOT / 'corpus' / 'chinese' / 'manifest.json'
pytestmark = pytest.mark.skipif(
    not (ROOT / '.data/chinese/audio/zh-main.wav').is_file(),
    reason='Local AliMeeting main WAV is absent (.data/chinese/audio/zh-main.wav); run Chinese preparation to enable these real-data smoke tests.',
)


def test_real_d3_d5_bundles_have_exact_frames_and_separators():
    manifest = chinese.load(MANIFEST)
    assert manifest['directions']['D3']['source'] == manifest['directions']['D5']['source'] == 'main'
    for name, seconds in [('main', 1800), ('dev', 300)]:
        bundle = manifest['bundles'][name]
        with wave.open(str(ROOT / bundle['audio']), 'rb') as stream:
            assert stream.getparams()[:3] == (1, 2, 48000)
            assert stream.getnframes() == seconds * 48000
            for chunk in bundle['chunks'][:-1]:
                stream.setpos(round(chunk['playback_end'] * 48000))
                assert stream.readframes(96000) == b'\0' * 192000
        assert chinese.sha256(ROOT / bundle['audio']) == bundle['sha256']


def test_real_transformed_words_match_human_text_and_piecewise_map():
    manifest = chinese.load(MANIFEST)
    tracks = {t['id']: t for t in chinese.load(ROOT / 'corpus/chinese/inventory.json')['tracks']}
    for chunk in manifest['bundles']['main']['chunks'][:3]:
        target = [s for s in tracks[chunk['id']]['segments'] if chunk['source_start'] <= s['start'] and s['end'] <= chunk['source_end']]
        assert ''.join(chinese.lexical(w['text']) for w in chunk['words']) == ''.join(chinese.lexical(s['text']) for s in target)
        assert ''.join(chinese.lexical(s['text']) for s in chunk['sentences']) == ''.join(chinese.lexical(s['text']) for s in target)
        for unit in chunk['words'] + chunk['sentences']:
            spans = chinese.mapped_intervals(unit['source_start'], unit['source_end'], chunk['mapping'])
            assert spans
            assert unit['start'] == pytest.approx(spans[0][0], abs=1e-7)
            assert unit['end'] == pytest.approx(spans[-1][1], abs=1e-7)
            assert chunk['playback_start'] <= unit['start'] <= unit['end'] <= chunk['playback_end']
            assert unit['speaker'] == chunk['speaker'] and unit['score']
        assert chunk['removed_gaps']
        assert any(not c['score'] for c in chunk['context'])
        with wave.open(str(ROOT / chunk['audio']['path']), 'rb') as stream:
            assert stream.getnframes() == round(chunk['duration'] * 48000)
            frames = stream.readframes(stream.getnframes())
            assert any(frames)
        assert chinese.sha256(ROOT / chunk['audio']['path']) == chunk['audio']['sha256']


def test_real_waveform_is_the_mapped_headset_not_just_correct_length():
    np = pytest.importorskip('numpy')
    manifest = chinese.load(MANIFEST)
    tracks = {t['id']: t for t in chinese.load(ROOT / 'corpus/chinese/inventory.json')['tracks']}
    for chunk in manifest['bundles']['main']['chunks'][:3]:
        pieces = [p for p in chunk['mapping'] if p['source_end'] - p['source_start'] >= 2]
        assert pieces
        for piece in (pieces[0], pieces[-1]):
            source_start = (piece['source_start'] + piece['source_end']) / 2
            local_start = piece['playback_start'] - chunk['playback_start'] + source_start - piece['source_start']
            source_pcm = chinese.run(['ffmpeg', '-v', 'error', '-ss', source_start, '-i', ROOT / tracks[chunk['id']]['audio'], '-t', 0.25,
                                      '-ar', 48000, '-ac', 1, '-f', 'f32le', 'pipe:1'])
            source = np.frombuffer(source_pcm, dtype='<f4').astype(float)
            with wave.open(str(ROOT / chunk['audio']['path']), 'rb') as stream:
                stream.setpos(round(local_start * 48000))
                playback = np.frombuffer(stream.readframes(len(source)), dtype='<i2').astype(float)
            assert np.std(source) > 0 and np.std(playback) > 0
            correlation = float(np.corrcoef(source, playback)[0, 1])
            assert correlation > 0.98, (chunk['chunk_id'], source_start, correlation)


def test_real_dev_isolated_and_main_sessions_are_disjoint():
    manifest = chinese.load(MANIFEST)
    main = {c['session'] for c in manifest['bundles']['main']['chunks']}
    dev = {c['session'] for c in manifest['bundles']['dev']['chunks']}
    heldout = manifest['isolated_D3']
    isolated_sessions = {c['session'] for c in heldout}
    assert main.isdisjoint(dev) and main.isdisjoint(isolated_sessions) and dev.isdisjoint(isolated_sessions)
    assert len(heldout) == 20
    tags = {tag for clip in heldout for tag in clip['tags']}
    assert {'short', 'long', 'internally-paused-alignment-estimated'} <= tags
    assert len({c['speaker'] for c in manifest['bundles']['main']['chunks']}) > 1
    for clip in heldout:
        assert ''.join(chinese.lexical(w['text']) for w in clip['words']) == chinese.lexical(clip['raw_text'])
        with wave.open(str(ROOT / clip['audio']['path']), 'rb') as stream:
            assert stream.getnframes() == round(clip['duration'] * 48000)
        assert chinese.sha256(ROOT / clip['audio']['path']) == clip['audio']['sha256']
