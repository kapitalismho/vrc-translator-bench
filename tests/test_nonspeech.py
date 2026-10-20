import importlib.util
from pathlib import Path

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location("prepare_nonspeech", Path(__file__).resolve().parents[1] / "tools/prepare_nonspeech.py")
nonspeech = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nonspeech)


def test_assembly_keeps_noise_and_conversation_in_separate_scoring_windows():
    rate = nonspeech.RATE
    inputs = {
        "keyboard": np.full(30 * rate, 0.1, dtype=np.float32),
        "coin": np.full(rate, -0.1, dtype=np.float32),
        "snap": np.full(2 * rate, 0.2, dtype=np.float32),
        "background": np.tile(np.array([-0.1, 0.1], dtype=np.float32), 30 * rate),
    }
    audio, events = nonspeech.assemble(inputs)
    assert audio.shape == (180 * rate,)
    np.testing.assert_array_equal(audio[:60 * rate], 0)
    np.testing.assert_array_equal(audio[60 * rate:90 * rate], 0.5)
    np.testing.assert_array_equal(audio[90 * rate:91 * rate], -0.5)
    np.testing.assert_array_equal(audio[91 * rate:100 * rate], 0)
    np.testing.assert_array_equal(audio[100 * rate:102 * rate], 0.5)
    np.testing.assert_array_equal(audio[102 * rate:120 * rate], 0)
    np.testing.assert_allclose(audio[120 * rate:], inputs["background"] * (10 ** (-30 / 20) / 0.1), rtol=1e-6)
    assert [(event["source_id"], event["source_start_seconds"], event["source_end_seconds"],
             event["playback_start_sample"], event["playback_end_sample"])
            for event in events] == [
        ("keyboard", 10, 40, 60 * rate, 90 * rate),
        ("coin", 0, 1, 90 * rate, 91 * rate),
        ("snap", 0, 2, 100 * rate, 102 * rate),
        ("background", 120, 180, 120 * rate, 180 * rate),
    ]


def test_background_gain_does_not_clip_high_crest_factor_recording():
    data = np.zeros(48000, dtype=np.float32)
    data[24000] = 1
    normalized, gain = nonspeech.normalize(data, rms=10 ** (-30 / 20))
    assert normalized[24000] == 0.5
    assert gain == 0.5
    assert np.count_nonzero(normalized) == 1
    with pytest.raises(ValueError, match="digital silence"):
        nonspeech.normalize(np.zeros(48000, dtype=np.float32))
