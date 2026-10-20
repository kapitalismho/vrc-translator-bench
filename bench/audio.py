from __future__ import annotations

import json
import os
import threading
import time
import wave
from pathlib import Path

from .adapter import OperationalError
from .storage import atomic_json, digest, utc_now


def wave_info(path):
    with wave.open(str(path), "rb") as source:
        if source.getcomptype() != "NONE" or source.getsampwidth() != 2 or source.getnchannels() not in (1, 2):
            raise ValueError("Playback requires mono/stereo uncompressed PCM16 WAV")
        return {"sample_rate": source.getframerate(), "channels": source.getnchannels(),
                "frames": source.getnframes(), "duration_seconds": source.getnframes() / source.getframerate()}


def _modules():
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError:
        raise OperationalError("Install the audio extra: pip install -e .[audio]") from None
    return np, sd


def cable_devices(output_device=None, input_device=None):
    _, sd = _modules()
    if os.name != "nt":
        raise OperationalError("Cable playback requires Windows WASAPI shared mode")
    try:
        devices = sd.query_devices()
        apis = sd.query_hostapis()
    except sd.PortAudioError as error:
        raise OperationalError(f"Cannot enumerate Windows audio devices: {error}") from error
    def choose(selected, fragment, channel_key):
        found = [(index, dict(device)) for index, device in enumerate(devices)
                 if apis[device["hostapi"]]["name"] == "Windows WASAPI"
                 and fragment in device["name"] and "16ch" not in device["name"]
                 and device[channel_key] > 0
                 and (selected is None or str(index) == str(selected) or device["name"] == selected)]
        if len(found) != 1:
            raise OperationalError(f"Select exactly one WASAPI {fragment} device; matches={found}")
        return found[0]
    return {"output": choose(output_device, "CABLE Input", "max_output_channels"),
            "input": choose(input_device, "CABLE Output", "max_input_channels"), "exclusive": False}


class Playback:
    def __init__(self, path, output_device=None):
        self.path = Path(path)
        self.info = wave_info(path)
        self.devices = cable_devices(output_device)
        self.records = []
        self.failure = None
        self.done = threading.Event()
        self.position = 0
        self.first_dac_ns = None
        self.finished_ns = None
        self.source = wave.open(str(path), "rb")
        np, sd = _modules()
        self.np = np
        self.sd = sd
        try:
            self.stream = sd.OutputStream(device=self.devices["output"][0], samplerate=self.info["sample_rate"],
                                          channels=self.info["channels"], dtype="int16", blocksize=0,
                                          extra_settings=sd.WasapiSettings(exclusive=False),
                                          callback=self._callback, finished_callback=self.done.set)
        except sd.PortAudioError as error:
            self.source.close()
            raise OperationalError(f"Cannot open shared cable playback: {error}") from error

    def _callback(self, outdata, frames, timing, status):
        try:
            self._render(outdata, frames, timing, status)
        except (self.sd.CallbackStop, self.sd.CallbackAbort):
            raise
        except Exception as error:
            self.failure = OperationalError(f"Playback callback failed: {error}")
            raise self.sd.CallbackAbort from error

    def _render(self, outdata, frames, timing, status):
        callback_ns = time.perf_counter_ns()
        dac_ns = callback_ns + round((timing.outputBufferDacTime - timing.currentTime) * 1e9)
        if self.first_dac_ns is None:
            self.first_dac_ns = dac_ns
        raw = self.source.readframes(frames)
        values = self.np.frombuffer(raw, dtype="int16").reshape(-1, self.info["channels"])
        count = len(values)
        outdata.fill(0)
        outdata[:count] = values
        self.records.append({"callback_t_ns": callback_ns, "dac_t_ns": dac_ns,
                             "portaudio_current_time": timing.currentTime, "portaudio_output_dac_time": timing.outputBufferDacTime,
                             "source_frame": self.position, "source_frames": count, "callback_frames": frames,
                             "status": str(status)})
        self.position += count
        if status:
            self.failure = OperationalError(f"Playback callback status: {status}")
            raise self.sd.CallbackAbort
        if count < frames or self.position == self.info["frames"]:
            self.finished_ns = dac_ns + round(count / self.info["sample_rate"] * 1e9)
            raise self.sd.CallbackStop

    def start(self):
        try:
            self.stream.start()
        except self.sd.PortAudioError as error:
            raise OperationalError(f"Cannot start shared cable playback: {error}") from error

    def check(self):
        if self.failure:
            raise self.failure
        if self.done.is_set() and self.position < self.info["frames"]:
            raise OperationalError("Playback stopped before all source frames were submitted")

    def close(self):
        try:
            self.stream.close()
        except self.sd.PortAudioError as error:
            raise OperationalError(f"Cannot close shared cable playback: {error}") from error
        finally:
            self.source.close()


class ClockPlayback:
    def __init__(self, path, output_device=None):
        self.info = wave_info(path)
        self.records = []
        self.first_dac_ns = None
        self.finished_ns = None
        self.done = threading.Event()
        self.devices = {"synthetic": True}

    def start(self):
        self.first_dac_ns = time.perf_counter_ns()
        self.finished_ns = self.first_dac_ns + round(self.info["duration_seconds"] * 1e9)
        self.records.append({"synthetic_start_t_ns": self.first_dac_ns, "frames": self.info["frames"], "actual_dac_observed": False})

    def check(self):
        if self.first_dac_ns is not None and time.perf_counter_ns() >= self.finished_ns:
            self.done.set()

    def close(self):
        pass


def calibrate(output, output_device=None, input_device=None, sample_rate=48000):
    np, sd = _modules()
    devices = cable_devices(output_device, input_device)
    duration = 3
    frames = sample_rate * duration
    rng = np.random.default_rng(301)
    signal = np.zeros(frames, dtype="float32")
    start = sample_rate // 2
    probe = rng.uniform(-0.07, 0.07, sample_rate // 5).astype("float32")
    probe *= np.hanning(len(probe)).astype("float32")
    signal[start:start + len(probe)] = probe
    received = np.zeros(frames, dtype="float32")
    records = []
    position = 0
    done = threading.Event()
    failure = []
    def callback(indata, outdata, count, timing, status):
        nonlocal position
        callback_ns = time.perf_counter_ns()
        length = min(count, frames - position)
        outdata.fill(0)
        outdata[:length, 0] = signal[position:position + length]
        received[position:position + length] = indata[:length, 0]
        records.append({"frame": position, "frames": length, "callback_t_ns": callback_ns,
                        "adc_t_ns": callback_ns + round((timing.inputBufferAdcTime - timing.currentTime) * 1e9),
                        "dac_t_ns": callback_ns + round((timing.outputBufferDacTime - timing.currentTime) * 1e9),
                        "portaudio_current_time": timing.currentTime, "portaudio_input_adc_time": timing.inputBufferAdcTime,
                        "portaudio_output_dac_time": timing.outputBufferDacTime, "status": str(status)})
        position += length
        if status:
            failure.append(str(status))
            raise sd.CallbackAbort
        if position >= frames:
            raise sd.CallbackStop
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    try:
        with sd.Stream(device=(devices["input"][0], devices["output"][0]), samplerate=sample_rate,
                       channels=(1, 1), dtype="float32", blocksize=0,
                       extra_settings=(sd.WasapiSettings(exclusive=False), sd.WasapiSettings(exclusive=False)),
                       callback=callback, finished_callback=done.set):
            if not done.wait(duration + 10):
                raise OperationalError("Cable calibration timed out")
    except sd.PortAudioError as error:
        raise OperationalError(f"Shared cable calibration failed: {error}") from error
    if failure or position != frames:
        raise OperationalError(f"Cable calibration callback failure: {failure}")
    nfft = 1 << (len(received) + len(probe) - 2).bit_length()
    correlation = np.fft.irfft(np.fft.rfft(received, nfft) * np.fft.rfft(probe[::-1], nfft), nfft)
    arrival_frame = int(np.argmax(np.abs(correlation))) - len(probe) + 1
    if arrival_frame < 0 or arrival_frame + len(probe) > len(received):
        raise OperationalError("Cable calibration did not locate a complete probe")
    observed = received[arrival_frame:arrival_frame + len(probe)]
    normalized = float(abs(np.dot(observed, probe)) / max(float(np.linalg.norm(observed) * np.linalg.norm(probe)), 1e-20))
    if normalized < 0.5:
        raise OperationalError(f"Cable probe not identifiable; normalized correlation={normalized}")
    def frame_time(frame, key):
        record = next(record for record in records if record["frame"] <= frame < record["frame"] + record["frames"])
        return record[key] + round((frame - record["frame"]) / sample_rate * 1e9)
    sent_ns = frame_time(start, "dac_t_ns")
    arrival_ns = frame_time(arrival_frame, "adc_t_ns")
    offset_ns = arrival_ns - sent_ns
    if not -20_000_000 <= offset_ns <= 2_000_000_000:
        raise OperationalError(f"Cable path offset is implausible: {offset_ns} ns")
    raw = output.with_suffix(".npz")
    np.savez_compressed(raw, emitted=signal, captured=received)
    report = {"schema_version": 1, "status": "measured", "offset_ns": offset_ns,
              "convention": "source_at_capture_ns = playback_dac_ns + source_frame/sample_rate*1e9 + offset_ns",
              "method": "single bounded shared-mode cable probe, normalized cross-correlation; not precision certification",
              "normalized_correlation": normalized, "probe_dac_ns": sent_ns, "probe_capture_ns": arrival_ns,
              "arrival_frame": arrival_frame, "probe_frame": start, "sample_rate": sample_rate,
              "devices": devices, "wall_start": started, "wall_end": utc_now(), "callbacks": records,
              "raw_evidence": {"path": raw.name, "sha256": digest(raw)}}
    atomic_json(output, report)
    return report
